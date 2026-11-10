"""Pause other media players when recording starts (MPRIS over D-Bus).

Only players that are actually playing get a Pause; nothing is resumed later.
"""
import json
import subprocess

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
MPRIS_PATH = "/org/mpris/MediaPlayer2"
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"


def _busctl(*args, timeout=1.0):
    return subprocess.run(
        ["busctl", "--user", "--json=short", f"--timeout={timeout}", *args],
        capture_output=True, text=True, timeout=timeout + 0.5,
    )


def list_players(run=_busctl):
    out = run("call", "org.freedesktop.DBus", "/org/freedesktop/DBus",
              "org.freedesktop.DBus", "ListNames")
    if out.returncode != 0:
        return []
    names = json.loads(out.stdout)["data"][0]
    return sorted(n for n in names if n.startswith(MPRIS_PREFIX))


def is_playing(name, run=_busctl):
    out = run("get-property", name, MPRIS_PATH, PLAYER_IFACE, "PlaybackStatus")
    return out.returncode == 0 and json.loads(out.stdout).get("data") == "Playing"


def pause_playing(run=_busctl):
    """Pause every MPRIS player that is playing; return the names paused."""
    paused = []
    for name in list_players(run):
        try:
            if is_playing(name, run):
                if run("call", name, MPRIS_PATH, PLAYER_IFACE, "Pause").returncode == 0:
                    paused.append(name)
        except (subprocess.TimeoutExpired, ValueError, KeyError):
            continue
    return paused
