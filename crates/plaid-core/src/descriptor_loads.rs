//! Code-built PI load descriptors (ADR-0264).
//! These are source/placement candidates, never executable-layout or lifetime proofs.
use crate::{GuestAddr, discovery::decode};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DescriptorLoad {
    pub source: u32,
    pub destination: u32,
    pub size: u32,
    /// Byte offset of the completing store in the supplied image.
    pub built_at: u32,
}

/// Recognize a straight-line descriptor construction: PI source, RAM, size,
/// and RAM end, at relative field offsets 0, 0x20, 0x40, 0x64. The descriptor
/// may start at any offset of any base register. Constants and stores never
/// propagate across a control transfer or a rewrite of their base register.
pub fn infer(rom: &[u8], image: &[u8]) -> Vec<DescriptorLoad> {
    let mut registers = [None; 32];
    registers[0] = Some(0u32);
    let mut stores: BTreeMap<(u32, i32), (u32, usize)> = BTreeMap::new();
    let mut found = BTreeMap::new();
    for (index, bytes) in image.as_chunks::<4>().0.iter().enumerate() {
        let w = u32::from_be_bytes(*bytes);
        let i = decode(w, GuestAddr(0));
        if !i.is_valid()
            || i.is_branch()
            || i.is_jump()
            || i.is_trap()
            || matches!(i.opcode_name(), "eret" | "syscall" | "break")
        {
            registers.fill(None);
            registers[0] = Some(0);
            stores.clear();
            continue;
        }
        stores.retain(|_, (_, at)| index - *at <= 64);
        let (op, rs, rt) = (w >> 26, (w >> 21 & 31) as usize, (w >> 16 & 31) as usize);
        let low = w as u16;
        if op == 43 {
            let offset = i32::from(low as i16);
            let key = (rs as u32, offset);
            // Another unknown base may alias any field already recorded.
            stores
                .retain(|&(base, previous), _| base == rs as u32 && previous.abs_diff(offset) >= 4);
            if let Some(value) = registers[rt] {
                stores.insert(key, (value, index));
                let fields = [0x64, 0x44, 0x24]
                    .map(|delta| stores.get(&(rs as u32, offset - delta)).copied());
                if let [Some((pi, a)), Some((ram, b)), Some((size, c))] = fields
                    && a < b
                    && b < c
                    && c < index
                    && pi & 0xf000_0000 == 0xb000_0000
                    && (0x8000_0000..0x8080_0000).contains(&ram)
                    && size > 0
                    && size.is_multiple_of(4)
                    && ram.is_multiple_of(4)
                    && ram.checked_add(size) == Some(value)
                    && value <= 0x8080_0000
                {
                    let source = pi & 0x0fff_ffff;
                    if source.is_multiple_of(4)
                        && source
                            .checked_add(size)
                            .is_some_and(|end| end as usize <= rom.len())
                    {
                        found.entry((source, ram, size)).or_insert(DescriptorLoad {
                            source,
                            destination: ram,
                            size,
                            built_at: 4 * index as u32,
                        });
                    }
                }
            }
        } else if matches!(op, 40..=46 | 56..=63) {
            // An unmodeled store may overlap a descriptor field.
            stores.clear();
        }
        let value = match op {
            15 => Some(u32::from(low) << 16),
            9 => registers[rs].map(|v| v.wrapping_add(low as i16 as u32)),
            13 => registers[rs].map(|v| v | u32::from(low)),
            0 if matches!(w & 63, 33 | 37) => registers[rs].zip(registers[rt]).map(|(a, b)| {
                if w & 63 == 33 {
                    a.wrapping_add(b)
                } else {
                    a | b
                }
            }),
            _ => None,
        };
        if let Some(destination) = i.destination_gpr().filter(|&r| r != 0) {
            registers[destination as usize] = value;
            stores.retain(|&(base, _), _| base != destination);
        }
    }
    found.into_values().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn descriptor(end: u32) -> Vec<u32> {
        let mut words = Vec::new();
        for (value, offset) in [
            (0xb000_0200u32, 0x10),
            (0x8004_0000, 0x30),
            (0x80, 0x50),
            (end, 0x74),
        ] {
            words.extend([
                0x3c08_0000 | value >> 16,
                0x3508_0000 | value & 0xffff,
                0xafa8_0000 | offset,
            ]);
        }
        words
    }
    fn run(words: &[u32]) -> Vec<DescriptorLoad> {
        infer(
            &vec![0; 0x400],
            &words
                .iter()
                .flat_map(|w| w.to_be_bytes())
                .collect::<Vec<_>>(),
        )
    }
    #[test]
    fn descriptor_constants_name_bounded_raw_loads() {
        let words = descriptor(0x8004_0080);
        assert_eq!(
            run(&words),
            [DescriptorLoad {
                source: 0x200,
                destination: 0x8004_0000,
                size: 0x80,
                built_at: 44
            }]
        );
        // Neither the stack register nor the absolute descriptor offset is special.
        let moved: Vec<_> = words
            .iter()
            .map(|&w| {
                if w >> 26 == 43 {
                    (w & !(31 << 21)) | (16 << 21) | 0x100
                } else {
                    w
                }
            })
            .collect();
        assert_eq!(run(&moved), run(&words));
    }
    #[test]
    fn descriptor_rejects_inconsistent_end_and_out_of_cartridge_source() {
        assert!(run(&descriptor(0x8004_0084)).is_empty());
        let mut words = descriptor(0x8004_0080);
        words[1] = 0x3508_03c0;
        assert!(run(&words).is_empty());
    }

    #[test]
    fn descriptor_rejects_unaligned_zero_and_out_of_ram_ranges() {
        for (field, value) in [
            (0, 0xa000_0200), // not an uncached cartridge alias
            (0, 0xb000_0201),
            (1, 0x8004_0001),
            (1, 0x807f_fffc), // end exceeds RDRAM
            (2, 0),
            (2, 0x81),
        ] {
            let mut words = descriptor(0x8004_0080);
            // Keep end consistent so each range guard is independently exercised.
            let ram = if field == 1 { value } else { 0x8004_0000 };
            let size = if field == 2 { value } else { 0x80 };
            for (k, v) in [(field * 3, value), (9, ram + size)] {
                words[k] = 0x3c08_0000 | v >> 16;
                words[k + 1] = 0x3508_0000 | v & 0xffff;
            }
            assert!(run(&words).is_empty(), "field {field}: {value:08x}");
        }
    }
    #[test]
    fn descriptor_does_not_join_paths_or_rewritten_values_and_bases() {
        for replacement in [
            0x0800_0040,
            0x1000_0000,
            0x03e0_0008,
            0x4200_0018, // ERET
            0x0000_000c, // SYSCALL
            0x0000_000d, // BREAK
            0x8fa8_0000,
            0x27bd_0010,
        ] {
            let mut words = descriptor(0x8004_0080);
            words.insert(5, replacement);
            assert!(run(&words).is_empty(), "{replacement:08x}");
        }
        let mut words = descriptor(0x8004_0080);
        words.insert(9, 0xafa9_0050); // unknown overwrite of the size field
        assert!(run(&words).is_empty());
        for store in [0xae09_0000, 0xa3a9_0051, 0xafa9_0051] {
            let mut words = descriptor(0x8004_0080);
            words.insert(9, store); // possible alias or partial field overwrite
            assert!(run(&words).is_empty());
        }
        let mut words = descriptor(0x8004_0080);
        words.splice(9..9, [0; 65]);
        assert!(run(&words).is_empty());
    }

    #[test]
    fn descriptor_accepts_signed_low_halves_and_computed_end() {
        let mut words = descriptor(0x8004_0080);
        // RAM = LUI 8004; ADDIU -8000 = 80038000, end = RAM + size.
        words[4] = 0x2508_8000;
        words.splice(9..11, [0x3c09_8004, 0x2529_8000, 0x2528_0080]);
        let found = run(&words);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].destination, 0x8003_8000);
        // The optional descriptor tail does not change the named byte range.
        words.push(0xafa0_0078);
        assert_eq!(run(&words), found);
    }

    #[test]
    fn descriptor_catalog_composes_content_bound_slot_text_and_data() {
        use crate::{
            declared_loads::{self, LoadImage},
            program::{GuestRange, RomOffset},
        };
        let mut rom = vec![0; 0x400];
        // Return, delay, then invalid data: the same boundary heuristic as raw slots.
        rom[0x200..0x204].copy_from_slice(&0x03e0_0008u32.to_be_bytes());
        rom[0x208..0x20c].copy_from_slice(&0xffff_ffffu32.to_be_bytes());
        let image: Vec<_> = descriptor(0x8004_0080)
            .iter()
            .flat_map(|w| w.to_be_bytes())
            .collect();
        let catalog = crate::overlays::discover(&rom, &image).unwrap();
        assert_eq!(catalog.len(), 1);
        assert_eq!(catalog[0].layout.text, 8);
        let loads = crate::overlays::loads(&catalog, &Default::default(), 0x8080_0000);
        assert_eq!(loads.len(), 1);
        assert_eq!(loads[0].linked, Some(GuestAddr(0x8004_0000)));
        let spec = LoadImage {
            base_offset: RomOffset(0),
            base: GuestRange {
                start: GuestAddr(0x8000_0000),
                size: 4,
            },
            loads,
        };
        let (_, composed) = declared_loads::compose(&rom, &spec).unwrap();
        let placed = spec.loads[0].destination.start;
        assert_eq!(composed.instruction_word(placed), Some(0x03e0_0008));
        assert_eq!(composed.instruction_word(GuestAddr(placed.0 + 8)), None);
        assert!(declared_loads::verify_slots(&composed, Some(&spec)));
    }
}
