"""Statically untaken branches preserve link, delay and complete CPU state."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import ares_oracle
import hashlib
import json
import os
import shutil
import subprocess
from test_cop0 import A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/branch-path-contract'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    items = [A.lui(A.gp, 0x8000), A.ori(A.gp, A.gp, 0x1000), A.addiu(A.v0, 0, 37)]
    # Link values are saved before later branches overwrite RA. A likely slot
    # contains reserved data; ordinary slots write memory using the new RA.
    for n, (op, rs, rt, likely) in enumerate([
        (1, 0, 16, False), (1, 0, 18, True),
        (1, 0, 0, False), (1, 0, 2, True),
        (7, 0, 0, False), (23, 0, 0, True),
        (5, A.t0, A.t0, False), (21, A.t0, A.t0, True),
    ]):
        items += [A.B(op, rs, rt, 'data'),
                  0x7677696e if likely else A.sw(A.ra, n * 8, A.gp),
                  A.sw(A.ra, n * 8 + 4, A.gp)]
    items += [*A.DONE, 'data', 0x7677696e]
    raw = OUT / 'program.bin'
    raw.write_bytes(A.assemble(items))
    oracle = ares_oracle.default()
    built = json.loads((oracle.parent / 'build.json').read_text())
    assert built['revision'] == A.builder().REV
    assert built['driver'] == hashlib.sha256((ROOT / 'spikes/096-native-slice/driver.cpp').read_bytes()).hexdigest()
    command = [str(oracle), str(raw), hex(A.EXIT)]
    expected = json.loads(subprocess.check_output(command, text=True, timeout=120))
    source = OUT / 'native.c'
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(source)], check=True)
    native = OUT / ('check.exe' if os.name == 'nt' else 'check')
    compile_cmd = [cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label', '-DPLAID_SAFEPOINTS',
                   '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={hex(A.EXIT)}u', '-I', str(OUT),
                   str(ROOT / 'spikes/096-native-slice/harness.c'), '-lm', '-o', str(native)]
    subprocess.run(compile_cmd, check=True)
    actual = json.loads(subprocess.check_output([str(native)], text=True, timeout=30))
    assert actual == expected, {k: (actual[k], expected[k]) for k in actual if actual[k] != expected[k]}
    # A missing link write must be detected by both the delay-slot store and
    # the following store, not just a generated-C string assertion.
    generated = source.read_text()
    link = f's->r[31] = 0xffffffff{A.BASE + 20:08x}ull;'
    assert link in generated
    source.write_text(generated.replace(link, '', 1))
    try:
        subprocess.run(compile_cmd, check=True)
        mutated = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        assert mutated.returncode != 0 or json.loads(mutated.stdout) != expected
    finally:
        source.write_text(generated)
    print('PASS untaken branch paths: pinned ares GPR/FPR/PC/HI/LO/FCSR/RAM, delay stores and annulled invalid slots; missing-link mutation killed')


if __name__ == '__main__':
    main()
