"""Deterministic synthetic post-IPL harvest; no commercial ROM or IPL3 needed."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from ares_boot import ROOT, build_oracle, capture_many
import harvest_boot
from native import write_boot_state


def boot_header_contract():
    capture = dict(boot_status=0x34000000, boot_entryhi=0xff, entered=True, boot_entry=0x80000400,
                   sp=[i % 256 for i in range(0x2000)], ram_prefix=[(i * 7 + 3) % 256 for i in range(0x400)],
                   rom_sha256='synthetic', revision='synthetic')
    with tempfile.TemporaryDirectory(prefix='plaid-boot-header-') as temporary:
        directory = Path(temporary)
        sp, ram = write_boot_state(capture, directory, 0x80000400)
        assert '#define PLAID_BOOT_STATUS 872415232u' in ram.read_text()
        assert '#define PLAID_BOOT_ENTRYHI 255ull' in ram.read_text()
        assert ','.join(map(str, capture['ram_prefix'])) in ram.read_text()
        assert ','.join(map(str, capture['sp'])) in sp.read_text()
        receipt = json.loads((directory / 'boot-state.json').read_text())
        assert receipt['rom_sha256'] == 'synthetic' and receipt['startup_payloads']['ram_prefix']['size'] == 0x400
        import hashlib
        assert receipt['startup_payloads']['ram_prefix']['sha256'] == hashlib.sha256(bytes(capture['ram_prefix'])).hexdigest()
        assert 'ram_prefix' not in receipt and 'sp' not in receipt
        write_boot_state(dict(capture, boot_entry=0xa0000400), directory, 0xa0000400)
        for change in [dict(boot_status=None), dict(boot_status=True), dict(boot_status=-1), dict(boot_entryhi=None), dict(boot_entryhi=1 << 64),
                       dict(boot_status=0x100000000), dict(entered=False), dict(boot_entry=0x80001000), dict(ram_prefix=None),
                       dict(ram_prefix=capture['ram_prefix'][:-1]), dict(sp=capture['sp'][:-1]),
                       dict(ram_prefix=[256] * 0x400), dict(ram_prefix=[True] * 0x400)]:
            try:
                write_boot_state(dict(capture, **change), directory, 0x80000400)
                raise AssertionError(f'invalid boot state accepted: {change.keys()}')
            except ValueError:
                pass
        try:
            write_boot_state(dict(capture, boot_entry=0x80000000), directory, 0x80000000)
            raise AssertionError('boot prefix overlapped the base executable image')
        except ValueError:
            pass
    print('PASS native startup headers: exact bounded bytes, entry/length/byte refusal, provenance and payload hashes')


def projection_contract():
    site = {'site': {'pc': 0x8080042c}, 'closed_proof': None, 'link_register': 31}
    load = {'destination': {'start': 0x80800400, 'size': 0x100}, 'linked': 0x80000400,
            'relocatable': True, 'encoding': 'raw', 'source': 0x1000}
    program = {'indirect_sites': [site], 'load_images': {'fixture': {
        'base': {'start': 0x80002000, 'size': 0x100}, 'loads': [load]}}}
    bindings = harvest_boot.replay_bindings(program, 0x80002000, 0x100)
    assert harvest_boot.replay_sites(program, bindings) == [0x8000042c, 0xa000042c]
    for changed in [[], bindings + [(0x80800400, 0x80001400, 0x100, 0x1000)],
                    [(0x80800400, 0x80000400, 0x100, -1)]]:
        try:
            harvest_boot.replay_sites(program, changed)
        except ValueError:
            pass
        else:
            raise AssertionError('missing/ambiguous/unsupported binding accepted')
    print('PASS relocated replay site projection: runtime PCs, aliases, ambiguous and unsupported refusal')



def raw_occupant_contract():
    with tempfile.TemporaryDirectory(prefix='plaid-occupant-') as temporary:
        d = Path(temporary)
        rom, loads, program, receipt = (d / n for n in ('rom.z64', 'loads.json', 'map.json', 'receipt.json'))
        payload = bytes.fromhex('2402002a03e000080000000000000000')
        rom.write_bytes(bytes.fromhex('80371240') + bytes(0xfc) + payload)
        original = {'destination': '0x80001008', 'size': '0x20', 'rom': '0x80', 'encoding': 'raw', 'slot': True}
        initial = json.dumps({'source': 'synthetic', 'loads': [original]})
        program.write_text(json.dumps({'direct_edges': [], 'indirect_sites': [
            {'site': {'pc': 0x80000420}, 'closed_proof': None, 'link_register': 31, 'candidates': [], 'observed': []}]}))
        capture = dict(raw_occupant=True, destination=0x80001000, size=16, rom=0x100,
                       entry=0xa0001000, load_site=0x8000041c, bytes=list(payload),
                       revision='synthetic', rom_sha256='synthetic')
        saved = harvest_boot.capture_many
        try:
            info = {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}
            harvest_boot.capture_many = lambda *args, **kwargs: [capture]
            loads.write_text(initial)
            assert harvest_boot.harvest(rom, loads, program, info, receipt)
            declared = json.loads(loads.read_text())['loads']
            assert declared[0] == original and len(declared) == 2  # old slot placement is stable
            assert dict(destination='0x80001000', size='0x10', rom='0x100', encoding='raw', slot=True) in declared
            before = loads.read_bytes()
            assert not harvest_boot.harvest(rom, loads, program, info, receipt)
            assert loads.read_bytes() == before
            canonical = rom.read_bytes()
            for width in (2, 4):
                ordered = bytearray(len(canonical))
                for lane in range(width):
                    ordered[lane::width] = canonical[width - 1 - lane::width]
                rom.write_bytes(ordered); loads.write_text(initial)
                assert harvest_boot.harvest(rom, loads, program, info, receipt)
            rom.write_bytes(canonical)
            for change in [dict(bytes=list(payload[:-1])), dict(bytes=[0] * 16),
                           dict(rom=0x104), dict(size=12), dict(entry=0x1000), dict(entry=0x80001010), dict(destination=0x80001004)]:
                loads.write_text(initial)
                harvest_boot.capture_many = lambda *args, **kwargs: [dict(capture, **change)]
                assert not harvest_boot.harvest(rom, loads, program, info, receipt)
                assert loads.read_text() == initial
                assert json.loads(receipt.read_text())['refusal'] == 'invalid completed PI occupant'
        finally:
            harvest_boot.capture_many = saved
    print('PASS raw occupant harvest: covered range adds guarded alternate once; malformed/full-content mismatch refused')

def mapped_harvest_contract():
    with tempfile.TemporaryDirectory(prefix='plaid-mapped-') as temporary:
        d = Path(temporary)
        rom, loads, program, receipt = (d / n for n in ('rom.z64', 'loads.json', 'map.json', 'receipt.json'))
        initial = json.dumps(dict(source='synthetic', loads=[]))
        loads.write_text(initial)
        program.write_text(json.dumps(dict(direct_edges=[{'target': {'pc': 0x60000000}}], indirect_sites=[])))
        capture = dict(destination=0x60000000, physical_start=0x1000, entry=0x60000000,
                       bytes=[0x24, 2, 0, 42, 3, 0xe0, 0, 8, 0, 0, 0, 0],
                       revision='synthetic', rom_sha256='synthetic')
        saved = harvest_boot.capture_many
        try:
            harvest_boot.capture_many = lambda *args, **kwargs: [capture]
            info = dict(header=dict(boot_address=0x80000400), boot_image_size=0x100)
            assert harvest_boot.harvest(rom, loads, program, info, receipt)
            declaration = json.loads(loads.read_text())['loads'][0]
            assert declaration == dict(destination='0x60000000', physical='0x1000', size='0xc',
                                       rom='0x0', encoding='ares_tlb', entry='0x60000000', text_size='0xc', slot=True)
            before = loads.read_bytes()
            assert not harvest_boot.harvest(rom, loads, program, info, receipt)
            assert loads.read_bytes() == before
            for changed in [dict(physical_start=0x800000), dict(physical_start=0x1002),
                            dict(destination=0x80001000), dict(destination=0x7ffffffc),
                            dict(entry=0x6000000c), dict(bytes=[]), dict(bytes=[0])]:
                loads.write_text(initial)
                harvest_boot.capture_many = lambda *args, **kwargs: [dict(capture, **changed)]
                assert not harvest_boot.harvest(rom, loads, program, info, receipt)
                assert loads.read_text() == initial
        finally:
            harvest_boot.capture_many = saved
    print('PASS mapped harvest: physical/virtual identity, bounded text, whole-ROM replay declaration, duplicate and mutation refusal')


def replay_cache_contract():
    import ares_boot
    calls, saved, saved_root = [], ares_boot.replay, os.environ.get('PLAID_REPLAY_CACHE')
    ares_boot.replay = lambda rom, data, entries, *rest: calls.append(entries) or [{'entry': entries[0], 'n': len(calls)}]
    try:
        with tempfile.TemporaryDirectory(prefix='plaid-replay-cache-') as temporary:
            os.environ['PLAID_REPLAY_CACHE'] = temporary
            rom = Path(temporary) / 'rom.z64'
            rom.write_bytes(bytes(0x1000))
            first = capture_many(rom, [0x80000400])
            assert capture_many(rom, [0x80000400]) == first and len(calls) == 1
            capture_many(rom, [0x80000404])
            capture_many(rom, [0x80000400], covered=[(0, 4)])
            rom.write_bytes(bytes(0xfff) + b'')
            assert capture_many(rom, [0x80000400]) == [{'entry': 0x80000400, 'n': 4}] and len(calls) == 4
    finally:
        ares_boot.replay = saved
        if saved_root is None:
            os.environ.pop('PLAID_REPLAY_CACHE')
        else:
            os.environ['PLAID_REPLAY_CACHE'] = saved_root


def independent_source_contract():
    mapped_load = dict(destination='0x61000000', size='0x100', text_size='0x80',
                       encoding='ares_tlb', slot=True)
    edges = dict(direct_edges=[dict(target=dict(pc=pc)) for pc in
                              (0x61000000, 0x6100007c, 0x61000080, 0x61000100)], indirect_sites=[])
    assert harvest_boot.missing_targets(edges, dict(loads=[mapped_load]), 0x80000400, 0x100) == [0x61000080, 0x61000100]
    with tempfile.TemporaryDirectory(prefix='plaid-independent-source-') as temporary:
        d = Path(temporary)
        loads, program, receipt = (d / f'{n}.json' for n in ('loads', 'map', 'receipt'))
        initial = dict(source='synthetic', loads=[])
        unsupported = dict(site=dict(pc=0x80800000), closed_proof=None, link_register=31,
                           candidates=[], observed=[])
        p = dict(direct_edges=[dict(target=dict(pc=0x61000000))], indirect_sites=[unsupported],
                 load_images={'fixture': dict(base=dict(start=0x80000400, size=0x100), loads=[
                     dict(destination=dict(start=0x80800000, size=0x100), linked=0x60000000,
                          relocatable=True, encoding={'ares_tlb': {'text_size': 0x100}}, source=0)])})
        captured = dict(destination=0x61000000, physical_start=0x2000, entry=0x61000000,
                        bytes=list(struct.pack('>3I', 0x2402002a, 0x03e00008, 0)),
                        revision='synthetic', rom_sha256='synthetic')
        saved, calls = harvest_boot.capture_many, []
        def replay(rom, entries, **kwargs):
            calls.append((entries, kwargs))
            assert not kwargs  # source-only replay cannot acquire call observations
            return [captured]
        harvest_boot.capture_many = replay
        try:
            info = dict(header=dict(boot_address=0x80000400), boot_image_size=0x100)
            loads.write_text(json.dumps(initial))
            program.write_text(json.dumps(p))
            assert harvest_boot.harvest('unused.z64', loads, program, info, receipt)
            assert calls[0][0] == [0x61000000]
            result = json.loads(loads.read_text())
            assert result.get('observed_roots', []) == []
            assert result['loads'][0]['encoding'] == 'ares_tlb'
            assert 'call_projection_refusal' in json.loads(receipt.read_text())
            # Invalid image identity must refuse before source-only fallback.
            loads.write_text(json.dumps(initial))
            p['load_images']['ambiguous'] = p['load_images']['fixture']
            program.write_text(json.dumps(p))
            assert not harvest_boot.harvest('unused.z64', loads, program, info, receipt)
            assert len(calls) == 1 and json.loads(loads.read_text()) == initial
            del p['load_images']['ambiguous']
            # No known source request: unsupported projection still refuses.
            loads.write_text(json.dumps(initial))
            p['direct_edges'] = []
            program.write_text(json.dumps(p))
            assert not harvest_boot.harvest('unused.z64', loads, program, info, receipt)
            assert len(calls) == 1 and json.loads(loads.read_text()) == initial
            # Missing bytes do not turn a numeric target into executable code.
            p['direct_edges'] = [dict(target=dict(pc=0x61000000))]
            program.write_text(json.dumps(p))
            harvest_boot.capture_many = lambda *a, **kw: [dict(rejected_entry=0x61000000)]
            assert not harvest_boot.harvest('unused.z64', loads, program, info, receipt)
            assert json.loads(loads.read_text()) == initial
        finally:
            harvest_boot.capture_many = saved
    print('PASS independent missing-source replay: unsupported calls remain unobserved, no bytes/no request refuse')


def table_data_contract():
    with tempfile.TemporaryDirectory(prefix='plaid-table-data-') as temporary:
        receipt = Path(temporary) / 'receipt.json'
        initial = dict(source='synthetic', loads=[dict(destination='0x80001000', size='0x40', rom='0x200', encoding='raw')])
        table = dict(table_start=0x80001010, count=2)
        program = dict(unresolved=[dict(kind='invalid_pointer_table_entry', site=dict(pc=0x80800020), evidence=['table'])],
                       evidence={'table': dict(detail=json.dumps(table))},
                       load_images={'fixture': dict(base=dict(start=0x80000400, size=0x100), loads=[
                           dict(destination=dict(start=0x80800000, size=0x100), linked=0x60000000,
                                relocatable=True, encoding={'ares_tlb': {'text_size': 0x100}}, source=0)])})
        payload = (bytes(0x10) + struct.pack('>2I', 0x60000040, 0x60000050) + bytes(8) +
                   struct.pack('>2I', 0x60000060, 0x60000070) + bytes(0x18))
        captured = dict(entry=0x60000020, destination=0x60001000, physical_start=0x1000, bytes=list(payload))
        calls, saved = [], harvest_boot.capture_many
        def replay(rom, entries):
            calls.append(entries)
            return [captured]
        harvest_boot.capture_many = replay
        try:
            loads = json.loads(json.dumps(initial))
            assert harvest_boot.repair_table_data('unused.z64', loads, program, 0x80000400, 0x100, receipt)
            assert calls == [[0x60000020]]
            assert loads['loads'] == [
                dict(destination='0x80001000', size='0x10', rom='0x200', encoding='raw'),
                dict(destination='0x80001010', size='0x8', rom='0x0', encoding='ares_data', entry='0x60000020', physical='0x1010'),
                dict(destination='0x80001018', size='0x28', rom='0x218', encoding='raw')]
            before = json.dumps(loads, sort_keys=True)
            assert not harvest_boot.repair_table_data('unused.z64', loads, program, 0x80000400, 0x100, receipt)
            assert json.dumps(loads, sort_keys=True) == before
            later = json.loads(json.dumps(program))
            later['unresolved'][0]['site']['pc'] += 4
            later['evidence']['table']['detail'] = json.dumps(dict(table_start=0x80001020, count=2))
            assert harvest_boot.repair_table_data('unused.z64', loads, later, 0x80000400, 0x100, receipt)
            assert calls[-1] == [0x60000020]  # do not wait for an unexecuted later case
            assert any(l['destination'] == '0x80001020' and l['entry'] == '0x60000020'
                       for l in loads['loads'] if l['encoding'] == 'ares_data')
            for change in [dict(physical_start=0x2000), dict(bytes=[]),
                           dict(bytes=list(payload[:0x10] + struct.pack('>2I', 0x60000041, 0x60000050) + payload[0x18:]))]:
                loads = json.loads(json.dumps(initial))
                harvest_boot.capture_many = lambda *a: [dict(captured, **change)]
                assert not harvest_boot.repair_table_data('unused.z64', loads, program, 0x80000400, 0x100, receipt)
                assert loads == initial
            loads = json.loads(json.dumps(initial))
            loads['loads'][0]['encoding'] = 'yaz0'
            before = json.dumps(loads)
            harvest_boot.capture_many = replay
            assert not harvest_boot.repair_table_data('unused.z64', loads, program, 0x80000400, 0x100, receipt)
            assert json.dumps(loads) == before
        finally:
            harvest_boot.capture_many = saved
    print('PASS first-use table data: unique replay address, physical slice, source-preserving splits and invalid/conflicting refusal')


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(Path(__file__).resolve())], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True, timeout=600)
        return
    boot_header_contract()
    replay_cache_contract()
    raw_occupant_contract()
    mapped_harvest_contract()
    independent_source_contract()
    table_data_contract()
    for coverage in ([], [None], [[1]], [[4, 4]], [[0, 3]], [[False, 4]], [[0, 0x100000000]]):
        try:
            capture_many('never-read.z64', [], covered=coverage)
        except ValueError as error:
            assert 'coverage ranges' in str(error), error
        else:
            raise AssertionError(f'invalid coverage accepted: {coverage}')
    for bindings in ([None], [[0, 0, 0, None]], [[0, 0, 4, True]], [[0, 0, 4, -3]], [[0, 0xfffffffc, 8, None]]):
        try:
            capture_many('never-read.z64', [], covered=[(0, 4)], sites=[0], bindings=bindings)
        except ValueError as error:
            assert 'bindings' in str(error)
        else:
            raise AssertionError('invalid replay binding accepted')
    projection_contract()
    exe = build_oracle()
    firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    rom = bytearray(0x3000)
    rom[:4] = bytes.fromhex('80371240')
    # Store executable words through KSEG1, then fetch the same text in KSEG0.
    words = [0x3c08a000, 0x35081000, 0x3c092402, 0x3529002a, 0xad090000,
             0x3c0903e0, 0x35290008, 0xad090004, 0xad000008,
             0x3c198000, 0x37391000, 0x03200008, 0xad09f1d8]
    rom[0x1000:0x1000 + 4 * len(words)] = struct.pack(f'>{len(words)}I', *words)
    with tempfile.TemporaryDirectory(prefix='plaid-ares-test-') as temporary:
        directory = Path(temporary)
        source, output = directory / 'fixture.z64', directory / 'capture.json'
        source.write_bytes(rom)

        def run(target, budget, exact=False, covered=None, sites=None, bindings=None, check=True):
            command = [str(exe), str(source), str(firmware), '0x80000400', target,
                       str(budget), 'fixture', str(output)]
            if exact:
                command.append('exact-many')
            if covered is not None:
                coverage = directory / 'covered.txt'
                coverage.write_text(''.join(f'{lo} {hi}\n' for lo, hi in covered))
                command.extend(['uncovered', str(coverage)])
            if sites is not None:
                listed = directory / 'sites.txt'
                listed.write_text(''.join(f'{s}\n' for s in sites))
                command.append(str(listed))
            if bindings is not None:
                bound = directory / 'bindings.txt'
                bound.write_text(''.join(f'{a} {b} {n} {r}\n' for a, b, n, r in bindings))
                command.append(str(bound))
            if not check:
                return subprocess.run(command, timeout=30).returncode
            subprocess.run(command, check=True, timeout=30)
            return output.read_bytes()

        first = run('0x80001000', 1000)
        assert run('0x80001000', 1000) == first
        image, stop = [json.loads(line) for line in first.splitlines()]
        assert image['entry'] == image['destination'] == 0x80001000, image
        assert bytes(image['bytes']) == struct.pack('>3I', 0x2402002a, 0x03e00008, 0), image
        assert image['cpu_writes'] == [[0x1000, 0x100c]] and image['pi_dma'] == [], image
        assert image['steps'] == 13 and stop['remaining'] == 0, (image, stop)
        # The same produced words reached through the game's own indexed TLB write.
        # No addresses from commercial games occur in this fixture.
        mapped_words = words[:9] + [
            0x40800000,  # MTC0 zero, Index
            0x40802800,  # MTC0 zero, PageMask
            0x3c0a6000, 0x408a5000,  # EntryHi
            0x240a005f, 0x408a1000,  # global/valid/cache3, physical 1000
            0x240a009f, 0x408a1800,  # odd physical 2000
            0x42000002,  # TLBWI
            0x3c196000, 0x03200008, 0]
        def mapped_replay(changed):
            fixture = bytearray(rom)
            fixture[0x1000:0x1000 + 4 * len(changed)] = struct.pack(f'>{len(changed)}I', *changed)
            source.write_bytes(fixture)
            return [json.loads(line) for line in run('', 1000, covered=[(0x80000400, 0x80000500)]).splitlines()]
        mapped = mapped_replay(mapped_words)
        assert mapped[0]['entry'] == mapped[0]['destination'] == 0x60000000, mapped
        assert mapped[0]['physical_start'] == 0x1000 and mapped[0]['bytes'] == image['bytes'], mapped
        assert mapped[-1]['uncovered_entry'] == 0x60000000, mapped
        # Exact composition replay must select the identical first generation.
        exact = [json.loads(line) for line in run('0x60000000', 1000, exact=True).splitlines()]
        assert exact[0] == mapped[0], exact
        # Non-global and invalid mappings cannot acquire an executable declaration.
        for lo0, lo1 in [(0x5e, 0x9e), (0x5d, 0x9d)]:
            changed = mapped_words.copy()
            changed[13], changed[15] = 0x240a0000 | lo0, 0x240a0000 | lo1
            rejected = mapped_replay(changed)
            assert not any('physical_start' in row for row in rejected), rejected
        # Two virtual neighbors can have nonadjacent physical page sources.
        # A source-only batch must keep each first-fetch mapping independent.
        pages = words[:9] + [
            0x3c090800, 0x35290400, 0xad090000, 0xad000004,  # j 60001000; nop
            0x3c08a000, 0x35083000,
            0x3c092402, 0x3529002a, 0xad090000,
            0x3c0903e0, 0x35290008, 0xad090004, 0xad000008,
        ] + mapped_words[9:]
        pages[-6] = 0x240a00df  # odd half physical 3000, global/valid/cache3
        fixture = bytearray(rom)
        fixture[0x1000:0x1000 + 4 * len(pages)] = struct.pack(f'>{len(pages)}I', *pages)
        source.write_bytes(fixture)
        batch = run('0x60000000,0x60001000', 1000)
        assert batch == run('0x60000000,0x60001000', 1000, exact=True)
        rows = [json.loads(line) for line in batch.splitlines()]
        assert [(r['destination'], r['physical_start'], len(r['bytes'])) for r in rows[:-1]] == [
            (0x60000000, 0x1000, 12), (0x60001000, 0x3000, 12)], rows
        assert rows[-1]['remaining'] == 0
        source.write_bytes(rom)
        print('PASS mapped fetch: guest COP0/TLB writes, identical produced physical bytes, exact replay, non-global/invalid refusal')
        # No named target: an indirect fetch beyond supplied images must still
        # discover precisely the same completed producer, at its first fetch.
        unknown = [json.loads(line) for line in run('', 1000, covered=[(0x80000400, 0x80000500)]).splitlines()]
        assert unknown[0] == image and unknown[-1]['uncovered_entry'] == image['entry'], unknown
        # A listed unproven transfer reports the target its register held as
        # it executed (ADR-0222); an unexecuted listed site reports nothing.
        observed = [json.loads(line) for line in run('', 1000, covered=[(0x80000400, 0x80000500)],
                                                     sites=[0x8000042c, 0x80000430]).splitlines()]
        assert observed[0] == image and observed[-1]['indirect_targets'] == [[0x8000042c, 0x80001000]], observed[-1]
        assert 'indirect_targets' not in unknown[-1], unknown[-1]
        # The fixture's call is fixed at runtime 420+0xc; give it a synthetic
        # map placement. Source bytes identify which shared-slot image is live.
        def bound_observation(bindings, sites=None):
            return json.loads(run('', 1000, covered=[(0x80000400, 0x80000500)],
                                  sites=sites or [0x8000042c], bindings=bindings).splitlines()[-1])
        fixed = [[0x80000400, 0x80000400, 0x100, -2], [0x80001000, 0x80001000, 12, -2]]
        relocated = [[0x80800400, 0x80000400, 4 * len(words), 0x1000], fixed[1]]
        assert bound_observation(fixed)['indirect_targets'] == [[0x8000042c, 0x80001000]]
        assert bound_observation(relocated)['indirect_targets'] == [[0x8080042c, 0x80001000]]
        # Equal runtime slot, wrong ROM source: only the matching image wins.
        wrong = [0x80810400, 0x80000400, 4 * len(words), 0x1100]
        assert bound_observation(relocated + [wrong])['indirect_targets'] == [[0x8080042c, 0x80001000]]
        ambiguous = [0x80810400, 0x80000400, 4 * len(words), 0x1000]
        assert bound_observation(relocated + [ambiguous])['indirect_targets'] == []
        assert bound_observation([wrong, fixed[1]])['indirect_targets'] == []
        # Targets must be translated under the same live binding, including
        # uncached aliases. Mutated/unmatched and ambiguous targets are refused.
        target_binding = [0x80811000, 0xa0001000, 12, 0x1200]
        rom[0x1200:0x120c] = bytes(image['bytes'])
        source.write_bytes(rom)
        assert bound_observation([relocated[0], target_binding])['indirect_targets'] == [[0x8080042c, 0x80811000]]
        assert bound_observation([relocated[0], target_binding, [0x80821000, 0x80001000, 12, 0x1200]])['indirect_targets'] == []
        assert bound_observation([relocated[0], [0x80811000, 0x80001000, 12, 0x1300]])['indirect_targets'] == []
        assert bound_observation([[0x80800400, 0xa0000400, 4 * len(words), 0x1000], fixed[1]])['indirect_targets'] == [[0x8080042c, 0x80001000]]
        source.write_bytes(rom)

        assert run('', 1000, covered=[(0x80000400, 0x80000500)], sites=[0x8000042e], check=False) == 2
        # A finite budget can miss a later site. Coverage records that miss;
        # a sufficient budget observes it without manufacturing unvisited sites.
        short_sites = json.loads(run('', 4, covered=[(0x80000400, 0x80001100)],
                                     sites=[0x8000042c, 0x80000430]).splitlines()[-1])
        later_sites = json.loads(run('', 20, covered=[(0x80000400, 0x80001100)],
                                     sites=[0x8000042c, 0x80000430]).splitlines()[-1])
        assert short_sites['stop_reason'] == 'instruction_budget' and short_sites['observed_runtime_sites'] == []
        assert short_sites['unobserved_runtime_sites'] == [0x8000042c, 0x80000430]
        assert later_sites['observed_runtime_sites'] == [0x8000042c]
        assert later_sites['unobserved_runtime_sites'] == [0x80000430]
        # Coverage prevents recapture; a short budget must not invent bytes.
        covered = [json.loads(line) for line in run('', 20, covered=[(0x80000400, 0x80001100)]).splitlines()]
        assert len(covered) == 1 and covered[0]['uncovered_entry'] is None, covered
        short = [json.loads(line) for line in run('', 4, covered=[(0x80000400, 0x80000500)]).splitlines()]
        assert len(short) == 1 and short[0]['steps'] == 4 and short[0]['uncovered_entry'] is None, short
        # SP memory is taken at the entry fetch, before any guest instruction.
        entry = [json.loads(line) for line in run('0x80000400', 1000).splitlines()][-1]
        assert len(stop['sp']) == 0x2000 and stop['sp'] == entry['sp'] and entry['steps'] == 1, entry['steps']
        # The jump delay slot overwrites prefix RAM after the entry snapshot.
        # Capturing the stop-time bytes instead would retain 03e00008 at 0x1d8.
        assert bytes(stop['ram_prefix']) == rom[:0x400] == bytes(entry['ram_prefix']), stop['ram_prefix']
        assert stop['boot_entry'] == entry['boot_entry'] == 0x80000400
        # Snapshot Status at entry, before a later guest write in the jump slot.
        changed = bytearray(rom)
        changed[0x1030:0x1034] = struct.pack('>I', 0x40806000)  # mtc0 zero,Status
        source.write_bytes(changed)
        status_stop = json.loads(run('0x80001000', 1000).splitlines()[-1])
        assert status_stop['boot_status'] == entry['boot_status'] != 0
        source.write_bytes(rom)
        refused = [json.loads(line) for line in run('0x80001000', 4).splitlines()]
        assert len(refused) == 1 and refused[0]['remaining'] == 1 and refused[0]['steps'] == 4
        refused = [json.loads(line) for line in run('0x80000400', 1000).splitlines()]
        assert refused[0]['reason'] == 'no completed RAM producer' and not any('bytes' in r for r in refused)
        refused = [json.loads(line) for line in run('', 1000, covered=[(0x80000404, 0x80000500)]).splitlines()]
        assert refused[0]['reason'] == 'no completed RAM producer' and not any('bytes' in r for r in refused)
        # A completed PI producer in a numerically covered slot is a new
        # image when the full resident bytes differ. Prefix twins are irrelevant.
        saved_rom = bytes(rom)
        dma_words = [0x3c08a460, 0x24091000, 0xad090000,
                     0x3c091000, 0x35291800, 0xad090004,
                     0x2409000f, 0xad09000c,
                     0x3c198000, 0x37391000, 0x0320f809, 0,
                     0x1000ffff, 0]
        payload = struct.pack('>4I', 0x2402002a, 0x03e00008, 0, 0)
        rom[0x1000:0x1100] = bytes(0x100)
        rom[0x1000:0x1000 + len(dma_words)*4] = struct.pack(f'>{len(dma_words)}I', *dma_words)
        rom[0x1800:0x1810] = payload
        rom[0x1900:0x1910] = payload[:-4] + bytes.fromhex('00000001')
        source.write_bytes(rom)
        slot_bindings = [[0x80000400, 0x80000400, 0x100, -2],
                         [0x80801000, 0x80001000, 16, 0x1900]]
        def occupant_result(bound=slot_bindings):
            return [json.loads(line) for line in run('', 40,
                covered=[(0x80000400, 0x80000500), (0x80001000, 0x80001010)],
                sites=[0x80000428], bindings=bound).splitlines()]
        occupant, summary = occupant_result()
        assert occupant['raw_occupant'] and occupant['rom'] == 0x1800
        assert occupant['destination'] == occupant['entry'] == 0x80001000
        assert occupant['size'] == 16 and bytes(occupant['bytes']) == payload
        assert occupant['load_site'] == 0x8000041c
        assert summary['stop_reason'] == 'undeclared_slot_occupant'
        # A completed subrange from an already declared source is known even
        # when unrelated bytes outside that subrange differ in RAM.
        rom[0x1810:0x1820] = bytes(range(16)); source.write_bytes(rom)
        containing = [0x80811000, 0x80001000, 32, 0x1800]
        assert not any(r.get('raw_occupant') for r in occupant_result([slot_bindings[0], containing]))
        # Same content and two ambiguous declarations retain existing refusal.
        matching = [0x80811000, 0x80001000, 16, 0x1800]
        assert not any(r.get('raw_occupant') for r in occupant_result(slot_bindings + [matching]))
        ambiguous_results = occupant_result(slot_bindings + [matching, [0x80821000, 0xa0001000, 16, 0x1800]])
        assert not any(r.get('raw_occupant') for r in ambiguous_results)
        assert ambiguous_results[-1]['indirect_targets'] == []
        # A later equal-value CPU write destroys the completed DMA generation.
        mutated = dma_words[:8] + [0x3c0aa000, 0xad40100c] + dma_words[8:]
        rom[0x1000:0x1000 + len(mutated)*4] = struct.pack(f'>{len(mutated)}I', *mutated)
        source.write_bytes(rom)
        assert not any(r.get('raw_occupant') for r in occupant_result())
        # A misaligned/partial PI effect cannot masquerade as a complete source.
        mutated = dma_words.copy(); mutated[1] = 0x24091004
        rom[0x1000:0x1100] = bytes(0x100)
        rom[0x1000:0x1000 + len(mutated)*4] = struct.pack(f'>{len(mutated)}I', *mutated)
        source.write_bytes(rom)
        assert not any(r.get('raw_occupant') for r in occupant_result())
        # Adjacent DMA chunks from one loader site retain their entire source.
        chunks = [0x3c08a460, 0x24091000, 0x3c0a1000, 0x354a1800, 0x240b0002,
                  0xad090000, 0xad0a0004, 0x240c000f, 0xad0c000c,
                  0x8d020010, 0x30420001, 0x1440fffd, 0,
                  0x25290010, 0x254a0010, 0x256bffff, 0x1560fff4, 0,
                  0x3c198000, 0x37391000, 0x0320f809, 0, 0x1000ffff, 0]
        rom[0x1000:0x1100] = bytes(0x100)
        rom[0x1000:0x1000 + len(chunks)*4] = struct.pack(f'>{len(chunks)}I', *chunks)
        rom[0x1810:0x1820] = bytes(range(16))
        source.write_bytes(rom)
        merged = [json.loads(line) for line in run('', 1000,
            covered=[(0x80000400, 0x80000500), (0x80001000, 0x80001020)],
            sites=[0x80000450], bindings=slot_bindings).splitlines()][0]
        assert merged['raw_occupant'] and merged['size'] == 32, merged
        assert bytes(merged['bytes']) == rom[0x1800:0x1820] and merged['load_site'] == 0x80000420
        # A second DMA changes a later word while the fetched word stays equal.
        # The first generation is declared; the stale second one is refused.
        stale_dma = dma_words[:12] + [0x8d020010, 0x30420001, 0x1440fffd, 0,
                    0x24091000, 0xad090000, 0x3c091000, 0x35291a00, 0xad090004,
                    0x2409000f, 0xad09000c, 0x0320f809, 0, 0x1000ffff, 0]
        rom[0x1000:0x1100] = bytes(0x100)
        rom[0x1000:0x1000 + len(stale_dma)*4] = struct.pack(f'>{len(stale_dma)}I', *stale_dma)
        rom[0x1a00:0x1a10] = struct.pack('>4I', 0x2402002a, 0x03e00008, 0x24100001, 0)
        source.write_bytes(rom)
        stale_results = [json.loads(line) for line in run('', 1000,
            covered=[(0x80000400, 0x80000500), (0x80001000, 0x80001010)],
            sites=[0x80000428, 0x8000045c], bindings=[slot_bindings[0], matching]).splitlines()]
        assert not any(r.get('raw_occupant') for r in stale_results), [r for r in stale_results if r.get('raw_occupant')]
        rom[:] = saved_rom; source.write_bytes(rom)
        print('PASS covered shared-slot PI occupant: full bytes, source, aliases, ambiguity, equal-value overwrite and partial producer')
        # Fetching 1000 fills I-cache, then its store changes RAM at 1008.
        # Capturing 1008 must reject that stale instruction generation.
        stale = words.copy()
        stale[2:4] = [0x3c09ad19, 0x35290008]
        stale[5:7] = [0x24090000, 0]
        rom[0x1000:0x1000 + 4 * len(stale)] = struct.pack(f'>{len(stale)}I', *stale)
        source.write_bytes(rom)
        refused = [json.loads(line) for line in run('0x80001008', 1000).splitlines()]
        assert refused[0]['reason'] == 'stale instruction cache' and not any('bytes' in r for r in refused), refused
        refused = [json.loads(line) for line in run('', 1000, covered=[(0x80000400, 0x80001008)]).splitlines()]
        assert refused[0]['reason'] == 'stale instruction cache' and not any('bytes' in r for r in refused), refused
        # Synthetic fixtures cannot bypass production's ROM-derived CIC selection,
        # in any of the three accepted ROM byte orders.
        for width in (1, 2, 4):
            ordered = bytearray(len(rom))
            for lane in range(width):
                ordered[lane::width] = rom[width - 1 - lane::width]
            source.write_bytes(ordered)
            try:
                capture_many(source, [0x80001000])
                raise AssertionError('synthetic IPL3 was accepted for reset boot')
            except ValueError as error:
                assert str(error) == 'unsupported IPL3 CRC32 e8b8467d; no guessed CIC', str(error)

        # Exact batching must retain each first-fetch state when one entry
        # mutates another entry in the same produced range. The legacy batch
        # behavior still treats the first harvested range as covering both.
        words = [
            0x3c08a000, 0x35081000,       # t0 = KSEG1 0x1000
            0x3c09ad09, 0x35290020,       # t1 = sw t1,0x20(t0)
            0xad090000,                   # initial target1 word
            0x3c092402, 0x3529002a,       # t1 = addiu v0,zero,42 (mutation value)
            0x3c0a0320, 0x354a0008,       # t2 = jr t9
            0xad0a0004,                   # initial word at 0x1004
            0xad000008, 0xad00000c, 0xad000010, 0xad000014,
            0xad000018, 0xad00001c,       # fill the contiguous produced range
            0x3c0b2402, 0x356b0001,       # t3 = initial target2 word
            0xad0b0020,                   # initial word at 0x1020
            0x3c198000, 0x37391020,       # t9 = KSEG0 0x1020
            0x3c188000, 0x37181000,       # t8 = KSEG0 0x1000
            0x03000008, 0,                # jump to first target
            0xad090020,                   # target1 writes target2 after its fetch
            0x03200008, 0,                # jump to target2
        ]
        rom[0x1000:0x1000 + 4 * len(words)] = struct.pack(f'>{len(words)}I', *words)
        source.write_bytes(rom)

        legacy = [json.loads(line) for line in run('0x80001000,0x80001020', 1000).splitlines()]
        assert [row['entry'] for row in legacy if 'bytes' in row] == [0x80001000], legacy
        assert legacy[-1]['remaining'] == 0, legacy[-1]

        batched = [json.loads(line) for line in run('0x80001000,0x80001020', 1000, exact=True).splitlines()]
        first_capture, second_capture = [row for row in batched if 'bytes' in row]
        assert [first_capture['entry'], second_capture['entry']] == [0x80001000, 0x80001020], batched
        independent_first = [json.loads(line) for line in run('0x80001000', 1000, exact=True).splitlines()][0]
        independent_second = [json.loads(line) for line in run('0x80001020', 1000, exact=True).splitlines()][0]

        def first_fetch_identity(row):
            import hashlib
            return (row['entry'], row['destination'], row['steps'], row['cpu_writes'],
                    row['pi_dma'], row['bytes'], hashlib.sha256(bytes(row['bytes'])).hexdigest())

        assert first_fetch_identity(first_capture) == first_fetch_identity(independent_first)
        assert first_fetch_identity(second_capture) == first_fetch_identity(independent_second)
        assert first_capture['steps'] < second_capture['steps'], (first_capture['steps'], second_capture['steps'])
        assert first_capture['bytes'][0x20:0x24] == [0x24, 0x02, 0x00, 0x01], first_capture['bytes'][0x20:0x24]
        assert second_capture['bytes'][0x20:0x24] == [0x24, 0x02, 0x00, 0x2a], second_capture['bytes'][0x20:0x24]
        assert batched[-1]['remaining'] == 0, batched[-1]
    print('PASS ares harvest: deterministic synthetic text, exact RAM/PC/CPU-write ranges, SP memory at entry, budget refusal (declared post-IPL fixture)')

    # A recovered range can overlap known images. Only missing components are
    # added; static declarations and caller-supplied snapshots gain no authority.
    with tempfile.TemporaryDirectory(prefix='plaid-harvest-test-') as temporary:
        directory = Path(temporary)
        loads, program, receipt = [directory / f'{n}.json' for n in ('loads', 'map', 'receipt')]
        original = {'destination': '0x80001008', 'size': '0x4', 'rom': '0x20', 'encoding': 'raw'}
        loads.write_text(json.dumps({'source': 'synthetic', 'loads': [original]}))
        program.write_text(json.dumps({'direct_edges': [{'target': {'pc': 0x80001000}}], 'indirect_sites': []}))
        synthetic = dict(image, revision='synthetic-test', rom_sha256='synthetic-test', cic='fixture', budget=1000, consumed_rom=[])
        saved = harvest_boot.capture_many
        harvest_boot.capture_many = lambda *args: [synthetic]
        try:
            assert harvest_boot.harvest(source, loads, program, {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}, receipt)
            declarations = json.loads(loads.read_text())['loads']
            assert declarations == [dict(destination='0x80001000', size='0x8', rom='0x0', encoding='ares_boot', entry='0x80001000'), original]
            assert not harvest_boot.harvest(source, loads, program, {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}, receipt)
        finally:
            harvest_boot.capture_many = saved
        # An unproven indirect has no named target. Discovery still asks for
        # the first uncovered fetch and composes it through guarded ares_boot.
        loads.write_text(json.dumps({'source': 'synthetic', 'loads': [original]}))
        program.write_text(json.dumps({'direct_edges': [], 'indirect_sites': [{'closed_proof': None, 'candidates': [], 'observed': []}]}))
        requested = []
        def capture_unknown(rom, entries, covered, sites, bindings):
            requested.append((entries, covered))
            return [synthetic, {'uncovered_entry': synthetic['entry']}]
        harvest_boot.capture_many = capture_unknown
        try:
            assert harvest_boot.harvest(source, loads, program, {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}, receipt)
            assert requested == [([], [(0x80000000, 0x80000400), (0x80000400, 0x80000500), (0x80001008, 0x8000100c)])], requested
            assert json.loads(loads.read_text())['loads'][0]['encoding'] == 'ares_boot'
            assert json.loads(receipt.read_text())['uncovered_entry'] == synthetic['entry']
        finally:
            harvest_boot.capture_many = saved
        # A jump table no image supplies is captured at its site's first fetch,
        # and its piece is kept although it holds no code target.
        loads.write_text(json.dumps({'source': 'synthetic', 'loads': [original]}))
        table = {'table_start': 0x80001004, 'count': 1}
        program.write_text(json.dumps({'direct_edges': [], 'indirect_sites': [],
                                       'unresolved': [{'kind': 'pointer_table_source_missing', 'site': {'pc': 0x80000400},
                                                       'evidence': ['table-candidates:t']}],
                                       'evidence': {'table-candidates:t': {'detail': json.dumps(table)}}}))
        requested = []
        harvest_boot.capture_many = lambda rom, entries: requested.extend(entries) or [synthetic]
        try:
            assert harvest_boot.harvest(source, loads, program, {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}, receipt)
            assert requested == [0x80000400], requested
            assert json.loads(loads.read_text())['loads'][0] == dict(destination='0x80001000', size='0x8', rom='0x0', encoding='ares_boot', entry='0x80001000')
        finally:
            harvest_boot.capture_many = saved
        # Targets unproven calls took become discovery roots once; computed
        # jumps are not listed, and a repeated observation adds nothing.
        loads.write_text(json.dumps({'source': 'synthetic', 'loads': [original]}))
        program.write_text(json.dumps({'direct_edges': [], 'indirect_sites': [
            {'site': {'pc': 0x80000420}, 'closed_proof': None, 'link_register': 31, 'candidates': [], 'observed': []},
            {'site': {'pc': 0x80000430}, 'closed_proof': None, 'link_register': None, 'candidates': [], 'observed': []}]}))
        asked = []
        def capture_observed(rom, entries, covered, sites, bindings):
            asked.append(sites)
            return [{'uncovered_entry': None, 'indirect_targets': [[0x80000420, 0x80000460]]}]
        harvest_boot.capture_many = capture_observed
        try:
            info = {'header': {'boot_address': 0x80000400}, 'boot_image_size': 0x100}
            assert harvest_boot.harvest(source, loads, program, info, receipt)
            assert asked == [[0x80000420, 0xa0000420]], asked
            assert json.loads(loads.read_text())['observed_roots'] == [{'site': '0x80000420', 'target': '0x80000460'}]
            assert json.loads(receipt.read_text())['observed_roots'] == [[0x80000420, 0x80000460]]
            assert not harvest_boot.harvest(source, loads, program, info, receipt)
        finally:
            harvest_boot.capture_many = saved
        # PI DMA from the ROM into RAM outside every image is an RSP search
        # input only (ADR-0225): recorded once, without another CPU round.
        loads.write_text(json.dumps({'source': 'synthetic', 'loads': [original]}))
        dmas = [[0x2000, 0x10000100, 0x100], [0x2000, 0x10000100, 0x100], [0x420, 0x10000200, 0x40],
                [0x3000, 0x10000300, 0x6], [0x3004, 0x10000300, 0x8], [0x4000, 0x10002ff0, 0x20]]
        harvest_boot.capture_many = lambda rom, entries, covered, sites, bindings: [{'uncovered_entry': None, 'pi_dma': dmas}]
        dma_rom = directory / 'dma.z64'
        dma_rom.write_bytes(bytes(0x3000))
        try:
            assert not harvest_boot.harvest(dma_rom, loads, program, info, receipt)
            assert json.loads(loads.read_text())['rsp_sources'] == [{'destination': '0x80002000', 'size': '0x100', 'rom': '0x100'}]
            assert json.loads(receipt.read_text())['rsp_sources'] == [{'destination': '0x80002000', 'size': '0x100', 'rom': '0x100'}]
            before = loads.read_text()
            assert not harvest_boot.harvest(dma_rom, loads, program, info, receipt) and loads.read_text() == before
        finally:
            harvest_boot.capture_many = saved
    print('PASS ares harvest composition: preserve static images, split overlaps, capture missing jump tables, record observed call targets, record RSP DMA sources, stop when all targets are covered')


if __name__ == '__main__':
    main()
