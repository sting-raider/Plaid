"""Data-only replay sources initialize before use and recheck after writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/replayed-data-contract'


def main():
    cargo = shutil.which('cargo') or str(Path.home() / '.cargo/bin/cargo.exe')
    subprocess.run([cargo, 'run', '--quiet', '--locked', '-p', 'plaid-lower', '--example',
                    'replayed_data', '--', str(OUT)], cwd=ROOT, check=True)
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    if not cc:
        raise RuntimeError('replayed data contract requires a C compiler')
    def run(name):
        exe = OUT / (name + ('.exe' if os.name == 'nt' else ''))
        subprocess.run([cc, '-O2', '-std=c11', f'-DPLAID_LOWERED="{name}.c"',
                        '-DPLAID_EXIT=0x80000f00u', '-I', str(OUT),
                        str(ROOT / 'spikes/096-native-slice/harness.c'), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    actual = run('init')
    expected = _ares_run(OUT / 'init.bin')
    assert actual.returncode == expected.returncode == 0, (actual.stdout, actual.stderr, expected.stderr)
    assert json.loads(actual.stdout) == json.loads(expected.stdout), (actual.stdout, expected.stdout)
    assert json.loads(actual.stdout)['ram'][:5] == [0x80000080, 0x800000a0, 0, 0, 42]
    for name in ('tamper', 'rewrite'):
        actual = run(name)
        assert actual.returncode == 6 and json.loads(actual.stdout) == {'fault': 8, 'fault_pc': 0x80000040}, (name, actual.stdout)
    text = (OUT / 'tamper.c').read_text()
    guard = '  if (!s->load_ok[0] && plaid_verify_load(s, 0, 0x80000040u)) return 1;\n'
    assert guard in text
    (OUT / 'mutation.c').write_text(text.replace(guard, '', 1))
    mutated = run('mutation')
    assert mutated.returncode == 6 and json.loads(mutated.stdout)['fault'] == 3, mutated.stdout
    print('PASS replayed data: initialization and full state/RAM match ares; first-use and post-write tamper fault 8; missing guard mutation faults 3')


if __name__ == '__main__':
    main()
