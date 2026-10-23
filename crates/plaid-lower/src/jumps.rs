//! Exact structural leaf recognizer; no symbol names or game addresses.
use plaid_core::{GuestAddr, discovery::CodeImage};
use std::collections::BTreeSet;

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Jump {
    pub restore: bool,
    pub nonzero: bool,
    /// GPR sp, ra, s0-s7, fp followed by single-word FPR f20-f31.
    pub offsets: [u16; 23],
    pub words: u32,
}

pub(crate) fn recognize(image: &CodeImage, entry: u32) -> Option<Jump> {
    let word = |i: u32| image.word(GuestAddr(entry.checked_add(i * 4)?));
    let restore = match word(0)? >> 26 {
        43 => false,
        35 => true,
        _ => return None,
    };
    let mut offsets = [0; 23];
    let mut seen = BTreeSet::new();
    for i in 0..23 {
        let w = word(i)?;
        let (op, base, reg, offset) = (w >> 26, w >> 21 & 31, w >> 16 & 31, w as u16);
        let k = if op == if restore { 35 } else { 43 } {
            match reg {
                29 => 0,
                31 => 1,
                16..=23 => reg as usize - 14,
                30 => 10,
                _ => return None,
            }
        } else if op == if restore { 49 } else { 57 } && (20..=31).contains(&reg) {
            reg as usize - 9
        } else {
            return None;
        };
        // Distinct aligned nonnegative words through the unchanged a0 only.
        if base != 4 || k != i as usize || offset >= 0x8000 || offset % 4 != 0 || !seen.insert(k) {
            return None;
        }
        offsets[k] = offset;
    }
    if offsets.iter().collect::<BTreeSet<_>>().len() != 23 {
        return None;
    }
    let result = if restore { 0x00a0_1025 } else { 0x0000_1025 };
    let (nonzero, words) = if word(23)? == 0x03e0_0008 && word(24)? == result {
        (false, 25)
    } else if word(23)? == result && word(24)? == 0x03e0_0008 && word(25)? == 0 {
        (false, 26)
    } else if restore
        && word(23)? == result
        && word(24)? == 0x1440_0002
        && word(25)? == 0
        && word(26)? == 0x2402_0001
        && word(27)? == 0x03e0_0008
        && word(28)? == 0
    {
        (true, 29)
    } else {
        return None;
    };
    Some(Jump {
        restore,
        nonzero,
        offsets,
        words,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn image(restore: bool) -> CodeImage {
        let regs = [29, 31, 16, 17, 18, 19, 20, 21, 22, 23, 30];
        let mut words: Vec<u32> = regs
            .iter()
            .enumerate()
            .map(|(i, r)| {
                (if restore { 35 } else { 43 }) << 26 | 4 << 21 | r << 16 | (i as u32 * 4)
            })
            .collect();
        words
            .extend((20..32).map(|r| {
                (if restore { 49 } else { 57 }) << 26 | 4 << 21 | r << 16 | ((r - 9) * 4)
            }));
        words.extend([0x03e00008, if restore { 0x00a01025 } else { 0x00001025 }]);
        CodeImage {
            base: plaid_core::program::CodeAddress {
                pc: GuestAddr(0x80000000),
                image: "jumps".into(),
                generation: 0,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: vec![],
            slots: vec![],
        }
    }

    #[test]
    fn complete_save_restore_only() {
        for restore in [false, true] {
            let mut variants = vec![image(restore)];
            let mut preceding = image(restore);
            preceding.words.truncate(23);
            preceding
                .words
                .extend([if restore { 0x00a01025 } else { 0x00001025 }, 0x03e00008, 0]);
            variants.push(preceding.clone());
            if restore {
                preceding.words.truncate(24);
                preceding
                    .words
                    .extend([0x14400002, 0, 0x24020001, 0x03e00008, 0]);
                variants.push(preceding);
            }
            for image in variants {
                assert_eq!(recognize(&image, 0x80000000).unwrap().restore, restore);
                for i in 0..image.words.len() {
                    let mut bad = image.clone();
                    bad.words[i] ^= 1;
                    assert!(recognize(&bad, 0x80000000).is_none(), "word {i}");
                }
                for mutation in 0..3 {
                    let mut bad = image.clone();
                    match mutation {
                        0 => bad.words[0] ^= 1 << 21, // wrong base
                        1 => bad.words.swap(0, 1),    // wrong transfer order
                        _ => bad.words[1] &= !0xffff, // overlapping offsets
                    }
                    assert!(recognize(&bad, 0x80000000).is_none());
                }
            }
        }
    }
}
