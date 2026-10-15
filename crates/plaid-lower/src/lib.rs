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
    program::{EdgeKind, ProgramMap},
    returns,
    solver::{ClosureStatus, Scope, solve},
};
use std::collections::{BTreeMap, BTreeSet};

pub mod coverage;

const PRELUDE: &str = r#"#include <stdint.h>
#include <string.h>
#include <fenv.h>
typedef uint8_t u8; typedef uint32_t u32; typedef int32_t s32;
typedef uint64_t u64; typedef int64_t s64;
#define PLAID_RAM_SIZE 0x800000u
typedef struct {
  u64 r[32]; u64 hi, lo; u64 f[32]; u32 fcc; u32 fcsr; u32 llbit; u32 pc; u32 fault; u32 fault_pc;
  u8 ram[PLAID_RAM_SIZE];
  u8 line_segment[PLAID_RAM_SIZE / 16]; /* 0 untouched, 1 KSEG0, 2 KSEG1 */
  u8 load_ok[64]; /* declared load verified in RAM (ADR-0136) */
} plaid_state;
/* executable bytes; load: index of the declared load holding them, or -1 */
typedef struct { u32 start, end; int load; } plaid_range;
#define SX32(v) ((u64)(s64)(s32)(u32)(v))
/* fault 1: address/alignment outside the supported model; 2: store to
   executable bytes (declared immutable); 3: transfer without a proven target;
   4: one RDRAM line accessed through both KSEG0 and KSEG1, whose result
   depends on write-back D-cache state this coherent model does not track;
   5: a return whose $ra is not the continuation of the call that entered
   its function (the checked call/return assumption);
   6: an overflow-trapping add/subtract that would raise an exception;
   7: a COP1 operation outside the modeled subset: a NaN or subnormal
      operand, an out-of-range conversion, or an enabled FPU exception;
   8: code of a declared load entered while RAM does not hold its declared
      bytes. Executable bytes of a load not yet verified may be written;
   9: a BREAK was reached (its exception handler is not modeled);
   10: a conditional trap was taken (its exception handler is not modeled). */
static inline int plaid_fault(plaid_state *s, u32 pc, u32 code) {
  s->fault = code; s->fault_pc = pc; return 1;
}
"#;

