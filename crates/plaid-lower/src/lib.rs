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
   depends on write-back D-cache state this coherent model does not track;
   5: a return whose $ra is not the continuation of the call that entered
   its function (the checked call/return assumption);
   6: an overflow-trapping add/subtract that would raise an exception. */
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
    // Overflow-trapping add/sub: abort (fault 6) where the VR4300 would raise.
    let trap = |ty: &str, y: String, sub: bool, sign: &str, d: u32, wrap: &str| {
        let (op, flip) = if sub { ("-", "") } else { ("+", "~") };
        format!(
            "{{ {ty} x = ({ty}){a}, y = ({ty}){y}, z = x {op} y; if ({flip}(x ^ y) & (x ^ z) & {sign}) return plaid_fault(s, 0x{pc:08x}u, 6); {} }}",
            set(d, wrap.into())
        )
    };
    Ok(match (word >> 26, word & 63) {
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
            (1, _, 0) => conditional(format!("(s64){a} < 0")),
            (1, _, 1) => conditional(format!("(s64){a} >= 0")),
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
    let report = solve(map, images, Scope::DeclaredStaticImagesGuardedRam)?;
    if report.status != ClosureStatus::Closed {
        let kinds: BTreeSet<_> = report.blockers.iter().map(|b| b.kind.as_str()).collect();
        return Err(format!("program is not CLOSED: {kinds:?}"));
    }
    let [image] = images else {
        return Err("exactly one code image is supported".into());
    };
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
        let Some(proof) = site
            .closed_proof
            .as_ref()
            .and_then(|id| map.evidence.get(id))
        else {
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
    let base = physical(image.base.pc.0)?;
    let words: Vec<_> = image.words.iter().map(|w| format!("0x{w:08x}u")).collect();
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
    for f in callees.iter().filter(|f| seen.insert(f.pc.0)) {
        let body = returns::function_body(map, image, f);
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
    // 2: an exit was reached; 0: the host entry returned, which leaves the program.
    out += &format!(
        "static int plaid_run(plaid_state *s) {{\n  int r = F_{:08x}(s, s->r[31]);\n  if (r == 2) return 0;\n  return r ? r : plaid_fault(s, 0x{:08x}u, 5);\n}}\n",
        entry.0, entry.0
    );
    Ok(out)
}
