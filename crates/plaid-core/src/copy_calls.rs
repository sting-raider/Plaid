//! Structural candidates for ROM-to-RAM copy helpers; this is not loader evidence.
use crate::{
    GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{MapIndex, prefix_state_in, transfer},
    program::{ProgramMap, RomOffset},
};
use std::collections::{BTreeMap, BTreeSet};

const MAX_IMAGE: u32 = 8 * 1024 * 1024;
const MAX_HELPER_WORDS: u32 = 128;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CopyCall {
    pub source: RomOffset,
    pub end: RomOffset,
    pub destination: GuestAddr,
    pub helper: GuestAddr,
    pub callers: BTreeSet<GuestAddr>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct Affine {
    source: i64,
    end: i64,
    destination: i64,
    constant: i64,
}

impl Affine {
    const fn input(source: i64, end: i64, destination: i64) -> Self {
        Self {
            source,
            end,
            destination,
            constant: 0,
        }
    }
    const fn constant(value: i64) -> Self {
        Self {
            source: 0,
            end: 0,
            destination: 0,
            constant: value,
        }
    }
    fn plus(self, other: Self) -> Option<Self> {
        Some(Self {
            source: self.source.checked_add(other.source)?,
            end: self.end.checked_add(other.end)?,
            destination: self.destination.checked_add(other.destination)?,
            constant: self.constant.checked_add(other.constant)?,
        })
    }
    fn minus(self, other: Self) -> Option<Self> {
        Some(Self {
            source: self.source.checked_sub(other.source)?,
            end: self.end.checked_sub(other.end)?,
            destination: self.destination.checked_sub(other.destination)?,
            constant: self.constant.checked_sub(other.constant)?,
        })
    }
}

#[derive(Debug, Clone, Copy)]
struct CopyEffect {
    target: u32,
    source: Affine,
    destination: Affine,
    length: Affine,
}

fn reg(word: u32, shift: u32) -> usize {
    ((word >> shift) & 31) as usize
}

fn value32(value: u64) -> Option<u32> {
    let low = value as u32;
    (value == u64::from(low) || value == i64::from(low as i32) as u64).then_some(low)
}

fn jal_target(word: u32, pc: GuestAddr) -> u32 {
    ((pc.0.wrapping_add(4)) & 0xf000_0000) | ((word & 0x03ff_ffff) << 2)
}

fn valid_plain(word: u32, pc: GuestAddr) -> bool {
    let instruction = decode(word, pc);
    instruction.is_valid()
        && !instruction.has_delay_slot()
        && !instruction.is_trap()
        && !matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
}

fn delay(image: &CodeImage, pc: GuestAddr) -> Option<u32> {
    let slot = GuestAddr(pc.0.checked_add(4)?);
    let word = image.instruction_word(slot)?;
    valid_plain(word, slot).then_some(word)
}

fn affine_transfer(word: u32, state: &mut [Option<Affine>; 32]) {
    let op = word >> 26;
    let rs = state[reg(word, 21)];
    let rt = state[reg(word, 16)];
    let imm = word as u16;
    let simm = i64::from(word as i16);
    let value = match op {
        15 => Some(Affine::constant(((u32::from(imm) << 16) as i32) as i64)),
        13 => rs
            .filter(|v| v.source == 0 && v.end == 0 && v.destination == 0)
            .map(|v| Affine::constant((v.constant as u32 | u32::from(imm)) as i32 as i64)),
        9 | 25 => rs.and_then(|v| v.plus(Affine::constant(simm))),
        0 => match word & 63 {
            33 | 45 => rs.zip(rt).and_then(|(a, b)| a.plus(b)),
            35 => rs.zip(rt).and_then(|(a, b)| a.minus(b)),
            37 => {
                if rs == Some(Affine::constant(0)) {
                    rt
                } else if rt == Some(Affine::constant(0)) {
                    rs
                } else {
                    None
                }
            }
            _ => None,
        },
        _ => None,
    };
    let instruction = decode(word, GuestAddr(0));
    if let Some(dest) = instruction.destination_gpr()
        && dest != 0
    {
        state[dest as usize] = value;
    }
    state[0] = Some(Affine::constant(0));
}

fn helper_copies(image: &CodeImage, helper: GuestAddr) -> Option<Vec<CopyEffect>> {
    let mut state = [None; 32];
    state[0] = Some(Affine::constant(0));
    state[4] = Some(Affine::input(1, 0, 0));
    state[5] = Some(Affine::input(0, 1, 0));
    state[6] = Some(Affine::input(0, 0, 1));
    let mut calls = Vec::new();
    let mut offset = 0;
    while offset < MAX_HELPER_WORDS * 4 {
        let pc = GuestAddr(helper.0.checked_add(offset)?);
        let word = image.instruction_word(pc)?;
        let instruction = decode(word, pc);
        if !instruction.is_valid()
            || instruction.is_trap()
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
        {
            return None;
        }
        let name = instruction.opcode_name();
        if name == "jr" && ((word >> 21) & 31) == 31 {
            delay(image, pc)?;
            return Some(calls);
        }
        if instruction.has_delay_slot() {
            let slot = delay(image, pc)?;
            affine_transfer(slot, &mut state);
            if name == "jal" {
                if let (Some(source), Some(destination), Some(length)) =
                    (state[4], state[5], state[6])
                {
                    calls.push(CopyEffect {
                        target: jal_target(word, pc),
                        source,
                        destination,
                        length,
                    });
                }
                // Structural ABI assumption: calls preserve s0-s7 only.
                for (register, value) in state.iter_mut().enumerate().skip(1) {
                    if !(16..=23).contains(&register) {
                        *value = None;
                    }
                }
                state[0] = Some(Affine::constant(0));
            } else if matches!(
                name,
                "beq" | "bne" | "beqz" | "bnez" | "blez" | "bgtz" | "bltz" | "bgez"
            ) {
                // The bounded scan follows the linear layout through conditional loops.
            } else {
                return None;
            }
            offset += 4;
        } else {
            affine_transfer(word, &mut state);
        }
        offset += 4;
    }
    None
}

fn has_chunk_remainder_shape(calls: &[CopyEffect]) -> bool {
    calls.iter().enumerate().any(|(i, first)| {
        let chunk = first.length.constant;
        if first.length.source != 0
            || first.length.end != 0
            || first.length.destination != 0
            || chunk <= 0
            || chunk > i64::from(MAX_IMAGE)
            || chunk % 4 != 0
            || first.source.source != 1
            || first.source.end != 0
            || first.source.destination != 0
            || first.destination.source != 0
            || first.destination.end != 0
            || first.destination.destination != 1
            || first.source.constant < 0
            || first.source.constant % 4 != 0
            || first.source.constant != first.destination.constant
        {
            return false;
        }
        let Some(next) = first.source.constant.checked_add(chunk) else {
            return false;
        };
        let Some(negative_next) = next.checked_neg() else {
            return false;
        };
        calls.iter().skip(i + 1).any(|second| {
            first.target == second.target
                && second.source.source == 1
                && second.source.end == 0
                && second.source.destination == 0
                && second.source.constant == next
                && second.destination.source == 0
                && second.destination.end == 0
                && second.destination.destination == 1
                && second.destination.constant == next
                && second.length.source == -1
                && second.length.end == 1
                && second.length.destination == 0
                && second.length.constant == negative_next
        })
    })
}

pub(crate) fn helper_shape(image: &CodeImage, entry: GuestAddr) -> bool {
    helper_copies(image, entry).is_some_and(|calls| has_chunk_remainder_shape(&calls))
}

#[derive(Debug, Clone)]
struct Wrapper {
    source: u32,
    end: u32,
    destination: GuestAddr,
    helper: GuestAddr,
    caller: GuestAddr,
}

fn wrappers(rom: &[u8], map: &ProgramMap, image: &CodeImage) -> Vec<Wrapper> {
    let index = MapIndex::new(map);
    let mut out = Vec::new();
    for block in &map.blocks {
        if block.start.image != image.base.image || block.start.generation != image.base.generation
        {
            continue;
        }
        let Some(block_end) = block.start.pc.0.checked_add(block.size) else {
            continue;
        };
        for pc_raw in (block.start.pc.0..block_end).step_by(4) {
            let pc = GuestAddr(pc_raw);
            let Some(word) = image.instruction_word(pc) else {
                continue;
            };
            if decode(word, pc).opcode_name() != "jal" {
                continue;
            }
            let Some(helper_delay) = delay(image, pc) else {
                continue;
            };
            let helper = jal_target(word, pc);
            let helper_pc = GuestAddr(helper);
            if image.instruction_word(helper_pc).is_none() {
                continue;
            }
            let Some(next_pc) = pc_raw.checked_add(8).map(GuestAddr) else {
                continue;
            };
            let Some(next_word) = image.instruction_word(next_pc) else {
                continue;
            };
            if decode(next_word, next_pc).opcode_name() != "jal" || delay(image, next_pc).is_none()
            {
                continue;
            }
            let site = image.address(pc);
            let Some((_, mut state, _)) = prefix_state_in(&index, image, &site) else {
                continue;
            };
            transfer(helper_delay, GuestAddr(pc_raw + 4), &mut state);
            let (Some(source_value), Some(end_value), Some(destination_value)) =
                (state[4], state[5], state[6])
            else {
                continue;
            };
            let (Some(source), Some(end), Some(destination)) = (
                value32(source_value),
                value32(end_value),
                value32(destination_value),
            ) else {
                continue;
            };
            if jal_target(next_word, next_pc) != destination {
                continue;
            }
            let len = end.checked_sub(source);
            let Some(len) = len else {
                continue;
            };
            if len == 0
                || len > MAX_IMAGE
                || !source.is_multiple_of(16)
                || !end.is_multiple_of(16)
                || source as usize > rom.len()
                || end as usize > rom.len()
                || !(0x8000_0000..0x8080_0000).contains(&destination)
                || !destination.is_multiple_of(4)
                || u64::from(destination) + u64::from(len) > 0x8080_0000
            {
                continue;
            }
            out.push(Wrapper {
                source,
                end,
                destination: GuestAddr(destination),
                helper: helper_pc,
                caller: pc,
            });
        }
    }
    out
}

/// Return repeated, adjacent ROM-range wrapper candidates. This does not prove
/// that any wrapper ran or that its byte bindings are live at runtime.
pub fn infer(rom: &[u8], map: &ProgramMap, image: &CodeImage) -> Vec<CopyCall> {
    let mut grouped = BTreeMap::<(u32, GuestAddr), Vec<Wrapper>>::new();
    for wrapper in wrappers(rom, map, image) {
        grouped
            .entry((wrapper.helper.0, wrapper.destination))
            .or_default()
            .push(wrapper);
    }
    let mut output = Vec::new();
    for ((helper, destination), entries) in &grouped {
        if entries
            .iter()
            .map(|w| w.caller)
            .collect::<BTreeSet<_>>()
            .len()
            < 2
        {
            continue;
        }
        if !helper_shape(image, GuestAddr(*helper)) {
            continue;
        }
        let mut accepted = BTreeMap::<(u32, u32), BTreeSet<GuestAddr>>::new();
        for wrapper in entries {
            accepted
                .entry((wrapper.source, wrapper.end))
                .or_default()
                .insert(wrapper.caller);
        }
        let ranges: Vec<_> = accepted.keys().copied().collect();
        for &(source, end) in &ranges {
            if ranges
                .iter()
                .any(|&(other_source, other_end)| end == other_source || other_end == source)
            {
                output.push(CopyCall {
                    source: RomOffset(u64::from(source)),
                    end: RomOffset(u64::from(end)),
                    destination: *destination,
                    helper: GuestAddr(*helper),
                    callers: accepted[&(source, end)].clone(),
                });
            }
        }
    }
    output.sort_by_key(|call| (call.source, call.end, call.destination, call.helper));
    output.dedup();
    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::program::{BasicBlock, CodeAddress, RomIdentity};

    const BASE: u32 = 0x8000_0000;
    const HELPER: u32 = 0x8000_0100;
    const CALLEE: u32 = 0x8000_0500;
    const DEST: u32 = 0x8000_4000;

    fn i(op: u32, rs: u32, rt: u32, imm: i16) -> u32 {
        op << 26 | rs << 21 | rt << 16 | imm as u16 as u32
    }
    fn r(rs: u32, rt: u32, rd: u32, funct: u32) -> u32 {
        rs << 21 | rt << 16 | rd << 11 | funct
    }
    fn jal(target: u32) -> u32 {
        3 << 26 | ((target >> 2) & 0x03ff_ffff)
    }
    fn lui(reg: u32, value: u16) -> u32 {
        i(15, 0, reg, value as i16)
    }
    fn ori(reg: u32, value: u16) -> u32 {
        i(13, 0, reg, value as i16)
    }

    struct Fixture {
        rom: Vec<u8>,
        map: ProgramMap,
        image: CodeImage,
    }

    fn fixture(base: u32) -> Fixture {
        let mut words = vec![0; 240];
        for (start, source) in [(0usize, 0x100u16), (10, 0x120u16)] {
            words[start] = lui(4, 0);
            words[start + 1] = ori(4, source);
            words[start + 2] = lui(5, 0);
            words[start + 3] = ori(5, source + 0x20);
            words[start + 4] = lui(6, 0x8000);
            words[start + 5] = jal(base + 0x100);
            words[start + 6] = i(13, 6, 6, 0x4000);
            words[start + 7] = jal(DEST);
            words[start + 8] = 0;
        }
        let h = (HELPER - BASE) as usize / 4;
        words[h] = r(4, 0, 16, 33); // preserve source
        words[h + 1] = r(6, 0, 17, 33); // preserve destination
        words[h + 2] = r(5, 4, 18, 35); // remaining length
        words[h + 3] = r(16, 0, 4, 33);
        words[h + 4] = r(17, 0, 5, 33);
        words[h + 5] = i(9, 0, 6, 32);
        words[h + 6] = jal(CALLEE);
        words[h + 7] = 0;
        words[h + 8] = i(9, 16, 4, 32);
        words[h + 9] = i(9, 17, 5, 32);
        words[h + 10] = i(9, 18, 6, -32);
        words[h + 11] = jal(CALLEE);
        words[h + 12] = 0;
        words[h + 13] = r(31, 0, 0, 8);
        words[h + 14] = 0;
        words.copy_within(h + 3..h + 15, h + 6);
        words[h + 3] = i(35, 29, 6, 0); // unknown a2 before unrelated cache call
        words[h + 4] = jal(0x8000_6000);
        words[h + 5] = 0;
        words[h + 16] = 0;
        words[h + 17] = 0;
        words[h + 16] = i(5, 16, 0, -2); // conditional loop branch (bnez)
        words[h + 40] = r(31, 0, 0, 8);
        words[h + 41] = 0;

        let id = "synthetic-copy-call-image".to_owned();
        let image = CodeImage {
            base: CodeAddress {
                pc: GuestAddr(base),
                image: id.clone(),
                generation: 1,
            },
            words,
            rom_offset: Some(RomOffset(0)),
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "0".repeat(64),
            size: 64,
        });
        for start in [0u32, 40] {
            map.blocks.insert(BasicBlock {
                start: CodeAddress {
                    pc: GuestAddr(base + start),
                    image: id.clone(),
                    generation: 1,
                },
                size: 36,
                delay_slot_entry: false,
                evidence: BTreeSet::new(),
            });
        }
        Fixture {
            rom: vec![0; 0x200],
            map,
            image,
        }
    }

    #[test]
    fn finds_two_adjacent_wrapper_ranges_with_a_symbolic_chunk_and_remainder() {
        let f = fixture(BASE);
        let calls = infer(&f.rom, &f.map, &f.image);
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0].source, RomOffset(0x100));
        assert_eq!(calls[0].end, RomOffset(0x120));
        assert_eq!(calls[0].helper, GuestAddr(HELPER));
        assert_eq!(calls[0].callers.len(), 1);
        assert_eq!(calls[1].source, RomOffset(0x120));
    }

    #[test]
    fn address_shift_preserves_the_inferred_structure() {
        let f = fixture(0x8010_0000);
        let calls = infer(&f.rom, &f.map, &f.image);
        assert_eq!(calls.len(), 2);
        assert_eq!(calls[0].helper, GuestAddr(0x8010_0100));
    }

    #[test]
    fn rejects_nonadjacent_ranges_and_a_single_wrapper() {
        let mut f = fixture(BASE);
        f.image.words[11] = ori(4, 0x130);
        f.image.words[13] = ori(5, 0x150);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
        f = fixture(BASE);
        f.map.blocks.pop_last();
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_bad_helper_dataflow_and_length_arithmetic() {
        let mut f = fixture(BASE);
        let helper = (HELPER - BASE) as usize / 4;
        f.image.words[helper + 1] = r(4, 0, 17, 33); // destination copied from source
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
        f = fixture(BASE);
        f.image.words[helper + 2] = r(5, 4, 18, 33); // length is not End - Source
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_invalid_delays_and_out_of_rom_ranges() {
        let mut f = fixture(BASE);
        f.image.words[6] = jal(DEST);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
        f = fixture(BASE);
        f.image.words[3] = ori(5, 0x300);
        f.image.words[13] = ori(5, 0x320);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_wrapper_call_to_a_different_destination() {
        let mut f = fixture(BASE);
        f.image.words[7] = jal(DEST + 4);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn rejects_missing_helper_bytes_and_different_downstream_targets() {
        let mut f = fixture(BASE);
        f.image.holes.push(crate::program::GuestRange {
            start: GuestAddr(HELPER),
            size: 4,
        });
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
        f = fixture(BASE);
        let helper = (HELPER - BASE) as usize / 4;
        f.image.words[helper + 14] = jal(DEST);
        assert!(infer(&f.rom, &f.map, &f.image).is_empty());
    }

    #[test]
    fn helper_scan_has_a_128_word_bound() {
        let mut f = fixture(BASE);
        let helper = (HELPER - BASE) as usize / 4;
        f.image.words[helper + 40] = 0;
        f.image.words[helper + 128] = r(31, 0, 0, 8);
        assert!(!helper_shape(&f.image, GuestAddr(HELPER)));
    }

    #[test]
    fn rejects_unconditional_control_transfers_in_linear_scan() {
        let mut f = fixture(BASE);
        let helper = (HELPER - BASE) as usize / 4;
        f.image.words[helper + 16] = i(4, 0, 0, 1); // always-taken beq zero,zero
        assert!(!helper_shape(&f.image, GuestAddr(HELPER)));
        f = fixture(BASE);
        f.image.words[helper + 16] = 2 << 26; // j
        assert!(!helper_shape(&f.image, GuestAddr(HELPER)));
    }
}