const HELPERS: &str = r#"static inline int plaid_addr(plaid_state *s, u64 va, u32 size, u32 pc, int write, u32 *out) {
  u32 v = (u32)va, p, i;
  if (va != SX32(v) || (v & (size - 1)) || v < 0x80000000u || v >= 0xc0000000u)
    return plaid_fault(s, pc, 1);
  p = v & 0x1fffffffu;
  if (p > PLAID_RAM_SIZE - size) return plaid_fault(s, pc, 1);
  if (s->line_segment[p >> 4] && s->line_segment[p >> 4] != (v < 0xa0000000u ? 1 : 2))
    return plaid_fault(s, pc, 4);
  s->line_segment[p >> 4] = v < 0xa0000000u ? 1 : 2;
  if (write)
    for (i = 0; i < sizeof plaid_code / sizeof plaid_code[0]; i++)
      if (p < plaid_code[i].end && p + size > plaid_code[i].start &&
          (plaid_code[i].load < 0 || s->load_ok[plaid_code[i].load]))
        return plaid_fault(s, pc, 2);
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
/* Host runtime functions call this before writing guest RAM at physical p. */
int plaid_runtime_write(plaid_state *s, u32 p, u32 size, u32 pc) {
  u32 i;
  if (p > PLAID_RAM_SIZE || size > PLAID_RAM_SIZE - p) return plaid_fault(s, pc, 1);
  for (i = 0; i < sizeof plaid_code / sizeof plaid_code[0]; i++)
    if (p < plaid_code[i].end && p + size > plaid_code[i].start &&
        (plaid_code[i].load < 0 || s->load_ok[plaid_code[i].load]))
      return plaid_fault(s, pc, 2);
  return 0;
}
static inline int plaid_load(plaid_state *s, u64 va, u32 size, u32 pc, u64 *value) {
  u32 p, i; u64 x = 0;
  if (plaid_addr(s, va, size, pc, 0, &p)) return 1;
  for (i = 0; i < size; i++) x = x << 8 | s->ram[p + i];
  *value = x; return 0;
}
static inline int plaid_store(plaid_state *s, u64 va, u32 size, u64 value, u32 pc) {
  u32 p, i;
  if (plaid_addr(s, va, size, pc, 1, &p)) return 1;
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
fn simple(word: u32, pc: u32) -> Result<String, String> {
    let (rs, rt, rd, sa) = (
        (word >> 21) & 31,
        (word >> 16) & 31,
        (word >> 11) & 31,
        (word >> 6) & 31,
    );
    let (imm, simm) = (word & 0xffff, word as u16 as i16);
    let (a, b) = (format!("s->r[{rs}]"), format!("s->r[{rt}]"));
    let addr = format!("{a} + (u64)(s64){simm}");
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
    Ok(match (word >> 26, word & 63) {
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
        // COP1 data moves with 64-bit FPRs (Status.FR = 1): 32-bit forms
        // replace only the low word, as on the VR4300 (ADR-0131).
        (17, _) if word & 0x7ff == 0 => {
            let f = format!("s->f[{rd}]");
            match rs {
                0 => set(rt, format!("SX32((u32){f})")),
                1 => set(rt, f),
                4 => format!("{f} = ({f} & 0xffffffff00000000ull) | (u32){b};"),
                5 => format!("{f} = {b};"),
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
                "{{ {ty} x, y; {bits} xb = {lane}s->f[{rd}], yb = {lane}s->f[{rt}]; memcpy(&x, &xb, sizeof x); memcpy(&y, &yb, sizeof y); s->fcsr &= ~0x3f000u; if (x != x || y != y) return plaid_fault(s, 0x{pc:08x}u, 7); s->fcc = ({} && x < y) || ({} && x == y); }}",
                f >> 2 & 1,
                f >> 1 & 1
            )
        }
        // COP1 arithmetic and conversions (ADR-0139); fd is the sa field.
        (17, f) if matches!(rs, 16 | 17) && matches!(f, 0..=5 | 7) => {
            let kind = if rs == 16 { "s" } else { "d" };
            format!("if (plaid_arith_{kind}(s, {f}, {sa}, {rd}, {rt}, 0x{pc:08x}u)) return 1;")
        }
        (17, 6) if matches!(rs, 16 | 17) => format!("s->f[{sa}] = s->f[{rd}];"),
        (17, f @ (8..=15 | 36 | 37)) if matches!(rs, 16 | 17) => {
            let (x, bad) = if rs == 16 {
                (
                    format!("(double)plaid_f32((u32)s->f[{rd}])"),
                    format!("plaid_f32_bad((u32)s->f[{rd}])"),
                )
            } else {
                (
                    format!("plaid_f64(s->f[{rd}])"),
                    format!("plaid_f64_bad(s->f[{rd}])"),
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
            format!("if (plaid_to_s(s, {rs}, {sa}, {rd}, 0x{pc:08x}u)) return 1;")
        }
        (17, 33) if matches!(rs, 16 | 20 | 21) => {
            format!("if (plaid_to_d(s, {rs}, {sa}, {rd}, 0x{pc:08x}u)) return 1;")
        }
        (49, _) => format!(
            "{{ u64 v; if (plaid_load(s, {addr}, 4, 0x{pc:08x}u, &v)) return 1; s->f[{rt}] = (s->f[{rt}] & 0xffffffff00000000ull) | v; }}"
        ),
        (53, _) => format!("if (plaid_load(s, {addr}, 8, 0x{pc:08x}u, &s->f[{rt}])) return 1;"),
        (57, _) => {
            format!("if (plaid_store(s, {addr}, 4, (u32)s->f[{rt}], 0x{pc:08x}u)) return 1;")
        }
        (61, _) => format!("if (plaid_store(s, {addr}, 8, s->f[{rt}], 0x{pc:08x}u)) return 1;"),
        (63, _) => store(8),
        (0, 33) => set(rd, format!("SX32((u32){a} + (u32){b})")),
        (0, 35) => set(rd, format!("SX32((u32){a} - (u32){b})")),
        (0, 36) => set(rd, format!("{a} & {b}")),
        (0, 37) => set(rd, format!("{a} | {b}")),
        (0, 38) => set(rd, format!("{a} ^ {b}")),
        (0, 39) => set(rd, format!("~({a} | {b})")),
        (0, 42) => set(rd, format!("(u64)((s64){a} < (s64){b})")),
        (0, 43) => set(rd, format!("(u64)({a} < {b})")),
        (9, _) => set(rt, format!("SX32((u32){a} + (u32)(s32){simm})")),
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
    })
}

struct Lowerer<'a> {
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
}

impl Lowerer<'_> {
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
    fn call(&self, target: u32, link: u32, pc: u32) -> Result<String, String> {
        if let Some(name) = self.runtime.get(&target) {
            return Ok(format!(
                "{{ int r = plaid_rt_{name}(s); if (r) return r; }} {}",
                self.fallthrough(link, pc)
            ));
        }
        if !self.functions.contains(&target) {
            return Err(format!(
                "{pc:08x}: call target {target:08x} is not a function"
            ));
        }
        Ok(format!(
            "{{ int r = F_{target:08x}(s, {}); if (r) return r; }} {}",
            sx(link),
            self.fallthrough(link, pc)
        ))
    }
    fn control(&self, word: u32, pc: u32, slot: &str) -> Result<String, String> {
        let (rs, rt, rd) = ((word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31);
        let (a, b) = (format!("s->r[{rs}]"), format!("s->r[{rt}]"));
        let after = pc.wrapping_add(8);
        let branch = pc
            .wrapping_add(4)
            .wrapping_add_signed(i32::from(word as u16 as i16) * 4);
        let jump = (pc.wrapping_add(4) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2);
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
        match (word >> 26, word & 63, rt) {
            (0, 8, _) if self.returns.contains(&pc) => Ok(format!(
                "{{ u64 t = {a}; {slot} if (t != ret) return plaid_fault(s, 0x{pc:08x}u, 5); return 0; }}"
            )),
            (0, 8, _) => {
                let mut cases = String::new();
                for &t in proven()? {
                    cases += &format!(" case {}: {}", sx(t), self.goto(t)?);
                }
                Ok(format!(
                    "{{ u64 t = {a}; {slot} switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}"
                ))
            }
            (0, 9, _) => {
                let mut cases = String::new();
                for &t in proven()? {
                    cases += &format!(" case {}: {}", sx(t), self.call(t, after, pc)?);
                }
                Ok(format!(
                    "{{ u64 t = {a}; {} {slot} switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}",
                    set(rd, sx(after))
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
            )),
            (17, _, _) if rs == 8 => conditional(format!(
                "(s->fcsr &= ~0x3f000u, {}s->fcc)",
                if rt & 1 == 0 { "!" } else { "" }
            )),
            (1, _, 0) => conditional(format!("(s64){a} < 0")),
            (1, _, 1) => conditional(format!("(s64){a} >= 0")),
            // BLTZAL BGEZAL (likely: 18, 19) link first, then test rs, as ares.
            (1, _, 16..=19) => {
                let test = format!("(s64){a} {} 0", if rt & 1 == 0 { "<" } else { ">=" });
                let call = self.call(branch, after, pc)?;
                let link = set(31, sx(after));
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
                "{slot} {{ int r = plaid_rt_{}(s); if (r) return r; }} if (s->r[31] != ret) return plaid_fault(s, 0x{pc:08x}u, 5); return 0;",
                self.runtime[&jump]
            )),
            (2, _, _) => Ok(format!("{slot} {}", self.goto(jump)?)),
            (3, _, _) => Ok(format!(
                "s->r[31] = {}; {slot} {}",
                sx(after),
                self.call(jump, after, pc)?
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
    lower_c_with_preload(map, images, image, entry, exits)
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
) -> Result<String, String> {
    // Address-taken dispatch is its own scope (ADR-0153).
    let scope = if map.address_taken.is_empty() {
        Scope::DeclaredStaticImagesGuardedRam
    } else {
        Scope::DeclaredStaticImagesGuardedRamAddressTaken
    };
    let report = solve(map, images, scope)?;
    if report.status != ClosureStatus::Closed {
        let kinds: BTreeSet<_> = report.blockers.iter().map(|b| b.kind.as_str()).collect();
        return Err(format!("program is not CLOSED: {kinds:?}"));
    }
    let [image] = images else {
        return Err("exactly one code image is supported".into());
    };
    let loads: Vec<(u32, u32)> = map
        .load_images
        .get(&image.base.image)
        .map(|spec| {
            spec.loads
                .iter()
                .map(|l| {
                    (
                        l.destination.start.0,
                        l.destination.start.0 + l.destination.size,
                    )
                })
                .collect()
        })
        .unwrap_or_default();
    if loads.len() > 64 {
        return Err("at most 64 declared loads are supported".into());
    }
    let load_of = |start: u32| loads.iter().position(|(s, e)| *s <= start && start < *e);
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
    let runtime: BTreeMap<u32, String> = map
        .runtime_functions
        .iter()
        .map(|(a, f)| (a.pc.0, f.name.clone()))
        .collect();
    let mut targets = BTreeMap::new();
    let mut returns = BTreeSet::new();
    let mut callees = vec![host.clone()];
    for site in &map.indirect_sites {
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
        if site.link_register.is_some() {
            callees.extend(site.candidates.keys().cloned());
        }
        targets.insert(
            site.site.pc.0,
            site.candidates
                .keys()
                .map(|t| t.pc.0)
                .collect::<BTreeSet<_>>(),
        );
    }
    callees.extend(
        map.direct_edges
            .iter()
            .filter(|e| e.kind == EdgeKind::Call)
            .map(|e| e.target.clone()),
    );
    let entered = plaid_core::callbacks::targets(map, image);
    callees.extend(entered.iter().cloned());
    callees.retain(|f| !runtime.contains_key(&f.pc.0));
    let functions: BTreeSet<u32> = callees.iter().map(|f| f.pc.0).collect();

    let mut code = Vec::new();
    for block in &map.blocks {
        if block.delay_slot_entry {
            return Err(format!(
                "{:08x}: delay-slot entry blocks are unsupported",
                block.start.pc.0
            ));
        }
        let (start, end) = (block.start.pc.0, block.start.pc.0.wrapping_add(block.size));
        code.push(format!(
            "{{{}, {}, {}}}",
            physical(start)?,
            physical(end - 1)? + 1,
            load_of(start).map_or(-1, |l| l as i64)
        ));
    }
    // Jump tables are store-protected like code (ADR-0132).
    for site in &map.indirect_sites {
        if let Some((start, count)) = plaid_core::tables::table_range(map, image, site) {
            code.push(format!(
                "{{{}, {}, {}}}",
                physical(start.0)?,
                physical(start.0 + count * 4 - 1)? + 1,
                load_of(start.0).map_or(-1, |l| l as i64)
            ));
        }
    }
    let mut out = String::from(PRELUDE);
    out += &format!(
        "static const plaid_range plaid_code[] = {{{}}};\n{HELPERS}",
        code.join(", ")
    );
    if !loads.is_empty() {
        // Expected bytes come from the composite image (ADR-0136).
        let words: Vec<_> = image.words.iter().map(|w| format!("0x{w:08x}u")).collect();
        out += &format!(
            "static const u32 plaid_declared[] = {{{}}};\nstatic int plaid_verify_load(plaid_state *s, int load, u32 pc) {{\n  u32 i, j, o;\n  for (i = 0; i < sizeof plaid_code / sizeof plaid_code[0]; i++)\n    if (plaid_code[i].load == load)\n      for (j = plaid_code[i].start; j < plaid_code[i].end; j++) {{\n        o = j - 0x{:x}u;\n        if (s->ram[j] != (u8)(plaid_declared[o / 4] >> (24 - 8 * (o % 4)))) return plaid_fault(s, pc, 8);\n      }}\n  s->load_ok[load] = 1; return 0;\n}}\n",
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
    for name in runtime.values() {
        out += &format!("int plaid_rt_{name}(plaid_state *s);\n");
    }
    for f in &functions {
        out += &format!("static int F_{f:08x}(plaid_state *s, u64 ret);\n");
    }
    // The runtime enters guest code only here, and only at proven callbacks.
    out += "int plaid_enter(plaid_state *s, u32 entry, u64 ret) {\n  switch (entry) {\n";
    for t in &entered {
        out += &format!("  case 0x{0:08x}u: return F_{0:08x}(s, ret);\n", t.pc.0);
    }
    out += "  }\n  return plaid_fault(s, entry, 3);\n}\n";
    let mut seen = BTreeSet::new();
    let bodies = returns::function_bodies(map, image, callees.iter());
    for f in callees.iter().filter(|f| seen.insert(f.pc.0)) {
        let body = &bodies[f];
        let lowerer = Lowerer {
            labels: body.iter().map(|b| b.pc.0).collect(),
            targets: &targets,
            returns: &returns,
            functions: &functions,
            runtime: &runtime,
        };
        out += &format!(
            "static int F_{:08x}(plaid_state *s, u64 ret) {{\n  (void)ret;\n  goto L_{:08x};\n",
            f.pc.0, f.pc.0
        );
        for block in map.blocks.iter().filter(|b| body.contains(&b.start)) {
            let (start, end) = (block.start.pc.0, block.start.pc.0.wrapping_add(block.size));
            if exits.contains(&start) {
                out += &format!("L_{start:08x}: s->pc = 0x{start:08x}u; return 2;\n");
                continue;
            }
            out += &format!("L_{start:08x}:\n");
            if let Some(l) = load_of(start) {
                out += &format!(
                    "  if (!s->load_ok[{l}] && plaid_verify_load(s, {l}, 0x{start:08x}u)) return 1;\n"
                );
            }
            let mut pc = start;
            let mut transferred = false;
            while pc < end {
                let w = word(pc)?;
                if is_control(w) {
                    let slot = simple(word(pc + 4)?, pc + 4)?;
                    out += &format!("  {}\n", lowerer.control(w, pc, &slot)?);
                    pc += 8;
                    transferred = true;
                    if pc != end {
                        return Err(format!("{start:08x}: block continues past its transfer"));
                    }
                } else {
                    let s = simple(w, pc)?;
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
    }
    // 2: an exit was reached; 0: the host entry returned through its checked $ra.
    out += &format!(
        "static int plaid_run(plaid_state *s) {{\n  u64 host = s->r[31];\n  int r = F_{:08x}(s, host);\n  if (r == 2) return 0;\n  /* a checked return to the host's $ra hands control back (ADR-0146) */\n  if (r == 0) {{ s->pc = (u32)host; return 0; }}\n  return r;\n}}\n",
        entry.0
    );
    Ok(out)
}
