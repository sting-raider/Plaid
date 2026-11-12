"""ROM in, native executable out, with no per-game inputs (ADR-0183).

    python scripts/native.py <rom> [--name N] [--loads loads.json] [--rt64] [--seconds S]

Steps, each a plain `plaid` command whose output stays in target/native/<name>:
  infer-loads    fixed loads from the ROM's file table (or --loads, for ROMs
                 without one), plus the reset stub
  identify       libultra functions the host runtime replaces
  discover       with the ROM's relocatable overlays when it has a file table
  solve          the address-taken scope; when OPEN, refine copy-call sources,
                 then harvest with pinned ares and retry. If only unproven
                 indirect sites remain, they become fail-closed run-time
                 dispatch over the lowered entries (ADR-0233; the manifest
                 records native_complete: false). --strict refuses instead
  lower-map      size-based parts, compiled in parallel with gcc
  rsp-from-rom   derive and lower candidate microcode from ROM image pointers
  snapshots      oracle-only; never loaded by the default build
  sp-boot        SP DMEM/IMEM as the ROM's IPL3 leaves them in pinned ares
  ram-boot       IPL3's first 0x400 RDRAM bytes, before the game overwrites them
  validate       one build/run; --repair-loop optionally admits fault-3/15
                 captures in up to four rounds, never guest execution fallback
  --rt64         also link the RT64 window build (target/rt64-shim/Release)

Saves go to <out>/<name>.sra (SRAM) or <name>.fla (FlashRAM); EEPROM to
<name>.eep. The executables take the ROM again at run time with --rom.
"""
import argparse
import contextlib
from engine_paths import BUNDLED, work_root, tool, prepare_runtime
from fragment_mapped import partition_mapped
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native_audio import audio_peak
from harvest_boot import harvest, harvest_refills, harvest_vectors
from ares_boot import ORACLE_SOURCES, capture_many
from repair_record import write_record, admit_records, native_manifest

ROOT = Path(__file__).resolve().parents[1]
# Opt-in repair uses a shorter replay budget unless --deep is also supplied.
FAST_SITE_BUDGET = 100_000_000
REPAIR_ROUND_CAP = 4
OBJECT_CACHE = Path(os.environ.get('PLAID_OBJECT_CACHE', Path.home() / '.cache/plaid/objects'))
SIGNATURES = ROOT / '.refs/n64sym/src/builtin_signatures.sig'
RT64 = work_root(ROOT) / 'target/rt64-shim/Release'
VALIDATION_NS_PER_SAFEPOINT = 1000  # guest ns per loop iteration on the virtual clock

# Per-phase wall times, so a slow ROM is attributable without re-running the
# whole pipeline under a profiler. Each entry is (name, seconds, cached).
TIMINGS = []
_PHASES = []


@contextlib.contextmanager
def phase(name):
    """Time one named pipeline phase.

    `memo_plaid` marks the innermost phase as cached when it restores a
    recorded analysis result, so a receipt never hides a skipped phase."""
    frame = {'name': name, 'calls': 0, 'cached': 0}
    started = time.perf_counter()
    _PHASES.append(frame)
    try:
        yield
    finally:
        _PHASES.pop()
        TIMINGS.append((name, time.perf_counter() - started,
                        bool(frame['calls']) and frame['cached'] == frame['calls']))


def print_timings():
    """One aligned line per phase, in pipeline order, with cached phases marked."""
    if not TIMINGS:
        return
    width = max(len(name) for name, _, _ in TIMINGS)
    print(f'timings: total {sum(t for _, t, _ in TIMINGS):.3f} s', flush=True)
    for name, elapsed, cached in TIMINGS:
        print(f'timings:   {name:<{width}} {elapsed:9.3f} s{"  (cached)" if cached else ""}', flush=True)


def run(*args, **kw):
    print('+', ' '.join(str(a) for a in args), flush=True)
    return subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kw)


