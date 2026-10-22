//! RSP microcode lowering (ADR-0167..0169).
//!
//! A text is a span of IMEM bytes, usually a whole 4 KiB snapshot, and every
//! word of it gets a label. Register jumps dispatch over exactly those
//! labels, so the target set is closed by construction. The lowered code
//! runs a word only while IMEM still holds the bytes it was lowered from
//! (DMA can rewrite IMEM); anything else leaves the text for the host to
//! pick another. Semantics follow pinned ares (`ares/n64/rsp`).

const PRELUDE: &str = include_str!("rsp_prelude.h");
const VECTOR_UNIT: &str = include_str!("rsp_vu.h");

fn reg(n: u32) -> String {
    format!("r->r[{n}]")
}

/// `dst = value;`, or nothing for `$zero`.
fn set(n: u32, value: String) -> String {
    if n == 0 {
        String::new()
    } else {
        format!("{} = {value};", reg(n))
    }
}

fn is_control(w: u32) -> bool {
    match w >> 26 {
        0 => matches!(w & 0x3f, 8 | 9),
        1 => matches!((w >> 16) & 31, 0 | 1 | 16 | 17),
        2..=7 => true,
        _ => false,
    }
}

/// One non-control instruction at `pc`, or an error naming what is
/// unsupported. `verify` re-checks the text after a DMA may have written IMEM.
fn simple(w: u32, pc: u32, verify: &str) -> Result<String, String> {
    let (rs, rt, rd, sa) = (
        (w >> 21) & 31,
        (w >> 16) & 31,
        (w >> 11) & 31,
        (w >> 6) & 31,
    );
    let simm = w as u16 as i16 as i32;
    let uimm = w & 0xffff;
    let (s, t) = (reg(rs), reg(rt));
    let addr = format!("{s} + (u32){simm}");
    let unsupported = || Err(format!("{pc:03x}: unsupported RSP instruction {w:08x}"));
    Ok(match w >> 26 {
        0 => match w & 0x3f {
            0 => set(rd, format!("{t} << {sa}")),
            2 => set(rd, format!("{t} >> {sa}")),
            3 => set(rd, format!("(u32)((s32){t} >> {sa})")),
            4 => set(rd, format!("{t} << ({s} & 31)")),
            6 => set(rd, format!("{t} >> ({s} & 31)")),
            7 => set(rd, format!("(u32)((s32){t} >> ({s} & 31))")),
            13 => format!(
                "r->broken = 1; r->halted = 1; r->pc = 0x{:03x}u; return 0;",
                (pc + 4) & 0xfff
            ),
            32 | 33 => set(rd, format!("{s} + {t}")),
            34 | 35 => set(rd, format!("{s} - {t}")),
            36 => set(rd, format!("{s} & {t}")),
            37 => set(rd, format!("{s} | {t}")),
            38 => set(rd, format!("{s} ^ {t}")),
            39 => set(rd, format!("~({s} | {t})")),
            42 => set(rd, format!("(u32)((s32){s} < (s32){t})")),
            43 => set(rd, format!("(u32)({s} < {t})")),
            _ => return unsupported(),
        },
        8 | 9 => set(rt, format!("{s} + (u32){simm}")),
        10 => set(rt, format!("(u32)((s32){s} < {simm})")),
        11 => set(rt, format!("(u32)({s} < (u32){simm})")),
        12 => set(rt, format!("{s} & 0x{uimm:x}u")),
        13 => set(rt, format!("{s} | 0x{uimm:x}u")),
        14 => set(rt, format!("{s} ^ 0x{uimm:x}u")),
        15 => set(rt, format!("0x{:x}u", uimm << 16)),
        16 => match rs {
            0 if rt == 0 => {
                format!("{{ u32 v; if (plaid_rsp_mfc0(r, {rd}, &v, 0x{pc:03x}u)) return 1; }}")
            }
            0 => format!("{{ if (plaid_rsp_mfc0(r, {rd}, &{t}, 0x{pc:03x}u)) return 1; }}"),
            4 => format!(
                "{{ if (plaid_rsp_mtc0(r, {rd}, {t}, 0x{pc:03x}u)) return 1; if (r->halted) {{ r->pc = 0x{:03x}u; return 0; }} if (r->imem_written) {{ r->imem_written = 0; {verify} }} }}",
                (pc + 4) & 0xfff
            ),
            _ => return unsupported(),
        },
        // COP2 (ADR-0168): moves, then computational ops (bit 25) by function
        18 if rs & 16 == 0 => {
            let e = (w >> 7) & 15;
            match rs {
                0 => format!("plaid_mfc2(r, {rt}, {rd}, {e});"),
                2 => format!("plaid_cfc2(r, {rt}, {rd});"),
                4 => format!("plaid_mtc2(r, {rt}, {rd}, {e});"),
                6 => format!("plaid_ctc2(r, {rt}, {rd});"),
                _ => return unsupported(),
            }
        }
        18 => {
            let (f, e, vd, de) = (w & 0x3f, (w >> 21) & 15, sa, rd & 7);
            match f {
                0x30 | 0x31 | 0x34 | 0x35 => format!(
                    "plaid_vdiv(r, {}, {}, {vd}, {de}, {rt}, {e});",
                    f >> 2 & 1,
                    f & 1
                ),
                0x32 | 0x36 => format!("plaid_vdivh(r, {vd}, {de}, {rt}, {e});"),
                0x33 => format!("plaid_vmov(r, {vd}, {de}, {rt}, {e});"),
                0x37 | 0x3f => String::new(), // VNOP, VNULL
                // ares runs the reserved encodings as VZERO; no microcode
                // should rely on that, so they stay unsupported.
                0x00..=0x11 | 0x13..=0x15 | 0x1d | 0x20..=0x2d => {
                    format!("plaid_vu(r, 0x{f:02x}, {vd}, {rd}, {rt}, {e});")
                }
                _ => return unsupported(),
            }
        }
        // LWC2 / SWC2: the opcode is in rd, the element in bits 7..10 and a
        // 7-bit signed offset scaled by the access size.
        50 | 58 if rd <= 11 && (rd != 10 || w >> 26 == 58) => format!(
            "plaid_{}(r, {rd}, {rt}, {rs}, {}, {});",
            if w >> 26 == 50 { "lwc2" } else { "swc2" },
            (w as i32) << 25 >> 25,
            (w >> 7) & 15
        ),
        32 => set(rt, format!("(u32)(s32)(s8)plaid_rsp_ld(r, {addr}, 1)")),
        33 => set(rt, format!("(u32)(s32)(s16)plaid_rsp_ld(r, {addr}, 2)")),
        35 | 39 => set(rt, format!("plaid_rsp_ld(r, {addr}, 4)")),
        36 => set(rt, format!("plaid_rsp_ld(r, {addr}, 1)")),
        37 => set(rt, format!("plaid_rsp_ld(r, {addr}, 2)")),
        40 => format!("plaid_rsp_st(r, {addr}, 1, {t});"),
        41 => format!("plaid_rsp_st(r, {addr}, 2, {t});"),
        43 => format!("plaid_rsp_st(r, {addr}, 4, {t});"),
        _ => return unsupported(),
    })
}

