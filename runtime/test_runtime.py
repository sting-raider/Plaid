"""Deterministic test of the Plaid host runtime (ADR-0159).

A synthetic MIPS program, assembled with spike096's assembler, declares
libultra functions as runtime functions, is lowered with `plaid lower-c` and
linked with runtime/plaid_rt.c. Its threads append to a log in guest RAM; the
log order checks libultra scheduling: a higher-priority thread preempts on
start and on a message send, a blocked receive yields, lowering a priority
yields, and a VI retrace preempts a spinning thread at a loop safepoint.

A second program checks the renderer bridge (ADR-0163) without a GPU: a stub
plaid_gfx_* records the VI registers the runtime derives from an OSViMode and
framebuffer, and the graphics task addresses and RAM it hands over.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spike096', ROOT / 'spikes/096-native-slice/run.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)
OUT = ROOT / 'target/runtime-test'

Q, BUF, Q2, BUF2, SLOT = 0x80002000, 0x80002020, 0x80002040, 0x80002060, 0x80002080
T1, T2, T4 = 0x80002100, 0x80002300, 0x80002500
LOG, INDEX = 0x80003000, 0x80003100


def li(r, v):
    return [A.lui(r, v >> 16), A.ori(r, r, v & 0xFFFF)]


def call(name, *args):
    """Set a0.. (ints or labels) and the stack arguments, then jal."""
    out = []
    for n, v in enumerate(args):
        reg = A.a0 + n if n < 4 else A.t0
        out += [A.lui(reg, 0x8000), A.LO(reg, reg, v)] if isinstance(v, str) else li(reg, v)
        if n >= 4:
            out.append(A.sw(A.t0, 4 * n, A.sp))
    return out + [A.jal(name), A.nop]


def log(value):
    return [*li(A.t5, value), *li(A.t8, INDEX), A.lw(A.t9, 0, A.t8), A.sll(A.t7, A.t9, 2), *li(A.t6, LOG),
            A.addu(A.t7, A.t7, A.t6), A.sw(A.t5, 0, A.t7), A.addiu(A.t9, A.t9, 1), A.sw(A.t9, 0, A.t8)]


def log_word(address):
    return [*li(A.t4, address), A.lw(A.t4, 0, A.t4), *li(A.t8, INDEX), A.lw(A.t9, 0, A.t8), A.sll(A.t7, A.t9, 2),
            *li(A.t6, LOG), A.addu(A.t7, A.t7, A.t6), A.sw(A.t4, 0, A.t7), A.addiu(A.t9, A.t9, 1), A.sw(A.t9, 0, A.t8)]


RUNTIME = ['osCreateMesgQueue', 'osCreateThread', 'osStartThread', 'osSendMesg', 'osRecvMesg',
           'osSetThreadPri', 'osViSetEvent']
PROGRAM = [
    *li(A.sp, 0x80007F00),
    *call('osCreateMesgQueue', Q, BUF, 4),
    *call('osCreateThread', T1, 1, 't1', 0, 0x8000FF00, 10),
    *call('osStartThread', T1),
    *A.DONE,  # the boot context never resumes
    't1',
    *log(1),
    *call('osCreateThread', T2, 2, 't2', 0, 0x80017F00, 20),
    *call('osStartThread', T2),  # higher priority: runs now
    *log(3),
    *call('osSendMesg', Q, 7, 1),  # wakes t2, which preempts
    *log(4),
    *call('osCreateMesgQueue', Q2, BUF2, 4),
    *call('osViSetEvent', Q2, 0x99, 1),
    *call('osCreateThread', T4, 4, 't4', 0, 0x8001FF00, 30),
    *call('osStartThread', T4),  # runs, blocks on the VI queue
    *log(5),
    'spin', A.beq(A.zero, A.zero, 'spin'), A.nop,  # preempted only at its safepoint
    't2',
    *log(2),
    *call('osRecvMesg', Q, SLOT, 1),
    *log_word(SLOT),
    *call('osSetThreadPri', 0, 5),  # below t1: yields for good
    *log(0xDEAD),
    'spin2', A.beq(A.zero, A.zero, 'spin2'), A.nop,
    't4',
    *call('osRecvMesg', Q2, SLOT + 4, 1),
    *log_word(SLOT + 4),
    *A.DONE,
]
for name in RUNTIME:  # declared runtime functions: never decoded
    PROGRAM += [name, A.jr(A.ra), A.nop]
EXPECTED = [1, 2, 3, 7, 4, 5, 0x99]

# An NTSC LAN1-like OSViMode: comRegs at +4, fldRegs[0] at +0x28.
MODE, TASK, DL, FB = 0x80004000, 0x80004100, 0x80006000, 0x80100000
COM = [0x311E, 320, 0x03E52239, 0x20D, 0xC15, 0x0C150C15, 0x006C02EC, 0x200, 0]
FLD = [0x280, 0x400, 0x002501FF, 0x000E0204, 2]
GFX_RUNTIME = ['osViSetMode', 'osViSwapBuffer', 'osSpTaskStartGo']


def poke(address, value):
    return [*li(A.t0, address), *li(A.t1, value), A.sw(A.t1, 0, A.t0)]


GFX_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *[w for i, v in enumerate(COM) for w in poke(MODE + 4 + 4 * i, v)],
    *[w for i, v in enumerate(FLD) for w in poke(MODE + 0x28 + 4 * i, v)],
    *poke(TASK, 1), *poke(TASK + 0x10, 0x80005000), *poke(TASK + 0x18, 0x80005800), *poke(TASK + 0x30, DL),
    *poke(DL, 0xB8000000),
    *call('osViSetMode', MODE), *call('osViSwapBuffer', FB), *call('osSpTaskStartGo', TASK),
    'spin', A.beq(A.zero, A.zero, 'spin'), A.nop,  # until the time limit
]
for name in GFX_RUNTIME:
    GFX_PROGRAM += [name, A.jr(A.ra), A.nop]
GFX_STUB = r'''#include <stdio.h>
#include <stdint.h>
int plaid_gfx_open(const uint8_t *h) { printf("{\"stub_open\":%u}\n", h[0]); return 0; }
void plaid_gfx_task(const uint8_t *ram, uint32_t ucode, uint32_t data, uint32_t dl) {
  uint32_t p = dl & 0x1fffffff;
  printf("{\"stub_task\":[%u,%u,%u,%u]}\n", ucode, data, dl,
         (uint32_t)ram[p] << 24 | (uint32_t)ram[p + 1] << 16 | (uint32_t)ram[p + 2] << 8 | ram[p + 3]);
}
void plaid_gfx_screen(const uint32_t *r) {
  static int once;
  int i;
  if (once++) return;
  printf("{\"stub_screen\":[");
  for (i = 0; i < 14; i++) printf("%s%u", i ? "," : "", r[i]);
  printf("]}\n");
}
int plaid_gfx_closed(void) { return 0; }
'''


def build(exe, cc, name, program, runtime, extra=()):
    (OUT / f'{name}.bin').write_bytes(A.assemble(program))
    labels = A.label_pcs(program)
    decl = dict(format='plaid-runtime-functions-v0', source='runtime test declaration',
                functions=[dict(entry=hex(labels[n]), name=n, callbacks=['a2'] if n == 'osCreateThread' else [])
                           for n in runtime])
    (OUT / f'{name}.runtime.json').write_text(json.dumps(decl))
    subprocess.run([str(exe), 'lower-c', str(OUT / f'{name}.bin'), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                    str(OUT / f'{name}.c'), str(OUT / f'{name}.runtime.json')], check=True)
    native = OUT / (f'{name}-native.exe' if os.name == 'nt' else f'{name}-native')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', f'-DPLAID_LOWERED="{name}.c"', '-I', str(OUT), *extra,
                    str(ROOT / 'runtime/plaid_rt.c'), '-pthread', '-o', str(native)], check=True)
    return native


def graphics_bridge(exe, cc):
    (OUT / 'stub.c').write_text(GFX_STUB)
    rom = OUT / 'stub.z64'
    rom.write_bytes(bytes([0x80, 0x37, 0x12, 0x40]) + bytes(0x1000))
    native = build(exe, cc, 'gfx', GFX_PROGRAM, GFX_RUNTIME, ['-DPLAID_RT64', str(OUT / 'stub.c')])
    run = subprocess.run([str(native), '--rom', str(rom), '--stop-at', 'none', '--seconds', '0.5'],
                         capture_output=True, text=True, timeout=30)
    lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    assert run.returncode == 0 and lines.get('stop') == 'time limit', (run.returncode, run.stdout, run.stderr)
    assert lines['stub_open'] == 0x80
    assert lines['stub_task'] == [0x80005000, 0x80005800, DL, 0xB8000000], lines['stub_task']
    screen = [COM[0], (FB & 0x1FFFFFFF) + FLD[0], COM[1], FLD[4], 0, COM[2], COM[3], COM[4], COM[5], COM[6],
              FLD[2], FLD[3], COM[7], FLD[1]]
    assert lines['stub_screen'] == screen, (lines['stub_screen'], screen)
    print('renderer bridge: VI registers from OSViMode and framebuffer, graphics task addresses and big-endian RAM')


def main():
    exe = ROOT / 'target/debug/plaid.exe'
    if not exe.exists():
        exe = ROOT / 'target/debug/plaid'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    native = build(exe, cc, 'sched', PROGRAM, RUNTIME)
    run = subprocess.run([str(native), '--seconds', '5', '--dump', hex(LOG), str(len(EXPECTED) + 1)],
                         capture_output=True, text=True, timeout=30)
    lines = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    dump = next(line for line in lines if 'dump' in line)['words']
    stop = next(line for line in lines if 'stop' in line)
    assert run.returncode == 0 and stop['stop'] == 'exit', (run.returncode, run.stdout, run.stderr)
    assert dump == EXPECTED + [0], ([hex(w) for w in dump], EXPECTED)
    assert stop['vi'] >= 1
    print('runtime scheduling: start/send preemption, blocking receive, priority drop and VI preemption '
          'of a spinning thread match libultra order', json.dumps(dump))
    graphics_bridge(exe, cc)


if __name__ == '__main__':
    sys.exit(main())
