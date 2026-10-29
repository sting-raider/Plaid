/* ADR-0235: bounded kernel COP0 state. No guest instruction decoder. */
/* PCG sampler adapted from ares/ares/random.hpp at
   9408cb43d4948fc3ea6e152a307a34348df3fe04 (ISC):
   Copyright (c) 2004-2025 ares team, Near et al

   Permission to use, copy, modify, and/or distribute this software for any
   purpose with or without fee is hereby granted, provided that the above
   copyright notice and this permission notice appear in all copies.

   THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
   WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
   MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
   ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
   WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
   ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
   OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE. */
static inline u32 plaid_cp0_random_step(plaid_state *s) {
  u64 old = s->cp0_random_state;
  u32 bits = (u32)(((old >> 18) ^ old) >> 27), rotate = (u32)(old >> 59);
  s->cp0_random_state = old * 6364136223846793005ull + s->cp0_random_increment;
  return (bits >> rotate) | (bits << ((0u - rotate) & 31u));
}
static inline void plaid_cp0_random_seed(plaid_state *s, u64 seed, u64 sequence) {
  s->cp0_random_state = 0;
  s->cp0_random_increment = (sequence << 1) | 1u;
  (void)plaid_cp0_random_step(s);
  s->cp0_random_state += seed;
  (void)plaid_cp0_random_step(s);
  s->cp0_random_known = 1;
}
/* Pinned ares samples Random on each read/TLBWR, including Wired=31.
   This is its sampling model, not an instruction-clock approximation. */
static inline int plaid_cp0_random(plaid_state *s, u32 *index, u32 pc) {
  u64 sample;
  if (!(s->cp0_known & (1u << 6))) return plaid_fault(s, pc, 12);
  if (!s->cp0_random_known) {
    if (s->cp0_wired != 31u) return plaid_fault(s, pc, 12);
    *index = 31u; return 0;
  }
  sample = (u64)plaid_cp0_random_step(s) << 32;
  sample |= plaid_cp0_random_step(s);
  *index = s->cp0_wired > 31u ? (u32)sample & 63u :
           (u32)(sample % (32u - s->cp0_wired)) + s->cp0_wired;
  return 0;
}
static inline int plaid_cp0_kernel(plaid_state *s, u32 pc) {
  if (!s->status_known || (!(s->cp0_status & 6u) && (s->cp0_status & 0x18u)))
    return plaid_fault(s, pc, 12);
  return 0;
}
/* Effect witnesses are checked before a host call. An alias must use the
   callee's pinned mapping and the same physical source for every proof word. */
static inline int plaid_cp0_host_source(plaid_state *s, const u32 (*words)[2], u32 n,
                                        u32 delta, u32 tlb, u32 pc) {
  u32 j, p, index; u8 seg;
  for (j = 0; j < n; j++) {
    u32 q = words[j][0], w = words[j][1];
    if (tlb && (plaid_tlb_lookup(s, (q | 0x80000000u) + delta, 0, &p, &seg, &index, 0, NULL)
                || index + 1 != tlb || p != q)) return plaid_fault(s, pc, 12);
    if (((u32)s->ram[q] << 24 | (u32)s->ram[q+1] << 16 | (u32)s->ram[q+2] << 8 | s->ram[q+3]) != w)
      return plaid_fault(s, pc, 8);
  }
  return 0;
}
/* The SDK's queue division traps are outside its normal host ABI. Read the
   same raw queue field as that ABI, without inventing a guest memory access. */
