"""Offline candidate harness: audio format and local-only inference contract."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNNER = runpy.run_path(str(ROOT / "scripts/22-benchmark-candidates.py"))


class CandidateTests(unittest.TestCase):
    def test_whisper_receives_normalized_pcm_and_transcribes_without_download(self):
        model = Mock()
        model.transcribe.return_value = (
            iter([SimpleNamespace(text="你好"), SimpleNamespace(text=" GitHub")]), None)
        factory = Mock(return_value=model)
        args = SimpleNamespace(backend="whisper", model=Path("/local/model"),
                               device="cuda", compute_type="int8_float16",
                               language=None, context="")
        with patch.dict("sys.modules", faster_whisper=SimpleNamespace(WhisperModel=factory)):
            candidate = RUNNER["Candidate"](args)
            result = candidate.transcribe(np.array([-32768, 0, 16384], dtype=np.int16).tobytes())
        self.assertEqual(result, "你好 GitHub")
        self.assertTrue(factory.call_args.kwargs["local_files_only"])
        waveform = model.transcribe.call_args.args[0]
        np.testing.assert_array_equal(waveform, [-1, 0, 0.5])
        self.assertEqual(waveform.dtype, np.float32)
        self.assertEqual(model.transcribe.call_args.kwargs["task"], "transcribe")
        self.assertFalse(model.transcribe.call_args.kwargs["condition_on_previous_text"])


if __name__ == "__main__":
    unittest.main()
