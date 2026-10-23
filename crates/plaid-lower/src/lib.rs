//! Synthetic-only native vertical slice (ADR-0125, ADR-0126).
//!
//! Lowers a program the solver reports CLOSED under the declared-static-image
//! scope to one self-contained C translation unit. Every reachable block is a
//! C label, direct transfers are `goto`s and indirect jumps dispatch only over
//! their proven target sets. No guest decoder or interpreter is emitted: an
//! instruction outside the supported integer subset rejects the whole program.
use plaid_core::{
    GuestAddr,
    discovery::CodeImage,
    program::{BasicBlock, EdgeKind, ProgramMap},
    returns,
    solver::{ClosureStatus, Scope, solve},
};
use std::collections::{BTreeMap, BTreeSet};

pub mod coverage;
pub mod overlay;
pub mod rsp;

const PRELUDE: &str = r#"#include <stdint.h>
#include <string.h>
#include <fenv.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32;
typedef uint64_t u64; typedef int64_t s64;
#define PLAID_RAM_SIZE 0x800000u
/* one TLB entry as TLBWI writes it: PageMask, EntryHi, EntryLo0/1 (ADR-0162) */
typedef struct { u32 mask, hi, lo[2]; } plaid_tlb_entry;
typedef struct { u32 start, end; } plaid_text_range;
typedef struct plaid_native_frame_s {
  struct plaid_native_frame_s *prev, *next;
  const plaid_text_range *ranges; u32 count;
} plaid_native_frame;
typedef struct plaid_state_s {
  u64 r[32]; u64 hi, lo; u64 f[32]; u32 fcc; u32 fcsr; u32 llbit; u32 pc; u32 fault; u32 fault_pc;
  /* Live Status comes from a post-IPL receipt or verified SDK context. */
  u32 cp0_status, status_known, status_thread, mi_mask;
  /* Known Status.FR: 2 = FR 1, 1 = FR 0, 0 = unchecked bare harness.
     Boot receipts, native Status writes and SDK restores establish it. */
  u32 fr_mode;
  u32 cp0_known, cp0_index, cp0_wired, cp0_taglo, cp0_taghi, cp0_watchlo;
  u64 cp0_entryhi, cp0_epc, cp0_error_epc; plaid_tlb_entry cp0_tlb;
  u8 ram[PLAID_RAM_SIZE];
  /* The VR4300 D-cache as pinned ares models it (ADR-0183): 512 direct-mapped
     16-byte lines indexed by virtual address bits 4-12; dtag holds a resident
     line's physical page | 1. RAM holds the latest store: ddirty marks a
     resident line with stores hardware has not yet written back, dstale the
     bytes whose cached copy is older than RAM (an uncached store or DMA
     since), dold those older bytes, and line_lost a RAM line holding stores
     hardware discarded. */
  u32 dtag[512]; u8 ddirty[512]; u16 dstale[512]; u8 dold[512][16];
  u8 line_lost[PLAID_RAM_SIZE / 16];
  u8 load_ok[64]; /* declared load verified in RAM (ADR-0136) */
  /* Per RAM word: 0 data, 1 fixed text, 2+n declared load n,
     253 immutable proof data, 254 revoked fixed text, 255 bound overlay. */
  u8 prot[PLAID_RAM_SIZE / 4]; u8 prot_ready, text_dirty;
  plaid_native_frame *native_frames; /* includes suspended SDK threads */
  plaid_tlb_entry tlb[32]; /* written by the runtime's osMapTLB family */
  u64 tlb_generation[32];
  /* uncached access to RCP memory, registers and the PI buses (physical
     0x04000000-0x1fffffff), set by the runtime: 0 done, else fault 1;
     NULL leaves them all faulting (ADR-0177) */
  int (*io)(struct plaid_state_s *s, u32 p, u32 size, int write, u64 *value);
  /* relocatable overlay n runs at link + ovl_delta[n] while ovl_ok[n]: a
     binding made by byte verification, revoked by a write into its text
     (prot 255) (ADR-0181) */
  u32 ovl_delta[1024]; u8 ovl_ok[1024];
  u32 ovl_backing[1024], ovl_tlb[1024]; u64 ovl_generation[1024];
  u32 ovl_active[1024]; /* native frames pin their overlay binding (ADR-0187) */
} plaid_state;
/* A host runtime with preemptive scheduling builds with PLAID_SAFEPOINTS and
   defines both names; every loop header checks plaid_preempt (ADR-0159). */
#ifdef PLAID_SAFEPOINTS
extern volatile int plaid_preempt;
int plaid_rt_safepoint(plaid_state *s);
#define PLAID_SAFEPOINT(s) do { if (plaid_preempt) { int r_ = plaid_rt_safepoint(s); if (r_) return r_; } } while (0)
#else
#define PLAID_SAFEPOINT(s) ((void)0)
#endif
/* executable bytes; load: index of the declared load holding them, or -1 */
typedef struct { u32 start, end; int load; } plaid_range;
#define SX32(v) ((u64)(s64)(s32)(u32)(v))
/* fault 1: address/alignment outside the supported model; 2: store to
   active native text or immutable proof data; 3: transfer without a proven target;
   4: an RDRAM access whose result depends on D-cache state: uncached
   (KSEG1) to a resident line with stores not yet written back, cached to a
   resident line RAM has overtaken, a line resident at two indexes, or a
   line holding stores the cache discarded (ADR-0183);
   5: a return whose $ra is not the continuation of the call that entered
   its function (the checked call/return assumption);
   6: an overflow-trapping add/subtract that would raise an exception;
   7: a COP1 operation outside the modeled subset: a NaN or subnormal
      operand, an out-of-range conversion, or an enabled FPU exception;
   8: fixed text or code of a declared load entered while RAM does not hold
      its compiled bytes. Writes into a load revoke its verification, so entry compares
      again (ADR-0161); a write by the load's own code into it faults 2;
   9: a BREAK was reached (its exception handler is not modeled);
   10: a conditional trap was taken (its exception handler is not modeled);
   11: Status observation/acquisition outside the supported SDK context;
   12: COP0 state, mode or event effects outside the verified subset. */
static inline int plaid_fault(plaid_state *s, u32 pc, u32 code) {
  s->fault = code; s->fault_pc = pc; return 1;
}
/* The declared SDK ABI handles lazy COP1 acquisition before resuming an
   instruction. Track its visible CU1 effect; an incompatible FR mode faults. */
int plaid_status_acquire(plaid_state *s, u32 pc);
/* CFC1/CTC1 use CU1 but do not address the FR-dependent FPR layout. */
static inline int plaid_status_cop1(plaid_state *s, u32 pc) {
  if (s->status_known && !(s->cp0_status & 0x20000000u)) return plaid_status_acquire(s, pc);
  return 0;
}
static inline int plaid_status_fp(plaid_state *s, u32 pc, int fr0) {
  if (s->status_known) {
    if (((s->cp0_status >> 26) & 1) == (u32)fr0) return plaid_fault(s, pc, 11);
  } else if (s->fr_mode && s->fr_mode != (fr0 ? 1u : 2u)) return plaid_fault(s, pc, 11);
  return plaid_status_cop1(s, pc);
}
"#;

const BUILD_PROT: &str = r#"/* Executable ranges are word-aligned, so a per-word map answers the same
   overlap question as scanning plaid_code, in constant time (ADR-0159). */
static void plaid_build_prot(plaid_state *s) {
  u32 i, w;
  for (i = 0; i < sizeof plaid_code / sizeof plaid_code[0]; i++)
    for (w = plaid_code[i].start >> 2; w < (plaid_code[i].end + 3) >> 2 && w < PLAID_RAM_SIZE / 4; w++)
      if (s->prot[w] != 253 && (s->prot[w] != 1 || plaid_code[i].load == -2)) s->prot[w] = plaid_code[i].load == -2 ? 253 : plaid_code[i].load < 0 ? 1 : (u8)(2 + plaid_code[i].load);
  s->prot_ready = 1;
}
"#;

const COP0: &str = include_str!("cop0.h");

const HELPERS: &str = r#"/* Native frames pin their fixed-text bodies; one suspended at a call pins only
   the continuation it can still run (ADR-0239).
   The intrusive list permits SDK threads to suspend/resume out of stack order. */
/* Keep the intentional stack-frame registration out of GCC's dangling-pointer
   heuristic; the wrapper always unregisters before its local frame expires. */
#if defined(__GNUC__)
__attribute__((noinline, unused))
#endif
static void plaid_text_pin(plaid_state *s, plaid_native_frame *f) {
  f->prev = 0; f->next = s->native_frames;
  if (f->next) f->next->prev = f;
  s->native_frames = f;
}
static inline void plaid_text_unpin(plaid_state *s, plaid_native_frame *f) {
  if (f->prev) f->prev->next = f->next; else s->native_frames = f->next;
  if (f->next) f->next->prev = f->prev;
}
static inline int plaid_text_active(plaid_state *s, u32 p, u32 size) {
  plaid_native_frame *f; u32 i;
  for (f = s->native_frames; f; f = f->next)
    for (i = 0; i < f->count; i++)
      if (p < f->ranges[i].end && p + size > f->ranges[i].start) return 1;
  return 0;
}
/* Only revoked words need comparing; changed text is never executed. */
static inline int plaid_text_enter(plaid_state *s, u32 p, const u32 *words, u32 count, u32 pc) {
  u32 i, j;
  if (!s->text_dirty) return 0;
  for (i = 0; i < count; i++) if (s->prot[(p >> 2) + i] == 254) {
    for (j = 0; j < 4; j++)
      if (s->ram[p + 4 * i + j] != (u8)(words[i] >> (24 - 8 * j))) return plaid_fault(s, pc, 8);
    s->prot[(p >> 2) + i] = 1;
  }
  return 0;
}
/* Proof-bearing data and active native text refuse writes. Inactive text
   revokes its byte verification; the next entry checks it again (ADR-0219). */
int plaid_ovl_write(plaid_state *s, u32 p, u32 pc);
u32 plaid_link(plaid_state *s, u32 t);
int plaid_tlb_write(plaid_state *s, u32 index, plaid_tlb_entry entry, u32 pc);
int plaid_tlb_clear(plaid_state *s, u32 pc);
static inline int plaid_protected(plaid_state *s, u32 p, u32 size, u32 pc) {
  u32 w, q = pc & 0x1fffffffu;
  u8 own = 0, k;
  if (!s->prot_ready) plaid_build_prot(s);
  if (pc >= 0x80000000u && pc < 0xc0000000u && q < PLAID_RAM_SIZE) own = s->prot[q >> 2];
  for (w = p >> 2; w <= (p + size - 1) >> 2; w++) {
    k = s->prot[w];
    if (k == 253) return 1; /* proof-bearing base data */
    if (k == 1 || k == 254) {
      if (plaid_text_active(s, w << 2, 4)) return 1;
      s->prot[w] = 254; s->text_dirty = 1;
      continue;
    }
    if (k == 255) {
      if (plaid_ovl_write(s, w << 2, pc)) return 1;
      continue;
    }
    if (k > 1 && s->load_ok[k - 2]) {
      if (k == own || plaid_text_active(s, w << 2, 4)) return 1;
      s->load_ok[k - 2] = 0;
    }
  }
  return 0;
}
/* The instruction word of bound overlay n at link address pc, as RAM holds
   it: relocated immediates are read from the bytes the game's loader wrote
   (ADR-0181). */
static inline u32 plaid_ow(plaid_state *s, u32 n, u32 pc) {
  const u8 *m = s->ram + (pc + s->ovl_backing[n]);
  return (u32)m[0] << 24 | (u32)m[1] << 16 | (u32)m[2] << 8 | m[3];
}
/* Mapped data (KUSEG, KSSEG, KSEG3) through the TLB as pinned ares matches
   it (tlb.cpp): the first entry whose VPN2 matches decides. Only global
   entries are modeled, so a matching entry with an ASID fails closed, as do
   an invalid page and a store to a clean one (ADR-0162). The D-cache is
   indexed by vaddr[12:4], so a 4 KiB page whose virtual bit 12 differs from
   its physical one caches the line at another index: class 3. */
static inline int plaid_tlb_lookup(plaid_state *s, u32 v, int write, u32 *p, u8 *seg, u32 *index,
                                   u32 changed, const plaid_tlb_entry *replacement) {
  u32 i, pm, m, lo;
  for (i = 0; i < 32; i++) {
    const plaid_tlb_entry *e = replacement && i == changed ? replacement : &s->tlb[i];
    pm = e->mask & (0xaaau << 13);
    m = pm | pm >> 1 | 0x1fffu;
    if ((v & ~m) != (e->hi & ~m)) continue;
    if (!(e->lo[0] & e->lo[1] & 1)) return 1;
    lo = e->lo[(v & ((m >> 1) + 1)) != 0];
    if (!(lo & 2) || (write && !(lo & 4))) return 1;
    *p = (((lo >> 6) & 0xffffffu) << 12) + (v & (m >> 1));
    *seg = ((lo >> 3) & 7) == 2 ? 2 : (v ^ *p) & 0x1000u ? 3 : 1;
    *index = i;
    return 0;
  }
  return 1;
}
static inline int plaid_tlb(plaid_state *s, u32 v, int write, u32 *p, u8 *seg) {
  u32 index;
  return plaid_tlb_lookup(s, v, write, p, seg, &index, 0, NULL);
}
/* RAM under slot i's bytes m is about to change without the cache: keep the
   cached bytes, which RAM still holds, as the line's older copy (ADR-0183) */
static inline void plaid_dstale(plaid_state *s, int i, u32 p, u16 m) {
  u32 b, base = p & ~15u;
  for (b = 0; b < 16; b++)
    if ((m >> b & 1) && !(s->dstale[i] >> b & 1)) s->dold[i][b] = s->ram[base + b];
  s->dstale[i] |= m;
}
/* Write slot i back: a dirty line's older bytes go over RAM, as hardware
   writes the whole cached line */
