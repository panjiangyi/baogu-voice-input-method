"""Read the mouse-selected text on X11 for the selection question feature.

The PRIMARY selection is read directly. It already holds whatever the user
last highlighted with the mouse, so GTK/Qt/terminal apps need no keystroke and
the real clipboard is never touched. Frontends that do not export PRIMARY
(some Electron apps) fall back to a synthetic Ctrl+C; that path snapshots the
clipboard first and restores it afterwards so the user's clipboard survives.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

PROBE_PREFIX = "__voiceime_selection_probe__"


def _executable(path: str | None) -> str | None:
    if path and os.path.isfile(path) and os.access(path, os.X_OK):
        return path
    return None


def find_tool(name: str, env_var: str) -> str | None:
    """Resolve an X11 helper, honouring an explicit override."""
    override = _executable(os.environ.get(env_var))
    if override:
        return override
    found = shutil.which(name)
    if found:
        return found
    return _executable(os.path.expanduser(f"~/.local/bin/{name}")) or _executable(
        f"/usr/bin/{name}"
    )


def _read_clipboard(xclip: str, selection: str, timeout: float = 0.6) -> str | None:
    """Return the selection text, "" when empty, or None when unreadable."""
    try:
        out = subprocess.run(
            [xclip, "-selection", selection, "-o"],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return ""
    return out.stdout


def _write_clipboard(xclip: str, text: str, timeout: float = 0.6) -> bool:
    try:
        done = subprocess.run(
            [xclip, "-selection", "clipboard", "-i"],
            input=text, text=True, timeout=timeout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def capture_selection(*, primary_only: bool = False, timeout: float = 0.4) -> str:
    """Return the currently selected text, or "" when nothing is selected."""
    xclip = find_tool("xclip", "VOICEIME_XCLIP")
    if not xclip:
        return ""

    primary = _read_clipboard(xclip, "primary")
    if primary:
        return primary
    if primary_only:
        return ""

    xdotool = find_tool("xdotool", "VOICEIME_XDOTOOL")
    if not xdotool:
        return ""

    previous = _read_clipboard(xclip, "clipboard") or ""
    probe = f"{PROBE_PREFIX}{os.getpid()}_{int(time.monotonic() * 1000)}__"
    if not _write_clipboard(xclip, probe):
        return ""
    try:
        subprocess.run(
            [xdotool, "key", "--clearmodifiers", "ctrl+c"],
            timeout=0.4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        _write_clipboard(xclip, previous)
        return ""

    captured = ""
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        current = _read_clipboard(xclip, "clipboard")
        if current is not None and current != probe:
            captured = current
            break
        time.sleep(0.02)
    _write_clipboard(xclip, previous)
    return captured