static inline int plaid_cp0_host_queue(plaid_state *s, u32 pc) {
  u32 v = (u32)s->r[4] + 16u, p, index, count; u8 seg;
  if (v >= 0x80000000u && v < 0xc0000000u) p = v & 0x1fffffffu;
  else if (plaid_tlb_lookup(s,v,0,&p,&seg,&index,0,NULL)) return plaid_fault(s,pc,12);
  if ((v&3u) || p > PLAID_RAM_SIZE-4u) return plaid_fault(s,pc,12);
  count=(u32)s->ram[p]<<24 | (u32)s->ram[p+1]<<16 | (u32)s->ram[p+2]<<8 | s->ram[p+3];
  return !count || count > 0x7fffffffu ? plaid_fault(s,pc,12) : 0;
}
static inline int plaid_cp0_read(plaid_state *s, u32 reg, u64 *v, u32 pc) {
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (reg == 12) { *v = s->cp0_status; return 0; }
  if (reg == 1) { u32 index; if (plaid_cp0_random(s, &index, pc)) return 1; *v = index; return 0; }
  if (!(s->cp0_known & (1u << reg))) return plaid_fault(s, pc, 12);
  switch (reg) {
  case 0: *v = s->cp0_index; break;
  case 2: case 3: *v = s->cp0_tlb.lo[reg - 2]; break;
  case 4:
    if (!(s->cp0_readonly_known & (1u << 4))) return plaid_fault(s, pc, 12);
    *v = s->cp0_context; break;
  case 5: *v = s->cp0_tlb.mask; break;
  case 6: *v = s->cp0_wired; break;
  case 8: *v = s->cp0_badvaddr; break;
  case 10: *v = s->cp0_entryhi; break;
  case 13:
    if (s->cp0_interrupt_pending)
      s->cp0_cause = (s->cp0_cause & ~0xff00u) | (s->cp0_interrupt_pending(s) & 0xff00u);
    *v = s->cp0_cause; break;
  case 14: *v = s->cp0_epc; break;
  case 18: *v = s->cp0_watchlo; break;
  case 19: *v = 0; break;
  case 20:
    if (!(s->cp0_readonly_known & (1u << 20))) return plaid_fault(s, pc, 12);
    *v = s->cp0_xcontext; break;
  case 28: *v = s->cp0_taglo; break;
  case 29: *v = s->cp0_taghi; break;
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
  case 4:
    s->cp0_context = (s->cp0_context & 0x7ffff0ull) | (v & 0xffffffffff800000ull);
    break;
  case 5: s->cp0_tlb.mask = (u32)v & 0x01ffe000u; break;
  case 6: s->cp0_wired = (u32)v & 63u; break;
  case 10: s->cp0_entryhi = v & 0xc00000ffffffe0ffull; break;
  case 14: s->cp0_epc = v; break;
  /* WatchLo with neither R nor W set watches nothing, as libultra's
     osInitialize writes it; an armed watch is outside the subset (ADR-0260) */
  case 18:
    if (v & 3u) return plaid_fault(s, pc, 12);
    s->cp0_watchlo = (u32)v & 0xfffffff8u; break;
  case 19: break;
  case 20:
    s->cp0_xcontext = (s->cp0_xcontext & 0x1fffffff0ull) | (v & 0xfffffffe00000000ull);
    break;
  /* TagLo/TagHi feed CACHE Index Store Tag only (ADR-0259) */
  case 28: s->cp0_taglo = (u32)v & 0x0fffffc0u; break;
  case 29: s->cp0_taghi = 0; break;
  case 30: s->cp0_error_epc = v; break;
  case 12:
    if (s->native_refill_active) {
      /* A synchronous guest handler may mask interrupts and leave EXL while
         paging. It cannot enable delivery or select ErrorEPC in this scope. */
      if ((v & 0x030000fcu) || ((v & 1u) && !(v & 2u))) return plaid_fault(s,pc,12);
      s->cp0_status = ((u32)v & 0xff57ffffu) | (s->cp0_status & 0x00200000u);
      s->fr_mode = (s->cp0_status & 0x04000000u) ? 2 : 1;
      break;
    }
    /* SDK-owned code may change only FR. Interrupt/event and privilege state
       must be identical before accepting this write (ADR-0276). */
    if (s->status_thread) {
      if (((u32)v ^ s->cp0_status) & ~0x04000000u) return plaid_fault(s, pc, 12);
      s->cp0_status = (u32)v;
      s->fr_mode = (s->cp0_status & 0x04000000u) ? 2 : 1;
      break;
    }
    /* Timer/exception delivery and SDK scheduler Status writes need a separate
       contract. Reject before changing state, including FR. */
    if (((v ^ s->cp0_status) & 1u) || (v & 0x030000f8u) ||
        ((v & 1u) && !(v & 6u) && (v & 0xff00u))) return plaid_fault(s, pc, 12);
    s->cp0_status = ((u32)v & 0xff57ffffu) | (s->cp0_status & 0x00200000u);
    s->fr_mode = (s->cp0_status & 0x04000000u) ? 2 : 1;
    break;
  default: return plaid_fault(s, pc, 12);
  }
  s->cp0_known |= 1u << reg;
  return 0;
}
/* Address exception state, independent of vector execution. Call only after
   classifying a guest TLB miss/invalid/modification, never a source refusal.
   The bounded native address model is sign-extended 32-bit kernel mode. */
