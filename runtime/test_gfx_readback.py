"""RCP framebuffer writes reach guest RAM without breaking D-cache semantics."""
import json
import subprocess


STUB = r'''#include <stdint.h>
#include <stdio.h>
#include <string.h>
int plaid_gfx_native_rsp(int (*work)(void *), void *context) { return work(context); }
int plaid_gfx_open(const uint8_t *h) { (void)h; return 0; }
int plaid_gfx_task(const uint8_t *ram, uint32_t ucode, uint32_t data, uint32_t dl,
                   int (*writeback)(void *, uint32_t, uint32_t, const uint8_t *), void *context) {
#if READBACK_MODE != 2
  static const uint8_t changed[4] = {0xaa, 0xbb, 0xcc, 0xdd};
#endif
#if READBACK_MODE == 2
  static const uint8_t line[16] = {0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97,
                                  0x98, 0x99, 0x9a, 0x9b, 0x9c, 0x9d, 0x9e, 0x9f};
#endif
  int a = -9, b = -9, protected_unchanged = -1;
  (void)ucode; (void)data; (void)dl;
#if READBACK_MODE == 0
  uint8_t same[4];
  memcpy(same, ram + 0x4804, sizeof same);
  a = writeback(context, 0x4800, 4, changed);
  b = writeback(context, 0x4804, 4, same); /* same-value transfer */
#elif READBACK_MODE == 1
  a = writeback(context, 0x4820, 4, changed); /* partial line cannot heal line_lost */
#elif READBACK_MODE == 2
  a = writeback(context, 0x4820, 16, line); /* full line repairs line_lost */
#elif READBACK_MODE == 3
  {
    uint8_t before[4];
    memcpy(before, ram + LIVE_TEXT, sizeof before);
    a = writeback(context, LIVE_TEXT, 4, changed); /* text the caller still runs is protected */
    protected_unchanged = memcmp(before, ram + LIVE_TEXT, sizeof before) == 0;
  }
#elif READBACK_MODE == 4
  a = writeback(context, 0x7ffffe, 4, changed); /* crosses the 8 MiB RAM boundary */
#endif
  printf("{\"writeback\":[%d,%d],\"protected_unchanged\":%d}\n", a, b, protected_unchanged);
  return (a != 0 || b > 0) ? 1 : 0;
}
int plaid_gfx_rdp(const uint8_t *ram, const uint8_t *commands, uint32_t size, const uint8_t *dirty,
                  int (*writeback)(void *, uint32_t, uint32_t, const uint8_t *), void *context) {
  (void)ram; (void)commands; (void)size; (void)dirty; (void)writeback; (void)context; return 0;
}
void plaid_gfx_screen(const uint32_t *regs) { (void)regs; }
int plaid_gfx_closed(void) { return 0; }
uint32_t plaid_gfx_input(void) { return 0; }
void plaid_audio_play(const uint8_t *samples, uint32_t bytes, uint32_t rate) {
  (void)samples; (void)bytes; (void)rate;
}
'''


def _program(T, mode):
    A = T.A
    program = [*T.li(A.sp, 0x80007F00), *T.poke(T.INDEX, 0)]
    if mode == 0:
        program += [*T.poke(0xA0004800, 0x11223344), *T.poke(0xA0004804, 0x55667788)]
        program += T.log_word(0x80004800)  # clean cached line before the RCP write
    elif mode in (1, 2):
        for offset, word in enumerate((0x01020304, 0x11121314, 0x21222324, 0x31323334)):
            program += T.poke(0xA0004820 + 4 * offset, word)
        program += [*T.poke(0x80004820, 0xAABBCCDD)]  # dirty the line
        program += T.call('osInvalDCache', 0x80004820, 16)  # discarded dirty line is lost

    program += [*T.poke(T.TASK, 1), *T.poke(T.TASK + 0x10, 0x80005000),
                *T.poke(T.TASK + 0x18, 0x80005800), *T.poke(T.TASK + 0x30, T.DL),
                *T.poke(T.DL, 0xB8000000), *T.call('osSpTaskStartGo', T.TASK)]
    if mode == 0:
        program += T.log_word(0x80004800)  # cache still has pre-write value
        program += T.log_word(0xA0004800)  # uncached alias sees framebuffer result
        program += T.log_word(0xA0004804)  # adjacent word remained unchanged
        program += T.log_word(0x80004804)  # same-value transfer preserved cached view
        program += [*T.call('osInvalDCache', 0x80004800, 16)]
        program += T.log_word(0x80004800)  # clean-line invalidation refills from RCP result
    elif mode in (1, 2):
        count = 1 if mode == 1 else 4
        for i in range(count):
            program += T.log_word(0xA0004820 + 4 * i)
    live = 4 * sum(not isinstance(w, str) for w in program)  # DONE runs after the task call
    program += A.DONE
    for name in ('osSpTaskStartGo', 'osInvalDCache'):
        if name == 'osInvalDCache' and mode not in (0, 1, 2):
            continue
        program += [name, A.jr(A.ra), A.nop]
    return program, live


