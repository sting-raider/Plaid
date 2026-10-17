//! Constant-initialized catalogs of two adjacent 1172/raw-DEFLATE streams.
//! Recognition uses ROM bytes and matching segment lengths, never a title ID.
use crate::rom::sha256;
use flate2::{Decompress, FlushDecompress, Status};
use std::collections::{BTreeMap, BTreeSet};

const LIMIT: usize = 8 << 20;

/// Decode one bounded stream, requiring the DEFLATE end marker and exact size.
pub fn stream(bytes: &[u8]) -> Result<(Vec<u8>, usize), String> {
    if bytes.get(..2) != Some(&[0x11, 0x72]) || bytes.len() < 6 {
        return Err("not a 1172 stream".into());
    }
    let size = u32::from_be_bytes(bytes[2..6].try_into().unwrap()) as usize;
    if size == 0 || size > LIMIT {
        return Err("1172 size outside image bound".into());
    }
    let mut decoder = Decompress::new(false);
    let mut out = vec![0; size + 1];
    let status = decoder
        .decompress(
            &bytes[6..bytes.len().min(6 + LIMIT)],
            &mut out,
            FlushDecompress::Finish,
        )
        .map_err(|e| format!("invalid 1172 DEFLATE: {e}"))?;
    if status != Status::StreamEnd || decoder.total_out() != size as u64 {
        return Err("truncated 1172 stream or decoded size mismatch".into());
    }
    out.truncate(size);
    Ok((out, 6 + decoder.total_in() as usize))
}

