/* Synthetic SDK-state contracts. No guest decoder or host event clock. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>
#include "status-cases.h"

static plaid_state state;
static const u32 global_a = 0x80004000u, global_b = 0x80004004u;
static u32 context_log[30], context_count;
static void observe_context(u32 a, u32 b) { context_log[context_count++] = a; context_log[context_count++] = b; }

static void contexts_and_events(void) {
  rt_thread *one, *two;
  u32 q = 0x80005000u, buffer = q + 0x20;
  int ev;
  S->status_known = 0;
  assert(plaid_rt___osGetSR(S) == 1 && S->fault == 11);
  S->fault = 0;
  wr32(global_a, 0x003fff01u); wr32(global_b, 0x0001ff01u);
  S->r[29] = 0xffffffff80007f00ull;
  S->r[4] = 0x80002000; S->r[5] = 1; S->r[6] = 0x80000600; S->r[7] = 0;
  wr32(0x80007f10, 0x80010000); wr32(0x80007f14, 10);
  assert(plaid_rt_osCreateThread_global(S, global_a) == 0);
  one = thread_of(0x80002000);
  assert(rd32(one->guest + 0x118) == 0xff03 && rd32(one->guest + 0x128) == 0x3f);
  observe_context(rd32(one->guest + 0x118), rd32(one->guest + 0x128));
  S->r[4] = 0x80002200;
  assert(plaid_rt_osCreateThread_global(S, global_b) == 0);
  two = thread_of(0x80002200);
  running = one; restore(one);
  assert(S->cp0_status == 0xff01 && S->mi_mask == 0x3f);
  observe_context(S->cp0_status, S->mi_mask);
  assert(plaid_rt___osDisableInt(S) == 0 && S->r[2] == 1);
  save(one);
  assert(rd32(one->guest + 0x118) == 0xff02);
  observe_context(rd32(one->guest + 0x118), rd32(one->guest + 0x128));
  running = two; restore(two);
  assert(ints_enabled && S->cp0_status == 0xff01 && S->mi_mask == 1);
  observe_context(S->cp0_status, S->mi_mask);
  S->r[4] = 0x002a5501;
  wr32(two->guest + 0x128, 2); save(two);
  observe_context(rd32(two->guest + 0x118), rd32(two->guest + 0x128));
  assert(rd32(two->guest + 0x128) == 3);
  restore(two);
  assert(plaid_rt_osSetIntMask_global(S, global_b) == 0);
  assert(S->cp0_status == 0x5501 && S->mi_mask == 0);
  observe_context(S->cp0_status, S->mi_mask);
  save(two);
  observe_context(rd32(two->guest + 0x118), rd32(two->guest + 0x128));
  running = one; restore(one);
  assert(!ints_enabled && S->cp0_status == 0xff00);
  observe_context(S->cp0_status, S->mi_mask);
  S->r[4] = 1; assert(plaid_rt___osRestoreInt(S) == 0);
  assert(ints_enabled && S->cp0_status == 0xff01);
  observe_context(S->cp0_status, S->mi_mask);
  wr32(two->guest + 0x118, rd32(two->guest + 0x118) & ~0x1000u);
  running = two; restore(two);
  assert(S->cp0_status == 0x4501 && S->mi_mask == 0);
  observe_context(S->cp0_status, S->mi_mask);
  assert(plaid_status_fp(S, 0x80000600u, 1) == 0);
  assert(rd32(two->guest + 0x18) == 1);
  observe_context(S->cp0_status, rd32(two->guest + 0x18));
  assert(plaid_rt___osGetSR(S) == 0 && S->r[2] == 0x20004501u);
  assert(plaid_status_fp(S, 0x80000600u, 0) == 1 && S->fault == 11);
  S->fault = 0;

  /* Exception-vector installation selects the dispatch mask namespace, even
     for a thread that was created by the previous SDK copy. */
  status_kernel_global = global_b; running = one; restore(one);
  assert(S->mi_mask == 1); observe_context(S->cp0_status, S->mi_mask);
  status_kernel_global = global_a; restore(one);
  assert(S->mi_mask == 0x3f); observe_context(S->cp0_status, S->mi_mask);
  assert(plaid_rt_osInitialize_global(S, global_a) == 0);
  assert(S->cp0_status == 0x2000ff00u && S->fcsr == 0x01000800u);
  observe_context(S->cp0_status, S->fcsr);
  save(one);
  assert(rd32(one->guest + 0x18) == 0); /* initialize is not a lazy FPU trap */
  observe_context(rd32(one->guest + 0x18), rd32(one->guest + 0x118));

  S->r[4] = q; S->r[5] = buffer; S->r[6] = 16;
  assert(plaid_rt_osCreateMesgQueue(S) == 0);
  for (ev = EV_SP; ev <= EV_DP; ev++) {
    unsigned before = rd32(q + 8);
    events[ev] = (rt_event){q, (u32)ev, 1};
    S->cp0_status = 0xff01; S->mi_mask = 0; ints_enabled = 1;
    post(ev); deliver_pending(); assert(pending[ev] == 1 && rd32(q + 8) == before);
    S->mi_mask = 1u << (ev - EV_SP); S->cp0_status &= ~0x400u;
    deliver_pending(); assert(pending[ev] == 1);
    S->cp0_status |= 0x402u; deliver_pending(); assert(pending[ev] == 1);
    S->cp0_status &= ~2u; S->cp0_status |= 4u;
    deliver_pending(); assert(pending[ev] == 1);
    S->cp0_status &= ~4u; ints_enabled = 0;
    deliver_pending(); assert(pending[ev] == 1);
    ints_enabled = 1; deliver_pending();
    assert(pending[ev] == 0 && rd32(q + 8) == before + 1);
    deliver_pending(); assert(rd32(q + 8) == before + 1);
  }
  S->cp0_status = 0x7f01; S->mi_mask = 0x3f;
  timers[0] = (rt_timer){1, 0, q, 0x1234, 0, 0};
  deliver_pending(); assert(timers[0].used);
  S->cp0_status |= 0x8000; deliver_pending(); assert(!timers[0].used);
  S->mi_mask = 0; pi_complete(q, 0x1111); pi_complete(q, 0x2222);
  assert(pi_completion_count == 2);
  S->mi_mask = 1u << (EV_PI - EV_SP); deliver_pending();
  assert(pi_completion_count == 0 && rd32(buffer + 7 * 4) == 0x1111 && rd32(buffer + 8 * 4) == 0x2222);
  ints_enabled = 0; S->cp0_status &= ~1u; running = NULL;
  post(EV_SP); deliver_pending();
  assert(pending[EV_SP] == 0 && !ints_enabled && !(S->cp0_status & 1));
  running = &boot;
}

