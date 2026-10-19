//! Bounded compile-time proofs about ordinary callee register effects.
use crate::{
    GuestAddr,
    discovery::{CodeImage, decode},
    indirect::MapIndex,
};
use std::collections::{BTreeMap, BTreeSet};

const MAX_CALL_DEPTH: usize = 8;
const MAX_WORD_READS: usize = 4096;

pub(crate) struct NoWrite {
    pub words: BTreeMap<u32, u32>,
    pub reads: usize,
}

/// Prove that every normally traversed path from `entry` leaves `register`
/// unchanged, returning all instruction words read by placed guest PC and the
/// number of reads (including repeated nested-callee reads).
///
/// This only proves a GPR effect on normal checked returns. It does not prove
/// memory, timing, return-target, or whole-program control-flow closure.
pub(crate) fn no_gpr_write(
    index: &MapIndex<'_>,
    image: &CodeImage,
    entry: GuestAddr,
    register: u8,
    budget: usize,
) -> Option<NoWrite> {
    if !(1..=30).contains(&register) || !entry.0.is_multiple_of(4) {
        return None;
    }
    let mut proof = Proof {
        index,
        image,
        register,
        limit: budget.min(MAX_WORD_READS),
        reads: 0,
        words: BTreeMap::new(),
        active_calls: BTreeSet::new(),
    };
    proof.function(entry, 0).then_some(NoWrite {
        words: proof.words,
        reads: proof.reads,
    })
}

struct Proof<'a, 'm> {
    index: &'a MapIndex<'m>,
    image: &'a CodeImage,
    register: u8,
    limit: usize,
    reads: usize,
    words: BTreeMap<u32, u32>,
    active_calls: BTreeSet<u32>,
}

impl Proof<'_, '_> {
    fn normal_block(&self, pc: GuestAddr, require_start: bool) -> bool {
        let blocks: Vec<_> = self
            .index
            .containing(&self.image.address(pc))
            .into_iter()
            .filter(|block| !block.delay_slot_entry)
            .collect();
        blocks.len() == 1 && (!require_start || blocks[0].start.pc == pc)
    }

    fn read(&mut self, pc: GuestAddr) -> Option<u32> {
        if self.reads >= self.limit {
            return None;
        }
        self.reads += 1;
        if !pc.0.is_multiple_of(4)
            || self
                .image
                .slots
                .iter()
                .any(|(placed, _, _)| placed.contains(pc))
            || !self.normal_block(pc, false)
        {
            return None;
        }
        let word = self.image.instruction_word(pc)?;
        let instruction = decode(word, pc);
        let opcode = word >> 26;
        if !instruction.is_valid()
            || instruction.is_trap()
            || crate::discovery::is_conditional_trap(word)
            || matches!(instruction.opcode_name(), "syscall" | "break" | "eret")
            || matches!(opcode, 18 | 19)
            || instruction.destination_gpr() == Some(u32::from(self.register))
        {
            return None;
        }
        self.words.insert(pc.0, word);
        Some(word)
    }

    fn delay(&mut self, pc: GuestAddr) -> Option<()> {
        let slot = GuestAddr(pc.0.checked_add(4)?);
        let word = self.read(slot)?;
        let instruction = decode(word, slot);
        if instruction.has_delay_slot()
            || instruction.is_branch()
            || instruction.is_jump()
            || instruction.is_jump_with_address()
        {
            return None;
        }
        Some(())
    }

    fn target(&self, pc: GuestAddr) -> Option<()> {
        self.normal_block(pc, true).then_some(())
    }

    fn function(&mut self, entry: GuestAddr, depth: usize) -> bool {
        if depth > MAX_CALL_DEPTH
            || !self.target(entry).is_some()
            || !self.active_calls.insert(entry.0)
        {
            return false;
        }
        let result = self.function_body(entry, depth);
        self.active_calls.remove(&entry.0);
        result
    }

