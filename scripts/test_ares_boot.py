"""Deterministic synthetic post-IPL harvest; no commercial ROM or IPL3 needed."""
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from ares_boot import ROOT, build_oracle, capture_many
import harvest_boot


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(Path(__file__).resolve())], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True, timeout=300)
        return
    exe = build_oracle()
    firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    rom = bytearray(0x3000)
    rom[:4] = bytes.fromhex('80371240')
    # Store executable words through KSEG1, then fetch the same text in KSEG0.
    words = [0x3c08a000, 0x35081000, 0x3c092402, 0x3529002a, 0xad090000,
             0x3c0903e0, 0x35290008, 0xad090004, 0xad000008,
             0x3c198000, 0x37391000, 0x03200008, 0]
    rom[0x1000:0x1000 + 4 * len(words)] = struct.pack(f'>{len(words)}I', *words)
    with tempfile.TemporaryDirectory(prefix='plaid-ares-test-') as temporary:
        directory = Path(temporary)
        source, output = directory / 'fixture.z64', directory / 'capture.json'
        source.write_bytes(rom)

        def run(target, budget):
            subprocess.run([str(exe), str(source), str(firmware), '0x80000400', target,
                            str(budget), 'fixture', str(output)], check=True, timeout=30)
            return output.read_bytes()

        first = run('0x80001000', 1000)
        assert run('0x80001000', 1000) == first
        image, stop = [json.loads(line) for line in first.splitlines()]
        assert image['entry'] == image['destination'] == 0x80001000, image
        assert bytes(image['bytes']) == struct.pack('>3I', 0x2402002a, 0x03e00008, 0), image
        assert image['cpu_writes'] == [[0x1000, 0x100c]] and image['pi_dma'] == [], image
        assert image['steps'] == 13 and stop['remaining'] == 0, (image, stop)
        # SP memory is taken at the entry fetch, before any guest instruction.
        entry = [json.loads(line) for line in run('0x80000400', 1000).splitlines()][-1]
        assert len(stop['sp']) == 0x2000 and stop['sp'] == entry['sp'] and entry['steps'] == 1, entry['steps']
        refused = [json.loads(line) for line in run('0x80001000', 4).splitlines()]
        assert len(refused) == 1 and refused[0]['remaining'] == 1 and refused[0]['steps'] == 4
        refused = [json.loads(line) for line in run('0x80000400', 1000).splitlines()]
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
    print('PASS ares harvest composition: preserve static images, split overlaps, stop when all targets are covered')


if __name__ == '__main__':
    main()
