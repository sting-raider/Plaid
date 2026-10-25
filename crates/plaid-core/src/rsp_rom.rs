//! Candidate data pointers, not a proof of the RSP executable universe.
use crate::{GuestAddr, discovery::CodeImage, indirect::transfer, program::ProgramMap};
use std::collections::BTreeSet;

/// Collect aligned image pointers from data and constant expressions in decoded
/// CPU blocks. A pointer is only a search hint; consumers must check its bytes.
pub fn roots(image: &CodeImage, map: &ProgramMap) -> BTreeSet<GuestAddr> {
    constants(image, map)
        .into_iter()
        .filter(|&address| image.word(address).is_some())
        .collect()
}

/// [`roots`] before the image's own bytes are required: aligned values the
/// image's data and decoded blocks name, wherever they point (ADR-0225).
pub fn constants(image: &CodeImage, map: &ProgramMap) -> BTreeSet<GuestAddr> {
    let mut out = BTreeSet::new();
    let mut add = |value: u32| {
        if value.is_multiple_of(8) {
            out.insert(GuestAddr(value));
        }
    };
    for (i, &word) in image.words.iter().enumerate() {
        if image
            .word(GuestAddr(image.base.pc.0 + i as u32 * 4))
            .is_some()
        {
            add(word);
        }
    }
    for block in &map.blocks {
        if block.start.image != image.base.image || block.start.generation != image.base.generation
        {
            continue;
        }
        let mut state = [None; 32];
        state[0] = Some(0);
        for offset in (0..block.size).step_by(4) {
            let pc = GuestAddr(block.start.pc.0 + offset);
            let Some(word) = image.word(pc) else { break };
            transfer(word, pc, &mut state);
            for value in state.iter().flatten() {
                add(*value as u32);
            }
        }
    }
    for value in crate::data_roots::pointer_constants(image, map).into_keys() {
        add(value.0);
    }
    out
}

/// Recognize a constant-sized boot DMA from OSTask.ucode to IMEM. This is a
/// search contract for the standard task loader, never a general RSP proof.
/// Paths from IMEM 0 follow jumps, both branch arms and constant JR targets
/// (ADR-0251): a boot may load the ucode pointer after the code that uses it.
pub fn boot_ucode_size(bytes: &[u8]) -> Option<u32> {
    boot_dma_contract(bytes).0
}

/// ROM-byte compositions a boot can write back to OSTask.ucode_boot through
/// one bounded, contiguous IMEM-to-RDRAM DMA. These remain candidates only.
pub fn boot_self_replacements(bytes: &[u8]) -> BTreeSet<Vec<u8>> {
    boot_dma_contract(bytes).1
}

