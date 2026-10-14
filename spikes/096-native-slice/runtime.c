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
