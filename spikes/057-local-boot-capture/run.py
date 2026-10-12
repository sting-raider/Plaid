"""Capture an explicitly configured local ROM prefix; artifacts stay ignored."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
FIRMWARE = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--cic', choices=('CIC-NUS-6102', 'CIC-NUS-6105'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--history', choices=('sp',))
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--budget', type=int, default=10000)
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if os.name == 'nt':
        def linux_path(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a',
                str(path.resolve())], text=True).strip()
        command = ['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux_path(Path(__file__)),
            '--rom', linux_path(args.rom), '--cic', args.cic, '--output', linux_path(args.output),
            '--budget', str(args.budget)]
        if args.verify_existing:
            command.append('--verify-existing')
        if args.build:
            command.extend(['--build', linux_path(args.build)])
        if args.history:
            command.extend(['--history', args.history])
        if args.baseline:
            command.extend(['--baseline', linux_path(args.baseline)])
        subprocess.run(command, check=True)
        return
    assert 0 < args.budget <= 10000000
    if str(ROOT).startswith('/mnt/'):
        # Keep the complete Git source check, using serial index reads on DrvFS.
        # Threaded preloading can delay this scan for minutes on a cold tree.
        index = int(os.environ.get('GIT_CONFIG_COUNT', '0'))
        os.environ['GIT_CONFIG_COUNT'] = str(index + 1)
        os.environ[f'GIT_CONFIG_KEY_{index}'] = 'core.preloadIndex'
        os.environ[f'GIT_CONFIG_VALUE_{index}'] = 'false'
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'target') or output.is_relative_to(ROOT / 'artifacts')
    assert subprocess.run(['git', 'check-ignore', '-q', str(output / 'receipt.json')], cwd=ROOT).returncode == 0
    output.mkdir(parents=True, exist_ok=True)
    build = (args.build or output / 'build').resolve()
    assert build.is_relative_to(ROOT / 'target')
    data = args.rom.read_bytes()
    assert data[:4] == bytes.fromhex('80371240'), 'supply a canonical big-endian .z64 ROM'
    assert 4096 <= len(data) <= 64 * 1024 * 1024 and len(data) % 4 == 0
    assert FIRMWARE.stat().st_size == 1984
    assert digest(FIRMWARE) == 'fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd'
    spec = importlib.util.spec_from_file_location('builder', ROOT / 'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    sources = [ROOT / 'spikes' / p for p in ('006-ares-rom-source/driver.cpp',
        '004-ares-fetch/driver.cpp', '004-ares-fetch/boot_cic.hpp')]
    driver = ROOT / 'spikes/011-ares-cache-fetch/driver.cpp'
    options = dict(raw_fetch_access=True, physical_fetch_access=True)
    if args.history:
        driver = ROOT / 'spikes/040-ares-boot-sp-history/driver.cpp'
        sources.extend(ROOT / 'spikes' / p for p in (
            '011-ares-cache-fetch/driver.cpp', '040-ares-boot-sp-history/observer.hpp',
            '037-ares-boot-pi-queue-history/observer.hpp', '030-ares-boot-pi-history/observer.hpp',
            '027-ares-boot-history/observer.hpp', '032-ares-queue-identity/observer.hpp'))
        options.update(cache_fill_access=True, cache_operation_access=True, rdram_burst_access=True,
            rdram_scalar_access=True, fetch_boundary_access=True, pi_dma_access=True,
            queue_access=True, sp_backing_access=True)
    if not args.verify_existing:
        exe = builder.build(driver, build, extra_sources=sources, **options)
        for mode in ('plain', 'traced', 'repeat'):
            subprocess.run([str(exe), 'plain' if mode == 'plain' else 'traced', str(args.rom),
                str(output / f'{mode}.ndjson'), str(output / f'{mode}.json'),
                str(output / f'{mode}.messages'), str(args.budget), str(FIRMWARE), args.cic],
                check=True, timeout=600)
        rejected = subprocess.run([str(exe), 'plain', str(args.rom), str(output / 'bad.ndjson'),
            str(output / 'bad.json'), str(output / 'bad.messages'), str(args.budget), str(FIRMWARE),
            'CIC-NUS-6106'])
        assert rejected.returncode == 3 and not (output / 'bad.json').exists()
        if args.cic == 'CIC-NUS-6102':
            subprocess.run([str(exe), 'traced', str(args.rom), str(output / 'default.ndjson'),
                str(output / 'default.json'), str(output / 'default.messages'), str(args.budget),
                str(FIRMWARE)], check=True, timeout=600)
            assert digest(output / 'default.ndjson') == digest(output / 'traced.ndjson')
            assert digest(output / 'default.json') == digest(output / 'traced.json')
    states = [json.loads((output / f'{mode}.json').read_bytes()) for mode in ('plain', 'traced', 'repeat')]
    assert states[0] == states[1] == states[2]
    assert not (output / 'plain.ndjson').exists()
    assert digest(output / 'traced.ndjson') == digest(output / 'repeat.ndjson')
    assert len({digest(output / f'{mode}.messages') for mode in ('plain', 'traced', 'repeat')}) == 1
    if args.baseline:
        for suffix in ('ndjson', 'json', 'messages'):
            assert digest(output / f'traced.{suffix}') == digest(args.baseline / f'traced.{suffix}'), suffix
    count = 0
    domains = dict(pif=0, sp=0, ram=0, cartridge=0, other=0)
    with (output / 'traced.ndjson').open() as stream:
        header = json.loads(next(stream))
        assert header == dict(record='header', format='plaid-ares-fetch-research-v5',
            revision=builder.REV, rom_sha256=digest(args.rom), budget=args.budget,
            initial_state='cpu_power_pif_entry', mapped_cartridge_size=len(data) & ~7,
            source_policy='delegated_rom_halves_before_prologue',
            boot_inputs=dict(firmware_sha256=digest(FIRMWARE), firmware_size=1984,
                region='ntsc', cic=args.cic, rdram_size=8388608, deterministic_entropy=True,
                pif_processor='reference_hle', pif_checksum_enforced=True),
            cache_policy='selected_icache_line_at_prologue')
        for raw in stream:
            event = json.loads(raw)
            if event['record'] == 'end':
                assert event == dict(record='end', fetch_count=count, reason='instruction_call_budget')
                assert not stream.read()
                break
            assert event['record'] == 'fetch' and event['seq'] == count
            count += 1
            physical = event['physical']
            domain = ('pif' if 0x1fc00000 <= physical < 0x1fc007c0 else
                'sp' if 0x4000000 <= physical < 0x4002000 else 'ram' if physical < 0x800000 else
                'cartridge' if 0x10000000 <= physical < 0x1fc00000 else 'other')
            domains[domain] += 1
            if event['source']['kind'] == 'cartridge_rom':
                offset = event['source']['offset']
                assert not event['cached'] and physical == 0x10000000 + offset
                assert event['word'] == int.from_bytes(data[offset:offset+4], 'big')
        else:
            raise AssertionError('missing stop footer')
    receipt = dict(format='plaid-local-boot-capture-receipt-v0', revision=builder.REV,
        rom_sha256=digest(args.rom), firmware_sha256=digest(FIRMWARE), cic=args.cic,
        budget=args.budget, fetch_count=count, domains=domains,
        trace_sha256=digest(output / 'traced.ndjson'), checkpoint_sha256=digest(output / 'traced.json'),
        checkpoint_controls_agree=True, repeat_source_equal=True,
        driver_sha256=digest(driver), sources={str(p.relative_to(ROOT)): digest(p) for p in sources},
        cic_identity_certified=False, hardware_boot_certified=False, mutation_census_certified=False,
        guest_completion_claimed=False, native_complete=False)
    if args.history:
        history = output / 'traced.ndjson.history.ndjson'
        assert not (output / 'plain.ndjson.history.ndjson').exists()
        assert digest(history) == digest(output / 'repeat.ndjson.history.ndjson')
        with history.open('rb') as source:
            first = json.loads(source.readline())
            source.seek(max(0, history.stat().st_size - 512))
            last = json.loads(source.read().splitlines()[-1])
        assert first == dict(record='header', format='plaid-ares-access-history-v3',
            revision=builder.REV, rom_sha256=digest(args.rom), budget=args.budget,
            mapped_cartridge_size=len(data) & ~7, firmware_sha256=digest(FIRMWARE),
            policy='identity_ram_pi_queue_and_observed_sp_backing',
            lifecycle_policy='single_run_no_host_restore', paired_fetch_format=header['format'])
        assert last['record'] == 'end' and last['fetch_count'] == count
        assert last['reason'] == 'instruction_call_budget'
        receipt.update(history_format=first['format'], history_sha256=digest(history),
            history_records=last['record_count'])
    (output / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
