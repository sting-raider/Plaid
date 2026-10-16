//! ROM-owned overlay descriptions. Recognition is structural, not title/address based.
//! A catalog is a discovery input; it does not certify reachability or a load lifetime.
use crate::{
    GuestAddr,
    declared_loads::{DeclaredLoad, LoadEncoding, yaz0},
    program::{EvidenceRefs, GuestRange, RomOffset},
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

const MAX_IMAGE: usize = 8 * 1024 * 1024;
fn word(bytes: &[u8], at: usize) -> Result<u32, String> {
    let end = at.checked_add(4).ok_or("overlay offset overflow")?;
    Ok(u32::from_be_bytes(
        bytes
            .get(at..end)
            .ok_or("truncated overlay word")?
            .try_into()
            .unwrap(),
    ))
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RomFile {
    pub virtual_start: u32,
    pub virtual_end: u32,
    pub rom_start: u32,
    pub rom_end: u32,
}
impl RomFile {
    pub fn decode(&self, rom: &[u8]) -> Result<Vec<u8>, String> {
        let size = self
            .virtual_end
            .checked_sub(self.virtual_start)
            .ok_or("reversed file range")? as usize;
        if size == 0 || size > MAX_IMAGE || self.rom_start == u32::MAX {
            return Err("unavailable or oversized overlay file".into());
        }
        let start = self.rom_start as usize;
        if self.rom_end == 0 {
            return Ok(rom
                .get(start..start.checked_add(size).ok_or("ROM range overflow")?)
                .ok_or("file outside ROM")?
                .to_vec());
        }
        let bytes = rom
            .get(start..self.rom_end as usize)
            .ok_or("compressed file outside ROM")?;
        if word(bytes, 4)? as usize != size {
            return Err("compressed file size differs from table".into());
        }
        yaz0(bytes)
    }
}

/// Locate a unique sorted 16-byte file table containing its own uncompressed
/// file. Its zero terminator must fit inside that self-entry. Deleted entries
/// retain their virtual range but do not supply bytes.
pub fn file_table(rom: &[u8]) -> Result<(u32, Vec<RomFile>), String> {
    let mut found = None;
    for start in (0..rom.len().saturating_sub(32)).step_by(16) {
        if word(rom, start)? != 0 || word(rom, start + 8)? != 0 || word(rom, start + 12)? != 0 {
            continue;
        }
        let mut files = Vec::new();
        let mut end = 0;
        for at in (start..rom.len().saturating_sub(15)).step_by(16).take(4097) {
            let f = RomFile {
                virtual_start: word(rom, at)?,
                virtual_end: word(rom, at + 4)?,
                rom_start: word(rom, at + 8)?,
                rom_end: word(rom, at + 12)?,
            };
            if f.virtual_start == 0 && f.virtual_end == 0 && f.rom_start == 0 && f.rom_end == 0 {
                if files.len() >= 2
                    && files.iter().any(|r: &RomFile| {
                        r.virtual_start as usize == start
                            && r.rom_start as usize == start
                            && r.rom_end == 0
                            && r.virtual_end as usize >= at + 16
                    })
                {
                    if found.is_some() {
                        return Err("ambiguous ROM file tables".into());
                    }
                    found = Some((start as u32, files));
                }
                break;
            }
            let Some(size) = f.virtual_end.checked_sub(f.virtual_start) else {
                break;
            };
            if size == 0
                || size as usize > MAX_IMAGE
                || f.virtual_start < end
                || files.len() == 4096
            {
                break;
            }
            if f.rom_start != u32::MAX {
                let physical_end = if f.rom_end == 0 {
                    f.rom_start.checked_add(size)
                } else {
                    Some(f.rom_end)
                };
                if physical_end.is_none_or(|e| e <= f.rom_start || e as usize > rom.len()) {
                    break;
                }
            } else if f.rom_end != u32::MAX {
                break;
            }
            end = f.virtual_end;
            files.push(f);
        }
    }
    found.ok_or_else(|| "no self-describing ROM file table".into())
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Relocation {
    /// Byte offset in the decoded image (section-relative on disk).
    pub offset: u32,
    pub kind: u8,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Layout {
    pub text: u32,
    pub data: u32,
    pub rodata: u32,
    pub bss: u32,
    pub file_size: u32,
    pub relocations: Vec<Relocation>,
}
impl Layout {
    /// Zelda64 trailer profile: text/data/rodata, relocation section, then BSS
    /// in RAM. Other overlay formats must identify their own profile.
    pub fn parse(bytes: &[u8]) -> Result<Self, String> {
        if bytes.len() < 24 || bytes.len() > MAX_IMAGE || !bytes.len().is_multiple_of(4) {
            return Err("invalid overlay file size".into());
        }
        let trailer = word(bytes, bytes.len() - 4)? as usize;
        if trailer < 24 || trailer > bytes.len() || !trailer.is_multiple_of(4) {
            return Err("invalid overlay trailer".into());
        }
        let at = bytes.len() - trailer;
        let (text, data, rodata, bss) = (
            word(bytes, at)?,
            word(bytes, at + 4)?,
            word(bytes, at + 8)?,
            word(bytes, at + 12)?,
        );
        let sizes = [text, data, rodata];
        if sizes.iter().any(|n| !n.is_multiple_of(4))
            || sizes.iter().map(|n| u64::from(*n)).sum::<u64>() != at as u64
            || bytes.len() as u64 + u64::from(bss) > MAX_IMAGE as u64
        {
            return Err("overlay sections disagree with trailer".into());
        }
        let count = word(bytes, at + 16)? as usize;
        if count > (trailer - 24) / 4 {
            return Err("overlay relocation count exceeds trailer".into());
        }
        let mut relocations = Vec::with_capacity(count);
        let mut seen = BTreeSet::new();
        for n in 0..count {
            let packed = word(bytes, at + 20 + 4 * n)?;
            let section = (packed >> 30) as usize;
            let kind = ((packed >> 24) & 63) as u8;
            let local = packed & 0xffffff;
            if section == 0
                || !matches!(kind, 2 | 4 | 5 | 6)
                || !local.is_multiple_of(4)
                || local.checked_add(4).is_none_or(|e| e > sizes[section - 1])
            {
                return Err("unsupported or out-of-section overlay relocation".into());
            }
            let offset = sizes[..section - 1].iter().sum::<u32>() + local;
            if !seen.insert(offset) {
                return Err("duplicate overlay relocation site".into());
            }
            relocations.push(Relocation { offset, kind });
        }
        if bytes[at + 20 + count * 4..bytes.len() - 4]
            .iter()
            .any(|b| *b != 0)
        {
            return Err("nonzero overlay trailer padding".into());
        }
        Ok(Self {
            text,
            data,
            rodata,
            bss,
            file_size: bytes.len() as u32,
            relocations,
        })
    }

    /// Materialize the exact loader result, retaining upper instruction bits.
    /// HI/LO matching follows register identity, including reused HI records.
    pub fn relocate(&self, bytes: &[u8], link: u32, loaded: u32) -> Result<Vec<u8>, String> {
        if Self::parse(bytes)? != *self {
            return Err("overlay layout does not match source".into());
        }
        let span = self
            .file_size
            .checked_add(self.bss)
            .ok_or("overlay span overflow")?;
        let end = link
            .checked_add(span)
            .ok_or("overlay link range overflow")?;
        if !link.is_multiple_of(4)
            || !loaded.is_multiple_of(4)
            || !(0x80000000..0xa0000000).contains(&link)
            || loaded < 0x80000000
            || loaded.checked_add(span).is_none_or(|e| e > 0x80800000)
        {
            return Err("overlay load outside aligned direct RAM".into());
        }
        let delta = loaded.wrapping_sub(link);
        let target = |address: u32| -> Result<u32, String> {
            if !(link..=end).contains(&address) {
                return Err("relocation target outside overlay".into());
            }
            Ok(address.wrapping_add(delta))
        };
        let mut out = bytes.to_vec();
        let mut highs: [Option<(usize, u32)>; 32] = [None; 32];
        for r in &self.relocations {
            let at = r.offset as usize;
            let w = word(&out, at)?;
            let changed = match r.kind {
                2 if w & 0x0f000000 != 0 => w, // Segmented data pointer: loader leaves it alone.
                2 => target(w)?,
                4 => {
                    if !matches!(w >> 26, 2 | 3) {
                        return Err("R_MIPS_26 does not name J/JAL".into());
                    }
                    (w & 0xfc000000)
                        | ((target(0x80000000 | ((w & 0x03ffffff) << 2))? & 0x0fffffff) >> 2)
                }
                5 => {
                    if w >> 26 != 15 || w >> 21 & 31 != 0 {
                        return Err("HI16 does not name LUI".into());
                    }
                    highs[((w >> 16) & 31) as usize] = Some((at, w));
                    continue;
                }
                6 => {
                    let (hi, original) = highs[((w >> 21) & 31) as usize]
                        .ok_or("LO16 lacks register-matched HI16")?;
                    let current = word(&out, hi)?;
                    let low = w as u16 as i16 as i32 as u32;
                    if current.wrapping_shl(16).wrapping_add(low) & 0x0f000000 != 0 {
                        continue;
                    }
                    let value = target(original.wrapping_shl(16).wrapping_add(low))?;
                    let high = (current & 0xffff0000) | (value.wrapping_add(0x8000) >> 16);
                    out[hi..hi + 4].copy_from_slice(&high.to_be_bytes());
                    (w & 0xffff0000) | (value & 0xffff)
                }
                _ => return Err("unsupported relocation".into()),
            };
            out[at..at + 4].copy_from_slice(&changed.to_be_bytes());
        }
        out.resize(span as usize, 0);
        Ok(out)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Overlay {
    pub file: RomFile,
    pub link: u32,
    pub source_sha256: String,
    pub layout: Layout,
    pub table_offsets: Vec<u32>,
}

/// Find contiguous VROM start/end, link start/end tuples in a supplied static
/// image. File identity and trailer layout must independently agree. Callers
/// retain that image's identity alongside these offsets.
pub fn discover(rom: &[u8], table_image: &[u8]) -> Result<Vec<Overlay>, String> {
    let (_, files) = file_table(rom)?;
    let files: BTreeMap<_, _> = files.into_iter().map(|f| (f.virtual_start, f)).collect();
    let mut found: BTreeMap<(u32, u32), Overlay> = BTreeMap::new();
    for at in (0..table_image.len().saturating_sub(15)).step_by(4) {
        let a = word(table_image, at)?;
        let Some(file) = files.get(&a) else { continue };
        if word(table_image, at + 4)? != file.virtual_end {
            continue;
        }
        let (link, end) = (word(table_image, at + 8)?, word(table_image, at + 12)?);
        if !(0x80000000..0xa0000000).contains(&link) || end <= link || end - link > MAX_IMAGE as u32
        {
            continue;
        }
        let bytes = file.decode(rom)?;
        // a fixed-address file named the same way has no relocation trailer;
        // it is not an overlay, and leaving it out of the image fails closed
        let Ok(layout) = Layout::parse(&bytes) else {
            continue;
        };
        if layout.file_size.checked_add(layout.bss) != Some(end - link) {
            return Err("overlay table range differs from file and BSS".into());
        }
        layout
            .relocate(&bytes, link, 0x80000000)
            .map_err(|e| format!("overlay file {a:#x}: {e}"))?;
        found
            .entry((a, link))
            .or_insert_with(|| Overlay {
                file: file.clone(),
                link,
                source_sha256: sha256(&bytes),
                layout,
                table_offsets: Vec::new(),
            })
            .table_offsets
            .push(at as u32);
    }
    Ok(found.into_values().collect())
}

/// The executable overlays of a catalog as relocatable loads at their link
/// addresses, in link order: each file's bytes (text, data, rodata and the
/// relocation trailer) as the table stores them. Data-only overlays and
/// overlays sharing a link range are left out; their code, if any, stays
/// outside the image and fails closed.
pub fn loads(overlays: &[Overlay], evidence: &EvidenceRefs) -> Vec<DeclaredLoad> {
    let mut out: Vec<DeclaredLoad> = Vec::new();
    let mut sorted: Vec<&Overlay> = overlays.iter().filter(|o| o.layout.text > 0).collect();
    sorted.sort_by_key(|o| o.link);
    for (i, o) in sorted.iter().enumerate() {
        let end = u64::from(o.link) + u64::from(o.layout.file_size + o.layout.bss);
        let clash = |p: &&Overlay| {
            u64::from(p.link) < end
                && u64::from(o.link)
                    < u64::from(p.link) + u64::from(p.layout.file_size + p.layout.bss)
        };
        if sorted[..i].iter().chain(&sorted[i + 1..]).any(clash) {
            continue;
        }
        out.push(DeclaredLoad {
            destination: GuestRange {
                start: GuestAddr(o.link),
                size: o.layout.file_size,
            },
            source: RomOffset(u64::from(o.file.rom_start)),
            encoding: if o.file.rom_end == 0 {
                LoadEncoding::Raw
            } else {
                LoadEncoding::Yaz0
            },
            evidence: evidence.clone(),
            relocatable: true,
        });
    }
    out
}

/// A non-relocatable file the code places at a fixed address (ADR-0183).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StaticLoad {
    pub file: RomFile,
    pub destination: u32,
    pub size: u32,
    /// Where the image names the file's virtual start, and where it builds
    /// the destination.
    pub file_constant_at: u32,
    pub destination_constant_at: u32,
    /// The file's own `jal` targets inside it, and how many of those follow
    /// a `jr ra` once placed at `destination`.
    pub calls: (u32, u32),
}

/// `lui`/`addiu`/`ori` constants of `bytes` placed at `base`, with the pc
/// that completes each (the first, so the result is deterministic).
fn constants(bytes: &[u8], base: u32) -> BTreeMap<u32, u32> {
    let words: Vec<u32> = bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let mut out = BTreeMap::new();
    for (k, &w) in words.iter().enumerate() {
        if w >> 26 != 0xf {
            continue;
        }
        let (rt, hi) = ((w >> 16) & 31, w << 16);
        for (m, &v) in words.iter().enumerate().skip(k + 1).take(16) {
            let lo = v & 0xffff;
            let value = match v >> 26 {
                9 => hi.wrapping_add(lo as i16 as u32),
                0xd => hi | lo,
                _ => continue,
            };
            if (v >> 21) & 31 == rt {
                out.entry(value).or_insert(base.wrapping_add(4 * m as u32));
            }
        }
    }
    out
}

/// Fixed loads reachable from the base window: a ROM file whose virtual start
/// the code builds as a constant, placed at the one constant RAM address
/// where at least 95% of its own `jal` targets begin a function (follow a
/// `jr ra`), with at least one call per 4 KiB. Accepted files join the
/// search. A tie between destinations, or overlapping placements, accepts
/// nothing: the caller declares such a load by hand or it stays out of the
/// image and fails closed.
pub fn static_loads(rom: &[u8], base: &[u8], at: u32) -> Result<Vec<StaticLoad>, String> {
    const JR_RA: u32 = 0x03e0_0008;
    // shortcut: loads are inferred only for ROMs with a file table; others
    // declare theirs by hand until a table-free rule exists
    let Ok((_, files)) = file_table(rom) else {
        return Ok(Vec::new());
    };
    let mut by_start: BTreeMap<u32, RomFile> = files
        .into_iter()
        .filter(|f| f.virtual_start != 0 && f.rom_start != u32::MAX)
        .map(|f| (f.virtual_start, f))
        .collect();
    let mut work = vec![(base.to_vec(), at)];
    let mut out: Vec<StaticLoad> = Vec::new();
    while let Some((image, at)) = work.pop() {
        let found = constants(&image, at);
        let ram: Vec<(u32, u32)> = found
            .iter()
            .filter(|(v, _)| (0x8000_0000..0x8080_0000).contains(*v) && *v % 4 == 0)
            .map(|(&v, &pc)| (v, pc))
            .collect();
        for (&value, &named_at) in &found {
            let Some(file) = by_start.get(&value).cloned() else {
                continue;
            };
            let Ok(bytes) = file.decode(rom) else {
                continue;
            };
            let word = |off: u32| word(&bytes, off as usize).ok();
            let targets: Vec<u32> = (0..bytes.len() as u32 / 4)
                .filter_map(|k| word(4 * k))
                .filter(|w| w >> 26 == 3)
                .map(|w| 0x8000_0000 | ((w & 0x03ff_ffff) << 2))
                .collect();
            let score = |dest: u32| {
                let inside = targets
                    .iter()
                    .filter_map(|t| t.checked_sub(dest))
                    .filter(|&off| (off as usize) < bytes.len());
                inside.fold((0u32, 0u32), |(hit, all), off| {
                    // `jr ra`, its delay slot, then any zero padding
                    let mut p = off;
                    while p >= 4 && off - p < 40 && word(p - 4) == Some(0) {
                        p -= 4;
                    }
                    let start = off == 0
                        || (p >= 4 && word(p - 4) == Some(JR_RA))
                        || (p >= 8 && word(p - 8) == Some(JR_RA));
                    (hit + start as u32, all + 1)
                })
            };
            let mut best: Option<(u32, u32, u32, u32)> = None;
            let mut tied = false;
            for &(dest, pc) in &ram {
                let (hit, all) = score(dest);
                if u64::from(all) * 4096 < bytes.len() as u64 || hit * 20 < all * 19 {
                    continue;
                }
                match best {
                    Some((h, ..)) if hit < h => {}
                    Some((h, ..)) if hit == h => tied = true,
                    _ => {
                        best = Some((hit, all, dest, pc));
                        tied = false;
                    }
                }
            }
            let Some((hit, all, destination, pc)) = best.filter(|_| !tied) else {
                continue;
            };
            let size = bytes.len() as u32;
            let end = u64::from(destination) + u64::from(size);
            if out.iter().any(|l| {
                u64::from(l.destination) < end
                    && u64::from(destination) < u64::from(l.destination) + u64::from(l.size)
            }) {
                return Err(format!(
                    "inferred loads overlap at {destination:#x}; declare them by hand"
                ));
            }
            by_start.remove(&value);
            out.push(StaticLoad {
                file,
                destination,
                size,
                file_constant_at: named_at,
                destination_constant_at: pc,
                calls: (all, hit),
            });
            work.push((bytes, destination));
        }
    }
    out.sort_by_key(|l| l.destination);
    Ok(out)
}

/// The reset stub: the boot window's bytes before the first file the table
/// places in it (ADR-0183). IPL3 copies both, but the stub is its own file and
/// the game may reclaim it, so it is declared as a load of its own: a write
/// revokes it, and running it again re-checks its bytes.
pub fn reset_stub(rom: &[u8], window: u32) -> Option<u32> {
    let (_, files) = file_table(rom).ok()?;
    files
        .iter()
        .filter(|f| f.rom_end == 0 && f.rom_start == f.virtual_start)
        .map(|f| f.rom_start)
        .filter(|&s| s > 0x1000 && s < 0x1000 + window && s % 4 == 0)
        .min()
        .map(|s| s - 0x1000)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> Vec<u8> {
        let mut words = vec![
            0x3c088080, 0x25080020, 0x0c200004, 0, 0x03e00008, 0, 0, 0, 0x80800034, 0x06001234, 0,
            0, 0, 0, 0, 0,
        ];
        let start = words.len() * 4;
        words.extend([
            32, 16, 16, 16, 5, 0x45000000, 0x46000004, 0x44000008, 0x82000000, 0x82000004,
        ]);
        while !(words.len() + 1).is_multiple_of(4) {
            words.push(0);
        }
        words.push(((words.len() + 1) * 4 - start) as u32);
        words.into_iter().flat_map(u32::to_be_bytes).collect()
    }
    fn put(bytes: &mut [u8], at: usize, value: u32) {
        bytes[at..at + 4].copy_from_slice(&value.to_be_bytes());
    }
    #[test]
    fn relocating_at_different_bases_preserves_opcodes_and_carries_signed_low() {
        let bytes = fixture();
        let layout = Layout::parse(&bytes).unwrap();
        for base in [0x80001000, 0x80017ff0, 0x803fffe0] {
            let result = layout.relocate(&bytes, 0x80800000, base).unwrap();
            let pointer = base + 32;
            assert_eq!(
                word(&result, 0).unwrap(),
                0x3c080000 | pointer.wrapping_add(0x8000) >> 16
            );
            assert_eq!(word(&result, 4).unwrap(), 0x25080000 | pointer & 0xffff);
            assert_eq!(
                word(&result, 8).unwrap(),
                0x0c000000 | ((base + 16) & 0x0fffffff) >> 2
            );
            assert_eq!(word(&result, 32).unwrap(), base + 52);
            assert_eq!(word(&result, 36).unwrap(), 0x06001234);
            assert_eq!(&result[bytes.len()..], &[0; 16]);
        }
    }
    #[test]
    fn malformed_trailers_and_unpaired_relocations_fail_closed() {
        let bytes = fixture();
        for (at, value) in [
            (bytes.len() - 4, u32::MAX),
            (80, u32::MAX),
            (84, 0x05000000),
            (84, 0x45000020),
            (88, 0x46000005),
            (88, 0x46000000),
            (84, 0x47000000),
        ] {
            let mut bad = bytes.clone();
            put(&mut bad, at, value);
            assert!(Layout::parse(&bad).is_err(), "{at}: {value:x}");
        }
        let mut bad = bytes.clone();
        put(&mut bad, 4, 0x25290020); // LO refers to unrecorded r9.
        assert!(
            Layout::parse(&bad)
                .unwrap()
                .relocate(&bad, 0x80800000, 0x80001000)
                .is_err()
        );
        let mut bad = bytes.clone();
        put(&mut bad, 32, 0x80000000);
        assert!(
            Layout::parse(&bad)
                .unwrap()
                .relocate(&bad, 0x80800000, 0x80001000)
                .is_err()
        );
        assert!(
            Layout::parse(&bytes)
                .unwrap()
                .relocate(&bytes, 0x80800000, 0x807ffff0)
                .is_err()
        );
    }
    #[test]
    fn file_table_and_overlay_tuple_are_discovered_without_fixed_locations() {
        let overlay = fixture();
        for table_at in [0x40, 0xc0] {
            let mut rom = vec![0; 0x800];
            for (n, w) in [
                0,
                0x20,
                0,
                0,
                table_at,
                table_at + 64,
                table_at,
                0,
                0x1000,
                0x1000 + overlay.len() as u32,
                0x400,
                0,
            ]
            .into_iter()
            .enumerate()
            {
                put(&mut rom, table_at as usize + n * 4, w);
            }
            rom[0x400..0x400 + overlay.len()].copy_from_slice(&overlay);
            let mut image = vec![0; 64];
            for (n, w) in [
                0x1000,
                0x1000 + overlay.len() as u32,
                0x80800000,
                0x80800000 + overlay.len() as u32 + 16,
            ]
            .into_iter()
            .enumerate()
            {
                put(&mut image, 12 + n * 4, w);
            }
            let catalog = discover(&rom, &image).unwrap();
            assert_eq!(catalog.len(), 1);
            assert_eq!(catalog[0].table_offsets, vec![12]);
            assert_eq!(file_table(&rom).unwrap().0, table_at);
            put(&mut image, 24, 0x80800004);
            assert!(discover(&rom, &image).is_err());
            if table_at == 0x40 {
                loads_place_executable_overlays_at_their_link_addresses(&catalog);
            }
        }
    }

    /// A table with a reset stub, a boot file and one code file; the boot
    /// file names the code file and two RAM addresses (ADR-0183).
    fn static_rom(dest: bool) -> Vec<u8> {
        let mut rom = vec![0; 0x2100];
        let table = [
            [0, 0x20, 0, 0],
            [0x40, 0x90, 0x40, 0],
            [0x1060, 0x1100, 0x1060, 0],
            [0x2000, 0x2020, 0x2000, 0],
        ];
        for (n, w) in table.iter().flatten().enumerate() {
            put(&mut rom, 0x40 + n * 4, *w);
        }
        let boot = [
            0x3c05_0000,                        // lui a1, 0
            0x24a5_2000,                        // addiu a1, a1, 0x2000
            0x3c04_8020,                        // lui a0, 0x8020 (a decoy)
            0x2484_0000,                        // addiu a0, a0, 0
            if dest { 0x3c06_8010 } else { 0 }, // lui a2, 0x8010
            if dest { 0x24c6_0000 } else { 0 }, // addiu a2, a2, 0
        ];
        for (n, w) in boot.into_iter().enumerate() {
            put(&mut rom, 0x1080 + n * 4, w);
        }
        // f0 calls f1 at +0x10, which calls f0
        let code = [
            0x0c04_0004,
            0,
            0x03e0_0008,
            0,
            0x0c04_0000,
            0,
            0x03e0_0008,
            0,
        ];
        for (n, w) in code.into_iter().enumerate() {
            put(&mut rom, 0x2000 + n * 4, w);
        }
        rom
    }

    #[test]
    fn a_named_file_is_placed_where_its_calls_begin_functions() {
        let rom = static_rom(true);
        let [load] = static_loads(&rom, &rom[0x1000..0x1100], 0x80000400)
            .unwrap()
            .try_into()
            .unwrap();
        assert_eq!(
            (load.file.rom_start, load.destination, load.size),
            (0x2000, 0x80100000, 0x20)
        );
        assert_eq!(load.calls, (2, 2));
        assert_eq!(reset_stub(&rom, 0x100), Some(0x60));
        // without a destination whose calls fit, nothing is inferred
        let rom = static_rom(false);
        assert!(
            static_loads(&rom, &rom[0x1000..0x1100], 0x80000400)
                .unwrap()
                .is_empty()
        );
    }

    fn loads_place_executable_overlays_at_their_link_addresses(catalog: &[Overlay]) {
        let refs: EvidenceRefs = ["overlays:test".to_string()].into();
        let [load] = loads(catalog, &refs).try_into().unwrap();
        assert_eq!(load.destination.start, GuestAddr(0x80800000));
        assert_eq!(load.destination.size, catalog[0].layout.file_size);
        assert_eq!(load.source, RomOffset(0x400));
        assert_eq!(load.encoding, LoadEncoding::Raw);
        assert!(load.relocatable && load.evidence == refs);
        // an overlay sharing its link range makes both ambiguous
        let mut twin = catalog[0].clone();
        twin.link += 4;
        assert!(loads(&[catalog[0].clone(), twin], &refs).is_empty());
        // a data-only overlay supplies no code
        let mut data = catalog[0].clone();
        data.layout.text = 0;
        assert!(loads(&[data], &refs).is_empty());
    }
}
