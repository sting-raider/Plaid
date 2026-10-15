"""Deterministic test of the Plaid host runtime (ADR-0159).

A synthetic MIPS program, assembled with spike096's assembler, declares
libultra functions as runtime functions, is lowered with `plaid lower-c` and
linked with runtime/plaid_rt.c. Its threads append to a log in guest RAM; the
log order checks libultra scheduling: a higher-priority thread preempts on
start and on a message send, a blocked receive yields, lowering a priority
yields, osYieldThread queues behind an equal priority, and a VI retrace preempts a spinning thread at a loop safepoint.

A second program checks the renderer bridge (ADR-0163) without a GPU: a stub
plaid_gfx_* records the VI registers the runtime derives from an OSViMode and
framebuffer, and the graphics task addresses and RAM it hands over. It also
checks controller 1 (ADR-0164): a scripted --press merged with the stub
window's stick. A third program checks that --save keeps the EEPROM across
runs (ADR-0165). A fourth runs an RSP task through lowered IMEM snapshots
(ADR-0169).
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
T1, T2, T4, T5 = 0x80002100, 0x80002300, 0x80002500, 0x80002700
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
           'osSetThreadPri', 'osViSetEvent', 'osYieldThread']
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
    *call('osCreateThread', T5, 5, 't5', 0, 0x80027F00, 10),
    *call('osStartThread', T5),  # equal priority: queued behind t1
    *log(6),
    *call('osYieldThread'),  # t5 runs first
    *log(8),
    'spin', A.beq(A.zero, A.zero, 'spin'), A.nop,  # preempted only at its safepoint
    't2',
    *log(2),
    *call('osRecvMesg', Q, SLOT, 1),
    *log_word(SLOT),
    *call('osSetThreadPri', 0, 5),  # below t1: yields for good
    *log(0xDEAD),
    'spin2', A.beq(A.zero, A.zero, 'spin2'), A.nop,
    't5',
    *log(0x10),
    *call('osYieldThread'),  # back to t1, queued first
    *log(0xDEAD),
    'spin3', A.beq(A.zero, A.zero, 'spin3'), A.nop,
    't4',
    *call('osRecvMesg', Q2, SLOT + 4, 1),
    *log_word(SLOT + 4),
    *A.DONE,
]
for name in RUNTIME:  # declared runtime functions: never decoded
    PROGRAM += [name, A.jr(A.ra), A.nop]
EXPECTED = [1, 2, 3, 7, 4, 5, 6, 0x10, 8, 0x99]

# An NTSC LAN1-like OSViMode: comRegs at +4, fldRegs[0] at +0x28.
MODE, TASK, DL, FB, PADS = 0x80004000, 0x80004100, 0x80006000, 0x80100000, 0x80004200
COM = [0x311E, 320, 0x03E52239, 0x20D, 0xC15, 0x0C150C15, 0x006C02EC, 0x200, 0]
FLD = [0x280, 0x400, 0x002501FF, 0x000E0204, 2]
GFX_RUNTIME = ['osViSetMode', 'osViSwapBuffer', 'osSpTaskStartGo', 'osContGetReadData']


def poke(address, value):
    return [*li(A.t0, address), *li(A.t1, value), A.sw(A.t1, 0, A.t0)]


GFX_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *[w for i, v in enumerate(COM) for w in poke(MODE + 4 + 4 * i, v)],
    *[w for i, v in enumerate(FLD) for w in poke(MODE + 0x28 + 4 * i, v)],
    *poke(TASK, 1), *poke(TASK + 0x10, 0x80005000), *poke(TASK + 0x18, 0x80005800), *poke(TASK + 0x30, DL),
    *poke(DL, 0xB8000000),
    *call('osViSetMode', MODE), *call('osViSwapBuffer', FB), *call('osSpTaskStartGo', TASK),
    *call('osContGetReadData', PADS),
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
uint32_t plaid_gfx_input(void) { return 0x10F0; } /* stick 16, -16 */
void plaid_audio_play(const uint8_t *s, uint32_t bytes, uint32_t rate) {
  printf("{\"stub_audio\":[%u,%u,%u]}\n", bytes, rate, (uint32_t)s[0] << 24 | s[1] << 16 | s[2] << 8 | s[3]);
}
'''


# Reads EEPROM block 1, increments its first word and writes it back.
READ, DATA = 0x80004300, 0x80004310
SAVE_RUNTIME = ['osEepromRead', 'osEepromWrite']
SAVE_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *call('osEepromRead', 0, 1, READ),
    *li(A.t0, READ), A.lw(A.t1, 0, A.t0), A.addiu(A.t1, A.t1, 1), *li(A.t0, DATA), A.sw(A.t1, 0, A.t0),
    *li(A.t1, 0xA5A5A5A5), A.sw(A.t1, 4, A.t0),
    *call('osEepromWrite', 0, 1, DATA),
    *A.DONE,
]
for name in SAVE_RUNTIME:
    SAVE_PROGRAM += [name, A.jr(A.ra), A.nop]


# ---- RSP tasks (ADR-0169) ----
spec97 = importlib.util.spec_from_file_location('spike097', ROOT / 'spikes/097-rsp-slice/run.py')
V = importlib.util.module_from_spec(spec97)
spec97.loader.exec_module(V)
BOOT, UCODE, UDATA, OUTB, SPQ, SPBUF, RTASK = (0x80006000, 0x80006200, 0x80006400, 0x80005000, 0x80004400,
                                               0x80004420, 0x80004500)
# Like libultra's rspboot, the boot microcode has code above 0x080 that runs
# before it DMAs the task's ucode over it: ucode_data to DMEM 0, then 0x80
# bytes of ucode to IMEM 0x080, then a jump there.
BOOT_CODE = [A.j('part2'), A.nop,
             'part3', A.lw(A.t0, 0x10, A.at), A.addiu(A.t1, A.zero, 0x7F), A.addiu(A.t2, A.zero, 0x1080),
             V.mtc0(A.t2, 0), V.mtc0(A.t0, 1), V.mtc0(A.t1, 2), A.jr(A.t2), A.nop,
             *[A.nop] * 24,
             'part2', A.addiu(A.at, A.zero, 0xFC0), A.lw(A.t0, 0x18, A.at), A.lw(A.t1, 0x1C, A.at),
             A.addiu(A.t1, A.t1, -1), V.mtc0(A.zero, 0), V.mtc0(A.t0, 1), V.mtc0(A.t1, 2), A.j('part3'), A.nop]
# The ucode adds to a data word, keeps the physical output_buff the task
# carries, adds a vector to itself, and DMAs 32 bytes of results out.
UCODE_CODE = [A.lw(A.t0, 0, A.zero), *li(A.t1, 0x11111111), A.addu(A.t0, A.t0, A.t1), A.sw(A.t0, 0x100, A.zero),
              A.addiu(A.at, A.zero, 0xFC0), A.lw(A.t2, 0x28, A.at), A.sw(A.t2, 0x104, A.zero),
              V.lqv(1, 1), V.vu(0x14, 2, 1, 1, 0), V.sqv(2, 0x11, A.zero),
              A.addiu(A.t3, A.zero, 0x100), V.mtc0(A.t3, 0), V.mtc0(A.t2, 1), A.addiu(A.t4, A.zero, 0x1F),
              V.mtc0(A.t4, 3), 'wait', V.mfc0(A.t5, 6), A.bne(A.t5, A.zero, 'wait'), A.nop, V.BREAK, A.nop]
UDATA_WORDS = [0x01020304, 0, 0, 0, 0x7FFF0001, 0x8000FFFF, 0x12340000, 0xC0004000]


def rsp_words(items, base):
    labels, pc = {}, base
    for x in items:
        if isinstance(x, str):
            labels[x] = pc
        else:
            pc += 4
    words, pc = [], base
    for x in items:
        if not isinstance(x, str):
            words.append(x(pc, labels) & 0xFFFFFFFF if callable(x) else x)
            pc += 4
    return words


BOOT_WORDS, UCODE_WORDS = rsp_words(BOOT_CODE, 0), rsp_words(UCODE_CODE, 0x80)
TASK_WORDS = [2, 0, BOOT, 4 * len(BOOT_WORDS), UCODE, 0x800, UDATA, 32, 0, 0, OUTB, 0, 0, 0, 0, 0]
RSP_RUNTIME = ['osCreateMesgQueue', 'osSetEventMesg', 'osSpTaskLoad', 'osSpTaskStartGo', 'osRecvMesg',
               'osCreateThread', 'osStartThread']
RSP_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *[w for i, v in enumerate(BOOT_WORDS) for w in poke(BOOT + 4 * i, v)],
    *[w for i, v in enumerate(UCODE_WORDS) for w in poke(UCODE + 4 * i, v)],
    *[w for i, v in enumerate(UDATA_WORDS) for w in poke(UDATA + 4 * i, v)],
    *[w for i, v in enumerate(TASK_WORDS) for w in poke(RTASK + 4 * i, v)],
    *call('osCreateThread', T1, 1, 'audio', 0, 0x8000FF00, 10),
    *call('osStartThread', T1),
    *A.DONE,  # the boot context never resumes
    'audio',  # a thread, so it may block on the SP event
    *call('osCreateMesgQueue', SPQ, SPBUF, 4),
    *call('osSetEventMesg', 4, SPQ, 0x55),  # OS_EVENT_SP
    *call('osSpTaskLoad', RTASK), *call('osSpTaskStartGo', RTASK),
    *call('osRecvMesg', SPQ, OUTB + 0x20, 1),
    *A.DONE,
]
for name in RSP_RUNTIME:
    RSP_PROGRAM += [name, A.jr(A.ra), A.nop]


def rsp_tasks(exe, cc):
    """The snapshot protocol end to end: the first run saves IMEM at the boot
    entry, the second (boot lowered) saves it where the boot jumps into the
    ucode it loaded, and the third runs the whole task natively."""
    snaps, texts = OUT / 'rsp-snapshots', OUT / 'rsp-texts'
    for d in (snaps, texts):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    rsp_c = ['-DPLAID_RSP', '-I', str(ROOT / 'crates/plaid-lower/src')]
    for step, pc in enumerate((0x000, 0x080, None)):
        files = subprocess.check_output([sys.executable, str(ROOT / 'runtime/rsp_texts.py'), str(exe), str(snaps),
                                         str(texts)], text=True).split()
        native = build(exe, cc, 'rsp', RSP_PROGRAM, RSP_RUNTIME, [*rsp_c, *files])
        run = subprocess.run([str(native), '--rsp-dump', str(snaps), '--dump', hex(OUTB), '9'],
                             capture_output=True, text=True, timeout=30)
        lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        saved = sorted(p.name for p in snaps.glob('imem-*.bin'))
        if pc is not None:
            assert run.returncode == 1 and lines['stop'] == 'unlowered RSP code', (run.stdout, run.stderr)
            assert len(saved) == step + 1 and any(s.startswith(f'imem-{pc:03x}-') for s in saved), saved
            continue
        assert run.returncode == 0 and lines['stop'] == 'exit', (run.returncode, run.stdout, run.stderr)
        vector = [((h + h) & 0xFFFF) for w in UDATA_WORDS[4:] for h in (w >> 16, w & 0xFFFF)]
        expected = [0x12131415, OUTB & 0x1FFFFFFF, 0, 0,
                    *[vector[i] << 16 | vector[i + 1] for i in range(0, 8, 2)], 0x55]
        assert lines['words'] == expected, ([hex(w) for w in lines['words']], [hex(w) for w in expected])
    print('RSP tasks: boot and ucode IMEM snapshots saved, lowered and run natively; the ucode read the physical '
          'task, its DMA reached RDRAM and the SP event followed')


# ---- AI DMA (ADR-0170) ----
AIQ, AIBUF, VAL = 0x80004400, 0x80004420, 0x80004440
B1, B2, B3 = 0x80020000, 0x80021000, 0x80022000


def log_v0():
    return [*li(A.t4, VAL), A.sw(A.v0, 0, A.t4), *log_word(VAL)]


AI_RUNTIME = ['osCreateMesgQueue', 'osSetEventMesg', 'osRecvMesg', 'osCreateThread', 'osStartThread', 'osGetCount',
              'osAiSetFrequency', 'osAiSetNextBuffer', 'osAiGetLength', 'osAiGetStatus']
AI_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *poke(B2, 0x11223344),
    *call('osCreateThread', T1, 1, 'aithr', 0, 0x8000FF00, 10),
    *call('osStartThread', T1),
    *A.DONE,
    'aithr',
    *call('osCreateMesgQueue', AIQ, AIBUF, 4),
    *call('osSetEventMesg', 6, AIQ, 0x66),  # OS_EVENT_AI
    *call('osAiSetFrequency', 32000), *log_v0(),
    *call('osAiSetNextBuffer', B1, 0x1000), *log_v0(),
    *call('osAiSetNextBuffer', B2, 0x1000), *log_v0(),
    *call('osAiSetNextBuffer', B3, 0x1000), *log_v0(),  # the FIFO is full
    *call('osAiGetStatus'), *log_v0(),
    *call('osRecvMesg', AIQ, SLOT, 1), *log_word(SLOT),  # B1 started
    *call('osGetCount'), *log_v0(),
    *call('osRecvMesg', AIQ, SLOT, 1), *log_word(SLOT),  # B1 played out, B2 started
    *call('osGetCount'), *log_v0(),
    *call('osAiGetStatus'), *log_v0(),
    'drain', *call('osAiGetLength'), A.bne(A.v0, A.zero, 'drain'), A.nop,
    *call('osAiGetStatus'), *log_v0(),
    *A.DONE,
]
for name in AI_RUNTIME:
    AI_PROGRAM += [name, A.jr(A.ra), A.nop]


def audio_dma(exe, cc):
    """The AI FIFO drains at the DAC rate and raises the AI event as each
    buffer starts; samples reach the WAV file and the host audio hook."""
    (OUT / 'stub.c').write_text(GFX_STUB)
    rom, wav = OUT / 'stub.z64', OUT / 'ai.wav'
    native = build(exe, cc, 'ai', AI_PROGRAM, AI_RUNTIME, ['-DPLAID_RT64', str(OUT / 'stub.c')])
    run = subprocess.run([str(native), '--rom', str(rom), '--stop-at', 'none', '--seconds', '5', '--wav', str(wav),
                          '--dump', hex(LOG), '11'], capture_output=True, text=True, timeout=30)
    lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    assert run.returncode == 0 and lines['stop'] == 'exit', (run.returncode, run.stdout, run.stderr)
    w = lines['words']
    rate = 48681812 // round(48681812 / 32000)
    assert w[:6] == [rate, 0, 0, 0xFFFFFFFF, 0xC3100001, 0x66], [hex(x) for x in w]
    assert w[7] == 0x66 and w[9:] == [0x43100000, 0x03100000], [hex(x) for x in w]
    # one buffer of 1024 samples at the DAC rate, in COUNT ticks (46.875 MHz)
    ticks, want = (w[8] - w[6]) & 0xFFFFFFFF, 1024 * 46875000 // rate
    assert want * 0.8 < ticks < want * 1.5, (ticks, want)
    data = wav.read_bytes()
    assert len(data) == 44 + 0x2000 and data[44 + 0x1000:44 + 0x1004] == bytes([0x22, 0x11, 0x44, 0x33])
    assert int.from_bytes(data[24:28], 'little') == rate
    assert lines['stub_audio'] == [0x1000, rate, 0x11223344], lines['stub_audio']
    print('AI DMA: a two-buffer FIFO refuses a third buffer, drains at the DAC rate', f'({ticks} of {want} ticks),',
          'raises the AI event per buffer start, and feeds the WAV file and host audio')


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
    run = subprocess.run([str(native), '--rom', str(rom), '--stop-at', 'none', '--seconds', '1',
                          '--press', '0x9000@0:100000', '--press', '0x0010@100000:1', '--dump', hex(PADS), '3'],
                         capture_output=True, text=True, timeout=30)
    lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    assert run.returncode == 0 and lines.get('stop') == 'time limit', (run.returncode, run.stdout, run.stderr)
    assert lines['stub_open'] == 0x80
    assert 54 <= lines['vi'] <= 62, lines['vi']  # NTSC retraces in one second (ADR-0166)
    assert lines['stub_task'] == [0x80005000, 0x80005800, DL, 0xB8000000], lines['stub_task']
    screen = [COM[0], (FB & 0x1FFFFFFF) + FLD[0], COM[1], FLD[4], 0, COM[2], COM[3], COM[4], COM[5], COM[6],
              FLD[2], FLD[3], COM[7], FLD[1]]
    assert lines['stub_screen'] == screen, (lines['stub_screen'], screen)
    # pad 1: A|START (the later R press is not yet due), stick 16, -16; pad 2: errno 8 (absent)
    assert lines['words'] == [0x900010F0, 0, 0x00000800], [hex(w) for w in lines['words']]
    print('renderer bridge: VI registers from OSViMode and framebuffer, graphics task addresses and big-endian RAM, '
          'controller 1 from scripted presses and the window,', lines['vi'], 'VI retraces in one second')


def save_file(exe, cc):
    native = build(exe, cc, 'save', SAVE_PROGRAM, SAVE_RUNTIME)
    save = OUT / 'save.eep'
    for leftover in (save, OUT / 'save.eep.tmp'):
        leftover.unlink(missing_ok=True)
    for count in (0, 1):
        run = subprocess.run([str(native), '--save', str(save), '--dump', hex(READ), '2'],
                             capture_output=True, text=True, timeout=30)
        lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        assert run.returncode == 0 and lines.get('stop') == 'exit', (run.returncode, run.stdout, run.stderr)
        assert lines['words'] == [count, 0xA5A5A5A5 if count else 0], [hex(w) for w in lines['words']]
    data = save.read_bytes()
    assert data == bytes(8) + bytes([0, 0, 0, 2]) + b'\xa5' * 4 + bytes(512 - 16), data[:16]
    assert not (OUT / 'save.eep.tmp').exists()
    save.write_bytes(bytes(100))  # not an EEPROM image: refused, never overwritten
    run = subprocess.run([str(native), '--save', str(save)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 2 and save.read_bytes() == bytes(100), (run.returncode, run.stderr)
    print('EEPROM save: kept across runs, replaced through a temporary file, a malformed save refused')


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
    print('runtime scheduling: start/send preemption, blocking receive, priority drop, yield and VI preemption '
          'of a spinning thread match libultra order', json.dumps(dump))
    graphics_bridge(exe, cc)
    save_file(exe, cc)
    rsp_tasks(exe, cc)
    audio_dma(exe, cc)
    from test_overlays import main as overlay_verifiers
    overlay_verifiers()


if __name__ == '__main__':
    sys.exit(main())
