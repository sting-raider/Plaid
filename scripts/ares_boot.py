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
# Open-call and raw-occupant coverage may extend observation, never snapshots.
SITE_BUDGET = 2_000_000_000


def lock_exclusive(lock):
    if os.name == 'nt':
        import msvcrt
        while True:
            try:
                return msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            except OSError:  # LK_LOCK gives up after 10 s; keep waiting
                pass
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX)


def build_oracle():
    import ares_oracle as builder
    directory = ROOT / 'target/ares-boot/oracle'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'build.lock').open('w') as lock:
        lock_exclusive(lock)
        return builder.build(ROOT / 'scripts/ares_boot.cpp', directory,
                             raw_fetch_access=True, physical_fetch_access=True,
                             rdram_burst_access=True, rdram_scalar_access=True, pi_dma_access=True,
                             cpu_instruction_access=True)


# Everything that builds the oracle or shapes its output (spikes/003 build inputs).
ORACLE_SOURCES = ('scripts/ares_boot.py', 'scripts/ares_oracle.py', 'scripts/ares_boot.cpp', 'spikes/003-ares-oracle/run.py',
                  'spikes/003-ares-oracle/driver.cpp', 'spikes/044-ares-cpu-copy-dataflow/prepare.py')


def validate_refill(rows, data, anchor, target, natural):
    """Counterfactual sources never certify neutral reachability or call edges."""
    if not isinstance(rows, list) or len(rows) != 3 or any(not isinstance(r, dict) for r in rows):
        raise ValueError('refill requires anchor, source and footer')
    first, page, stop = rows
    root = stop.get('counterfactual')
    expected = dict(version=1, anchor=anchor, target=target, anchor_step=natural['steps'],
                    root_step=natural['steps'] + 1, applied=True)
    before = dict(expected, root_step=0, applied=False)
    same = lambda a, b: json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    if (not same(root, expected) or not same(first.get('counterfactual'), before) or
            not same(page.get('counterfactual'), expected) or stop.get('remaining') != 0 or
            stop.get('stop_reason') != 'entries_complete' or
            any(first.get(k) != natural.get(k) for k in
                ('entry', 'destination', 'physical_start', 'steps', 'bytes')) or
            page.get('entry') != target or not expected['root_step'] <= page.get('steps', -1) < BUDGET):
        raise ValueError('invalid counterfactual root/anchor/stop identity')
    source, start, physical, payload = (page.get(k) for k in
                                      ('rom_source', 'destination', 'physical_start', 'bytes'))
    if (any(type(v) is not int or v < 0 for v in (source, start, physical)) or
            not isinstance(payload, list) or not payload or
            any(type(b) is not int or not 0 <= b <= 255 for b in payload) or
            (start | physical | len(payload)) & 3 or source & 1 or
            not start <= target < start + len(payload) or
            not (start + len(payload) <= 0x80000000 or
                 0xc0000000 <= start < start + len(payload) <= 0x100000000) or
            physical + len(payload) > 0x800000 or
            source + len(payload) > len(data) or bytes(payload) != data[source:source + len(payload)]):
        raise ValueError('invalid completed refill ROM source')
    return page


def capture_refill(rom, anchor, target):
    """Fresh reset, authenticated anchor, one explicit PC root, raw DMA source.

    Cache namespace and output format differ from ordinary reset replay. The
    result supplies guarded source candidates, never observed call targets.
    """
    if (any(type(v) is not int or not 0 <= v <= 0xffffffff or v & 3 for v in (anchor, target)) or
            anchor == target or 0x80000000 <= target < 0xc0000000):
        raise ValueError('refill roots require distinct aligned addresses and a mapped target')
    rom = Path(rom).resolve()
    data = rom.read_bytes()
    width = {bytes.fromhex('37804012'): 2, bytes.fromhex('40123780'): 4}.get(data[:4])
    if width:
        canonical = bytearray(len(data))
        for lane in range(width):
            canonical[lane::width] = data[width - 1 - lane::width]
        with tempfile.TemporaryDirectory(prefix='plaid-refill-canonical-') as temporary:
            path = Path(temporary) / 'input.z64'
            path.write_bytes(canonical)
            return capture_refill(path, anchor, target)
    natural_rows = capture_many(rom, [anchor], exact=True)
    natural = next((r for r in natural_rows if r.get('entry') == anchor), None)
    if natural is None or natural.get('counterfactual') is not None:
        raise ValueError('neutral reset did not authenticate the refill anchor')
    key = hashlib.sha256(json.dumps(['refill-v1', REV,
        [hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ORACLE_SOURCES],
        hashlib.sha256(data).hexdigest(), anchor, target]).encode()).hexdigest()
    cached = Path(os.environ.get('PLAID_REPLAY_CACHE', Path.home() / '.cache/plaid/ares-replay')) / f'{key}.json'
    if cached.exists():
        rows = json.loads(cached.read_text())
    else:
        exe = build_oracle()
        firmware = ROOT / '.refs/ares/ares/System/Nintendo 64/pif.ntsc.rom'
        if hashlib.sha256(firmware.read_bytes()).hexdigest() != natural['firmware_sha256']:
            raise ValueError('refill firmware differs from authenticated reset')
        with tempfile.TemporaryDirectory(prefix='plaid-refill-') as temporary:
            output = Path(temporary) / 'source.jsonl'
            command = [str(exe), str(rom), str(firmware), hex(natural_rows[-1]['boot_entry']), hex(target),
                       str(BUDGET), 'CIC-NUS-' + natural['cic'], str(output), 'refill-v1', hex(anchor)]
            subprocess.run(command, check=True, timeout=300)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        # A completed, deterministic refusal is worth caching too: unresolved
        # roots recur across frontier rounds. Validation still runs on every hit.
        cached.parent.mkdir(parents=True, exist_ok=True)
        partial = cached.with_name(f'{key}.{os.getpid()}.tmp')
        partial.write_text(json.dumps(rows))
        partial.replace(cached)
    page = dict(validate_refill(rows, data, anchor, target, natural))
    page.update(format='plaid-ares-refill-source-v1', revision=REV,
                rom_sha256=hashlib.sha256(data).hexdigest(),
                output_sha256=hashlib.sha256(bytes(page['bytes'])).hexdigest())
    return page


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
    # A replay is deterministic in its sources and arguments, so an identical
    # request reuses the recorded results instead of launching ares (and WSL).
    key = hashlib.sha256(json.dumps([REV, [hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ORACLE_SOURCES],
                                     hashlib.sha256(data).hexdigest(), entries, exact, covered, sites, bindings]).encode()).hexdigest()
    cached = Path(os.environ.get('PLAID_REPLAY_CACHE', Path.home() / '.cache/plaid/ares-replay')) / f'{key}.json'
    if cached.exists():
        return json.loads(cached.read_text())
    # JSON-normalized, exactly as a cache hit or the WSL route returns it.
    results = json.loads(json.dumps(replay(rom, data, entries, exact, covered, sites, bindings, budget)))
    cached.parent.mkdir(parents=True, exist_ok=True)
    partial = cached.with_name(f'{key}.{os.getpid()}.tmp')
    partial.write_text(json.dumps(results))
    partial.replace(cached)
    return results


def replay(rom, data, entries, exact, covered, sites, bindings, budget):
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
                                             for _, p, n in result.get('pi_dma', [])
                                             if 0x10000000 <= p and p + n <= 0x10000000 + len(data)})
            if result.get('raw_occupant'):
                result['consumed_rom'] = [[result['rom'], result['rom'] + result['size']]]
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