/// The first stream is text; the second is data. Padding is under 16 bytes.
pub fn decode(rom: &[u8], start: u64, end: u64) -> Result<(Vec<u8>, u32), String> {
    let bytes = usize::try_from(start)
        .ok()
        .zip(usize::try_from(end).ok())
        .and_then(|(a, b)| rom.get(a..b))
        .ok_or("1172 pair outside ROM")?;
    let (mut text, used) = stream(bytes)?;
    let text_size = text.len();
    let (data, next) = stream(&bytes[used..])?;
    if bytes.len() - used - next >= 16
        || text_size % 16 != 0
        || data.len() % 16 != 0
        || text_size + data.len() > LIMIT
    {
        return Err("1172 pair boundary, alignment or size mismatch".into());
    }
    text.extend(data);
    Ok((text, text_size as u32))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SlotFile {
    pub source: u32,
    pub end: u32,
    pub destination: u32,
    pub text: u32,
    pub data: u32,
    pub bss: u32,
    pub index: usize,
    pub source_table: u32,
    pub metadata_source: u32,
    pub metadata_offset: usize,
    pub sha256: String,
}

/// Recover literal stores within straight-line LUI/ADDIU/ORI/SW blocks.
/// Unknown instructions end the block; no inferred memory values or CFG joins.
fn constants(boot: &[u8]) -> (BTreeSet<u32>, Vec<BTreeMap<u32, u32>>) {
    let mut regs = [None; 32];
    regs[0] = Some(0);
    let mut all = BTreeSet::new();
    let mut stores = BTreeMap::new();
    let mut blocks = Vec::new();
    let mut delay = false;
    for chunk in boot.as_chunks::<4>().0 {
        let w = u32::from_be_bytes(*chunk);
        let (op, rs, rt) = (w >> 26, (w >> 21 & 31) as usize, (w >> 16 & 31) as usize);
        let signed = w as u16 as i16 as i32 as u32;
        let was_delay = delay;
        delay = false;
        let mut finish = false;
        match op {
            0 if w == 0 => {}
            0 if w & 63 == 8 => delay = true,
            15 if rs == 0 => regs[rt] = Some(w << 16),
            9 | 13 if regs[rs].is_some() => {
                regs[rt] = regs[rs].map(|base| {
                    if op == 9 {
                        base.wrapping_add(signed)
                    } else {
                        base | (w & 0xffff)
                    }
                });
            }
            43 if regs[rs].is_some() && regs[rt].is_some() => {
                let address = regs[rs].unwrap().wrapping_add(signed);
                let value = regs[rt].unwrap();
                if stores.get(&address).is_some_and(|old| *old != value) {
                    blocks.push(std::mem::take(&mut stores));
                    stores.insert(address, value);
                    finish = true;
                } else {
                    stores.insert(address, value);
                }
            }
            _ => finish = true,
        }
        regs[0] = Some(0);
        all.extend(regs.iter().flatten());
        if finish || was_delay {
            if !stores.is_empty() {
                blocks.push(std::mem::take(&mut stores));
            }
            regs = [None; 32];
            regs[0] = Some(0);
        }
    }
    if !stores.is_empty() {
        blocks.push(stores);
    }
    (all, blocks)
}

#[derive(Clone)]
struct Pair {
    start: u32,
    end: u32,
    bytes: Vec<u8>,
    text: u32,
}

fn row(bytes: &[u8], at: usize) -> Option<[u32; 11]> {
    let mut out = [0; 11];
    for (i, value) in out.iter_mut().enumerate() {
        *value = u32::from_be_bytes(bytes.get(at + 4 * i..at + 4 * i + 4)?.try_into().ok()?);
    }
    Some(out)
}

fn segment_record(r: [u32; 11]) -> bool {
    let [_, start, end, _, _, ts, te, ds, de, bs, be] = r;
    if !(0x8000_0000..0x8080_0000).contains(&start) || end <= start || end > 0x8080_0000 {
        return false;
    }
    r[5..].iter().all(|&v| v == 0)
        || (start == ts && ts < te && te == ds && ds <= de && de == bs && bs <= be && be == end)
}

fn segments(r: [u32; 11], pair: &Pair) -> Option<Option<(u32, u32)>> {
    if !segment_record(r) {
        return None;
    }
    let [_, start, _, _, _, ts, te, ds, de, bs, be] = r;
    if r[5..].iter().all(|&v| v == 0) {
        return (pair.bytes.len() <= 64).then_some(None);
    }
    (te - ts == pair.text && de - ds == pair.bytes.len() as u32 - pair.text)
        .then_some(Some((start, be - bs)))
}

/// Infer shared slots only when a whole ROM-source catalog has a unique
/// matching segment table in a pair named by boot constants. This is a
/// declared executable universe, still subject to native content/pin checks.
pub fn infer(rom: &[u8], boot: &[u8]) -> Vec<SlotFile> {
    let (named, blocks) = constants(boot);
    let mut values = BTreeMap::new();
    let mut conflicts = BTreeSet::new();
    for stores in &blocks {
        for (&at, &value) in stores {
            if values.insert(at, value).is_some_and(|old| old != value) {
                conflicts.insert(at);
            }
        }
    }
    let mut catalogs = BTreeMap::<u32, Vec<Pair>>::new();
    for stores in blocks {
        for &lo in stores
            .keys()
            .filter(|&&a| a % 4 == 0 && !stores.contains_key(&a.wrapping_sub(4)))
        {
            let mut rows = Vec::new();
            let mut at = lo;
            while let (Some(&start), Some(&end)) =
                (stores.get(&at), stores.get(&at.wrapping_add(4)))
            {
                let Ok((bytes, text)) = decode(rom, u64::from(start), u64::from(end)) else {
                    break;
                };
                rows.push(Pair {
                    start,
                    end,
                    bytes,
                    text,
                });
                let Some(next) = at.checked_add(8) else {
                    break;
                };
                at = next;
            }
            // Never admit a valid suffix of a damaged or truncated catalog.
            if rows.len() >= 3
                && !stores.contains_key(&at)
                && !stores.contains_key(&at.wrapping_add(4))
                && conflicts.range(lo..at).next().is_none()
            {
                catalogs.insert(lo, rows);
            }
        }
    }
    if catalogs.is_empty() {
        return Vec::new();
    }
    let images: Vec<_> = named
        .into_iter()
        .filter_map(|start| {
            let bytes = rom.get(start as usize..)?;
            let (mut text, used) = stream(bytes).ok()?;
            let (data, _) = stream(&bytes[used..]).ok()?;
            if text.len() + data.len() > LIMIT {
                return None;
            }
            text.extend(data);
            Some((start, text))
        })
        .collect();
    let mut out = Vec::new();
    for (source_table, pairs) in catalogs {
        let mut matches = Vec::new();
        for (source, image) in &images {
            let table_size = pairs.len() * 44;
            if image.len() < table_size {
                continue;
            }
            for at in (0..=image.len() - table_size).step_by(4) {
                let entries: Option<Vec<_>> = pairs
                    .iter()
                    .enumerate()
                    .map(|(i, p)| segments(row(image, at + 44 * i)?, p))
                    .collect();
                if let Some(entries) = entries
                    && entries.iter().flatten().count() >= 3
                {
                    // A matching prefix or suffix is not a complete segment table.
                    if at
                        .checked_sub(44)
                        .and_then(|p| row(image, p))
                        .is_some_and(segment_record)
                        || row(image, at + table_size).is_some_and(segment_record)
                    {
                        continue;
                    }
                    matches.push((*source, at, entries));
                }
            }
        }
        if matches.len() != 1 {
            continue;
        }
        let (metadata_source, metadata_offset, entries) = matches.pop().unwrap();
        for (index, (pair, entry)) in pairs.iter().zip(&entries).enumerate() {
            let Some((destination, bss)) = *entry else {
                continue;
            };
            // Only the addresses actually shared by multiple files are slots.
            if entries
                .iter()
                .flatten()
                .filter(|(a, _)| *a == destination)
                .count()
                < 2
            {
                continue;
            }
            out.push(SlotFile {
                source: pair.start,
                end: pair.end,
                destination,
                text: pair.text,
                data: pair.bytes.len() as u32 - pair.text,
                bss,
                index,
                source_table,
                metadata_source,
                metadata_offset,
                sha256: sha256(&pair.bytes),
            });
        }
    }
    out.sort_by_key(|f| (f.source, f.destination));
    out.dedup();
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn encoded(data: &[u8]) -> Vec<u8> {
        use std::io::Write;
        let mut e = flate2::write::DeflateEncoder::new(Vec::new(), flate2::Compression::default());
        e.write_all(data).unwrap();
        [
            vec![0x11, 0x72],
            (data.len() as u32).to_be_bytes().to_vec(),
            e.finish().unwrap(),
        ]
        .concat()
    }

    #[test]
    fn exact_stream_and_pair_boundaries_refuse_corruption() {
        let text: Vec<_> = (0..32).collect();
        let data = vec![7; 16];
        let bytes = [encoded(&text), encoded(&data)].concat();
        assert_eq!(
            decode(&bytes, 0, bytes.len() as u64).unwrap(),
            ([text, data].concat(), 32)
        );
        for size in [0u32, 31, 33, LIMIT as u32 + 1] {
            let mut bad = bytes.clone();
            bad[2..6].copy_from_slice(&size.to_be_bytes());
            assert!(decode(&bad, 0, bad.len() as u64).is_err());
        }
        for end in 0..bytes.len() {
            assert!(decode(&bytes, 0, end as u64).is_err());
        }
        assert!(decode(&bytes, u64::MAX, 0).is_err());
        let padded = [bytes.clone(), vec![0; 16]].concat();
        assert!(decode(&padded, 0, padded.len() as u64).is_err());
    }

    #[test]
    fn literal_stores_include_jr_delay_and_refuse_unknown_values() {
        let words = [
            0x3c088040u32,
            0x2508fe10,
            0x3c0900fd,
            0x25299ef0,
            0xad090000,
            0x03e00008,
            0xad090004,
        ];
        let bytes: Vec<_> = words.into_iter().flat_map(u32::to_be_bytes).collect();
        let (_, blocks) = constants(&bytes);
        assert_eq!(
            blocks,
            vec![[(0x803ffe10, 0xfc9ef0), (0x803ffe14, 0xfc9ef0)].into()]
        );
        let mut changed = words.to_vec();
        changed.insert(4, 0x8d290000);
        let bytes: Vec<_> = changed.into_iter().flat_map(u32::to_be_bytes).collect();
        assert!(constants(&bytes).1.is_empty());
    }

    fn fixture(shift: u32) -> (Vec<u8>, Vec<u8>, usize) {
        let mut rom = vec![0; 0x5000];
        let link = 0x8001_1000u32;
        let mut records = Vec::new();
        let mut init = vec![0x3c088030, 0x35081200]; // synthetic source-table address
        for index in 0..3u32 {
            let start = 0x2000 + shift + index * 0x100;
            let text: Vec<_> = [0x2402_0000 | index, 0x03e0_0008, 0, 0, 0, 0, 0, 0]
                .into_iter()
                .flat_map(u32::to_be_bytes)
                .collect();
            let data: Vec<_> = [link, 0x0123_4567, 0, 0]
                .into_iter()
                .flat_map(u32::to_be_bytes)
                .collect();
            let bytes = [encoded(&text), encoded(&data)].concat();
            let end = start + bytes.len() as u32;
            rom[start as usize..end as usize].copy_from_slice(&bytes);
            for (offset, value) in [(8 * index, start), (8 * index + 4, end)] {
                init.extend([
                    0x3c090000 | (value >> 16),
                    0x35290000 | (value & 0xffff),
                    0xad090000 | offset,
                ]);
            }
            records.extend(
                [
                    0,
                    link,
                    link + 64,
                    0,
                    0,
                    link,
                    link + 32,
                    link + 32,
                    link + 48,
                    link + 48,
                    link + 64,
                ]
                .into_iter()
                .flat_map(u32::to_be_bytes),
            );
        }
        records.resize(144, 0);
        let metadata_start = 0x1000 + shift;
        let bytes = [encoded(&[0; 16]), encoded(&records)].concat();
        rom[metadata_start as usize..metadata_start as usize + bytes.len()].copy_from_slice(&bytes);
        init.extend([0x340a0000 | metadata_start, 0x03e00008, 0]);
        (
            rom,
            init.into_iter().flat_map(u32::to_be_bytes).collect(),
            metadata_start as usize,
        )
    }

    #[test]
    fn catalog_inference_is_structural_and_refuses_missing_or_ambiguous_metadata() {
        for shift in [0, 0x480] {
            let (rom, boot, metadata) = fixture(shift);
            let files = infer(&rom, &boot);
            assert_eq!(files.len(), 3);
            assert!(files.iter().all(|f| f.destination == 0x80011000
                && f.text == 32
                && f.data == 16
                && f.bss == 16));
            assert_eq!(files[0].source, 0x2000 + shift);
            let mut missing = rom.clone();
            missing[metadata] = 0;
            assert!(infer(&missing, &boot).is_empty());
            let mut ambiguous = rom.clone();
            ambiguous[0x4000..0x4100].copy_from_slice(&rom[metadata..metadata + 0x100]);
            let mut named = boot.clone();
            named.extend(
                [0x340a4000u32, 0x03e00008, 0]
                    .into_iter()
                    .flat_map(u32::to_be_bytes),
            );
            assert!(infer(&ambiguous, &named).is_empty());
            let mut wrong_size = rom.clone();
            wrong_size[(0x2000 + shift) as usize + 5] ^= 16;
            assert!(infer(&wrong_size, &boot).is_empty());
        }
    }

    #[test]
    fn paired_slot_composition_verifies_text_and_relocates_only_text_pointers() {
        use crate::{
            GuestAddr,
            declared_loads::{DeclaredLoad, LoadEncoding, LoadImage},
            program::{GuestRange, RomOffset},
        };
        let (rom, boot, _) = fixture(0);
        let f = &infer(&rom, &boot)[0];
        let load = DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(0x80811000),
                size: f.text + f.data,
            },
            source: RomOffset(u64::from(f.source)),
            encoding: LoadEncoding::RarePair {
                end: RomOffset(u64::from(f.end)),
                text_size: f.text,
            },
            evidence: Default::default(),
            relocatable: true,
            linked: Some(GuestAddr(f.destination)),
        };
        let spec = LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(0x80810000),
                size: 16,
            },
            loads: vec![load],
        };
        let (_, image) = crate::declared_loads::compose(&rom, &spec).unwrap();
        assert_eq!(image.slots[0].2, 32);
        assert_eq!(image.word(GuestAddr(0x80811020)), Some(0x80811000));
        assert_eq!(image.word(GuestAddr(0x80811024)), Some(0x01234567));
        assert_eq!(image.instruction_word(GuestAddr(0x80811020)), None);
        let mut code_shaped_data = image.clone();
        let at = ((0x80811020 - code_shaped_data.base.pc.0) / 4) as usize;
        code_shaped_data.words[at..at + 3].copy_from_slice(&[0x24020007, 0x03e00008, 0]);
        assert!(!crate::data_roots::plausible_at(
            &code_shaped_data,
            GuestAddr(0x80811020),
            &[0x80811020].into()
        ));
        let identity = crate::program::RomIdentity {
            sha256: sha256(&rom),
            size: rom.len() as u64,
        };
        let rejected =
            crate::discovery::direct_cfg(identity, &code_shaped_data, &[GuestAddr(0x80811020)], 32)
                .unwrap();
        assert!(rejected.map.blocks.is_empty());
        assert!(
            rejected
                .map
                .unresolved
                .iter()
                .any(|u| u.kind == "unmapped_target")
        );
        assert_eq!(image.slot_copies(0x8001101c), vec![0x8081101c]);
        assert_eq!(image.slot_copies(0x80011020), vec![0x80011020]);
        assert!(crate::declared_loads::verify_slots(&image, Some(&spec)));
        let mut changed = spec.clone();
        if let LoadEncoding::RarePair { text_size, .. } = &mut changed.loads[0].encoding {
            *text_size += 4;
        }
        assert!(crate::declared_loads::compose(&rom, &changed).is_err());
        assert!(!crate::declared_loads::verify_slots(&image, Some(&changed)));
        changed.loads[0].encoding = spec.loads[0].encoding;
        changed.loads[0].linked = None;
        assert!(crate::declared_loads::compose(&rom, &changed).is_err());
    }
}