static inline int plaid_cp0_tlb_exception(plaid_state *s, u64 va, u32 pc,
                                         int delay, u32 code, int miss, u32 *vector) {
  u32 required = (1u << 4) | (1u << 10) | (1u << 20);
  u32 status = s->cp0_status, cause;
  if (!s->cp0_interrupt_pending || (status & 2u)) required |= 1u << 13;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if ((s->cp0_known & required) != required || (status & 0xe0u) ||
      va != SX32(va) || (pc & 3u) || (delay != 0 && delay != 1) ||
      code < 1 || code > 3 || (miss && code == 1) || (miss != 0 && miss != 1) ||
      ((status & 2u) && !(s->cp0_known & (1u << 14))))
    return plaid_fault(s, pc, 12);
  cause = (s->cp0_cause & 0x8000ff00u) | (code << 2);
  if (s->cp0_interrupt_pending)
    cause = (cause & ~0xff00u) | (s->cp0_interrupt_pending(s) & 0xff00u);
  if (!(status & 2u)) {
    s->cp0_epc = SX32(pc - (delay ? 4u : 0u));
    cause = (cause & ~0x80000000u) | (delay ? 0x80000000u : 0);
  }
  s->cp0_badvaddr = va;
  s->cp0_entryhi = (s->cp0_entryhi & 255u) | (va & 0xc00000ffffffe000ull);
  s->cp0_context = (s->cp0_context & 0xffffffffff800000ull) | ((va >> 9) & 0x7ffff0ull);
  s->cp0_xcontext = (s->cp0_xcontext & 0xfffffffe00000000ull) |
                    ((va >> 9) & 0x7ffffff0ull) | ((va >> 31) & 0x180000000ull);
  s->cp0_cause = cause;
  s->cp0_status = status | 2u;
  s->cp0_known |= (1u << 8) | (1u << 13) | (1u << 14);
  s->cp0_readonly_known |= (1u << 4) | (1u << 20);
  *vector = (status & 0x00400000u ? 0xbfc00200u : 0x80000000u) +
            (miss && !(status & 2u) ? 0 : 0x180u);
  s->pc = *vector;
  return 0;
}
/* Both architectural writes share staging normalization and source guards. */
static inline int plaid_cp0_tlbwrite(plaid_state *s, u32 index, u32 pc) {
  u32 pm, m; plaid_tlb_entry e;
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
  return plaid_tlb_write(s, index, e, pc);
}
static inline int plaid_cp0_tlbwi(plaid_state *s, u32 pc) {
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (!(s->cp0_known & 1u)) return plaid_fault(s, pc, 12);
  if ((s->cp0_index & 63u) >= 32) return 0;
  return plaid_cp0_tlbwrite(s, s->cp0_index, pc);
}
static inline int plaid_cp0_tlbwr(plaid_state *s, u32 pc) {
  u32 index; u64 before = s->cp0_random_state;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if (plaid_cp0_random(s, &index, pc)) return 1;
  if (index >= 32u) return 0;
  if (!plaid_cp0_tlbwrite(s, index, pc)) return 0;
  s->cp0_random_state = before;
  return 1;
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
  if (!(s->cp0_status & 6u) || !(s->cp0_known & (1u << reg)) ||
      (status & 0x030000f8u) ||
      (!s->native_refill_active && (s->status_thread ||
        ((status & 1u) && !(status & 6u) && (status & 0xff00u)))))
    return plaid_fault(s, pc, 12);
  t = reg == 30 ? s->cp0_error_epc : s->cp0_epc;
  if (t != SX32(t) || (t & 3u)) return plaid_fault(s, pc, 12);
  if (s->native_refill_active && (reg != 14 || t != s->native_refill_epc || status != s->native_refill_status))
    return plaid_fault(s, pc, 12);
  s->cp0_status = status; s->llbit = 0; s->pc = (u32)t;
  *target = t;
  return 0;
}
/* CACHE (ADR-0259). Native code fetches no guest instructions, so the
   I-cache operations change nothing observable; D-cache operations act on the
   modelled tags (ADR-0183). A dirty line dropped without write-back keeps its
   stores in RAM here but not on hardware: like osInvalDCache, it is marked
   lost so a later access fails closed. CDE retains known resident bytes;
   unavailable invalid-slot bytes stay unknown until written (ADR-0271).
   Index Load Tag and a valid Index Store Tag are outside the subset. */
