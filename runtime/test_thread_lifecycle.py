"""A parked SDK thread's old stacks must never run after destruction/reuse."""
import json
import os
import subprocess


def program(T, coroutine, destroy):
    import test_coroutines as C
    A = T.A
    coordinator, worker = 0x80005000, 0x80005200
    queue, buffer, output, count = 0x80005400, 0x80005420, 0x80005440, 0x80005460
    runtime = ['osCreateThread', 'osStartThread', 'osStopThread', 'osDestroyThread',
               'osCreateMesgQueue', 'osRecvMesg', 'osSendMesg', 'osSetThreadPri']
    p = [*T.li(A.sp, 0x80027F00),
         # Declare both coroutine entries through ordinary SDK callbacks.
         *T.call('osCreateThread', 0x80005600, 4, 'coroutine', 0, 0x8002FF00, 1),
         *T.call('osCreateThread', 0x80005600, 4, 'self_destroy', 0, 0x8002FF00, 1),
         *T.call('osDestroyThread', 0x80005600),
         *T.call('osCreateThread', coordinator, 1, 'coordinator', 0, 0x80017F00, 10),
         *T.call('osStartThread', coordinator), *A.DONE,
         'coordinator', *T.call('osCreateMesgQueue', queue, buffer, 4),
         *T.poke(count, 140), 'again',
         *T.call('osCreateThread', worker, 2, 'old', 0, 0x8000FF00, 20),
         *T.call('osStartThread', worker),
         *([*T.call('osDestroyThread', worker)] if destroy else []),
         *T.poke(worker, 0xBAD), *T.poke(worker + 8, 0xBAD),
         *T.call('osCreateThread', worker, 3, 'new', 0x12345678, 0x8000EF00, 5),
         *T.log_word(worker + 4), *T.log_word(worker + 0x14),
         *T.log_word(worker), *T.log_word(worker + 8),
         *T.call('osStartThread', worker),
         *T.call('osSendMesg', queue, 7, 0),
         *T.call('osRecvMesg', queue, output, 1), *T.log_word(output),
         *T.call('osRecvMesg', queue, output, 1), *T.log_word(output),
         *T.li(A.t0, count), A.lw(A.t1, 0, A.t0), A.addiu(A.t1, A.t1, -1), A.sw(A.t1, 0, A.t0),
         A.beq(A.t1, A.zero, 'finished'), A.nop,
         *T.poke(T.INDEX, 0), A.j('again'), A.nop, 'finished',
         # All abandoned fixed-text registrations must have been released.
         A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'old'), A.sw(A.zero, 0, A.t0),
         A.lui(A.t0, 0x8000), A.LO(A.t0, A.t0, 'coroutine'), A.sw(A.zero, 0, A.t0),
         *T.log(0x600D), *A.DONE,
         'old',
         *([*T.call('save', C.SCHED), *T.call('save', C.WORKER),
            *T.poke(C.WORKER, 0x8000DF00), *T.li(A.t0, C.WORKER),
            A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'coroutine'), A.sw(A.t1, 4, A.t0),
            *T.call('restore', C.WORKER, 1)] if coroutine else [*T.call('osStopThread', 0)]),
         *T.poke(T.LOG + 28, 0xBAD), *A.DONE,
         'coroutine', *T.call('save', C.WORKER), *T.call('osRecvMesg', queue, 0, 1),
         *T.poke(T.LOG + 28, 0xBAD), *A.DONE,
         'new', *T.li(A.t0, output + 4), A.sw(A.a0, 0, A.t0),
         *T.call('osSetThreadPri', 0, 20),
         *T.call('osSendMesg', queue, 9, 0),
         # Self-destroy from a live coroutine must also retire its root.
         *([*T.call('save', C.SCHED), *T.call('save', C.WORKER), *T.poke(C.WORKER, 0x8000CF00), *T.li(A.t0, C.WORKER),
            A.lui(A.t1, 0x8000), A.LO(A.t1, A.t1, 'self_destroy'), A.sw(A.t1, 4, A.t0),
            *T.call('restore', C.WORKER, 1)] if coroutine else [*T.call('osDestroyThread', 0)]),
         *T.poke(T.LOG + 28, 0xBAD), *A.DONE,
         'self_destroy', *T.call('osDestroyThread', 0), *T.poke(T.LOG + 28, 0xBAD), *A.DONE,
         *C.bodies(A)]
    p += [item for name in runtime for item in [name, A.jr(A.ra), A.nop]]
    return p, runtime, output


