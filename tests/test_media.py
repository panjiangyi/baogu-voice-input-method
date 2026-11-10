import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import baogu_media  # noqa: E402


def fake_bus(statuses):
    calls = []

    def run(*args):
        calls.append(args)
        if args[-1] == "ListNames":
            names = ["org.freedesktop.DBus", *(baogu_media.MPRIS_PREFIX + n for n in statuses)]
            return SimpleNamespace(returncode=0, stdout=json.dumps({"type": "as", "data": [names]}))
        if args[0] == "get-property":
            status = statuses[args[1].removeprefix(baogu_media.MPRIS_PREFIX)]
            return SimpleNamespace(returncode=0, stdout=json.dumps({"type": "s", "data": status}))
        return SimpleNamespace(returncode=0, stdout="")

    return run, calls


class PauseMediaTest(unittest.TestCase):
    def test_pauses_only_playing_players(self):
        run, calls = fake_bus({"spotify": "Playing", "vlc": "Paused", "chromium.instance1": "Playing"})
        paused = baogu_media.pause_playing(run)
        self.assertEqual(paused, [baogu_media.MPRIS_PREFIX + "chromium.instance1",
                                  baogu_media.MPRIS_PREFIX + "spotify"])
        pauses = [c[1] for c in calls if c[-1] == "Pause"]
        self.assertEqual(pauses, paused)

    def test_bus_failure_pauses_nothing(self):
        def run(*_args):
            return SimpleNamespace(returncode=1, stdout="")
        self.assertEqual(baogu_media.pause_playing(run), [])


if __name__ == "__main__":
    unittest.main()