static inline void plaid_dwriteback(plaid_state *s, int i) {
  u32 b, base = (s->dtag[i] & ~0xfffu) | ((u32)i & 0xffu) << 4;
  if (s->ddirty[i] && s->dstale[i])
    for (b = 0; b < 16; b++)
      if (s->dstale[i] >> b & 1) s->ram[base + b] = s->dold[i][b];
  if (s->ddirty[i]) s->dstale[i] = 0;
  s->ddirty[i] = 0;
}
/* The D-cache slot holding physical line p, or -1: an index's bits 4-11
   are p's, bit 12 is the virtual address's own (ADR-0183) */
static inline int plaid_dresident(plaid_state *s, u32 p) {
  u32 t = (p & ~0xfffu) | 1, i = (p >> 4) & 0xffu;
  if (s->dtag[i] == t) return (int)i;
  if (s->dtag[i | 0x100u] == t) return (int)(i | 0x100u);
  return -1;
}
static inline int plaid_addr(plaid_state *s, u64 va, u32 size, u32 pc, int write, u32 *out) {
  u32 v = (u32)va, p;
  u8 seg;
  if (va != SX32(v) || (v & (size - 1))) return plaid_fault(s, pc, 1);
  if (v >= 0x80000000u && v < 0xc0000000u) {
    p = v & 0x1fffffffu;
    seg = v < 0xa0000000u ? 1 : 2;
  } else if (plaid_tlb(s, v, write, &p, &seg)) {
    return plaid_fault(s, pc, 1);
  }
  if (p > PLAID_RAM_SIZE - size) {
    if (s->io && seg == 2 && p >= 0x04000000u && p < 0x20000000u) { *out = p; return 2; }
    return plaid_fault(s, pc, 1);
  }
  /* The cache as hardware has it (ADR-0183): a miss writes the old line
     back and fills (write-allocate); a cached read of a stale byte returns
     the older cached copy (3: plaid_load reads it); a cached store makes its
     bytes current. Faults: an uncached access to a dirty resident line,
     whose stores hardware's RAM lacks, a line resident at both indexes, and
     a lost line. */
  if (s->line_lost[p >> 4]) return plaid_fault(s, pc, 4);
  {
    u16 m = (u16)(((1u << size) - 1) << (p & 15));
    if (seg == 2) {
      int i = plaid_dresident(s, p);
      if (i >= 0) {
        if (s->ddirty[i]) return plaid_fault(s, pc, 4);
        if (write) plaid_dstale(s, i, p, m);
      }
    } else {
      u32 i = (v >> 4) & 0x1ffu, t = (p & ~0xfffu) | 1;
      if (s->dtag[i] != t) {
        if (s->dtag[i ^ 0x100] == t) return plaid_fault(s, pc, 4);
        if (s->dtag[i]) plaid_dwriteback(s, (int)i);
        s->dtag[i] = t; s->ddirty[i] = 0; s->dstale[i] = 0;
      } else if (!write && (s->dstale[i] & m)) { *out = p; return 3; }
      if (write) { s->ddirty[i] = 1; s->dstale[i] &= (u16)~m; }
    }
  }
  if (write && plaid_protected(s, p, size, pc)) return plaid_fault(s, pc, 2);
  *out = p; return 0;
}
/* COP1 arithmetic (ADR-0139), following pinned ares: fcsr holds FCSR bits
   0-17 and 24 (bit 23 is fcc); the host FPU rounds by FCSR.RM. */
#define PLAID_FS (1u << 24)
static inline int plaid_f32_bad(u32 b) {
  u32 e = b & 0x7f800000u, m = b & 0x7fffffu;
  return m && (e == 0x7f800000u || e == 0);
}
static inline int plaid_f64_bad(u64 b) {
  u64 e = b & 0x7ff0000000000000ull, m = b & 0xfffffffffffffull;
  return m && (e == 0x7ff0000000000000ull || e == 0);
}
static inline float plaid_f32(u32 b) { float f; memcpy(&f, &b, 4); return f; }
static inline double plaid_f64(u64 b) { double d; memcpy(&d, &b, 8); return d; }
static inline u32 plaid_b32(float f) { u32 b; memcpy(&b, &f, 4); return b; }
static inline u64 plaid_b64(double d) { u64 b; memcpy(&b, &d, 8); return b; }
/* host exception flags -> FCSR cause and sticky flags (ares checkFPUExceptions) */
static inline int plaid_fpe(plaid_state *s, int e, u32 pc) {
  u32 cause = 0;
  if (!e) return 0;
  if ((e & FE_UNDERFLOW) && (!(s->fcsr & PLAID_FS) || (s->fcsr & 0x180u))) return plaid_fault(s, pc, 7);
  if (e & FE_INEXACT) cause |= 1u << 12;
  if (e & FE_UNDERFLOW) cause |= 1u << 13;
  if (e & FE_OVERFLOW) cause |= 1u << 14;
  if (e & FE_DIVBYZERO) cause |= 1u << 15;
  if (e & FE_INVALID) cause |= 1u << 16;
  s->fcsr |= cause;
  if (cause & (s->fcsr << 5)) return plaid_fault(s, pc, 7); /* enables 7-11 */
  s->fcsr |= cause >> 10;
  return 0;
}
/* subnormal results flush per FCSR.RM when FS is set; NaN becomes ares's default NaN */
static inline int plaid_out32(plaid_state *s, u32 *b, u32 pc) {
  if (!(*b & 0x7f800000u) && (*b & 0x7fffffu)) {
    if (!(s->fcsr & PLAID_FS) || (s->fcsr & 0x180u)) return plaid_fault(s, pc, 7);
    s->fcsr |= 0x3000u | (0x3000u >> 10);
    switch (s->fcsr & 3) {
    case 2: *b = *b >> 31 ? 0x80000000u : 0x00800000u; break;
    case 3: *b = *b >> 31 ? 0x80800000u : 0; break;
    default: *b &= 0x80000000u;
    }
  } else if ((*b & 0x7f800000u) == 0x7f800000u && (*b & 0x7fffffu)) *b = 0x7fbfffffu;
  return 0;
}
static inline int plaid_out64(plaid_state *s, u64 *b, u32 pc) {
  if (!(*b & 0x7ff0000000000000ull) && (*b & 0xfffffffffffffull)) {
    if (!(s->fcsr & PLAID_FS) || (s->fcsr & 0x180u)) return plaid_fault(s, pc, 7);
    s->fcsr |= 0x3000u | (0x3000u >> 10);
    switch (s->fcsr & 3) {
    case 2: *b = *b >> 63 ? 0x8000000000000000ull : 0x0010000000000000ull; break;
    case 3: *b = *b >> 63 ? 0x8010000000000000ull : 0; break;
    default: *b &= 0x8000000000000000ull;
    }
  } else if ((*b & 0x7ff0000000000000ull) == 0x7ff0000000000000ull && (*b & 0xfffffffffffffull))
    *b = 0x7ff7ffffffffffffull;
  return 0;
}
/* ADD SUB MUL DIV SQRT ABS NEG .S (op = function field); writes clear the upper word */
static inline int plaid_arith_s(plaid_state *s, u32 op, u32 fd, u32 fs, u32 ft, u32 pc) {
  u32 x = (u32)s->f[fs], y = (u32)s->f[ft], r; int e = 0;
  volatile float a, b, z;
  s->fcsr &= ~0x3f000u;
  if (plaid_f32_bad(x) || (op < 4 && plaid_f32_bad(y))) return plaid_fault(s, pc, 7);
  if (op == 5 || op == 7) { s->f[fd] = op == 5 ? x & 0x7fffffffu : x ^ 0x80000000u; return 0; }
  a = plaid_f32(x); b = plaid_f32(y);
  feclearexcept(FE_ALL_EXCEPT);
  switch (op) {
  case 0: z = a + b; break;
  case 1: z = a - b; break;
  case 2: z = a * b; break;
  case 3: z = a / b; break;
  default: if (a < 0) { z = plaid_f32(0x7fc00000u); e = FE_INVALID; } else z = __builtin_sqrtf(a);
  }
  e |= fetestexcept(FE_ALL_EXCEPT);
  r = plaid_b32(z);
  if (plaid_fpe(s, e, pc) || plaid_out32(s, &r, pc)) return 1;
  s->f[fd] = r; return 0;
}
static inline int plaid_arith_d(plaid_state *s, u32 op, u32 fd, u32 fs, u32 ft, u32 pc) {
  u64 x = s->f[fs], y = s->f[ft], r; int e = 0;
  volatile double a, b, z;
  s->fcsr &= ~0x3f000u;
  if (plaid_f64_bad(x) || (op < 4 && plaid_f64_bad(y))) return plaid_fault(s, pc, 7);
  if (op == 5 || op == 7) { s->f[fd] = op == 5 ? x & ~(1ull << 63) : x ^ (1ull << 63); return 0; }
  a = plaid_f64(x); b = plaid_f64(y);
  feclearexcept(FE_ALL_EXCEPT);
  switch (op) {
  case 0: z = a + b; break;
  case 1: z = a - b; break;
  case 2: z = a * b; break;
  case 3: z = a / b; break;
  default: if (a < 0) { z = plaid_f64(0x7ff8000000000000ull); e = FE_INVALID; } else z = __builtin_sqrt(a);
  }
  e |= fetestexcept(FE_ALL_EXCEPT);
  r = plaid_b64(z);
  if (plaid_fpe(s, e, pc) || plaid_out64(s, &r, pc)) return 1;
  s->f[fd] = r; return 0;
}
/* CVT/ROUND/TRUNC/CEIL/FLOOR to W or L (wide), rounding by rm (0 nearest even,
   1 zero, 2 up, 3 down): exact, without libm; inexact iff a fraction remains.
   Input ranges are ares's: |x| < 2^31 for W, |x| < 2^53 for L. */
static inline int plaid_to_int(plaid_state *s, double x, int bad, u32 rm, int wide, u32 fd, u32 pc) {
  long long t; double frac;
  s->fcsr &= ~0x3f000u;
  if (bad || (wide ? !(x < 9007199254740992.0 && x > -9007199254740992.0)
                   : !(x < 2147483648.0 && x >= -2147483648.0)))
    return plaid_fault(s, pc, 7);
  t = (long long)x; frac = x - (double)t;
  switch (rm) {
  case 0: if (frac > 0.5 || (frac == 0.5 && (t & 1))) t++; else if (frac < -0.5 || (frac == -0.5 && (t & 1))) t--; break;
  case 2: if (frac > 0) t++; break;
  case 3: if (frac < 0) t--; break;
  }
  if (!wide && (t > 2147483647ll || t < -2147483647ll - 1)) return plaid_fault(s, pc, 7);
  if (frac != 0) {
    s->fcsr |= 1u << 12;
    if (s->fcsr & (1u << 7)) return plaid_fault(s, pc, 7);
    s->fcsr |= 1u << 2;
  }
  s->f[fd] = wide ? (u64)t : (u32)t; return 0;
}
/* CVT.S and CVT.D from W, L (range-checked as ares), S or D */
static inline int plaid_to_s(plaid_state *s, u32 fmt, u32 fd, u32 fs, u32 pc) {
  u64 v = s->f[fs]; u32 r; int e; volatile float z;
  s->fcsr &= ~0x3f000u;
  if ((fmt == 17 && plaid_f64_bad(v)) ||
      (fmt == 21 && ((s64)v >= 0x0080000000000000ll || (s64)v < -0x0080000000000000ll)))
    return plaid_fault(s, pc, 7);
  feclearexcept(FE_ALL_EXCEPT);
  if (fmt == 17) z = (float)plaid_f64(v);
  else if (fmt == 20) z = (float)(s32)(u32)v;
  else z = (float)(s64)v;
  e = fetestexcept(FE_ALL_EXCEPT);
  r = plaid_b32(z);
  if (plaid_fpe(s, e, pc) || plaid_out32(s, &r, pc)) return 1;
  s->f[fd] = r; return 0;
}
static inline int plaid_to_d(plaid_state *s, u32 fmt, u32 fd, u32 fs, u32 pc) {
  u64 v = s->f[fs], r; int e; volatile double z;
  s->fcsr &= ~0x3f000u;
  if ((fmt == 16 && plaid_f32_bad((u32)v)) ||
      (fmt == 21 && ((s64)v >= 0x0080000000000000ll || (s64)v < -0x0080000000000000ll)))
    return plaid_fault(s, pc, 7);
  feclearexcept(FE_ALL_EXCEPT);
  if (fmt == 16) z = (double)plaid_f32((u32)v);
  else if (fmt == 20) z = (double)(s32)(u32)v;
  else z = (double)(s64)v;
  e = fetestexcept(FE_ALL_EXCEPT);
  r = plaid_b64(z);
  if (plaid_fpe(s, e, pc) || plaid_out64(s, &r, pc)) return 1;
  s->f[fd] = r; return 0;
}
/* CTC1 $31: rounding mode, flags, enables, cause, FS; a cause with its enable
   (or unimplemented) raises at once in ares, so it faults here */
static inline int plaid_ctc1(plaid_state *s, u32 v, u32 pc) {
  static const int modes[4] = {FE_TONEAREST, FE_TOWARDZERO, FE_UPWARD, FE_DOWNWARD};
  s->fcsr = v & 0x0103ffffu; s->fcc = v >> 23 & 1;
  fesetround(modes[v & 3]);
  if (((v >> 12) & (v >> 7) & 0x1fu) || (v & (1u << 17))) return plaid_fault(s, pc, 7);
  return 0;
}
"#;