def plaid(*args, **kw):
    return run(ROOT / 'target/release/plaid', *args, **kw)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def memo_plaid(*args, writes=()):
    """An analysis command is deterministic in the plaid binary, its arguments,
    the files they name and the analysis-time ares sources it may replay, so
    an identical invocation restores the recorded stdout and written files
    (ADR-0248). `writes` are outputs only, never read, so not part of the key."""
    exe = ROOT / ('target/release/plaid.exe' if os.name == 'nt' else 'target/release/plaid')
    inputs = [digest(exe), [digest(ROOT / p) for p in ORACLE_SOURCES]]
    for a in args:
        path = Path(str(a))
        inputs.append([str(a), digest(path)] if a not in writes and path.is_file() else str(a))
    store = work_root(ROOT) / 'target/native-cache' / hashlib.sha256(json.dumps(inputs).encode()).hexdigest()
    if _PHASES:
        _PHASES[-1]['calls'] += 1
    if not (store / 'stdout').exists():
        try:
            result = plaid(*args, capture_output=True, text=True)
        except subprocess.CalledProcessError as error:
            sys.stderr.write(error.stderr)
            raise
        sys.stderr.write(result.stderr)
        partial = store.with_name(f'{store.name}.{os.getpid()}.tmp')
        partial.mkdir(parents=True, exist_ok=True)
        for n, path in enumerate(writes):
            (partial / str(n)).write_bytes(Path(path).read_bytes())
        (partial / 'stdout').write_text(result.stdout)
        try:
            partial.replace(store)
        except OSError:  # an identical concurrent invocation recorded it first
            shutil.rmtree(partial)
    else:
        if _PHASES:
            _PHASES[-1]['cached'] += 1
        print('+ (cached)', *args, flush=True)
    for n, path in enumerate(writes):
        Path(path).write_bytes((store / str(n)).read_bytes())
    return (store / 'stdout').read_text()


def discover_map(arguments, overlay_support, output):
    """File-table presence is immutable across refinements of the same ROM."""
    if overlay_support is False:
        print(memo_plaid(*arguments, writes=(output,)).strip())
        return False
    try:
        print(memo_plaid(*arguments, '--overlays', writes=(output,)).strip().splitlines()[-1])
    except subprocess.CalledProcessError as error:
        if 'file table' not in error.stderr:
            sys.exit(error.stderr)
        print(memo_plaid(*arguments, writes=(output,)).strip())
        return False
    return True


def part_compiler():
    """Clang when installed (targeting MinGW on Windows, so GCC links it), else GCC."""
    if BUNDLED:
        return [tool('clang'), '--target=x86_64-w64-windows-gnu',
                '--sysroot=' + str(ROOT / 'toolchain/mingw/x86_64-w64-mingw32')]
    if not shutil.which('clang'):
        return ['gcc']
    return ['clang', '--target=x86_64-w64-windows-gnu'] if os.name == 'nt' else ['clang']


def compile_source(source, flags, dependencies, compiler):
    obj = Path(f'{source}.o')
    stamp = Path(f'{obj}.sha256')
    digest = hashlib.sha256(source.read_bytes() + compiler + dependencies +
                            json.dumps(list(map(str, flags))).encode()).hexdigest()
    if not obj.exists() or not stamp.exists() or stamp.read_text() != digest:
        # Objects are content-addressed machine-wide, so a unit another build
        # already compiled (shared RSP microcode, a renamed game) is copied.
        shared = OBJECT_CACHE / f'{digest}.o'
        temporary = Path(f'{obj}.tmp')
        stamp.unlink(missing_ok=True)
        try:
            if shared.exists():
                shutil.copyfile(shared, temporary)
            else:
                run(*flags, '-c', source, '-o', temporary)
                OBJECT_CACHE.mkdir(parents=True, exist_ok=True)
                partial = shared.with_name(f'{digest}.{os.getpid()}.{threading.get_ident()}.tmp')
                shutil.copyfile(temporary, partial)
                partial.replace(shared)
            temporary.replace(obj)
            stamp.write_text(digest)
        finally:
            temporary.unlink(missing_ok=True)
    return obj


def compile_workers():
    """All logical CPUs, fewer if free RAM could not hold that many gcc processes."""
    workers = os.cpu_count() or 1
    try:
        import psutil
        return max(1, min(workers, int(psutil.virtual_memory().available / (1 << 30) / 0.5)))
    except ImportError:  # shortcut: no memory cap without psutil; add one if a host swaps
        return workers