    fn function_body(&mut self, entry: GuestAddr, depth: usize) -> bool {
        let mut pending = BTreeSet::from([entry.0]);
        let mut visited = BTreeSet::new();
        let mut has_return = false;

        while let Some(raw_pc) = pending.pop_first() {
            if !visited.insert(raw_pc) {
                continue;
            }
            let pc = GuestAddr(raw_pc);
            let Some(word) = self.read(pc) else {
                return false;
            };
            let instruction = decode(word, pc);
            let opcode = word >> 26;

            if instruction.is_branch() {
                if instruction.does_link() {
                    return false;
                }
                if self.delay(pc).is_none() {
                    return false;
                }
                let offset = i32::from(word as u16 as i16).wrapping_mul(4) as u32;
                let target = GuestAddr(pc.0.wrapping_add(4).wrapping_add(offset));
                if self.target(target).is_none() {
                    return false;
                }
                pending.insert(target.0);
                if !instruction.is_unconditional_branch() {
                    let Some(next) = pc.0.checked_add(8) else {
                        return false;
                    };
                    if self.target(GuestAddr(next)).is_none() {
                        return false;
                    }
                    pending.insert(next);
                }
                continue;
            }

            if instruction.is_jump_with_address() {
                if !matches!(opcode, 2 | 3)
                    || instruction.does_link() != (opcode == 3)
                    || self.delay(pc).is_none()
                {
                    return false;
                }
                let target = self.image.jump_target(pc, word);
                if self.target(target).is_none() {
                    return false;
                }
                if opcode == 3 {
                    if depth == MAX_CALL_DEPTH || !self.function(target, depth + 1) {
                        return false;
                    }
                    let Some(next) = pc.0.checked_add(8) else {
                        return false;
                    };
                    if self.target(GuestAddr(next)).is_none() {
                        return false;
                    }
                    pending.insert(next);
                } else {
                    pending.insert(target.0);
                }
                continue;
            }

            if instruction.is_jump() || instruction.has_delay_slot() {
                if word == 0x03e0_0008 {
                    if self.delay(pc).is_none() {
                        return false;
                    }
                    has_return = true;
                    continue;
                }
                return false;
            }

            let Some(next) = pc.0.checked_add(4) else {
                return false;
            };
            pending.insert(next);
        }

        has_return
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        EvidenceKind, GuestAddr,
        discovery::CodeImage,
        indirect::MapIndex,
        program::{BasicBlock, CodeAddress, EvidenceRefs, ProgramMap, RomIdentity},
    };

    const BASE: u32 = 0x8000_1000;

    fn image(words: Vec<u32>) -> CodeImage {
        CodeImage {
            base: CodeAddress {
                pc: GuestAddr(BASE),
                image: "callee-effects-test".into(),
                generation: 3,
            },
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        }
    }

