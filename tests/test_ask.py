"""Ask-mode helpers: request intake, atomic state, and error text."""
import json
import runpy
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ENGINE = runpy.run_path(str(ROOT / "voiceime-engine"))
# runpy returns a copy, so patch the shared function globals, not ENGINE itself.
GLOBALS = ENGINE["take_ask_request"].__globals__


class AskRequestTests(unittest.TestCase):
    def test_request_is_read_then_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voiceime-ask.request"
            path.write_text(json.dumps({"selection": "选中文字"}), encoding="utf-8")
            with patch.dict(GLOBALS, ASK_REQUEST_FILE=path):
                self.assertEqual(ENGINE["take_ask_request"](), {"selection": "选中文字"})
                self.assertIsNone(ENGINE["take_ask_request"]())
            self.assertFalse(path.exists())

    def test_missing_or_malformed_request_is_none(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(GLOBALS, ASK_REQUEST_FILE=Path(directory) / "absent"):
                self.assertIsNone(ENGINE["take_ask_request"]())
            bad = Path(directory) / "bad"
            bad.write_text("{not json", encoding="utf-8")
            with patch.dict(GLOBALS, ASK_REQUEST_FILE=bad):
                self.assertIsNone(ENGINE["take_ask_request"]())


class AskStateTests(unittest.TestCase):
    def test_state_write_is_atomic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "voiceime-ask.state"
            with patch.dict(GLOBALS, ASK_STATE_FILE=path):
                ENGINE["write_ask_state"]("s1", "done", question="问", answer="答")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["session"], "s1")
            self.assertEqual(data["status"], "done")
            self.assertEqual(data["question"], "问")
            self.assertEqual(data["answer"], "答")
            self.assertTrue(data["time"] > 0)
            self.assertFalse((Path(directory) / "voiceime-ask.state.tmp").exists())

    def test_run_ask_utterance_publishes_answer_without_fcitx(self):
        globals_ = ENGINE["run_ask_utterance"].__globals__

        class FakePipe:
            def fileno(self):
                return 0

        class FakeRecorder:
            stdout = FakePipe()

            def poll(self):
                return None

        class FakePoll:
            def register(self, *_args):
                pass

            def poll(self, _timeout):
                return []

        class FakeAsr:
            def create_stream(self):
                return object()

            def accept_pcm(self, *_args):
                pass

            def decode_ready(self, *_args):
                pass

            def text(self, _stream):
                return "这句话什么意思"

            def finalize(self, _stream):
                return "这句话什么意思"

        calls = {}

        class FakeLLM:
            enabled = True
            last_status = "success"

            def answer(self, question, selection):
                calls["question"] = question
                calls["selection"] = selection
                return "意思是部署已经完成。"

        fake_select = types.SimpleNamespace(
            POLLIN=1, POLLHUP=2, POLLERR=4, poll=lambda: FakePoll()
        )
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "voiceime-ask.state"
            with patch.dict(globals_, {
                "ASK_STATE_FILE": state,
                "STATE_FILE": Path(directory) / "engine.state",
                "start_recorder": lambda _mic: FakeRecorder(),
                "stop_recorder": lambda _proc: b"",
                "resolve_mic": lambda: "",
                "select": fake_select,
                "terminate": False,
                "start_request": 5,
                "stop_request": 5,
                "RELEASE_SILENCE_SEC": 0.0,
            }):
                ENGINE["run_ask_utterance"](
                    FakeAsr(), FakeLLM(),
                    {"selection": "部署已经完成\n第二行"}, 5,
                )
            data = json.loads(state.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["question"], "这句话什么意思")
        self.assertEqual(data["answer"], "意思是部署已经完成。")
        self.assertEqual(calls["question"], "这句话什么意思")
        self.assertEqual(calls["selection"], "部署已经完成\n第二行")

    def test_error_message_maps_status(self):
        class FakeLLM:
            last_status = "unavailable"

        llm = FakeLLM()
        message = ENGINE["ask_error_message"]
        self.assertIn("DEEPSEEK_API_KEY", message(llm))
        llm.last_status = "timeout"
        self.assertIn("超时", message(llm))
        llm.last_status = "failed"
        self.assertIn("重试", message(llm))


if __name__ == "__main__":
    unittest.main()
