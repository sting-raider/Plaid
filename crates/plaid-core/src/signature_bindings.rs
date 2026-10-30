//! Conservative scalar references; unsupported materializations provide no binding.
use super::{CodeImage, GuestAddr, Signature};
use std::collections::BTreeMap;

pub(super) fn collect(
    image: &CodeImage,
    entry: u32,
    signatures: &[&Signature],
) -> BTreeMap<String, GuestAddr> {
    let Some((first, rest)) = signatures.split_first() else {
        return BTreeMap::new();
    };
    let mut out = variant(image, entry, first);
    for signature in rest {
        let other = variant(image, entry, signature);
        out.retain(|name, address| other.get(name) == Some(address));
    }
    out
}

fn variant(image: &CodeImage, entry: u32, signature: &Signature) -> BTreeMap<String, GuestAddr> {
    signature
        .data
        .iter()
        .filter_map(|(name, (high, low))| {
            if high.is_empty() || high.len() != low.len() {
                return None;
            }
            let (mut high, mut low) = (high.clone(), low.clone());
            high.sort_unstable();
            low.sort_unstable();
            if high.windows(2).any(|w| w[0] == w[1]) || low.windows(2).any(|w| w[0] == w[1]) {
                return None;
            }
            let addresses: Option<Vec<_>> = high
                .iter()
                .zip(&low)
                .map(|(&h, &l)| reference(image, entry, signature.size, h, l))
                .collect();
            let addresses = addresses?;
            addresses
                .iter()
                .all(|a| *a == addresses[0])
                .then(|| (name.clone(), addresses[0]))
        })
        .collect()
}

fn reference(image: &CodeImage, entry: u32, size: u32, high: u32, low: u32) -> Option<GuestAddr> {
    // shortcut: only straight-line scalar references; extend when a verified
    // consumer needs indexed materializations.
    if low <= high || low - high > 32 || low >= size || (high | low) & 3 != 0 {
        return None;
    }
    let word = |offset: u32| image.instruction_word(GuestAddr(entry.checked_add(offset)?));
    let split = low != high + 4;
    let (start, end) = (entry.wrapping_add(high), entry.wrapping_add(low));
    let (high_word, low_word) = (word(high)?, word(low)?);
    let register = high_word >> 16 & 31;
    if high_word >> 26 != 15
        || high_word >> 21 & 31 != 0
        || register == 0
        || low_word >> 21 & 31 != register
    {
        return None;
    }
    // JAL writes only ra before its delay slot. A scalar argument completed
    // there reaches the callee before it can clobber caller-saved registers.
    // This does not permit a pair spanning the call's return or a JALR target.
    let call_delay = low >= 8
        && word(low - 4)? >> 26 == 3
        && register != 31
        && matches!(low_word >> 26, 9 | 13)
        && matches!(low_word >> 16 & 31, 4..=7);
    // A pair split by other instructions (osContInit's __osEepromTimerQ) holds
    // only when its LUI is not in a delay slot, no intervening instruction
    // clobbers the value or diverts control before low, and no transfer enters it.
    if split {
        if high >= 4 && transfer(word(high - 4)?, start.wrapping_sub(4)).is_some() {
            return None;
        }
        if !(high + 4..low).step_by(4).all(|o| {
            word(o)
                .is_some_and(|w| keeps(w, register) || (call_delay && o + 4 == low && w >> 26 == 3))
        }) {
            return None;
        }
        for o in (0..size).step_by(4) {
            let w = word(o)?;
            match transfer(w, entry.wrapping_add(o)) {
                Some(Some(t)) if start < t && t <= end => return None,
                Some(None) if call_delay && w != 0x03e0_0008 => return None,
                Some(None) if w & 63 == 8 && w >> 21 & 31 != 31 => return None,
                _ => {}
            }
        }
    }
    let (high, low) = (high_word, low_word);
    let address = match low >> 26 {
        9 | 13 if low >> 16 & 31 == 0 => return None,
        9 | 35 | 43 => (high << 16).wrapping_add(low as u16 as i16 as i32 as u32),
        13 => (high << 16) | (low & 0xffff),
        _ => return None,
    };
    Some(GuestAddr(address))
}