    fn proof(words: Vec<u32>) -> (ProgramMap, CodeImage) {
        let image = image(words);
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "0".repeat(64),
            size: 64,
        });
        map.evidence.insert(
            "synthetic-callee".into(),
            crate::program::Evidence {
                kind: EvidenceKind::TestOracle,
                producer: "callee-effects-test".into(),
                revision: "0".into(),
                detail: "authored instruction words and decoded map blocks".into(),
            },
        );
        let evidence: EvidenceRefs = ["synthetic-callee".into()].into();
        for offset in 0..image.words.len() {
            map.blocks.insert(BasicBlock {
                start: image.address(GuestAddr(BASE + offset as u32 * 4)),
                size: 4,
                delay_slot_entry: false,
                evidence: evidence.clone(),
            });
        }
        (map, image)
    }

    fn addiu(register: u8) -> u32 {
        (9 << 26) | (u32::from(register) << 16) | 1
    }

    fn jal(word_index: usize) -> u32 {
        (3 << 26) | (((BASE + word_index as u32 * 4) >> 2) & 0x03ff_ffff)
    }

    fn beq(offset_words: i16) -> u32 {
        (4 << 26) | (1 << 16) | offset_words as u16 as u32
    }

    fn prove(words: Vec<u32>, register: u8) -> Option<BTreeMap<u32, u32>> {
        let (map, image) = proof(words);
        no_gpr_write(
            &MapIndex::new(&map),
            &image,
            GuestAddr(BASE),
            register,
            MAX_WORD_READS,
        )
        .map(|proof| proof.words)
    }

    #[test]
    fn leaf_preserves_register_while_writing_others_and_storing_memory() {
        let words = vec![addiu(9), 0xac22_0000, 0x03e0_0008, 0];
        let certificate = prove(words.clone(), 8).unwrap();
        assert_eq!(certificate.len(), words.len());
        assert_eq!(certificate.get(&(BASE + 4)), Some(&0xac22_0000));
    }

    #[test]
    fn rejects_direct_write_and_one_branch_clobber() {
        assert!(prove(vec![addiu(8), 0x03e0_0008, 0], 8).is_none());
        assert!(prove(vec![beq(3), 0, addiu(8), 0x03e0_0008, 0x03e0_0008, 0], 8).is_none());
    }

    #[test]
    fn checks_branch_and_return_delay_slots() {
        assert!(prove(vec![beq(2), addiu(8), 0x03e0_0008, 0], 8).is_none());
        assert!(prove(vec![0x03e0_0008, addiu(8)], 8).is_none());
    }

    #[test]
    fn nested_direct_calls_are_checked_recursively() {
        assert!(prove(vec![jal(4), 0, 0x03e0_0008, 0, 0x03e0_0008, 0], 8).is_some());
        assert!(prove(vec![jal(4), 0, 0x03e0_0008, 0, addiu(8), 0x03e0_0008, 0], 8).is_none());

        let (map, image) = proof(vec![
            jal(8),
            0,
            jal(8),
            0,
            0x03e0_0008,
            0,
            0,
            0,
            0x03e0_0008,
            0,
        ]);
        let result = no_gpr_write(
            &MapIndex::new(&map),
            &image,
            GuestAddr(BASE),
            8,
            MAX_WORD_READS,
        )
        .unwrap();
        assert_eq!(result.words.len(), 8);
        assert_eq!(result.reads, 10); // nested callee words are read once per call site
    }

    #[test]
    fn rejects_unknown_indirects_missing_targets_recursion_and_branch_link() {
        assert!(prove(vec![0x0100_0008, 0], 8).is_none()); // jr r8
        assert!(prove(vec![beq(4), 0, 0x03e0_0008, 0], 8).is_none());
        assert!(prove(vec![jal(0), 0, 0x03e0_0008, 0], 8).is_none());
        assert!(prove(vec![(1 << 26) | (16 << 16), 0, 0x03e0_0008, 0], 8).is_none());
        assert!(prove(vec![0x0000_000c, 0], 8).is_none()); // syscall
    }

    #[test]
    fn rejects_unsupported_traps_invalid_words_and_coprocessors() {
        for word in [
            0xffff_ffff, // invalid
            0x0000_000d, // break
            0x4200_0018, // eret
            0x0000_0030, // tge
            18 << 26,    // cop2
            19 << 26,    // cop3
        ] {
            assert!(prove(vec![word, 0], 8).is_none(), "accepted {word:08x}");
        }
        assert!(prove(vec![0x03e0_0008, 0], 0).is_none());
        assert!(prove(vec![0x03e0_0008, 0], 31).is_none());
    }

    #[test]
    fn rejects_slot_ranges_and_exhausted_word_budget() {
        let (map, mut image) = proof(vec![0x03e0_0008, 0]);
        image.slots.push((
            crate::program::GuestRange {
                start: GuestAddr(BASE),
                size: 8,
            },
            BASE,
            8,
        ));
        assert!(
            no_gpr_write(
                &MapIndex::new(&map),
                &image,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS
            )
            .is_none()
        );

        let (map, mut image) = proof(vec![addiu(9), 0x03e0_0008, 0, 0x03e0_0008, 0]);
        image.slots.push((
            crate::program::GuestRange {
                start: GuestAddr(BASE + 4),
                size: 8,
            },
            BASE,
            8,
        ));
        assert!(
            no_gpr_write(
                &MapIndex::new(&map),
                &image,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS
            )
            .is_none()
        );

        let mut long = vec![0; MAX_WORD_READS + 1];
        long[MAX_WORD_READS - 1] = 0x03e0_0008;
        long[MAX_WORD_READS] = 0;
        assert!(prove(long, 8).is_none());
    }

    #[test]
    fn enforces_the_caller_supplied_read_budget() {
        let (map, image) = proof(vec![0x03e0_0008, 0]);
        let index = MapIndex::new(&map);
        assert!(no_gpr_write(&index, &image, GuestAddr(BASE), 8, 0).is_none());
        assert!(no_gpr_write(&index, &image, GuestAddr(BASE), 8, 1).is_none());
        let result = no_gpr_write(&index, &image, GuestAddr(BASE), 8, 2).unwrap();
        assert_eq!(result.reads, 2);
        assert_eq!(result.words.len(), 2);
    }
}