def stopped_waiter(exe, cc, T):
    A = T.A
    coordinator, worker, queue, buffer, output = (0x80005000, 0x80005200, 0x80005400, 0x80005420, 0x80005440)
    runtime = ['osCreateThread', 'osStartThread', 'osStopThread', 'osCreateMesgQueue', 'osRecvMesg', 'osSendMesg']
    for send in (False, True):
        p = [*T.li(A.sp, 0x80027F00),
             *T.call('osCreateThread', coordinator, 1, 'coordinator', 0, 0x80017F00, 10),
             *T.call('osStartThread', coordinator), *A.DONE,
             'coordinator', *T.call('osCreateMesgQueue', queue, buffer, 1),
             *([*T.call('osSendMesg', queue, 42, 0)] if send else []),
             *T.call('osCreateThread', worker, 2, 'worker', 0, 0x8000FF00, 20),
             *T.call('osStartThread', worker), *T.call('osStopThread', worker),
             *T.call('osStopThread', worker), *T.log(1),
             *([*T.call('osRecvMesg', queue, output, 0)] if send else [*T.call('osSendMesg', queue, 99, 0)]),
             *T.log(2), *T.log_word(queue + 8), *T.log_word(worker + 0x10),
             *T.call('osStartThread', worker), *T.log(3),
             *([*T.call('osRecvMesg', queue, output, 0)] if send else []),
             *T.log_word(output), *A.DONE,
             'worker', *T.li(A.s0, 0x31415926),
             *([*T.call('osSendMesg', queue, 99, 1)] if send else [*T.call('osRecvMesg', queue, output, 1)]),
             *T.li(A.t0, output + 4), A.sw(A.s0, 0, A.t0), *T.log(4), *T.call('osStopThread', 0), *A.DONE]
        p += [item for name in runtime for item in [name, A.jr(A.ra), A.nop]]
        binary = T.build(exe, cc, f'stopped-waiter-{int(send)}', p, runtime)
        result = subprocess.run([str(binary), '--dump', hex(T.LOG), '7'], capture_output=True, text=True, timeout=10)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert next(row['words'] for row in rows if 'dump' in row) == [1, 2, 0 if send else 1, 0x10000, 4, 3, 99], rows
        result = subprocess.run([str(binary), '--dump', hex(output + 4), '1'], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0 and next(json.loads(line)['words'] for line in result.stdout.splitlines()
                                               if line.startswith('{"dump"')) == [0x31415926], result.stdout


def run(exe, cc, T):
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    T.OUT.mkdir(parents=True, exist_ok=True)
    stopped_waiter(exe, cc, T)
    for coroutine in (False, True):
        for destroy in (False, True):
            p, runtime, output = program(T, coroutine, destroy)
            name = f'thread-lifecycle-{int(coroutine)}-{int(destroy)}'
            binary = T.build(exe, cc, name, p, runtime, fr0=True,
                             address_taken=True, residual_dispatch=True)
            result = subprocess.run([str(binary), '--dump', hex(T.LOG), '8'],
                                    capture_output=True, text=True, timeout=10)
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            stop = next(row for row in rows if 'stop' in row)
            words = next(row['words'] for row in rows if 'dump' in row)
            assert result.returncode == 0 and stop['stop'] == 'exit' and stop['fault'] == 0, (result.stdout, result.stderr)
            assert words == [5, 3, 0, 0, 7, 9, 0x600D, 0], words
            result = subprocess.run([str(binary), '--dump', hex(output), '2'],
                                    capture_output=True, text=True, timeout=10)
            words = next(json.loads(line)['words'] for line in result.stdout.splitlines() if line.startswith('{"dump"'))
            assert result.returncode == 0 and words == [9, 0x12345678], (result.stdout, result.stderr)
    # Disable the retirement check in a private runtime copy. A parked old
    # host never acknowledges: the timeout must reject this regression.
    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    guard = 'if (host_context->retired) retire_context(host_context);'
    assert runtime.count(guard) == 1
    source = T.OUT / 'thread-lifecycle-mutant.c'
    source.write_text(runtime.replace(guard, 'if (0 && host_context->retired) retire_context(host_context);'))
    mutant = T.OUT / ('thread-lifecycle-mutant.exe' if os.name == 'nt' else 'thread-lifecycle-mutant')
    subprocess.run([cc, '-O2', '-std=gnu11', '-DPLAID_SAFEPOINTS',
                    '-DPLAID_LOWERED="thread-lifecycle-0-0.c"', '-I', str(T.OUT),
                    '-I', str(T.ROOT / 'runtime'), str(source), '-pthread', '-o', str(mutant)], check=True)
    try:
        result = subprocess.run([str(mutant)], capture_output=True, text=True, timeout=2)
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError(('retirement guard mutation survived', result.stdout, result.stderr))
    print('thread lifecycle: stopped send/receive restart, 140 stopped/blocked recreations, destroy/create, live coroutines, self-destroy, pins, queue and arguments pass')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    run(T.ROOT / 'target/debug/plaid.exe', shutil.which('gcc'), T)
