"""Verified SDK calls dispatch saved contexts through the native scheduler."""
import json
import subprocess


def refused_entry(result, stop):
    assert result.returncode != 0 and stop['fault'] == 3 and stop['fault_pc'] == '8000f000', stop


def run(exe, cc, T):
    A = T.A
    mask, one, two = 0x80004000, 0x80002100, 0x80002300
    queue, buffer, slot = 0x80005000, 0x80005020, 0x80005040
    names = ['osCreateThread', 'osStartThread', 'osSetIntMask', '__osGetSR',
             'osCreateMesgQueue', 'osRecvMesg', 'osSendMesg', 'osGetThreadPri']
    saved = [*range(A.s0, A.s7 + 1), A.gp, A.fp, A.sp]
    initialize = lambda seed: [word for register in saved if register != A.sp
                               for word in T.li(register, seed + register)]
    observe = lambda offset: [*T.li(A.t0, T.LOG),
                              *[A.sw(register, offset + 4 * index, A.t0)
                                for index, register in enumerate(saved)]]

    def status():
        return [*T.call('__osGetSR'), *T.li(A.t4, T.LOG),
                *T.li(A.t8, T.INDEX), A.lw(A.t9, 0, A.t8), A.sll(A.t7, A.t9, 2),
                A.addu(A.t7, A.t7, A.t4), A.sw(A.v0, 0, A.t7),
                A.addiu(A.t9, A.t9, 1), A.sw(A.t9, 0, A.t8)]

    program = [*T.li(A.sp, 0x80007f00), *T.poke(mask, 0x0015ab01),
               *T.call('osCreateMesgQueue', queue, buffer, 4),
               *T.call('osCreateThread', one, 71, 'one', 0x1234, 0x80010000, 10),
               *T.log_word(one + 0x118), *T.log_word(one + 0x128),
               *T.call('osStartThread', one), *A.DONE,
               'one', *T.li(A.t0, T.LOG), A.sw(A.a0, 8, A.t0),
               *T.poke(T.INDEX, 3), *status(), *initialize(0x12340000),
               *T.call('osCreateThread', two, 72, 'two', 0x5678, 0x80018000, 20),
               *T.poke(two + 0x118, 0x5503), *T.poke(two + 0x128, 0x2b),
               *T.call('osStartThread', two), *observe(0x80), *T.log(1), *status(),
               *T.log_word(two + 0x118), *T.log_word(two + 0x128),
               *T.poke(mask, 0x003fff01),
               *T.call('osSendMesg', queue, 0xcafe, 1), *A.DONE,
               'two', *initialize(0x56780000), *T.log(2), *status(),
               *T.call('osRecvMesg', queue, slot, 1), *observe(0xb0), *T.log(3), *status(),
               *T.log_word(slot), *T.log_word(two + 4),
               *T.call('osGetThreadPri', 0), *T.li(A.t0, T.LOG), A.sw(A.v0, 56, A.t0), *A.DONE]
    for name in names:
        program += [name, A.jr(A.ra), A.nop]
    native = T.build(exe, cc, 'sdk-dispatch', program, names,
                     status_globals={'osCreateThread': mask, 'osSetIntMask': mask}, fr0=True)
    expected = [0xff03, 0x3f, 0x1234, 0xab01, 2, 0x101, 1, 0xab01,
                0x5502, 0x2b, 3, 0x5501, 0xcafe, 20, 20]
    result = subprocess.run([str(native), '--dump', hex(T.LOG), '55'],
                            capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 0, (result.stdout, result.stderr)
    words = next(row['words'] for row in rows if 'dump' in row)
    assert words[:len(expected) + 1] == expected + [0], rows
    assert words[32:43] == [0x12340000 + r if r != A.sp else 0x8000fff0 for r in saved], rows
    assert words[44:55] == [0x56780000 + r if r != A.sp else 0x80017ff0 for r in saved], rows
    stop = next(row for row in rows if 'stop' in row)
    assert stop['stop'] == 'exit' and stop['fault'] == 0, stop
    print('SDK dispatch: first host handoff, saved EXL cleared, priority preemption, blocked queues, '
          'guest-edited saved IM/MI and global-mask restore')
    residual_entries(exe, cc, T)


def residual_entries(exe, cc, T):
    A = T.A
    names = ['osCreateThread', 'osStartThread', 'osDestroyThread']
    field = 0x80005000
    for bad in [False, True]:
        # The first callback declares the native worker. The second callback
        # reads mutable RAM, so its actual value remains a residual edge.
        create = T.call('osCreateThread', 0x80002300, 2, 0, 0x1234, 0x80018000, 10)
        program = [*T.li(A.sp, 0x80007f00),
                   *T.call('osCreateThread', 0x80002100, 1, 'worker', 0, 0x80010000, 10),
                   *T.call('osDestroyThread', 0x80002100),
                   *T.li(A.t0, field)]
        program += T.li(A.t1, 0x8000f000) if bad else [A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'worker')]
        program += [A.sw(A.t1, 0, A.t0), *create[:-2], *T.li(A.t0, field),
                    A.lw(A.a2, 0, A.t0), *create[-2:],
                    *T.call('osStartThread', 0x80002300), *A.DONE,
                    'worker', *T.li(A.t0, T.LOG), A.sw(A.a0, 0, A.t0), *A.DONE]
        for name in names:
            program += [name, A.jr(A.ra), A.nop]
        name = 'sdk-residual-bad' if bad else 'sdk-residual'
        native = T.build(exe, cc, name, program, names, residual_dispatch=True)
        strict = subprocess.run([str(exe), 'lower-c', str(T.OUT / f'{name}.bin'), hex(A.BASE),
                                 hex(A.BASE), hex(A.EXIT), str(T.OUT / f'{name}.strict.c'),
                                 str(T.OUT / f'{name}.runtime.json'), '--address-taken'],
                                capture_output=True, text=True)
        assert strict.returncode != 0 and 'unresolved_runtime_callback' in strict.stderr, strict.stderr
        result = subprocess.run([str(native), '--dump', hex(T.LOG), '2'],
                                capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        words = next(row['words'] for row in rows if 'dump' in row)
        if bad:
            refused_entry(result, stop)
            assert words == [0, 0], rows
            source = T.OUT / f'{name}.c'
            original = source.read_text()
            guard = 'plaid_fault(s, entry, 3)'
            assert original.count(guard) == 1
            mutant = T.OUT / 'sdk-residual-mutant.exe'
            try:
                source.write_text(original.replace(guard, '0'))
                subprocess.run([cc, '-O2', '-std=gnu11', '-DPLAID_SAFEPOINTS',
                                f'-DPLAID_LOWERED="{name}.c"', '-I', str(T.OUT),
                                str(T.ROOT / 'runtime/plaid_rt.c'), '-pthread', '-o', str(mutant)], check=True)
            finally:
                source.write_text(original)
            mutation = subprocess.run([str(mutant), '--seconds', '0.1'],
                                      capture_output=True, text=True, timeout=30)
            mutated_stop = next(json.loads(line) for line in mutation.stdout.splitlines()
                                if line.startswith('{"stop"'))
            try:
                refused_entry(mutation, mutated_stop)
            except AssertionError:
                pass
            else:
                raise AssertionError('native entry guard mutation escaped the refusal assertion')
            assert mutation.returncode == 0 and mutated_stop['fault'] == 0, mutated_stop
            (T.OUT / 'sdk-dispatch-mutation.json').write_text(json.dumps(mutated_stop, indent=2))
        else:
            assert result.returncode == 0 and stop['fault'] == 0 and stop['stop'] == 'exit', rows
            assert words == [0x1234, 0], rows
    print('SDK residual callbacks: strict refusal, native worker dispatch, unknown entry fault 3; '
          'removing the native entry guard fails the unknown-target assertion')


if __name__ == '__main__':
    import os
    import shutil
    import test_runtime as T
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
