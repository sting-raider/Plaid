"""Retraces advance during synchronous native RSP work without scheduling the CPU."""
import json
import os
import subprocess


def run(exe, cc, T):
    A, V, out = T.A, T.V, T.OUT
    queue, buffer, result = 0x80002000, 0x80002100, 0x80003000
    commands = [0x30000000, 0x11223344] * 10
    code = [w for i, value in enumerate(commands) for w in [*T.li(A.t0, value), A.sw(A.t0, i * 4, A.zero)]]
    code += [A.addiu(A.t0, A.zero, 2), V.mtc0(A.t0, 11), V.mtc0(A.zero, 8)]
    for end in range(8, 81, 8):
        code += [A.addiu(A.t0, A.zero, end), V.mtc0(A.t0, 9)]
    code += [V.BREAK]
    words = T.rsp_words(code, 0)
    task = [1, 0, T.BOOT, len(words) * 4] + [0] * 12
    task[12] = T.DL
    names = ['osCreateMesgQueue', 'osSetEventMesg', 'osSpTaskLoad', 'osSpTaskStartGo', 'osRecvMesg']
    program = [*T.li(A.sp, 0x80007f00), *T.poke(0xa4400000, 2),
               *T.poke(T.DL, commands[0]), *T.poke(T.DL + 4, commands[1]),
               *[w for i, value in enumerate(words) for w in T.poke(T.BOOT + i * 4, value)],
               *[w for i, value in enumerate(task) for w in T.poke(T.RTASK + i * 4, value)],
               *T.call('osCreateMesgQueue', queue, buffer, 16),
               *T.call('osSetEventMesg', 4, queue, 0x44),
               *T.call('osSetEventMesg', 7, queue, 0x77),
               *T.call('osSetEventMesg', 9, queue, 0x99),
               *T.call('osSpTaskLoad', T.RTASK), *T.call('osSpTaskStartGo', T.RTASK),
               # This runtime boundary delivers pending events after its operation.
               *T.call('osRecvMesg', queue, result + 48, 0)]
    for i in range(12):
        program += T.call('osRecvMesg', queue, result + i * 4, 0)
    program += A.DONE
    for name in names:
        program += [name, A.jr(A.ra), A.nop]
    image, lowered, registry, stub = [out / ('rsp-vi-code.' + suffix) for suffix in ('bin', 'c', 'registry.c', 'stub.c')]
    rom = out / 'rsp-vi.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0x1000))
    image.write_bytes(b''.join(w.to_bytes(4, 'big') for w in words).ljust(4096, b'\0'))
    subprocess.run([str(exe), 'lower-rsp', str(image), '0', '0x1000', '0', 'vi_task', str(lowered), '--raw'],
                   check=True, capture_output=True)
    registry.write_text('#include "rsp_state.h"\nextern const plaid_rsp_text plaid_rsp_text_vi_task;\n'
                        'const plaid_rsp_text *const plaid_rsp_texts[] = {&plaid_rsp_text_vi_task, 0};\n')
    source = T.GFX_STUB
    source = source.replace('int plaid_gfx_native_rsp(', 'static int active, retraces;\nextern void plaid_test_advance(void);\nint plaid_gfx_native_rsp(')
    source = source.replace('  int result = work(context);', '  active = 1; int result = work(context); active = 0;\n'
                            '  printf("{\\"rsp_retraces\\":%d}\\n", retraces);')
    source = source.replace('  uint32_t i, pages = 0;', '  uint32_t i, pages = 0;\n'
        # The VI source may post events, but must not deliver them into guest RAM here.
        '  if (ram[0x2008] || ram[0x2009] || ram[0x200a] || ram[0x200b]) return 1;\n'
        '  plaid_test_advance();')
    source = source.replace('  if (once++) return;', '  if (active) retraces++;\n  if (once++) return;')
    stub.write_text(source)
    # Generate the CPU unit without linking the clock stub yet.
    T.build(exe, cc, 'rsp-vi', program, names)
    source = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    begin = source.index('static u64 now_ns(void) {')
    end = source.index('\n}', begin) + 2
    source = source[:begin] + ('static u64 test_now;\nvoid plaid_test_advance(void) { test_now += VI_PERIOD_NS; }\n'
                              'static u64 now_ns(void) { return test_now; }') + source[end:]
    for mutant in (False, True):
        text = source
        if mutant:
            text = text.replace('  if (rsp_graphics) vi_poll(now_ns());\n  u64 data', '  u64 data')
            text = text.replace('  if (rsp_graphics) vi_poll(now_ns());\n  return result;', '  return result;')
        runtime = out / 'rsp-vi-runtime.c'
        runtime.write_text(text)
        binary = out / ('rsp-vi-check.exe' if os.name == 'nt' else 'rsp-vi-check')
        subprocess.run([cc, '-O2', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS', '-DPLAID_RSP', '-DPLAID_RT64',
            '-DPLAID_LOWERED="rsp-vi.c"', '-I', str(out), '-I', str(T.ROOT / 'runtime'),
            '-I', str(T.ROOT / 'crates/plaid-lower/src'), str(runtime), str(lowered), str(registry), str(stub),
            '-pthread', '-o', str(binary)], check=True)
        run = subprocess.run([str(binary), '--rsp-gfx', '--rom', str(rom), '--stop-at', 'none',
                              '--dump', hex(result), '12'], capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in run.stdout.splitlines() if line.startswith('{')]
        assert run.returncode == 0, (run.stdout, run.stderr)
        assert next(v['rsp_retraces'] for v in rows if 'rsp_retraces' in v) == (0 if mutant else 10), rows
        if not mutant:
            assert next(v['words'] for v in rows if 'words' in v) == [0x44] + [0x77] * 10 + [0x99], rows
            assert next(v for v in rows if 'stop' in v)['vi'] == 10, rows
            assert [v['stub_rdp'] for v in rows if 'stub_rdp' in v] == [
                [8, 2048 if i == 0 else 0, *commands[:2]] for i in range(10)], rows
    print('native RSP VI: 10 exact-clock retraces during work; CPU RAM/event delivery deferred; SP/VI/DP '
          'order, command bytes and dirty pages preserved; removed-poll mutation killed')