fn boot_dma_contract(bytes: &[u8]) -> (Option<u32>, BTreeSet<Vec<u8>>) {
    // A task boot is small; a whole microcode at IMEM 0 is not searched past it.
    const WINDOW: u32 = 0x200;
    let words: Vec<u32> = bytes
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let mut state = [None; 32];
    state[0] = Some(0);
    // Task-field provenance is separate from numeric register constants.
    type Path = (
        [Option<u64>; 32],
        [Option<u32>; 32],
        Option<u64>,
        Option<u32>,
        [Option<u32>; 2],
    );
    let mut work: Vec<(u32, Path)> = vec![(0, (state, [None; 32], None, None, [None; 2]))];
    let mut seen = std::collections::HashSet::new();
    let mut size = None;
    let mut replacements = BTreeSet::new();
    while let Some((pc, path)) = work.pop() {
        if seen.len() >= 4096 || pc >= WINDOW || !seen.insert((pc, path)) {
            continue;
        }
        let (mut state, mut ucode, mut mem, mut source, pending) = path;
        let Some(&word) = words.get(pc as usize / 4) else {
            continue;
        };
        let (rs, rt, rd) = (
            ((word >> 21) & 31) as usize,
            ((word >> 16) & 31) as usize,
            (word >> 11) & 31,
        );
        if word >> 26 == 16 && rs == 4 {
            match rd {
                0 => mem = state[rt],
                1 => source = ucode[rt],
                2 if source == Some(0xfd0) && mem == Some(0x1080) => {
                    if let Some(n) = state[rt] {
                        let n = ((n as u32 & 0xfff) | 7) + 1;
                        if n <= 0xf80 {
                            size.get_or_insert(n);
                        }
                    }
                    // This DMA replaces the boot's IMEM; do not inspect its
                    // former words for further self-write candidates.
                    continue;
                }
                3 if source == Some(0xfc8) => {
                    if let (Some(mem), Some(length)) = (mem, state[rt]) {
                        let start = (mem & 0xff8) as usize;
                        let n = ((length as usize & 0xfff) | 7) + 1;
                        // Refuse DMEM, multi-row/skip, wrap and unknown bytes.
                        if mem & 0x1000 != 0
                            && length <= 0xfff
                            && start + n <= bytes.len()
                            && start + n <= 0x1000
                            && n <= bytes.len()
                        {
                            let mut variant = bytes.to_vec();
                            variant[..n].copy_from_slice(&bytes[start..start + n]);
                            if variant != bytes {
                                replacements.insert(variant);
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        let branch = pc.wrapping_add(4).wrapping_add((word as i16 as u32) << 2) & 0xffc;
        let targets = match (word >> 26, word & 63) {
            (0, 13) => continue, // BREAK ends the task
            (0, 8 | 9) => [state[rs].map(|v| v as u32 & 0xffc), None],
            (2 | 3, _) => [Some((word << 2) & 0xffc), None],
            (1, _) if matches!(rt, 0 | 1 | 16 | 17) => [Some(branch), Some(pc + 8)],
            (4..=7, _) => [Some(branch), Some(pc + 8)],
            _ => [None; 2],
        };
        let control = targets[0].is_some() || matches!((word >> 26, word & 63), (0, 8 | 9));
        // DMEM addresses wrap at 4 KiB, so -0x30(zero) is OSTask.ucode too.
        let pointer = (word >> 26 == 35)
            .then(|| state[rs].map(|v| (v as u32).wrapping_add(word as i16 as u32) & 0xfff))
            .flatten()
            .filter(|&field| matches!(field, 0xfc8 | 0xfd0));
        if let Some(dest) = crate::discovery::decode(word, GuestAddr(0))
            .destination_gpr()
            .filter(|&dest| dest != 0)
        {
            ucode[dest as usize] = pointer;
        }
        // ADDI has wrapping RSP semantics, unlike the trapping CPU form.
        let word = if word >> 26 == 8 {
            word ^ (1 << 26)
        } else {
            word
        };
        transfer(word, GuestAddr(pc), &mut state);
        if word >> 26 == 3 || (word >> 26 == 0 && word & 63 == 9) {
            state[if word >> 26 == 3 { 31 } else { rd as usize }] = Some(u64::from(pc + 8));
        }
        if control {
            // The delay slot runs first, then each target.
            work.push((pc + 4, (state, ucode, mem, source, targets)));
        } else if pending[0].is_some() || pending[1].is_some() {
            for target in pending.into_iter().flatten() {
                work.push((target, (state, ucode, mem, source, [None; 2])));
            }
        } else {
            work.push((pc + 4, (state, ucode, mem, source, [None; 2])));
        }
    }
    (size, replacements)
}

/// SDK overlay-table hints: u32 offset from ucode, u16 DMA length minus one,
/// u16 SP destination. Only rooted data within one DMEM-sized window is scanned.
/// A descriptor is not authority: the target must also pass content filtering.
pub fn overlay_descriptors(
    image: &CodeImage,
    roots: &BTreeSet<GuestAddr>,
) -> BTreeSet<(u32, u32, u32)> {
    let mut out = BTreeSet::new();
    for (i, &offset) in image.words.iter().enumerate() {
        let at = GuestAddr(image.base.pc.0 + i as u32 * 4);
        if !at.0.is_multiple_of(8) || offset == 0 || offset > 0x10000 || !offset.is_multiple_of(8) {
            continue;
        }
        if roots
            .range(..=at)
            .next_back()
            .is_none_or(|r| at.0 - r.0 >= 0x1000)
        {
            continue;
        }
        let Some(spec) = image.word(GuestAddr(at.0 + 4)) else {
            continue;
        };
        let dest = spec & 0xffff;
        let size = ((spec >> 16) | 7) + 1;
        if image.word(at).is_some()
            && (0x1000..0x2000).contains(&dest)
            && dest.is_multiple_of(8)
            && size >= 64
            && size <= 0x2000 - dest
        {
            out.insert((offset, size, dest & 0xfff));
        }
    }
    let layouts = roots
        .iter()
        .flat_map(|root| {
            let bytes: Vec<_> = (0..0x1000)
                .step_by(4)
                .map_while(|n| image.word(GuestAddr(root.0.saturating_add(n))))
                .flat_map(u32::to_be_bytes)
                .collect();
            packed_overlay_layouts(&bytes, 0x80)
        })
        .collect();
    out.extend(packed_overlay_descriptors(image, roots, &layouts));
    out
}

/// Recognize a packed-table DMA loader's field accesses and native SP DMA
/// helper. This supplies a table layout hint, not a control-flow certificate.
fn packed_overlay_layouts(text: &[u8], imem: u32) -> BTreeSet<(u32, u32)> {
    let words: Vec<_> = text
        .as_chunks::<4>()
        .0
        .iter()
        .map(|w| u32::from_be_bytes(*w))
        .collect();
    let rs = |w: u32| (w >> 21) & 31;
    let rt = |w: u32| (w >> 16) & 31;
    let rd = |w: u32| (w >> 11) & 31;
    let mut layouts = BTreeSet::new();
    for (i, &load) in words.iter().enumerate().filter(|(_, w)| *w >> 26 == 37) {
        let length = rt(load);
        if length == 0 {
            continue;
        }
        let window = &words[i..words.len().min(i + 32)];
        if !window.contains(&(0x3000_0fff | length << 21 | length << 16)) {
            continue;
        }
        for &shift in window
            .iter()
            .filter(|&&w| w & 0xffe0_07ff == 0x302 && rt(w) == length)
        {
            let destination = rd(shift);
            for &source in window.iter().filter(|&&w| {
                w >> 26 == 37 && rs(w) == rs(load) && (w & 0xffff) == (load & 0xffff) + 2
            }) {
                let address = rt(source);
                if address == 0 {
                    continue;
                }
                // The source offset is added to OSTask.ucode, not an arbitrary
                // pointer loaded from DMEM. The task base itself remains a hint.
                let adds_ucode = window.iter().any(|&w| {
                    w >> 26 == 35
                        && w & 0xffff == 0x10
                        && window.iter().any(|&add| {
                            add & 0xfc00_07ff == 0x21
                                && rd(add) == address
                                && ((rs(add) == address && rt(add) == rt(w))
                                    || (rt(add) == address && rs(add) == rt(w)))
                        })
                });
                if !adds_ucode {
                    continue;
                }
                for pair in window.windows(2).filter(|pair| pair[0] >> 26 == 3) {
                    let slot = pair[1];
                    if slot >> 26 != 37 || rs(slot) != destination || rt(slot) != destination {
                        continue;
                    }
                    let target = (pair[0] << 2) & 0xfff;
                    let Some(at) = target.checked_sub(imem).map(|v| v as usize / 4) else {
                        continue;
                    };
                    let Some(helper) = words.get(at..words.len().min(at + 32)) else {
                        continue;
                    };
                    let dma = [
                        0x4080_0000 | destination << 16,
                        0x4080_0800 | address << 16,
                        0x4080_1000 | length << 16,
                    ];
                    if helper.windows(3).any(|w| w == dma) {
                        let (len, dest) = (load & 0xffff, slot & 0xffff);
                        if len > dest && (len - dest).is_multiple_of(2) && len - dest <= 16 {
                            layouts.insert((len, dest));
                        }
                    }
                }
            }
        }
    }
    layouts
}

/// Decode only layouts named by a rooted RSP loader. Packed lengths select
/// a destination halfword by byte offset; low twelve bits are SP_RD_LEN.
/// The resulting ROM candidates still require content and live-fetch guards.
fn packed_overlay_descriptors(
    image: &CodeImage,
    roots: &BTreeSet<GuestAddr>,
    layouts: &BTreeSet<(u32, u32)>,
) -> BTreeSet<(u32, u32, u32)> {
    let half = |at: u32| {
        image
            .word(GuestAddr(at & !3))
            .map(|w| if at & 2 == 0 { w >> 16 } else { w & 0xffff })
    };
    let mut out = BTreeSet::new();
    for root in roots {
        for &(length, destination) in layouts {
            let mut entries = BTreeSet::new();
            for offset_at in (length..0xffc).step_by(4) {
                let (Some(packed), Some(offset)) = (
                    half(root.0.saturating_add(offset_at)),
                    half(root.0.saturating_add(offset_at + 2)),
                ) else {
                    break;
                };
                let selector = packed >> 12;
                if selector & 1 != 0 || selector >= length - destination {
                    break;
                }
                let Some(dest) = half(root.0.saturating_add(destination + selector)) else {
                    break;
                };
                let size = ((packed & 0xfff) | 7) + 1;
                if !(0x1000..0x2000).contains(&dest)
                    || !dest.is_multiple_of(8)
                    || offset == 0
                    || !offset.is_multiple_of(8)
                    || size > 0x2000 - dest
                {
                    break;
                }
                entries.insert((offset, size, dest & 0xfff));
            }
            if entries.len() >= 2 {
                out.extend(entries);
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{BasicBlock, CodeAddress, GuestRange, RomIdentity};

    #[test]
    fn pointers_include_stored_lui_addiu_and_data_but_not_killed_values_or_holes() {
        let mut image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "synthetic".into(),
                generation: 0,
            },
            words: vec![0; 0x10000 / 4],
            rom_offset: None,
            physical_start: None,
            holes: vec![GuestRange {
                start: GuestAddr(0x8000_7000),
                size: 8,
            }],
            slots: vec![],
        };
        // Store an OSTask-like ucode pointer through an unknown task base.
        image.words[..9].copy_from_slice(&[
            0x3c08_8001,
            0x2508_8010,
            0xaca8_0010, // lui/addiu/sw -> 80008010
            0x3c09_8001,
            0x8d29_0000,
            0x2529_8020, // load kills the constant
            0x8000_8030,
            0x8000_7000,
            0x8000_8041,
        ]);
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "0".repeat(64),
            size: 0x10000,
        });
        map.blocks.insert(BasicBlock {
            start: image.base.clone(),
            size: 24,
            delay_slot_entry: false,
            evidence: BTreeSet::new(),
        });
        let found = roots(&image, &map);
        assert!(found.contains(&GuestAddr(0x8000_8010)));
        assert!(found.contains(&GuestAddr(0x8000_8030)));
        assert!(!found.contains(&GuestAddr(0x8000_8020)));
        assert!(!found.contains(&GuestAddr(0x8000_7000)));
        assert!(!found.contains(&GuestAddr(0x8000_8041)));
        // Only a rooted DMEM-sized data window may propose SDK descriptors.
        image.words[0x8040 / 4] = 0x1000;
        image.words[0x8044 / 4] = 0x016f_1000;
        image.words[0x8050 / 4] = 0x1000;
        image.words[0x8054 / 4] = 0x1000_1ff8; // transfer exceeds IMEM
        assert_eq!(
            overlay_descriptors(&image, &found),
            [(0x1000, 0x170, 0)].into()
        );
        assert!(overlay_descriptors(&image, &BTreeSet::new()).is_empty());
    }

    #[test]
    fn packed_layout_needs_the_length_selector_task_source_and_exact_dma_helper() {
        let mut words = vec![
            0x94a4_0024,
            0x0004_1b02,
            0x94a2_0026,
            0x8c28_0010,
            0x3084_0fff,
            0x0048_1021,
            0x0c00_0040,
            0x9463_0020,
            0x0060_0008,
            0,
        ];
        words.resize(32, 0);
        words.extend([0x4083_0000, 0x4082_0800, 0x4084_1000, 0x03e0_0008, 0]);
        let bytes = |w: &[u32]| w.iter().flat_map(|v| v.to_be_bytes()).collect::<Vec<_>>();
        assert_eq!(
            packed_overlay_layouts(&bytes(&words), 0x80),
            [(0x24, 0x20)].into()
        );
        for (at, bad) in [
            (1, 0x0004_1ac2),
            (2, 0x94a2_0028),
            (3, 0x8c28_0018),
            (4, 0x3084_07ff),
            (5, 0x0049_1021),
            (7, 0x9462_0020),
            (34, 0x4085_1000),
        ] {
            let mut changed = words.clone();
            changed[at] = bad;
            assert!(
                packed_overlay_layouts(&bytes(&changed), 0x80).is_empty(),
                "{at}: {bad:08x}"
            );
        }
        assert!(packed_overlay_layouts(&bytes(&words), 0).is_empty());
    }

    #[test]
    fn packed_overlays_require_rooted_complete_tables_and_bounded_destinations() {
        let mut image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x8000_0000),
                image: "synthetic".into(),
                generation: 0,
            },
            words: vec![0; 0x1100 / 4],
            rom_offset: None,
            physical_start: None,
            holes: vec![],
            slots: vec![],
        };
        // Two destinations, then three length/offset pairs. The second pair
        // selects destination byte offset two, and DMA rounds lengths up.
        image.words[8..13].copy_from_slice(&[
            0x1d00_1200,
            0x0043_0800,
            0x2080_0900,
            0x007f_0a00,
            0,
        ]);
        let roots = [image.base.pc].into();
        let layouts = [(0x24, 0x20)].into();
        let expected = [
            (0x800, 0x48, 0xd00),
            (0x900, 0x88, 0x200),
            (0xa00, 0x80, 0xd00),
        ]
        .into();
        assert_eq!(
            packed_overlay_descriptors(&image, &roots, &layouts),
            expected
        );
        let mut short = image.clone();
        short.words[10] = 0x202b_0900;
        assert_eq!(
            packed_overlay_descriptors(&short, &roots, &layouts),
            [
                (0x800, 0x48, 0xd00),
                (0x900, 0x30, 0x200),
                (0xa00, 0x80, 0xd00)
            ]
            .into()
        );
        assert!(packed_overlay_descriptors(&image, &BTreeSet::new(), &layouts).is_empty());
        for bad in [0x1080_0900, 0x4080_0900, 0x2080_0901, 0x2fff_0900] {
            let mut changed = image.clone();
            changed.words[10] = bad;
            assert!(
                packed_overlay_descriptors(&changed, &roots, &layouts).is_empty(),
                "{bad:08x}"
            );
        }
        image.holes.push(GuestRange {
            start: GuestAddr(0x8000_0028),
            size: 4,
        });
        assert!(packed_overlay_descriptors(&image, &roots, &layouts).is_empty());
        image.holes.clear();
        image.words[0x1000 / 4..0x1000 / 4 + 3].copy_from_slice(&[
            0x1d00_1200,
            0x0043_0800,
            0x2080_0900,
        ]);
        image.words[8..13].fill(0);
        assert!(packed_overlay_descriptors(&image, &roots, &layouts).is_empty());
    }

    #[test]
    fn boot_contract_follows_jumps_and_wrapped_task_offsets() {
        // A boot that jumps ahead, loads OSTask.ucode as -0x30(zero) (DMEM
        // 0xfd0 after wrapping) in a delay slot, then returns to the DMA.
        let words = [
            0x0800_0408u32, // j 0x20
            0,
            0x341f_1080, // ori ra, zero, 0x1080
            0x3401_0f7f, // ori at, zero, 0xf7f
            0x4090_0800, // mtc0 s0, SP_DRAM_ADDR
            0x409f_0000, // mtc0 ra, SP_MEM_ADDR
            0x4081_1000, // mtc0 at, SP_RD_LEN
            0x0000_000d, // break
            0x0800_0402, // j 0x08
            0x8c10_ffd0, // lw s0, -0x30(zero)
        ];
        let bytes = |w: &[u32]| w.iter().flat_map(|w| w.to_be_bytes()).collect::<Vec<_>>();
        assert_eq!(boot_ucode_size(&bytes(&words)), Some(0xf80));
        let mut changed = words;
        changed[9] = 0x8c10_ffd8; // OSTask.ucode_data is not executable ucode
        assert_eq!(boot_ucode_size(&bytes(&changed)), None);
        let mut changed = words;
        changed[8] = 0x0800_0407; // the jump never reaches the load's DMA
        assert_eq!(boot_ucode_size(&bytes(&changed)), None);
    }

    #[test]
    fn boot_contract_uses_dma_size_instead_of_task_size() {
        // Task address, LW ucode, IMEM destination, length; issue the DMA.
        let words = [
            0x2001_0fc0u32,
            0x8c22_0010,
            0x2003_0f7f,
            0x2007_1080,
            0x4087_0000,
            0x4082_0800,
            0x4083_1000,
        ];
        let bytes: Vec<_> = words.into_iter().flat_map(u32::to_be_bytes).collect();
        assert_eq!(boot_ucode_size(&bytes), Some(0xf80));
        let mut changed = words;
        changed[1] = 0x8c22_0018; // ucode_data is not executable ucode
        assert_eq!(
            boot_ucode_size(
                &changed
                    .into_iter()
                    .flat_map(u32::to_be_bytes)
                    .collect::<Vec<_>>()
            ),
            None
        );
    }

    #[test]
    fn boot_self_dma_requires_its_own_task_pointer_and_bounded_imem_bytes() {
        // Copy one doubleword from this boot's IMEM tail to its RAM prefix.
        // The replacement jumps straight to the ordinary ucode loader.
        let words = [
            0x3401_1028u32, // ori at, zero, IMEM source
            0x8c02_ffc8,    // lw v0, OSTask.ucode_boot(zero), wrapped DMEM
            0x4081_0000,    // mtc0 at, SP_MEM_ADDR
            0x4082_0800,    // mtc0 v0, SP_DRAM_ADDR
            0x4080_1800,    // mtc0 zero, SP_WR_LEN (eight bytes)
            0x0000_000d,    // break
            0,
            0,
            0,
            0,
            0x0800_0406,
            0, // replacement entry, not a CPU/ROM address
        ];
        let bytes = |w: &[u32]| w.iter().flat_map(|w| w.to_be_bytes()).collect::<Vec<_>>();
        let original = bytes(&words);
        let mut expected = original.clone();
        expected[..8].copy_from_slice(&original[0x28..0x30]);
        assert_eq!(boot_self_replacements(&original), [expected].into());
        for (at, word) in [
            (1, 0x8c02_ffd0), // a different task field
            (1, 0x8c22_ffc8), // unknown base
            (1, 0x3402_2000), // constant destination, no task provenance
            (2, 0x4080_0000), // DMEM is not this text
            (0, 0x3401_1030), // source beyond available ROM bytes
            (0, 0x3401_1ff8), // source crosses IMEM wrap
            (4, 0x4080_1000), // read DMA, not write DMA
            (4, 0x4081_1800), // length includes row/skip bits
            (2, 0x3402_2000), // overwrite the loaded pointer
        ] {
            let mut bad = words;
            bad[at] = word;
            assert!(
                boot_self_replacements(&bytes(&bad)).is_empty(),
                "{at}: {word:08x}"
            );
        }
        let mut zero = words;
        zero[1] = 0x8c00_ffc8; // a load into zero cannot supply a DMA pointer
        zero[3] = 0x4080_0800;
        assert!(boot_self_replacements(&bytes(&zero)).is_empty());
    }
}
