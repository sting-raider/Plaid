#!/usr/bin/env python3
"""Run Plaid's local landing gate (AGENTS.md, "Local validation") in one command.

  python scripts/gate.py --doctor          check the toolchain only
  python scripts/gate.py --quick           fmt + clippy + Rust tests
  python scripts/gate.py                   the full gate without game ROMs
  python scripts/gate.py --roms DIR        ... plus the 30 s game controls

The runtime suite runs when the branch touches runtime/ or crates/plaid-lower/
relative to origin/main (--runtime forces it, --no-runtime skips it).
Exit status is nonzero if any step fails.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MP2_PRESSES = ['0x1000@600:4', '0x1000@1250:4'] + [f'0x8000@{f}:4' for f in (1360, 1440, 1520, 1600, 1680, 1760, 2000, 2100, 2200)]
# (label, ROM file glob, extra native.py args). Controls must stop with fault 0 and ~1798 VIs.
CONTROLS = [
    ('Paper Mario', 'Paper Mario*.z64', []),
    ('Banjo-Kazooie', 'Banjo-Kazooie*.z64', []),
    ("Majora's Mask", '*Majora*.z64', []),
    ('Star Fox 64', 'Star Fox 64*.z64', []),
    ('Ocarina of Time', '*Ocarina of Time*.z64', []),
    ('Rogue Squadron', '*Rogue Squadron*.z64', []),
    ('Mario Party 2 (check: reaches destination/rules selection)', 'Mario Party 2*.z64',
     [arg for p in MP2_PRESSES for arg in ('--press', p)]),
]
MIN_VI = 1700  # a 30 s run is ~1798; well below means the game stalled


def tool(name):
    found = shutil.which(name)
    if not found and name in ('cargo', 'rustc'):
        home = Path.home() / '.cargo' / 'bin' / (name + ('.exe' if os.name == 'nt' else ''))
        found = str(home) if home.exists() else None
    return found


def stop_fields(output):
    """vi/fault/fault_pc from the last {"stop" line (native.py truncates it, so no json.loads)."""
    lines = [l for l in output.splitlines() if l.startswith('{"stop"')]
    if not lines:
        return None
    line = lines[-1]
    get = lambda key, pat: (m.group(1) if (m := re.search(f'"{key}":{pat}', line)) else None)
    return {'stop': get('stop', '"([^"]*)"'), 'vi': int(get('vi', r'(\d+)') or -1),
            'fault': int(get('fault', r'(\d+)') or -1), 'fault_pc': get('fault_pc', '"([0-9a-f]+)"')}


assert stop_fields('x\n{"stop":"seconds","vi":1798,"gfx_tasks":9,"fault":0,"fault_pc":"00000000","ra"') == \
    {'stop': 'seconds', 'vi': 1798, 'fault': 0, 'fault_pc': '00000000'}


def doctor():
    ok = True
    for name, args in (('git', ['--version']), ('cargo', ['--version']), ('rustc', ['--version']),
                       ('gcc', ['--version']), ('g++', ['--version'])):
        path = tool(name)
        version = subprocess.run([path, *args], capture_output=True, text=True).stdout.splitlines()[0] if path else 'MISSING'
        ok &= bool(path)
        print(f'  {name:6} {version}')
    print(f'  python {sys.version.split()[0]}' + ('' if sys.version_info >= (3, 11) else '  (need 3.11+)'))
    ok &= sys.version_info >= (3, 11)
    refs = ROOT / '.refs'
    print(f'  .refs  {"present" if refs.exists() else "MISSING: run python scripts/fetch_refs.py"}')
    return ok and refs.exists()


def touches_runtime():
    r = subprocess.run(['git', 'diff', '--name-only', 'origin/main...HEAD'], cwd=ROOT, capture_output=True, text=True)
    dirty = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    paths = r.stdout.splitlines() + [l[3:] for l in dirty.splitlines()]
    return r.returncode != 0 or any(p.startswith(('runtime/', 'crates/plaid-lower/')) for p in paths)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--doctor', action='store_true', help='check tools and exit')
    ap.add_argument('--quick', action='store_true', help='fmt, clippy and Rust tests only')
    ap.add_argument('--roms', type=Path, default=os.environ.get('PLAID_ROMS'), help='folder with your own ROMs (or PLAID_ROMS)')
    ap.add_argument('--runtime', action=argparse.BooleanOptionalAction, default=None, help='force/skip runtime/test_runtime.py')
    ap.add_argument('--seconds', type=float, default=30)
    a = ap.parse_args()

    print('toolchain:')
    if not doctor():
        sys.exit('toolchain incomplete; see CONTRIBUTIONS.md section 1')
    shim = ROOT / 'target/rt64-shim/Release/plaid_rt64.dll'
    print(f'  rt64   {"present" if shim.exists() else "missing (needed only for --roms; see CONTRIBUTIONS.md section 1)"}')
    if a.doctor:
        return
    if a.roms and not shim.exists():
        sys.exit(f'--roms needs {shim}; build it first (CONTRIBUTIONS.md, "Running a game")')

    cargo, py = tool('cargo'), sys.executable
    steps = [('fmt', [cargo, 'fmt', '--all', '--', '--check']),
             ('clippy', [cargo, 'clippy', '--locked', '--workspace', '--all-targets', '--', '-D', 'warnings']),
             ('cargo test', [cargo, 'test', '--locked', '--workspace'])]
    if not a.quick:
        steps += [('test_cli', [py, 'scripts/test_cli.py']), ('progress', [py, 'tools/progress.py', '--check'])]
        if a.runtime or (a.runtime is None and touches_runtime()):
            steps.append(('test_runtime', [py, 'runtime/test_runtime.py']))

    results = []
    for label, cmd in steps:
        print(f'\n== {label}: {" ".join(map(str, cmd))}', flush=True)
        t = time.time()
        rc = subprocess.run(cmd, cwd=ROOT).returncode
        results.append((label, rc == 0, f'{time.time() - t:.0f} s'))

    if a.roms and not a.quick:
        env = dict(os.environ, SDL_AUDIODRIVER='dummy')
        for label, pattern, extra in CONTROLS:
            roms = sorted(Path(a.roms).glob(pattern))
            if not roms:
                results.append((label, None, f'not run: no {pattern} in {a.roms}'))
                continue
            cmd = [py, 'scripts/native.py', str(roms[0]), '--rt64', '--seconds', str(a.seconds), *extra]
            print(f'\n== {label}: {roms[0].name}', flush=True)
            r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
            print(r.stdout[-1500:], r.stderr[-1500:], sep='\n')
            s = stop_fields(r.stdout)
            good = r.returncode == 0 and s is not None and s['fault'] == 0 and s['vi'] >= MIN_VI * a.seconds / 30
            results.append((label, good, f"vi {s['vi']} fault {s['fault']} pc {s['fault_pc']}" if s else 'no stop line'))

    print('\n== summary')
    for label, good, note in results:
        print(f"  {'PASS' if good else 'SKIP' if good is None else 'FAIL'}  {label:60} {note}")
    if not a.roms and not a.quick:
        print('  (game controls not run: pass --roms DIR to include them)')
    sys.exit(0 if all(g is not False for _, g, _ in results) else 1)


if __name__ == '__main__':
    main()
