"""Native RSP DPC writes retain sparse DMA dirtiness; CPU writes invalidate RAM."""
import json
import os
import subprocess


def run(exe, cc, T):
    A, V, out = T.A, T.V, T.OUT
    commands = [0x11223344, 0x55667788, 0x99aabbcc, 0xddeeff00, 0x12345678, 0x90abcdef]
    code = [w for i, value in enumerate(commands) for w in [*T.li(A.t0, value), A.sw(A.t0, i * 4, A.zero)]]
    code += [A.addiu(A.t0, A.zero, 2), V.mtc0(A.t0, 11), V.mtc0(A.zero, 8),
             A.addiu(A.t0, A.zero, 8), V.mtc0(A.t0, 9),
             A.addiu(A.t0, A.zero, 16), V.mtc0(A.t0, 9),
             # DMA changes exactly page 4 before the third submission.
             V.mtc0(A.zero, 0), A.addiu(A.t0, A.zero, 0x4000), V.mtc0(A.t0, 1),
             A.addiu(A.t0, A.zero, 7), V.mtc0(A.t0, 3),
             A.addiu(A.t0, A.zero, 24), V.mtc0(A.t0, 9), V.BREAK]
    words = T.rsp_words(code, 0)
    task = [1, 0, T.BOOT, len(words) * 4] + [0] * 12
    task[12] = T.DL
    names = ['osSpTaskLoad', 'osSpTaskStartGo']
    program = [*T.li(A.sp, 0x80007f00),
               *[w for i, value in enumerate(words) for w in T.poke(T.BOOT + i * 4, value)],
               *[w for i, value in enumerate(task) for w in T.poke(T.RTASK + i * 4, value)],
               *T.call('osSpTaskLoad', T.RTASK), *T.call('osSpTaskStartGo', T.RTASK),
               # A subsequent CPU submission must still see arbitrary CPU texture writes.
               *T.poke(T.DL, 0xdeadbeef), *T.poke(T.DL + 4, 0x76543210),
               *T.poke(0xa410000c, 1), *T.poke(0xa4100000, T.DL & 0x1fffffff),
               *T.poke(0xa4100004, (T.DL & 0x1fffffff) + 8), *A.DONE]
    for name in names:
        program += [name, A.jr(A.ra), A.nop]
    image, lowered, registry, stub = [out / ('rsp-dirty-code.' + suffix) for suffix in ('bin', 'c', 'registry.c', 'stub.c')]
    image.write_bytes(b''.join(w.to_bytes(4, 'big') for w in words).ljust(4096, b'\0'))
    subprocess.run([str(exe), 'lower-rsp', str(image), '0', '0x1000', '0', 'dirty', str(lowered), '--raw'],
                   check=True, capture_output=True)
    registry.write_text('#include "rsp_state.h"\nextern const plaid_rsp_text plaid_rsp_text_dirty;\n'
                        'const plaid_rsp_text *const plaid_rsp_texts[] = {&plaid_rsp_text_dirty, 0};\n')
    stub.write_text(T.GFX_STUB.replace('  printf("{\\"stub_rdp\\":[%u,%u", size, pages);',
        '  if (pages == 1 && !dirty[4]) return 1;\n  printf("{\\"stub_rdp\\":[%u,%u", size, pages);'))
    native = T.build(exe, cc, 'rsp-dirty', program, names,
        ['-DPLAID_RSP', '-DPLAID_RT64', '-I', str(T.ROOT / 'crates/plaid-lower/src'), str(lowered), str(registry), str(stub)])
    result = subprocess.run([str(native), '--rsp-gfx', '--rom', str(out / 'stub.z64'), '--stop-at', 'none',
                             '--dump', '0x80004000', '2'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert [v['stub_rdp'] for v in rows if 'stub_rdp' in v] == [
        [8, 2048, *commands[:2]], [8, 0, *commands[2:4]], [8, 1, *commands[4:]],
        [8, 2048, 0xdeadbeef, 0x76543210]], rows
    assert next(v['words'] for v in rows if 'words' in v) == commands[:2], rows
    stop = next(v for v in rows if 'stop' in v)
    assert stop['stop'] == 'exit' and stop['fault'] == 0, stop
    # Restoring the unconditional CPU invalidation must lose the sparse census.
    source = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    guard = 'write && !rsp_executing'
    assert source.count(guard) == 1
    mutant = out / 'rsp-dirty-runtime.c'
    mutant.write_text(source.replace(guard, 'write'))
    binary = out / ('rsp-dirty-mutant.exe' if os.name == 'nt' else 'rsp-dirty-mutant')
    subprocess.run([cc, '-O2', '-std=gnu11', '-w', '-DPLAID_SAFEPOINTS', '-DPLAID_RSP', '-DPLAID_RT64',
        '-DPLAID_LOWERED="rsp-dirty.c"', '-I', str(out), '-I', str(T.ROOT / 'runtime'),
        '-I', str(T.ROOT / 'crates/plaid-lower/src'), str(mutant), str(lowered), str(registry), str(stub),
        '-pthread', '-o', str(binary)], check=True)
    changed = subprocess.run([str(binary), '--rsp-gfx', '--rom', str(out / 'stub.z64'), '--stop-at', 'none'],
                             capture_output=True, text=True, timeout=30)
    assert changed.returncode == 0, changed.stderr
    rows = [json.loads(line) for line in changed.stdout.splitlines() if line.startswith('{')]
    assert [v['stub_rdp'][1] for v in rows if 'stub_rdp' in v] == [2048] * 4, rows
    print('RSP dirty pages: task entry/full, repeated DPC/clean, DMA/exact page, subsequent CPU/full; command bytes and RAM preserved')
