"""Routing and ownership regressions, without changing desktop audio."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('baogu_aec', str(ROOT / 'baogu-aec'))
spec = importlib.util.spec_from_loader(loader.name, loader)
aec = importlib.util.module_from_spec(spec)
loader.exec_module(aec)


class AecTests(unittest.TestCase):
    def test_moves_only_streams_on_target_output(self):
        devices = [{'index': 1, 'name': 'speakers'}, {'index': 2, 'name': 'headphones'}]
        streams = [{'index': 11, 'sink': 1}, {'index': 12, 'sink': 2},
                   {'index': 13, 'sink': 1, 'properties': {'node.name': 'echo-cancel-playback'}}]
        with patch.object(aec, 'listing', side_effect=[devices, streams]), patch.object(aec, 'pactl') as call:
            aec.move_streams('speakers', aec.SINK)
        call.assert_called_once_with('move-sink-input', '11', aec.SINK)

    def test_disable_restores_defaults_and_unloads_owned_module(self):
        with tempfile.TemporaryDirectory() as directory:
            statefile = Path(directory) / 'state'
            statefile.write_text('{}')
            def response(*args):
                if args == ('get-default-sink',):
                    return aec.SINK
                if args == ('get-default-source',):
                    return aec.SOURCE
                if args == ('list', 'short', 'modules'):
                    return f'42\tmodule-echo-cancel\tsource_name={aec.SOURCE}\t\n'
                return ''
            with patch.object(aec, 'STATE', statefile), patch.object(aec, 'pactl', side_effect=response) as call, patch.object(aec, 'move_streams') as move:
                aec.disable({'module': '42', 'source': 'mic', 'sink': 'speakers'})
            call.assert_any_call('set-default-sink', 'speakers')
            call.assert_any_call('set-default-source', 'mic')
            call.assert_any_call('unload-module', '42')
            move.assert_called_once_with(aec.SINK, 'speakers')
            self.assertFalse(statefile.exists())

    def test_disable_preserves_user_switch_and_unrelated_module(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(aec, 'STATE', Path(directory) / 'state'), patch.object(aec, 'pactl', side_effect=['headphones', 'other_mic', '42\tmodule-other\t\n']) as call, patch.object(aec, 'move_streams'):
                aec.disable({'module': '42', 'source': 'mic', 'sink': 'speakers'})
            self.assertEqual(call.call_count, 3)


if __name__ == '__main__':
    unittest.main()
