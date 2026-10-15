//! RSP microcode lowering (ADR-0167).
//!
//! A microcode's text is small and fixed (IMEM is 4 KiB, and DMA into IMEM
//! faults), so every word of the text gets a label. Register jumps dispatch
//! over exactly those labels: the target set is closed by construction, and
//! anything else faults 3. Semantics follow pinned ares (`ares/n64/rsp`).

const PRELUDE: &str = include_str!("rsp_prelude.h");

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

/// One non-control instruction at `pc`, or an error naming what is unsupported.
fn simple(w: u32, pc: u32) -> Result<String, String> {
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
                "{{ if (plaid_rsp_mtc0(r, {rd}, {t}, 0x{pc:03x}u)) return 1; if (r->halted) {{ r->pc = 0x{:03x}u; return 0; }} }}",
                (pc + 4) & 0xfff
            ),
            _ => return unsupported(),
        },
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

/// Lowers microcode `text` placed at IMEM offset `imem` to
/// `int plaid_rsp_<name>(plaid_rsp *r, u32 pc)`, which runs from `pc` until
/// the microcode halts (returns 0) or a fault (returns 1).
pub fn lower_rsp(text: &[u8], imem: u32, name: &str) -> Result<String, String> {
    if !name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') || name.is_empty() {
        return Err(format!("bad microcode name {name:?}"));
    }
    if !imem.is_multiple_of(4)
        || !text.len().is_multiple_of(4)
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
    let label = |pc: u32| format!("L_{pc:03x}");
    // a direct transfer: a label inside the text, else the dispatch faults
    let go = |target: u32| {
        if (imem..end).contains(&target) {
            format!("goto {};", label(target))
        } else {
            format!("{{ pc = 0x{target:03x}u; goto dispatch; }}")
        }
    };
    let mut out =
        format!("int plaid_rsp_{name}(plaid_rsp *r, u32 pc) {{\ndispatch:\n  switch (pc) {{\n");
    for i in 0..words.len() as u32 {
        out += &format!(
            "  case 0x{:03x}: goto {};\n",
            imem + 4 * i,
            label(imem + 4 * i)
        );
    }
    out += "  default: return plaid_rsp_fault(r, pc, 3);\n  }\n";
    for (i, &w) in words.iter().enumerate() {
        let pc = imem + 4 * i as u32;
        out += &format!("{}:\n", label(pc));
        if !is_control(w) {
            out += &format!("  {}\n", simple(w, pc)?);
            continue;
        }
        let slot = *words
            .get(i + 1)
            .ok_or_else(|| format!("{pc:03x}: transfer without a delay slot in the text"))?;
        if is_control(slot) {
            return Err(format!("{pc:03x}: transfer in a delay slot"));
        }
        let slot = simple(slot, pc + 4)?;
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
        "  return plaid_rsp_fault(r, 0x{:03x}u, 3);\n}}\n",
        end & 0xfff
    );
    Ok(format!("{PRELUDE}\n{out}"))
}
