"""Check the native builder's immutable-ROM overlay detection boundary."""
from subprocess import CompletedProcess
from unittest.mock import patch

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
