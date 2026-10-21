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
    pub returns: BTreeSet<u32>,
    pub bindings: BTreeMap<u32, (u32, u32, u64)>,
    pub runtime: BTreeMap<u32, crate::program::RuntimeFunction>,
}

/// Explicitly permits strict linked-text to placed-text binding and verified
/// constant-cell tail continuations. Legacy entry points retain their prior
/// same-slot/fixed-address behavior.
pub(crate) fn no_gpr_write_bound(
    index: &MapIndex<'_>,
    map: &crate::program::ProgramMap,
    image: &CodeImage,
    entry: GuestAddr,
    register: u8,
    budget: usize,
    caller_slot: Option<usize>,
) -> Option<NoWrite> {
    if !std::ptr::eq(index.source(), map)
        || !(1..=30).contains(&register)
        || !entry.0.is_multiple_of(4)
        || caller_slot.is_some_and(|slot| slot >= image.slots.len())
    {
        return None;
    }
    let mut proof = Proof {
        index,
        image,
        register,
        caller_slot,
        limit: budget.min(MAX_WORD_READS),
        reads: 0,
        words: BTreeMap::new(),
        active_calls: BTreeSet::new(),
        map: Some(map),
        returns: BTreeSet::new(),
        bindings: BTreeMap::new(),
        active_slot: None,
        runtime: BTreeMap::new(),
    };
    let resolved = proof.resolve_raw(entry)?;
    proof
        .function(resolved.0, 0, resolved.1)
        .then_some(NoWrite {
            words: proof.words,
            reads: proof.reads,
            returns: proof.returns,
            bindings: proof.bindings,
            runtime: proof.runtime,
        })
}

/// Prove that every normally traversed path from `entry` leaves `register`
/// unchanged, returning all instruction words read by placed guest PC and the
/// number of reads (including repeated nested-callee reads).
///
/// This only proves a GPR effect on normal checked returns. It does not prove
/// memory, timing, return-target, or whole-program control-flow closure.
/// BREAK paths terminate under the existing checked-abort scope; the global
/// solver still rejects BREAK in scopes that do not admit that boundary.
#[cfg(test)]
pub(crate) fn no_gpr_write(
    index: &MapIndex<'_>,
    image: &CodeImage,
    entry: GuestAddr,
    register: u8,
    budget: usize,
) -> Option<NoWrite> {
    no_gpr_write_in(index, image, entry, register, budget, None)
}

/// Prove the same source effect while permitting words in `caller_slot`, the
/// current placed alternate at the call site. Other placed alternates remain
/// outside this proof. The caller still owns binding identity and lifetime
/// checks; this only extends the source-effect read set.
#[cfg(test)]
pub(crate) fn no_gpr_write_in(
    index: &MapIndex<'_>,
    image: &CodeImage,
    entry: GuestAddr,
    register: u8,
    budget: usize,
    caller_slot: Option<usize>,
) -> Option<NoWrite> {
    if !(1..=30).contains(&register) || !entry.0.is_multiple_of(4) {
        return None;
    }
    if caller_slot.is_some_and(|slot| slot >= image.slots.len()) {
        return None;
    }
    let mut proof = Proof {
        index,
        image,
        register,
        caller_slot,
        limit: budget.min(MAX_WORD_READS),
        reads: 0,
        words: BTreeMap::new(),
        active_calls: BTreeSet::new(),
        map: None,
        returns: BTreeSet::new(),
        bindings: BTreeMap::new(),
        active_slot: None,
        runtime: BTreeMap::new(),
    };
    proof.function(entry, 0, None).then_some(NoWrite {
        words: proof.words,
        reads: proof.reads,
        returns: proof.returns,
        bindings: proof.bindings,
        runtime: proof.runtime,
    })
}

struct Proof<'a, 'm> {
    index: &'a MapIndex<'m>,
    image: &'a CodeImage,
    register: u8,
    caller_slot: Option<usize>,
    limit: usize,
    reads: usize,
    words: BTreeMap<u32, u32>,
    active_calls: BTreeSet<u32>,
    map: Option<&'m crate::program::ProgramMap>,
    returns: BTreeSet<u32>,
    bindings: BTreeMap<u32, (u32, u32, u64)>,
    active_slot: Option<usize>,
    runtime: BTreeMap<u32, crate::program::RuntimeFunction>,
}