/// A lowered text: C source, and the words that became fault stubs.
pub struct LoweredRsp {
    pub c: String,
    pub stubs: Vec<String>,
}

/// Entry words reachable through direct control flow, including delay slots.
/// Register targets are checked by closed native dispatch and per-word fetch
/// identity guards; they do not extend this startup selection mask.
pub struct RspReachability {
    pub words: Vec<u32>,
    pub indirect: bool,
    pub exits: Vec<u32>,
}

pub fn reachable_words(text: &[u8], imem: u32) -> Result<RspReachability, String> {
    if text.is_empty()
        || !text.len().is_multiple_of(4)
        || !imem.is_multiple_of(4)
        || imem as usize + text.len() > 0x1000
    {
        return Err("reachability text must be word-aligned and fit in IMEM".into());
    }
    let end = imem + text.len() as u32;
    let mut seen = std::collections::BTreeSet::new();
    let mut visited = std::collections::BTreeSet::new();
    let mut exits = std::collections::BTreeSet::new();
    let mut pending = vec![imem];
    let mut indirect = false;
    while let Some(pc) = pending.pop() {
        if !(imem..end).contains(&pc) {
            exits.insert(pc);
            continue;
        }
        if !visited.insert(pc) {
            continue;
        }
        seen.insert(pc);
        let i = (pc - imem) as usize;
        let w = u32::from_be_bytes(text[i..i + 4].try_into().unwrap());
        if !is_control(w) {
            if !(w >> 26 == 0 && w & 63 == 13) && simple(w, pc, "").is_ok() {
                pending.push((pc + 4) & 0xfff);
            }
            continue;
        }
        // Fetching a transfer also fetches its delay slot. Invalid slots fault
        // in native code, but still belong to the identity certificate.
        let slot_pc = (pc + 4) & 0xfff;
        if slot_pc < imem || slot_pc >= end {
            exits.insert(slot_pc);
            continue;
        }
        seen.insert(slot_pc);
        if w >> 26 == 0 {
            indirect = true;
            continue;
        }
        if matches!(w >> 26, 2 | 3) {
            pending.push((w << 2) & 0xfff);
        } else {
            pending.push((pc + 8) & 0xfff);
            pending.push((pc + 4).wrapping_add((w as i16 as i32 as u32) << 2) & 0xfff);
        }
    }
    Ok(RspReachability {
        words: seen.into_iter().collect(),
        indirect,
        exits: exits.into_iter().collect(),
    })
}

