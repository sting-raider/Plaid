//! Candidate data pointers, not a proof of the RSP executable universe.
use crate::{GuestAddr, discovery::CodeImage, indirect::transfer, program::ProgramMap};
use std::collections::BTreeSet;

/// Collect aligned image pointers from data and constant expressions in decoded
/// CPU blocks. A pointer is only a search hint; consumers must check its bytes.
pub fn roots(image: &CodeImage, map: &ProgramMap) -> BTreeSet<GuestAddr> {
    let mut out = BTreeSet::new();
    let mut add = |value: u32| {
        let address = GuestAddr(value);
        if value.is_multiple_of(8) && image.word(address).is_some() {
            out.insert(address);
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
pub fn boot_ucode_size(bytes: &[u8]) -> Option<u32> {
    let mut state = [None; 32];
    state[0] = Some(0);
    let mut ucode = [false; 32];
    let (mut mem, mut source) = (None, false);
    for w in bytes.as_chunks::<4>().0.iter().take(64) {
        let word = u32::from_be_bytes(*w);
        let (rs, rt, rd) = (
            ((word >> 21) & 31) as usize,
            ((word >> 16) & 31) as usize,
            (word >> 11) & 31,
        );
        if word >> 26 == 16 && rs == 4 {
            match rd {
                0 => mem = state[rt],
                1 => source = ucode[rt],
                2 if source && mem == Some(0x1080) => {
                    if let Some(n) = state[rt] {
                        let n = ((n as u32 & 0xfff) | 7) + 1;
                        if n <= 0xf80 {
                            return Some(n);
                        }
                    }
                }
                _ => {}
            }
        }
        let pointer = word >> 26 == 35
            && state[rs].is_some_and(|v| (v as u32).wrapping_add(word as i16 as u32) == 0xfd0);
        if let Some(dest) = crate::discovery::decode(word, GuestAddr(0)).destination_gpr() {
            ucode[dest as usize] = pointer;
        }
        // ADDI has wrapping RSP semantics, unlike the trapping CPU form.
        let word = if word >> 26 == 8 {
            word ^ (1 << 26)
        } else {
            word
        };
        transfer(word, GuestAddr(0), &mut state);
    }
    None
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
            && size >= 128
            && size <= 0x2000 - dest
        {
            out.insert((offset, size, dest & 0xfff));
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
}