def compile_all(jobs):
    """Compile (source, flags, dependencies) jobs on one pool, largest first so
    the longest unit starts at once and the tail stays short; results keep job order.
    Each object is keyed on the version of the compiler that builds it."""
    versions = {c: subprocess.check_output([c, '--version']) for c in {flags[0] for _, flags, _ in jobs}}
    order = sorted(range(len(jobs)), key=lambda i: -jobs[i][0].stat().st_size)
    objs = [None] * len(jobs)
    with ThreadPoolExecutor(compile_workers()) as pool:
        for i, obj in zip(order, pool.map(lambda i: compile_source(*jobs[i], versions[jobs[i][1][0]]), order)):
            objs[i] = obj
    return objs


def rsp_dependencies():
    return b''.join(p.read_bytes() for p in sorted((ROOT / 'crates/plaid-lower/src').glob('rsp*.h')))


def lower_parts(rom, mapping, entry, exit_pc, output, block_count, residual):
    # Remove stale sources when a smaller split replaces an earlier build.
    for old_part in output.parent.glob(f'{output.stem}.part*.c'):
        old_part.unlink()
    part_count = min(64, max(16, (block_count + 2499) // 2500))
    plaid('lower-map', rom, mapping, entry, exit_pc, output, '--parts', str(part_count),
          '--runtime-unit', *(['--residual-dispatch'] if residual else []), stdout=subprocess.DEVNULL)


def write_boot_state(capture, out, entry):
    """Keep the bounded startup payload and its analysis provenance together."""
    if (capture.get('boot_entry') != entry or not 0x80000000 <= entry < 0xc0000000 or
            not 0x400 <= entry & 0x1fffffff < 0x800000):
        raise ValueError('post-IPL entry does not leave the RDRAM prefix outside executable code')
    for field, size in [('sp', 0x2000), ('ram_prefix', 0x400)]:
        data = capture.get(field)
        if (capture.get('entered') is not True or not isinstance(data, list) or len(data) != size or
                any(type(b) is not int or not 0 <= b <= 255 for b in data)):
            raise ValueError(f'pinned ares supplied no valid post-IPL {field}')
    status = capture.get('boot_status')
    if type(status) is not int or not 0 <= status <= 0xffffffff:
        raise ValueError('pinned ares supplied no valid post-IPL Status')
    entryhi = capture.get('boot_entryhi')
    if type(entryhi) is not int or not 0 <= entryhi < 1 << 64:
        raise ValueError('pinned ares supplied no valid post-IPL EntryHi')
    cp0 = capture.get('boot_cp0')
    if (not isinstance(cp0, dict) or set(cp0) != {'context', 'xcontext', 'wired', 'cause'} or
            any(type(cp0[key]) is not int or not 0 <= cp0[key] < 1 << bits
                for key, bits in [('context', 64), ('xcontext', 64), ('wired', 6), ('cause', 32)]) or
            cp0['context'] & 15 or cp0['xcontext'] & 15):
        raise ValueError('pinned ares supplied no valid post-IPL global CP0 state')
    copy = capture.get('boot_rom_copy')
    if (not isinstance(copy, dict) or set(copy) != {'destination', 'rom', 'size', 'verified'} or
            any(type(copy.get(k)) is not int for k in ('destination', 'rom', 'size')) or
            copy != dict(destination=entry & 0x1fffffff, rom=0x1000, size=0x100000, verified=True) or
            copy.get('verified') is not True or copy['destination'] + copy['size'] > 0x800000):
        raise ValueError('pinned ares did not authenticate the complete post-IPL ROM copy')
    sp_boot, ram_boot = out / 'sp_boot.h', out / 'ram_boot.h'
    sp_boot.write_text('static const u8 plaid_sp_boot[0x2000] = {' + ','.join(map(str, capture['sp'])) + '};\n')
    ram_boot.write_text(f'#define PLAID_BOOT_STATUS {status}u\n#define PLAID_BOOT_ENTRYHI {entryhi}ull\n'
                        + ''.join(f'#define PLAID_BOOT_{key.upper()} {value}ull\n' for key, value in cp0.items()) +
                        f'#define PLAID_BOOT_ROM_COPY_BASE {copy["destination"]}u\n#define PLAID_BOOT_ROM_COPY_SIZE {copy["size"]}u\n' +
                        'static const u8 plaid_ram_boot[] = {' + ','.join(map(str, capture['ram_prefix'])) + '};\n')
    receipt = {k: v for k, v in capture.items() if k not in ('sp', 'ram_prefix')}
    receipt['startup_payloads'] = {field: {'size': len(capture[field]), 'sha256': hashlib.sha256(bytes(capture[field])).hexdigest()}
                                   for field in ('sp', 'ram_prefix')}
    (out / 'boot-state.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return sp_boot, ram_boot


def validation_stop(result):
    lines = [line for line in result.stdout.splitlines() if line.startswith('{"stop"')]
    try:
        stop = json.loads(lines[-1])
        if type(stop.get('fault')) is int and isinstance(stop.get('fault_pc'), str):
            return stop
    except (IndexError, ValueError, AttributeError):
        pass
    return None


def repair_loop(build, records, round_cap=REPAIR_ROUND_CAP):
    """Only this invocation's captures and explicit inputs enter the next build."""
    records = list(records)
    seen = {json.loads(path.read_text())['sha256'] for path in records}
    for number in range(1, round_cap + 1):
        try:
            result, record = build(records)
        except (SystemExit, subprocess.SubprocessError, OSError, ValueError):
            print(f'repair round {number}: fault=none pc=none stop=build-or-validation-error', flush=True)
            raise
        stop = validation_stop(result)
        fault, pc = (stop['fault'], stop['fault_pc']) if stop else ('none', 'none')
        record_hash = json.loads(record.read_text())['sha256'] if record else None
        if stop and fault == 0 and result.returncode == 0:
            reason = 'success'
        elif not stop:
            reason = 'missing-or-invalid-stop'
        elif fault not in (3, 15):
            reason = 'non-repairable-stop'
        elif not record:
            reason = 'capture-unavailable'
        elif record_hash in seen:
            reason = 'repeated-hash'
        elif number == round_cap:
            reason = 'round-cap'
        else:
            reason = 'admit-and-rebuild'
        print(f'repair round {number}: fault={fault} pc={pc}' +
              (f' sha256={record_hash}' if record_hash else '') + f' stop={reason}', flush=True)
        if reason == 'success':
            return
        if reason != 'admit-and-rebuild':
            sys.exit(result.stderr[-2000:] + f'\nnative validation failed ({reason}); executable is not accepted')
        records.append(record)
        seen.add(record_hash)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('rom', type=Path)
    ap.add_argument('--name')
    ap.add_argument('--loads', type=Path, help='plaid-loads-v0 for a ROM without a file table')
    ap.add_argument('--rt64', action='store_true')
    ap.add_argument('--strict', action='store_true', help='build only a CLOSED map; refuse residual run-time dispatch (ADR-0233)')
    ap.add_argument('--rsp-gfx', action='store_true', help='run lowered graphics microcode; requires --rt64')
    ap.add_argument('--rsp-dump', type=Path, help='capture IMEM for oracle comparison only; never a build input')
    ap.add_argument('--repair-record', type=Path, action='append', default=[], help='admit a captured code image; repeat in generation order')
    ap.add_argument('--repair-capture', action='store_true', help='compatibility flag; validation always captures fault-3/15 stops')
    ap.add_argument('--repair-loop', action='store_true', help='try bounded automatic repair with a shorter site replay budget')
    ap.add_argument('--press', action='append', default=[], help='runtime button press, e.g. 0x1000@300:4')
    ap.add_argument('--require-audio', action='store_true', help='reject a validation run with empty or silent PCM')
    ap.add_argument('--deep', action='store_true', help='watch unproven indirect sites for the full analysis-time replay budget (default without --repair-loop)')
    ap.add_argument('--seconds', type=float, default=60, help='length of the native validation run')
    ap.add_argument('--realtime', action='store_true',
                    help='validate on the wall clock instead of the virtual clock (ADR-0333)')
    a = ap.parse_args()
    if a.rsp_gfx and not a.rt64:
        ap.error('--rsp-gfx requires --rt64')
    if a.repair_loop and not a.deep:
        os.environ.setdefault('PLAID_SITE_BUDGET', str(FAST_SITE_BUDGET))
    else:
        os.environ.pop('PLAID_SITE_BUDGET', None)
    # Keep the first round's refined loads, rather than replaying analysis or
    # inheriting observations left by a previous invocation in the output dir.
    base_loads = a.loads

    def build(records):
        a.repair_record = records
        result, record, inferred = build_once(a)
        if base_loads is None:
            a.loads = inferred
        return result, record

    repair_loop(build, a.repair_record, REPAIR_ROUND_CAP if a.repair_loop else 1)


def build_once(a):
    rom = a.rom.resolve()
    # 32 characters keep both Zelda titles (and similar series) apart
    name = a.name or ''.join(c for c in rom.stem.lower() if c.isalnum())[:32]
    out = work_root(ROOT) / 'target/native' / name
    texts = out / 'rsp-rom'
    for d in (out, texts):
        d.mkdir(parents=True, exist_ok=True)

    build_env = os.environ.copy()
    build_env.setdefault('CARGO_PROFILE_RELEASE_INCREMENTAL', 'true')
    with phase('build'):
        if not BUNDLED:
            run('cargo', 'build', '-q', '--release', '-p', 'plaid', env=build_env)
    with phase('rom-info'):
        info = json.loads(plaid('rom-info', rom, capture_output=True, text=True).stdout)
    entry = info['header']['boot_address']  # the header entry, less a CIC-6103/6106 offset
    loads = a.loads.resolve() if a.loads else out / 'loads.json'
    if not a.loads:
        with phase('infer-loads'):
            plaid('infer-loads', rom, loads)
    base_loads = loads
    if a.repair_record:
        admitted = out / 'observed-loads.json'
        shutil.copyfile(loads, admitted)
        admit_records(admitted, a.repair_record)
        loads = admitted
    # the main image ends where the entry stub's BSS clear begins; else IPL3's 1 MiB
    window = [rom, '0x1000', entry, hex(info.get('boot_image_size') or 0x100000)]
    m = out / 'map.json'
    overlay_support = None
    for attempt in range(64):
        with phase('harvest-vectors'):
            harvest_vectors(rom, loads, out / 'vector-harvest.json')
        # A ROM with no file table and no reset stub has no loads to declare.
        with_loads = ['--loads', loads] if (json.loads(loads.read_text())['loads'] or json.loads(loads.read_text()).get('observed_images')) else []
        with phase('identify'):
            (out / 'id.json').write_text(memo_plaid('identify', *window, SIGNATURES, *with_loads), newline='')
        discover = ['discover', *window, entry, m, out / 'id.json', *with_loads, '--address-taken', '--fr0']
        with phase('discover'):
            overlay_support = discover_map(discover, overlay_support, m)
        program = json.loads(m.read_text())
        with phase('partition'):
            partitioned = attempt < 63 and partition_mapped(loads, m)
        if partitioned:
            continue
        with phase('solve'):
            verdict = json.loads(memo_plaid('solve', rom, m, '--address-taken'))
        if verdict['status'] == 'closed' or a.loads or a.repair_record or attempt == 63:
            break
        previous_loads = loads.read_bytes()
        with phase('infer-call-loads'):
            plaid('infer-call-loads', rom, m, loads)
        if loads.read_bytes() != previous_loads:
            continue
        print('solve', verdict['status'], len(verdict['blockers']), 'blockers; analysis-time boot harvest', flush=True)
        with phase('harvest'):
            harvested = harvest(rom, loads, m, info, out / f'boot-harvest-{attempt}.json')
            if not harvested:
                harvested = harvest_refills(rom, loads, m, info, out / f'refill-harvest-{attempt}.json')
        if not harvested:
            break
    print('solve', verdict['status'], len(verdict['blockers']), 'blockers')
    residual = verdict['status'] != 'closed' and not a.strict
    if residual:
        with phase('residual-solve'):
            verdict = json.loads(memo_plaid('solve', rom, m, '--residual-dispatch'))
        print('residual-dispatch solve', verdict['status'], len(verdict['blockers']), 'blockers,', len(verdict.get('residual_sites', [])), 'residual sites')
    if verdict['status'] != 'closed' and not (residual and verdict.get('trapped_sites') and all(b in verdict['trapped_sites'] for b in verdict['blockers'])):
        sys.exit('not CLOSED under the address-taken scope' + ('' if a.strict else ', even with residual dispatch') + ': nothing is built')
    # Always rewritten: a stale manifest must never describe a later build.
    (out / 'native-manifest.json').write_text(json.dumps(native_manifest(program, verdict, residual), indent=2) + '\n')

    # The native run starts SP memory as the ROM's own IPL3 leaves it (ADR-0195).
    try:
        with phase('boot-state'):
            sp_boot, ram_boot = write_boot_state(capture_many(rom, [entry])[-1], out, entry)
    except ValueError as error:
        sys.exit(str(error) + ': nothing is built')

    c = out / f'{name}.c'
    # RAM address zero is executable when the guest owns its refill vector.
    exit_pc = '0xbfc00000' if program.get('tlb_exception_vectors') else '0x80000000'
    # Both read only the final map and loads and write separate outputs, so they
    # run side by side (one phase: the shared phase stack is not thread-safe).
    with phase('rsp-from-rom+lower'), ThreadPoolExecutor(2) as pool:
        rsp = pool.submit(plaid, 'rsp-from-rom', rom, m, texts, '--loads', loads)
        lower_parts(rom, m, entry, exit_pc, c, len(program['blocks']), residual)
        rsp.result()
    rsp_manifest = json.loads((texts / 'rsp-files.json').read_text())
    # Generated game code builds at -O0: optimising it cost ~18x the compile
    # time and ran no faster, since each guest op is guest-state memory traffic.
    # Clang -O0 is ~4x faster again than GCC -O0; GCC stays the fallback.
    # Clang errors by default on the setjmp buffer pointer type that GCC only warns about.
    part_flags = ['-O0', '-std=gnu11', '-w', '-Wno-incompatible-pointer-types', '-DPLAID_SAFEPOINTS']
    cc = [*part_compiler(), *part_flags]
    # CPU helpers and RSP arithmetic are embedded in their generated sources.
    # Only the shared RSP ABI headers remain external include dependencies.
    rsp_headers = rsp_dependencies()
    parts = [c, *sorted(out.glob(f'{name}.part*.c'))]
    runtime_header=out/f'{name}.runtime.h'
    rt = [tool('gcc'), '-O1', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS', '-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', ROOT / 'crates/plaid-lower/src', f'-DPLAID_LOWERED="{runtime_header.name}"', f'-DPLAID_SP_BOOT="{sp_boot.name}"', f'-DPLAID_RAM_BOOT="{ram_boot.name}"', '-I', out]
    # Keep runtime objects in the build directory, alongside the generated C.
    runtime_source = out / 'runtime.c'
    runtime_source.write_text(f'#include "{(ROOT / "runtime/plaid_rt.c").as_posix()}"\n')
    runtime_deps = runtime_header.read_bytes() + sp_boot.read_bytes() + ram_boot.read_bytes() + (ROOT / 'runtime/plaid_rt.c').read_bytes() + b''.join(p.read_bytes() for p in sorted((ROOT / 'runtime').glob('*.h'))) + rsp_headers
    window_exe = RT64 / f'{name}{"-rsp" if a.rsp_gfx else ""}-rt64.exe'
    if a.rt64:
        window_source = out / 'runtime-window.c'
        window_source.write_bytes(runtime_source.read_bytes())
    exe = out / f'{name}.exe'
    saves = ['--sram', out / f'{name}.sra', '--flash', out / f'{name}.fla', '--save', out / f'{name}.eep']

    texts_c = [texts / (t['name'] + '.c') for t in rsp_manifest['texts']] + [texts / 'rsp_registry.c']
    flags = [tool('gcc'), '-O2', '-I', ROOT / 'crates/plaid-lower/src']
    # One pool for every C unit: the RSP texts and runtime fill the CPU while the last CPU parts finish.
    # __builtin_setjmp buffers are compiler-specific and runtime/jumps.h longjmps
    # from GCC code, so a part that sets a jump buffer compiles with GCC too.
    jobs = [(p, [tool('gcc'), *part_flags] if b'__builtin_setjmp' in p.read_bytes() else cc, b'') for p in parts] + [(p, flags, rsp_headers) for p in texts_c] + [(runtime_source, rt, runtime_deps)]
    if a.rt64:
        jobs.append((window_source, [*rt, '-DPLAID_RT64'], runtime_deps))
    with phase('gcc'):
        objs = compile_all(jobs)
    part_objs, objects = objs[:len(parts)], objs[len(parts):len(parts) + len(texts_c)]
    main_obj = objs[len(parts) + len(texts_c)]
    if a.rt64:
        window_obj = objs[-1]
    with phase('link'):
        run(tool('gcc'), main_obj, *part_objs, '-pthread', *objects, '-o', exe)
        prepare_runtime(out)
    if a.rt64:
        with phase('link-window'):
            resource = out / 'plaid-icon.o'
            prepare_runtime(RT64)
            run(tool('windres'), 'runtime/rt64/icon.rc', '-I', 'runtime/rt64', '-o', resource)
            run(tool('gcc'), window_obj, *part_objs, RT64 / 'plaid_rt64.dll', '-pthread', *objects, resource, '-o', window_exe)
    command = [str(window_exe if a.rt64 else exe), '--rom', str(rom), *map(str, saves),
               '--stop-at', 'none', '--seconds', str(a.seconds)]
    if a.rsp_gfx:
        command.append('--rsp-gfx')
    if a.rsp_dump:
        a.rsp_dump.mkdir(parents=True, exist_ok=True)
        command.extend(['--rsp-dump', str(a.rsp_dump.resolve())])
    for press in a.press:
        command.extend(['--press', press])
    if a.require_audio:
        command.extend(['--wav', str(out / 'validation.wav')])
    # Validation runs are silent (SDL's dummy driver); --wav still records the audio.
    env = {**os.environ, 'SDL_AUDIODRIVER': 'dummy'}
    # The virtual clock (ADR-0332) replays exactly and skips idle time, so a
    # 60 s validation takes ~15-25 s and host load cannot starve retraces.
    if not a.realtime:
        env.setdefault('PLAID_DETERMINISTIC', str(VALIDATION_NS_PER_SAFEPOINT))
    with tempfile.TemporaryDirectory(dir=out, prefix='repair-raw-') as temporary:
        raw_capture = Path(temporary) / 'capture.json'
        command.extend(['--repair-capture', str(raw_capture)])
        with phase('validation'):
            r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=a.seconds + 60, env=env)
        stop = validation_stop(r)
        record = None
        if stop and stop['fault'] in (3, 15) and raw_capture.exists():
            raw = json.loads(raw_capture.read_text())
            target = stop.get('fault_target') if stop['fault'] == 3 else stop['fault_pc']
            if (raw.get('fault'), raw.get('site'), raw.get('target'), raw.get('vi')) != (
                    stop['fault'], stop['fault_pc'], target, stop.get('vi')):
                raise ValueError('repair capture does not match validation stop')
            record = write_record(raw_capture, out / 'repair')
            print('repair record:', record, flush=True)
    stops = [line for line in r.stdout.splitlines() if line.startswith('{"stop"')]
    print(stops[-1][:400] if stops else r.stderr[-400:])
    if r.returncode or not stop or stop['fault']:
        return r, record, base_loads
    if a.require_audio:
        try:
            print('audio peak:', audio_peak(out / 'validation.wav'))
        except ValueError as error:
            sys.exit(str(error) + '; executable is not accepted')
    if a.rt64:
        launcher = RT64 / f'Play {name}{" native RSP" if a.rsp_gfx else ""}.cmd'
        play = [str(window_exe), '--rom', str(rom), *map(str, saves), '--stop-at', 'none']
        if a.rsp_gfx:
            play.append('--rsp-gfx')
        line = ' '.join('"' + arg.replace('%', '%%') + '"' for arg in play)
        launcher.write_text('@echo off\nsetlocal DisableDelayedExpansion\n' + line + '\nif errorlevel 1 pause\n')
        print('window build:', window_exe)
        print('play:', launcher)
    print('headless build:', exe)
    return r, record, base_loads


if __name__ == '__main__':
    try:
        main()
    finally:
        print_timings()