const RUNTIME_WRITE: &str = r#"/* Host runtime functions call this before writing guest RAM at physical p. */
int plaid_runtime_write(plaid_state *s, u32 p, u32 size, u32 pc) {
  if (p > PLAID_RAM_SIZE || size > PLAID_RAM_SIZE - p) return plaid_fault(s, pc, 1);
  if (size && plaid_protected(s, p, size, 0)) return plaid_fault(s, pc, 2);
  return 0;
}
int plaid_status_acquire(plaid_state *s, u32 pc) {
  if (s->status_known) {
    u32 p;
    if (!(s->cp0_status & 0x20000000u)) {
      p = (s->status_thread & 0x1fffffffu) + 0x18;
      if (!s->status_thread || plaid_runtime_write(s, p, 4, pc)) return plaid_fault(s, pc, 11);
      s->ram[p] = 0; s->ram[p + 1] = 0; s->ram[p + 2] = 0; s->ram[p + 3] = 1;
      s->cp0_status |= 0x20000000u;
    }
  }
  return 0;
}
"#;

const HELPERS_TAIL: &str = r#"static inline int plaid_load(plaid_state *s, u64 va, u32 size, u32 pc, u64 *value) {
  u32 p, i; u64 x = 0;
  int r = plaid_addr(s, va, size, pc, 0, &p);
  if (r == 2) return s->io(s, p, size, 0, value) ? plaid_fault(s, pc, 1) : 0;
  if (r == 3) { /* the cached copy, older than RAM in its stale bytes */
    u32 d = ((u32)va >> 4) & 0x1ffu, b;
    for (i = 0; i < size; i++) {
      b = (p + i) & 15u;
      x = x << 8 | (s->dstale[d] >> b & 1 ? s->dold[d][b] : s->ram[p + i]);
    }
    *value = x; return 0;
  }
  if (r) return 1;
  for (i = 0; i < size; i++) x = x << 8 | s->ram[p + i];
  *value = x; return 0;
}
static inline int plaid_store(plaid_state *s, u64 va, u32 size, u64 value, u32 pc) {
  u32 p, i;
  int r = plaid_addr(s, va, size, pc, 1, &p);
  if (r == 2) return s->io(s, p, size, 1, &value) ? plaid_fault(s, pc, 1) : 0;
  if (r) return 1;
  for (i = 0; i < size; i++) s->ram[p + i] = (u8)(value >> (8 * (size - 1 - i)));
  return 0;
}
/* LWL/LWR/LDL/LDR and SWL/SWR/SDL/SDR, big-endian, as pinned ares: loads
   merge the containing aligned word; stores write only the bytes they cover. */
static inline int plaid_load_left(plaid_state *s, u64 va, u32 size, u32 pc, u64 *rt) {
  u64 w, x; u32 sh = 8 * ((u32)va & (size - 1));
  if (plaid_load(s, va & ~(u64)(size - 1), size, pc, &w)) return 1;
  x = w << sh | (*rt & ((1ull << sh) - 1));
  *rt = size == 4 ? SX32(x) : x; return 0;
}
static inline int plaid_load_right(plaid_state *s, u64 va, u32 size, u32 pc, u64 *rt) {
  u64 w, all = size == 4 ? 0xffffffffull : ~0ull; u32 m = (u32)va & (size - 1), sh = 8 * (size - 1 - m);
  u64 x;
  if (plaid_load(s, va & ~(u64)(size - 1), size, pc, &w)) return 1;
  x = (*rt & all & ~(all >> sh)) | w >> sh;
  /* LWR sign-extends only when it loads bit 31; otherwise the upper word stays */
  *rt = size == 8 ? x : m == 3 ? SX32(x) : (*rt & 0xffffffff00000000ull) | x; return 0;
}
static inline int plaid_store_left(plaid_state *s, u64 va, u32 size, u64 v, u32 pc) {
  u32 j, m = (u32)va & (size - 1);
  for (j = 0; j < size - m; j++)
    if (plaid_store(s, va + j, 1, v >> (8 * (size - 1 - j)), pc)) return 1;
  return 0;
}
static inline int plaid_store_right(plaid_state *s, u64 va, u32 size, u64 v, u32 pc) {
  u32 j, m = (u32)va & (size - 1);
  for (j = 0; j <= m; j++)
    if (plaid_store(s, va - j, 1, v >> (8 * j), pc)) return 1;
  return 0;
}
"#;

fn physical(pc: u32) -> Result<u32, String> {
    if (0x8000_0000..0xc000_0000).contains(&pc) {
        Ok(pc & 0x1fff_ffff)
    } else {
        Err(format!("{pc:08x} is outside KSEG0/KSEG1"))
    }
}

fn sx(pc: u32) -> String {
    format!("0x{:016x}ull", i64::from(pc as i32) as u64)
}

fn set(d: u32, expr: String) -> String {
    if d == 0 {
        String::new()
    } else {
        format!("s->r[{d}] = {expr};")
    }
}

/// Before an indirect transfer's switch over link addresses: map a target
/// in bound overlay code to its link address (ADR-0181).
fn relink(overlay: bool) -> &'static str {
    if overlay {
        "if (t == SX32((u32)t)) { t = SX32(plaid_link(s, (u32)t)); } "
    } else {
        ""
    }
}

/// The run-time half of relocatable overlays (ADR-0181): one ADR-0172
/// verifier per overlay; `plaid_link`, which maps a real address in bound
/// overlay text to its link address and binds an overlay on first entry
/// when exactly one overlay and base verify byte for byte; and
/// `plaid_ovl_write`, which revokes a binding when its text is written.
fn overlay_runtime(
    overlays: &[(u32, u32)],
    mapped_bases: &[(Option<u32>, Option<u32>)],
    layouts: &[(Vec<u8>, plaid_core::overlays::Layout)],
    compared: &[usize],
    guarded: &[Vec<(u32, u32)>],
    functions: &BTreeSet<u32>,
    image: &CodeImage,
) -> Result<String, String> {
    if overlays.is_empty() {
        return Ok(format!(
            "int plaid_ovl_write(plaid_state *s, u32 p, u32 pc) {{ (void)s; (void)p; (void)pc; return 1; }}\nstatic int plaid_tlb_change(plaid_state *s, u32 index, const plaid_tlb_entry *entry, int clear, u32 pc) {{ (void)s; (void)index; (void)entry; (void)clear; (void)pc; return 0; }}\n{TLB_WRITES}"
        ));
    }
    let mut out = String::from(
        "typedef struct { u32 f, w, probe; } plaid_ovl_fn;\ntypedef struct { u32 start, end; } plaid_ovl_range;\ntypedef struct { u32 link, text, mapped, virtual_base, physical_base, span, guards; const plaid_ovl_range *ranges; int (*verify)(const uint8_t *, size_t, uint32_t); u32 n; const plaid_ovl_fn *f; } plaid_ovl;\n",
    );
    let mut table = Vec::new();
    for (k, (&(link, _), (bytes, layout))) in overlays.iter().zip(layouts).enumerate() {
        // a slot alternate is checked over its text (ADR-0185)
        out += &overlay::verifier_guarded(bytes, layout, compared[k], link, k as u32, &guarded[k])?;
        let ranges: Vec<_> = std::iter::once((0, layout.text))
            .chain(guarded[k].iter().copied())
            .collect();
        let span = ranges.iter().map(|r| r.1).max().unwrap_or(layout.text);
        out += &format!(
            "static const plaid_ovl_range plaid_ovl_ranges_{k}[] = {{{}}};\n",
            ranges
                .iter()
                .map(|(s, e)| format!("{{{s}u,{e}u}}"))
                .collect::<Vec<_>>()
                .join(",")
        );
        let relocated: BTreeSet<u32> = layout.relocations.iter().map(|r| link + r.offset).collect();
        let entries: Vec<_> = functions
            .range(link..link + layout.text)
            .map(|&f| {
                let w = image.word(GuestAddr(f)).unwrap_or(0);
                format!(
                    "{{0x{f:08x}u, 0x{w:08x}u, {}}}",
                    u8::from(!relocated.contains(&f))
                )
            })
            .collect();
        out += &format!(
            "static const plaid_ovl_fn plaid_ovl_fn_{k}[] = {{{}}};\n",
            if entries.is_empty() {
                "{0, 0, 0}".into()
            } else {
                entries.join(", ")
            }
        );
        table.push(format!(
            "{{0x{link:08x}u, {}u, {}u, {}u, {}u, {span}u, {}u, plaid_ovl_ranges_{k}, plaid_overlay_verify_{k}, {}u, plaid_ovl_fn_{k}}}",
            layout.text,
            u8::from(mapped_bases[k].0.is_some()),
            mapped_bases[k].0.unwrap_or(0),
            mapped_bases[k].1.unwrap_or(u32::MAX),
            ranges.len(),
            entries.len()
        ));
    }
    out += &format!(
        "static const plaid_ovl plaid_ovls[] = {{{}}};\n#define PLAID_OVLS {}u\n",
        table.join(", "),
        table.len()
    );
    out += OVERLAY_RUNTIME;
    out += TLB_WRITES;
    Ok(out)
}

const TLB_WRITES: &str = r#"/* Every modeled mapping mutation advances its identity, including an equal
   rewrite. Preflight before changing any entry or revoking a binding. */
int plaid_tlb_write(plaid_state *s, u32 index, plaid_tlb_entry entry, u32 pc) {
  index &= 31u;
  if (s->tlb_generation[index] == UINT64_MAX) return plaid_fault(s, pc, 1);
  if (plaid_tlb_change(s, index, &entry, 0, pc)) return 1;
  s->tlb[index] = entry; s->tlb_generation[index]++;
  return 0;
}
int plaid_tlb_clear(plaid_state *s, u32 pc) {
  u32 i;
  for (i = 0; i < 32; i++)
    if (s->tlb_generation[i] == UINT64_MAX) return plaid_fault(s, pc, 1);
  if (plaid_tlb_change(s, 0, NULL, 1, pc)) return 1;
  for (i = 0; i < 32; i++) {
    s->tlb[i] = (plaid_tlb_entry){0, 0x80000000u, {0, 0}};
    s->tlb_generation[i]++;
  }
  return 0;
}
"#;

const OVERLAY_RUNTIME: &str = r#"/* A mapped executable must have one contiguous physical backing and one
   winning TLB entry throughout its text. Probe every 4 KiB boundary, not
   only the endpoints: an earlier entry may shadow a page in the middle. */
static int plaid_ovl_mapping(plaid_state *s, u32 k, u32 *base, u32 *index,
                             u32 changed, const plaid_tlb_entry *replacement) {
  u32 v = plaid_ovls[k].virtual_base, n = plaid_ovls[k].span;
  u32 p, i, offset = 0; u8 seg;
  if (!n || n > PLAID_RAM_SIZE || v > UINT32_MAX - (n - 1)) return 1;
  for (;;) {
    if (plaid_tlb_lookup(s, v + offset, 0, &p, &seg, &i, changed, replacement)) return 1;
    if (!offset) {
      if (plaid_ovls[k].physical_base != UINT32_MAX && p != plaid_ovls[k].physical_base) return 1;
      *base = p; *index = i;
    }
    else if (i != *index || p != *base + offset) return 1;
    if (*base > PLAID_RAM_SIZE - n) return 1;
    if (offset == n - 1) return 0;
    offset = ((v + offset) | 0xfffu) - v + 1;
    if (offset >= n) offset = n - 1;
  }
}
static int plaid_ovl_contains(u32 k, u32 offset) {
  u32 r;
  for (r = 0; r < plaid_ovls[k].guards; r++)
    if (offset >= plaid_ovls[k].ranges[r].start && offset < plaid_ovls[k].ranges[r].end) return 1;
  return 0;
}
static void plaid_ovl_protect(plaid_state *s, u32 k, u32 a, u8 value) {
  u32 r, w;
  for (r = 0; r < plaid_ovls[k].guards; r++)
    for (w = (a + plaid_ovls[k].ranges[r].start) >> 2; w < (a + plaid_ovls[k].ranges[r].end) >> 2; w++)
      s->prot[w] = value;
}
static void plaid_ovl_revoke(plaid_state *s, u32 k) {
  u32 a = plaid_ovls[k].link + s->ovl_backing[k];
  s->ovl_ok[k] = 0;
  plaid_ovl_protect(s, k, a, 0);
}
static int plaid_ovl_changed(plaid_state *s, u32 k, u32 index,
                              const plaid_tlb_entry *entry, int clear) {
  u32 a = 0, i = 0;
  if (!s->ovl_ok[k] || !s->ovl_tlb[k]) return 0;
  return clear || s->ovl_tlb[k] == index + 1 ||
    plaid_ovl_mapping(s, k, &a, &i, index, entry) ||
    i + 1 != s->ovl_tlb[k] || a != plaid_ovls[k].link + s->ovl_backing[k];
}
static int plaid_tlb_change(plaid_state *s, u32 index, const plaid_tlb_entry *entry, int clear, u32 pc) {
  u32 k;
  for (k = 0; k < PLAID_OVLS; k++)
    if (s->ovl_active[k] && plaid_ovl_changed(s, k, index, entry, clear)) return plaid_fault(s, pc, 2);
  for (k = 0; k < PLAID_OVLS; k++)
    if (plaid_ovl_changed(s, k, index, entry, clear)) plaid_ovl_revoke(s, k);
  return 0;
}
/* Physical aliases of active mapped text cannot invalidate native frames.
   Preflight all bindings before revoking any overlapping inactive copy. */
int plaid_ovl_write(plaid_state *s, u32 p, u32 pc) {
  u32 k, a;
  for (k = 0; k < PLAID_OVLS; k++) {
    if (!s->ovl_ok[k]) continue;
    a = plaid_ovls[k].link + s->ovl_backing[k];
    if (!plaid_ovl_contains(k, p - a)) continue;
    if (p - a >= plaid_ovls[k].text) return 1; /* proof-bearing data stays immutable */
    if (s->ovl_active[k] || pc - plaid_ovls[k].link < plaid_ovls[k].text) return 1;
  }
  for (k = 0; k < PLAID_OVLS; k++)
    if (s->ovl_ok[k] && plaid_ovl_contains(k, p - (plaid_ovls[k].link + s->ovl_backing[k])))
      plaid_ovl_revoke(s, k);
  return 0;
}
/* Translate only after source bytes and mapping identity agree. Compiled
   addresses name native functions; virtual addresses remain guest-visible. */
