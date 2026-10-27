"""Synthetic counterfactual refill/source contracts; no game or firmware bytes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from unittest.mock import patch

from ares_boot import ROOT, build_oracle, capture_refill, validate_refill
import harvest_boot


def main():
    for anchor, target in [(0, 0), (False, 4), (1, 4), (0, 0x80001000), (0, 1 << 32)]:
        try:
            capture_refill('never-read.z64', anchor, target)
        except ValueError:
            pass
        else:
            raise AssertionError('malformed root accepted')
    exe = build_oracle()
    firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    rom = bytearray(0x3000)
    rom[:4] = bytes.fromhex('80371240')
    # Produce a neutral anchor. The mapped target is never reached naturally.
    boot = [0x40806000, 0x3c08a000, 0x35081000, 0xad000000, 0xad000004,
            0xad000008, 0xad00000c, 0x3c198000, 0x37391000, 0x03200008, 0]
    # The reference takes a real instruction TLB miss. Its guest handler performs
    # PI DMA, waits, installs a global TLB mapping, then retries using ERET.
    handler = [0x3c08a460, 0x24092000, 0xad090000, 0x3c091000, 0x35291800,
               0xad090004, 0x2409000f, 0xad09000c, 0x8d020010, 0x30420001,
               0x1440fffd, 0, 0x40800000, 0x40802800, 0x3c0a6000, 0x408a5000,
               0x240a009f, 0x408a1000, 0x240a00df, 0x408a1800, 0x42000002, 0x42000018, 0]
    payload = struct.pack('>4I', 0x2402002a, 0x1000ffff, 0, 0)
    rom[0x1800:0x1810] = payload
    rom[0x1900:0x1910] = payload  # equal bytes at another source are not evidence
    rom[0x1000:0x1000 + len(boot) * 4] = struct.pack(f'>{len(boot)}I', *boot)
    with tempfile.TemporaryDirectory(prefix='plaid-refill-contract-') as temporary:
        directory = Path(temporary)
        source, output = directory / 'fixture.z64', directory / 'capture.jsonl'

        def run(changed=handler, anchor=0x80001000, target=0x60000000, mode=True):
            fixture = bytearray(rom)
            fixture[:0x100] = bytes(0x100)
            fixture[:len(changed) * 4] = struct.pack(f'>{len(changed)}I', *changed)
            source.write_bytes(fixture)
            cmd = [str(exe), str(source), str(firmware), '0x80000400', hex(target),
                   '10000', 'fixture', str(output)]
            cmd += ['refill-v1', hex(anchor)] if mode else ['exact-many']
            subprocess.run(cmd, check=True, timeout=30, env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            return [json.loads(line) for line in output.read_text().splitlines()]

        natural = run(target=0x80001000, mode=False)[0]
        neutral = run(mode=False)
        assert not any('bytes' in r for r in neutral) and neutral[-1]['remaining'] == 1
        rows = run()
        assert rows == run(), 'fresh resets differ'
        page = validate_refill(rows, source.read_bytes(), 0x80001000, 0x60000000, natural)
        assert page['rom_source'] == 0x1800 and bytes(page['bytes']) == payload
        assert page['physical_start'] == 0x2000 and page['destination'] == 0x60000000
        assert page['previous_fetches'][-1] == [0x80000054, 0x42000018]
        assert rows[-1]['steps'] == 64 and rows[-1]['stop_pc'] == 0x60000004

        for index, key, value in [(1, 'rom_source', 0x1804), (1, 'physical_start', 0x800000),
                                  (1, 'destination', 0x80002000), (1, 'bytes', []),
                                  (0, 'steps', 12), (2, 'remaining', 1),
                                  (2, 'counterfactual', None)]:
            changed = copy.deepcopy(rows)
            changed[index][key] = value
            try:
                validate_refill(changed, source.read_bytes(), 0x80001000, 0x60000000, natural)
            except ValueError:
                pass
            else:
                raise AssertionError(f'accepted changed {key}')
        # These are real observer/guest variants, including an equal-value write
        # through the uncached physical alias after the DMA has completed.
        variants = [handler[:12] + [0x3c0ba000, 0xad60200c] + handler[12:]]
        for index, value in [(1, 0x24092004), (6, 0x2409000d), (16, 0x240a009e),
                             (16, 0x240a009d)]:
            changed = handler.copy()
            changed[index] = value
            variants.append(changed)
        for changed in variants:
            result = run(changed)
            assert not any('rom_source' in r for r in result), [r.get('rom_source') for r in result]
        alternate = handler.copy()
        alternate[4] = 0x35291900
        other = next(r for r in run(alternate) if 'rom_source' in r)
        assert bytes(other['bytes']) == payload and other['rom_source'] == 0x1900
        missing = run(anchor=0x80001200)
        assert not missing[-1]['counterfactual']['applied']
        assert not any('rom_source' in r for r in missing)
        # Exercise the production wrapper, including footer-only boot metadata
        # and its separate cache. No special synthetic CIC enters production.
        natural_rows = [dict(natural, firmware_sha256=hashlib.sha256(firmware.read_bytes()).hexdigest(), cic='fixture'),
                        dict(boot_entry=0x80000400)]
        source.write_bytes(rom)
        calls = []

        def replay(command, **kwargs):
            assert command[3] == '0x80000400' and command[-2:] == ['refill-v1', '0x80001000']
            calls.append(command)
            Path(command[7]).write_text('\n'.join(json.dumps(r) for r in rows))

        with patch('ares_boot.capture_many', return_value=natural_rows), \
                patch('ares_boot.build_oracle', return_value=exe), \
                patch('ares_boot.subprocess.run', side_effect=replay), \
                patch.dict(os.environ, PLAID_REPLAY_CACHE=str(directory / 'cache')):
            captured = capture_refill(source, 0x80001000, 0x60000000)
            assert captured == capture_refill(source, 0x80001000, 0x60000000) and len(calls) == 1
            assert captured['format'] == 'plaid-ares-refill-source-v1'
            calls.clear()
            with patch('ares_boot.subprocess.run', side_effect=lambda command, **kwargs:
                       (calls.append(command), Path(command[7]).write_text(json.dumps(rows[-1])))):
                for _ in range(2):
                    try:
                        capture_refill(source, 0x80001000, 0x60001000)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('cached missing-source refusal accepted')
            assert len(calls) == 1, 'a deterministic negative replay was repeated'
        declarations, program, receipt = (directory / (name + '.json') for name in ('loads', 'map', 'receipt'))
        original = dict(destination='0x61000000', entry='0x61000000', size='0x10',
                        text_size='0x10', encoding='ares_tlb', physical='0x1000', slot=True)
        declarations.write_text(json.dumps(dict(source='synthetic', loads=[original])))
        program.write_text(json.dumps(dict(direct_edges=[dict(target=dict(pc=0x60000000))], indirect_sites=[])))
        with patch('harvest_boot.capture_many', return_value=[dict(entry=0x61000000, steps=11, physical_start=0x1000, bytes=[0] * 16)]), \
                patch('harvest_boot.capture_refill', return_value=captured):
            info = dict(header=dict(boot_address=0x80000400), boot_image_size=0x100)
            assert harvest_boot.harvest_refills(source, declarations, program, info, receipt)
            declared = json.loads(declarations.read_text())
            assert declared['loads'] == [original, dict(destination='0x60000000', size='0x10',
                rom='0x1800', encoding='tlb_raw', text_size='0x10', slot=True)]
            assert 'observed_roots' not in declared and 'rsp_sources' not in declared
            before = declarations.read_bytes()
            assert not harvest_boot.harvest_refills(source, declarations, program, info, receipt)
            assert declarations.read_bytes() == before
    print('PASS explicit refill roots: neutral isolation, real exception/DMA/TLB/ERET, '
          'repeat identity, full raw source, equal-write/partial/unaligned/invalid/ASID refusals')


if __name__ == '__main__':
    main()
