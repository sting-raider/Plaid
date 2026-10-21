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
    capture = dict(entered=True, boot_entry=0x80000400,
                   sp=[i % 256 for i in range(0x2000)], ram_prefix=[(i * 7 + 3) % 256 for i in range(0x400)],
                   rom_sha256='synthetic', revision='synthetic')
    with tempfile.TemporaryDirectory(prefix='plaid-boot-header-') as temporary:
        directory = Path(temporary)
        sp, ram = write_boot_state(capture, directory, 0x80000400)
        assert ','.join(map(str, capture['ram_prefix'])) in ram.read_text()
        assert ','.join(map(str, capture['sp'])) in sp.read_text()
        receipt = json.loads((directory / 'boot-state.json').read_text())
        assert receipt['rom_sha256'] == 'synthetic' and receipt['startup_payloads']['ram_prefix']['size'] == 0x400
        import hashlib
        assert receipt['startup_payloads']['ram_prefix']['sha256'] == hashlib.sha256(bytes(capture['ram_prefix'])).hexdigest()
        assert 'ram_prefix' not in receipt and 'sp' not in receipt
        write_boot_state(dict(capture, boot_entry=0xa0000400), directory, 0xa0000400)
        for change in [dict(entered=False), dict(boot_entry=0x80001000), dict(ram_prefix=None),
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


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(Path(__file__).resolve())], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True, timeout=600)
        return
    boot_header_contract()
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
        refused = [json.loads(line) for line in run('0x80001000', 4).splitlines()]
        assert len(refused) == 1 and refused[0]['remaining'] == 1 and refused[0]['steps'] == 4
        refused = [json.loads(line) for line in run('0x80000400', 1000).splitlines()]
        assert refused[0]['reason'] == 'no completed RAM producer' and not any('bytes' in r for r in refused)
        refused = [json.loads(line) for line in run('', 1000, covered=[(0x80000404, 0x80000500)]).splitlines()]
        assert refused[0]['reason'] == 'no completed RAM producer' and not any('bytes' in r for r in refused)
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