u32 plaid_link(plaid_state *s, u32 t) {
  u32 k, j, b = 0, a, w, i = 0, p = t & 0x1fffffffu, hk = 0, hb = 0, hi = 0;
  int ram = t >= 0x80000000u && t < 0xa0000000u && p < PLAID_RAM_SIZE && !(t & 3u), hit = 0;
  u8 m = 0;
  if (t & 3u) return 1;
  if (!s->prot_ready) plaid_build_prot(s);
  if (ram) {
    m = s->prot[p >> 2];
    if (m && m != 255) return t;
  }
  for (k = 0; k < PLAID_OVLS; k++) {
    if (!s->ovl_ok[k]) continue;
    if (s->ovl_tlb[k]) {
      a = 0; i = 0;
      if (s->ovl_generation[k] != s->tlb_generation[s->ovl_tlb[k] - 1] ||
          plaid_ovl_mapping(s, k, &a, &i, 0, NULL) || i + 1 != s->ovl_tlb[k] ||
          a != plaid_ovls[k].link + s->ovl_backing[k]) {
        if (s->ovl_active[k]) return 1;
        plaid_ovl_revoke(s, k); continue;
      }
    }
    if (t - (plaid_ovls[k].link + s->ovl_delta[k]) < plaid_ovls[k].text)
      return t - s->ovl_delta[k];
  }
  for (k = 0; k < PLAID_OVLS; k++) {
    if (plaid_ovls[k].mapped) {
      if (t - plaid_ovls[k].virtual_base >= plaid_ovls[k].text) continue;
      a = 0; i = 0;
      if (plaid_ovl_mapping(s, k, &a, &i, 0, NULL)) continue;
      b = 0x80000000u + a;
    } else if (!ram || m) continue;
    for (j = 0; j < plaid_ovls[k].n; j++) {
      if (plaid_ovls[k].mapped) {
        if (t - plaid_ovls[k].virtual_base != plaid_ovls[k].f[j].f - plaid_ovls[k].link) continue;
      } else {
        w = (u32)s->ram[p] << 24 | (u32)s->ram[p + 1] << 16 | (u32)s->ram[p + 2] << 8 | s->ram[p + 3];
        if (plaid_ovls[k].f[j].probe && plaid_ovls[k].f[j].w != w) continue;
        b = t - (plaid_ovls[k].f[j].f - plaid_ovls[k].link);
      }
      if (!plaid_ovls[k].verify(s->ram, PLAID_RAM_SIZE, b)) continue;
      if (hit) return 1;
      hit = 1; hk = k; hb = b; hi = plaid_ovls[k].mapped ? i + 1 : 0;
    }
  }
  if (hit && !s->ovl_active[hk]) {
    a = hb & 0x1fffffffu;
    /* First reject overlap, allowing only this candidate's previous copy. */
    for (w = a >> 2; w < (a + plaid_ovls[hk].span) >> 2; w++)
      if (plaid_ovl_contains(hk, (w << 2) - a) && s->prot[w] &&
          !(s->ovl_ok[hk] && s->prot[w] == 255 &&
          plaid_ovl_contains(hk, (w << 2) - (plaid_ovls[hk].link + s->ovl_backing[hk])))) return 1;
    if (s->ovl_ok[hk]) plaid_ovl_revoke(s, hk);
    plaid_ovl_protect(s, hk, a, 255);
    s->ovl_delta[hk] = (hi ? plaid_ovls[hk].virtual_base : hb) - plaid_ovls[hk].link;
    s->ovl_backing[hk] = a - plaid_ovls[hk].link;
    s->ovl_tlb[hk] = hi;
    s->ovl_generation[hk] = hi ? s->tlb_generation[hi - 1] : 0;
    s->ovl_ok[hk] = 1;
    return t - s->ovl_delta[hk];
  }
  if (hit) return 1;
  for (k = 0; k < PLAID_OVLS; k++)
    if (t - plaid_ovls[k].link < plaid_ovls[k].text ||
        (plaid_ovls[k].mapped && t - plaid_ovls[k].virtual_base < plaid_ovls[k].text)) return 1;
  return t;
}
"#;

fn is_control(word: u32) -> bool {
    match word >> 26 {
        0 => matches!(word & 63, 8 | 9),
        // REGIMM: branches and branch-and-link; the traps are not control.
        1 => matches!((word >> 16) & 31, 0..=3 | 16..=19),
        2..=7 | 20..=23 => true,
        17 => (word >> 21) & 31 == 8,
        _ => false,
    }
}

/// One non-control instruction, with exact pinned-ares integer semantics.
/// `fr0`: Status.FR = 0 (ADR-0160). As pinned ares: arithmetic sources (fs)
/// and 64-bit transfers use the even register of a pair, a 32-bit transfer
/// of an odd register is the upper word of its even partner, and ft and fd
/// index the register itself.
fn simple(word: u32, pc: u32, fr0: bool) -> Result<String, String> {
    simple_lo(word, pc, fr0, None)
}

/// [`simple`] with the 16-bit immediate of an address computation (ADDIU or
/// a load/store offset) given as a C expression: an overlay's LO16
/// relocation, read from its bound bytes (ADR-0181).
fn simple_lo(word: u32, pc: u32, fr0: bool, lo: Option<&str>) -> Result<String, String> {
    if lo.is_some() && !matches!(word >> 26, 9 | 32..=63) {
        return Err(format!("{pc:08x}: LO16 relocation on {word:08x}"));
    }
    let (rs, rt, rd, sa) = (
        (word >> 21) & 31,
        (word >> 16) & 31,
        (word >> 11) & 31,
        (word >> 6) & 31,
    );
    let pair = |n: u32| if fr0 { n & !1 } else { n };
    let fs = pair(rd);
    // 32-bit FPR transfers: read and replace one word of a 64-bit FPR
    let get32 = |n: u32| {
        if fr0 && n & 1 == 1 {
            format!("(u32)(s->f[{}] >> 32)", n - 1)
        } else {
            format!("(u32)s->f[{n}]")
        }
    };
    let put32 = |n: u32, v: &str| {
        if fr0 && n & 1 == 1 {
            let e = n - 1;
            format!("s->f[{e}] = (s->f[{e}] & 0xffffffffull) | (u64)(u32){v} << 32;")
        } else {
            format!("s->f[{n}] = (s->f[{n}] & 0xffffffff00000000ull) | (u32){v};")
        }
    };
    let (imm, simm) = (word & 0xffff, word as u16 as i16);
    let lo = lo.map_or_else(|| simm.to_string(), |e| format!("(int16_t)({e})"));
    let (a, b) = (format!("s->r[{rs}]"), format!("s->r[{rt}]"));
    let addr = format!("{a} + (u64)(s64){lo}");
    let load = |size: u32, ext: &str| {
        format!(
            "{{ u64 v; if (plaid_load(s, {addr}, {size}, 0x{pc:08x}u, &v)) return 1; {} }}",
            set(rt, format!("(u64)(s64)({ext})v"))
        )
    };
    let store =
        |size: u32| format!("if (plaid_store(s, {addr}, {size}, {b}, 0x{pc:08x}u)) return 1;");
    let partial_load = |side: &str, size: u32| {
        format!(
            "{{ u64 v = {b}; if (plaid_load_{side}(s, {addr}, {size}, 0x{pc:08x}u, &v)) return 1; {} }}",
            set(rt, "v".into())
        )
    };
    let partial_store = |side: &str, size: u32| {
        format!("if (plaid_store_{side}(s, {addr}, {size}, {b}, 0x{pc:08x}u)) return 1;")
    };
    // Overflow-trapping add/sub: abort (fault 6) where the VR4300 would raise.
    let trap = |ty: &str, y: String, sub: bool, sign: &str, d: u32, wrap: &str| {
        let (op, flip) = if sub { ("-", "") } else { ("+", "~") };
        format!(
            "{{ {ty} x = ({ty}){a}, y = ({ty}){y}, z = x {op} y; if ({flip}(x ^ y) & (x ^ z) & {sign}) return plaid_fault(s, 0x{pc:08x}u, 6); {} }}",
            set(d, wrap.into())
        )
    };
    // Conditional traps abort (fault 10) where the VR4300 would raise.
    let cond_trap = |cond: String| format!("if ({cond}) return plaid_fault(s, 0x{pc:08x}u, 10);");
    let ll = |size: u32, ext: &str| {
        format!(
            "{{ u64 v; if (plaid_load(s, {addr}, {size}, 0x{pc:08x}u, &v)) return 1; {} s->llbit = 1; }}",
            set(rt, format!("(u64)(s64)({ext})v"))
        )
    };
    let sc = |size: u32| {
        format!(
            "if (s->llbit) {{ if (plaid_store(s, {addr}, {size}, {b}, 0x{pc:08x}u)) return 1; {} }} else {{ {} }}",
            set(rt, "1".into()),
            set(rt, "0".into())
        )
    };
    let code = match (word >> 26, word & 63) {
        (0, 15) => String::new(),
        (0, 48) => cond_trap(format!("(s64){a} >= (s64){b}")),
        (0, 49) => cond_trap(format!("{a} >= {b}")),
        (0, 50) => cond_trap(format!("(s64){a} < (s64){b}")),
        (0, 51) => cond_trap(format!("{a} < {b}")),
        (0, 52) => cond_trap(format!("{a} == {b}")),
        (0, 54) => cond_trap(format!("{a} != {b}")),
        (1, _) if matches!(rt, 8..=12 | 14) => {
            let (x, y) = (format!("(s64){a}"), format!("(s64){simm}"));
            cond_trap(match rt {
                8 => format!("{x} >= {y}"),
                9 => format!("{a} >= (u64){y}"),
                10 => format!("{x} < {y}"),
                11 => format!("{a} < (u64){y}"),
                12 => format!("{x} == {y}"),
                _ => format!("{x} != {y}"),
            })
        }
        (48, _) => ll(4, "s32"),
        (52, _) => ll(8, "s64"),
        (56, _) => sc(4),
        (60, _) => sc(8),
        (0, 0) => set(rd, format!("SX32((u32){b} << {sa})")),
        (0, 2) => set(rd, format!("SX32((u32){b} >> {sa})")),
        (0, 3) => set(rd, format!("SX32((s64){b} >> {sa})")),
        (0, 4) => set(rd, format!("SX32((u32){b} << ({a} & 31))")),
        (0, 6) => set(rd, format!("SX32((u32){b} >> ({a} & 31))")),
        (0, 7) => set(rd, format!("SX32((s64){b} >> ({a} & 31))")),
        (0, 20) => set(rd, format!("{b} << ({a} & 63)")),
        (0, 22) => set(rd, format!("{b} >> ({a} & 63)")),
        (0, 23) => set(rd, format!("(u64)((s64){b} >> ({a} & 63))")),
        (0, 16) => set(rd, "s->hi".into()),
        (0, 17) => format!("s->hi = {a};"),
        (0, 18) => set(rd, "s->lo".into()),
        (0, 19) => format!("s->lo = {a};"),
        // ares multiplies by a sign-extended 35-bit rt; keep the low 64 bits.
        (0, 24) => format!(
            "{{ u64 m = {a} * (u64)((s64)({b} << 29) >> 29); s->lo = SX32(m); s->hi = SX32(m >> 32); }}"
        ),
        (0, 25) => format!(
            "{{ u64 m = (u64)(u32){a} * (u64)(u32){b}; s->lo = SX32(m); s->hi = SX32(m >> 32); }}"
        ),
        (0, 26) => format!(
            "{{ s64 n = (s32){a}, d = (s64){b}; if (d) {{ s->lo = SX32(n / d); s->hi = SX32(n % d); }} else {{ s->lo = n < 0 ? 1 : ~0ull; s->hi = (u64)n; }} }}"
        ),
        (0, 27) => format!(
            "{{ u32 n = (u32){a}, d = (u32){b}; if (d) {{ s->lo = SX32(n / d); s->hi = SX32(n % d); }} else {{ s->lo = ~0ull; s->hi = SX32(n); }} }}"
        ),
        // 128-bit products and quotients follow ares (GCC/Clang __int128).
        (0, 28) => format!(
            "{{ unsigned __int128 m = (unsigned __int128)((__int128)(s64){a} * (s64){b}); s->lo = (u64)m; s->hi = (u64)(m >> 64); }}"
        ),
        (0, 29) => format!(
            "{{ unsigned __int128 m = (unsigned __int128){a} * {b}; s->lo = (u64)m; s->hi = (u64)(m >> 64); }}"
        ),
        (0, 30) => format!(
            "{{ s64 n = (s64){a}, d = (s64){b}; if (!d) {{ s->lo = n < 0 ? 1 : ~0ull; s->hi = (u64)n; }} else if (d == -1 && n == -0x7fffffffffffffffll - 1) {{ s->lo = (u64)n; s->hi = 0; }} else {{ s->lo = (u64)(n / d); s->hi = (u64)(n % d); }} }}"
        ),
        (0, 31) => format!(
            "{{ u64 n = {a}, d = {b}; if (d) {{ s->lo = n / d; s->hi = n % d; }} else {{ s->lo = ~0ull; s->hi = n; }} }}"
        ),
        (0, 13) => format!("return plaid_fault(s, 0x{pc:08x}u, 9);"),
        (0, 32) => trap("u32", b.clone(), false, "0x80000000u", rd, "SX32(z)"),
        (0, 34) => trap("u32", b.clone(), true, "0x80000000u", rd, "SX32(z)"),
        (0, 44) => trap("u64", b.clone(), false, "(1ull << 63)", rd, "z"),
        (0, 46) => trap("u64", b.clone(), true, "(1ull << 63)", rd, "z"),
        (0, 45) => set(rd, format!("{a} + {b}")),
        (0, 47) => set(rd, format!("{a} - {b}")),
        (0, 56) => set(rd, format!("{b} << {sa}")),
        (0, 58) => set(rd, format!("{b} >> {sa}")),
        (0, 59) => set(rd, format!("(u64)((s64){b} >> {sa})")),
        (0, 60) => set(rd, format!("{b} << {}", sa + 32)),
        (0, 62) => set(rd, format!("{b} >> {}", sa + 32)),
        (0, 63) => set(rd, format!("(u64)((s64){b} >> {})", sa + 32)),
        (8, _) => trap(
            "u32",
            format!("(s32){simm}"),
            false,
            "0x80000000u",
            rt,
            "SX32(z)",
        ),
        (24, _) => trap(
            "u64",
            format!("(s64){simm}"),
            false,
            "(1ull << 63)",
            rt,
            "z",
        ),
        (25, _) => set(rt, format!("{a} + (u64)(s64){simm}")),
        (55, _) => load(8, "s64"),
        (16, _) if plaid_core::solver::is_cop0_move(word) => match rs {
            0 | 1 => {
                let value = if rs == 0 { "SX32(v)" } else { "v" };
                let assign = set(rt, value.into());
                format!(
                    "{{ u64 v; if (plaid_cp0_read(s, {rd}, &v, 0x{pc:08x}u)) return 1; {assign} }}"
                )
            }
            _ => format!("if (plaid_cp0_write(s, {rd}, s->r[{rt}], 0x{pc:08x}u)) return 1;"),
        },
        (16, _) if plaid_core::solver::is_cop0_tlb(word) => {
            let operation = match word & 63 {
                1 => "tlbr",
                2 => "tlbwi",
                _ => "tlbp",
            };
            format!("if (plaid_cp0_{operation}(s, 0x{pc:08x}u)) return 1;")
        }
        // COP1 data moves with 64-bit FPRs (Status.FR = 1): 32-bit forms
        // replace only the low word, as on the VR4300 (ADR-0131).
        // Moves have rs < 16; `add.s $f0, ...` also has zero low bits.
        (17, _) if word & 0x7ff == 0 && rs < 16 => {
            let wide = format!("s->f[{}]", pair(rd));
            match rs {
                0 => set(rt, format!("SX32({})", get32(rd))),
                1 => set(rt, wide),
                4 => put32(rd, &b),
                5 => format!("{wide} = {b};"),
                // CFC1/CTC1 (ADR-0139): FCR31 is the FCSR, FCR0 the revision.
                2 => set(
                    rt,
                    match rd {
                        31 => "SX32(s->fcsr | s->fcc << 23)".into(),
                        0 => "0xa00u".into(),
                        _ => "0".into(),
                    },
                ),
                6 if rd == 31 => {
                    format!("if (plaid_ctc1(s, (u32){b}, 0x{pc:08x}u)) return 1;")
                }
                6 => String::new(),
                _ => {
                    return Err(format!(
                        "{pc:08x}: instruction {word:08x} is outside the lowered subset"
                    ));
                }
            }
        }
        // C.cond.S/D (FR = 1): the condition bit is (lt && a < b) || (eq && a == b)
        // for ordered operands, as pinned ares; a NaN operand faults 7 (ADR-0135).
        (17, f) if matches!(rs, 16 | 17) && f >= 48 && word & 0x7c0 == 0 => {
            let (ty, bits, lane) = if rs == 16 {
                ("float", "u32", "(u32)")
            } else {
                ("double", "u64", "")
            };
            format!(
                "{{ {ty} x, y; {bits} xb = {lane}s->f[{fs}], yb = {lane}s->f[{rt}]; memcpy(&x, &xb, sizeof x); memcpy(&y, &yb, sizeof y); s->fcsr &= ~0x3f000u; if (x != x || y != y) return plaid_fault(s, 0x{pc:08x}u, 7); s->fcc = ({} && x < y) || ({} && x == y); }}",
                f >> 2 & 1,
                f >> 1 & 1
            )
        }
        // COP1 arithmetic and conversions (ADR-0139); fd is the sa field.
        (17, f) if matches!(rs, 16 | 17) && matches!(f, 0..=5 | 7) => {
            let kind = if rs == 16 { "s" } else { "d" };
            format!("if (plaid_arith_{kind}(s, {f}, {sa}, {fs}, {rt}, 0x{pc:08x}u)) return 1;")
        }
        (17, 6) if matches!(rs, 16 | 17) => format!("s->f[{sa}] = s->f[{fs}];"),
        (17, f @ (8..=15 | 36 | 37)) if matches!(rs, 16 | 17) => {
            let (x, bad) = if rs == 16 {
                (
                    format!("(double)plaid_f32((u32)s->f[{fs}])"),
                    format!("plaid_f32_bad((u32)s->f[{fs}])"),
                )
            } else {
                (
                    format!("plaid_f64(s->f[{fs}])"),
                    format!("plaid_f64_bad(s->f[{fs}])"),
                )
            };
            // ROUND/TRUNC/CEIL/FLOOR encode their mode in the low bits; CVT uses FCSR.RM.
            let rm = if f < 16 {
                (f & 3).to_string()
            } else {
                "s->fcsr & 3".to_string()
            };
            let wide = u32::from(f < 12 || f == 37);
            format!("if (plaid_to_int(s, {x}, {bad}, {rm}, {wide}, {sa}, 0x{pc:08x}u)) return 1;")
        }
        (17, 32) if matches!(rs, 17 | 20 | 21) => {
            format!("if (plaid_to_s(s, {rs}, {sa}, {fs}, 0x{pc:08x}u)) return 1;")
        }
        (17, 33) if matches!(rs, 16 | 20 | 21) => {
            format!("if (plaid_to_d(s, {rs}, {sa}, {fs}, 0x{pc:08x}u)) return 1;")
        }
        (49, _) => format!(
            "{{ u64 v; if (plaid_load(s, {addr}, 4, 0x{pc:08x}u, &v)) return 1; {} }}",
            put32(rt, "v")
        ),
        (53, _) => format!(
            "if (plaid_load(s, {addr}, 8, 0x{pc:08x}u, &s->f[{}])) return 1;",
            pair(rt)
        ),
        (57, _) => format!(
            "if (plaid_store(s, {addr}, 4, {}, 0x{pc:08x}u)) return 1;",
            get32(rt)
        ),
        (61, _) => format!(
            "if (plaid_store(s, {addr}, 8, s->f[{}], 0x{pc:08x}u)) return 1;",
            pair(rt)
        ),
        (63, _) => store(8),
        (47, _) => format!("if (plaid_cache(s, {rt}u, {addr}, 0x{pc:08x}u)) return 1;"),
        (0, 33) => set(rd, format!("SX32((u32){a} + (u32){b})")),
        (0, 35) => set(rd, format!("SX32((u32){a} - (u32){b})")),
        (0, 36) => set(rd, format!("{a} & {b}")),
        (0, 37) => set(rd, format!("{a} | {b}")),
        (0, 38) => set(rd, format!("{a} ^ {b}")),
        (0, 39) => set(rd, format!("~({a} | {b})")),
        (0, 42) => set(rd, format!("(u64)((s64){a} < (s64){b})")),
        (0, 43) => set(rd, format!("(u64)({a} < {b})")),
        (9, _) => set(rt, format!("SX32((u32){a} + (u32)(s32){lo})")),
        (10, _) => set(rt, format!("(u64)((s64){a} < (s64){simm})")),
        (11, _) => set(rt, format!("(u64)({a} < (u64)(s64){simm})")),
        (12, _) => set(rt, format!("{a} & 0x{imm:x}u")),
        (13, _) => set(rt, format!("{a} | 0x{imm:x}u")),
        (14, _) => set(rt, format!("{a} ^ 0x{imm:x}u")),
        (15, _) => set(rt, sx(imm << 16)),
        (32, _) => load(1, "int8_t"),
        (33, _) => load(2, "int16_t"),
        (35, _) => load(4, "s32"),
        (36, _) => load(1, "u8"),
        (37, _) => load(2, "uint16_t"),
        (39, _) => load(4, "u32"),
        (34, _) => partial_load("left", 4),
        (38, _) => partial_load("right", 4),
        (26, _) => partial_load("left", 8),
        (27, _) => partial_load("right", 8),
        (42, _) => partial_store("left", 4),
        (46, _) => partial_store("right", 4),
        (44, _) => partial_store("left", 8),
        (45, _) => partial_store("right", 8),
        (40, _) => store(1),
        (41, _) => store(2),
        (43, _) => store(4),
        _ => {
            return Err(format!(
                "{pc:08x}: instruction {word:08x} is outside the lowered subset"
            ));
        }
    };
    Ok(if word >> 26 == 17 && matches!(rs, 2 | 6) {
        format!("if (plaid_status_cop1(s, 0x{pc:08x}u)) {{ return 1; }}\n{code}")
    } else if matches!(word >> 26, 17 | 49 | 53 | 57 | 61) {
        format!(
            "if (plaid_status_fp(s, 0x{pc:08x}u, {})) {{ return 1; }}\n{code}",
            u8::from(fr0)
        )
    } else {
        code
    })
}

