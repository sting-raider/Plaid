"""Deterministic test of the Plaid host runtime (ADR-0159).

A synthetic MIPS program, assembled with spike096's assembler, declares
libultra functions as runtime functions, is lowered with `plaid lower-c` and
linked with runtime/plaid_rt.c. Its threads append to a log in guest RAM; the
log order checks libultra scheduling: a higher-priority thread preempts on
start and on a message send, a blocked receive yields, lowering a priority
yields, osYieldThread queues behind an equal priority, and a VI retrace preempts a spinning thread at a loop safepoint.

A second program checks the renderer bridge (ADR-0163) without a GPU: a stub
plaid_gfx_* records the VI registers the guest program wrote, and the graphics task addresses and RAM it hands over. It also
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
OUT = Path(os.environ.get('PLAID_RUNTIME_TEST_OUT', ROOT / 'target/runtime-test')).resolve()

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
           'osSetThreadPri', 'osSetEventMesg', 'osYieldThread']
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
    *call('osCreateThread', T4, 4, 't4', 0, 0x8001FF00, 30),
    *call('osStartThread', T4),  # runs, blocks on the VI queue
    *log(5),
    *call('osCreateThread', T5, 5, 't5', 0, 0x80027F00, 10),
    *call('osStartThread', T5),  # equal priority: queued behind t1
    *log(6),
    *call('osYieldThread'),  # t5 runs first
    *log(8),
    # Arm VI only after setup: a host stall may otherwise preempt before log(6).
    *call('osSetEventMesg', 7, Q2, 0x99),  # OS_EVENT_VI
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
GFX_RUNTIME = ['osSpTaskStartGo', 'osContGetReadData']
# VI registers as libultra's VI manager programs them from that mode and FB
SCREEN = [COM[0], (FB & 0x1FFFFFFF) + FLD[0], COM[1], FLD[4], 0, COM[2], COM[3], COM[4], COM[5], COM[6],
          FLD[2], FLD[3], COM[7], FLD[1]]


def poke(address, value):
    return [*li(A.t0, address), *li(A.t1, value), A.sw(A.t1, 0, A.t0)]


GFX_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *[w for i, v in enumerate(SCREEN) if i != 4 for w in poke(0xA4400000 + 4 * i, v)],
    *poke(TASK, 1), *poke(TASK + 0x10, 0x80005000), *poke(TASK + 0x18, 0x80005800), *poke(TASK + 0x30, DL),
    *poke(DL, 0xB8000000),
    *call('osSpTaskStartGo', TASK),
    *call('osContGetReadData', PADS),
    'spin', A.beq(A.zero, A.zero, 'spin'), A.nop,  # until the time limit
]
for name in GFX_RUNTIME:
    GFX_PROGRAM += [name, A.jr(A.ra), A.nop]
GFX_STUB = r'''#include <stdio.h>
#include <stdint.h>
int plaid_gfx_native_rsp(int (*work)(void *), void *context) {
  int result = work(context);
  printf("{\"stub_native_rsp\":%d}\n", result);
  return result;
}
int plaid_gfx_open(const uint8_t *h) { printf("{\"stub_open\":%u}\n", h[0]); return 0; }
int plaid_gfx_task(const uint8_t *ram, uint32_t ucode, uint32_t data, uint32_t dl,
                   int (*writeback)(void *, uint32_t, uint32_t, const uint8_t *), void *context) {
  uint32_t p = dl & 0x1fffffff;
  (void)writeback; (void)context;
  printf("{\"stub_task\":[%u,%u,%u,%u]}\n", ucode, data, dl,
         (uint32_t)ram[p] << 24 | (uint32_t)ram[p + 1] << 16 | (uint32_t)ram[p + 2] << 8 | ram[p + 3]);
  return 0;
}
int plaid_gfx_rdp(const uint8_t *ram, const uint8_t *commands, uint32_t size, const uint8_t *dirty,
                  int (*writeback)(void *, uint32_t, uint32_t, const uint8_t *), void *context) {
  uint32_t i, pages = 0;
  (void)ram; (void)writeback; (void)context;
  for (i = 0; i < 2048; i++) pages += dirty[i] != 0;
  printf("{\"stub_rdp\":[%u,%u", size, pages);
  for (i = 0; i < size; i += 4)
    printf(",%u", (uint32_t)commands[i] << 24 | (uint32_t)commands[i + 1] << 16 |
           (uint32_t)commands[i + 2] << 8 | commands[i + 3]);
  printf("]}\n");
  return 0;
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


def rsp_state_abi(exe, cc):
    """Recompile one retained text after a host state layout change."""
    directory = OUT / 'rsp-abi'
    directory.mkdir(exist_ok=True)
    image = directory / 'code.bin'
    image.write_bytes(b''.join(w.to_bytes(4, 'big') for w in
                              [A.addiu(A.t0, A.zero, 42), A.sw(A.t0, 0, A.zero), V.BREAK]))
    lowered = directory / 'code.c'
    subprocess.run([str(exe), 'lower-rsp', str(image), '0', '12', '0', 'abi', str(lowered), '--raw'], check=True)
    harness = directory / 'host.c'
    harness.write_text('''#include "rsp_state.h"
#include <assert.h>
extern const plaid_rsp_text plaid_rsp_text_abi;
static plaid_rsp r;
int main(void) {
  memcpy(r.imem, plaid_rsp_text_abi.bytes, 12);
  assert(plaid_rsp_text_abi.run(&r, 0) == 0);
  assert(r.halted && r.broken && r.pc == 12 && r.fault == 0);
  assert(r.r[8] == 42 && r.dmem[3] == 42);
  for (unsigned i = 4; i < sizeof r.dmem; i++) assert(r.dmem[i] == 0);
  return 0;
}
''')
    header = (ROOT / 'crates/plaid-lower/src/rsp_state.h').read_text()
    for changed in (False, True):
        # Both TUs must see the new layout even when the lowered C is retained.
        (directory / 'rsp_state.h').write_text(header.replace('  u32 pc, fault, fault_pc;',
                                              '  u64 abi_test_padding[3];\n  u32 pc, fault, fault_pc;')
                                             if changed else header)
        native = directory / 'abi.exe'
        subprocess.run([cc, '-O2', '-I', str(directory), str(lowered), str(harness), '-o', str(native)], check=True)
        subprocess.run([str(native)], check=True, timeout=30)
    print('RSP state ABI: retained lowered C agrees with the host before and after a layout change')


def rsp_completion(exe, cc):
    registry = OUT / 'rsp-incomplete-registry.c'
    prefix = '#include "rsp_state.h"\nstatic const u8 bytes[4096] = {'
    body = '''};
static int incomplete(plaid_rsp *r, u32 pc) { (void)r; (void)pc; return 0; }
static const plaid_rsp_text text = {0, 4096, bytes, incomplete, "incomplete"};
const plaid_rsp_text *const plaid_rsp_texts[] = {&text, 0};
'''
    # Unknown code must also fail, rather than being hidden by --rsp-capture.
    boot = b''.join(w.to_bytes(4, 'big') for w in BOOT_WORDS)
    for data, reason in ((bytes(4), 'unlowered RSP code'),
                         (boot, 'RSP task returned without halting')):
        registry.write_text(prefix + ','.join(map(str, data)) + body)
        native = build(exe, cc, 'rsp-incomplete', RSP_PROGRAM, RSP_RUNTIME,
                       ['-DPLAID_RSP', '-I', str(ROOT / 'crates/plaid-lower/src'), str(registry)])
        run = subprocess.run([str(native), '--rsp-capture', '1', str(OUT)],
                             capture_output=True, text=True, timeout=30)
        assert run.returncode == 1 and reason in run.stdout, (run.stdout, run.stderr)
    print('RSP capture refuses unknown code and a text returning success without halting')


def rsp_graphics(exe, cc):
    """CPU and lowered RSP share DPC state; raw commands cross the renderer ABI unchanged."""
    commands = [0x11223344, 0x55667788, 0x99AABBCC, 0xDDEEFF00]
    code = [w for offset, value in zip((0xFF8, 0xFFC, 0, 4), commands)
            for w in [*li(A.t0, value), A.sw(A.t0, offset, A.zero)]]
    code += [A.addiu(A.t0, A.zero, 2), V.mtc0(A.t0, 11),  # XBUS source
             A.addiu(A.t0, A.zero, 0xFF8), V.mtc0(A.t0, 8),
             A.addiu(A.t0, A.zero, 0x1008), V.mtc0(A.t0, 9), V.BREAK]
    words = rsp_words(code, 0)
    task = [1, 0, BOOT, 4 * len(words), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    task[12] = DL  # the runtime reports the task's command buffer before executing it
    program = [*li(A.sp, 0x80007F00),
               *[w for i, v in enumerate(words) for w in poke(BOOT + 4 * i, v)],
               *[w for i, v in enumerate(task) for w in poke(RTASK + 4 * i, v)],
               *poke(0xA410000C, 8),  # freeze from the CPU, observed by the RSP
               'before_gfx_load', *call('osSpTaskLoad', RTASK), *call('osSpTaskStartGo', RTASK),
               *log_word(0xA4100000), *log_word(0xA4100004), *log_word(0xA4100008),
               *poke(0xA410000C, 4), *log_word(0xA4100008),  # unfreeze drains wrapped DMEM
               *log_word(0xA4000FF8),  # executed microcode leaves known SP memory
               *poke(0xA410000C, 1),  # RDRAM source
               *poke(DL, 0x12345678), *poke(DL + 4, 0x90ABCDEF),
               *poke(0xA4100000, DL & 0x1FFFFFFF), *poke(0xA4100004, (DL & 0x1FFFFFFF) + 8),
               *A.DONE]
    runtime = ['osSpTaskLoad', 'osSpTaskStartGo']
    for name in runtime:
        program += [name, A.jr(A.ra), A.nop]
    snapshot = OUT / 'gfx-rsp.bin'
    snapshot.write_bytes(b''.join(w.to_bytes(4, 'big') for w in words).ljust(4096, b'\0'))
    lowered = OUT / 'gfx-rsp.c'
    subprocess.run([str(exe), 'lower-rsp', str(snapshot), '0', '0x1000', '0', 'gfx_test', str(lowered), '--raw'],
                   check=True, capture_output=True)
    registry = OUT / 'gfx-registry.c'
    registry.write_text('#include "rsp_state.h"\nextern const plaid_rsp_text plaid_rsp_text_gfx_test;\n'
                        'const plaid_rsp_text *const plaid_rsp_texts[] = {&plaid_rsp_text_gfx_test, 0};\n')
    (OUT / 'stub.c').write_text(GFX_STUB)
    native = build(exe, cc, 'rsp-gfx', program, runtime,
                   ['-DPLAID_RSP', '-DPLAID_RT64', '-I', str(ROOT / 'crates/plaid-lower/src'),
                    str(lowered), str(registry), str(OUT / 'stub.c')])
    run = subprocess.run([str(native), '--rsp-gfx', '--rom', str(OUT / 'stub.z64'), '--stop-at', 'none',
                          '--dump', hex(LOG), '5'], capture_output=True, text=True, timeout=30)
    lines = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert [line['stub_rdp'] for line in lines if 'stub_rdp' in line] == [
        [16, 2048, *commands], [8, 2048, 0x12345678, 0x90ABCDEF]], lines
    assert next(line['words'] for line in lines if 'words' in line) == [
        0xFF8, 0x1008, 0xFF8, 0x1008, commands[0]], lines
    assert next(line['stop'] for line in lines if 'stop' in line) == 'exit', lines
    assert [line['stub_native_rsp'] for line in lines if 'stub_native_rsp' in line] == [0], lines
    assert not any('stub_task' in line for line in lines), lines
    # Unknown HLE microcode must select the same native RSP/DPC path without
    # --rsp-gfx, including a CPU freeze set before the renderer's refusal.
    (OUT / 'stub.c').write_text(GFX_STUB.replace(
        '(void)writeback; (void)context;',
        '(void)writeback; (void)context; return 2;', 1))
    for corrupt in (False, True):
        variant = program.copy()
        if corrupt:
            before_load = variant.index('before_gfx_load')
            variant[before_load:before_load] = poke(BOOT, 0xFFFFFFFF)
        auto = build(exe, cc, f'rsp-gfx-auto-{int(corrupt)}', variant, runtime,
                     ['-DPLAID_RSP', '-DPLAID_RT64', '-I', str(ROOT / 'crates/plaid-lower/src'),
                      str(lowered), str(registry), str(OUT / 'stub.c')])
        result = subprocess.run([str(auto), '--rom', str(OUT / 'stub.z64'), '--stop-at', 'none',
                                 '--dump', hex(LOG), '5'], capture_output=True, text=True, timeout=30)
        auto_lines = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert 'switching to native RSP LLE' in result.stderr, result.stderr
        if corrupt:
            assert result.returncode == 1 and 'unlowered RSP code' in result.stdout, result.stdout
            assert not any('stub_rdp' in line for line in auto_lines), auto_lines
        else:
            assert result.returncode == 0, (result.stdout, result.stderr)
            assert [line for line in auto_lines if 'stub_rdp' in line or 'words' in line] == [
                line for line in lines if 'stub_rdp' in line or 'words' in line], auto_lines
    print('native graphics RSP: shared CPU/RSP DPC, frozen lists, wrapped DMEM, RDRAM and CPU RAM visibility')


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


IO_PROGRAM = [
    *li(A.sp, 0x80007F00),
    *log_word(0xA4000040),  # DMEM holds ROM 0x40-0xfff after boot
    *log_word(0xA4600010),  # PI_STATUS: idle
    *log_word(0xA4600014),  # PI_BSD_DOM1_LAT from the header
    *poke(0xA460001C, 0x1FF), *log_word(0xA460001C),  # PI_BSD_DOM1_PGS keeps four bits
    *poke(0xA4000100, 0x12345678), *log_word(0xA4000100),
    *poke(0xA4100000, 0x1237), *log_word(0xA410000C),  # DPC_START: start valid, ready
    *poke(0xA4100004, 0x2000), *log_word(0xA4100008),  # DPC_END: the list is consumed at once
    *poke(0xA410000C, 0x2A), *log_word(0xA410000C),  # DPC_STATUS: set source, freeze, flush
    *log_word(0xA6001010),  # no 64DD: open bus
    *log_word(0xB0000040),  # cartridge ROM
    *log_word(0xA8000000),  # SRAM is not modelled: fault 1
    *A.DONE,
]
CACHED_IO_PROGRAM = [*li(A.sp, 0x80007F00), *log_word(0x84000040), *A.DONE]


def rcp_io(exe, cc):
    """Uncached CPU words reach SP memory and the PI as pinned ares answers
    them (ADR-0177); unmodelled devices and cached access fail closed."""
    rom = OUT / 'io.z64'
    rom.write_bytes(bytes([0x80, 0x37, 0x12, 0x40]) + bytes(0x3C) + bytes([0xCA, 0xFE, 0xF0, 0x0D]) + bytes(0xFBC))
    for name, program, words in (('io', IO_PROGRAM, [0xCAFEF00D, 0, 0x40, 0xF, 0x12345678, 0x480, 0x2000, 0x87,
                                                0x10101010, 0xCAFEF00D, 0]),
                                 ('io_cached', CACHED_IO_PROGRAM, [0])):
        native = build(exe, cc, name, program, [])
        run = subprocess.run([str(native), '--rom', str(rom), '--dump', hex(LOG), str(len(words))],
                             capture_output=True, text=True, timeout=30)
        lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        assert lines.get('stop') == 'guest fault' and lines['fault'] == 1, (run.stdout, run.stderr)
        assert lines.get('words', []) == words, [hex(w) for w in lines.get('words', [])]
    print('RCP I/O: DMEM boot bytes, idle PI status, masked PI timing, DPC registers, open bus and ROM words as ares; '
          'SRAM and cached RCP access fail closed')


def raw_pi_dma(exe, cc):
    handle, destination = 0x80004800, 0x80004900
    rom = OUT / 'io.z64'
    original = rom.read_bytes()
    for name, direction, offset, stop in [('raw_pi', 0, 0x40, 'exit'),
                                          ('raw_pi_phys', 0, 0x10000040, 'exit'),
                                          ('raw_pi_kseg1', 0, 0xb0000040, 'exit'),
                                          ('raw_pi_write', 1, 0x40, 'PI write to cartridge'),
                                          ('raw_pi_oob', 0, len(original), 'PI DMA outside the ROM')]:
        program = [*li(A.sp, 0x80007F00), *poke(handle + 0xC, 0xB0000000),
                   *call('osEPiRawStartDma', handle, direction, offset, destination, 4),
                   *log_word(destination), *log_v0(), *A.DONE,
                   'osEPiRawStartDma', A.jr(A.ra), A.nop]
        native = build(exe, cc, name, program, ['osEPiRawStartDma'])
        run = subprocess.run([str(native), '--rom', str(rom), '--dump', hex(LOG), '2'],
                             capture_output=True, text=True, timeout=30)
        lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        assert lines['stop'] == stop and run.returncode == (stop != 'exit'), (run.stdout, run.stderr)
        assert lines['words'] == ([0xCAFEF00D, 0] if stop == 'exit' else [0, 0]), lines
        assert lines['pi_dma'] == (stop == 'exit') and rom.read_bytes() == original, lines
    # A TLB-mapped destination is written at the physical page libultra's
    # osVirtualToPhysical names, as the PI does (ADR-0224).
    program = [*li(A.sp, 0x80007F00), *poke(handle + 0xC, 0xB0000000),
               *call('osMapTLB', 0, 0, 0xE0200000, 0x6000, 0xFFFFFFFF, 0xFFFFFFFF),
               *call('osEPiRawStartDma', handle, 0, 0x40, 0xE0200000, 4),
               *log_word(0x80006000), *log_v0(), *A.DONE,
               'osMapTLB', A.jr(A.ra), A.nop, 'osEPiRawStartDma', A.jr(A.ra), A.nop]
    native = build(exe, cc, 'raw_pi_tlb', program, ['osMapTLB', 'osEPiRawStartDma'])
    run = subprocess.run([str(native), '--rom', str(rom), '--dump', hex(LOG), '2'],
                         capture_output=True, text=True, timeout=30)
    lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    assert lines['stop'] == 'exit' and run.returncode == 0, (run.stdout, run.stderr)
    assert lines['words'] == [0xCAFEF00D, 0] and rom.read_bytes() == original, lines
    print('raw handle PI DMA: o32 stack size, cartridge bytes and return value; TLB-mapped destination; writes and out-of-range reads refused')


SP_BOOT_PROGRAM = [*li(A.sp, 0x80007F00), *(w for a in (0xA4000000, 0xA4000040, 0xA4001000, 0xA4001FFC)
                                            for w in log_word(a)), *A.DONE]


def sp_boot(exe, cc):
    """A native build starts DMEM and IMEM from the post-IPL state native.py
    captures in pinned ares (ADR-0195), not from the PIF's ROM copy."""
    rom = OUT / 'io.z64'
    state = bytes((i * 7 + 3) & 0xFF for i in range(0x2000))
    (OUT / 'sp_boot.h').write_text('static const u8 plaid_sp_boot[0x2000] = {' + ','.join(map(str, state)) + '};\n')
    native = build(exe, cc, 'sp_boot', SP_BOOT_PROGRAM, [], ['-DPLAID_SP_BOOT="sp_boot.h"'])
    run = subprocess.run([str(native), '--rom', str(rom), '--dump', hex(LOG), '4'],
                         capture_output=True, text=True, timeout=30)
    lines = {k: v for line in run.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    words = [int.from_bytes(state[o:o + 4], 'big') for o in (0, 0x40, 0x1000, 0x1FFC)]
    assert run.returncode == 0 and lines.get('stop') == 'exit', (run.returncode, run.stdout, run.stderr)
    assert lines['words'] == words, [hex(w) for w in lines['words']]
    print('SP boot: DMEM and IMEM start from the declared post-IPL state, not ROM 0x40-0xfff')


def tlb_unmap(exe, cc):
    names = ['osMapTLB', 'osUnmapTLB', 'osVirtualToPhysical']
    program = [*li(A.sp, 0x80007F00),
               *call('osMapTLB', 5, 0, 0x00400000, 0x4000, 0xFFFFFFFF, 0xFFFFFFFF),
               *call('osMapTLB', 6, 0, 0x00600000, 0x8000, 0xFFFFFFFF, 0xFFFFFFFF),
               *call('osVirtualToPhysical', 0x00400020), *log_v0(),
               *call('osUnmapTLB', 5),
               *call('osVirtualToPhysical', 0x00400020), *log_v0(),
               *call('osVirtualToPhysical', 0x00600020), *log_v0(), *A.DONE]
    for name in names:
        program += [name, A.jr(A.ra), A.nop]
    native = build(exe, cc, 'tlb_unmap', program, names)
    result = subprocess.run([str(native), '--dump', hex(LOG), '3'], capture_output=True, text=True, timeout=30)
    lines = {k: v for line in result.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
    assert result.returncode == 0 and lines.get('words') == [0x4020, 0xFFFFFFFF, 0x8020], (result.stdout, result.stderr)
    print('SDK TLB unmap: only the indexed mapping is invalidated; an independent mapping survives')

    effects = OUT / ('tlb-register-effects.exe' if os.name == 'nt' else 'tlb-register-effects')
    subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                    '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="tlb_unmap.c"', '-I', str(OUT),
                    str(ROOT / 'runtime/test_tlb_register_effects.c'), '-pthread', '-o', str(effects)], check=True)
    subprocess.run([str(effects)], check=True, timeout=30)


