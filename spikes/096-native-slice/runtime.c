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