/// Blocks a suspended frame can still execute after each linking call returns
/// (ADR-0219 continuation pins), keyed by the call's link address: those
/// reachable from the link through in-function edges, the next block, and
/// proven jump tables. A jump with no proven target set keeps every block
/// live, so imprecision only ever pins more.
fn continuation_blocks<'b>(
    blocks: &[&'b BasicBlock],
    edges: &BTreeMap<u32, Vec<u32>>,
    targets: &BTreeMap<u32, BTreeSet<u32>>,
    returns: &BTreeSet<u32>,
    word: &dyn Fn(u32) -> Result<u32, String>,
) -> BTreeMap<u32, Vec<&'b BasicBlock>> {
    let by_start: BTreeMap<u32, &BasicBlock> = blocks.iter().map(|b| (b.start.pc.0, *b)).collect();
    let mut unknown = false;
    let mut next: BTreeMap<u32, BTreeSet<u32>> = BTreeMap::new();
    let mut links = BTreeSet::new();
    for b in blocks {
        let (start, end) = (b.start.pc.0, b.start.pc.0.wrapping_add(b.size));
        let out = next.entry(start).or_default();
        out.insert(end);
        for pc in (start..end).step_by(4) {
            out.extend(edges.get(&pc).into_iter().flatten().copied());
            let Ok(w) = word(pc) else { continue };
            let (op, funct, rt) = (w >> 26, w & 63, (w >> 16) & 31);
            if op == 0 && funct == 8 && !returns.contains(&pc) {
                match targets.get(&pc) {
                    Some(ts) => out.extend(ts.iter().copied()),
                    None => unknown = true,
                }
            }
            if op == 3 || (op == 0 && funct == 9) || (op == 1 && (16..=19).contains(&rt)) {
                links.insert(pc.wrapping_add(8));
            }
        }
    }
    links
        .into_iter()
        .map(|link| {
            if unknown {
                return (link, blocks.to_vec());
            }
            let mut seen = BTreeSet::new();
            let mut work = vec![link];
            while let Some(pc) = work.pop() {
                if by_start.contains_key(&pc) && seen.insert(pc) {
                    work.extend(next.get(&pc).into_iter().flatten().copied());
                }
            }
            (link, seen.iter().map(|pc| by_start[pc]).collect())
        })
        .collect()
}

struct Lowerer<'a> {
    image: &'a CodeImage,
    fr0: bool,
    /// Block starts of the function being emitted (exits included).
    labels: BTreeSet<u32>,
    /// Constant-proven indirect targets by site.
    targets: &'a BTreeMap<u32, BTreeSet<u32>>,
    /// `jr $ra` sites closed by a return certificate: lowered as checked returns.
    returns: &'a BTreeSet<u32>,
    /// Function entries, each emitted as one C function.
    functions: &'a BTreeSet<u32>,
    /// Declared runtime functions (ADR-0129): host-provided `plaid_rt_<name>`.
    runtime: &'a BTreeMap<u32, String>,
    /// Residual sites (ADR-0218): a jump's candidate outside this function
    /// faults 3 instead of refusing the lowering (ADR-0223).
    residual: &'a BTreeSet<u32>,
    /// `plaid_call_<k>` dispatchers by JALR target set.
    dispatch: &'a BTreeMap<&'a BTreeSet<u32>, usize>,
    /// Relocatable overlays' link ranges, and the one this function is in.
    overlays: &'a [(u32, u32)],
    ovl: Option<usize>,
    /// Pinned frame of a fixed-text function (ADR-0219): its entry and full
    /// range count, and per call continuation the range count still live there.
    frame: Option<(u32, usize)>,
    continuations: BTreeMap<u32, usize>,
}

