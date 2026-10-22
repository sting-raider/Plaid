"""Check the native builder's immutable-ROM overlay detection boundary."""
from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import patch
import json
from pathlib import Path
import tempfile

import native


def run_contract():
    arguments = ['discover', 'synthetic.z64', '0x1000', '0x80000000', '0x20',
                 '0x80000000', 'map.json']
    output = 'map.json'

    def probe(stderr):
        def memo(*args, writes=()):
            assert writes == (output,)
            if stderr and (args[-1] == '--overlays' or 'file table' not in stderr):
                raise CalledProcessError(1, args, '', stderr)
            return 'discovered synthetic map'
        return patch.object(native, 'memo_plaid', side_effect=memo)

    with probe('no self-describing ROM file table') as memo:
        supported = native.discover_map(arguments, None, output)
        assert supported is False
        assert native.discover_map(arguments, supported, output) is False
        assert [call.args for call in memo.call_args_list] == [(*arguments, '--overlays'), *[tuple(arguments)] * 2]

    with probe(None) as memo:
        supported = native.discover_map(arguments, None, output)
        assert supported is True
        assert native.discover_map(arguments, supported, output) is True
        assert [call.args for call in memo.call_args_list] == [(*arguments, '--overlays')] * 2

    with probe('declared source identity mismatch') as memo:
        try:
            native.discover_map(arguments, None, output)
        except SystemExit as error:
            assert str(error) == 'declared source identity mismatch'
        else:
            raise AssertionError('non-file-table errors must stop discovery')
        assert memo.call_count == 1
    print('PASS native discovery: immutable negative overlay probe and fatal-error propagation')
    # The manifest records whether the build is closed or dispatches residual
    # sites at run time; --strict refuses anything but a CLOSED map (ADR-0233).
    def build(ordinary, strict):
        with tempfile.TemporaryDirectory(prefix='plaid-manifest-') as temporary:
            root = Path(temporary)
            loads = root / 'loads.json'
            loads.write_text(json.dumps({'loads': []}))
            solves = []
            def plaid(command, *args, **kwargs):
                if command == 'rom-info':
                    payload = {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}
                elif command == 'solve':
                    solves.append(args[-1])
                    payload = ({'status': ordinary, 'blockers': [{}] * (ordinary != 'closed')} if args[-1] == '--address-taken'
                               else {'status': 'closed', 'blockers': [], 'residual_sites': [{'pc': 0x80000420}]})
                else:
                    payload = {}
                return CompletedProcess([], 0, json.dumps(payload), '')
            argv = ['native.py', 'synthetic.z64', '--name', 'manifest', '--loads', str(loads), *(['--strict'] if strict else [])]
            with patch.object(native, 'ROOT', root), patch.object(native, 'plaid', side_effect=plaid), \
                    patch.object(native, 'memo_plaid', side_effect=lambda *a, writes=(): plaid(*a).stdout),                     patch.object(native, 'run'), patch.object(native, 'discover_map'), \
                    patch.object(native, 'capture_many', side_effect=ValueError('test stop after manifest')), \
                    patch('sys.argv', argv):
                try:
                    native.main()
                except SystemExit as error:
                    stop = str(error)
                else:
                    raise AssertionError('test did not stop before native build')
            manifest = root / 'target/native/manifest/native-manifest.json'
            return stop, solves, json.loads(manifest.read_text()) if manifest.exists() else None

    stop, solves, manifest = build('closed', False)
    assert 'test stop after manifest' in stop and solves == ['--address-taken'], (stop, solves)
    assert manifest == {'mode': 'closed', 'native_complete': True, 'residual_sites': []}, manifest
    stop, solves, manifest = build('open', False)
    assert 'test stop after manifest' in stop and solves == ['--address-taken', '--residual-dispatch'], (stop, solves)
    assert manifest == {'mode': 'residual-dispatch', 'native_complete': False, 'residual_sites': ['80000420']}, manifest
    stop, solves, manifest = build('open', True)
    assert 'nothing is built' in stop and solves == ['--address-taken'] and manifest is None, (stop, solves, manifest)
    print('PASS native manifest: closed builds are complete, residual dispatch is the recorded default, --strict refuses OPEN')
