"""ROM-word arithmetic supplies discovery roots, checked against pinned ares."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from test_tlb_execution import _ares_run

ROOT = Path(__file__).resolve().parents[1]


def main():
    import test_runtime as T
    A = T.A
    out = ROOT / 'target/rom-pointer-root-contract'
    out.mkdir(parents=True, exist_ok=True)
    # The oracle's cartridge is zero-filled; raw code/data at 0x80 is also zero.
    words = [*T.li(A.a0, 0x800000dc), *T.li(A.a1, 0x24), A.lui(A.a2, 0xb000),
             A.lw(A.v0, 0x80, A.a2), A.subu(A.a1, A.a1, A.v0), A.addu(A.a0, A.a0, A.a1),
             A.jalr(A.ra, A.a0), A.nop, A.lui(A.gp, 0x8000), A.sw(A.s1, 0x1000, A.gp), *A.DONE]
    data = bytearray(A.assemble(words))
    data[0xf8:0x118] = A.assemble([A.jr(A.ra), A.nop, A.addiu(A.s1, A.s1, 21), A.jr(A.ra), A.nop, A.nop, A.nop, A.nop])[:32]
    raw = out / 'root.bin'
    raw.write_bytes(data)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    native_c = out / 'native.c'
    subprocess.run([str(exe), 'lower-c', str(raw), hex(A.BASE), hex(A.BASE), hex(A.EXIT), str(native_c), '--address-taken'], check=True)
    harness = (ROOT / 'spikes/096-native-slice/harness.c').read_text()
    harness = harness.replace('static plaid_state s;', '''static plaid_state s;
static int rom_read(plaid_state *state, u32 p, u32 size, int write, u64 *value) {
  (void)state;
  if (p != 0x10000080u || size != 4 || write) return 1;
  *value = 0; return 0;
}''').replace('  plaid_load_images(&s);', '  s.io = rom_read;\n  plaid_load_images(&s);')
    source = out / 'harness.c'
    source.write_text(harness)
    binary = out / ('check.exe' if os.name == 'nt' else 'check')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                    '-DPLAID_LOWERED="native.c"', f'-DPLAID_EXIT=0x{A.EXIT:x}u',
                    '-I', str(ROOT / 'spikes/096-native-slice'), str(source), '-o', str(binary)], check=True)
    actual = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    reference = _ares_run(raw)
    assert actual.returncode == reference.returncode == 0, (actual.stdout, actual.stderr, reference.stdout, reference.stderr)
    state = json.loads(actual.stdout)
    assert state == json.loads(reference.stdout), (state, reference.stdout)
    assert state['regs'][A.s1] == 21 and state['ram'][0] == 21
    print('PASS ROM expression root: lowered dispatch, CPU/PC/FPU/RAM equal pinned ares; no closed-target certificate')


if __name__ == '__main__':
    main()
