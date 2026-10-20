//! Speculative discovery roots, never indirect-target certificates. PI reads
//! can observe a pending-write latch; assuming ROM content only widens roots.
use crate::{
    GuestAddr,
    data_roots::plausible_at,
    discovery::{CodeImage, decode},
    indirect::{code_pointer, signed_word, transfer},
    program::ProgramMap,
};
use std::collections::{BTreeMap, BTreeSet, HashMap};

/// Bounded lexical expressions in already decoded code. Branches may skip
/// definitions, so even a fully known expression supplies no closure proof.
pub(crate) fn scan(
    rom: &[u8],
    image: &CodeImage,
    map: &ProgramMap,
    starts: &BTreeSet<u32>,
) -> BTreeMap<GuestAddr, GuestAddr> {
    let words: HashMap<_, _> = map
        .blocks
        .iter()
        .filter(|b| {
            b.start.image == image.base.image
                && b.start.generation == image.base.generation
                && !b.delay_slot_entry
        })
        .flat_map(|b| (0..b.size / 4).map(move |n| GuestAddr(b.start.pc.0 + n * 4)))
        .filter_map(|pc| image.instruction_word(pc).map(|w| (pc, w)))
        .collect();
    let mut roots = BTreeMap::new();
    // Only seed near an uncached-cartridge LUI; scanning every ordinary
    // address construction repeatedly made unchanged control ROMs slower.
    let seeds: BTreeSet<_> = words
        .iter()
        .filter(|(_, word)| **word >> 26 == 15 && (0xb000..0xbfc0).contains(&(**word & 0xffff)))
        .flat_map(|(pc, _)| (0..64).filter_map(move |n| pc.0.checked_sub(n * 4).map(GuestAddr)))
        .filter(|pc| words.get(pc).is_some_and(|w| w >> 26 == 15))
        .collect();
    for start in seeds {
        let mut values = [None; 32];
        values[0] = Some(0);
        let mut from_rom = [false; 32];
        for n in 0..64 {
            let Some(pc) = start.0.checked_add(n * 4).map(GuestAddr) else {
                break;
            };
            let Some(&word) = words.get(&pc) else {
                break;
            };
            let instruction = decode(word, pc);
            if matches!(instruction.opcode_name(), "jr" | "jalr") {
                if from_rom[instruction.get_rs() as usize]
                    && let Some(target) =
                        values[instruction.get_rs() as usize].and_then(code_pointer)
                {
                    for target in image.slot_copies(image.slot_view(pc, target)) {
                        let target = GuestAddr(target);
                        if plausible_at(image, target, starts) {
                            roots.entry(target).or_insert(start);
                        }
                    }
                }
                break;
            }
            if !instruction.is_valid()
                || instruction.does_link()
                || instruction.is_trap()
                || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
            {
                break;
            }
            let base = values[((word >> 21) & 31) as usize];
            let rs = ((word >> 21) & 31) as usize;
            let rt = ((word >> 16) & 31) as usize;
            if let Some(dest) = instruction.destination_gpr()
                && dest != 0
            {
                from_rom[dest as usize] = match word >> 26 {
                    0 => from_rom[rs] || from_rom[rt],
                    9 | 12 | 13 | 14 | 25 => from_rom[rs],
                    _ => false,
                };
            }
            transfer(word, pc, &mut values);
            // Only uncached cartridge words are speculative ROM constants.
            if word >> 26 == 35
                && let Some(base) = base
            {
                let address = base.wrapping_add(word as i16 as i64 as u64);
                if let Some(address) = code_pointer(address)
                    && (0xb0000000..0xbfc00000).contains(&address)
                    && let Some(data) = rom.get((address - 0xb0000000) as usize..)
                    && let Some(data) = data.get(..4)
                {
                    let rt = ((word >> 16) & 31) as usize;
                    if rt != 0 {
                        values[rt] =
                            Some(signed_word(u32::from_be_bytes(data.try_into().unwrap())));
                        from_rom[rt] = true;
                    }
                }
            }
        }
    }
    roots
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        data_roots::discover_address_taken,
        program::{CodeAddress, PhysicalAddr, RomIdentity, RomOffset},
        solver::{self, Scope},
    };

    fn fixture(base: u16, offset: u16, clobber: bool) -> (CodeImage, Vec<u8>, ProgramMap) {
        let mut words = vec![0; 128];
        words[..12].copy_from_slice(&[
            0x3c048000,
            0x348400dc, // pointer before the ROM-dependent adjustment
            0x3c051357,
            0x34a52468,
            0x3c060000 | u32::from(base),
            0x8cc20000 | u32::from(offset),
            if clobber { 0x00001021 } else { 0x00000000 },
            0x00a22823,
            0x00852021, // subu a1,a1,v0; addu a0,a0,a1
            0x0080f809,
            0,
            0x0800000b,
        ]);
        words[32] = 0x13572444;
        words[62] = 0x03e00008; // layout witness for the otherwise unnamed function
        words[64..69]
            .copy_from_slice(&[0x27bdfff0, 0xafbf000c, 0x8fbf000c, 0x03e00008, 0x27bd0010]);
        let bytes: Vec<u8> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(0x80000000),
                image: "rom-expression".into(),
                generation: 0,
            },
            words,
            rom_offset: Some(RomOffset(64)),
            physical_start: Some(PhysicalAddr(0)),
            holes: vec![],
            slots: vec![],
        };
        let map = discover_address_taken(
            RomIdentity {
                sha256: "a".repeat(64),
                size: 4096,
            },
            &bytes,
            &image,
            &[image.base.pc],
            &[],
            None,
            &Default::default(),
            1000,
        )
        .unwrap()
        .map;
        (image, bytes, map)
    }

    #[test]
    fn rom_word_expression_discovers_a_root_without_a_target_certificate() {
        let (image, bytes, map) = fixture(0xb000, 0x80, false);
        let target = image.address(GuestAddr(0x80000100));
        assert!(map.address_taken.contains_key(&target));
        assert!(map.blocks.iter().any(|b| b.start == target));
        let site = map
            .indirect_sites
            .iter()
            .find(|s| s.site.pc == GuestAddr(0x80000024))
            .unwrap();
        assert!(
            site.closed_proof.is_none(),
            "a speculative ROM read cannot certify a PI target"
        );
        assert!(
            solver::solve(&map, std::slice::from_ref(&image), Scope::WholeRom)
                .unwrap()
                .blockers
                .iter()
                .any(|b| b.kind == "unresolved_indirect_site")
        );
        assert!(scan(&bytes[..0x80], &image, &map, &Default::default()).is_empty());
    }

    #[test]
    fn ram_misalignment_and_clobbers_do_not_supply_rom_roots() {
        for (base, offset, clobber) in [
            (0xa000, 0x80, false),
            (0xb000, 0x82, false),
            (0xb000, 0x80, true),
        ] {
            let (image, bytes, map) = fixture(base, offset, clobber);
            assert!(
                !map.address_taken
                    .contains_key(&image.address(GuestAddr(0x80000100)))
            );
            assert!(scan(&bytes, &image, &map, &Default::default()).is_empty());
        }
    }

    #[test]
    fn unrelated_rom_read_does_not_taint_a_redefined_target() {
        let (mut image, bytes, map) = fixture(0xb000, 0x80, false);
        image.words[7] = 0x3c048000;
        image.words[8] = 0x34840100;
        assert!(scan(&bytes, &image, &map, &Default::default()).is_empty());
    }
}
