"""Source-bound SDK data is visible across native guest and host interfaces."""
import json
import os
import subprocess
import sys


def run(exe, cc, T):
    A, out = T.A, T.OUT
    table, tail, queue, buffer, log = 0x80005000, 0x80004000, 0x80006000, 0x80006020, 0x80001000
    create = [*T.li(A.t0, tail), A.sw(A.t0, 0, A.a0), A.sw(A.t0, 4, A.a0),
              A.sw(A.zero, 8, A.a0), A.sw(A.zero, 12, A.a0), A.sw(A.a2, 16, A.a0), A.sw(A.a1, 20, A.a0), A.jr(A.ra), A.nop]
    event = [A.sll(A.t0, A.a0, 3), *T.li(A.t1, table), A.addu(A.t0, A.t0, A.t1),
             A.sw(A.a1, 0, A.t0), A.sw(A.a2, 4, A.t0), A.jr(A.ra), A.nop]
    program = [*T.li(A.sp, 0x80007f00), *T.poke(tail, 0), *T.poke(tail + 4, 0xffffffff),
               *T.call('osCreateMesgQueue', queue, buffer, 4), *T.call('osSetEventMesg', 12, queue, 0x1234)]
    for index, address in enumerate([table + 96, table + 100, queue, queue + 4]):
        program += [*T.li(A.t0, address), A.lw(A.t1, 0, A.t0), *T.li(A.t0, log), A.sw(A.t1, index * 4, A.t0)]
    program += [*A.DONE, 'osCreateMesgQueue', *create, 'osSetEventMesg', *event]
    binary = T.build(exe, cc, 'kernel-globals', program, ['osCreateMesgQueue', 'osSetEventMesg'],
                     data_bindings={'osCreateMesgQueue': {'__osThreadTail': tail}, 'osSetEventMesg': {'__osEventStateTab': table}},
                     source_sizes={'osCreateMesgQueue': len(create) * 4, 'osSetEventMesg': len(event) * 4})
    expected = [queue, 0x1234, tail, tail]
    def check(binary):
        result = subprocess.run([str(binary), '--dump', hex(log), '4'], capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        assert not result.returncode and next(row for row in rows if 'stop' in row)['fault'] == 0, (result.stdout, result.stderr)
        assert next(row for row in rows if 'dump' in row)['words'] == expected, rows
    check(binary)
    sys.path.insert(0, str(T.ROOT / 'scripts'))
    import ares_oracle
    reference = subprocess.run([str(ares_oracle.default()), str(out / 'kernel-globals.bin'), hex(A.EXIT)], capture_output=True, text=True, timeout=60)
    assert not reference.returncode, reference.stderr
    state = json.loads(reference.stdout)
    assert state['pc'] == A.EXIT and state['ram'][:4] == expected and not any(state['ram'][4:]), state

    runtime = (T.ROOT / 'runtime/plaid_rt.c').read_text()
    source, contract = out / 'kernel-global-contract.c', out / 'kernel-global-contract.exe'
    source.write_text('#define main runtime_main\n#include "' + (T.ROOT / 'runtime/plaid_rt.c').as_posix() + '"\n#undef main\n' + r'''
#include <assert.h>
static plaid_state state;
int main(void) {
  u32 before;
  S = &state; S->io = rt_io; S->r[31] = 0xffffffff80000f00ull;
  plaid_load_images(S); assert(!plaid_run(S));
  assert(event_table_global == 0x80005000 && queue_tail_global == 0x80004000);
  /* A native guest write changes the next host event delivery, including disable. */
  wr32(0x80005038, 0x80006000); wr32(0x8000503c, 0x5678);
  pending[EV_VI] = 1; deliver_pending();
  assert(rd32(0x80006008) == 1 && rd32(0x80006020) == 0x5678);
  wr32(0x80005038, 0); pending[EV_VI] = 1; deliver_pending();
  assert(rd32(0x80006008) == 1);
  before = rd32(0x80005060);
  assert(plaid_rt_bind_event_table(S, 0x80005100) && S->fault == 12);
  assert(event_table_global == 0x80005000 && rd32(0x80005060) == before); S->fault = 0;
  assert(plaid_rt_bind_queue_tail(S, 0x80004004) && S->fault == 12); S->fault = 0;
  queue_tail_global = 0; wr32(0x80004004, 0);
  assert(plaid_rt_bind_queue_tail(S, 0x80004000) && !queue_tail_global); S->fault = 0;
  wr32(0x80004004, 0xffffffff); assert(!plaid_rt_bind_queue_tail(S, 0x80004000));
  /* A failed backfill cannot publish a binding or change executable bytes. */
  event_table_global = 0; before = rd32(0x80000000);
  plaid_text_range ranges[] = {{0, 4}};
  plaid_native_frame frame = {0, 0, ranges, 1, 0, 0, -1};
  plaid_text_pin(S, &frame);
  assert(plaid_rt_bind_event_table(S, 0x80000000) && !event_table_global);
  assert(rd32(0x80000000) == before); S->fault = 0; plaid_text_unpin(S, &frame);
  /* A late first binding preserves already registered host events. */
  event_table_global = 0; events[12].mq = 0x80006000; events[12].msg = 0x9876; events[12].set = 1;
  assert(!plaid_rt_bind_event_table(S, 0x80005000) && rd32(0x80005064) == 0x9876);
  return 0;
}
''')
    def compile(runtime_source, target, extra=()):
        subprocess.run([cc, '-O2', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-function', '-Wno-unused-label',
                        '-DPLAID_SAFEPOINTS', '-DPLAID_LOWERED="kernel-globals.c"', '-I', str(out), '-I', str(T.ROOT / 'runtime'),
                        str(runtime_source), *extra, '-pthread', '-o', str(target)], check=True)
    compile(source, contract)
    result = subprocess.run([str(contract)], capture_output=True, text=True, timeout=30)
    assert not result.returncode, (result.stdout, result.stderr)
    for name, before, after in [
        ('publication', 'wr(event_table_global + ev * 8, data, 8);', '(void)data;'),
        ('tail', 'wr32(mq, queue_tail_global); wr32(mq + 4, queue_tail_global);', 'wr32(mq, 0); wr32(mq + 4, 0);'),
        ('guest-write', 'if (!event_table_global) return events[ev];', 'return events[ev];'),
    ]:
        assert runtime.count(before) == 1
        altered = out / ('kernel-' + name + '.runtime.c'); altered.write_text(runtime.replace(before, after))
        mutant = out / ('kernel-' + name + '.exe')
        if name == 'guest-write':
            mutated_contract = out / 'kernel-mutated-contract.c'
            mutated_contract.write_text(source.read_text().replace((T.ROOT / 'runtime/plaid_rt.c').as_posix(), altered.as_posix()))
            compile(mutated_contract, mutant)
            assert subprocess.run([str(mutant)], capture_output=True, timeout=30).returncode, name
        else:
            compile(altered, mutant)
            try: check(mutant)
            except AssertionError: pass
            else: raise AssertionError(name + ' mutation survived')
    labels = A.label_pcs(program)
    needle = '  plaid_load_images(S);'
    assert runtime.count(needle) == 1
    altered.write_text(runtime.replace(needle, needle + f' S->ram[{labels["osSetEventMesg"] & 0x1fffffff}] ^= 1;'))
    compile(altered, mutant)
    result = subprocess.run([str(mutant), '--dump', hex(table + 96), '2'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode and next(row for row in rows if 'stop' in row)['fault'] == 8, rows
    assert next(row for row in rows if 'dump' in row)['words'] == [0, 0], rows
    print('PASS source-bound SDK event/tail publication, guest writes/disable, late binding, conflicts, source refusal; pinned-ares ABI memory comparison and three mutations')


if __name__ == '__main__':
    import shutil
    from pathlib import Path
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(Path(os.environ['PLAID_TEST_EXE']).resolve(), shutil.which('gcc'), T)