impl Lowerer<'_> {
    /// While a call is outstanding, the suspended frame pins only the text its
    /// continuation can still reach; the full body is pinned again on return.
    fn pin(&self, link: u32, call: String) -> String {
        match (self.frame, self.continuations.get(&link)) {
            (Some((f, full)), Some(n)) => format!(
                "frame->ranges = C_{f:08x}_{link:08x}; frame->count = {n}u; {call} frame->ranges = R_{f:08x}; frame->count = {full}u;"
            ),
            _ => call,
        }
    }
    fn ovl_of(&self, pc: u32) -> Option<usize> {
        self.overlays.iter().position(|(s, e)| *s <= pc && pc < *e)
    }
    /// A return address as the guest sees it: in overlay code, where the
    /// bound copy really runs (ADR-0181).
    fn link(&self, after: u32) -> String {
        match self.ovl {
            Some(k) => format!("SX32(0x{after:08x}u + s->ovl_delta[{k}])"),
            None => sx(after),
        }
    }
    /// The translation to link addresses an indirect transfer needs when
    /// one of its targets is overlay code.
    fn relink(&self, targets: &BTreeSet<u32>) -> &'static str {
        relink(targets.iter().any(|t| self.ovl_of(*t).is_some()))
    }
    fn goto(&self, target: u32) -> Result<String, String> {
        if self.labels.contains(&target) {
            Ok(format!("goto L_{target:08x};"))
        } else {
            Err(format!("transfer to {target:08x} has no proven block"))
        }
    }
    fn fallthrough(&self, next: u32, pc: u32) -> String {
        self.goto(next)
            .unwrap_or_else(|_| format!("return plaid_fault(s, 0x{pc:08x}u, 3);"))
    }
    /// A guest call: the callee returns 0 only after a checked return to `link`.
    fn call(&self, target: u32, link: u32, pc: u32, bound: bool) -> Result<String, String> {
        if let Some(name) = self.runtime.get(&target) {
            return Ok(format!(
                "{} {}",
                self.pin(
                    link,
                    format!("{{ s->cp0_known &= 1u << 10; int r = plaid_rt_{name}(s); if (r) return r; }}")
                ),
                self.fallthrough(link, pc)
            ));
        }
        if !self.functions.contains(&target) {
            return Err(format!(
                "{pc:08x}: call target {target:08x} is not a function"
            ));
        }
        // Another overlay's link address names whatever RAM holds there.
        if !bound && self.ovl_of(target).is_some_and(|k| Some(k) != self.ovl) {
            return Ok(format!("return plaid_fault(s, 0x{pc:08x}u, 3);"));
        }
        Ok(format!(
            "{} {}",
            self.pin(
                link,
                format!(
                    "{{ int r = F_{target:08x}(s, {}); if (r) return r; }}",
                    self.link(link)
                )
            ),
            self.fallthrough(link, pc)
        ))
    }
    /// A tail transfer keeps the entering call's continuation and balances
    /// overlay pins through the callee's ordinary native wrapper.
    fn tail(&self, target: u32, pc: u32) -> Result<String, String> {
        if self.labels.contains(&target) {
            return self.goto(target);
        }
        if let Some(name) = self.runtime.get(&target) {
            return Ok(format!(
                "{{ s->cp0_known &= 1u << 10; int r = plaid_rt_{name}(s); if (r) return r; }} if (s->r[31] != ret) return plaid_fault(s, 0x{pc:08x}u, 5); return 0;"
            ));
        }
        if self.functions.contains(&target) {
            return Ok(format!("return F_{target:08x}(s, ret);"));
        }
        Err(format!(
            "{pc:08x}: tail target {target:08x} has no native function or label"
        ))
    }
    fn control(&self, word: u32, pc: u32, slot: &str) -> Result<String, String> {
        let (rs, rt, rd) = ((word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31);
        let (a, b) = (format!("s->r[{rs}]"), format!("s->r[{rt}]"));
        let after = pc.wrapping_add(8);
        let branch = pc
            .wrapping_add(4)
            .wrapping_add_signed(i32::from(word as u16 as i16) * 4);
        let jump = self.image.jump_target(GuestAddr(pc), word).0;
        let conditional = |cond: String| -> Result<String, String> {
            Ok(format!(
                "{{ int t = {cond}; {slot} if (t) {} }} {}",
                self.goto(branch)?,
                self.fallthrough(after, pc)
            ))
        };
        // Branch likely: the delay slot executes only when the branch is taken.
        let likely = |cond: String| -> Result<String, String> {
            Ok(format!(
                "{{ int t = {cond}; if (t) {{ {slot} {} }} }} {}",
                self.goto(branch)?,
                self.fallthrough(after, pc)
            ))
        };
        let proven = || {
            self.targets
                .get(&pc)
                .ok_or_else(|| format!("{pc:08x}: indirect site lacks a proven target set"))
        };
        if plaid_core::solver::is_eret(word) {
            let mut cases = String::new();
            for &t in proven()? {
                if let Ok(code) = self.tail(t, pc) {
                    cases += &format!(" case {}: {code}", sx(t));
                }
            }
            return Ok(format!(
                "{{ u64 t; if (plaid_cp0_eret(s, &t, 0x{pc:08x}u)) return 1; {}switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}",
                self.relink(proven()?)
            ));
        }
        match (word >> 26, word & 63, rt) {
            (0, 8, _) if self.returns.contains(&pc) => Ok(format!(
                "{{ u64 t = {a}; {slot} if (t != ret) return plaid_fault(s, 0x{pc:08x}u, 5); return 0; }}"
            )),
            (0, 8, _) => {
                let mut cases = String::new();
                for &t in proven()? {
                    match self.tail(t, pc) {
                        Ok(code) => cases += &format!(" case {}: {code}", sx(t)),
                        Err(_) if self.residual.contains(&pc) => {}
                        Err(e) => return Err(e),
                    }
                }
                Ok(format!(
                    "{{ u64 t = {a}; {slot} {}switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}",
                    self.relink(proven()?)
                ))
            }
            (0, 9, _) => {
                if let Some(k) = self.dispatch.get(proven()?) {
                    return Ok(format!(
                        "{{ u64 t = {a}; {} {slot} {} {} }}",
                        set(rd, self.link(after)),
                        self.pin(
                            after,
                            format!(
                                "{{ int r = plaid_call_{k}(s, t, {}, 0x{pc:08x}u); if (r) return r; }}",
                                self.link(after)
                            )
                        ),
                        self.fallthrough(after, pc)
                    ));
                }
                let mut cases = String::new();
                for &t in proven()? {
                    cases += &format!(" case {}: {}", sx(t), self.call(t, after, pc, true)?);
                }
                Ok(format!(
                    "{{ u64 t = {a}; {} {slot} {}switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}",
                    set(rd, self.link(after)),
                    self.relink(proven()?)
                ))
            }
            (1, _, 2) => likely(format!("(s64){a} < 0")),
            (1, _, 3) => likely(format!("(s64){a} >= 0")),
            (20, _, _) => likely(format!("{a} == {b}")),
            (21, _, _) => likely(format!("{a} != {b}")),
            (22, _, 0) => likely(format!("(s64){a} <= 0")),
            (23, _, 0) => likely(format!("(s64){a} > 0")),
            // BC1 clears the FCSR cause bits first, as pinned ares does.
            (17, _, _) if rs == 8 && rt & 2 != 0 => likely(format!(
                "(s->fcsr &= ~0x3f000u, {}s->fcc)",
                if rt & 1 == 0 { "!" } else { "" }
            ))
            .map(|code| {
                format!(
                    "if (plaid_status_fp(s, 0x{pc:08x}u, {})) {{ return 1; }}\n{code}",
                    u8::from(self.fr0)
                )
            }),
            (17, _, _) if rs == 8 => conditional(format!(
                "(s->fcsr &= ~0x3f000u, {}s->fcc)",
                if rt & 1 == 0 { "!" } else { "" }
            ))
            .map(|code| {
                format!(
                    "if (plaid_status_fp(s, 0x{pc:08x}u, {})) {{ return 1; }}\n{code}",
                    u8::from(self.fr0)
                )
            }),
            (1, _, 0) => conditional(format!("(s64){a} < 0")),
            (1, _, 1) => conditional(format!("(s64){a} >= 0")),
            // BLTZAL BGEZAL (likely: 18, 19) link first, then test rs, as ares.
            (1, _, 16..=19) => {
                let test = format!("(s64){a} {} 0", if rt & 1 == 0 { "<" } else { ">=" });
                let call = self.call(branch, after, pc, false)?;
                let link = set(31, self.link(after));
                Ok(if rt & 2 == 0 {
                    format!(
                        "{{ {link} int t = {test}; {slot} if (t) {{ {call} }} }} {}",
                        self.fallthrough(after, pc)
                    )
                } else {
                    format!(
                        "{{ {link} int t = {test}; if (t) {{ {slot} {call} }} }} {}",
                        self.fallthrough(after, pc)
                    )
                })
            }
            // A tail call into the runtime returns to $ra, which must be ours.
            (2, _, _) if self.runtime.contains_key(&jump) => Ok(format!(
                "{slot} {{ s->cp0_known &= 1u << 10; int r = plaid_rt_{}(s); if (r) return r; }} if (s->r[31] != ret) return plaid_fault(s, 0x{pc:08x}u, 5); return 0;",
                self.runtime[&jump]
            )),
            (2, _, _) if self.targets.contains_key(&pc) => {
                let k = self.dispatch[proven()?];
                Ok(format!(
                    "{slot} return plaid_call_{k}(s, {}, ret, 0x{pc:08x}u);",
                    sx(jump)
                ))
            }
            (2, _, _) if self.ovl_of(jump).is_some_and(|k| Some(k) != self.ovl) => {
                Ok(format!("{slot} return plaid_fault(s, 0x{pc:08x}u, 3);"))
            }
            (2, _, _) => Ok(format!("{slot} {}", self.tail(jump, pc)?)),
            (3, _, _) if self.targets.contains_key(&pc) => {
                let k = self.dispatch[proven()?];
                Ok(format!(
                    "s->r[31] = {}; {slot} {} {}",
                    self.link(after),
                    self.pin(
                        after,
                        format!(
                            "{{ int r = plaid_call_{k}(s, {}, {}, 0x{pc:08x}u); if (r) return r; }}",
                            sx(jump),
                            self.link(after)
                        )
                    ),
                    self.fallthrough(after, pc)
                ))
            }
            (3, _, _) => Ok(format!(
                "s->r[31] = {}; {slot} {}",
                self.link(after),
                self.call(jump, after, pc, false)?
            )),
            (4, _, _) => conditional(format!("{a} == {b}")),
            (5, _, _) => conditional(format!("{a} != {b}")),
            (6, _, 0) => conditional(format!("(s64){a} <= 0")),
            (7, _, 0) => conditional(format!("(s64){a} > 0")),
            _ => Err(format!(
                "{pc:08x}: control instruction {word:08x} is outside the lowered subset"
            )),
        }
    }
}

/// Lower a program CLOSED under the guarded-RAM declared-static scope to C,
/// one C function per guest function. `exits` are host-boundary addresses:
/// reaching one makes `plaid_run` return 0 with `s->pc` set.
pub fn lower_c(
    map: &ProgramMap,
    images: &[CodeImage],
    entry: GuestAddr,
    exits: &[GuestAddr],
) -> Result<String, String> {
    let [image] = images else {
        return Err("exactly one code image is supported".into());
    };
    lower_c_with_preload(map, images, image, entry, exits, false)
}

/// Lower with `preload` as the RAM contents the host installs before entry
/// (the IPL3 copy). With declared loads (ADR-0136) the code image is the
/// composite and the preload is its base window.
pub fn lower_c_with_preload(
    map: &ProgramMap,
    images: &[CodeImage],
    preload: &CodeImage,
    entry: GuestAddr,
    exits: &[GuestAddr],
    residual_dispatch: bool,
) -> Result<String, String> {
    Ok(lower_c_parts(map, images, preload, entry, exits, 1, residual_dispatch)?.remove(0))
}

