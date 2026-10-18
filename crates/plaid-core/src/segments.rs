//! Named section descriptors: raw source, linked text/data/BSS extents.
use crate::{GuestAddr, program::RomOffset};
use std::collections::{BTreeMap, BTreeSet};

const STRIDE: usize = 48;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Segment {
    pub descriptor: RomOffset,
    pub source: u32,
    pub end: u32,
    pub linked: GuestAddr,
    pub text: u32,
    pub bss: u32,
}

/// Recheck all section relationships against the original ROM descriptor.
pub fn read(rom: &[u8], descriptor: RomOffset) -> Result<Segment, String> {
    let at = usize::try_from(descriptor.0).map_err(|_| "segment descriptor overflow")?;
    if !at.is_multiple_of(4) {
        return Err("unaligned segment descriptor".into());
    }
    let bytes = rom
        .get(
            at..at
                .checked_add(STRIDE)
                .ok_or("segment descriptor overflow")?,
        )
        .ok_or("segment descriptor outside ROM")?;
    let w: Vec<u32> = bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|b| u32::from_be_bytes(*b))
        .collect();
    let [
        start,
        end,
        linked,
        text_start,
        text_end,
        data_start,
        data_end,
        bss_start,
        bss_end,
    ] = w[..9].try_into().unwrap();
    if start < 0x1000
        || start >= end
        || end as usize > rom.len()
        || !start.is_multiple_of(16)
        || !end.is_multiple_of(16)
        || !(0x8000_0000..0x8080_0000).contains(&linked)
        || linked != text_start
        || text_start >= text_end
        || text_end != data_start
        || data_start > data_end
        || data_end != bss_start
        || bss_start > bss_end
        || bss_end > 0x8080_0000
        || end - start != data_end - linked
        || w[..9].iter().any(|v| !v.is_multiple_of(4))
        || w[9..]
            .iter()
            .any(|&v| v != 0 && (!(0x8000_0000..=0x8080_0000).contains(&v) || !v.is_multiple_of(4)))
    {
        return Err("invalid raw segment section bounds".into());
    }
    Ok(Segment {
        descriptor,
        source: start,
        end,
        linked: GuestAddr(linked),
        text: text_end - linked,
        bss: bss_end - bss_start,
    })
}

// A compiler call-site witness: a descriptor address in a0, completed in a
// JAL delay slot. A bounded linear callee scan must find every section field
// through that pointer. This is structural candidate evidence, not reachability.
fn loader_reads(words: &[u32], base: GuestAddr, entry: u32) -> bool {
    let Some(offset) = entry.checked_sub(base.0).filter(|v| v.is_multiple_of(4)) else {
        return false;
    };
    let mut pointers = [false; 32];
    pointers[4] = true;
    let mut fields = BTreeSet::new();
    let mut call_delay = false;
    for (n, &word) in words.iter().skip(offset as usize / 4).take(128).enumerate() {
        let pc = GuestAddr(entry.wrapping_add(n as u32 * 4));
        let instruction = crate::discovery::decode(word, pc);
        if !instruction.is_valid() {
            return false;
        }
        let (rs, rt) = (((word >> 21) & 31) as usize, ((word >> 16) & 31) as usize);
        if word >> 26 == 35 && pointers[rs] && word as u16 <= 32 {
            fields.insert(word as u16);
        }
        let copy = word >> 26 == 0
            && matches!(word & 63, 0x21 | 0x25 | 0x2d)
            && ((rs == 0 && pointers[rt]) || (rt == 0 && pointers[rs]));
        if let Some(rd) = instruction.destination_gpr().filter(|&r| r != 0) {
            pointers[rd as usize] = copy;
        }
        // Evaluate a call's delay slot before dropping caller-saved values.
        if call_delay {
            for r in (1..16).chain(24..28).chain([31]) {
                pointers[r] = false;
            }
        }
        call_delay = instruction.does_link();
        if word == 0x03e0_0008 {
            return (0..=32).step_by(4).all(|field| fields.contains(&field));
        }
    }
    false
}

fn named_loaders(image: &[u8], base: GuestAddr) -> BTreeMap<u32, BTreeSet<u32>> {
    let words: Vec<_> = image
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let mut named: BTreeMap<u32, BTreeSet<u32>> = BTreeMap::new();
    let mut loaders = BTreeMap::new();
    for (n, window) in words.windows(3).enumerate() {
        let [hi, call, lo] = [window[0], window[1], window[2]];
        if hi >> 16 != 0x3c04 || call >> 26 != 3 || lo >> 16 != 0x2484 && lo >> 16 != 0x3484 {
            continue;
        }
        let pc = base.0.wrapping_add(n as u32 * 4 + 4);
        let loader = (pc.wrapping_add(4) & 0xf000_0000) | ((call & 0x03ff_ffff) << 2);
        if !*loaders
            .entry(loader)
            .or_insert_with(|| loader_reads(&words, base, loader))
        {
            continue;
        }
        let address = if lo >> 26 == 9 {
            (hi << 16).wrapping_add(lo as i16 as u32)
        } else {
            (hi << 16) | (lo & 0xffff)
        };
        named.entry(address).or_default().insert(loader);
    }
    named
}

