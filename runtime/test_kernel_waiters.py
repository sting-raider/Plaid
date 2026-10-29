"""Guest waiter lists and the SDK callee-saved context at native ABI yields."""
import json
import os
import subprocess
import sys


def run(exe, cc, T):
    A, out = T.A, T.OUT
    # Exercise publication on real host stacks, rather than only constructing
    # scheduler entries in the contract below.
    queue, tail, main, first, second = 0x80005000, 0x80004000, 0x80002000, 0x80002200, 0x80002400
    names = ['osCreateMesgQueue', 'osCreateThread', 'osStartThread', 'osRecvMesg', 'osSendMesg', 'osStopThread']
    observations = []
    def observe(address, value):
        offset = len(observations) * 4; observations.append(value)
        return [*T.li(A.t0, address), A.lw(A.t1, 0, A.t0), *T.li(A.t0, 0x80003000), A.sw(A.t1, offset, A.t0)]
    program = [*T.li(A.sp, 0x80007f00), *T.poke(tail, 0), *T.poke(tail + 4, 0xffffffff),
               *T.call('osCreateMesgQueue', queue, queue + 0x20, 1),
               *T.call('osCreateThread', main, 1, 'main', 0, 0x8000ff00, 10), *T.call('osStartThread', main), *A.DONE,
               'main', *observe(main + 0x10, 4 << 16),
               *T.call('osCreateThread', first, 2, 'wait', 0, 0x80017f00, 20), *T.call('osStartThread', first),
               *T.call('osCreateThread', second, 3, 'wait', 0, 0x8001ff00, 30), *T.call('osStartThread', second),
               *observe(queue, second), *observe(second, first), *observe(first, tail), *observe(first + 8, queue),
               *observe(first + 0x10, 8 << 16), *T.call('osSendMesg', queue, 7, 1),
               *observe(queue, first), *observe(second + 0x10, 1 << 16),
               *T.call('osSendMesg', queue, 8, 1), *observe(queue, tail), *observe(first + 0x10, 1 << 16), *A.DONE,
               'wait', *T.call('osRecvMesg', queue, 0, 1), *T.call('osStopThread', 0), *A.DONE]
    for name in names: program += [name, A.jr(A.ra), A.nop]
    native = T.build(exe, cc, 'kernel-waiter-threads', program, names,
                     data_bindings={'osCreateMesgQueue': {'__osThreadTail': tail}}, source_sizes={'osCreateMesgQueue': 8})
    result = subprocess.run([str(native), '--dump', '0x80003000', str(len(observations))], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert not result.returncode and next(row for row in rows if 'stop' in row)['fault'] == 0, (result.stdout, result.stderr)
    assert next(row for row in rows if 'dump' in row)['words'] == observations, rows
    T.build(exe, cc, 'waiter-fixture', list(A.DONE), [])
    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    contract = (T.ROOT / 'runtime/test_kernel_waiters.c').read_text()

    def compile(source, target):
        subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                        '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="waiter-fixture.c"', '-I', str(out),
                        '-I', str(T.ROOT / 'runtime'), str(source), '-pthread', '-o', str(target)], check=True)

    def invoke(binary, *args):
        return subprocess.run([str(binary), *args], capture_output=True, text=True, timeout=30)

    binary = out / 'kernel-waiters.exe'
    compile(T.ROOT / 'runtime/test_kernel_waiters.c', binary)
    result = invoke(binary)
    assert not result.returncode, (result.stdout, result.stderr)
    result = invoke(binary, 'refuse')
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 1 and next(row for row in rows if 'stop' in row)['fault'] == 2, rows
    assert next(row for row in rows if 'dump' in row)['words'] == [0x80004000], rows
    for mode, fault in [('fr', 12), ('cu1', 12), ('pinned', 2)]:
        result = invoke(binary, 'context-refuse', mode)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert result.returncode == 1 and next(row for row in rows if 'stop' in row)['fault'] == fault, rows
        unchanged = [0xa5a5a5a5] * (0x1b0 // 4); unchanged[0x18 // 4] = 1
        assert next(row for row in rows if 'dump' in row)['words'] == unchanged, mode

    # Independent architectural SD/SW/SDC1 operations, not SDK bytes or a host
    # implementation of save(). Compare untouched fields as well as stores.
    sys.path.insert(0, str(T.ROOT / 'scripts'))
    import ares_oracle
    oracle = ares_oracle.default()
    expected_contexts = []
    for fp in (0, 1):
        expected = []
        for start in (0, 64):
            program = [*T.li(A.t0, 0x2000ff00), 0x40886000, A.nop, A.nop]
            program += [w for offset in range(0, 0x1b0, 4) for w in T.poke(0x80002000 + offset, 0xa5a5a5a5)]
            program += T.poke(0x80002018, fp)
            for r in [*range(16, 24), *range(28, 32)]:
                program += [*T.poke(0x80003000, 0x12345678), *T.poke(0x80003004, r),
                            *T.li(A.t0, 0x80003000), A.ld(r, 0, A.t0)]
            program += T.li(A.t0, 0x80002000)
            for r, offset in [*[(r, 0x98 + (r - 16) * 8) for r in range(16, 24)],
                              *[(r, 0xe8 + (r - 28) * 8) for r in range(28, 32)]]:
                program += [A.sd(r, offset, A.t0)]
            program += [A.sw(A.ra, 0x11c, A.t0), *T.poke(0x80002118, 0x2000ff02), *T.poke(0x80002128, 0x15)]
            if fp:
                program += [*T.li(A.t1, 0x01800003), A.ctc1(A.t1, 31)]
                for r in range(20, 31, 2):
                    program += [*T.poke(0x80003000, 0x3ff00000), *T.poke(0x80003004, r),
                                *T.li(A.t0, 0x80003000), A.ldc1(r, 0, A.t0),
                                *T.li(A.t0, 0x80002000), A.sdc1(r, 0x180 + (r - 20) * 4, A.t0)]
                program += [0x4449f800, A.sw(A.t1, 0x12c, A.t0)]  # cfc1 t1,FCSR
            count = min(64, 0x1b0 // 4 - start)
            program += [*T.li(A.t0, 0x80002000 + start * 4), *T.li(A.t1, 0x80001000)]
            for i in range(count):
                program += [A.lw(A.t2, i * 4, A.t0), A.sw(A.t2, i * 4, A.t1)]
            program += A.DONE
            # Keep the large synthetic initialization clear of the oracle's
            # output slice and its fixed exit address.
            program = [A.j('body'), A.nop] + [A.nop] * (0x4000 // 4 - 2) + ['body'] + program
            labels = A.label_pcs(program); labels['exit'] = A.EXIT
            words, pc = [], A.BASE
            for item in program:
                if isinstance(item, str): continue
                words.append((item(pc, labels) if callable(item) else item) & 0xffffffff); pc += 4
            raw = out / 'kernel-context-reference.bin'
            raw.write_bytes(b''.join(word.to_bytes(4, 'big') for word in words))
            reference = subprocess.run([str(oracle), str(raw), hex(A.EXIT)], capture_output=True, text=True, timeout=60)
            assert not reference.returncode, (reference.stdout, reference.stderr)
            state = json.loads(reference.stdout)
            assert state['pc'] == A.EXIT and not any(state['ram'][count:]), state
            expected += state['ram'][:count]
        actual = invoke(binary, 'context', *(['fp'] if fp else []))
        assert not actual.returncode, (actual.stdout, actual.stderr)
        observed = json.loads(actual.stdout)['context']
        assert observed == expected, (fp, [(i, hex(a), hex(b)) for i, (a, b) in enumerate(zip(observed, expected)) if a != b])
        expected_contexts.append(expected)

    mutations = [
        ('priority', 't->pri > list[j - 1]->pri', 't->pri < list[j - 1]->pri', ()),
        ('removal', 'if (was_blocked) publish_waiters(t->wait_queue, t->wait_full);', '(void)was_blocked;', ()),
        ('preflight', 'for (i = 0; i < count; i++) kernel_write_check(list[i]->guest, 0x14);', '', ('refuse',)),
        ('epc', 'wr32(t->guest + 0x11c, (u32)t->r[31]);', '', ('context',)),
        ('fp-condition', 't->fcsr | t->fcc << 23', 't->fcsr', ('context', 'fp')),
        ('same-priority', 'if (t->pri == (s32)arg(1)) return 0;', '', ()),
        ('runnable-state', 'if (queue_tail_global && t->guest) wr16(t->guest + 0x10, 2);', '', ()),
    ]
    for name, before, after, args in mutations:
        assert before in runtime, name
        altered = out / f'waiter-{name}.runtime.c'; altered.write_text(runtime.replace(before, after))
        source = out / f'waiter-{name}.contract.c'
        source.write_text(contract.replace('#include "plaid_rt.c"', '#include "' + altered.as_posix() + '"'))
        mutant = out / f'waiter-{name}.exe'; compile(source, mutant)
        result = invoke(mutant, *args)
        if name == 'preflight':
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            assert next(row for row in rows if 'dump' in row)['words'] != [0x80004000], name
        elif name in ('epc', 'fp-condition'):
            assert result.returncode or json.loads(result.stdout)['context'] != expected_contexts[int(name == 'fp-condition')], name
        else:
            assert result.returncode, name
    print('PASS SDK waiter priority/FIFO, same-priority no-op, reprioritize, wake/stop/destroy and states, atomic refusal; callee-saved/FP context and untouched bytes match pinned ares; seven mutations')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug/plaid.exe', shutil.which('gcc'), T)
