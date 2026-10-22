"""Cloud stalls must not stall subsequent push-to-talk utterances."""
import os
from pathlib import Path
import runpy
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ENGINE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "baogu-engine"))


class BridgeContextTests(unittest.TestCase):
    def bridge(self):
        bridge = ENGINE["FcitxBridge"].__new__(ENGINE["FcitxBridge"])
        bridge._bus = bridge._gio = None
        return bridge

    def test_old_bridge_fails_back_to_no_context(self):
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=1, stdout="")):
            self.assertEqual(self.bridge().context("session"), {})

    def test_busctl_preserves_quoted_context_and_caps_unicode(self):
        import json
        reply = "sss " + " ".join(json.dumps(x, ensure_ascii=False) for x in
                                  ('editor', '前' * 700, 'echo "hello"'))
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=reply)):
            self.assertEqual(self.bridge().context("session"), {
                "app": "editor", "before": "前" * 500, "after": 'echo "hello"'})


class BoundedCleanupTests(unittest.TestCase):
    def exercise_stalled_request(self, supersede=False):
        cleanup = ENGINE["_bounded_llm_text"]
        release = threading.Event()
        entered = threading.Event()
        calls = []

        class SlowCloud:
            timeout = 5
            last_status = "success"

            def correct(self, text):
                calls.append(text)
                entered.set()
                release.wait(2)
                return "迟到的结果"

        with patch.dict(cleanup.__globals__, current_session="s", start_request=1,
                        terminate=False, llm_inflight=None, llm_executor=None), \
                patch.dict(os.environ, BAOGU_LLM_MAX_WAIT="0.08" if not supersede else "1"):
            cloud = SlowCloud()
            timer = None
            if supersede:
                def next_press():
                    entered.wait(1)
                    cleanup.__globals__["start_request"] = 2
                timer = threading.Thread(target=next_press)
                timer.start()
            started = time.monotonic()
            try:
                result, status = cleanup("s", 1, "完整原文", cloud)
                self.assertLess(time.monotonic() - started, .5)
                self.assertEqual(result, "完整原文")
                self.assertEqual(status, "superseded" if supersede else "timeout")
                # A subsequent utterance keeps its own text and does not
                # accumulate HTTP work behind the abandoned request.
                self.assertEqual(cleanup("s", 2, "下一句", cloud), ("下一句", "busy"))
                self.assertEqual(calls, ["完整原文"])
            finally:
                release.set()
                if timer:
                    timer.join()
                executor = cleanup.__globals__["llm_executor"]
                if executor:
                    executor.shutdown(wait=True)

    def test_timeout_falls_back_without_queueing_next_utterance(self):
        self.exercise_stalled_request()

    def test_next_press_interrupts_cloud_wait(self):
        self.exercise_stalled_request(supersede=True)


if __name__ == "__main__":
    unittest.main()
