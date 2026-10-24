"""Non-graphics task boots use the CPU's synchronous DPC bus too."""
import json
import subprocess


def run(exe, cc, T):
    A, V, out = T.A, T.V, T.OUT
    code = [w for reg in range(8, 16)
            for w in (V.mfc0(A.t0, reg), A.sw(A.t0, 4 * (reg - 8), A.zero))]
    code += [A.addiu(A.t0, A.zero, 0x1300), V.mtc0(A.t0, 8),
             A.addiu(A.t0, A.zero, 0x1340), V.mtc0(A.t0, 9),
             A.addiu(A.t0, A.zero, 4), V.mtc0(A.t0, 11),
             *T.li(A.t0, T.OUTB & 0x1FFFFFFF), V.mtc0(A.t0, 1),
             V.mtc0(A.zero, 0), A.addiu(A.t0, A.zero, 31), V.mtc0(A.t0, 3), V.BREAK]
    words = T.rsp_words(code, 0)
    task = [4, 0, T.BOOT, 4 * len(words)] + [0] * 12
    runtime = ['osSpTaskLoad', 'osSpTaskStartGo']
    program = [*T.li(A.sp, 0x80007F00),
               *[w for i, v in enumerate(words) for w in T.poke(T.BOOT + 4 * i, v)],
               *[w for i, v in enumerate(task) for w in T.poke(T.RTASK + 4 * i, v)],
               *T.poke(0xA4100000, 0x1200), *T.poke(0xA4100004, 0x1240),
               *T.poke(0xA410000C, 8),
               *T.call('osSpTaskLoad', T.RTASK), *T.call('osSpTaskStartGo', T.RTASK),
               *T.li(A.t0, 0xA4100008), A.lw(A.t1, 0, A.t0),
               *T.li(A.t2, T.OUTB + 32), A.sw(A.t1, 0, A.t2),
               A.lw(A.t1, 4, A.t0), A.sw(A.t1, 4, A.t2), *A.DONE]
    for name in runtime:
        program += [name, A.jr(A.ra), A.nop]
    image, lowered, registry = [out / ('rsp-dpc-code.' + suffix) for suffix in ('bin', 'c', 'registry.c')]
    image.write_bytes(b''.join(w.to_bytes(4, 'big') for w in words).ljust(4096, b'\0'))
    subprocess.run([str(exe), 'lower-rsp', str(image), '0', '0x1000', '0', 'dpc_task',
                    str(lowered), '--raw'], check=True, capture_output=True)
    registry.write_text('#include "rsp_state.h"\nextern const plaid_rsp_text plaid_rsp_text_dpc_task;\n'
                        'const plaid_rsp_text *const plaid_rsp_texts[] = {&plaid_rsp_text_dpc_task, 0};\n')
    native = T.build(exe, cc, 'rsp-dpc', program, runtime,
                     ['-DPLAID_RSP', '-I', str(T.ROOT / 'crates/plaid-lower/src'), str(lowered), str(registry)])
    result = subprocess.run([str(native), '--dump', hex(T.OUTB), '10'],
                            capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 0, (result.stdout, result.stderr)
    actual = next(row['words'] for row in rows if 'words' in row)
    assert 0 < actual[4] <= 0xFFFFFF, actual
    assert actual[:4] + actual[5:] == [
        0x1200, 0x1240, 0x1240, 0x82, 0, 0, 0, 0x1340, 0x80], rows
    assert next(row for row in rows if 'stop' in row)['audio_tasks'] == 1
    print('non-graphics RSP DPC: shared CPU register state, idle counters, writes and DMA output')
