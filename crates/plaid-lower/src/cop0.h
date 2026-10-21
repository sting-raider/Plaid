/* ADR-0235: bounded kernel COP0 state. No guest instruction decoder. */
static inline int plaid_cp0_kernel(plaid_state *s, u32 pc) {
  if (!s->status_known || (!(s->cp0_status & 6u) && (s->cp0_status & 0x18u)))
    return plaid_fault(s, pc, 12);
  return 0;
}
static inline int plaid_cp0_read(plaid_state *s, u32 reg, u64 *v, u32 pc) {
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (reg == 12) { *v = s->cp0_status; return 0; }
  if (!(s->cp0_known & (1u << reg))) return plaid_fault(s, pc, 12);
  switch (reg) {
  case 0: *v = s->cp0_index; break;
  case 2: case 3: *v = s->cp0_tlb.lo[reg - 2]; break;
  case 5: *v = s->cp0_tlb.mask; break;
  case 6: *v = s->cp0_wired; break;
  case 10: *v = s->cp0_entryhi; break;
  case 14: *v = s->cp0_epc; break;
  case 30: *v = s->cp0_error_epc; break;
  default: return plaid_fault(s, pc, 12);
  }
  return 0;
}
static inline int plaid_cp0_write(plaid_state *s, u32 reg, u64 v, u32 pc) {
  if (plaid_cp0_kernel(s, pc)) return 1;
  switch (reg) {
  case 0: s->cp0_index = (u32)v & 0x8000003fu; break;
  case 2: case 3: s->cp0_tlb.lo[reg - 2] = (u32)v & 0x3fffffffu; break;
  case 5: s->cp0_tlb.mask = (u32)v & 0x01ffe000u; break;
  case 6: s->cp0_wired = (u32)v & 63u; break;
  case 10: s->cp0_entryhi = v & 0xc00000ffffffe0ffull; break;
  case 14: s->cp0_epc = v; break;
  case 30: s->cp0_error_epc = v; break;
  case 12:
    /* Timer/exception delivery and SDK scheduler Status writes need a separate
       contract. Reject before changing state, including FR. */
    if (s->status_thread || ((v ^ s->cp0_status) & 1u) || (v & 0x030000f8u) ||
        ((v & 1u) && !(v & 6u) && (v & 0xff00u))) return plaid_fault(s, pc, 12);
    s->cp0_status = ((u32)v & 0xff57ffffu) | (s->cp0_status & 0x00200000u);
    s->fr_mode = (s->cp0_status & 0x04000000u) ? 2 : 1;
    break;
  default: return plaid_fault(s, pc, 12);
  }
  s->cp0_known |= 1u << reg;
  return 0;
}
static inline int plaid_cp0_tlbwi(plaid_state *s, u32 pc) {
  u32 pm, m; plaid_tlb_entry e;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (!(s->cp0_known & 1u)) return plaid_fault(s, pc, 12);
  if ((s->cp0_index & 63u) >= 32) return 0;
  if ((s->cp0_known & 0x42cu) != 0x42cu) return plaid_fault(s, pc, 12);
  /* The existing native model supports global 32-bit mappings only. Preserve
     full staging register values, but refuse unsupported committed mappings. */
  if (s->cp0_entryhi != (SX32(s->cp0_entryhi) & 0xc00000ffffffe0ffull) ||
      !(s->cp0_tlb.lo[0] & s->cp0_tlb.lo[1] & 1u)) return plaid_fault(s, pc, 12);
  pm = s->cp0_tlb.mask & (0xaaau << 13); pm |= pm >> 1;
  m = pm | 0x1fffu;
  e = s->cp0_tlb; e.mask = pm; e.hi = (u32)s->cp0_entryhi & ~m;
  e.hi |= (u32)s->cp0_entryhi & 255u;
  e.lo[0] &= 0x03ffffffu; e.lo[1] &= 0x03ffffffu;
  return plaid_tlb_write(s, s->cp0_index, e, pc);
}
/* Host boundaries can also populate the shared table. Refuse a raw entry
   that cannot represent a normalized VR4300 mapping before observing it. */
static inline int plaid_cp0_entry(plaid_state *s, u32 i, u32 pc) {
  const plaid_tlb_entry *e = &s->tlb[i];
  u32 pm = e->mask & (0xaaau << 13); pm |= pm >> 1;
  if (!s->tlb_generation[i] || e->mask != pm || (e->hi & (pm | 0x1f00u)) ||
      ((e->lo[0] | e->lo[1]) & 0xfc000000u) || ((e->lo[0] ^ e->lo[1]) & 1u))
    return plaid_fault(s, pc, 12);
  return 0;
}
static inline int plaid_cp0_tlbr(plaid_state *s, u32 pc) {
  u32 i;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (!(s->cp0_known & 1u)) return plaid_fault(s, pc, 12);
  i = s->cp0_index & 63u;
  if (i >= 32) return 0;
  if (plaid_cp0_entry(s, i, pc)) return 1;
  s->cp0_tlb = s->tlb[i];
  s->cp0_entryhi = SX32(s->tlb[i].hi) & 0xc00000ffffffe0ffull;
  s->cp0_known |= 0x42cu;
  return 0;
}
static inline int plaid_cp0_tlbp(plaid_state *s, u32 pc) {
  u32 i, m;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (!(s->cp0_known & 0x400u)) return plaid_fault(s, pc, 12);
  for (i = 0; i < 32; i++) if (plaid_cp0_entry(s, i, pc)) return 1;
  for (i = 0; i < 32; i++) {
    const plaid_tlb_entry *e = &s->tlb[i];
    m = e->mask | 0x1fffu;
    if ((SX32(e->hi) & 0xc00000ffffffe000ull & ~(u64)m) !=
        (s->cp0_entryhi & 0xc00000ffffffe000ull & ~(u64)m)) continue;
    if (!(e->lo[0] & e->lo[1] & 1u) && (e->hi & 255u) != (s->cp0_entryhi & 255u)) continue;
    s->cp0_index = i; s->cp0_known |= 1u; return 0;
  }
  s->cp0_index = 0x80000000u; s->cp0_known |= 1u;
  return 0;
}

/* HLE does not enter guest vectors or establish EPC. Only explicit guest
   register writes outside SDK contexts can establish this bounded return. */
static inline int plaid_cp0_eret(plaid_state *s, u64 *target, u32 pc) {
  u32 status, reg; u64 t;
  if (plaid_cp0_kernel(s, pc)) return 1;
  reg = (s->cp0_status & 4u) ? 30 : 14;
  status = s->cp0_status & ~((reg == 30) ? 4u : 2u);
  if (s->status_thread || !(s->cp0_status & 6u) ||
      !(s->cp0_known & (1u << reg)) || (status & 0x030000f8u) ||
      ((status & 1u) && !(status & 6u) && (status & 0xff00u)))
    return plaid_fault(s, pc, 12);
  t = reg == 30 ? s->cp0_error_epc : s->cp0_epc;
  if (t != SX32(t) || (t & 3u)) return plaid_fault(s, pc, 12);
  s->cp0_status = status; s->llbit = 0; s->pc = (u32)t;
  *target = t;
  return 0;
}
