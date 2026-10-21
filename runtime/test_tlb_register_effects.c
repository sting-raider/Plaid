/* Verify the host effects consumed by callee_effects.rs, including 64-bit GPRs.
   Argument loads are warmed before the snapshot; only TLB state may change. */
#define main runtime_main
#include "plaid_rt.c"
#undef main
#include <assert.h>

static plaid_state state, before;

static void prepare(void) {
  unsigned i;
  memset(&state, 0, sizeof state);
  S = &state;
  running = &boot;
  for (i = 0; i < 32; i++) {
    S->r[i] = 0x1234567800000000ull + i;
    S->f[i] = 0xabcdef0100000000ull + i;
  }
  S->r[0] = 0;
  S->r[29] = SX32(0x80007f00u);
  S->r[4] = 5; S->r[5] = 0; S->r[6] = 0xe0200000u; S->r[7] = 0x6000;
  S->pc = 0x80000100u; S->hi = 0x123456789abcdef0ull; S->lo = ~S->hi;
  wr32(0x80007f10u, 0xffffffffu); wr32(0x80007f14u, 0xffffffffu);
  assert(arg(4) == 0xffffffffu && arg(5) == 0xffffffffu);
}

static void unchanged_except_tlb(void) {
  memcpy(before.tlb, S->tlb, sizeof S->tlb);
  memcpy(before.tlb_generation, S->tlb_generation, sizeof S->tlb_generation);
  assert(memcmp(&before, S, sizeof before) == 0);
  assert(plaid_preempt == 0);
}

int main(void) {
  unsigned i;
  prepare(); before = state;
  assert(plaid_rt_osMapTLB(S) == 0);
  assert(S->tlb[5].hi == 0xe0200000u && S->tlb[5].lo[0] == ((0x6000u >> 6) | 31u));
  assert(S->tlb[5].lo[1] == 1 && S->tlb_generation[5] == 1);
  unchanged_except_tlb();
  before = state;
  assert(plaid_rt_osUnmapTLB(S) == 0);
  assert(S->tlb[5].hi == 0x80000000u && S->tlb[5].lo[0] == 0 && S->tlb_generation[5] == 2);
  unchanged_except_tlb();
  before = state;
  assert(plaid_rt_osUnmapTLBAll(S) == 0);
  for (i = 0; i < 32; i++) {
    assert(S->tlb[i].hi == 0x80000000u && S->tlb[i].lo[0] == 0 && S->tlb[i].lo[1] == 0);
    assert(S->tlb_generation[i] == before.tlb_generation[i] + 1);
  }
  unchanged_except_tlb();
  puts("TLB host effects: all GPR/FPR, PC, HI/LO, RAM and event state preserved; only TLB/generations change");
  return 0;
}