impl Proof<'_, '_> {
    // These host implementations only update TLB/binding state. They neither
    // write GPRs nor enter callbacks/scheduling; runtime scope remains mandatory.
    fn runtime_boundary(&self, pc: GuestAddr) -> Option<&crate::program::RuntimeFunction> {
        let function = self.map?.runtime_functions.get(&self.image.address(pc))?;
        (matches!(
            function.name.as_str(),
            "osMapTLB" | "osUnmapTLB" | "osUnmapTLBAll"
        ) && self.index.containing(&self.image.address(pc)).is_empty()
            && function.callbacks.is_empty()
            && function.status_global.is_none()
            && function.eeprom_timer.is_none()
            && !self.image.slots.iter().any(|(placed, linked, text)| {
                placed.contains(pc) || pc.0.checked_sub(*linked).is_some_and(|off| off < *text)
            }))
        .then_some(function)
    }

    fn resolve_raw(&mut self, pc: GuestAddr) -> Option<(GuestAddr, Option<usize>)> {
        if self.runtime_boundary(pc).is_some() {
            return Some((pc, None));
        }
        // The caller's already selected slot keeps its existing source scope.
        if self.map.is_none()
            || self
                .caller_slot
                .is_some_and(|slot| self.image.slots[slot].0.contains(pc))
        {
            self.target(pc)?;
            return Some((pc, None));
        }
        let matches: Vec<_> = self
            .image
            .slots
            .iter()
            .enumerate()
            .filter(|(_, (_, linked, text))| {
                pc.0.checked_sub(*linked)
                    .is_some_and(|offset| offset < *text && offset.is_multiple_of(4))
            })
            .collect();
        if matches.is_empty() {
            self.target(pc)?;
            return Some((
                pc,
                self.active_slot
                    .filter(|&slot| self.image.slots[slot].0.contains(pc)),
            ));
        }
        let map = self.map?;
        if matches.len() != 1 {
            return None;
        }
        let (slot_index, (slot, linked, text)) = matches[0];
        let offset = pc.0.checked_sub(*linked)?;
        let placed = slot.start.0.checked_add(offset)?;
        let spec = map.load_images.get(&self.image.base.image)?;
        let loads: Vec<_> = spec
            .loads
            .iter()
            .filter(|load| {
                load.destination == *slot
                    && load.linked == Some(GuestAddr(*linked))
                    && load.relocatable
                    && match load.encoding {
                        crate::declared_loads::LoadEncoding::TlbRaw { text_size }
                        | crate::declared_loads::LoadEncoding::RarePair { text_size, .. }
                        | crate::declared_loads::LoadEncoding::Segment { text_size, .. } => {
                            text_size == *text
                        }
                        _ => *text <= load.destination.size,
                    }
            })
            .collect();
        if loads.len() != 1 {
            return None;
        }
        let target = GuestAddr(placed);
        self.target(target)?;
        let source = loads[0].source.0;
        self.bindings.insert(pc.0, (*linked, target.0, source));
        Some((target, Some(slot_index)))
    }

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
        if self.active_slot.is_some_and(|slot| {
            let (placed, _, text) = &self.image.slots[slot];
            pc.0.checked_sub(placed.start.0)
                .is_none_or(|offset| offset >= *text)
        }) || !pc.0.is_multiple_of(4)
            || self
                .image
                .slots
                .iter()
                .enumerate()
                .any(|(slot, (placed, _, _))| {
                    placed.contains(pc)
                        && Some(slot) != self.caller_slot
                        && Some(slot) != self.active_slot
                })
            || !self.normal_block(pc, false)
        {
            return None;
        }
        let word = self.image.instruction_word(pc)?;
        // BREAK terminates native execution under the existing guarded scope
        // (ADR-0138); it cannot reach a normal call continuation.
        if crate::solver::is_break(word) {
            self.words.insert(pc.0, word);
            return Some(word);
        }
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
        if crate::solver::is_break(word)
            || instruction.has_delay_slot()
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

    fn function(&mut self, entry: GuestAddr, depth: usize, slot: Option<usize>) -> bool {
        if let Some(function) = self.runtime_boundary(entry).cloned() {
            if depth > MAX_CALL_DEPTH || self.reads >= self.limit {
                return false;
            }
            self.reads += 1;
            self.runtime.insert(entry.0, function);
            return true;
        }
        if depth > MAX_CALL_DEPTH
            || !self.target(entry).is_some()
            || !self.active_calls.insert(entry.0)
        {
            return false;
        }
        // Binding authority belongs to this traversal, never to a prior call.
        let previous_slot = self.active_slot;
        self.active_slot = slot;
        let result = self.function_body(entry, depth);
        self.active_slot = previous_slot;
        self.active_calls.remove(&entry.0);
        result
    }