int main(int argc, char **argv) {
  unsigned batch = argc == 2 ? (unsigned)strtoul(argv[1], NULL, 0) : 0, i;
  assert(batch < sizeof status_cases / sizeof status_cases[0] / 16);
  S = &state; running = &boot;
  contexts_and_events();
  memset(timers, 0, sizeof timers); memset(pending, 0, sizeof pending);
  for (i = 16; i < 24; i++) S->r[i] = 0x1234567800000000ull + i;
  S->hi = 0x123456789abcdef0ull; S->lo = 0xfedcba9876543210ull;
  printf("{\"context\":[");
  for (i = 0; i < context_count; i++) printf("%s%u", i ? "," : "", context_log[i]);
  printf("],\"words\":[");
  for (i = 0; i < 16; i++) {
    const u32 *c = status_cases[batch * 16 + i];
    u32 old;
    S->cp0_status = c[0]; S->status_known = 1; S->mi_mask = c[1]; ints_enabled = c[0] & 1;
    wr32(global_a, c[2]); S->r[4] = c[3];
    assert(plaid_rt_osSetIntMask_global(S, global_a) == 0);
    old = (u32)S->r[2];
    assert(plaid_rt___osGetSR(S) == 0);
    printf("%s%u,%u,%u,%u", i ? "," : "", old, (u32)S->r[2], (u32)(S->r[2] >> 32), S->mi_mask);
  }
  puts("]}");
  for (i = 16; i < 24; i++) assert(S->r[i] == 0x1234567800000000ull + i);
  assert(S->hi == 0x123456789abcdef0ull && S->lo == 0xfedcba9876543210ull && S->fault == 0);
  return 0;
}
