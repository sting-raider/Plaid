"""Fixed CPU text can be revoked by CPU/device writes, never executed stale."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'target/text-write-contract'


def main():
    spec = importlib.util.spec_from_file_location('text_asm', ROOT / 'spikes/096-native-slice/run.py')
    a = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a)
    OUT.mkdir(parents=True, exist_ok=True)
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    items = [a.jal('leaf'), a.nop, *a.DONE, 'leaf', a.lui(a.t0, 0xa400),
             a.lw(a.v0, 0, a.t0), a.addiu(a.v0, a.v0, 42), a.jr(a.ra), a.nop]
    labels = a.label_pcs(items)
    leaf = labels['leaf']
    raw = a.assemble(items)
    source, c = OUT / 'cpu.bin', OUT / 'cpu.c'
    source.write_bytes(raw)
    subprocess.run([str(exe), 'lower-c', str(source), hex(a.BASE), hex(a.BASE), hex(a.EXIT), str(c)],
                   check=True, capture_output=True)
    harness = OUT / 'check.c'
    harness.write_text('#define main slice_main\n#include "' +
                       (ROOT/'spikes/096-native-slice/harness.c').as_posix() +
                       '"\n#undef main\n#include <assert.h>\n#include "rsp_state.h"\n#include "rsp_prelude.h"\n' + r'''
static plaid_rsp rsp;
static int active;
static int device_write(u32 p, u32 n) { return plaid_runtime_write(&s, p, n, 0); }
static int dma(u32 p) {
  rsp.pending_mem = 0x1000; rsp.pending_dram = p;
  rsp.fault = rsp.halted = 0;
  return plaid_rsp_dma(&rsp, 7, 1, 0xc0);
}
static int io(plaid_state *state, u32 p, u32 size, int write, u64 *value) {
  (void)state; (void)p; (void)size; (void)write; *value = 0;
  if (active) { int r = dma(LEAF); assert(r == 1 && s.fault == 2); return r; }
  return 0;
}
int main(void) {
  u8 original[8]; u64 sentinel = 0xffffffffbfc00000ull;
  s.io = io;
  assert(slice_main() == 0 && !s.native_frames);
  rsp.rdram = s.ram; rsp.rdram_size = PLAID_RAM_SIZE; rsp.rdram_write = device_write;
  memcpy(original, s.ram + LEAF, 8);
  memset(rsp.imem, 0x99, 8);
  /* Ordinary data and inactive text are valid DMA sinks. */
  assert(dma(0x2000) == 0 && s.ram[0x2000] == 0x99 && rsp.dma_dram == 0x2008);
  assert(dma(LEAF) == 0 && s.prot[LEAF >> 2] == 254 && s.text_dirty);
  assert(F_LEAF(&s, sentinel) == 1 && s.fault == 8 && !s.native_frames);
  assert(s.fault_pc == (0x80000000u | LEAF));
  /* CPU stores use the same revocation and re-entry verification. */
  s.fault = 0;
  assert(plaid_store(&s, 0xffffffffa0000000ull | LEAF, 4, 0, 0x80002000u) == 0);
  assert(F_LEAF(&s, sentinel) == 1 && s.fault == 8 && !s.native_frames);
  memcpy(rsp.imem, original, 8);
  assert(dma(LEAF) == 0);
  s.fault = 0; s.r[31] = sentinel;
  assert(F_LEAF(&s, sentinel) == 0 && s.r[2] == 42 && !s.native_frames);
  assert(s.prot[LEAF >> 2] == 1);
  /* An actual native frame invokes the DMA while its own body is pinned. */
  active = 1;
  assert(F_LEAF(&s, sentinel) == 1 && s.fault == 1 && rsp.fault == 1);
  assert(rsp.fault_pc == 0xc0 && !s.native_frames && !memcmp(original, s.ram + LEAF, 8));
  active = 0; s.fault = 0;
  /* Suspended frames can leave in non-LIFO order without losing other pins. */
  { static const plaid_text_range ranges[] = {{LEAF, LEAF + 8}};
    plaid_native_frame first = {0, 0, ranges, 1, 0, 0, -1}, second = {0, 0, ranges, 1, 0, 0, -1};
    plaid_text_pin(&s, &first); plaid_text_pin(&s, &second); plaid_text_unpin(&s, &first);
    assert(dma(LEAF) == 1 && s.fault == 2);
    s.fault = 0;
    assert(plaid_store(&s, 0xffffffffa0000000ull | LEAF, 4, 0, 0x80002000u) == 1 && s.fault == 2);
    plaid_text_unpin(&s, &second); assert(!s.native_frames);
  }
  /* Proof-bearing data is immutable even with no native frame. */
  s.prot[0x2100 >> 2] = 253; s.fault = 0;
  assert(dma(0x2100) == 1 && s.fault == 2 && s.ram[0x2100] == 0);
  return 0;
}
'''.replace('F_LEAF', f'F_{leaf:08x}').replace('LEAF', f'0x{leaf & 0x1fffffff:x}u'))
    native = OUT / ('check.exe' if os.name == 'nt' else 'check')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Werror', '-Wno-unused-function', '-Wno-unused-label',
                    '-DPLAID_LOWERED="cpu.c"', f'-DPLAID_EXIT={hex(a.EXIT)}u', '-I', str(OUT),
                    '-I', str(ROOT/'crates/plaid-lower/src'), str(harness), '-lm', '-o', str(native)], check=True)
    run = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, (run.returncode, run.stdout, run.stderr)
    oracle = ROOT / 'target/native-slice/oracle/oracle'
    built = json.loads((oracle.parent/'build.json').read_text())
    assert built['revision'] == a.builder().REV
    if os.name == 'nt':
        def linux(path):
            return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(path)], text=True).strip()
        reference = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(source), hex(a.EXIT)]
    else:
        reference = [str(oracle), str(source), hex(a.EXIT)]
    ref = subprocess.run(reference, capture_output=True, text=True, timeout=120)
    assert ref.returncode == 0 and json.loads(run.stdout) == json.loads(ref.stdout), (run.stdout, ref.stdout, ref.stderr)
    print('PASS text writes: CPU/RSP inactive revocation, data DMA, stale-entry refusal, restored entry, active/suspended frame faults, proof-data protection; CPU state matches pinned ares')


if __name__ == '__main__':
    main()