/// Neither writes GPR `register` nor transfers control.
fn keeps(word: u32, register: u32) -> bool {
    match word >> 26 {
        0 => {
            matches!(
                word & 63,
                0 | 2..=4 | 6 | 7 | 16 | 18 | 20 | 22 | 23 | 32..=39 | 42..=47 | 56 | 58..=60 | 62 | 63
            ) && word >> 11 & 31 != register
        }
        8..=15 | 32..=39 | 55 => word >> 16 & 31 != register, // ALU immediates, LUI, loads
        40..=46 | 49 | 53 | 57 | 61 | 63 => true,             // stores, FPU loads and stores
        _ => false,
    }
}

/// The control transfer at `pc`, with `None` for a register target.
fn transfer(word: u32, pc: u32) -> Option<Option<u32>> {
    let branch = pc
        .wrapping_add(4)
        .wrapping_add(((word & 0xffff) as i16 as i32 as u32) << 2);
    match word >> 26 {
        0 if matches!(word & 63, 8 | 9) => Some(None),
        1 | 4..=7 | 20..=23 => Some(Some(branch)),
        16..=18 if word >> 21 & 31 == 8 => Some(Some(branch)),
        2 | 3 => Some(Some(
            (pc.wrapping_add(4) & 0xf000_0000) | (word & 0x03ff_ffff) << 2,
        )),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(words: &[u32], high: Vec<u32>, low: Vec<u32>) -> (CodeImage, Signature) {
        let bytes: Vec<_> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
        let signature = Signature {
            name: "fixture".into(),
            size: bytes.len() as u32,
            crc_a: 0,
            crc_b: 0,
            relocs: BTreeMap::new(),
            calls: BTreeMap::new(),
            data: [("global".into(), (high, low))].into(),
        };
        let image = CodeImage {
            base: crate::program::CodeAddress {
                pc: GuestAddr(0x80000400),
                image: "fixture".into(),
                generation: 0,
            },
            words: words.to_vec(),
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        (image, signature)
    }

    #[test]
    fn signed_low_and_unsigned_ori_have_distinct_addresses() {
        for (low, address) in [
            (0x25088000, 0x80008000),
            (0x35088000, 0x80018000),
            (0x8d028000, 0x80008000),
            (0xad048000, 0x80008000),
        ] {
            let (image, signature) = fixture(&[0x3c088001, low], vec![0], vec![4]);
            assert_eq!(
                collect(&image, 0x80000400, &[&signature]),
                [("global".into(), GuestAddr(address))].into()
            );
        }
    }

    #[test]
    fn split_pairs_need_straight_line_dataflow() {
        // osContInit's queue and message share one LUI value (lui a0; lui a1;
        // addiu a1; addiu a0) and the queue's pair is split.
        let words = [
            0x3c048028, 0x3c058028, 0x24a547d0, 0x248447b8, 0x03e00008, 0,
        ];
        let (image, signature) = fixture(&words, vec![0], vec![12]);
        assert_eq!(
            collect(&image, 0x80000400, &[&signature])["global"],
            GuestAddr(0x802847b8)
        );
        for (index, word) in [
            (1, 0x3c048029), // the register is rewritten between the pair
            (1, 0x10000001), // a branch between the pair
            (4, 0x1000fffe), // a later branch enters the pair at its low half
        ] {
            let mut changed = words;
            changed[index] = word;
            let (image, signature) = fixture(&changed, vec![0], vec![12]);
            assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        }
        // the LUI in a call's delay slot: the call's return is not straight-line
        let words = [
            0x0c000000, 0x3c048028, 0x3c058028, 0x24a547d0, 0x248447b8, 0,
        ];
        let (image, signature) = fixture(&words, vec![4], vec![16]);
        assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
    }

    #[test]
    fn every_use_and_variant_must_agree() {
        let (mut image, signature) = fixture(
            &[0x3c088001, 0x25088000, 0x3c098001, 0x25298000],
            vec![8, 0],
            vec![12, 4],
        );
        assert_eq!(
            collect(&image, 0x80000400, &[&signature])["global"],
            GuestAddr(0x80008000)
        );
        image.words[3] += 4;
        assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        image.words[3] -= 4;
        let mut other = signature.clone();
        other.data.clear();
        assert!(collect(&image, 0x80000400, &[&signature, &other]).is_empty());

        let (image, mut first) = fixture(
            &[0x3c088001, 0x25088000, 0x3c098001, 0x25299000],
            vec![0],
            vec![4],
        );
        let mut second = first.clone();
        second.data.insert("global".into(), (vec![8], vec![12]));
        assert!(!collect(&image, 0x80000400, &[&first]).is_empty());
        assert!(!collect(&image, 0x80000400, &[&second]).is_empty());
        assert!(collect(&image, 0x80000400, &[&first, &second]).is_empty());
        first.data = second.data.clone();
        assert_eq!(
            collect(&image, 0x80000400, &[&first, &second])["global"],
            GuestAddr(0x80009000)
        );
    }

    #[test]
    fn jal_delay_arguments_are_complete_before_the_callee_runs() {
        for argument in 4..=7 {
            for base in [argument, 8] {
                for opcode in [9, 13] {
                    for low in [0, 0x7fff, 0x8000, 0xffff] {
                        let words = [
                            0x3c00_8001 | base << 16,
                            0x0c10_0000,
                            opcode << 26 | base << 21 | argument << 16 | low,
                            0x03e0_0008,
                            0,
                        ];
                        let (image, signature) = fixture(&words, vec![0], vec![8]);
                        let address = if opcode == 9 {
                            0x8001_0000u32.wrapping_add(low as u16 as i16 as i32 as u32)
                        } else {
                            0x8001_0000 | low
                        };
                        assert_eq!(
                            collect(&image, 0x80000400, &[&signature])["global"],
                            GuestAddr(address)
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn delay_argument_proofs_refuse_clobbers_other_transfers_and_entries() {
        let original = [0x3c08_8001, 0x0c10_0000, 0x2504_8000, 0x03e0_0008, 0];
        for (index, replacement) in [
            (0, 0x3c1f_8001), // ra is overwritten by JAL
            (1, 0x0100_f809), // JALR, even with its normal link register
            (1, 0x1000_0001), // branch delay slot
            (1, 0x0c00_0102), // call enters the low instruction
            (2, 0x27e4_8000), // a different source register
            (2, 0x2509_8000), // not an argument register
            (3, 0x0120_f809), // another indirect transfer can enter the pair
            (4, 0x1000_fffd), // a later branch enters the low instruction
        ] {
            let mut words = original;
            words[index] = replacement;
            let (image, signature) = fixture(&words, vec![0], vec![8]);
            assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        }
        // LUI in a call's slot, and low after the return: neither is a
        // caller-owned value reaching the next callee argument boundary.
        for (words, high, low) in [
            (
                vec![0x3c1f_8001, 0x0c10_0000, 0x27e4_8000, 0x03e0_0008, 0],
                0,
                8,
            ),
            (
                vec![0x0c10_0000, 0x3c08_8001, 0x0c10_0000, 0x2504_8000, 0],
                4,
                12,
            ),
            (vec![0x3c08_8001, 0x0c10_0000, 0, 0x2504_8000, 0], 0, 12),
            (
                vec![0x3c08_8001, 0x2508_0001, 0x0c10_0000, 0x2504_8000, 0],
                0,
                12,
            ),
        ] {
            let (image, signature) = fixture(&words, vec![high], vec![low]);
            assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        }
        let (image, mut signature) = fixture(&original, vec![0], vec![8]);
        signature.size = 8;
        assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
    }

    #[test]
    fn clobbered_unpaired_zero_register_and_data_references_are_omitted() {
        for words in [
            [0x3c088001, 0x25298000],
            [0x3c008001, 0x24098000],
            [0x3c088001, 0x25008000],
            [0x3c088001, 0x35008000],
        ] {
            let (image, signature) = fixture(&words, vec![0], vec![4]);
            assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        }
        let (image, signature) = fixture(&[0x3c088001, 0x25080001, 0x25088000], vec![0], vec![8]);
        assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        let (mut image, signature) = fixture(&[0x3c088001, 0x25088000], vec![0], vec![4]);
        image.slots.push((
            crate::program::GuestRange {
                start: GuestAddr(0x80000400),
                size: 8,
            },
            0x80001000,
            4,
        ));
        assert!(collect(&image, 0x80000400, &[&signature]).is_empty());
        let mut unpaired = signature.clone();
        image.slots.clear();
        unpaired.data.get_mut("global").unwrap().1.clear();
        assert!(collect(&image, 0x80000400, &[&unpaired]).is_empty());
        let mut duplicate = signature.clone();
        duplicate.data.get_mut("global").unwrap().0.push(0);
        duplicate.data.get_mut("global").unwrap().1.push(4);
        assert!(collect(&image, 0x80000400, &[&duplicate]).is_empty());
    }
}
