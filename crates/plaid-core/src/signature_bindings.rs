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
                .map(|(&h, &l)| reference(image, entry, h, l))
                .collect();
            let addresses = addresses?;
            addresses
                .iter()
                .all(|a| *a == addresses[0])
                .then(|| (name.clone(), addresses[0]))
        })
        .collect()
}

fn reference(image: &CodeImage, entry: u32, high: u32, low: u32) -> Option<GuestAddr> {
    // shortcut: only adjacent scalar references; extend when a verified consumer
    // needs indexed/nonadjacent materializations and their register dataflow.
    if high.checked_add(4) != Some(low) {
        return None;
    }
    let high = image.instruction_word(GuestAddr(entry.checked_add(high)?))?;
    let low = image.instruction_word(GuestAddr(entry.checked_add(low)?))?;
    let register = high >> 16 & 31;
    if high >> 26 != 15 || high >> 21 & 31 != 0 || register == 0 || low >> 21 & 31 != register {
        return None;
    }
    let address = match low >> 26 {
        9 | 13 if low >> 16 & 31 == 0 => return None,
        9 | 35 | 43 => (high << 16).wrapping_add(low as u16 as i16 as i32 as u32),
        13 => (high << 16) | (low & 0xffff),
        _ => return None,
    };
    Some(GuestAddr(address))
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
