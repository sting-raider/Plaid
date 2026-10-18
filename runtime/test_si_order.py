"""SI DMA ordering versus pinned ares: the cache operations after an SI start precede the transfer."""
import json
import hashlib
import os
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    cache = lambda op, base, offset: 47 << 26 | base << 21 | op << 16 | offset
    wait = lambda label: [label, A.lw(A.t3, 24, A.t2), A.andi(A.t3, A.t3, 1), A.bne(A.t3, A.zero, label), A.nop]
    # port 2 has no device in either model, so only DMA/cache ordering is compared
    request = [0x00010300, 0xfffffffe] + [0] * 13 + [1]
    program = [*T.li(A.sp, 0x80007f00), *T.li(A.gp, 0x80001000), *T.li(A.t0, 0x80001100), *T.li(A.t2, 0xa4800000)]
    for n, word in enumerate(request):
        program += [*T.li(A.t1, word), A.sw(A.t1, 4 * n, A.t0)]
    program += [*T.call('osWritebackDCache', 0x80001100, 64), *T.li(A.t2, 0xa4800000)]
    program += [*T.li(A.t1, 0x1100), A.sw(A.t1, 0, A.t2), *T.li(A.t1, 0x1fc007c0), A.sw(A.t1, 16, A.t2)]
    program += [*wait('write_busy'), A.sw(A.zero, 24, A.t2)]
    program += [*T.li(A.t1, 0xffffffff)] + [A.sw(A.t1, 4 * n, A.t0) for n in range(16)]  # dirty fill
    program += [*T.li(A.t1, 0x1100), A.sw(A.t1, 0, A.t2), *T.li(A.t1, 0x1fc007c0), A.sw(A.t1, 4, A.t2)]
    program += [*T.call('osInvalDCache', 0x80001100, 64), *T.li(A.t0, 0x80001100), *T.li(A.t2, 0xa4800000)]  # after the start
    program += [*wait('read_busy'), A.sw(A.zero, 24, A.t2)]
    for n in range(16):
        program += [A.lw(A.t1, 4 * n, A.t0), A.sw(A.t1, 4 * n, A.gp)]
    # libultra-shaped bodies for ares: hit writeback (25) and hit invalidate (17) by line
    for name, op in (('osWritebackDCache', 25), ('osInvalDCache', 17)):
        program += [name, name + '_line', cache(op, A.a0, 0), A.addiu(A.a1, A.a1, -16),
                    A.bgtz(A.a1, name + '_line'), A.addiu(A.a0, A.a0, 16), A.jr(A.ra), A.nop]
    program = program[:program.index('osWritebackDCache')] + [*A.DONE] + program[program.index('osWritebackDCache'):]
    native = T.build(exe, cc, 'si-order', program, ['osWritebackDCache', 'osInvalDCache'])
    actual = subprocess.run([str(native), '--dump', '0x80001000', '64'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in actual.stdout.splitlines() if line.startswith('{')]
    stop = next(row for row in rows if 'stop' in row)
    assert actual.returncode == 0 and stop['fault'] == 0 and stop['stop'] == 'exit', (actual.stdout, actual.stderr)
    memory = next(row['words'] for row in rows if 'dump' in row)
    oracle = T.ROOT / 'target/native-slice/oracle/oracle'
    metadata = json.loads((oracle.parent / 'build.json').read_text())
    assert metadata['revision'] == A.builder().REV
    for key, source in [('driver', '096-native-slice'), ('fixture_driver', '003-ares-oracle')]:
        assert metadata[key] == hashlib.sha256((T.ROOT / f'spikes/{source}/driver.cpp').read_bytes()).hexdigest()
    args = [str(oracle), str(out / 'si-order.bin'), hex(A.EXIT)]
    if os.name == 'nt':
        def linux(p): return subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', str(p)], text=True).strip()
        args = ['wsl', '-d', 'Ubuntu', '--exec', linux(oracle), linux(out / 'si-order.bin'), hex(A.EXIT)]
    reference = subprocess.run(args, capture_output=True, text=True, timeout=120)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    expected = json.loads(reference.stdout)
    assert expected['pc'] == A.EXIT and expected['ram'] == memory, ([hex(w) for w in expected['ram']], [hex(w) for w in memory])
    assert memory[0] == 0x00018300 and memory[1] == 0xfffffffe, [hex(w) for w in memory[:2]]
    print('SI order: a cache invalidate after the SI start precedes the transfer; absent-port reply and RAM match pinned ares')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
