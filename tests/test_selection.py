"""Selection capture must prefer PRIMARY and never lose the clipboard."""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import voiceime_selection as sel  # noqa: E402


class SelectionTests(unittest.TestCase):
    def test_primary_is_read_without_touching_clipboard(self):
        with patch.object(
            sel, "find_tool",
            side_effect=lambda name, env: "/usr/bin/xclip" if name == "xclip" else None,
        ), patch.object(sel, "_read_clipboard", return_value="选中的文字") as read, \
                patch.object(sel, "_write_clipboard") as write:
            self.assertEqual(sel.capture_selection(), "选中的文字")
        write.assert_not_called()
        self.assertEqual(read.call_args[0][1], "primary")

    def test_no_xclip_returns_empty(self):
        with patch.object(sel, "find_tool", return_value=None):
            self.assertEqual(sel.capture_selection(), "")

    def test_primary_only_skips_ctrl_c(self):
        with patch.object(
            sel, "find_tool",
            side_effect=lambda name, env: "/usr/bin/xclip" if name == "xclip" else None,
        ), patch.object(sel, "_read_clipboard", return_value=""), \
                patch.object(sel.subprocess, "run") as run:
            self.assertEqual(sel.capture_selection(primary_only=True), "")
        run.assert_not_called()

    def test_ctrl_c_fallback_captures_and_restores(self):
        reads = {"primary": "", "clipboard": "旧的剪贴板"}
        writes = []

        def fake_write(_xclip, text, timeout=0.6):
            writes.append(text)
            reads["clipboard"] = text
            return True

        def fake_run(cmd, **_kwargs):
            if isinstance(cmd, list) and str(cmd[0]).endswith("xdotool"):
                reads["clipboard"] = "新选中的文字"
            return types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(sel, "find_tool", side_effect=lambda n, e: f"/usr/bin/{n}"), \
                patch.object(sel, "_read_clipboard", side_effect=lambda _x, s, timeout=0.6: reads[s]), \
                patch.object(sel, "_write_clipboard", side_effect=fake_write), \
                patch.object(sel.subprocess, "run", side_effect=fake_run):
            self.assertEqual(sel.capture_selection(timeout=0.3), "新选中的文字")
        self.assertTrue(writes[0].startswith(sel.PROBE_PREFIX))
        self.assertEqual(writes[-1], "旧的剪贴板")

    def test_no_copy_leaves_previous_clipboard(self):
        reads = {"primary": "", "clipboard": "旧的剪贴板"}
        writes = []

        def fake_write(_xclip, text, timeout=0.6):
            writes.append(text)
            reads["clipboard"] = text  # a frontend that blocks Ctrl+C keeps the probe
            return True

        with patch.object(sel, "find_tool", side_effect=lambda n, e: f"/usr/bin/{n}"), \
                patch.object(sel, "_read_clipboard", side_effect=lambda _x, s, timeout=0.6: reads[s]), \
                patch.object(sel, "_write_clipboard", side_effect=fake_write), \
                patch.object(sel.subprocess, "run",
                             return_value=types.SimpleNamespace(returncode=0, stdout="", stderr="")):
            self.assertEqual(sel.capture_selection(timeout=0.05), "")
        self.assertEqual(writes[-1], "旧的剪贴板")

    def test_missing_xdotool_returns_empty(self):
        with patch.object(
            sel, "find_tool",
            side_effect=lambda name, env: "/usr/bin/xclip" if name == "xclip" else None,
        ), patch.object(sel, "_read_clipboard", return_value=""):
            self.assertEqual(sel.capture_selection(), "")


if __name__ == "__main__":
    unittest.main()
