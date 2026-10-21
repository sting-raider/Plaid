"""Analysis-only pinned ares boot capture. RAM files are outputs, never inputs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
REV = '9408cb43d4948fc3ea6e152a307a34348df3fe04'
BUDGET = 100_000_000
# Open-call coverage may extend observation, never the snapshot contract.
SITE_BUDGET = 1_000_000_000


def build_oracle():
    import fcntl
    spec = importlib.util.spec_from_file_location('ares_builder', ROOT / 'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    directory = ROOT / 'target/ares-boot/oracle'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'build.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return builder.build(ROOT / 'scripts/ares_boot.cpp', directory,
                             raw_fetch_access=True, physical_fetch_access=True,
                             rdram_burst_access=True, rdram_scalar_access=True, pi_dma_access=True,
                             cpu_instruction_access=True)


def capture_many(rom, entries, exact=False, covered=None, sites=None, bindings=None):
    if bindings is not None and (sites is None or not isinstance(bindings, (list, tuple)) or
            any(not isinstance(b, (list, tuple)) or len(b) != 4 or
                any(type(v) is not int or not 0 <= v <= 0xffffffff or v % 4 for v in b[:3]) or
                b[2] == 0 or b[0] + b[2] > 0x100000000 or b[1] + b[2] > 0x100000000 or
                (b[3] is not None and (type(b[3]) is not int or b[3] < -1 or b[3] % 4 and b[3] != -1))
                for b in bindings)):
        raise ValueError('invalid replay bindings')
    budget = SITE_BUDGET if sites else BUDGET
    if sites is not None and (covered is None or not isinstance(sites, (list, tuple)) or
                              any(type(s) is not int or not 0 <= s <= 0xffffffff or s % 4 for s in sites)):
        raise ValueError('indirect-target observation requires aligned site addresses and coverage ranges')
    if covered is not None:
        if (exact or not isinstance(covered, (list, tuple)) or not covered or
                any(not isinstance(r, (list, tuple)) or len(r) != 2 or
                    any(type(v) is not int or not 0 <= v <= 0xffffffff or v % 4 for v in r) or r[0] >= r[1]
                    for r in covered)):
            raise ValueError('uncovered fetch capture requires aligned, nonempty coverage ranges and no exact mode')
    rom = Path(rom).resolve()
    data = rom.read_bytes()
    if len(data) < 4096 or len(data) > 64 * 1024 * 1024 or len(data) % 4:
        raise ValueError('boot capture requires a word-aligned ROM of 4 KiB..64 MiB')
    width = {bytes.fromhex('37804012'): 2, bytes.fromhex('40123780'): 4}.get(data[:4])
    if width:
        canonical = bytearray(len(data))
        for lane in range(width):
            canonical[lane::width] = data[width - 1 - lane::width]
        with tempfile.TemporaryDirectory(prefix='plaid-canonical-') as temporary:
            path = Path(temporary) / 'input.z64'
            path.write_bytes(canonical)
            return capture_many(path, entries, exact=exact, covered=covered, sites=sites, bindings=bindings)
    if data[:4] != bytes.fromhex('80371240'):
        raise ValueError('unrecognized N64 byte-order signature')
    crc = zlib.crc32(data[0x40:0x1000])
    cics = {0x6170a4a1: '6101', 0x90bb6cb5: '6102', 0x0b050ee0: '6103',
            0x98bc2c86: '6105', 0xacc8580a: '6106'}
    if crc not in cics:
        raise ValueError(f'unsupported IPL3 CRC32 {crc:08x}; no guessed CIC')
    boot = int.from_bytes(data[8:12], 'big') - {0x0b050ee0: 0x100000, 0xacc8580a: 0x200000}.get(crc, 0)
    if os.name == 'nt':
        def linux(p):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(p)], text=True).strip()
        command = ['wsl', '-d', 'Ubuntu', '--exec', 'python3', linux(Path(__file__).resolve()),
                   linux(rom), ','.join(hex(e) for e in entries), '--many']
        if exact:
            command.append('--exact-many')
        if covered is not None:
            command.extend(['--covered', json.dumps(covered)])
        if sites is not None:
            command.extend(['--sites', json.dumps(sites)])
        if bindings is not None:
            command.extend(['--bindings', json.dumps(bindings)])
        # Includes a cold reference build; the actual replay below stays bounded.
        return json.loads(subprocess.check_output(command, text=True, timeout=1200))
    # DrvFS index preloading is much slower than a serial source check.
    os.environ['GIT_CONFIG_COUNT'] = '1'
    os.environ['GIT_CONFIG_KEY_0'] = 'core.preloadindex'
    os.environ['GIT_CONFIG_VALUE_0'] = 'false'
    exe = build_oracle()
    firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
    assert hashlib.sha256(firmware.read_bytes()).hexdigest() == 'fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd'
    with tempfile.TemporaryDirectory(prefix='plaid-ares-') as temporary:
        output = Path(temporary) / 'capture.json'
        command = [str(exe), str(rom), str(firmware), hex(boot), ','.join(hex(e) for e in entries), str(budget),
                   'CIC-NUS-' + cics[crc], str(output)]
        if exact:
            command.append('exact-many')
        if covered is not None:
            coverage = Path(temporary) / 'covered.txt'
            coverage.write_text(''.join(f'{lo} {hi}\n' for lo, hi in covered))
            command.extend(['uncovered', str(coverage)])
            if sites is not None:
                listed = Path(temporary) / 'sites.txt'
                listed.write_text(''.join(f'{s}\n' for s in sites))
                command.append(str(listed))
        if bindings is not None:
            bound = Path(temporary) / 'bindings.txt'
            bound.write_text(''.join(f'{a} {b} {n} {r if r is not None else -2}\n' for a, b, n, r in bindings))
            command.append(str(bound))
        started = time.perf_counter()
        subprocess.run(command, check=True, timeout=900)
        replay_seconds = round(time.perf_counter() - started, 3)
        results = [json.loads(line) for line in output.read_text().splitlines()]
    for result in results:
        result.update(format='plaid-ares-boot-harvest-v1', revision=REV, budget=budget, vi_budget=3600, replay_seconds=replay_seconds, rom_sha256=hashlib.sha256(data).hexdigest(),
                  firmware_sha256=hashlib.sha256(firmware.read_bytes()).hexdigest(), cic=cics[crc],
                  initial_state='cpu_power_pif_entry', controller='gamepad1_neutral')
        if 'bytes' in result:
            result['output_sha256'] = hashlib.sha256(bytes(result['bytes'])).hexdigest()
            result['consumed_rom'] = sorted({(p - 0x10000000, p - 0x10000000 + n)
                                             for _, p, n in result['pi_dma']
                                             if 0x10000000 <= p and p + n <= 0x10000000 + len(data)})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('entry')
    parser.add_argument('--many', action='store_true')
    parser.add_argument('--exact-many', action='store_true')
    parser.add_argument('--covered', type=json.loads)
    parser.add_argument('--sites', type=json.loads)
    parser.add_argument('--bindings', type=json.loads)
    args = parser.parse_args()
    entries = [int(v, 0) for v in args.entry.split(',') if v]
    results = capture_many(args.rom, entries, exact=args.exact_many, covered=args.covered, sites=args.sites, bindings=args.bindings)
    print(json.dumps(results if args.many or args.exact_many else next((r for r in results if 'bytes' in r), results[-1]), separators=(',', ':')))