/// Content filter for text an SDK overlay table names (ADR-0243). The table
/// already says where and how long it is, so an overlay of 64 bytes or more passes when every
/// word is code and at least one is an RSP-specific operation.
pub fn plausible_overlay(text: &[u8]) -> bool {
    let words: Vec<_> = text
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    text.len() >= 64
        && text.len().is_multiple_of(4)
        && words.iter().any(|&w| rsp_specific(w))
        && words
            .iter()
            .enumerate()
            .all(|(i, &w)| is_control(w) || simple(w, i as u32 * 4, "").is_ok())
}

fn rsp_specific(w: u32) -> bool {
    (w >> 26 == 16 && matches!((w >> 21) & 31, 0 | 4) && (w >> 11) & 31 < 16)
        || (w >> 26 == 18 && w & (1 << 25) != 0)
}

/// Content filter for ROM pointer hints. False negatives remain unsupported;
/// this is deliberately not evidence of whole-ROM RSP closure.
pub fn plausible_text(text: &[u8]) -> bool {
    if text.len() < 128 {
        return false;
    }
    let words: Vec<_> = text[..text.len().min(256)]
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let specific = words.iter().filter(|&&w| rsp_specific(w)).count();
    specific >= 2
        && words
            .iter()
            .take(32)
            .enumerate()
            .all(|(i, &w)| is_control(w) || simple(w, i as u32 * 4, "").is_ok())
}

