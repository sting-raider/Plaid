//! Measured lowering coverage of the VR4300 instruction set, for the progress
//! history. Every encoding form the pinned decoder accepts is tried once in a
//! tiny program that must go through discovery, the guarded-scope solver and
//! lowering; a form counts as lowered only if the whole program lowers.
use crate::lower_c;
use plaid_core::{
    GuestAddr,
    discovery::{CodeImage, decode},
    pipeline::discover_image,
    program::{CodeAddress, RomIdentity},
};
use std::collections::BTreeMap;

const BASE: u32 = 0x8000_0000;
const EXIT: u32 = 0x8000_0020;

/// Decoder aliases of real instructions (the real forms are counted).
const PSEUDO: [&str; 9] = [
    "b", "bal", "beqz", "bnez", "move", "neg", "negu", "nop", "not",
];
/// Forms the pinned decoder knows that the VR4300 lacks: absent from the
/// pinned ares decoder (`ares/n64/cpu/decoder.cpp` at 9408cb43).
const NOT_VR4300: [&str; 12] = [
    "movn", "movz", "pref", "rfe", "ldc2", "lwc2", "sdc2", "swc2", "bc0f", "bc0fl", "bc0t", "bc0tl",
];

/// Sample words for every primary opcode, SPECIAL/REGIMM function, COP0/COP1
/// sub-operation and COP1 format function. Operand fields are canonical
/// (rs = t0 holding EXIT, rt = t1, rd = t2, sa = 1) or zero in every
/// combination, because many forms are valid only with some fields zero.
/// Branch offsets and jump targets reach EXIT.
fn samples() -> Vec<u32> {
    // (shift, canonical value) of the operand fields that may be zeroed.
    let variants = |base: u32, fields: &[(u32, u32)]| -> Vec<u32> {
        (0..1u32 << fields.len())
            .map(|mask| {
                fields
                    .iter()
                    .enumerate()
                    .filter(|(i, _)| mask >> i & 1 == 1)
                    .fold(base, |w, (_, (shift, value))| w | value << shift)
            })
            .collect()
    };
    let gpr = [(21, 8), (16, 9), (11, 10), (6, 1)];
    let mut out = Vec::new();
    for op in 0..64u32 {
        match op {
            0 => (0..64).for_each(|f| out.extend(variants(f, &gpr))),
            1 => (0..32).for_each(|r| out.extend(variants(1 << 26 | r << 16 | 5, &gpr[..1]))),
            2 | 3 => out.push(op << 26 | (EXIT >> 2) & 0x03ff_ffff),
            16 | 17 => {
                for sub in 0..32u32 {
                    let base = op << 26 | sub << 21;
                    if sub == 8 {
                        out.extend((0..4).map(|c| base | c << 16 | 5));
                    } else if sub >= 16 {
                        let fpr = [(16, 9), (11, 10), (6, 11)];
                        (0..64).for_each(|f| out.extend(variants(base | f, &fpr)));
                    } else {
                        out.extend(variants(base, &gpr[1..3]));
                    }
                }
            }
            // branch at 0x08 + 4 + 5 * 4 = EXIT; also an ALU/memory immediate
            _ => out.extend(variants(op << 26 | 5, &gpr[..2])),
        }
    }
    out
}

fn lowers(word: u32) -> bool {
    // lui t0,0x8000; ori t0,t0,0x20; <word>; nop; j EXIT; nop; nop; nop; EXIT: b .; nop
    let words = vec![
        0x3c08_8000,
        0x3508_0020,
        word,
        0,
        0x0800_0008,
        0,
        0,
        0,
        0x1000_ffff,
        0,
    ];
    let image = CodeImage {
        base: CodeAddress {
            pc: GuestAddr(BASE),
            image: "isa-coverage".into(),
            generation: 0,
        },
        words,
        rom_offset: None,
        physical_start: None,
        holes: Vec::new(),
    };
    let rom = RomIdentity {
        sha256: "c".repeat(64),
        size: 64,
    };
    discover_image(rom, &image, &[GuestAddr(BASE)], 100)
        .and_then(|d| lower_c(&d.map, &[image], GuestAddr(BASE), &[GuestAddr(EXIT)]))
        .is_ok()
}

/// Decoder mnemonic -> whether some sampled form of it lowers.
pub fn isa_coverage() -> BTreeMap<String, bool> {
    let mut out = BTreeMap::new();
    for word in samples() {
        let i = decode(word, GuestAddr(BASE + 8));
        let name = i.opcode_name();
        if !i.is_valid() || PSEUDO.contains(&name) || NOT_VR4300.contains(&name) {
            continue;
        }
        let lowered = lowers(word);
        *out.entry(name.to_string()).or_insert(false) |= lowered;
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn coverage_counts_real_vr4300_forms_and_lowers_the_integer_core() {
        let c = super::isa_coverage();
        assert!(c["addu"] && c["jr"] && c["ld"] && c["mtc1"]);
        assert!(c["lwl"] && c["sdr"] && c["lwu"]);
        assert!(c["c.eq.s"] && c["c.ngt.d"] && c["bc1tl"]);
        assert!(c["add.s"] && c["cvt.s.w"] && c["trunc.w.d"] && c["ctc1"]);
        assert!(c["round.w.s"] && c["floor.l.d"] && c["cvt.l.s"]);
        assert!(!c["eret"] && !c["syscall"]);
        assert!(!c.contains_key("nop") && !c.contains_key("movn"));
    }
}
