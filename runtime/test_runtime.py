"""Deterministic test of the Plaid host runtime (ADR-0159).

A synthetic MIPS program, assembled with spike096's assembler, declares
libultra functions as runtime functions, is lowered with `plaid lower-c` and
linked with runtime/plaid_rt.c. Its threads append to a log in guest RAM; the
log order checks libultra scheduling: a higher-priority thread preempts on
start and on a message send, a blocked receive yields, lowering a priority
yields, and a VI retrace preempts a spinning thread at a loop safepoint.
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


def main():
    exe = ROOT / 'target/debug/plaid.exe'
    if not exe.exists():
        exe = ROOT / 'target/debug/plaid'
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'sched.bin').write_bytes(A.assemble(PROGRAM))
    labels = A.label_pcs(PROGRAM)
    decl = dict(format='plaid-runtime-functions-v0', source='runtime test declaration',
                functions=[dict(entry=hex(labels[n]), name=n, callbacks=['a2'] if n == 'osCreateThread' else [])
                           for n in RUNTIME])
    (OUT / 'sched.runtime.json').write_text(json.dumps(decl))
    subprocess.run([str(exe), 'lower-c', str(OUT / 'sched.bin'), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                    str(OUT / 'sched.c'), str(OUT / 'sched.runtime.json')], check=True)
    native = OUT / ('sched-native.exe' if os.name == 'nt' else 'sched-native')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="sched.c"', '-I', str(OUT),
                    str(ROOT / 'runtime/plaid_rt.c'), '-pthread', '-o', str(native)], check=True)
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


if __name__ == '__main__':
    sys.exit(main())
