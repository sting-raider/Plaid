/* Host runtime functions for spike096 (ADR-0129). Each implements a declared
   guest function under the o32 ABI: arguments in a0-a3, result in v0;
   caller-saved registers are unspecified on return, callee-saved preserved. */

/* sum(a0 = bytes, a1 = count): v0 = sum of the bytes. */
int plaid_rt_sum(plaid_state *s) {
  u64 total = 0, b;
  u64 i;
  for (i = 0; (s64)i < (s64)s->r[5]; i++) {
    if (plaid_load(s, s->r[4] + i, 1, 0, &b)) return 1;
    total += b;
  }
  s->r[2] = SX32((u32)total);
  return 0;
}

/* spawn(a0 = guest function, a1 = argument): v0 = fn(a1) + 1. The guest
   function is entered through plaid_enter, which admits only proven callbacks. */
int plaid_rt_spawn(plaid_state *s) {
  const u64 host = 0xffffffffbfc00000ull; /* return sentinel outside guest code */
  u64 ra = s->r[31];
  u32 fn = (u32)s->r[4];
  int r;
  s->r[4] = s->r[5];
  s->r[31] = host;
  r = plaid_enter(s, fn, host);
  if (r) return r;
  s->r[31] = ra;
  s->r[2] = SX32((u32)s->r[2] + 1);
  return 0;
}

/* Every safepoint calls the runtime (ADR-0159); it must leave guest state
   exactly as ares does, so it only counts. */
volatile int plaid_preempt = 1;
static unsigned long plaid_safepoints;
int plaid_rt_safepoint(plaid_state *s) {
  (void)s;
  plaid_safepoints++;
  return 0;
}

/* map(a0 = index, a1 = PageMask, a2 = EntryHi, a3 = EntryLo0,
   16(sp) = EntryLo1): the TLBWI the guest body performs (ADR-0162). */
int plaid_rt_map(plaid_state *s) {
  u64 lo1;
  if (plaid_load(s, s->r[29] + 16, 4, 0, &lo1)) return 1;
  s->tlb[s->r[4] & 31] = (plaid_tlb_entry){(u32)s->r[5], (u32)s->r[6], {(u32)s->r[7], (u32)lo1}};
  return 0;
}
