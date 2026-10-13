"""Persistent user override for optional cloud correction."""
import os
from pathlib import Path


def llm_state_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "voiceime" / "deepseek-enabled.txt"


def llm_enabled(default=True):
    try:
        value = llm_state_path().read_text(encoding="utf-8").strip()
    except OSError:
        return default
    return {"1": True, "0": False}.get(value, default)


def toggle_llm(default=True):
    enabled = not llm_enabled(default)
    path = llm_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text("1\n" if enabled else "0\n", encoding="utf-8")
    temporary.replace(path)
    return enabled


class CorrectionShortcut:
    """Ctrl + Shift + F9; suppress key repeat until release."""
    def __init__(self):
        self.pressed = set()

    def feed(self, event, keycode):
        if event == "RawKeyRelease":
            self.pressed.discard(keycode)
            return False
        repeated = keycode in self.pressed
        self.pressed.add(keycode)
        return (keycode == 75 and not repeated
                and bool(self.pressed & {37, 105})
                and bool(self.pressed & {50, 62}))
