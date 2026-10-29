/* Synthetic guest SDK queue/context contracts; no game data. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>

static plaid_state state;
static const u32 queue = 0x80005000u, tail = 0x80004000u;

static void blocked(unsigned slot, s32 pri, u64 order, int full) {
  rt_thread *t = &threads[slot];
  memset(t, 0, sizeof *t);
  t->guest = 0x80002000u + slot * 0x200u;
  t->state = T_BLOCKED; t->pri = pri; t->seq = order;
  t->wait_queue = queue; t->wait_full = full;
  wr32(t->guest + 4, (u32)pri);
}
static void chain(int full, const unsigned *slots, unsigned count) {
  unsigned i; u32 head = queue + (full ? 4u : 0u), node = rd32(head);
  for (i = 0; i < count; i++) {
    rt_thread *t = &threads[slots[i]];
    assert(node == t->guest && rd32(node + 8) == head);
    assert(rd32(node + 0x10) >> 16 == 8);
    node = rd32(node);
  }
  assert(node == tail && rd32(tail) == 0 && rd32(tail + 4) == 0xffffffffu);
}
static void queues(void) {
  const unsigned initial[] = {2, 0, 1}, reprioritized[] = {1, 2, 0}, remaining[] = {2, 0};
  const unsigned single[] = {3};
  blocked(0, 20, 1, 0); blocked(1, 20, 2, 0); blocked(2, 30, 3, 0); blocked(3, 40, 4, 1);
  seq_counter = 4;
  publish_waiters(queue, 0); publish_waiters(queue, 1);
  chain(0, initial, 3); chain(1, single, 1);
  S->r[4] = threads[0].guest; S->r[5] = 20;
  assert(!plaid_rt_osSetThreadPri(S) && threads[0].seq == 1 && seq_counter == 4);
  chain(0, initial, 3);
  S->r[4] = threads[1].guest; S->r[5] = 30;
  assert(!plaid_rt_osSetThreadPri(S));
  /* Re-enqueue behind the earlier equal-priority waiter. */
  { const unsigned equal[] = {2, 1, 0}; chain(0, equal, 3); }
  S->r[5] = 50; assert(!plaid_rt_osSetThreadPri(S)); chain(0, reprioritized, 3);
  wake_waiter(queue, 0); assert(threads[1].state == T_RUNNABLE);
  assert(rd32(threads[1].guest + 0x10) >> 16 == 2); chain(0, remaining, 2);
  S->r[4] = threads[2].guest; assert(!plaid_rt_osStopThread(S));
  assert(rd32(threads[2].guest + 0x10) >> 16 == 1);
  { const unsigned last[] = {0}; chain(0, last, 1); }
  destroy_thread(&threads[0]); chain(0, NULL, 0);
  wake_waiter(queue, 1); assert(threads[3].state == T_RUNNABLE);
  assert(rd32(threads[3].guest + 0x10) >> 16 == 2); chain(1, NULL, 0);
}
static void context(int fp, const char *mode) {
  unsigned i; rt_thread *t = &threads[0];
  memset(t, 0, sizeof *t); t->guest = 0x80002000u; t->status_known = 1;
  t->status_global = 0x80006000u; wr32(t->status_global, 0x003fff01u);
  memset(S->ram + 0x2000, 0xa5, 0x1b0); wr32(t->guest + 0x18, (u32)fp);
  S->cp0_status = 0x2000ff00u; S->fr_mode = 1; S->mi_mask = 0x15;
  S->fcc = 1; S->fcsr = 0x01000003u;
  for (i = 0; i < 32; i++) {
    S->r[i] = i ? 0x1234567800000000ull + i : 0;
    S->f[i] = 0x3ff0000000000000ull + i;
  }
  S->hi = 0x11223344; S->lo = 0x55667788;
  S->llbit = 1;
  if (mode) {
    static const plaid_text_range range[] = {{0x2188, 0x2190}};
    static plaid_native_frame frame = {0, 0, range, 1, 0, 0, -1};
    dump_at = t->guest; dump_words = 0x1b0 / 4;
    if (!strcmp(mode, "fr")) S->fr_mode = 2;
    else if (!strcmp(mode, "cu1")) S->cp0_status &= ~0x20000000u;
    else {
      plaid_build_prot(S); S->prot[0x2188 / 4] = S->prot[0x218c / 4] = 1;
      plaid_text_pin(S, &frame);
    }
  }
  save(t);
  for (i = 0; i < 32; i++) {
    assert(S->r[i] == (i ? 0x1234567800000000ull + i : 0));
    assert(S->f[i] == 0x3ff0000000000000ull + i);
  }
  assert(S->hi == 0x11223344 && S->lo == 0x55667788 && S->llbit == 1);
  assert(S->cp0_status == 0x2000ff00u && S->fr_mode == 1);
  assert(S->fcsr == 0x01000003u && S->fcc == 1 && !S->pc && !S->fault);
  printf("{\"context\":[");
  for (i = 0; i < 0x1b0 / 4; i++) printf("%s%u", i ? "," : "", rd32(t->guest + 4 * i));
  printf("]}\n");
}
int main(int argc, char **argv) {
  S = &state; S->r[31] = 0xffffffff80000f00ull;
  plaid_load_images(S);
  wr32(tail, 0); wr32(tail + 4, 0xffffffffu);
  assert(!plaid_rt_bind_queue_tail(S, tail));
  if (argc > 1 && !strcmp(argv[1], "context")) { context(argc > 2, NULL); return 0; }
  if (argc > 2 && !strcmp(argv[1], "context-refuse")) { context(1, argv[2]); return 99; }
  if (argc > 1 && !strcmp(argv[1], "refuse")) {
    plaid_text_range range[] = {{0x2200, 0x2214}};
    plaid_native_frame frame = {0, 0, range, 1, 0, 0, -1};
    blocked(0, 20, 1, 0); blocked(1, 10, 2, 0);
    wr32(queue, tail); dump_at = queue; dump_words = 1;
    plaid_build_prot(S);
    for (unsigned i = 0x2200 / 4; i < 0x2214 / 4; i++) S->prot[i] = 1;
    plaid_text_pin(S, &frame); publish_waiters(queue, 0);
    return 99;
  }
  queues(); return 0;
}
