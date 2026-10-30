/* Source-bound runnable queues; synthetic host state only. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>

static plaid_state state;
static const u32 tail = 0x80004000u, ready = 0x80004800u, queue = 0x80005000u;
static void node(unsigned i, s32 pri, u64 order, int state) {
  rt_thread *t = &threads[i];
  memset(t, 0, sizeof *t); t->guest = 0x80002000u + i * 0x200u;
  t->state = state; t->pri = pri; t->seq = order;
  t->wait_queue = queue;
  wr32(t->guest + 4, (u32)pri); wr16(t->guest + 0x10, 1);
}
static void chain(const unsigned *slots, unsigned count) {
  unsigned i; u32 pointer = rd32(ready);
  for (i = 0; i < count; i++) {
    assert(pointer == threads[slots[i]].guest);
    assert(rd32(pointer + 8) == run_queue_global);
    assert(rd32(pointer + 0x10) >> 16 == 2);
    pointer = rd32(pointer);
  }
  assert(pointer == queue_tail_global);
}
int main(int argc, char **argv) {
  static const unsigned ordered[] = {1, 2, 0}, after_stop[] = {1, 0};
  u32 before; int mode = argc > 1 ? atoi(argv[1]) : 0;
  S = &state; S->r[31] = 0xffffffff80000f00ull; plaid_load_images(S);
  wr32(tail, 0); wr32(tail + 4, 0xffffffffu); wr32(ready, 0xdeadbeefu);
  node(0, 10, 1, T_RUNNABLE); node(1, 20, 2, T_RUNNABLE); node(2, 20, 3, T_RUNNABLE);
  node(3, 30, 4, T_RUNNING); running = &threads[3]; seq_counter = 4;
  if (mode == 2 || mode == 3) {
    /* Failed first/late binding cannot install the tail or publish a head. */
    static const plaid_text_range ranges[] = {{0x2200, 0x2214}};
    static plaid_native_frame frame = {0, 0, ranges, 1, 0, 0, -1};
    plaid_build_prot(S);
    for (unsigned i = 0x2200 / 4; i < 0x2214 / 4; i++) S->prot[i] = 1;
    plaid_text_pin(S, &frame);
    if (mode == 2) {
      assert(!plaid_rt_bind_run_queue(S, ready) && run_queue_global == ready);
      assert(plaid_rt_bind_queue_tail(S, tail) && !queue_tail_global);
    } else {
      assert(!plaid_rt_bind_queue_tail(S, tail));
      assert(plaid_rt_bind_run_queue(S, ready) && !run_queue_global);
    }
    assert(S->fault == 2 && rd32(ready) == 0xdeadbeefu);
    assert(!rd32(threads[0].guest) && !rd32(threads[1].guest));
    return 0;
  }
  if (mode == 1) {
    assert(!plaid_rt_bind_queue_tail(S, tail));
    assert(rd32(ready) == 0xdeadbeefu && !run_queue_global);
    assert(!plaid_rt_bind_run_queue(S, ready));
  } else {
    assert(!plaid_rt_bind_run_queue(S, ready));
    assert(rd32(ready) == 0xdeadbeefu && !queue_tail_global);
    assert(!plaid_rt_bind_queue_tail(S, tail));
  }
  chain(ordered, 3); assert(rd32(threads[3].guest + 0x10) >> 16 == 4);
  running = NULL;
  before = rd32(ready);
  assert(plaid_rt_bind_run_queue(S, ready + 4) && S->fault == 12);
  assert(run_queue_global == ready && rd32(ready) == before); S->fault = 0;
  run_queue_global = 0;
  assert(plaid_rt_bind_run_queue(S, tail) && S->fault == 12 && !run_queue_global); S->fault = 0;
  assert(!plaid_rt_bind_run_queue(S, ready));
  S->r[4] = threads[2].guest; assert(!plaid_rt_osStopThread(S)); chain(after_stop, 2);
  assert(rd32(threads[2].guest + 0x10) >> 16 == 1);
  destroy_thread(&threads[1]); { const unsigned last[] = {0}; chain(last, 1); }
  /* Raising an equal-priority peer reenqueues it after the earlier peer. */
  node(1, 20, 5, T_RUNNABLE); node(2, 10, 4, T_RUNNABLE);
  seq_counter = 6; S->r[4] = threads[2].guest; S->r[5] = 20;
  assert(!plaid_rt_osSetThreadPri(S)); chain(ordered, 3);
  S->r[5] = 20; before = (u32)threads[2].seq;
  assert(!plaid_rt_osSetThreadPri(S) && threads[2].seq == before); chain(ordered, 3);
  /* Waiting -> runnable changes two heads, with a failure in the second. */
  if (mode == 4) {
    static const plaid_text_range ranges[] = {{0x4800, 0x4804}};
    static plaid_native_frame frame = {0, 0, ranges, 1, 0, 0, -1};
    threads[0].state = threads[1].state = T_BLOCKED;
    threads[0].pri = 40; threads[0].seq = 8; threads[1].seq = 9;
    publish_waiters(queue, 0);
    dump_at = queue; dump_words = 1;
    S->prot[0x4800 / 4] = 1; plaid_text_pin(S, &frame);
    wake_waiter(queue, 0); return 99;
  }
  /* Numeric aliases bind one physical head; queue fields use the bound VA. */
  assert(!plaid_rt_bind_run_queue(S, ready | 0x20000000u)); chain(ordered, 3);
  puts("PASS synthetic run-queue state"); return 0;
}
