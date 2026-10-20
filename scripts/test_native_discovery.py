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
    # Even a default-CLOSED map must retain the explicitly selected validation
    # mode in its manifest; no later build step may erase that qualification.
    with tempfile.TemporaryDirectory(prefix='plaid-manifest-') as temporary:
        root = Path(temporary)
        loads = root / 'loads.json'
        loads.write_text(json.dumps({'loads': []}))
        def plaid(command, *args, **kwargs):
            payload = {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100} if command == 'rom-info' else {'status': 'closed', 'blockers': []}
            return CompletedProcess([], 0, json.dumps(payload), '')
        with patch.object(native, 'ROOT', root), patch.object(native, 'plaid', side_effect=plaid), \
                patch.object(native, 'run'), patch.object(native, 'discover_map'), \
                patch.object(native, 'capture_many', side_effect=ValueError('test stop after manifest')), \
                patch('sys.argv', ['native.py', 'synthetic.z64', '--name', 'manifest', '--loads', str(loads), '--residual-dispatch']):
            try:
                native.main()
            except SystemExit as error:
                assert 'test stop after manifest' in str(error), error
            else:
                raise AssertionError('test did not stop before native build')
        manifest = json.loads((root / 'target/native/manifest-residual/native-manifest.json').read_text())
        assert manifest == {'mode': 'residual-dispatch', 'native_complete': False, 'residual_sites': []}, manifest
    print('PASS residual manifest: explicit validation mode persists even when ordinary closure succeeds')
