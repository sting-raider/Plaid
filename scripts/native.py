"""ROM in, native executable out, with no per-game inputs (ADR-0183).

    python scripts/native.py <rom> [--name N] [--loads loads.json] [--rt64] [--seconds S]

Steps, each a plain `plaid` command whose output stays in target/native/<name>:
  infer-loads    fixed loads from the ROM's file table (or --loads, for ROMs
                 without one), plus the reset stub
  identify       libultra functions the host runtime replaces
  discover       with the ROM's relocatable overlays when it has a file table
  solve          the address-taken scope must be CLOSED, else nothing is built
  lower-map      16 parts, compiled in parallel with gcc
  RSP loop       run headless, lower every new microcode snapshot, relink,
                 until a run finds none (ADR-0169)
  --rt64         also link the RT64 window build (target/rt64-shim/Release)

Saves go to <out>/<name>.sra (SRAM) or <name>.fla (FlashRAM); EEPROM to
<name>.eep. The executables take the ROM again at run time with --rom.
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIGNATURES = ROOT / '.refs/n64sym/src/builtin_signatures.sig'
RT64 = ROOT / 'target/rt64-shim/Release'


def run(*args, **kw):
    print('+', ' '.join(str(a) for a in args), flush=True)
    return subprocess.run([str(a) for a in args], check=True, cwd=ROOT, **kw)


def plaid(*args, **kw):
    return run(ROOT / 'target/release/plaid', *args, **kw)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('rom', type=Path)
    ap.add_argument('--name')
    ap.add_argument('--loads', type=Path, help='plaid-loads-v0 for a ROM without a file table')
    ap.add_argument('--rt64', action='store_true')
    ap.add_argument('--seconds', type=float, default=60, help='length of each RSP-loop run')
    a = ap.parse_args()
    rom = a.rom.resolve()
    name = a.name or ''.join(c for c in rom.stem.lower() if c.isalnum())[:16]
    out = ROOT / 'target/native' / name
    snaps, texts = out / 'rsp-snaps', out / 'rsp-texts'
    for d in (out, snaps, texts):
        d.mkdir(parents=True, exist_ok=True)

    run('cargo', 'build', '-q', '--release', '-p', 'plaid')
    info = json.loads(plaid('rom-info', rom, capture_output=True, text=True).stdout)
    entry = info['header']['boot_address']  # the header entry, less a CIC-6103/6106 offset
    loads = a.loads.resolve() if a.loads else out / 'loads.json'
    if not a.loads:
        plaid('infer-loads', rom, loads)
    # a ROM with no file table and no reset stub has no loads to declare
    with_loads = ['--loads', loads] if json.loads(loads.read_text())['loads'] else []
    # the main image ends where the entry stub's BSS clear begins; else IPL3's 1 MiB
    window = [rom, '0x1000', entry, hex(info.get('boot_image_size') or 0x100000)]
    with open(out / 'id.json', 'w') as f:
        plaid('identify', *window, SIGNATURES, *with_loads, stdout=f)
    m = out / 'map.json'
    discover = ['discover', *window, entry, m, out / 'id.json', *with_loads, '--address-taken', '--fr0']
    tried = subprocess.run([str(ROOT / 'target/release/plaid'), *map(str, discover), '--overlays'],
                           cwd=ROOT, capture_output=True, text=True)
    if tried.returncode != 0:
        if 'file table' not in tried.stderr:
            sys.exit(tried.stderr)
        plaid(*discover)  # no file table, so no overlay catalog
    else:
        print(tried.stdout.strip().splitlines()[-1])
    verdict = json.loads(plaid('solve', rom, m, '--address-taken', capture_output=True, text=True).stdout)
    print('solve', verdict['status'], len(verdict['blockers']), 'blockers')
    if verdict['status'] != 'closed':
        sys.exit('not CLOSED under the address-taken scope: nothing is built')

    for old in out.glob('*.o'):
        old.unlink()
    c = out / f'{name}.c'
    plaid('lower-map', rom, m, entry, '0x80000000', c, '--parts', '16', stdout=subprocess.DEVNULL)
    cc = ['gcc', '-O1', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS']
    parts = sorted(out.glob(f'{name}.part*.c'))
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        list(pool.map(lambda p: run(*cc, '-c', p, '-o', f'{p}.o'), parts))
    rt = [*cc, '-DPLAID_RSP', '-I', ROOT / 'crates/plaid-lower/src', f'-DPLAID_LOWERED="{c.name}"', '-I', out]
    run(*rt, '-c', ROOT / 'runtime/plaid_rt.c', '-o', out / 'main.o')
    objs = [out / 'main.o', *(Path(f'{p}.o') for p in parts)]
    exe = out / f'{name}.exe'
    saves = ['--sram', out / f'{name}.sra', '--flash', out / f'{name}.fla', '--save', out / f'{name}.eep']

    def rsp_link():
        texts_c = subprocess.run([sys.executable, ROOT / 'runtime/rsp_texts.py', ROOT / 'target/release/plaid', snaps, texts],
                                 cwd=ROOT, check=True, capture_output=True, text=True).stdout.split()
        return ['-O1', '-I', ROOT / 'crates/plaid-lower/src', *texts_c]

    for _ in range(8):
        before = len(list(snaps.glob('imem-*.bin')))
        run('gcc', *objs, '-pthread', *rsp_link(), '-o', exe)
        r = subprocess.run([str(exe), '--rom', str(rom), *map(str, saves), '--rsp-dump', str(snaps),
                            '--stop-at', 'none', '--seconds', str(a.seconds)],
                           cwd=ROOT, capture_output=True, text=True, errors='replace')
        stops = [line for line in r.stdout.splitlines() if line.startswith('{"stop"')]
        print(stops[-1][:400] if stops else r.stderr[-400:])
        if len(list(snaps.glob('imem-*.bin'))) == before:
            break
    if a.rt64:
        run(*rt, '-DPLAID_RT64', '-c', ROOT / 'runtime/plaid_rt.c', '-o', out / 'main-rt64.o')
        window_exe = RT64 / f'{name}-rt64.exe'  # beside the RT64 DLLs it loads
        run('gcc', out / 'main-rt64.o', *objs[1:], RT64 / 'plaid_rt64.dll', '-pthread', *rsp_link(), '-o', window_exe)
        print('window build:', window_exe)
    print('headless build:', exe)


if __name__ == '__main__':
    main()
