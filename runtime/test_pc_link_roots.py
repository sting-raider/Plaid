"""ADR-0280: PC-link/shared-tail discovery candidates versus pinned ares."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_cop0 import A

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/pc-link-contract'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p = [A.B(1, A.zero, 16, 'exit'), A.nop, A.addiu(A.t3, A.ra, 0x100 - 8),
         A.jalr(A.ra, A.t3), A.nop, A.B(1, A.zero, 18, 'exit'),
         A.addiu(A.s1, A.zero, 99), A.addiu(A.t3, A.ra, 0x108 - 28),
         A.jalr(A.ra, A.t3), A.nop, A.lui(A.gp, 0x8000),
         A.sw(A.s1, 0x1000, A.gp), *A.DONE]
    data = bytearray(A.assemble(p))
    data[0xf8:0x114] = A.assemble([A.jr(A.ra), A.nop, A.addiu(A.s1, A.s1, 3),
        A.nop, A.addiu(A.s1, A.s1, 7), A.jr(A.ra), A.nop])[:28]
    # One ordinary address-taken root; the shared-tail entry has no ROM pointer.
    data[0x200:0x204] = (A.BASE + 0x100).to_bytes(4, 'big')
    raw = OUT / 'program.bin'
    raw.write_bytes(data)
    exe = Path(os.environ.get('PLAID_EXE', ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')))
    native_c = OUT / 'native.c'
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
        str(native_c), '--address-taken'], check=True, capture_output=True)
    source = OUT / 'harness.c'
    source.write_text((ROOT / 'spikes/096-native-slice/harness.c').read_text())
    binary = OUT / ('check.exe' if os.name == 'nt' else 'check')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    def run():
        subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
            '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT={A.EXIT}u',
            '-I', str(ROOT / 'spikes/096-native-slice'), str(source), '-o', str(binary)], check=True)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    actual = run()
    driver = OUT / 'driver.cpp'
    driver.write_text((ROOT / 'spikes/096-native-slice/driver.cpp').read_text())
    oracle = A.builder().build(driver, OUT / 'oracle')
    expected = json.loads(subprocess.check_output([str(oracle), str(raw), hex(A.EXIT)], text=True, timeout=120))
    assert actual.returncode == 0 and json.loads(actual.stdout) == expected, (actual.returncode, actual.stdout)
    assert expected['regs'][A.s1] == expected['ram'][0] == 17
    generated = native_c.read_text()
    needle = 'case 0xffffffff80000108ull:'
    assert needle in generated
    try:
        native_c.write_text(generated.replace(needle, 'case 0xffffffff8000010cull:'))
        mutant = run()
        assert mutant.returncode == 6 and json.loads(mutant.stdout)['fault'] == 3, mutant
    finally:
        native_c.write_text(generated)
    (OUT / 'receipt.json').write_text(json.dumps(dict(ares=A.builder().REV,
        state=list(expected), mutation='remove discovered shared-tail dispatch entry: fault3',
        scope='candidate discovery from untaken links; not a closed-target certificate'), indent=2))
    print('PASS PC-relative roots: ordinary/likely links, shared-tail native calls, full CPU/FPR/PC/HI/LO/FCSR/RAM equal ares; missing-entry mutation killed')


if __name__ == '__main__':
    main()