/// [`lower_c_with_preload`] as `parts` translation units that compile in
/// parallel (ADR-0174). The first is the program the runtime includes; each
/// other holds a share of the guest functions, which then have external
/// linkage, and declares the main unit's single-instance definitions.
pub fn lower_c_parts(
    map: &ProgramMap,
    images: &[CodeImage],
    preload: &CodeImage,
    entry: GuestAddr,
    exits: &[GuestAddr],
    parts: usize,
    residual_dispatch: bool,
) -> Result<Vec<String>, String> {
    let link = if parts > 1 { "" } else { "static " };
    // Address-taken dispatch is its own scope (ADR-0153); residual dispatch is
    // the validation-only relaxation of it (ADR-0218).
    let scope = if residual_dispatch {
        Scope::DeclaredStaticImagesGuardedRamResidualDispatch
    } else if map.address_taken.is_empty() {
        Scope::DeclaredStaticImagesGuardedRam
    } else {
        Scope::DeclaredStaticImagesGuardedRamAddressTaken
    };
    let report = solve(map, images, scope)?;
    if report.status != ClosureStatus::Closed {
        let kinds: BTreeSet<_> = report.blockers.iter().map(|b| b.kind.as_str()).collect();
        let first: Vec<_> = report
            .blockers
            .iter()
            .take(3)
            .map(|b| {
                format!(
                    "{:08x}: {}",
                    b.site.as_ref().map_or(0, |s| s.pc.0),
                    b.detail
                )
            })
            .collect();
        return Err(format!("program is not CLOSED: {kinds:?} {first:?}"));
    }
    let [image] = images else {
        return Err("exactly one code image is supported".into());
    };
    let declared = map
        .load_images
        .get(&image.base.image)
        .map_or(&[][..], |spec| spec.loads.as_slice());
    let range = |l: &plaid_core::declared_loads::DeclaredLoad| {
        (
            l.destination.start.0,
            l.destination.start.0 + l.destination.size,
        )
    };
    let loads: Vec<(u32, u32)> = declared
        .iter()
        .filter(|l| !l.relocatable)
        .map(range)
        .collect();
    if loads.len() > 64 {
        return Err("at most 64 declared loads are supported".into());
    }
    let load_of = |start: u32| loads.iter().position(|(s, e)| *s <= start && start < *e);
    let data_loads: BTreeSet<usize> = declared
        .iter()
        .filter(|l| !l.relocatable)
        .enumerate()
        .filter_map(|(i, l)| {
            matches!(
                l.encoding,
                plaid_core::declared_loads::LoadEncoding::AresData { .. }
            )
            .then_some(i)
        })
        .collect();
    // Relocatable overlays run only through a run-time binding (ADR-0181).
    let relocatable: Vec<&plaid_core::declared_loads::DeclaredLoad> =
        declared.iter().filter(|l| l.relocatable).collect();
    let overlays: Vec<(u32, u32)> = relocatable.iter().map(|l| range(l)).collect();
    let virtual_bases: Vec<Option<u32>> = relocatable
        .iter()
        .map(|l| match l.encoding {
            plaid_core::declared_loads::LoadEncoding::TlbRaw { .. }
            | plaid_core::declared_loads::LoadEncoding::AresTlb { .. } => l
                .linked
                .map(|a| a.0)
                .ok_or("TLB executable lacks its virtual base")
                .map(Some),
            _ if l
                .linked
                .is_some_and(|a| !(0x80000000..0xc0000000).contains(&a.0)) =>
            {
                Err("mapped executable slots require tlb_raw encoding")
            }
            _ => Ok(None),
        })
        .collect::<Result<_, _>>()?;
    let mapped_bases: Vec<_> = relocatable
        .iter()
        .zip(virtual_bases)
        .map(|(l, virtual_base)| {
            (
                virtual_base,
                match l.encoding {
                    plaid_core::declared_loads::LoadEncoding::AresTlb { physical, .. } => {
                        Some(physical)
                    }
                    _ => None,
                },
            )
        })
        .collect();
    if overlays.len() > 1024 {
        return Err("at most 1024 relocatable overlays are supported".into());
    }
    let mut layouts = Vec::new();
    let mut compared = Vec::new();
    let mut relocations = BTreeMap::new();
    for (k, &(link, end)) in overlays.iter().enumerate() {
        let bytes: Vec<u8> = (link..end)
            .step_by(4)
            .map(|pc| {
                image
                    .word(GuestAddr(pc))
                    .ok_or(format!("{pc:08x}: overlay byte missing"))
            })
            .collect::<Result<Vec<_>, _>>()?
            .into_iter()
            .flat_map(u32::to_be_bytes)
            .collect();
        let layout = relocatable[k].layout(&bytes)?;
        for r in &layout.relocations {
            relocations.insert(link + r.offset, (k, r.kind));
        }
        compared.push(if relocatable[k].linked.is_some() {
            layout.text as usize
        } else {
            bytes.len()
        });
        layouts.push((bytes, layout));
    }
    let ovl_of = |pc: u32| overlays.iter().position(|(s, e)| *s <= pc && pc < *e);
    // Proven indirect targets also become map entries; the host enters only here.
    let Some(host) = map.entries.keys().find(|e| e.pc == entry) else {
        return Err(format!("{:08x} is not a map entry", entry.0));
    };
    let word = |pc: u32| -> Result<u32, String> {
        image
            .word(GuestAddr(pc))
            .ok_or_else(|| format!("{pc:08x} has no supplied instruction word"))
    };
    let exits: BTreeSet<u32> = exits.iter().map(|e| e.0).collect();
    let mut status_wrappers = String::new();
    let mut bound_names = BTreeSet::new();
    let runtime: BTreeMap<u32, String> = map.runtime_functions.iter().map(|(a, f)| {
        let name = if let Some(global) = f.status_global {
            let name = format!("status_{:08x}", a.pc.0);
            status_wrappers += &format!("int plaid_rt_{}_global(plaid_state *s, u32 global);\nstatic inline int plaid_rt_{name}(plaid_state *s) {{ return plaid_rt_{}_global(s, 0x{:08x}u); }}\n",f.name,f.name,global.0);
            bound_names.insert(name.clone());
            name
        } else if let Some((queue, message)) = f.eeprom_timer {
            let name = format!("eeprom_{:08x}", a.pc.0);
            status_wrappers += &format!("int plaid_rt_osContInit_eeprom(plaid_state *s, u32 queue, u32 message);\nstatic inline int plaid_rt_{name}(plaid_state *s) {{ return plaid_rt_osContInit_eeprom(s, 0x{:08x}u, 0x{:08x}u); }}\n",queue.0,message.0);
            bound_names.insert(name.clone());
            name
        } else { f.name.clone() };
        (a.pc.0, name)
    }).collect();
    let mut targets = BTreeMap::new();
    let mut returns = BTreeSet::new();
    let mut callees = vec![host.clone()];
    let mut residual = BTreeMap::new();
    for site in &map.indirect_sites {
        if report.residual_sites.contains(&site.site) {
            let known: BTreeSet<u32> = site
                .candidates
                .keys()
                .chain(site.observed.keys())
                .map(|t| t.pc.0)
                .collect();
            residual.insert(site.site.pc.0, (site.link_register.is_some(), known));
            continue;
        }
        let proof = site
            .closed_proof
            .as_ref()
            .and_then(|id| map.evidence.get(id));
        if proof.is_none() && site.link_register.is_some() && !map.address_taken.is_empty() {
            // the solver accepted it under the address-taken scope
            callees.extend(map.address_taken.keys().cloned());
            targets.insert(
                site.site.pc.0,
                map.address_taken
                    .keys()
                    .map(|t| t.pc.0)
                    .collect::<BTreeSet<_>>(),
            );
            continue;
        }
        let Some(proof) = proof else {
            return Err(format!(
                "{:08x}: indirect site has no closure proof",
                site.site.pc.0
            ));
        };
        if proof.producer == returns::PRODUCER {
            returns.insert(site.site.pc.0);
            continue;
        }
        callees.extend(
            site.candidates
                .keys()
                .filter(|t| {
                    site.link_register.is_some()
                        || proof.producer == "plaid-tail-cell-jr/v0"
                        || ovl_of(site.site.pc.0) != ovl_of(t.pc.0)
                })
                .cloned(),
        );
        targets.insert(
            site.site.pc.0,
            site.candidates
                .keys()
                .map(|t| t.pc.0)
                .collect::<BTreeSet<_>>(),
        );
    }
    // A call into a slot dispatches over the alternates RAM may hold there,
    // through the binding (ADR-0185); other calls name their callee.
    let blocks: BTreeSet<u32> = map.blocks.iter().map(|b| b.start.pc.0).collect();
    for e in map.direct_edges.iter().filter(|e| {
        e.kind == EdgeKind::Call
            || e.kind == EdgeKind::Jump && ovl_of(e.site.pc.0) != ovl_of(e.target.pc.0)
    }) {
        let slot: BTreeSet<u32> = plaid_core::declared_loads::slot_targets(declared, e.target.pc.0)
            .into_iter()
            .filter(|t| blocks.contains(t))
            .collect();
        if blocks.contains(&e.target.pc.0) || slot.is_empty() {
            callees.push(e.target.clone());
            continue;
        }
        callees.extend(slot.iter().map(|&t| image.address(GuestAddr(t))));
        targets.insert(e.site.pc.0, slot);
    }
    // A proven register-call constant can name the linked slot too. Its
    // native dispatcher must contain the placed alternatives, not a phantom
    // function at the shared address.
    for site in map.indirect_sites.iter().filter(|s| {
        s.link_register.is_some()
            || s.closed_proof
                .as_ref()
                .and_then(|id| map.evidence.get(id))
                .is_some_and(|e| e.producer == "plaid-tail-cell-jr/v0")
    }) {
        if let Some(set) = targets.get_mut(&site.site.pc.0) {
            let expanded: BTreeSet<u32> = set
                .iter()
                .flat_map(|&t| {
                    if blocks.contains(&t) || runtime.contains_key(&t) {
                        vec![t]
                    } else {
                        plaid_core::declared_loads::slot_targets(declared, t)
                            .into_iter()
                            .filter(|a| blocks.contains(a))
                            .collect()
                    }
                })
                .collect();
            *set = expanded;
            callees.extend(
                set.iter()
                    .filter(|t| blocks.contains(t))
                    .map(|&t| image.address(GuestAddr(t))),
            );
        }
    }
    callees.retain(|f| blocks.contains(&f.pc.0) || runtime.contains_key(&f.pc.0));
    let entered = plaid_core::callbacks::targets(map, image);
    callees.extend(entered.iter().cloned());
    callees.retain(|f| !runtime.contains_key(&f.pc.0));
    let functions: BTreeSet<u32> = callees.iter().map(|f| f.pc.0).collect();
    // A residual site dispatches over every lowered entry, never beyond
    // (ADR-0218), and over its own candidate and observed targets: entries for
    // a call, block starts for a jump (ADR-0223).
    let every_entry: BTreeSet<u32> = functions.iter().chain(runtime.keys()).copied().collect();
    for (&pc, (call, known)) in &residual {
        let own = known.iter().copied().filter(|t| {
            if *call {
                functions.contains(t) || runtime.contains_key(t)
            } else {
                blocks.contains(t)
            }
        });
        targets.insert(pc, every_entry.iter().copied().chain(own).collect());
    }
    for site in &report.residual_sites {
        if plaid_core::solver::is_eret(word(site.pc.0)?) {
            targets.insert(
                site.pc.0,
                every_entry.iter().chain(blocks.iter()).copied().collect(),
            );
            residual.insert(site.pc.0, (false, BTreeSet::new()));
        }
    }
    let residual: BTreeSet<u32> = residual.into_keys().collect();

    let mut code = Vec::new();
    for block in &map.blocks {
        if block.delay_slot_entry {
            return Err(format!(
                "{:08x}: delay-slot entry blocks are unsupported",
                block.start.pc.0
            ));
        }
        let (start, end) = (block.start.pc.0, block.start.pc.0.wrapping_add(block.size));
        if let Some(k) = ovl_of(start) {
            if end > overlays[k].0 + layouts[k].1.text {
                return Err(format!("{start:08x}: overlay code outside its text"));
            }
            continue;
        }
        code.push(format!(
            "{{{}, {}, {}}}",
            physical(start)?,
            physical(end - 1)? + 1,
            load_of(start).map_or(-1, |l| l as i64)
        ));
    }
    // Jump tables are store-protected like code (ADR-0132).
    let mut guarded = vec![Vec::new(); overlays.len()];
    let mut data_guards = BTreeMap::new();
    let index = plaid_core::indirect::MapIndex::new(map);
    for site in &map.indirect_sites {
        let cell = plaid_core::tail_cells::source_cell_range_in(&index, map, image, site)
            .map(|range| (range.start, range.size / 4));
        if let Some((start, count)) =
            plaid_core::tables::table_range(&index, map, image, site).or(cell)
        {
            if let Some(k) = ovl_of(start.0) {
                let end = start
                    .0
                    .checked_add(count * 4)
                    .ok_or("overlay table range overflow")?;
                if end > overlays[k].1 {
                    return Err("overlay table exceeds its declared source".into());
                }
                guarded[k].push((start.0 - overlays[k].0, end - overlays[k].0));
                continue;
            }
            code.push(format!(
                "{{{}, {}, {}}}",
                physical(start.0)?,
                physical(start.0 + count * 4 - 1)? + 1,
                load_of(start.0).map_or(-2, |l| l as i64)
            ));
            if let Some(l) = load_of(start.0).filter(|l| data_loads.contains(l)) {
                // Data-only loads have no executable entry to trigger validation.
                // Verify at their consuming transfer, after guest initialization.
                data_guards.insert(site.site.pc.0, l);
            }
        }
    }
    let mut out = String::from(PRELUDE);
    out += &format!(
        "static const plaid_range plaid_code[] = {{{}}};\n{}{HELPERS}{COP0}{RUNTIME_WRITE}{HELPERS_TAIL}",
        code.join(", "),
        BUILD_PROT.replacen("static ", link, 1)
    );
    // What every other unit sees of the main unit's definitions.
    let mut shared =
        format!("{PRELUDE}void plaid_build_prot(plaid_state *s);\n{HELPERS}{COP0}{HELPERS_TAIL}");
    if !loads.is_empty() {
        shared += "int plaid_verify_load(plaid_state *s, int load, u32 pc);\n";
        // Expected bytes come from the composite image (ADR-0136), up to the
        // last fixed load; overlays verify through their own binding.
        let last = loads.iter().map(|l| l.1).max().unwrap_or(0);
        let words: Vec<_> = image
            .words
            .iter()
            .take((last.saturating_sub(image.base.pc.0) as usize).div_ceil(4))
            .map(|w| format!("0x{w:08x}u"))
            .collect();
        out += &format!(
            "static const u32 plaid_declared[] = {{{}}};\n{link}int plaid_verify_load(plaid_state *s, int load, u32 pc) {{\n  u32 i, j, o;\n  for (i = 0; i < sizeof plaid_code / sizeof plaid_code[0]; i++)\n    if (plaid_code[i].load == load)\n      for (j = plaid_code[i].start; j < plaid_code[i].end; j++) {{\n        o = j - 0x{:x}u;\n        if (s->ram[j] != (u8)(plaid_declared[o / 4] >> (24 - 8 * (o % 4)))) return plaid_fault(s, pc, 8);\n      }}\n  s->load_ok[load] = 1; return 0;\n}}\n",
            words.join(", "),
            physical(image.base.pc.0)?
        );
    }
    let base = physical(preload.base.pc.0)?;
    let words: Vec<_> = preload
        .words
        .iter()
        .map(|w| format!("0x{w:08x}u"))
        .collect();
    out += &format!(
        "static inline void plaid_load_images(plaid_state *s) {{\n  static const u32 w[] = {{{}}};\n  u32 i;\n  for (i = 0; i < {}; i++) {{ s->ram[0x{base:x} + 4 * i] = (u8)(w[i] >> 24); s->ram[0x{base:x} + 4 * i + 1] = (u8)(w[i] >> 16); s->ram[0x{base:x} + 4 * i + 2] = (u8)(w[i] >> 8); s->ram[0x{base:x} + 4 * i + 3] = (u8)w[i]; }}\n}}\n",
        words.join(", "),
        words.len(),
    );
    let mut declarations = String::new();
    for name in runtime.values() {
        if !bound_names.contains(name) {
            declarations += &format!("int plaid_rt_{name}(plaid_state *s);\n");
        }
    }
    declarations += &status_wrappers;
    for f in &functions {
        declarations += &format!("{link}int F_{f:08x}(plaid_state *s, u64 ret);\n");
    }
    out += &declarations;
    shared += &declarations;
    out += &overlay_runtime(
        &overlays,
        &mapped_bases,
        &layouts,
        &compared,
        &guarded,
        &functions,
        image,
    )?;
    // A JALR with several proven targets calls one dispatcher per target set
    // instead of inlining a call per target at every site (ADR-0174).
    let mut dispatch = BTreeMap::new();
    for (&pc, ts) in &targets {
        let w = word(pc)?;
        let jalr = w >> 26 == 0 && w & 63 == 9;
        if !(jalr && ts.len() >= 2 || matches!(w >> 26, 2 | 3)) || dispatch.contains_key(ts) {
            continue;
        }
        let k = dispatch.len();
        let mut cases = format!(
            "{}switch (t) {{",
            relink(ts.iter().any(|t| ovl_of(*t).is_some()))
        );
        for &t in ts {
            cases += &if let Some(name) = runtime.get(&t) {
                format!(
                    " case {}: s->cp0_known &= 1u << 10; return plaid_rt_{name}(s);",
                    sx(t)
                )
            } else if functions.contains(&t) {
                format!(" case {}: return F_{t:08x}(s, ret);", sx(t))
            } else {
                return Err(format!("{pc:08x}: call target {t:08x} is not a function"));
            };
        }
        cases += "\n";
        out += &format!(
            "{link}int plaid_call_{k}(plaid_state *s, u64 t, u64 ret, u32 pc) {{\n  (void)ret;\n  {cases}  }}\n  return plaid_fault(s, pc, 3);\n}}\n"
        );
        shared += &format!("int plaid_call_{k}(plaid_state *s, u64 t, u64 ret, u32 pc);\n");
        dispatch.insert(ts, k);
    }
    // The runtime enters guest code only here, and only at proven callbacks.
    out += "int plaid_enter(plaid_state *s, u32 entry, u64 ret) {\n";
    if !overlays.is_empty() {
        out += "  entry = plaid_link(s, entry);\n";
    }
    out += "  switch (entry) {\n";
    for t in &entered {
        out += &format!("  case 0x{0:08x}u: return F_{0:08x}(s, ret);\n", t.pc.0);
    }
    out += "  }\n  return plaid_fault(s, entry, 3);\n}\n";
    // Loop headers: targets of a backward direct transfer or table case.
    // Every other transfer inside a function moves forward, so a path that
    // never returns passes a header again and again (ADR-0159).
    let headers: BTreeSet<u32> = map
        .direct_edges
        .iter()
        .filter(|e| e.kind != EdgeKind::Call && e.target.pc.0 <= e.site.pc.0)
        .map(|e| e.target.pc.0)
        .chain(
            targets
                .iter()
                .flat_map(|(site, ts)| ts.iter().filter(move |t| **t <= *site))
                .copied(),
        )
        .collect();
    let mut seen = BTreeSet::new();
    // Address-taken calls repeat the same callees; analyze each identity once.
    let mut body_entries = BTreeSet::new();
    let bodies = returns::function_bodies_partitioned(
        map,
        image,
        callees.iter().filter(|f| body_entries.insert(*f)),
        |a| ovl_of(a.pc.0),
        &report.residual_sites,
    );
    // Blocks by start; `map.blocks` is ordered by start, so a body's blocks
    // come out in map order.
    let mut by_start: BTreeMap<_, Vec<_>> = BTreeMap::new();
    for b in &map.blocks {
        by_start.entry(&b.start).or_default().push(b);
    }
    // In-function control edges by site; calls leave the frame (ADR-0219).
    let mut edges_by_site: BTreeMap<u32, Vec<u32>> = BTreeMap::new();
    for e in map.direct_edges.iter().filter(|e| e.kind != EdgeKind::Call) {
        edges_by_site
            .entry(e.site.pc.0)
            .or_default()
            .push(e.target.pc.0);
    }
    let mut lowered = Vec::new();
    for f in callees.iter().filter(|f| seen.insert(f.pc.0)) {
        let mut out = String::new();
        let body = &bodies[f];
        let blocks: Vec<_> = body
            .iter()
            .filter_map(|b| by_start.get(b))
            .flatten()
            .copied()
            .collect();
        let fixed = ovl_of(f.pc.0).is_none();
        let range = |b: &&BasicBlock| -> Result<String, String> {
            Ok(format!(
                "{{{}u, {}u}}",
                physical(b.start.pc.0)?,
                physical(b.start.pc.0 + b.size - 1)? + 1
            ))
        };
        let mut pins = String::new();
        let mut continuations = BTreeMap::new();
        if fixed {
            let live = continuation_blocks(&blocks, &edges_by_site, &targets, &returns, &word);
            for (link, reach) in live {
                let ranges = reach.iter().map(&range).collect::<Result<Vec<_>, _>>()?;
                // An empty set still needs one entry for a valid C array.
                let shown = if ranges.is_empty() {
                    "{0u, 0u}".to_string()
                } else {
                    ranges.join(", ")
                };
                pins += &format!(
                    "static const plaid_text_range C_{:08x}_{link:08x}[] = {{{shown}}};\n",
                    f.pc.0
                );
                continuations.insert(link, ranges.len());
            }
        }
        let lowerer = Lowerer {
            frame: fixed.then_some((f.pc.0, blocks.len())),
            continuations,
            image,
            fr0: map.cop1_fr0,
            labels: body.iter().map(|b| b.pc.0).collect(),
            targets: &targets,
            returns: &returns,
            functions: &functions,
            runtime: &runtime,
            residual: &residual,
            dispatch: &dispatch,
            overlays: &overlays,
            ovl: ovl_of(f.pc.0),
        };
        // Relocated immediates are read from the bound copy (ADR-0181).
        let lower = |w: u32, pc: u32| -> Result<String, String> {
            let Some(&(k, kind)) = relocations.get(&pc) else {
                return simple(w, pc, map.cop1_fr0);
            };
            match kind {
                5 => Ok(set(
                    (w >> 16) & 31,
                    format!("SX32((plaid_ow(s, {k}, 0x{pc:08x}u) & 0xffffu) << 16)"),
                )),
                6 => simple_lo(
                    w,
                    pc,
                    map.cop1_fr0,
                    Some(&format!("plaid_ow(s, {k}, 0x{pc:08x}u)")),
                ),
                _ => Err(format!(
                    "{pc:08x}: relocation kind {kind} on executed {w:08x}"
                )),
            }
        };
        // A wrapper balances the pin on every exit, including faults and tails.
        let body_name = if let Some(k) = lowerer.ovl {
            out += &format!(
                "static int B_{0:08x}(plaid_state *s, u64 ret, plaid_native_frame *frame);\n{link}int F_{0:08x}(plaid_state *s, u64 ret) {{\n  int r;\n  s->ovl_active[{k}]++;\n  r = B_{0:08x}(s, ret, 0);\n  s->ovl_active[{k}]--;\n  return r;\n}}\n",
                f.pc.0
            );
            format!("static int B_{:08x}", f.pc.0)
        } else {
            let ranges = blocks
                .iter()
                .map(&range)
                .collect::<Result<Vec<_>, String>>()?;
            out += &format!(
                "static const plaid_text_range R_{0:08x}[] = {{{1}}};\n{pins}static int B_{0:08x}(plaid_state *s, u64 ret, plaid_native_frame *frame);\n{link}int F_{0:08x}(plaid_state *s, u64 ret) {{\n  plaid_native_frame frame = {{0, 0, R_{0:08x}, {2}}};\n  int r;\n  plaid_text_pin(s, &frame);\n  r = B_{0:08x}(s, ret, &frame);\n  plaid_text_unpin(s, &frame);\n  return r;\n}}\n",
                f.pc.0,
                ranges.join(", "),
                ranges.len()
            );
            format!("static int B_{:08x}", f.pc.0)
        };
        out += &format!(
            "{body_name}(plaid_state *s, u64 ret, plaid_native_frame *frame) {{\n  (void)ret; (void)frame;\n  goto L_{:08x};\n",
            f.pc.0
        );
        for &block in body.iter().filter_map(|b| by_start.get(b)).flatten() {
            let (start, end) = (block.start.pc.0, block.start.pc.0.wrapping_add(block.size));
            if exits.contains(&start) {
                out += &format!("L_{start:08x}: s->pc = 0x{start:08x}u; return 2;\n");
                continue;
            }
            out += &format!("L_{start:08x}:\n");
            if headers.contains(&start) {
                out += "  PLAID_SAFEPOINT(s);\n";
            }
            match (lowerer.ovl, ovl_of(start)) {
                (Some(k), Some(b)) if k == b => {
                    out += &format!(
                        "  if (!s->ovl_ok[{k}]) return plaid_fault(s, 0x{start:08x}u, 8);\n"
                    )
                }
                (None, None) => {
                    if load_of(start).is_none() {
                        let words = (start..end)
                            .step_by(4)
                            .map(|pc| word(pc).map(|w| format!("0x{w:08x}u")))
                            .collect::<Result<Vec<_>, _>>()?;
                        out += &format!(
                            "  {{ static const u32 words[] = {{{}}}; if (plaid_text_enter(s, {}u, words, {}, 0x{start:08x}u)) return 1; }}\n",
                            words.join(", "),
                            physical(start)?,
                            words.len()
                        );
                    }
                }
                _ => return Err(format!("{start:08x}: block crosses an overlay boundary")),
            }
            if let Some(l) = load_of(start) {
                out += &format!(
                    "  if (!s->load_ok[{l}] && plaid_verify_load(s, {l}, 0x{start:08x}u)) return 1;\n"
                );
            }
            let mut pc = start;
            let mut transferred = false;
            while pc < end {
                if let Some(l) = data_guards.get(&pc) {
                    out += &format!(
                        "  if (!s->load_ok[{l}] && plaid_verify_load(s, {l}, 0x{pc:08x}u)) return 1;\n"
                    );
                }
                let w = word(pc)?;
                if plaid_core::solver::is_eret(w) {
                    out += &format!("  {}\n", lowerer.control(w, pc, "")?);
                    pc += 4;
                    transferred = true;
                    if pc != end {
                        return Err(format!("{start:08x}: block continues past ERET"));
                    }
                } else if is_control(w) {
                    let slot = lower(word(pc + 4)?, pc + 4)?;
                    out += &format!("  {}\n", lowerer.control(w, pc, &slot)?);
                    pc += 8;
                    transferred = true;
                    if pc != end {
                        return Err(format!("{start:08x}: block continues past its transfer"));
                    }
                } else {
                    let s = lower(w, pc)?;
                    if !s.is_empty() {
                        out += &format!("  {s}\n");
                    }
                    pc += 4;
                }
            }
            if !transferred {
                out += &format!("  {}\n", lowerer.fallthrough(end, end - 4));
            }
        }
        out += "}\n";
        lowered.push(out);
    }
    // Contiguous shares of about equal size for the parts after the main
    // unit; with one part, all stay here.
    let share = lowered.iter().map(String::len).sum::<usize>() / parts.saturating_sub(1).max(1) + 1;
    let mut units = vec![out];
    let mut size = 0;
    for f in lowered {
        if parts > 1 && (units.len() == 1 || size >= share) && units.len() < parts {
            units.push(format!(
                "/* part {} of {parts} (ADR-0174) */\n{shared}",
                units.len()
            ));
            size = 0;
        }
        size += f.len();
        units.last_mut().expect("main unit").push_str(&f);
    }
    let mut out = units.remove(0);
    // 2: an exit was reached; 0: the host entry returned through its checked $ra.
    out += &format!(
        "static int plaid_run(plaid_state *s) {{\n  u64 host = s->r[31];\n  int r = F_{:08x}(s, host);\n  if (r == 2) return 0;\n  /* a checked return to the host's $ra hands control back (ADR-0146) */\n  if (r == 0) {{ s->pc = (u32)host; return 0; }}\n  return r;\n}}\n",
        entry.0
    );
    units.insert(0, out);
    Ok(units)
}