    fn function_body(&mut self, entry: GuestAddr, depth: usize) -> bool {
        let mut pending = BTreeSet::from([(entry.0, self.active_slot)]);
        let mut visited = BTreeSet::new();
        let mut has_return = false;

        while let Some((raw_pc, slot)) = pending.pop_first() {
            self.active_slot = slot;
            if !visited.insert((raw_pc, slot)) {
                continue;
            }
            let pc = GuestAddr(raw_pc);
            let Some(word) = self.read(pc) else {
                return false;
            };
            if crate::solver::is_break(word) {
                continue;
            }
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
                pending.insert((target.0, self.active_slot));
                if !instruction.is_unconditional_branch() {
                    let Some(next) = pc.0.checked_add(8) else {
                        return false;
                    };
                    if self.target(GuestAddr(next)).is_none() {
                        return false;
                    }
                    pending.insert((next, self.active_slot));
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
                let Some((target, target_slot)) = self.resolve_raw(target) else {
                    return false;
                };
                if self.target(target).is_none() && self.runtime_boundary(target).is_none() {
                    return false;
                }
                if opcode == 2 && self.runtime_boundary(target).is_some() {
                    return false;
                }
                if opcode == 3 {
                    if depth == MAX_CALL_DEPTH || !self.function(target, depth + 1, target_slot) {
                        return false;
                    }
                    let Some(next) = pc.0.checked_add(8) else {
                        return false;
                    };
                    if self.target(GuestAddr(next)).is_none() {
                        return false;
                    }
                    pending.insert((next, self.active_slot));
                } else {
                    pending.insert((target.0, target_slot));
                }
                continue;
            }

            if instruction.is_jump() || instruction.has_delay_slot() {
                if word == 0x03e0_0008 {
                    if self.delay(pc).is_none() {
                        return false;
                    }
                    self.returns.insert(pc.0);
                    has_return = true;
                    continue;
                }
                if let Some(map) = self.map.filter(|_| {
                    word & 0xfc1f_ffff == 8 && ((word >> 21) & 31) != 31 && ((word >> 21) & 31) != 0
                }) {
                    if self.delay(pc).is_none() {
                        return false;
                    }
                    let sites: Vec<_> = map
                        .indirect_sites
                        .iter()
                        .filter(|site| site.site == self.image.address(pc))
                        .collect();
                    if sites.len() != 1 {
                        return false;
                    }
                    let blocks = self.index.containing(&sites[0].site);
                    if blocks.len() != 1 || blocks[0].delay_slot_entry {
                        return false;
                    }
                    let Some(prefix) =
                        pc.0.checked_sub(blocks[0].start.pc.0)
                            .map(|n| n as usize / 4 + 1)
                    else {
                        return false;
                    };
                    // Three prefix scans, JR/delay/cell, and at most one target
                    // read per slot (or one fixed target). Reserve before verifying.
                    let Some(charge) = prefix
                        .checked_mul(3)
                        .and_then(|n| n.checked_add(self.image.slots.len().max(1)))
                        .and_then(|n| n.checked_add(3))
                    else {
                        return false;
                    };
                    if self
                        .reads
                        .checked_add(charge)
                        .is_none_or(|n| n > self.limit)
                    {
                        return false;
                    }
                    self.reads += charge;
                    let Some(cert) = crate::tail_cells::verified_certificate_in(
                        self.index, map, self.image, sites[0],
                    ) else {
                        return false;
                    };
                    self.words.insert(cert.source_cell.0, cert.source_word);
                    if cert.targets.is_empty() {
                        return false;
                    }
                    for target in cert.targets {
                        if !self.function(
                            target.pc,
                            depth + 1,
                            self.active_slot
                                .filter(|&slot| self.image.slots[slot].0.contains(target.pc)),
                        ) {
                            return false;
                        }
                    }
                    has_return = true;
                    continue;
                }
                return false;
            }

            let Some(next) = pc.0.checked_add(4) else {
                return false;
            };
            pending.insert((next, self.active_slot));
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
        jal_target(BASE + word_index as u32 * 4)
    }

    fn jal_target(target: u32) -> u32 {
        (3 << 26) | ((target >> 2) & 0x03ff_ffff)
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

    fn add_raw_binding(
        map: &mut ProgramMap,
        image: &mut CodeImage,
        placed: u32,
        linked: u32,
        size: u32,
    ) {
        map.evidence.insert(
            "synthetic-copy".into(),
            crate::program::Evidence {
                kind: EvidenceKind::TestOracle,
                producer: "callee-effects-test".into(),
                revision: "0".into(),
                detail: "synthetic load event".into(),
            },
        );
        let range = crate::program::GuestRange {
            start: GuestAddr(placed),
            size,
        };
        add_slot(image, placed, linked, size, size);
        let spec = map
            .load_images
            .entry(image.base.image.clone())
            .or_insert_with(|| crate::declared_loads::LoadImage {
                base_offset: crate::program::RomOffset(0),
                base: crate::program::GuestRange {
                    start: image.base.pc,
                    size: image.words.len() as u32 * 4,
                },
                loads: Vec::new(),
            });
        spec.loads.push(crate::declared_loads::DeclaredLoad {
            destination: range.clone(),
            source: crate::program::RomOffset(0x40),
            encoding: crate::declared_loads::LoadEncoding::Raw,
            evidence: ["synthetic-copy".into()].into(),
            relocatable: true,
            linked: Some(GuestAddr(linked)),
        });
        map.loads.insert(crate::program::LoadMapping {
            rom_offset: crate::program::RomOffset(0x40),
            destination: range.clone(),
            image: image.base.image.clone(),
            generation: image.base.generation,
            copy_event: None,
            evidence: ["synthetic-callee".into(), "synthetic-copy".into()].into(),
        });
        map.regions.insert(crate::program::Region {
            image: image.base.image.clone(),
            generation: image.base.generation,
            range,
            rom_offset: Some(crate::program::RomOffset(0x40)),
            physical_start: None,
            overlay: None,
            evidence: ["synthetic-callee".into(), "synthetic-copy".into()].into(),
        });
    }

    #[test]
    fn tlb_runtime_effects_keep_budget_and_slot_boundaries() {
        let (mut map, mut image) = proof(vec![0x03e00008, 0]);
        let address = image.base.clone();
        map.blocks.clear();
        let f = crate::program::RuntimeFunction {
            name: "osMapTLB".into(),
            evidence: ["synthetic-callee".into()].into(),
            callbacks: vec![],
            status_global: None,
            eeprom_timer: None,
        };
        map.runtime_functions.insert(address.clone(), f);
        for register in 1..=30 {
            let effect = no_gpr_write_bound(
                &MapIndex::new(&map),
                &map,
                &image,
                address.pc,
                register,
                1,
                None,
            )
            .unwrap();
            assert_eq!(effect.reads, 1);
            assert_eq!(effect.runtime.len(), 1);
            assert!(effect.words.is_empty() && effect.returns.is_empty());
        }
        assert!(
            no_gpr_write_bound(&MapIndex::new(&map), &map, &image, address.pc, 19, 0, None)
                .is_none()
        );
        image.slots.push((
            crate::program::GuestRange {
                start: GuestAddr(BASE + 0x1000),
                size: 8,
            },
            BASE,
            8,
        ));
        assert!(
            no_gpr_write_bound(&MapIndex::new(&map), &map, &image, address.pc, 19, 8, None)
                .is_none()
        );
    }

    #[test]
    fn a_prior_raw_call_does_not_authorize_a_later_placed_pc_or_fallthrough() {
        for later_call in [true, false] {
            let (mut map, mut image) = proof(vec![0; 64]);
            let placed = BASE + 0x20;
            let linked = 0x8000_4000;
            add_raw_binding(&mut map, &mut image, placed, linked, 8);
            image.words[0] = jal_target(linked);
            if later_call {
                image.words[2] = jal_target(placed);
                image.words[4] = 0x03e0_0008;
            }
            image.words[8] = 0x03e0_0008;
            assert!(
                no_gpr_write_bound(
                    &MapIndex::new(&map),
                    &map,
                    &image,
                    GuestAddr(BASE),
                    8,
                    MAX_WORD_READS,
                    None
                )
                .is_none(),
                "later explicit placed call: {later_call}"
            );
        }
    }

    #[test]
    fn mapped_fallthrough_cannot_escape_its_text_into_adjacent_fixed_code() {
        let (mut map, mut image) = proof(vec![0; 64]);
        let placed = BASE + 0x20;
        let linked = 0x8000_4000;
        add_raw_binding(&mut map, &mut image, placed, linked, 8);
        image.words[0] = jal_target(linked);
        image.words[2] = 0x03e0_0008;
        image.words[10] = 0x03e0_0008;
        assert!(
            no_gpr_write_bound(
                &MapIndex::new(&map),
                &map,
                &image,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        image.words[8] = 0x03e0_0008;
        image.words[2] = jal_target(linked);
        image.words[4] = 0x03e0_0008;
        assert!(
            no_gpr_write_bound(
                &MapIndex::new(&map),
                &map,
                &image,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS,
                None
            )
            .is_some()
        );
    }

    #[test]
    fn opt_in_binds_unique_raw_text_entry_and_returns_canonical_pc_witness() {
        let (mut map, mut image) = proof(vec![0; 64]);
        map.rom.size = 0x1000;
        let placed = BASE + 0x20;
        let linked = 0x8000_0000;
        add_raw_binding(&mut map, &mut image, placed, linked, 8);
        image.words[0] = jal_target(linked);
        image.words[1] = 0;
        image.words[2] = 0x03e0_0008;
        image.words[3] = 0;
        image.words[((placed - BASE) / 4) as usize] = 0x03e0_0008;
        image.words[((placed + 4 - BASE) / 4) as usize] = 0;
        let summary = no_gpr_write_bound(
            &MapIndex::new(&map),
            &map,
            &image,
            GuestAddr(BASE),
            8,
            MAX_WORD_READS,
            None,
        )
        .unwrap();
        assert_eq!(summary.bindings.get(&linked), Some(&(linked, placed, 0x40)));
        assert!(summary.returns.contains(&placed));
        assert!(summary.words.contains_key(&placed));
    }

    #[test]
    fn opt_in_rejects_ambiguous_out_of_text_and_unbound_raw_entries() {
        let (mut map, mut image) = proof(vec![0; 64]);
        let placed = BASE + 0x20;
        add_raw_binding(&mut map, &mut image, placed, 0x8000_4000, 8);
        image.words[((placed - BASE) / 4) as usize] = 0x03e0_0008;
        image.words[((placed + 4 - BASE) / 4) as usize] = 0;
        let index = MapIndex::new(&map);
        assert!(
            no_gpr_write_bound(
                &index,
                &map,
                &image,
                GuestAddr(0x8000_4008),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        assert!(
            no_gpr_write_bound(
                &index,
                &map,
                &image,
                GuestAddr(0x9000_4000),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        let mut other_generation = image.clone();
        other_generation.base.generation += 1;
        assert!(
            no_gpr_write_bound(
                &index,
                &map,
                &other_generation,
                GuestAddr(0x8000_4000),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        let mut hole = image.clone();
        hole.holes.push(crate::program::GuestRange {
            start: GuestAddr(placed),
            size: 4,
        });
        assert!(
            no_gpr_write_bound(
                &index,
                &map,
                &hole,
                GuestAddr(0x8000_4000),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        let mut delay_map = map.clone();
        delay_map.blocks.retain(|block| block.start.pc.0 != placed);
        delay_map.blocks.insert(crate::program::BasicBlock {
            start: image.address(GuestAddr(placed)),
            size: 4,
            delay_slot_entry: true,
            evidence: ["synthetic-callee".into()].into(),
        });
        assert!(
            no_gpr_write_bound(
                &MapIndex::new(&delay_map),
                &delay_map,
                &image,
                GuestAddr(0x8000_4000),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
        add_raw_binding(&mut map, &mut image, BASE + 0x30, 0x8000_4000, 8);
        assert!(
            no_gpr_write_bound(
                &MapIndex::new(&map),
                &map,
                &image,
                GuestAddr(0x8000_4000),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
    }

    #[test]
    fn opt_in_follows_only_rechecked_tail_cell_targets() {
        let (mut map, mut image) = proof(vec![0; 64]);
        map.rom.size = 0x1000;
        let placed = BASE + 0x20;
        let linked = 0x8000_0000;
        add_raw_binding(&mut map, &mut image, placed, linked, 0x20);
        image.slots[0].2 = 0x10;
        image.words[0] = jal_target(linked);
        image.words[1] = 0;
        image.words[2] = 0x03e0_0008;
        image.words[3] = 0;
        image.words[((placed - BASE) / 4) as usize] = 0x3c01_8000;
        image.words[((placed + 4 - BASE) / 4) as usize] = 0x8c21_0010;
        image.words[((placed + 8 - BASE) / 4) as usize] = 0x0020_0008;
        image.words[((placed + 12 - BASE) / 4) as usize] = 0;
        let target = BASE + 0x40;
        image.words[((placed + 16 - BASE) / 4) as usize] = target;
        image.words[((target - BASE) / 4) as usize] = 0x03e0_0008;
        image.words[((target + 4 - BASE) / 4) as usize] = 0;
        let references: EvidenceRefs = ["synthetic-callee".into()].into();
        map.blocks
            .retain(|block| !(block.start.pc.0 >= placed && block.start.pc.0 < placed + 0x14));
        map.blocks.insert(crate::program::BasicBlock {
            start: image.address(GuestAddr(placed)),
            size: 0x10,
            delay_slot_entry: false,
            evidence: references.clone(),
        });
        let site = crate::program::IndirectSite {
            site: image.address(GuestAddr(placed + 8)),
            link_register: None,
            delay_slot: crate::program::DelaySlot::Always,
            candidates: BTreeMap::new(),
            observed: BTreeMap::new(),
            closed_proof: None,
            evidence: references,
        };
        map.indirect_sites.insert(site.clone());
        let analyzed = crate::tail_cells::analyze(&map, &image).unwrap();
        let site = analyzed
            .indirect_sites
            .iter()
            .find(|candidate| candidate.site == site.site)
            .unwrap();
        let index = MapIndex::new(&analyzed);
        assert!(crate::tail_cells::verify_in(
            &index, &analyzed, &image, site
        ));
        let summary = no_gpr_write_bound(
            &index,
            &analyzed,
            &image,
            GuestAddr(BASE),
            8,
            MAX_WORD_READS,
            None,
        )
        .unwrap();
        assert!(summary.words.contains_key(&target));
        assert!(summary.returns.contains(&target));
        assert!(summary.bindings.contains_key(&linked));
        assert!(
            no_gpr_write_bound(&index, &analyzed, &image, GuestAddr(linked), 8, 8, None).is_none()
        );

        let mut changed_cell = image.clone();
        changed_cell.words[((placed + 16 - BASE) / 4) as usize] ^= 4;
        assert!(
            no_gpr_write_bound(
                &index,
                &analyzed,
                &changed_cell,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );

        let mut clobbered_target = image.clone();
        clobbered_target.words[((target - BASE) / 4) as usize] = addiu(8);
        assert!(
            no_gpr_write_bound(
                &index,
                &analyzed,
                &clobbered_target,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );

        let mut target_removed = analyzed.clone();
        target_removed
            .blocks
            .retain(|block| block.start.pc.0 != target);
        let removed_index = MapIndex::new(&target_removed);
        assert!(
            no_gpr_write_bound(
                &removed_index,
                &target_removed,
                &image,
                GuestAddr(BASE),
                8,
                MAX_WORD_READS,
                None
            )
            .is_none()
        );
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

    fn add_slot(image: &mut CodeImage, start: u32, linked: u32, size: u32, text: u32) {
        image.slots.push((
            crate::program::GuestRange {
                start: GuestAddr(start),
                size,
            },
            linked,
            text,
        ));
    }

    #[test]
    fn permits_only_the_explicit_current_slot_for_complete_nested_paths() {
        let (map, mut image) = proof(vec![0; 48]);
        let placed = BASE + 0x20;
        let linked = BASE + 0x1000;
        add_slot(&mut image, placed, linked, 40, 40);
        add_slot(&mut image, BASE + 0x80, BASE + 0x2000, 8, 8);
        let words = &mut image.words;
        words[8] = jal_target(linked + 16);
        words[10] = 0x03e0_0008;
        words[12] = jal_target(linked + 32);
        words[14] = 0x03e0_0008;
        words[16] = 0x03e0_0008;

        let index = MapIndex::new(&map);
        assert!(no_gpr_write(&index, &image, GuestAddr(placed), 8, MAX_WORD_READS).is_none());
        let summary = no_gpr_write_in(
            &index,
            &image,
            GuestAddr(placed),
            8,
            MAX_WORD_READS,
            Some(0),
        )
        .unwrap();
        assert!(summary.words.contains_key(&placed));
        assert!(summary.words.contains_key(&(placed + 32)));
        assert!(
            no_gpr_write_in(
                &index,
                &image,
                GuestAddr(placed),
                8,
                MAX_WORD_READS,
                Some(2),
            )
            .is_none()
        );
        assert!(
            no_gpr_write_in(
                &index,
                &image,
                GuestAddr(placed),
                8,
                MAX_WORD_READS,
                Some(1),
            )
            .is_none()
        );
    }

    #[test]
    fn rejects_fixed_to_other_slot_and_current_to_other_slot_calls() {
        let (map, mut image) = proof(vec![0; 48]);
        let first = BASE + 0x20;
        let first_link = BASE + 0x1000;
        let other = BASE + 0x40;
        let other_link = BASE + 0x2000;
        add_slot(&mut image, first, first_link, 16, 16);
        add_slot(&mut image, other, other_link, 8, 8);

        // The fixed entry at BASE calls the other placed alternate.
        image.words[0] = jal_target(other_link);
        image.words[2] = 0x03e0_0008;
        image.words[16] = 0x03e0_0008;
        let index = MapIndex::new(&map);
        assert!(
            no_gpr_write_in(&index, &image, GuestAddr(BASE), 8, MAX_WORD_READS, Some(0),).is_none()
        );

        // The currently allowed alternate also cannot transfer to another.
        image.words[8] = jal_target(other_link);
        image.words[10] = 0x03e0_0008;
        assert!(
            no_gpr_write_in(&index, &image, GuestAddr(first), 8, MAX_WORD_READS, Some(0),)
                .is_none()
        );
    }

    #[test]
    fn current_slot_text_bound_still_rejects_placed_data_tail() {
        let (map, mut image) = proof(vec![0; 16]);
        let placed = BASE + 0x20;
        add_slot(&mut image, placed, BASE + 0x1000, 16, 8);
        let index = MapIndex::new(&map);
        assert!(
            no_gpr_write_in(
                &index,
                &image,
                GuestAddr(placed),
                8,
                MAX_WORD_READS,
                Some(0),
            )
            .is_none()
        );
    }

    #[test]
    fn explicit_current_slot_mode_still_rejects_register_clobbers() {
        let (map, mut image) = proof(vec![0; 16]);
        let placed = BASE + 0x20;
        add_slot(&mut image, placed, BASE + 0x1000, 8, 8);
        image.words[8] = addiu(8);
        image.words[9] = 0x03e0_0008;
        assert!(
            no_gpr_write_in(
                &MapIndex::new(&map),
                &image,
                GuestAddr(placed),
                8,
                MAX_WORD_READS,
                Some(0),
            )
            .is_none()
        );
    }

    #[test]
    fn raw_kseg_slot_can_call_fixed_text_under_the_same_source_proof() {
        let slot = BASE + 0x1000;
        let (map, mut image) = proof(vec![0; 1028]);
        add_slot(&mut image, slot, slot, 16, 16);
        image.words[((slot - BASE) / 4) as usize] = jal_target(BASE + 0x100);
        image.words[(slot + 8 - BASE) as usize / 4] = 0x03e0_0008;
        image.words[0x100 / 4] = 0x03e0_0008;

        let summary = no_gpr_write_in(
            &MapIndex::new(&map),
            &image,
            GuestAddr(slot),
            8,
            MAX_WORD_READS,
            Some(0),
        )
        .unwrap();
        assert!(summary.words.contains_key(&slot));
        assert!(summary.words.contains_key(&(BASE + 0x100)));
    }

    #[test]
    fn guarded_break_ends_a_path_without_establishing_a_normal_return() {
        let words = vec![beq(3), 0, 0x03e0_0008, 0, 0x0007_000d];
        let summary = prove(words.clone(), 8).unwrap();
        assert_eq!(summary.get(&(BASE + 16)), Some(&0x0007_000d));
        let mut changed = words;
        changed[4] = addiu(8);
        assert!(prove(changed, 8).is_none());
        assert!(prove(vec![0x0007_000d], 8).is_none());
        assert!(prove(vec![0x03e0_0008, 0x0007_000d], 8).is_none());
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