def build(exe, cc, name, program, runtime, extra=(), status_globals=None, fr0=False, data_bindings=None, address_taken=False, residual_dispatch=False):
    (OUT / f'{name}.bin').write_bytes(A.assemble(program))
    labels = A.label_pcs(program)
    decl = dict(format='plaid-runtime-functions-v0', source='runtime test declaration',
                functions=[dict(entry=hex(labels[n]), name=n, callbacks=['a2'] if n == 'osCreateThread' else [])
                           for n in runtime])
    for function in decl['functions']:
        if status_globals and function['name'] in status_globals:
            function['status_global'] = hex(status_globals[function['name']])
        if data_bindings and function['name'] in data_bindings:
            function['data_bindings'] = {k: hex(v) for k, v in data_bindings[function['name']].items()}
    (OUT / f'{name}.runtime.json').write_text(json.dumps(decl))
    subprocess.run([str(exe), 'lower-c', str(OUT / f'{name}.bin'), hex(A.BASE), hex(A.BASE), hex(A.EXIT),
                    str(OUT / f'{name}.c'), str(OUT / f'{name}.runtime.json'), *(['--fr0'] if fr0 else []), *(['--address-taken'] if address_taken else []),
                    *(['--residual-dispatch'] if residual_dispatch else [])], check=True)
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
    assert lines['stub_screen'] == SCREEN, (lines['stub_screen'], SCREEN)
    # pad 1: A|START (the later R press is not yet due), stick 16, -16; pad 2: errno 8 (absent)
    assert lines['words'] == [0x900010F0, 0, 0x00000800], [hex(w) for w in lines['words']]
    print('renderer bridge: VI registers as the guest wrote them, graphics task addresses and big-endian RAM, '
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
    import test_interrupts
    test_interrupts.run(exe, cc, sys.modules[__name__])
    import test_status
    test_status.run(exe, cc, sys.modules[__name__])
    import test_sdk_dispatch
    test_sdk_dispatch.run(exe, cc, sys.modules[__name__])
    import test_cache_writeback
    test_cache_writeback.run(exe, cc, sys.modules[__name__])
    import test_cache_ranges
    test_cache_ranges.run(exe, cc, sys.modules[__name__])
    import test_coroutines
    test_coroutines.run(exe, cc, sys.modules[__name__])
    import test_thread_lifecycle
    test_thread_lifecycle.run(exe, cc, sys.modules[__name__])
    import test_cache_ops
    test_cache_ops.run(exe, cc, sys.modules[__name__])
    import test_controller_policy
    test_controller_policy.run(exe, cc, sys.modules[__name__])
    import test_vi_dp
    test_vi_dp.run(exe, cc, sys.modules[__name__])
    import test_joybus
    test_joybus.run(exe, cc, sys.modules[__name__])
    import test_si_order
    test_si_order.run(exe, cc, sys.modules[__name__])
    graphics_bridge(exe, cc)
    import test_gfx_readback
    test_gfx_readback.run(exe, cc, sys.modules[__name__])
    save_file(exe, cc)
    rsp_tasks(exe, cc)
    import test_rsp_dpc
    test_rsp_dpc.run(exe, cc, sys.modules[__name__])
    import test_rsp_rom
    test_rsp_rom.run(exe, cc, sys.modules[__name__])
    rsp_state_abi(exe, cc)
    rsp_completion(exe, cc)
    rsp_graphics(exe, cc)
    import test_rsp_dirty
    test_rsp_dirty.run(exe, cc, sys.modules[__name__])
    import test_rsp_vi
    test_rsp_vi.run(exe, cc, sys.modules[__name__])
    audio_dma(exe, cc)
    rcp_io(exe, cc)
    sp_boot(exe, cc)
    import test_boot_ram
    test_boot_ram.run(exe, cc, sys.modules[__name__])
    import test_boot_entryhi
    test_boot_entryhi.run(exe, cc, sys.modules[__name__])
    raw_pi_dma(exe, cc)
    import test_pi_manager
    test_pi_manager.run(exe, cc, sys.modules[__name__])
    import test_pi_bus
    test_pi_bus.run(exe, cc, sys.modules[__name__])
    import test_raw_pi
    test_raw_pi.run(exe, cc, sys.modules[__name__])
    from test_overlays import main as overlay_verifiers
    overlay_verifiers()
    from test_text_writes import main as text_write_contracts
    text_write_contracts()
    from test_heap_overlays import main as heap_contracts
    heap_contracts()
    from test_slots import main as slot_contracts
    slot_contracts()
    from test_slot_data import main as slot_data_contracts
    slot_data_contracts()
    from test_table_base import main as table_base_contracts
    table_base_contracts()
    from test_branch_paths import main as branch_path_contracts
    branch_path_contracts()
    tlb_unmap(exe, cc)
    from test_cop0 import main as cop0_contracts
    cop0_contracts()
    from test_eret import main as eret_contracts
    eret_contracts()
    from test_fr import main as fr_contracts
    fr_contracts()
    from test_dynamic_fr import main as dynamic_fr_contracts
    dynamic_fr_contracts()
    from test_call_fr import main as call_fr_contracts
    call_fr_contracts()
    from test_tlb_execution import main as tlb_execution_contracts
    tlb_execution_contracts()
    from test_indexed_dispatch import main as indexed_dispatch_contracts
    indexed_dispatch_contracts()
    from test_residual_dispatch import main as residual_dispatch_contracts
    residual_dispatch_contracts()
    from test_rom_pointer_roots import main as rom_pointer_root_contracts
    rom_pointer_root_contracts()
    from test_pc_link_roots import main as pc_link_root_contracts
    pc_link_root_contracts()
    from test_indexed_slot_calls import main as indexed_slot_call_contracts
    indexed_slot_call_contracts()
    from test_boot_execution import main as boot_execution_contracts
    boot_execution_contracts()
    from test_replayed_data import main as replayed_data_contracts
    replayed_data_contracts()
    subprocess.run([sys.executable, str(ROOT / 'scripts/test_ares_boot.py')], check=True)
    dpc = OUT / 'dpc-contract.exe'
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                    '-I', str(ROOT / 'crates/plaid-lower/src'), str(ROOT / 'runtime/test_dpc.c'), '-o', str(dpc)], check=True)
    subprocess.run([str(dpc)], check=True, timeout=30)


if __name__ == '__main__':
    sys.exit(main())
