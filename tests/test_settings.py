import os
import tempfile
import unittest
from unittest.mock import patch
from voiceime_settings import CorrectionShortcut, llm_enabled, toggle_llm


class SettingsTests(unittest.TestCase):
    def test_toggle_persists_and_overrides_default(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            self.assertTrue(llm_enabled(True))
            self.assertFalse(toggle_llm(True))
            self.assertFalse(llm_enabled(True))
            self.assertTrue(toggle_llm(False))
            self.assertTrue(llm_enabled(False))

    def test_shortcut_requires_modifiers_and_suppresses_repeat(self):
        keys = CorrectionShortcut()
        self.assertFalse(keys.feed("RawKeyPress", 75))
        keys.feed("RawKeyRelease", 75)
        keys.feed("RawKeyPress", 105)
        keys.feed("RawKeyPress", 62)
        self.assertTrue(keys.feed("RawKeyPress", 75))
        self.assertFalse(keys.feed("RawKeyPress", 75))
        keys.feed("RawKeyRelease", 75)
        self.assertTrue(keys.feed("RawKeyPress", 75))
        keys.feed("RawKeyRelease", 62)
        keys.feed("RawKeyRelease", 75)
        self.assertFalse(keys.feed("RawKeyPress", 75))

    def test_personal_terms_override_compiled_and_reload(self):
        from pathlib import Path
        from voiceime_glossary import GlossaryCorrector
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            path = Path(directory) / "voiceime" / "hotwords.txt"
            path.parent.mkdir()
            path.write_text("MySpecialProject\n", encoding="utf-8")
            self.assertEqual(GlossaryCorrector().correct("my special project"), "MySpecialProject")
            path.write_text("MyOtherProject\n", encoding="utf-8")
            self.assertEqual(GlossaryCorrector().correct("my other project"), "MyOtherProject")
