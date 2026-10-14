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
    program::ProgramMap,
    solver::{ClosureStatus, Scope, solve},
};
use std::collections::{BTreeMap, BTreeSet};

const PRELUDE: &str = r#"#include <stdint.h>
typedef uint8_t u8; typedef uint32_t u32; typedef int32_t s32;
typedef uint64_t u64; typedef int64_t s64;
#define PLAID_RAM_SIZE 0x800000u
typedef struct {
  u64 r[32]; u64 hi, lo; u32 pc; u32 fault; u32 fault_pc;
  u8 ram[PLAID_RAM_SIZE];
  u8 line_segment[PLAID_RAM_SIZE / 16]; /* 0 untouched, 1 KSEG0, 2 KSEG1 */
} plaid_state;
typedef struct { u32 start, end; } plaid_range;
#define SX32(v) ((u64)(s64)(s32)(u32)(v))
/* fault 1: address/alignment outside the supported model; 2: store to
   executable bytes (declared immutable); 3: transfer without a proven target;
   4: one RDRAM line accessed through both KSEG0 and KSEG1, whose result
   depends on write-back D-cache state this coherent model does not track. */
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
      if (p < plaid_code[i].end && p + size > plaid_code[i].start) return plaid_fault(s, pc, 2);
  *out = p; return 0;
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
        1..=7 | 20..=23 => true,
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
    Ok(match (word >> 26, word & 63) {
        (0, 0) => set(rd, format!("SX32((u32){b} << {sa})")),
        (0, 2) => set(rd, format!("SX32((u32){b} >> {sa})")),
        (0, 3) => set(rd, format!("SX32((s64){b} >> {sa})")),
        (0, 4) => set(rd, format!("SX32((u32){b} << ({a} & 31))")),
        (0, 6) => set(rd, format!("SX32((u32){b} >> ({a} & 31))")),
        (0, 7) => set(rd, format!("SX32((s64){b} >> ({a} & 31))")),
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
    labels: BTreeSet<u32>,
    targets: BTreeMap<u32, &'a BTreeSet<u32>>,
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
        match (word >> 26, word & 63, rt) {
            (0, 8 | 9, _) => {
                let link = if word & 63 == 9 {
                    set(rd, sx(after))
                } else {
                    String::new()
                };
                let set = self
                    .targets
                    .get(&pc)
                    .ok_or_else(|| format!("{pc:08x}: indirect site lacks a proven target set"))?;
                let mut cases = String::new();
                for &t in set.iter() {
                    cases += &format!(" case {}: {}", sx(t), self.goto(t)?);
                }
                Ok(format!(
                    "{{ u64 t = {a}; {link} {slot} switch (t) {{{cases} }} return plaid_fault(s, 0x{pc:08x}u, 3); }}"
                ))
            }
            (1, _, 0) => conditional(format!("(s64){a} < 0")),
            (1, _, 1) => conditional(format!("(s64){a} >= 0")),
            (2, _, _) => Ok(format!("{slot} {}", self.goto(jump)?)),
            (3, _, _) => Ok(format!(
                "s->r[31] = {}; {slot} {}",
                sx(after),
                self.goto(jump)?
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

/// Lower a program CLOSED under the guarded-RAM declared-static scope to C. `exits` are host-boundary
/// addresses: reaching one returns 0 from `plaid_run` with `s->pc` set.
pub fn lower_c(
    map: &ProgramMap,
    images: &[CodeImage],
    entry: GuestAddr,
    exits: &[GuestAddr],
) -> Result<String, String> {
    let report = solve(map, images, Scope::DeclaredStaticImagesGuardedRam)?;
    if report.status != ClosureStatus::Closed {
        let kinds: BTreeSet<_> = report.blockers.iter().map(|b| b.kind.as_str()).collect();
        return Err(format!("program is not CLOSED: {kinds:?}"));
    }
    // Proven indirect targets also become map entries; the host enters only here.
    if !map.entries.keys().any(|e| e.pc == entry) {
        return Err(format!("{:08x} is not a map entry", entry.0));
    }
    let word = |pc: u32| -> Result<u32, String> {
        images
            .iter()
            .find_map(|i| i.word(GuestAddr(pc)))
            .ok_or_else(|| format!("{pc:08x} has no supplied instruction word"))
    };
    let exits: BTreeSet<u32> = exits.iter().map(|e| e.0).collect();
    let mut targets = BTreeMap::new();
    for site in &map.indirect_sites {
        if site.closed_proof.is_none() {
            return Err(format!(
                "{:08x}: indirect site has no closure proof",
                site.site.pc.0
            ));
        }
        targets.insert(
            site.site.pc.0,
            site.candidates
                .keys()
                .map(|t| t.pc.0)
                .collect::<BTreeSet<_>>(),
        );
    }
    let targets = targets.iter().map(|(pc, set)| (*pc, set)).collect();
    let mut labels: BTreeSet<u32> = map.blocks.iter().map(|b| b.start.pc.0).collect();
    labels.extend(&exits);
    let lowerer = Lowerer { labels, targets };

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
            "{{{}, {}}}",
            physical(start)?,
            physical(end - 1)? + 1
        ));
    }
    let mut out = String::from(PRELUDE);
    out += &format!(
        "static const plaid_range plaid_code[] = {{{}}};\n{HELPERS}",
        code.join(", ")
    );
    out += "static inline void plaid_load_images(plaid_state *s) {\n  u32 i;\n";
    for (n, image) in images.iter().enumerate() {
        let words: Vec<_> = image.words.iter().map(|w| format!("0x{w:08x}u")).collect();
        out += &format!(
            "  {{ static const u32 w{n}[] = {{{}}};\n    for (i = 0; i < {}; i++) {{ s->ram[0x{:x} + 4 * i] = (u8)(w{n}[i] >> 24); s->ram[0x{:x} + 4 * i + 1] = (u8)(w{n}[i] >> 16); s->ram[0x{:x} + 4 * i + 2] = (u8)(w{n}[i] >> 8); s->ram[0x{:x} + 4 * i + 3] = (u8)w{n}[i]; }} }}\n",
            words.join(", "),
            words.len(),
            physical(image.base.pc.0)?,
            physical(image.base.pc.0)?,
            physical(image.base.pc.0)?,
            physical(image.base.pc.0)?,
        );
    }
    out += "}\nstatic int plaid_run(plaid_state *s) {\n";
    out += &format!("  {}\n", lowerer.goto(entry.0)?);
    for &exit in &exits {
        out += &format!("L_{exit:08x}: s->pc = 0x{exit:08x}u; return 0;\n");
    }
    for block in map.blocks.iter().filter(|b| !exits.contains(&b.start.pc.0)) {
        let (start, end) = (block.start.pc.0, block.start.pc.0.wrapping_add(block.size));
        out += &format!("L_{start:08x}:\n");
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
    Ok(out)
}
