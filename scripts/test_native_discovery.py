"""Check the native builder's immutable-ROM overlay detection boundary."""
from subprocess import CompletedProcess
from unittest.mock import patch
import json
from pathlib import Path
import tempfile

import native


def run_contract():
    arguments = ['discover', 'synthetic.z64', '0x1000', '0x80000000', '0x20',
                 '0x80000000', 'map.json']
    absent = CompletedProcess([], 1, '', 'no self-describing ROM file table')
    with patch.object(native.subprocess, 'run', return_value=absent) as probe, \
            patch.object(native, 'plaid') as discover:
        supported = native.discover_map(arguments, None)
        assert supported is False
        assert native.discover_map(arguments, supported) is False
        assert probe.call_count == 1
        assert probe.call_args.args[0][-1] == '--overlays'
        assert [call.args for call in discover.call_args_list] == [tuple(arguments)] * 2

    present = CompletedProcess([], 0, 'discovered synthetic map\n', '')
    with patch.object(native.subprocess, 'run', return_value=present) as probe, \
            patch.object(native, 'plaid') as discover:
        supported = native.discover_map(arguments, None)
        assert supported is True
        assert native.discover_map(arguments, supported) is True
        assert probe.call_count == 2 and discover.call_count == 0

    invalid = CompletedProcess([], 1, '', 'declared source identity mismatch')
    with patch.object(native.subprocess, 'run', return_value=invalid), \
            patch.object(native, 'plaid') as discover:
        try:
            native.discover_map(arguments, None)
        except SystemExit as error:
            assert str(error) == invalid.stderr
        else:
            raise AssertionError('non-file-table errors must stop discovery')
        assert discover.call_count == 0
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
                    patch.object(native, 'run'), patch.object(native, 'discover_map'), \
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
