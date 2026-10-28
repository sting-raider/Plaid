"""Check the native builder's immutable-ROM overlay detection boundary."""
from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import patch
import json
from pathlib import Path
import tempfile

import native
from fragment_mapped import partition_mapped


def mapped_partition_contract():
    with tempfile.TemporaryDirectory(prefix='plaid-fragments-') as temporary:
        root = Path(temporary)
        loads, mapping = root / 'loads.json', root / 'map.json'
        source = dict(destination='0x60000000', physical='0x2000', size='0x4000', text_size='0x4000',
                      encoding='ares_tlb', entry='0x60003000', rom='0x0', slot=True)
        document = dict(source='synthetic complete capture', loads=[source])
        placed = 0x80800000
        declaration = dict(destination=dict(start=placed, size=0x4000), linked=0x60000000,
                           encoding=dict(ares_tlb=dict(entry=0x60003000, physical=0x2000, text_size=0x4000)))
        program = dict(load_images={'image': dict(loads=[declaration])}, runtime_functions=[
            [dict(pc=placed + 0xff0, image='image'), dict(source_size=0x30)]], evidence={
            'table': dict(detail=json.dumps(dict(table_start=placed + 0x1ff0, count=8,
                                                site=dict(pc=placed + 0x1900))))})
        loads.write_text(json.dumps(document)); mapping.write_text(json.dumps(program))
        assert partition_mapped(loads, mapping)
        parts = json.loads(loads.read_text())['loads']
        assert parts == [dict(source, size='0x3000', text_size='0x3000'),
                         dict(source, destination='0x60003000', physical='0x5000', size='0x1000', text_size='0x1000')]
        before = loads.read_bytes()
        # The old map cannot select newly partitioned identities, and a map
        # describing each new part preserves the host/table boundaries again.
        assert not partition_mapped(loads, mapping) and loads.read_bytes() == before
        for change in [dict(entry=0x60003004), dict(physical=0x3000)]:
            altered = json.loads(json.dumps(program))
            altered['load_images']['image']['loads'][0]['encoding']['ares_tlb'].update(change)
            loads.write_text(json.dumps(document)); mapping.write_text(json.dumps(altered))
            before = loads.read_bytes()
            assert not partition_mapped(loads, mapping) and loads.read_bytes() == before
        ambiguous = json.loads(json.dumps(program))
        ambiguous['load_images']['other'] = ambiguous['load_images']['image']
        mapping.write_text(json.dumps(ambiguous))
        assert not partition_mapped(loads, mapping)
        # Keeping table words together is insufficient: a consumer on another
        # page must bind those words through the very same fragment.
        for proof in [dict(table_start=placed + 0x3010, count=1, site=dict(pc=placed + 0x100)),
                      dict(source_cell=placed + 0x3010, site=dict(pc=placed + 0x100)),
                      dict(table_start=placed + 0x3010, count=1)]:
            program['evidence'] = {'far': dict(detail=json.dumps(proof))}
            mapping.write_text(json.dumps(program)); loads.write_text(json.dumps(document))
            before = loads.read_bytes()
            assert not partition_mapped(loads, mapping) and loads.read_bytes() == before
    print('PASS mapped partition policy: exact identities, host/table extents, byte offsets, idempotence and ambiguous-source refusal')


def run_contract():
    mapped_partition_contract()
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
