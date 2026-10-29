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
  lower-map      16 parts, compiled in parallel with gcc
  rsp-from-rom   derive and lower candidate microcode from ROM image pointers
  snapshots      oracle-only; never loaded by the default build
  sp-boot        SP DMEM/IMEM as the ROM's IPL3 leaves them in pinned ares
  ram-boot       IPL3's first 0x400 RDRAM bytes, before the game overwrites them
  validate       run once (visibly with --rt64); unknown microcode faults
  --rt64         also link the RT64 window build (target/rt64-shim/Release)

Saves go to <out>/<name>.sra (SRAM) or <name>.fla (FlashRAM); EEPROM to
<name>.eep. The executables take the ROM again at run time with --rom.
"""
import argparse
from fragment_mapped import partition_mapped
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native_audio import audio_peak
from harvest_boot import harvest, harvest_refills, harvest_vectors
from ares_boot import ORACLE_SOURCES, capture_many

ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = ROOT / '.refs/n64sym/src/builtin_signatures.sig'
RT64 = ROOT / 'target/rt64-shim/Release'


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
    store = ROOT / 'target/native-cache' / hashlib.sha256(json.dumps(inputs).encode()).hexdigest()
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


def compile_source(source, flags, dependencies, compiler):
    obj = Path(f'{source}.o')
    stamp = Path(f'{obj}.sha256')
    digest = hashlib.sha256(source.read_bytes() + compiler + dependencies +
                            json.dumps(list(map(str, flags))).encode()).hexdigest()
    if not obj.exists() or not stamp.exists() or stamp.read_text() != digest:
        temporary = Path(f'{obj}.tmp')
        stamp.unlink(missing_ok=True)
        try:
            run(*flags, '-c', source, '-o', temporary)
            temporary.replace(obj)
            stamp.write_text(digest)
        finally:
            temporary.unlink(missing_ok=True)
    return obj


def rsp_dependencies():
    return b''.join(p.read_bytes() for p in sorted((ROOT / 'crates/plaid-lower/src').glob('rsp*.h')))


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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('rom', type=Path)
    ap.add_argument('--name')
    ap.add_argument('--loads', type=Path, help='plaid-loads-v0 for a ROM without a file table')
    ap.add_argument('--rt64', action='store_true')
    ap.add_argument('--strict', action='store_true', help='build only a CLOSED map; refuse residual run-time dispatch (ADR-0233)')
    ap.add_argument('--rsp-gfx', action='store_true', help='run lowered graphics microcode; requires --rt64')
    ap.add_argument('--rsp-dump', type=Path, help='capture IMEM for oracle comparison only; never a build input')
    ap.add_argument('--press', action='append', default=[], help='runtime button press, e.g. 0x1000@300:4')
    ap.add_argument('--require-audio', action='store_true', help='reject a validation run with empty or silent PCM')
    ap.add_argument('--seconds', type=float, default=60, help='length of the native validation run')
    a = ap.parse_args()
    if a.rsp_gfx and not a.rt64:
        ap.error('--rsp-gfx requires --rt64')
    rom = a.rom.resolve()
    # 32 characters keep both Zelda titles (and similar series) apart
    name = a.name or ''.join(c for c in rom.stem.lower() if c.isalnum())[:32]
    out = ROOT / 'target/native' / name
    texts = out / 'rsp-rom'
    for d in (out, texts):
        d.mkdir(parents=True, exist_ok=True)

    build_env = os.environ.copy()
    build_env.setdefault('CARGO_PROFILE_RELEASE_INCREMENTAL', 'true')
    run('cargo', 'build', '-q', '--release', '-p', 'plaid', env=build_env)
    info = json.loads(plaid('rom-info', rom, capture_output=True, text=True).stdout)
    entry = info['header']['boot_address']  # the header entry, less a CIC-6103/6106 offset
    loads = a.loads.resolve() if a.loads else out / 'loads.json'
    if not a.loads:
        plaid('infer-loads', rom, loads)
    # the main image ends where the entry stub's BSS clear begins; else IPL3's 1 MiB
    window = [rom, '0x1000', entry, hex(info.get('boot_image_size') or 0x100000)]
    m = out / 'map.json'
    overlay_support = None
    for attempt in range(64):
        harvest_vectors(rom, loads, out / 'vector-harvest.json')
        # A ROM with no file table and no reset stub has no loads to declare.
        with_loads = ['--loads', loads] if json.loads(loads.read_text())['loads'] else []
        (out / 'id.json').write_text(memo_plaid('identify', *window, SIGNATURES, *with_loads), newline='')
        discover = ['discover', *window, entry, m, out / 'id.json', *with_loads, '--address-taken', '--fr0']
        overlay_support = discover_map(discover, overlay_support, m)
        program = json.loads(m.read_text())
        if attempt < 63 and partition_mapped(loads, m):
            continue
        verdict = json.loads(memo_plaid('solve', rom, m, '--address-taken'))
        if verdict['status'] == 'closed' or a.loads or attempt == 63:
            break
        previous_loads = loads.read_bytes()
        plaid('infer-call-loads', rom, m, loads)
        if loads.read_bytes() != previous_loads:
            continue
        print('solve', verdict['status'], len(verdict['blockers']), 'blockers; analysis-time boot harvest', flush=True)
        if not harvest(rom, loads, m, info, out / f'boot-harvest-{attempt}.json') and not harvest_refills(
                rom, loads, m, info, out / f'refill-harvest-{attempt}.json'):
            break
    print('solve', verdict['status'], len(verdict['blockers']), 'blockers')
    residual = verdict['status'] != 'closed' and not a.strict
    if residual:
        verdict = json.loads(memo_plaid('solve', rom, m, '--residual-dispatch'))
        print('residual-dispatch solve', verdict['status'], len(verdict['blockers']), 'blockers,', len(verdict.get('residual_sites', [])), 'residual sites')
    if verdict['status'] != 'closed':
        sys.exit('not CLOSED under the address-taken scope' + ('' if a.strict else ', even with residual dispatch') + ': nothing is built')
    # Always rewritten: a stale manifest must never describe a later build.
    (out / 'native-manifest.json').write_text(json.dumps({'mode': 'residual-dispatch' if residual else 'closed', 'native_complete': not residual, 'residual_sites': [f"{s['pc']:08x}" for s in verdict.get('residual_sites', [])]}, indent=2) + '\n')

    # The native run starts SP memory as the ROM's own IPL3 leaves it (ADR-0195).
    try:
        sp_boot, ram_boot = write_boot_state(capture_many(rom, [entry])[-1], out, entry)
    except ValueError as error:
        sys.exit(str(error) + ': nothing is built')

    plaid('rsp-from-rom', rom, m, texts, '--loads', loads)
    rsp_manifest = json.loads((texts / 'rsp-files.json').read_text())
    c = out / f'{name}.c'
    # RAM address zero is executable when the guest owns its refill vector.
    exit_pc = '0xbfc00000' if program.get('tlb_exception_vectors') else '0x80000000'
    plaid('lower-map', rom, m, entry, exit_pc, c, '--parts', '16', '--runtime-unit', *(['--residual-dispatch'] if residual else []), stdout=subprocess.DEVNULL)
    cc = ['gcc', '-O1', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS']
    # CPU helpers and RSP arithmetic are embedded in their generated sources.
    # Only the shared RSP ABI headers remain external include dependencies.
    rsp_headers = rsp_dependencies()
    compiler = subprocess.check_output(['gcc', '--version'])

    def compile_cached(source, flags, dependencies=b''):
        return compile_source(source, flags, dependencies, compiler)

    parts = [c, *sorted(out.glob(f'{name}.part*.c'))]
    # Large CPU units can exceed RAM when every logical CPU launches GCC.
    with ThreadPoolExecutor(min(4, os.cpu_count() or 1)) as pool:
        part_objs = list(pool.map(lambda p: compile_cached(p, cc), parts))
    runtime_header=out/f'{name}.runtime.h'
    rt = [*cc, '-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', ROOT / 'crates/plaid-lower/src', f'-DPLAID_LOWERED="{runtime_header.name}"', f'-DPLAID_SP_BOOT="{sp_boot.name}"', f'-DPLAID_RAM_BOOT="{ram_boot.name}"', '-I', out]
    # Keep runtime objects in the build directory, alongside the generated C.
    runtime_source = out / 'runtime.c'
    runtime_source.write_text(f'#include "{(ROOT / "runtime/plaid_rt.c").as_posix()}"\n')
    runtime_deps = runtime_header.read_bytes() + sp_boot.read_bytes() + ram_boot.read_bytes() + (ROOT / 'runtime/plaid_rt.c').read_bytes() + b''.join(p.read_bytes() for p in sorted((ROOT / 'runtime').glob('*.h'))) + rsp_headers
    main_obj = compile_cached(runtime_source, rt, runtime_deps)
    window_exe = RT64 / f'{name}{"-rsp" if a.rsp_gfx else ""}-rt64.exe'
    if a.rt64:
        window_source = out / 'runtime-window.c'
        window_source.write_bytes(runtime_source.read_bytes())
        window_obj = compile_cached(window_source, [*rt, '-DPLAID_RT64'], runtime_deps)
    exe = out / f'{name}.exe'
    saves = ['--sram', out / f'{name}.sra', '--flash', out / f'{name}.fla', '--save', out / f'{name}.eep']

    texts_c = [texts / (t['name'] + '.c') for t in rsp_manifest['texts']] + [texts / 'rsp_registry.c']
    flags = ['gcc', '-O2', '-I', ROOT / 'crates/plaid-lower/src']
    with ThreadPoolExecutor(min(4, os.cpu_count() or 1)) as pool:
        objects = list(pool.map(lambda p: compile_cached(p, flags, rsp_headers), texts_c))
    run('gcc', main_obj, *part_objs, '-pthread', *objects, '-o', exe)
    if a.rt64:
        run('gcc', window_obj, *part_objs, RT64 / 'plaid_rt64.dll', '-pthread', *objects, '-o', window_exe)
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
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=a.seconds + 60, env=env)
    stops = [line for line in r.stdout.splitlines() if line.startswith('{"stop"')]
    print(stops[-1][:400] if stops else r.stderr[-400:])
    if r.returncode:
        sys.exit(r.stderr[-2000:] + '\nnative validation failed; executable is not accepted')
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


if __name__ == '__main__':
    main()
