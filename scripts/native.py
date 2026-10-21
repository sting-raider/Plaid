"""ROM in, native executable out, with no per-game inputs (ADR-0183).

    python scripts/native.py <rom> [--name N] [--loads loads.json] [--rt64] [--seconds S]

Steps, each a plain `plaid` command whose output stays in target/native/<name>:
  infer-loads    fixed loads from the ROM's file table (or --loads, for ROMs
                 without one), plus the reset stub
  identify       libultra functions the host runtime replaces
  discover       with the ROM's relocatable overlays when it has a file table
  solve          the address-taken scope must be CLOSED, else nothing is built
                 when OPEN, refine copy-call sources, then harvest with pinned
                 ares and retry; each candidate still needs native byte binding
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
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from native_audio import audio_peak
from harvest_boot import harvest
from ares_boot import capture_many

ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = ROOT / '.refs/n64sym/src/builtin_signatures.sig'
RT64 = ROOT / 'target/rt64-shim/Release'


def run(*args, **kw):
    print('+', ' '.join(str(a) for a in args), flush=True)
    return subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kw)


def plaid(*args, **kw):
    return run(ROOT / 'target/release/plaid', *args, **kw)


def discover_map(arguments, overlay_support):
    """File-table presence is immutable across refinements of the same ROM."""
    if overlay_support is False:
        plaid(*arguments)
        return False
    tried = subprocess.run([str(ROOT / 'target/release/plaid'), *map(str, arguments), '--overlays'],
                           cwd=ROOT, capture_output=True, text=True)
    if tried.returncode != 0:
        if 'file table' not in tried.stderr:
            sys.exit(tried.stderr)
        plaid(*arguments)
        return False
    print(tried.stdout.strip().splitlines()[-1])
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
    sp_boot, ram_boot = out / 'sp_boot.h', out / 'ram_boot.h'
    sp_boot.write_text('static const u8 plaid_sp_boot[0x2000] = {' + ','.join(map(str, capture['sp'])) + '};\n')
    ram_boot.write_text('static const u8 plaid_ram_boot[] = {' + ','.join(map(str, capture['ram_prefix'])) + '};\n')
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
    ap.add_argument('--residual-dispatch', action='store_true', help='VALIDATION ONLY (ADR-0218): accept unproven indirect sites as fail-closed dispatch over every lowered entry; the build is not natively complete')
    ap.add_argument('--rsp-gfx', action='store_true', help='run lowered graphics microcode; requires --rt64')
    ap.add_argument('--rsp-dump', type=Path, help='capture IMEM for oracle comparison only; never a build input')
    ap.add_argument('--press', action='append', default=[], help='runtime button press, e.g. 0x1000@300:4')
    ap.add_argument('--require-audio', action='store_true', help='reject a validation run with empty or silent PCM')
    ap.add_argument('--seconds', type=float, default=60, help='length of the native validation run')
    a = ap.parse_args()
    if a.rsp_gfx and not a.rt64:
        ap.error('--rsp-gfx requires --rt64')
    rom = a.rom.resolve()
    name = a.name or ''.join(c for c in rom.stem.lower() if c.isalnum())[:16]
    if a.residual_dispatch:
        name += '-residual'  # never replaces the complete build
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
    for attempt in range(16):
        # A ROM with no file table and no reset stub has no loads to declare.
        with_loads = ['--loads', loads] if json.loads(loads.read_text())['loads'] else []
        with open(out / 'id.json', 'w') as f:
            plaid('identify', *window, SIGNATURES, *with_loads, stdout=f)
        discover = ['discover', *window, entry, m, out / 'id.json', *with_loads, '--address-taken', '--fr0']
        overlay_support = discover_map(discover, overlay_support)
        verdict = json.loads(plaid('solve', rom, m, '--address-taken', capture_output=True, text=True).stdout)
        if verdict['status'] == 'closed' or a.loads or attempt == 15:
            break
        previous_loads = loads.read_bytes()
        plaid('infer-call-loads', rom, m, loads)
        if loads.read_bytes() != previous_loads:
            continue
        print('solve', verdict['status'], len(verdict['blockers']), 'blockers; analysis-time boot harvest', flush=True)
        if not harvest(rom, loads, m, info, out / f'boot-harvest-{attempt}.json'):
            break
    print('solve', verdict['status'], len(verdict['blockers']), 'blockers')
    if verdict['status'] != 'closed' and a.residual_dispatch:
        verdict = json.loads(plaid('solve', rom, m, '--residual-dispatch', capture_output=True, text=True).stdout)
        print('residual-dispatch solve', verdict['status'], len(verdict['blockers']), 'blockers,', len(verdict.get('residual_sites', [])), 'residual sites')
    if verdict['status'] != 'closed':
        sys.exit('not CLOSED under the address-taken scope: nothing is built')
    if a.residual_dispatch:
        (out / 'native-manifest.json').write_text(json.dumps({'mode': 'residual-dispatch', 'native_complete': False, 'residual_sites': [f"{s['pc']:08x}" for s in verdict.get('residual_sites', [])]}, indent=2) + '\n')

    # The native run starts SP memory as the ROM's own IPL3 leaves it (ADR-0195).
    try:
        sp_boot, ram_boot = write_boot_state(capture_many(rom, [entry])[-1], out, entry)
    except ValueError as error:
        sys.exit(str(error) + ': nothing is built')

    plaid('rsp-from-rom', rom, m, texts, '--loads', loads)
    rsp_manifest = json.loads((texts / 'rsp-files.json').read_text())
    c = out / f'{name}.c'
    plaid('lower-map', rom, m, entry, '0x80000000', c, '--parts', '16', *(['--residual-dispatch'] if a.residual_dispatch else []), stdout=subprocess.DEVNULL)
    cc = ['gcc', '-O1', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS']
    headers = b''.join(p.read_bytes() for p in sorted((ROOT / 'crates/plaid-lower/src').glob('*.h')))
    compiler = subprocess.check_output(['gcc', '--version'])

    def compile_cached(source, flags, dependencies=b''):
        return compile_source(source, flags, headers + dependencies, compiler)

    parts = sorted(out.glob(f'{name}.part*.c'))
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        part_objs = list(pool.map(lambda p: compile_cached(p, cc), parts))
    rt = [*cc, '-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', ROOT / 'crates/plaid-lower/src', f'-DPLAID_LOWERED="{c.name}"', f'-DPLAID_SP_BOOT="{sp_boot.name}"', f'-DPLAID_RAM_BOOT="{ram_boot.name}"', '-I', out]
    # Keep runtime objects in the build directory, alongside the generated C.
    runtime_source = out / 'runtime.c'
    runtime_source.write_text(f'#include "{(ROOT / "runtime/plaid_rt.c").as_posix()}"\n')
    runtime_deps = c.read_bytes() + sp_boot.read_bytes() + ram_boot.read_bytes() + (ROOT / 'runtime/plaid_rt.c').read_bytes() + b''.join(p.read_bytes() for p in sorted((ROOT / 'runtime').glob('*.h')))
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
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        objects = list(pool.map(lambda p: compile_cached(p, flags), texts_c))
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
    r = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=a.seconds + 60)
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
