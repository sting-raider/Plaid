/* Native-only vector entry. Translation faults are separate from source guards. */
int plaid_native_refill(plaid_state *s, u32 target) {
  u32 p, index, vector, code, m, lo;
  u8 seg;
  unsigned tries, i;
  if ((target & 3u) || (target >= 0x80000000u && target < 0xc0000000u)) return 0;
  if (!plaid_tlb_lookup(s, target, 0, &p, &seg, &index, 0, NULL)) return 0;
  if (s->native_refill_active || !s->status_known || (s->cp0_status & 6u))
    return plaid_fault(s, target, 12);
  for (tries = 0; tries < 8; tries++) {
    code = 2;
    int miss = 1;
    for (i = 0; i < 32; i++) {
      const plaid_tlb_entry *e = &s->tlb[i];
      if (plaid_cp0_entry(s, i, target)) return 1;
      m = e->mask | 0x1fffu;
      if ((target & ~m) != (e->hi & ~m)) continue;
      if (!(e->lo[0] & e->lo[1] & 1u)) {
        if (!(s->cp0_known & (1u << 10))) return plaid_fault(s, target, 12);
        if ((e->hi & 255u) != (s->cp0_entryhi & 255u)) continue;
      }
      lo = e->lo[(target & ((m >> 1) + 1)) != 0];
      if (lo & 2u) return plaid_fault(s, target, 12);
      miss = 0;
      break;
    }
    u32 previous_status = s->cp0_status;
    if (plaid_cp0_tlb_exception(s, SX32(target), target, 0, code, miss, &vector)) return 1;
    s->native_refill_status = previous_status;
    s->native_refill_epc = SX32(target);
    s->native_refill_active = 1;
    s->native_refill_resumed = 0;
    int result = plaid_native_vector(s, vector, s->native_refill_epc);
    s->native_refill_active = 0;
    if (result || !s->native_refill_resumed || (s->cp0_status & 2u))
      return result ? result : plaid_fault(s, vector, 12);
    if (!plaid_tlb_lookup(s, target, 0, &p, &seg, &index, 0, NULL)) return 0;
  }
  /* A bounded exception scope cannot certify an endless or redirecting pager. */
  return plaid_fault(s, target, 12);
}