/// Lowers the IMEM bytes `text` at offset `imem` to
/// `int plaid_rsp_<name>(plaid_rsp *r, u32 pc)` and the descriptor
/// `plaid_rsp_text_<name>`. The function runs from `pc` until the RSP halts
/// (returns 0), faults (1), or reaches a word it cannot run (2, `r->pc`).
/// Words that are not lowerable become fault-6 stubs: a snapshot holds
/// leftover bytes, and only the words that execute must be code.
pub fn lower_rsp(text: &[u8], imem: u32, name: &str) -> Result<LoweredRsp, String> {
    if !name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') || name.is_empty() {
        return Err(format!("bad microcode name {name:?}"));
    }
    if !imem.is_multiple_of(4)
        || !text.len().is_multiple_of(4)
        || text.is_empty()
        || imem as usize + text.len() > 0x1000
    {
        return Err("microcode text must be word-aligned and fit in IMEM".into());
    }
    let words: Vec<u32> = text
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let end = imem + 4 * words.len() as u32;
    let verify = format!(
        "plaid_rsp_verify(r, plaid_rsp_bytes_{name}, 0x{imem:03x}u, 0x{:x}u);",
        text.len()
    );
    let label = |pc: u32| format!("L_{pc:03x}");
    // a direct transfer: a label inside the text, else leave it
    let go = |target: u32| {
        if (imem..end).contains(&target) {
            format!("goto {};", label(target))
        } else {
            format!("return plaid_rsp_leave(r, 0x{target:03x}u);")
        }
    };
    let bytes: Vec<String> = text.iter().map(|b| b.to_string()).collect();
    let mut out = format!(
        "static const u8 plaid_rsp_bytes_{name}[{}] = {{\n  {}\n}};\n",
        text.len(),
        bytes
            .chunks(32)
            .map(|row| row.join(","))
            .collect::<Vec<_>>()
            .join(",\n  ")
    );
    out += &format!(
        "int plaid_rsp_{name}(plaid_rsp *r, u32 pc) {{\n  {verify}\ndispatch:\n  switch (pc) {{\n"
    );
    for i in 0..words.len() as u32 {
        out += &format!(
            "  case 0x{:03x}: goto {};\n",
            imem + 4 * i,
            label(imem + 4 * i)
        );
    }
    out += "  default: return plaid_rsp_leave(r, pc);\n  }\n";
    let mut stubs = Vec::new();
    for (i, &w) in words.iter().enumerate() {
        let pc = imem + 4 * i as u32;
        out += &format!("{}:\n", label(pc));
        let mut stub = |why: String| {
            stubs.push(why);
            format!("  return plaid_rsp_fault(r, 0x{pc:03x}u, 6);\n")
        };
        if !is_control(w) {
            out += &match simple(w, pc, &verify) {
                Ok(c) => format!("  PLAID_RSP_LIVE(0x{pc:03x}u) {c}\n"),
                Err(why) => stub(why),
            };
            continue;
        }
        let slot = match words.get(i + 1) {
            // The delay slot lies past this text: leave, so the runtime runs a
            // text that holds both words (ADR-0246).
            None => {
                out += &format!(
                    "  return plaid_rsp_leave(r, 0x{pc:03x}u);
"
                );
                continue;
            }
            Some(&slot) if is_control(slot) => {
                out += &stub(format!("{pc:03x}: transfer in a delay slot"));
                continue;
            }
            Some(&slot) => match simple(slot, pc + 4, &verify) {
                Ok(c) => c,
                Err(why) => {
                    out += &stub(why);
                    continue;
                }
            },
        };
        out += &format!("  PLAID_RSP_LIVE2(0x{pc:03x}u)\n");
        let (rs, rt, rd) = ((w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31);
        let (s, t) = (reg(rs), reg(rt));
        let branch = (pc + 4).wrapping_add(((w as u16 as i16 as i32) << 2) as u32) & 0xfff;
        let link = (pc + 8) & 0xfff;
        let next = go((pc + 8) & 0xfff);
        let cond = |c: String, link_reg: bool| {
            let l = if link_reg {
                set(31, format!("0x{link:03x}u"))
            } else {
                String::new()
            };
            format!(
                "  {{ int c = {c}; {l} {slot} if (c) {} }} {next}\n",
                go(branch)
            )
        };
        out += &match (w >> 26, w & 0x3f, rt) {
            (0, 8 | 9, _) => {
                let l = if w & 0x3f == 9 {
                    set(rd, format!("0x{link:03x}u"))
                } else {
                    String::new()
                };
                format!(
                    "  {{ u32 t = {s}; {l} {slot} if (t & 3) return plaid_rsp_fault(r, 0x{pc:03x}u, 3); pc = t & 0xfff; goto dispatch; }}\n"
                )
            }
            (1, _, 0) => cond(format!("(s32){s} < 0"), false),
            (1, _, 1) => cond(format!("(s32){s} >= 0"), false),
            (1, _, 16) => cond(format!("(s32){s} < 0"), true),
            (1, _, 17) => cond(format!("(s32){s} >= 0"), true),
            (2, ..) => format!("  {{ {slot} {} }}\n", go((w << 2) & 0xfff)),
            (3, ..) => format!(
                "  {{ {} {slot} {} }}\n",
                set(31, format!("0x{link:03x}u")),
                go((w << 2) & 0xfff)
            ),
            (4, ..) => cond(format!("{s} == {t}"), false),
            (5, ..) => cond(format!("{s} != {t}"), false),
            (6, ..) => cond(format!("(s32){s} <= 0"), false),
            (7, ..) => cond(format!("(s32){s} > 0"), false),
            _ => unreachable!("is_control"),
        };
    }
    out += &format!(
        "  return plaid_rsp_leave(r, 0x{:03x}u);\n}}\nconst plaid_rsp_text plaid_rsp_text_{name} = {{0x{imem:03x}u, 0x{:x}u, plaid_rsp_bytes_{name}, plaid_rsp_{name}, \"{name}\"}};\n",
        end & 0xfff,
        text.len()
    );
    Ok(LoweredRsp {
        c: format!("#include \"rsp_state.h\"\n{PRELUDE}{VECTOR_UNIT}\n{out}"),
        stubs,
    })
}