#[cfg(test)]
mod continuation_tests {
    use super::*;
    use plaid_core::program::CodeAddress;

    fn block(pc: u32, size: u32) -> BasicBlock {
        BasicBlock {
            start: CodeAddress {
                pc: GuestAddr(pc),
                image: "t".into(),
                generation: 0,
            },
            size,
            delay_slot_entry: false,
            evidence: Default::default(),
        }
    }

    // Blocks at 0x00 (prefix), 0x10 (call: jal at 0x10, link 0x18), 0x18 (tail).
    fn live(words: &[(u32, u32)], edges: &[(u32, u32)], targets: &[(u32, &[u32])]) -> Vec<u32> {
        let blocks = [block(0x00, 0x10), block(0x10, 0x08), block(0x18, 0x10)];
        let refs: Vec<&BasicBlock> = blocks.iter().collect();
        let words: BTreeMap<u32, u32> = words.iter().copied().collect();
        let word = |pc: u32| Ok(*words.get(&pc).unwrap_or(&0));
        let mut by_site: BTreeMap<u32, Vec<u32>> = BTreeMap::new();
        for &(s, t) in edges {
            by_site.entry(s).or_default().push(t);
        }
        let targets: BTreeMap<u32, BTreeSet<u32>> = targets
            .iter()
            .map(|(s, t)| (*s, t.iter().copied().collect()))
            .collect();
        let reach = continuation_blocks(&refs, &by_site, &targets, &BTreeSet::new(), &word);
        reach[&0x18].iter().map(|b| b.start.pc.0).collect()
    }

    const JAL: u32 = 0x0c00_0000;

    #[test]
    fn an_executed_prefix_is_not_live_after_the_call() {
        assert_eq!(live(&[(0x10, JAL)], &[], &[]), vec![0x18]);
    }

    #[test]
    fn a_loop_back_keeps_the_earlier_block_live() {
        // beq at 0x20 branches back to the prefix
        assert_eq!(
            live(&[(0x10, JAL)], &[(0x20, 0x00)], &[]),
            vec![0x00, 0x10, 0x18]
        );
    }

    #[test]
    fn jump_tables_keep_targets_and_unknown_jumps_keep_everything() {
        let jr_t0 = 0x0100_0008; // jr $t0
        assert_eq!(
            live(&[(0x10, JAL), (0x20, jr_t0)], &[], &[(0x20, &[0x10])]),
            vec![0x10, 0x18]
        );
        assert_eq!(
            live(&[(0x10, JAL), (0x20, jr_t0)], &[], &[]),
            vec![0x00, 0x10, 0x18]
        );
    }
}