def _run(exe, cc, T, mode, name, dump_words):
    stub = T.OUT / f'{name}-stub.c'
    stub.write_text(STUB)
    program, live = _program(T, mode)
    native = T.build(exe, cc, name, program,
                     ['osSpTaskStartGo'] + (['osInvalDCache'] if mode in (0, 1, 2) else []),
                     ['-DPLAID_RT64', f'-DREADBACK_MODE={mode}', f'-DLIVE_TEXT={live}u', str(stub)])
    rom = T.OUT / 'gfx-readback.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0xFFC))
    dump_at = hex(0x80000000 + live) if mode == 3 else ('0x807ffffc' if mode == 4 else hex(T.LOG))
    run = subprocess.run([str(native), '--rom', str(rom), '--stop-at', 'none', '--dump', dump_at, str(dump_words)],
                         capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
    status = next((row for row in rows if 'writeback' in row), None)
    stop = next((row for row in rows if 'stop' in row), {})
    dump = next((row['words'] for row in rows if 'dump' in row), None)
    return run, status, stop, dump, live


def run(exe, cc, T):
    run, status, stop, words, live = _run(exe, cc, T, 0, 'gfx-readback', 6)
    assert run.returncode == 0 and stop.get('stop') == 'exit' and stop.get('fault') == 0, (
        run.returncode, run.stdout, run.stderr)
    assert status == {'writeback': [0, 0], 'protected_unchanged': -1}, status
    assert words == [0x11223344, 0x11223344, 0xAABBCCDD, 0x55667788, 0x55667788, 0xAABBCCDD], words

    run, status, stop, words, live = _run(exe, cc, T, 1, 'gfx-readback-partial', 1)
    assert run.returncode == 1 and stop.get('stop') == 'guest fault' and stop.get('fault') == 4, (
        run.returncode, run.stdout, run.stderr)
    assert status == {'writeback': [0, -9], 'protected_unchanged': -1}, status

    run, status, stop, words, live = _run(exe, cc, T, 2, 'gfx-readback-full', 4)
    assert run.returncode == 0 and stop.get('stop') == 'exit' and stop.get('fault') == 0, (
        run.returncode, run.stdout, run.stderr)
    assert status == {'writeback': [0, -9], 'protected_unchanged': -1}, status
    assert words == [0x90919293, 0x94959697, 0x98999A9B, 0x9C9D9E9F], words

    run, status, stop, words, live = _run(exe, cc, T, 3, 'gfx-readback-protected', 1)
    assert run.returncode == 1 and stop.get('stop') == 'guest fault' and stop.get('fault') == 2, (
        run.returncode, run.stdout, run.stderr)
    assert status == {'writeback': [1, -9], 'protected_unchanged': 1}, status
    assert words == [int.from_bytes((T.OUT / 'gfx-readback-protected.bin').read_bytes()[live:live + 4], 'big')], words

    run, status, stop, words, live = _run(exe, cc, T, 4, 'gfx-readback-range', 1)
    assert run.returncode == 1 and stop.get('stop') == 'guest fault' and stop.get('fault') == 1, (
        run.returncode, run.stdout, run.stderr)
    assert status == {'writeback': [1, -9], 'protected_unchanged': -1}, status
    assert words == [0], words  # the last in-range word was not partially overwritten
    print('graphics RAM writeback: endian bytes, cache invalidate/refill and aliases, '
          'same-value/guards, partial/full line_lost, protected-text and range refusals')