static inline void plaid_ddrop(plaid_state *s, u32 i) {
  if (s->ddirty[i]) s->line_lost[((s->dtag[i] & ~0xfffu) | (i & 0xffu) << 4) >> 4] = 0xffffu;
  s->dtag[i] = 0; s->ddirty[i] = 0; s->dstale[i] = 0; s->dunknown[i] = 0;
}
static inline int plaid_cache(plaid_state *s, u32 op, u64 va, u32 pc) {
  u32 v = (u32)va, p, i = (v >> 4) & 0x1ffu;
  u8 seg;
  if (plaid_cp0_kernel(s, pc)) return 1;
  if ((op & 3u) == 0) return 0;
  if ((op & 3u) != 1) return plaid_fault(s, pc, 12);
  switch (op >> 2) {
  case 0: /* Index Writeback Invalidate */
    if (s->dtag[i]) plaid_dwriteback(s, (int)i);
    s->dtag[i] = 0; s->ddirty[i] = 0; s->dstale[i] = 0; s->dunknown[i] = 0;
    return 0;
  case 2: /* Index Store Tag, of an invalid line only */
    if (s->cp0_taglo & 0xc0u) return plaid_fault(s, pc, 12);
    plaid_ddrop(s, i);
    return 0;
  case 3: case 4: case 5: case 6: /* CDE and Hit operations */
    if (va != SX32(v)) return plaid_fault(s, pc, 1);
    if (v >= 0x80000000u && v < 0xc0000000u) p = v & 0x1fffffffu;
    else if (plaid_tlb(s, v, 0, &p, &seg)) return plaid_fault(s, pc, 1);
    if (op >> 2 == 3) { /* Create Dirty Exclusive: no RAM fill */
      u32 b, base = (s->dtag[i] & ~0xfffu) | (i & 0xffu) << 4;
      if (p >= PLAID_RAM_SIZE) return plaid_fault(s, pc, 1);
      if (s->dtag[i] != ((p & ~0xfffu) | 1)) {
        if (s->dtag[i ^ 0x100] == ((p & ~0xfffu) | 1)) return plaid_fault(s, pc, 4);
        if (plaid_protected(s, p & ~15u, 16, pc)) return plaid_fault(s, pc, 2);
        if (s->dtag[i]) {
          for (b = 0; b < 16; b++)
            if (!(s->dstale[i] >> b & 1)) s->dold[i][b] = s->ram[base + b];
          plaid_dwriteback(s, (int)i);
        } else s->dunknown[i] = 0xffffu;
        s->dtag[i] = (p & ~0xfffu) | 1; s->dstale[i] = 0xffffu;
      }
      s->ddirty[i] = 1;
      /* No destination RAM was read. Dirty residency guards it until writeback;
         unknown bytes still refuse reads and make an incomplete writeback lost. */
      s->line_lost[p >> 4] = 0;
      return 0;
    }
    if (p >= PLAID_RAM_SIZE || s->dtag[i] != ((p & ~0xfffu) | 1)) return 0;
    if (op >> 2 == 4) { plaid_ddrop(s, i); return 0; }
    plaid_dwriteback(s, (int)i);
    if (op >> 2 == 5) { s->dtag[i] = 0; s->ddirty[i] = 0; s->dstale[i] = 0; s->dunknown[i] = 0; }
    return 0;
  default:
    return plaid_fault(s, pc, 12);
  }
}
