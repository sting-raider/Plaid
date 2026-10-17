//! Declared executable loads (ADR-0136).
//!
//! A declared load names bytes that a program places at a destination at run
//! time: a raw ROM slice or a Yaz0-compressed one, by DMA, CPU copy or
//! decompression alike. Discovery analyzes the composite image (the base
//! window with every load applied), so code inside a load is analyzed from
//! its loaded bytes. A declaration is a claim: the native artifact compares a
//! load's executable bytes in RAM with the declared bytes before its code
//! first runs, and aborts on a mismatch.
use crate::{
    GuestAddr,
    discovery::CodeImage,
    program::{CodeAddress, EvidenceRefs, GuestRange, RomOffset},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LoadEncoding {
    Raw,
    Yaz0,
    /// Two adjacent 1172 streams: text followed by data, bounded by the catalog.
    RarePair {
        end: RomOffset,
        text_size: u32,
    },
    /// Re-execute the bounded ROM-only boot transformation; no snapshot input.
    Boot,
    /// Pinned ares reset boot; the payload selects the first fetched target.
    /// `source` remains zero (the whole ROM), never a RAM snapshot path.
    AresBoot {
        entry: GuestAddr,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DeclaredLoad {
    /// Where the decoded bytes are placed; `size` is the decoded size.
    pub destination: GuestRange,
    pub source: RomOffset,
    pub encoding: LoadEncoding,
    pub evidence: EvidenceRefs,
    /// A relocatable overlay placed at its link address (ADR-0172): the game
    /// loads it elsewhere and relocates it, so its code runs only through a
    /// checked runtime binding.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub relocatable: bool,
    /// One of the files a slot holds in turn (ADR-0185): linked and run at
    /// this address, its text sits at `destination` instead, moved there by
    /// [`crate::overlays::slot_layout`], and runs only through a binding
    /// that finds it in the slot by content.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub linked: Option<GuestAddr>,
}

impl DeclaredLoad {
    /// The overlay layout of a relocatable load whose placed bytes are
    /// `bytes`: a slot alternate's synthesized one, else the Zelda64 trailer.
    pub fn layout(&self, bytes: &[u8]) -> Result<crate::overlays::Layout, String> {
        match (self.linked, self.encoding) {
            (Some(_), LoadEncoding::RarePair { text_size, .. }) => {
                crate::overlays::slot_layout_bounded(bytes, self.destination.start.0, text_size)
            }
            (Some(_), _) => Ok(crate::overlays::slot_layout(
                bytes,
                self.destination.start.0,
            )),
            (None, _) => crate::overlays::Layout::parse(bytes),
        }
    }
}

/// Where code at `target` sits when `target` is in a slot (ADR-0185): the
/// placed address of each alternate whose text covers it. Which one runs is
/// decided at run time by the bytes RAM holds.
pub fn slot_targets(loads: &[DeclaredLoad], target: u32) -> Vec<u32> {
    loads
        .iter()
        .filter_map(|l| {
            let off = target.wrapping_sub(l.linked?.0);
            let size = match l.encoding {
                LoadEncoding::RarePair { text_size, .. } => text_size,
                _ => l.destination.size,
            };
            (off < size).then(|| l.destination.start.0 + off)
        })
        .collect()
}

/// Slot views must be derived from the declared files, not supplied as extra
/// authority to discharge missing targets. Their mapping is part of the hash.
pub fn verify_slots(image: &CodeImage, spec: Option<&LoadImage>) -> bool {
    let declared: Vec<_> = spec
        .into_iter()
        .flat_map(|s| &s.loads)
        .filter(|l| l.linked.is_some())
        .collect();
    if declared.len() != image.slots.len() {
        return false;
    }
    if image.slots.is_empty() {
        return true;
    }
    if image.base.image != image.content_identity() {
        return false;
    }
    image
        .slots
        .iter()
        .enumerate()
        .all(|(i, (placed, linked, text))| {
            if image.slots[..i].iter().any(|(other, _, _)| other == placed) {
                return false;
            }
            declared.iter().any(|l| {
                if !l.relocatable
                    || l.destination != *placed
                    || l.linked != Some(GuestAddr(*linked))
                    || placed.size as usize / 4 > image.words.len()
                {
                    return false;
                }
                let bytes: Option<Vec<_>> = (0..placed.size / 4)
                    .map(|n| {
                        placed
                            .start
                            .0
                            .checked_add(4 * n)
                            .and_then(|pc| image.word(GuestAddr(pc)))
                    })
                    .collect();
                bytes.is_some_and(|words| {
                    let bytes: Vec<_> = words.into_iter().flat_map(u32::to_be_bytes).collect();
                    l.layout(&bytes).is_ok_and(|layout| layout.text == *text)
                })
            })
        })
}

/// How a composite image was built: the base window and the loads applied to
/// it, in destination order.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LoadImage {
    pub base_offset: RomOffset,
    pub base: GuestRange,
    pub loads: Vec<DeclaredLoad>,
}

/// Decode one Yaz0 stream (header `Yaz0`, big-endian decoded size, 8 reserved
/// bytes, then flag-byte groups of literals and back-references).
pub fn yaz0(data: &[u8]) -> Result<Vec<u8>, String> {
    yaz0_stream(data).map(|(out, _)| out)
}

/// The largest decoded size accepted, so a stray header cannot demand an
/// arbitrary allocation; it exceeds any N64 cartridge.
const YAZ0_MAX: usize = 64 << 20;

/// [`yaz0`] and the number of stream bytes it consumed.
pub fn yaz0_stream(data: &[u8]) -> Result<(Vec<u8>, usize), String> {
    if data.len() < 16 || &data[..4] != b"Yaz0" {
        return Err("not a Yaz0 stream".into());
    }
    let size = u32::from_be_bytes([data[4], data[5], data[6], data[7]]) as usize;
    if size > YAZ0_MAX {
        return Err("Yaz0 decoded size exceeds 64 MiB".into());
    }
    let mut out = Vec::with_capacity(size);
    let mut at = 16;
    let next = |at: &mut usize| -> Result<u8, String> {
        let b = *data.get(*at).ok_or("truncated Yaz0 stream")?;
        *at += 1;
        Ok(b)
    };
    while out.len() < size {
        let flags = next(&mut at)?;
        for bit in (0..8).rev() {
            if out.len() >= size {
                break;
            }
            if flags >> bit & 1 == 1 {
                out.push(next(&mut at)?);
                continue;
            }
            let (b1, b2) = (next(&mut at)?, next(&mut at)?);
            let distance = ((usize::from(b1) & 0xf) << 8 | usize::from(b2)) + 1;
            let count = match b1 >> 4 {
                0 => usize::from(next(&mut at)?) + 0x12,
                n => usize::from(n) + 2,
            };
            if distance > out.len() || out.len() + count > size {
                return Err("Yaz0 back-reference outside the stream".into());
            }
            for _ in 0..count {
                out.push(out[out.len() - distance]);
            }
        }
    }
    Ok((out, at))
}

fn decoded(bytes: &[u8], load: &DeclaredLoad) -> Result<Vec<u8>, String> {
    let start = usize::try_from(load.source.0).map_err(|_| "load source too large")?;
    let size = load.destination.size as usize;
    let data = match load.encoding {
        LoadEncoding::Raw => bytes
            .get(start..start.checked_add(size).ok_or("load source overflow")?)
            .ok_or("load source outside the ROM")?
            .to_vec(),
        LoadEncoding::Yaz0 => yaz0(bytes.get(start..).ok_or("load source outside the ROM")?)?,
        LoadEncoding::RarePair { end, text_size } => {
            if !load.relocatable || load.linked.is_none() {
                return Err("1172 paired files require a slot binding".into());
            }
            let (data, actual_text) = crate::paired_streams::decode(bytes, load.source.0, end.0)?;
            if actual_text != text_size {
                return Err("1172 text size differs from the stream boundary".into());
            }
            data
        }
        LoadEncoding::Boot => {
            if start != 0 || load.relocatable || load.linked.is_some() {
                return Err(
                    "boot-produced loads require the whole ROM and a fixed destination".into(),
                );
            }
            let rom = crate::rom::CanonicalRom::from_bytes(bytes)?;
            let capture = crate::boot_execution::execute(&rom).map_err(|stop| {
                format!("boot capture stopped at {:08x}: {}", stop.pc.0, stop.reason)
            })?;
            if capture.destination != load.destination {
                return Err("boot-produced load differs from replayed destination".into());
            }
            capture.bytes
        }
        LoadEncoding::AresBoot { entry } => {
            if start != 0 || load.relocatable || load.linked.is_some() {
                return Err("ares boot loads require the whole ROM and a fixed destination".into());
            }
            let rom = crate::rom::CanonicalRom::from_bytes(bytes)?;
            let capture = crate::ares_boot::execute(&rom, entry.0)?;
            let offset =
                load.destination
                    .start
                    .0
                    .checked_sub(capture.destination)
                    .ok_or("ares load starts before the replayed image")? as usize;
            capture
                .bytes
                .get(offset..offset.checked_add(size).ok_or("ares load range overflow")?)
                .ok_or("ares load ends beyond the replayed image")?
                .to_vec()
        }
    };
    if data.len() != size {
        return Err(format!(
            "load at {:08x} decodes to {:#x} bytes, not the declared {size:#x}",
            load.destination.start.0,
            data.len()
        ));
    }
    if let Some(linked) = load.linked {
        if !load.relocatable {
            return Err("a slot alternate runs only through a binding".into());
        }
        let layout = match load.encoding {
            LoadEncoding::RarePair { text_size, .. } => {
                crate::overlays::slot_layout_bounded(&data, linked.0, text_size)?
            }
            _ => crate::overlays::slot_layout(&data, linked.0),
        };
        return layout.apply(&data, linked.0, load.destination.start.0);
    }
    Ok(data)
}

/// Build the base image and the composite image of `spec` from ROM bytes.
/// Loads must be word-aligned and must not overlap each other. Gaps between
/// them and the base window become holes in the composite (ADR-0150).
pub fn compose(bytes: &[u8], spec: &LoadImage) -> Result<(CodeImage, CodeImage), String> {
    spec.base.validate(true)?;
    let begin = usize::try_from(spec.base_offset.0).map_err(|_| "base offset too large")?;
    let base_bytes = bytes
        .get(begin..begin + spec.base.size as usize)
        .ok_or("base window outside the ROM")?;
    let image = |start: GuestAddr, bytes: &[u8], rom_offset| CodeImage {
        base: CodeAddress {
            pc: start,
            image: sha256(bytes),
            generation: 0,
        },
        words: bytes
            .as_chunks::<4>()
            .0
            .iter()
            .map(|w| u32::from_be_bytes(*w))
            .collect(),
        rom_offset,
        physical_start: None,
        holes: Vec::new(),
        slots: Vec::new(),
    };
    let base = image(spec.base.start, base_bytes, Some(spec.base_offset));
    if spec.loads.is_empty() {
        return Err("a load image needs at least one declared load".into());
    }
    let mut previous_end = 0;
    for load in &spec.loads {
        load.destination.validate(true)?;
        if u64::from(load.destination.start.0) < previous_end {
            return Err("declared loads overlap or are out of destination order".into());
        }
        previous_end = load.destination.end();
    }
    // The composite spans the base and every load; bytes no load or base
    // window supplies are holes (ADR-0150), never code or table bytes.
    let mut covered: Vec<(u64, u64)> = spec
        .loads
        .iter()
        .map(|l| (u64::from(l.destination.start.0), l.destination.end()))
        .chain([(u64::from(spec.base.start.0), spec.base.end())])
        .collect();
    covered.sort_unstable();
    let (lo, hi) = (covered[0].0, covered.iter().map(|c| c.1).max().unwrap_or(0));
    let mut holes = Vec::new();
    let mut reached = lo;
    for (s, e) in &covered {
        if *s > reached {
            holes.push(GuestRange {
                start: GuestAddr(reached as u32),
                size: (s - reached) as u32,
            });
        }
        reached = reached.max(*e);
    }
    let mut composite = vec![0u8; (hi - lo) as usize];
    let at = |a: u64| (a - lo) as usize;
    composite[at(u64::from(spec.base.start.0))..at(spec.base.end())].copy_from_slice(base_bytes);
    let mut slots = Vec::new();
    for load in &spec.loads {
        let data = decoded(bytes, load)?;
        if let Some(linked) = load.linked {
            slots.push((load.destination.clone(), linked.0, load.layout(&data)?.text));
        }
        composite[at(u64::from(load.destination.start.0))..at(load.destination.end())]
            .copy_from_slice(&data);
    }
    let mut out = image(GuestAddr(lo as u32), &composite, None);
    out.slots = slots;
    out.holes = holes;
    if !out.holes.is_empty() || !out.slots.is_empty() {
        out.base.image = out.content_identity();
    }
    Ok((base, out))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn load(start: u32, source: u64, size: u32, encoding: LoadEncoding) -> DeclaredLoad {
        DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(start),
                size,
            },
            source: RomOffset(source),
            encoding,
            evidence: EvidenceRefs::new(),
            relocatable: false,
            linked: None,
        }
    }

    #[test]
    fn slot_views_are_bound_to_declarations_text_and_content_identity() {
        let mut rom = vec![0; 64];
        for (i, word) in [0x2402_0007u32, 0x03e0_0008, 0, 0x8000_4000]
            .into_iter()
            .enumerate()
        {
            rom[16 + 4 * i..20 + 4 * i].copy_from_slice(&word.to_be_bytes());
        }
        let mut alternate = load(0x8000_0080, 16, 16, LoadEncoding::Raw);
        alternate.relocatable = true;
        alternate.linked = Some(GuestAddr(0x8000_4000));
        let spec = LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(0x8000_0000),
                size: 16,
            },
            loads: vec![alternate],
        };
        let (_, image) = compose(&rom, &spec).unwrap();
        assert!(verify_slots(&image, Some(&spec)));
        assert!(!verify_slots(&image, None));
        let mut changed = image.clone();
        changed.slots[0].1 += 4;
        assert!(!verify_slots(&changed, Some(&spec)));
        changed.base.image = changed.content_identity();
        assert!(!verify_slots(&changed, Some(&spec)));
        let mut changed = image.clone();
        changed.slots[0].2 += 4;
        changed.base.image = changed.content_identity();
        assert!(!verify_slots(&changed, Some(&spec)));
        let mut changed = image.clone();
        changed.slots.push(changed.slots[0].clone());
        let mut duplicated = spec.clone();
        duplicated.loads.push(duplicated.loads[0].clone());
        changed.base.image = changed.content_identity();
        assert!(!verify_slots(&changed, Some(&duplicated)));
        let mut changed_spec = spec.clone();
        changed_spec.loads[0].relocatable = false;
        assert!(!verify_slots(&image, Some(&changed_spec)));
    }

    #[test]
    fn yaz0_decodes_literals_and_overlapping_back_references() {
        // "abc", an 8-byte copy at distance 3, a literal 'x', and an 18-byte
        // run copied at distance 1 (the count-byte form).
        let mut s = b"Yaz0".to_vec();
        s.extend(30u32.to_be_bytes());
        s.extend([0; 8]);
        s.extend([
            0b1110_1000,
            b'a',
            b'b',
            b'c',
            0x60,
            0x02,
            b'x',
            0x00,
            0x00,
            0x00,
        ]);
        let out = yaz0(&s).unwrap();
        assert_eq!(out, [&b"abcabcabcab"[..], &[b'x'; 19]].concat());
        assert!(yaz0(&s[..s.len() - 1]).is_err());
        let mut bad = s.clone();
        bad[21] = 0x10; // distance 17 reaches before the start of the output
        assert!(yaz0(&bad).is_err());
    }

    #[test]
    fn compose_patches_extends_leaves_holes_and_rejects_overlaps() {
        let rom: Vec<u8> = (0..64u8).collect();
        let spec = |loads| LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(0x8000_0000),
                size: 16,
            },
            loads,
        };
        let (base, composite) = compose(
            &rom,
            &spec(vec![load(0x8000_0008, 32, 16, LoadEncoding::Raw)]),
        )
        .unwrap();
        assert_eq!(base.words.len(), 4);
        assert_eq!(composite.base.pc, GuestAddr(0x8000_0000));
        assert_eq!(
            composite.words,
            [
                0x0001_0203,
                0x0405_0607,
                0x2021_2223,
                0x2425_2627,
                0x2829_2a2b,
                0x2c2d_2e2f
            ]
        );
        assert_ne!(base.base.image, composite.base.image);
        assert!(composite.holes.is_empty());
        // a disjoint load leaves a hole that supplies no words (ADR-0150)
        let (_, gapped) = compose(
            &rom,
            &spec(vec![load(0x8000_0020, 32, 8, LoadEncoding::Raw)]),
        )
        .unwrap();
        assert_eq!(
            gapped.holes,
            vec![GuestRange {
                start: GuestAddr(0x8000_0010),
                size: 16
            }]
        );
        assert_eq!(gapped.word(GuestAddr(0x8000_000c)), Some(0x0c0d_0e0f));
        assert_eq!(gapped.word(GuestAddr(0x8000_0010)), None);
        assert_eq!(gapped.word(GuestAddr(0x8000_001c)), None);
        assert_eq!(gapped.word(GuestAddr(0x8000_0020)), Some(0x2021_2223));

        assert!(
            compose(
                &rom,
                &spec(vec![
                    load(0x8000_0008, 32, 8, LoadEncoding::Raw),
                    load(0x8000_000c, 40, 8, LoadEncoding::Raw)
                ])
            )
            .is_err()
        );
        assert!(
            compose(
                &rom,
                &spec(vec![load(0x8000_0010, 60, 8, LoadEncoding::Raw)])
            )
            .is_err()
        );
        assert!(
            compose(
                &rom,
                &spec(vec![load(0x8000_0010, 0, 8, LoadEncoding::Yaz0)])
            )
            .is_err()
        );
        assert!(compose(&rom, &spec(vec![])).is_err());
    }
}
