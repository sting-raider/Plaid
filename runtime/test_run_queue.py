"""Source-bound SDK runnable lists follow actual native scheduler handoffs."""
import json
import os
import subprocess


def run(exe, cc, T):
    A, out = T.A, T.OUT
    tail, ready, main, low, peer = 0x80004000, 0x80004800, 0x80002000, 0x80002200, 0x80002400
    names = ['osCreateMesgQueue', 'osCreateThread', 'osStartThread', 'osStopThread', 'osSetThreadPri', 'osYieldThread']
    expected = []
    def observe(address, value):
        offset = len(expected) * 4; expected.append(value)
        return [*T.li(A.t0, address), A.lw(A.t1, 0, A.t0), *T.li(A.t0, 0x80003000), A.sw(A.t1, offset, A.t0)]
    program = [*T.li(A.sp, 0x80007f00), *T.poke(tail, 0), *T.poke(tail + 4, 0xffffffff),
               *T.call('osCreateMesgQueue', 0x80005000, 0x80005020, 1),
               *T.call('osCreateThread', main, 1, 'main', 0, 0x8000ff00, 10), *T.call('osStartThread', main), *A.DONE,
               'main', *observe(ready, tail), *observe(main + 0x10, 4 << 16),
               *T.call('osCreateThread', low, 2, 'low', 0, 0x80017f00, 5), *T.call('osStartThread', low),
               *T.call('osCreateThread', peer, 3, 'peer', 0, 0x8001ff00, 10), *T.call('osStartThread', peer),
               *observe(ready, peer), *observe(peer, low), *observe(low, tail), *observe(low + 8, ready),
               *T.call('osYieldThread'), *observe(ready, low), *observe(peer + 0x10, 1 << 16),
               # Changing another runnable thread must preempt this caller.
               *T.call('osSetThreadPri', low, 30), *observe(ready, tail), *observe(low + 0x10, 1 << 16), *A.DONE,
               'peer', *observe(ready, main), *observe(main, low), *T.call('osStopThread', 0), *A.DONE,
               'low', *observe(ready, main), *observe(low + 0x10, 4 << 16), *T.call('osStopThread', 0), *A.DONE]
    for name in names: program += [name, A.jr(A.ra), A.nop]
    native = T.build(exe, cc, 'run-queue-threads', program, names,
                     data_bindings={'osCreateMesgQueue': {'__osThreadTail': tail}, 'osStartThread': {'__osRunQueue': ready}},
                     source_sizes={'osCreateMesgQueue': 8, 'osStartThread': 8})

    def invoke(binary, *args):
        return subprocess.run([str(binary), *args], capture_output=True, text=True, timeout=30)
    def check_threads(binary):
        result = invoke(binary, '--dump', '0x80003000', str(len(expected)))
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert not result.returncode and next(row for row in rows if 'stop' in row)['fault'] == 0, (result.stdout, result.stderr)
        assert next(row for row in rows if 'dump' in row)['words'] == expected, rows
    check_threads(native)
    T.build(exe, cc, 'run-queue-fixture', list(A.DONE), [])
    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    contract = (T.ROOT / 'runtime/test_run_queue.c').read_text()
    def compile(source, binary, lowered):
        subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-label', '-Wno-unused-function',
                        '-DPLAID_SAFEPOINTS', f'-DPLAID_LOWERED="{lowered}"', '-I', str(out),
                        '-I', str(T.ROOT / 'runtime'), str(source), '-pthread', '-o', str(binary)], check=True)
    binary = out / 'run-queue-contract.exe'
    compile(T.ROOT / 'runtime/test_run_queue.c', binary, 'run-queue-fixture.c')
    for mode in range(4):
        result = invoke(binary, str(mode)); assert not result.returncode, (mode, result.stdout, result.stderr)
    result = invoke(binary, '4')
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 1 and next(row for row in rows if 'stop' in row)['fault'] == 2, rows
    assert next(row for row in rows if 'dump' in row)['words'] == [main], rows
    mutations = [
        ('binding', 'run_queue_global = queue; queue_tail_global = tail;', 'queue_tail_global = tail;', '0', False),
        ('handoff', 'if (next) next->state = T_RUNNING;\n  publish_queues(0, 0);', 'if (next) next->state = T_RUNNING;', '', True),
        ('cross-list-preflight', '(run_queue_global && check_queue(&ready))', '0', '4', False),
        ('reenqueue', 't->seq = ++seq_counter; publish_queues(0, 0);', 'publish_queues(0, 0);', '0', False),
        ('preemption', '  } else {\n    maybe_preempt(1);\n  }\n  return 0;\n}\n/* The caller queues',
         '  }\n  return 0;\n}\n/* The caller queues', '', True),
        ('late-binding', 'if (queue && tail) {\n    collect_queue(&ready, queue, tail, 0, 0);',
         'if (queue && tail) {\n    queue_tail_global = tail;\n    collect_queue(&ready, queue, tail, 0, 0);', '2', False),
    ]
    for name, before, after, mode, threads in mutations:
        assert runtime.count(before) == 1, (name, runtime.count(before))
        altered = out / f'run-queue-{name}.runtime.c'; altered.write_text(runtime.replace(before, after))
        target = out / f'run-queue-{name}.exe'
        if threads:
            compile(altered, target, 'run-queue-threads.c')
            try: check_threads(target)
            except AssertionError: pass
            else: raise AssertionError(name + ' mutation survived')
        else:
            source = out / f'run-queue-{name}.contract.c'
            source.write_text(contract.replace('#include "plaid_rt.c"', '#include "' + altered.as_posix() + '"'))
            compile(source, target, 'run-queue-fixture.c'); result = invoke(target, mode)
            if name == 'cross-list-preflight':
                rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
                assert next(row for row in rows if 'dump' in row)['words'] != [main], name
            else:
                assert result.returncode, (name, result.stdout, result.stderr)
    # Source corruption must refuse before the first run-queue registration.
    pc = A.label_pcs(program)['osStartThread'] & 0x1fffffff
    needle = '  plaid_load_images(S);'; assert runtime.count(needle) == 1
    altered.write_text(runtime.replace(needle, needle + f' S->ram[{pc}] ^= 1;'))
    compile(altered, target, 'run-queue-threads.c')
    result = invoke(target, '--dump', hex(ready), '1')
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode and next(row for row in rows if 'stop' in row)['fault'] == 8, rows
    assert next(row for row in rows if 'dump' in row)['words'] == [0], rows
    print('PASS source-bound runnable queues: ordering, start/yield/preemption/stop/destroy, same-priority no-op, late binding/alias/conflict/source refusals, atomic two-list failure; six mutations')


if __name__ == '__main__':
    import shutil
    import test_runtime as T
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug/plaid.exe', shutil.which('gcc'), T)