/// Adjacent descriptors sharing a linked slot and passed independently to the
/// same section-reading loader are candidates. Their native bindings still
/// require exact text bytes in RAM; inference does not prove a load executes.
pub fn infer(rom: &[u8], image: &[u8], base: GuestAddr, source: RomOffset) -> Vec<Segment> {
    let Ok(start) = usize::try_from(source.0) else {
        return Vec::new();
    };
    if rom.get(start..start.saturating_add(image.len())) != Some(image) {
        return Vec::new();
    }
    let named = named_loaders(image, base);
    let records: BTreeMap<usize, Segment> = named
        .keys()
        .filter_map(|&address| {
            let offset = address.checked_sub(base.0)? as usize;
            if offset.checked_add(STRIDE)? > image.len() {
                return None;
            }
            let descriptor = RomOffset(source.0.checked_add(offset as u64)?);
            Some((offset, read(rom, descriptor).ok()?))
        })
        .collect();
    records
        .iter()
        .filter(|&(offset, record)| {
            [offset.checked_sub(STRIDE), offset.checked_add(STRIDE)]
                .into_iter()
                .flatten()
                .any(|other| {
                    records.get(&other).is_some_and(|neighbor| {
                        neighbor.linked == record.linked
                            && !named[&(base.0 + *offset as u32)]
                                .is_disjoint(&named[&(base.0 + other as u32)])
                            && if other < *offset {
                                neighbor.end == record.source
                            } else {
                                record.end == neighbor.source
                            }
                    })
                })
        })
        .map(|(_, record)| record.clone())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    fn put(rom: &mut [u8], p: usize, word: u32) {
        rom[p..p + 4].copy_from_slice(&word.to_be_bytes());
    }
    fn fixture() -> Vec<u8> {
        let mut rom = vec![0; 0x2200];
        // Two different code files, two explicitly referenced descriptors.
        for (p, target) in [(0x1000, 0x8000_0480u32), (0x1010, 0x8000_04b0u32)] {
            put(&mut rom, p, 0x3c04_0000 | target >> 16);
            put(&mut rom, p + 4, 0x0c00_0110); // JAL loader at 0x80000440
            put(&mut rom, p + 8, 0x3484_0000 | target & 0xffff);
        }
        put(&mut rom, 0x1040, 0x0080_802d); // preserve descriptor in s0
        for n in 0..9 {
            put(&mut rom, 0x1044 + n * 4, 0x8e02_0000 | (n as u32 * 4));
        }
        put(&mut rom, 0x1068, 0x03e0_0008);
        for (p, source) in [(0x1080, 0x2000u32), (0x10b0, 0x2100u32)] {
            let fields = [
                source,
                source + 0x100,
                0x80100000,
                0x80100000,
                0x80100080,
                0x80100080,
                0x80100100,
                0x80100100,
                0x80100120,
                0,
                0,
                0,
            ];
            for (n, w) in fields.into_iter().enumerate() {
                put(&mut rom, p + n * 4, w);
            }
        }
        rom
    }
    #[test]
    fn named_adjacent_section_descriptors_supply_exact_bounds() {
        let rom = fixture();
        let got = infer(
            &rom,
            &rom[0x1000..0x1100],
            GuestAddr(0x80000400),
            RomOffset(0x1000),
        );
        assert_eq!(got.len(), 2);
        assert_eq!(got[0].source, 0x2000);
        assert_eq!(got[1].source, 0x2100);
        assert_eq!(got[0].text, 0x80);
        assert_eq!(got[0].bss, 0x20);
    }
    #[test]
    fn unnamed_isolated_malformed_or_wrong_source_tables_add_no_loads() {
        let original = fixture();
        for field in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] {
            let mut rom = original.clone();
            put(&mut rom, 0x10b0 + 4 * field, 0xffff_ffff);
            assert!(
                infer(
                    &rom,
                    &rom[0x1000..0x1100],
                    GuestAddr(0x80000400),
                    RomOffset(0x1000)
                )
                .is_empty(),
                "field {field}"
            );
        }
        let mut rom = original.clone();
        rom[0x1010..0x1018].fill(0);
        assert!(
            infer(
                &rom,
                &rom[0x1000..0x1100],
                GuestAddr(0x80000400),
                RomOffset(0x1000)
            )
            .is_empty()
        );
        assert!(
            infer(
                &original,
                &original[0x1000..0x1100],
                GuestAddr(0x80000400),
                RomOffset(0x1004)
            )
            .is_empty()
        );
    }

    #[test]
    fn literal_names_unrelated_loads_or_clobbered_pointer_add_no_candidates() {
        for (at, word) in [
            (0x1004, 0),
            (0x1040, 0x00a0_802d),
            (0x1050, 0x2410_0000),
            (0x1044, 0),
        ] {
            let mut rom = fixture();
            put(&mut rom, at, word);
            assert!(
                infer(
                    &rom,
                    &rom[0x1000..0x1100],
                    GuestAddr(0x80000400),
                    RomOffset(0x1000)
                )
                .is_empty(),
                "mutation at {at:x}"
            );
        }
    }
}
