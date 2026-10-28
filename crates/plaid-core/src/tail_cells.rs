//! Source-identified candidates for indirect tail jumps through constant cells.
//!
//! This certifies a finite target set from the current image snapshot. It does
//! not prove the cell stays unchanged at runtime; a closing native scope must
//! bind and protect the source bytes.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, decode},
    indirect::{MapIndex, code_pointer, prefix_state_in, signed_word},
    program::*,
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const PRODUCER: &str = "plaid-tail-cell-jr/v0";
pub const SCHEMA_VERSION: u32 = 0;
const CAPTURE_SEMANTICS: &str = "jr_register_before_delay_slot";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TailCellTargetWord {
    pub address: CodeAddress,
    pub instruction_word: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TailCellCertificate {
    pub schema_version: u32,
    /// Binds this local witness to the image identity/generation. The guarded
    /// native scope separately validates its complete source image contents.
    pub image_base: CodeAddress,
    pub site: CodeAddress,
    pub block: CodeAddress,
    pub register: u8,
    pub load_pc: GuestAddr,
    pub load_base_register: u8,
    pub source_cell: GuestAddr,
    pub source_word: u32,
    pub targets: Vec<CodeAddress>,
    pub target_words: Vec<TailCellTargetWord>,
    pub prefix_sha256: String,
    pub capture_semantics: String,
    pub source_cell_requires_native_byte_binding: bool,
}

fn field(word: u32, shift: u32) -> u8 {
    ((word >> shift) & 31) as u8
}

fn canonical_32(value: u64) -> Option<u32> {
    let low = value as u32;
    (value == u64::from(low) || value == signed_word(low)).then_some(low)
}

fn mapped_target(map: &ProgramMap, target: &CodeAddress) -> bool {
    map.blocks
        .iter()
        .any(|block| block.start == *target && !block.delay_slot_entry)
}

fn certificate(
    index: &MapIndex,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<TailCellCertificate> {
    if site.site.image != image.base.image
        || site.site.generation != image.base.generation
        || site.link_register.is_some()
        || site.delay_slot != DelaySlot::Always
    {
        return None;
    }

    let jr = image.instruction_word(site.site.pc)?;
    let register = field(jr, 21);
    // Accept the canonical JR encoding only; JR $zero and JR $ra are not tail
    // dispatches for this certificate.
    if jr >> 26 != 0 || jr & 0x001f_ffff != 8 || register == 0 || register == 31 {
        return None;
    }

    let slot_pc = GuestAddr(site.site.pc.0.checked_add(4)?);
    let slot = decode(image.inline_delay_word(site.site.pc)?, slot_pc);
    if !slot.is_valid() || slot.is_trap() || slot.has_delay_slot() {
        return None;
    }

    let (block, _, prefix) = prefix_state_in(index, image, &site.site)?;
    let mut latest_definition = None;
    let mut pc = block.pc;
    while pc.0 < site.site.pc.0 {
        let word = image.instruction_word(pc)?;
        let instruction = decode(word, pc);
        if !instruction.is_valid() || instruction.is_trap() || instruction.has_delay_slot() {
            return None;
        }
        if instruction.destination_gpr() == Some(u32::from(register)) {
            latest_definition = Some((pc, word));
        }
        pc = GuestAddr(pc.0.checked_add(4)?);
    }
    let (load_pc, load) = latest_definition?;
    if load >> 26 != 35 || field(load, 16) != register {
        return None;
    }

    let load_address = image.address(load_pc);
    let (load_block, state, _) = prefix_state_in(index, image, &load_address)?;
    if load_block != block {
        return None;
    }
    let load_base_register = field(load, 21);
    let base = canonical_32(state[usize::from(load_base_register)]?)?;
    let address = base.wrapping_add_signed(i32::from(load as i16));
    if !address.is_multiple_of(4) {
        return None;
    }
    // Slot alternates read their own placed data copy, not the linked address.
    let source_cell = GuestAddr(image.slot_view(load_pc, address));
    if !source_cell.0.is_multiple_of(4) {
        return None;
    }
    let source_word = image.word(source_cell)?;
    let target = code_pointer(signed_word(source_word))?;
    let mut target_words = std::collections::BTreeMap::new();
    for copy in image.slot_copies(target) {
        if !copy.is_multiple_of(4) {
            return None;
        }
        let target_pc = GuestAddr(copy);
        let target_word = image.instruction_word(target_pc)?;
        if !decode(target_word, target_pc).is_valid() {
            return None;
        }
        target_words.insert(image.address(target_pc), target_word);
    }
    if target_words.is_empty() {
        return None;
    }
    let targets: Vec<_> = target_words.keys().cloned().collect();
    let target_words: Vec<_> = target_words
        .into_iter()
        .map(|(address, instruction_word)| TailCellTargetWord {
            address,
            instruction_word,
        })
        .collect();

    Some(TailCellCertificate {
        schema_version: SCHEMA_VERSION,
        image_base: image.base.clone(),
        site: site.site.clone(),
        block,
        register,
        load_pc,
        load_base_register,
        source_cell,
        source_word,
        targets,
        target_words,
        prefix_sha256: sha256(&prefix),
        capture_semantics: CAPTURE_SEMANTICS.into(),
        source_cell_requires_native_byte_binding: true,
    })
}

fn detail(
    index: &MapIndex,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<(TailCellCertificate, String, String)> {
    let certificate = certificate(index, image, site)?;
    let detail = serde_json::to_string(&certificate).ok()?;
    let id = format!("tail-cell-jr:{}", sha256(detail.as_bytes()));
    Some((certificate, detail, id))
}

/// Recheck a tail-cell certificate. Runtime closure still requires a guarded
/// scope, native target dispatch and source-cell byte binding.
pub fn verify(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> bool {
    verify_in(&MapIndex::new(map), map, image, site)
}

/// [`verify`] using a caller-owned CFG index.
pub fn verify_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> bool {
    verified_certificate_in(index, map, image, site).is_some()
}

/// Return the exact source certificate only when the current map and bytes
/// still recheck the closed tail-cell witness.
pub(crate) fn verified_certificate_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<TailCellCertificate> {
    let evidence_id = site.closed_proof.as_deref()?;
    let evidence = map.evidence.get(evidence_id)?;
    if evidence.kind != EvidenceKind::Static
        || evidence.producer != PRODUCER
        || evidence.revision != "0"
    {
        return None;
    }
    let (certificate, detail, id) = detail(index, image, site)?;
    let targets: BTreeSet<_> = certificate.targets.iter().cloned().collect();
    let valid = evidence_id == id.as_str()
        && evidence.detail == detail
        && site.candidates.keys().cloned().collect::<BTreeSet<_>>() == targets
        && site
            .candidates
            .values()
            .all(|references| references.contains(evidence_id))
        && site.observed.keys().all(|target| targets.contains(target))
        && certificate
            .targets
            .iter()
            .all(|target| mapped_target(map, target));
    valid.then_some(certificate)
}

/// The one source word that a verified native tail dispatch must bind/protect.
pub fn source_cell_range(
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<GuestRange> {
    source_cell_range_in(&MapIndex::new(map), map, image, site)
}

/// [`source_cell_range`] using a caller-owned CFG index.
pub fn source_cell_range_in(
    index: &MapIndex,
    map: &ProgramMap,
    image: &CodeImage,
    site: &IndirectSite,
) -> Option<GuestRange> {
    if !verify_in(index, map, image, site) {
        return None;
    }
    let certificate = certificate(index, image, site)?;
    Some(GuestRange {
        start: certificate.source_cell,
        size: 4,
    })
}

/// Record source-identified candidates. Unmapped code remains a candidate but
/// cannot receive a closed proof; absence of stores never proves cell stability.
pub fn analyze(map: &ProgramMap, image: &CodeImage) -> Result<ProgramMap, String> {
    map.validate()?;
    let mut out = map.clone();
    let index = MapIndex::new(map);
    let mut produced = BTreeSet::new();
    let sites: Vec<_> = map.indirect_sites.iter().collect();
    let found = crate::indirect::par_map(&sites, |old| detail(&index, image, old));
    for (old, found) in sites.into_iter().zip(found) {
        let Some((certificate, detail, id)) = found else {
            continue;
        };
        let targets: BTreeSet<_> = certificate.targets.iter().cloned().collect();
        out.evidence.insert(
            id.clone(),
            Evidence {
                kind: EvidenceKind::Static,
                producer: PRODUCER.into(),
                revision: "0".into(),
                detail,
            },
        );
        let mut site = old.clone();
        out.indirect_sites.remove(old);
        for target in targets {
            site.candidates
                .entry(target)
                .or_default()
                .insert(id.clone());
        }
        if old.closed_proof.as_deref().is_some_and(|proof| {
            map.evidence
                .get(proof)
                .is_some_and(|evidence| evidence.producer == PRODUCER)
        }) {
            site.closed_proof = Some(id.clone());
        }
        produced.insert((site.site.clone(), id));
        out.indirect_sites.insert(site);
    }
    // Nothing produced and no tail-cell claim to recheck: `out` is the
    // validated input, unchanged.
    if produced.is_empty()
        && !out.indirect_sites.iter().any(|site| {
            site.closed_proof
                .as_deref()
                .and_then(|id| out.evidence.get(id))
                .is_some_and(|evidence| evidence.producer == PRODUCER)
        })
    {
        return Ok(out);
    }

    // A proof only closes an exact candidate set whose executable targets are
    // already represented in the map. Rebuild the index after adding candidates
    // so a newly exposed alternate entry also invalidates the proof.
    let index = MapIndex::new(&out);
    let updates: Vec<_> = produced
        .into_iter()
        .filter_map(|(site_address, id)| {
            let mut site = out
                .indirect_sites
                .iter()
                .find(|site| site.site == site_address)?
                .clone();
            let exact_candidates =
                detail(&index, image, &site).is_some_and(|(certificate, _, current_id)| {
                    current_id == id
                        && site.candidates.keys().cloned().collect::<BTreeSet<_>>()
                            == certificate.targets.iter().cloned().collect()
                        && site
                            .observed
                            .keys()
                            .all(|target| certificate.targets.contains(target))
                        && certificate
                            .targets
                            .iter()
                            .all(|target| mapped_target(&out, target))
                });
            if exact_candidates {
                site.closed_proof = Some(id.clone());
                if !verify_in(&index, &out, image, &site) {
                    site.closed_proof = None;
                }
            } else if site.closed_proof.as_deref().is_some_and(|proof| {
                out.evidence
                    .get(proof)
                    .is_some_and(|evidence| evidence.producer == PRODUCER)
            }) {
                site.closed_proof = None;
            }
            Some((site, id))
        })
        .collect();
    for (site, id) in updates {
        let current = out
            .indirect_sites
            .iter()
            .find(|old| {
                old.site == site.site
                    && old
                        .candidates
                        .values()
                        .any(|references| references.contains(&id))
            })
            .cloned();
        if let Some(current) = current {
            out.indirect_sites.remove(&current);
        }
        out.indirect_sites.insert(site);
    }
    // Stale tail-cell claims must never survive a failed byte/CFG recheck.
    let index = MapIndex::new(&out);
    let stale: Vec<_> = out
        .indirect_sites
        .iter()
        .filter(|site| {
            site.closed_proof
                .as_deref()
                .and_then(|id| out.evidence.get(id))
                .is_some_and(|evidence| {
                    evidence.producer == PRODUCER && !verify_in(&index, &out, image, site)
                })
        })
        .cloned()
        .collect();
    for mut site in stale {
        let stale_proof = site.closed_proof.clone();
        site.closed_proof = None;
        let current = out
            .indirect_sites
            .iter()
            .find(|old| old.site == site.site && old.closed_proof == stale_proof)
            .cloned();
        if let Some(current) = current {
            out.indirect_sites.remove(&current);
        }
        out.indirect_sites.insert(site);
    }
    out.validate()?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    const BASE: u32 = 0x1000;
    const CELL: u32 = 0x1100;
    const TARGET: u32 = 0x1020;

    fn jr(register: u8) -> u32 {
        (u32::from(register) << 21) | 8
    }

    fn lw(register: u8, offset: u16) -> u32 {
        (35 << 26) | (u32::from(register) << 16) | u32::from(offset)
    }

    fn code(image: &str, generation: u64, pc: u32) -> CodeAddress {
        CodeAddress {
            pc: GuestAddr(pc),
            image: image.into(),
            generation,
        }
    }

    fn fixture() -> (ProgramMap, CodeImage, IndirectSite) {
        let mut words = vec![0; 65];
        words[0] = lw(8, CELL as u16);
        words[1] = 0;
        words[2] = jr(8);
        words[3] = 0;
        words[((TARGET - BASE) / 4) as usize] = (9 << 26) | (2 << 16) | 1;
        words[((CELL - BASE) / 4) as usize] = TARGET;
        let image = CodeImage {
            base: code("synthetic", 7, BASE),
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: Vec::new(),
        };
        let mut site = IndirectSite {
            site: code("synthetic", 7, BASE + 8),
            link_register: None,
            delay_slot: DelaySlot::Always,
            candidates: Default::default(),
            observed: Default::default(),
            closed_proof: None,
            evidence: Default::default(),
        };
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "0".repeat(64),
            size: 64,
        });
        map.evidence.insert(
            "synthetic-fixture".into(),
            Evidence {
                kind: EvidenceKind::TestOracle,
                producer: "synthetic-test".into(),
                revision: "0".into(),
                detail: "authored synthetic tail-cell fixture".into(),
            },
        );
        let references: EvidenceRefs = ["synthetic-fixture".into()].into();
        site.evidence = references.clone();
        map.blocks.insert(BasicBlock {
            start: code("synthetic", 7, BASE),
            size: 16,
            delay_slot_entry: false,
            evidence: references.clone(),
        });
        map.blocks.insert(BasicBlock {
            start: code("synthetic", 7, TARGET),
            size: 4,
            delay_slot_entry: false,
            evidence: references,
        });
        map.indirect_sites.insert(site.clone());
        (map, image, site)
    }

    fn analyzed(map: &ProgramMap, image: &CodeImage, site: &IndirectSite) -> ProgramMap {
        let mut input = map.clone();
        input
            .indirect_sites
            .retain(|candidate| candidate.site != site.site);
        input.indirect_sites.insert(site.clone());
        analyze(&input, image).unwrap()
    }

    fn analyzed_site(map: &ProgramMap, site: &IndirectSite) -> IndirectSite {
        map.indirect_sites
            .iter()
            .find(|candidate| candidate.site == site.site)
            .unwrap()
            .clone()
    }

    #[test]
    fn certifies_a_bound_cell_and_rechecks_the_finite_target() {
        let (map, image, site) = fixture();
        let analyzed = analyzed(&map, &image, &site);
        let site = analyzed_site(&analyzed, &site);
        assert!(verify(&analyzed, &image, &site));
        assert_eq!(
            source_cell_range(&analyzed, &image, &site),
            Some(GuestRange {
                start: GuestAddr(CELL),
                size: 4,
            })
        );
        assert_eq!(
            site.candidates.keys().cloned().collect::<BTreeSet<_>>(),
            [code("synthetic", 7, TARGET)].into()
        );
    }

    #[test]
    fn source_address_shift_changes_the_certificate_and_protected_range() {
        let (map, image, site) = fixture();
        let original = analyzed(&map, &image, &site);
        let original_site = analyzed_site(&original, &site);

        let mut shifted_image = image.clone();
        shifted_image.words[0] = lw(8, (CELL + 4) as u16);
        shifted_image.words.push(TARGET);
        let mut shifted_map = original.clone();
        shifted_map.indirect_sites.clear();
        shifted_map.indirect_sites.insert(site.clone());
        let shifted = analyze(&shifted_map, &shifted_image).unwrap();
        let shifted_site = analyzed_site(&shifted, &site);

        assert!(!verify(&original, &shifted_image, &original_site));
        assert_eq!(
            source_cell_range(&shifted, &shifted_image, &shifted_site)
                .unwrap()
                .start,
            GuestAddr(CELL + 4)
        );
    }

    #[test]
    fn cell_change_and_equal_bytes_in_another_generation_do_not_reuse_proof() {
        let (map, image, site) = fixture();
        let analyzed = analyzed(&map, &image, &site);
        let proved_site = analyzed_site(&analyzed, &site);

        let mut changed = image.clone();
        changed.words[((CELL - BASE) / 4) as usize] = TARGET + 4;
        assert!(!verify(&analyzed, &changed, &proved_site));

        let mut other_generation = analyzed.clone();
        let mut other_site = proved_site.clone();
        other_site.site.generation += 1;
        other_site.candidates = other_site
            .candidates
            .into_iter()
            .map(|(mut target, references)| {
                target.generation += 1;
                (target, references)
            })
            .collect();
        other_generation.indirect_sites.clear();
        other_generation.indirect_sites.insert(other_site.clone());
        for block in &analyzed.blocks {
            let mut block = block.clone();
            block.start.generation += 1;
            other_generation.blocks.insert(block);
        }
        let mut other_image = image.clone();
        other_image.base.generation += 1;
        assert!(!verify(&other_generation, &other_image, &other_site));
    }

    #[test]
    fn clobbers_and_alternate_entries_leave_the_site_open() {
        let (map, mut image, site) = fixture();
        image.words[1] = (9 << 26) | (8 << 16); // addiu t0, zero, 0
        let clobbered = analyzed(&map, &image, &site);
        assert!(analyzed_site(&clobbered, &site).closed_proof.is_none());

        let (mut map, image, site) = fixture();
        map.entries.insert(
            code("synthetic", 7, BASE + 4),
            ["synthetic-fixture".into()].into(),
        );
        let alternate = analyzed(&map, &image, &site);
        assert!(analyzed_site(&alternate, &site).closed_proof.is_none());
    }

    #[test]
    fn invalid_delay_semantics_are_refused_but_jr_captures_before_slot_write() {
        let (map, mut image, site) = fixture();
        let mut missing_slot = site.clone();
        missing_slot.delay_slot = DelaySlot::None;
        let missing = analyzed(&map, &image, &missing_slot);
        assert!(
            analyzed_site(&missing, &missing_slot)
                .closed_proof
                .is_none()
        );

        image.words[3] = (9 << 26) | (8 << 16); // slot changes t0 after JR captures it
        let captured = analyzed(&map, &image, &site);
        let captured_site = analyzed_site(&captured, &site);
        assert!(verify(&captured, &image, &captured_site));
        assert!(
            captured_site
                .candidates
                .contains_key(&code("synthetic", 7, TARGET))
        );

        image.words[3] = 0x1000_0000; // a branch cannot occupy the delay slot
        let nested = analyzed(&map, &image, &site);
        assert!(analyzed_site(&nested, &site).closed_proof.is_none());
    }

    #[test]
    fn register_zero_and_return_address_are_not_tail_dispatch_registers() {
        let (map, mut image, site) = fixture();
        for register in [0, 31] {
            image.words[0] = lw(register, CELL as u16);
            image.words[2] = jr(register);
            let refused = analyzed(&map, &image, &site);
            assert!(analyzed_site(&refused, &site).closed_proof.is_none());
        }
    }

    #[test]
    fn immediate_interlocked_lw_jr_is_eligible() {
        let (map, mut image, old_site) = fixture();
        image.words[1] = jr(8);
        image.words[2] = 0;
        let mut site = old_site.clone();
        site.site.pc = GuestAddr(BASE + 4);
        let mut map = map;
        map.indirect_sites.clear();
        map.indirect_sites.insert(site.clone());

        let analyzed = analyze(&map, &image).unwrap();
        let site = analyzed_site(&analyzed, &site);
        let certificate = certificate(&MapIndex::new(&analyzed), &image, &site).unwrap();
        assert_eq!(certificate.load_pc, GuestAddr(BASE));
        assert!(verify(&analyzed, &image, &site));
    }

    #[test]
    fn slot_data_uses_the_placed_source_and_linked_targets_expand_to_copies() {
        let base = 0x4000;
        let mut words = vec![0; 65];
        words[0] = lw(8, 0x1100);
        words[1] = 0;
        words[2] = jr(8);
        words[3] = 0;
        words[4] = (9 << 26) | (2 << 16) | 1;
        words[64] = 0x1010; // linked target, resident word is at the placed cell
        let image = CodeImage {
            base: code("slot", 3, base),
            words,
            rom_offset: None,
            physical_start: None,
            holes: Vec::new(),
            slots: vec![(
                GuestRange {
                    start: GuestAddr(base),
                    size: 0x200,
                },
                0x1000,
                0x40,
            )],
        };
        let mut site = IndirectSite {
            site: code("slot", 3, base + 8),
            link_register: None,
            delay_slot: DelaySlot::Always,
            candidates: Default::default(),
            observed: Default::default(),
            closed_proof: None,
            evidence: Default::default(),
        };
        let mut map = ProgramMap::new(RomIdentity {
            sha256: "1".repeat(64),
            size: 64,
        });
        map.evidence.insert(
            "synthetic-slot-fixture".into(),
            Evidence {
                kind: EvidenceKind::TestOracle,
                producer: "synthetic-test".into(),
                revision: "0".into(),
                detail: "authored synthetic slot tail-cell fixture".into(),
            },
        );
        let references: EvidenceRefs = ["synthetic-slot-fixture".into()].into();
        site.evidence = references.clone();
        map.blocks.insert(BasicBlock {
            start: code("slot", 3, base),
            size: 16,
            delay_slot_entry: false,
            evidence: references.clone(),
        });
        map.blocks.insert(BasicBlock {
            start: code("slot", 3, base + 0x10),
            size: 4,
            delay_slot_entry: false,
            evidence: references,
        });
        map.indirect_sites.insert(site.clone());

        let analyzed = analyze(&map, &image).unwrap();
        let site = analyzed_site(&analyzed, &site);
        assert!(verify(&analyzed, &image, &site));
        assert_eq!(
            source_cell_range(&analyzed, &image, &site).unwrap().start,
            GuestAddr(base + 0x100)
        );
        assert_eq!(
            site.candidates.keys().cloned().collect::<BTreeSet<_>>(),
            [code("slot", 3, base + 0x10)].into()
        );
    }

    #[test]
    fn absent_cell_or_target_bytes_and_unmapped_targets_never_close() {
        let (map, mut image, site) = fixture();
        image.words.truncate(4);
        let missing_cell = analyzed(&map, &image, &site);
        assert!(analyzed_site(&missing_cell, &site).candidates.is_empty());

        let (map, mut image, site) = fixture();
        image.holes.push(GuestRange {
            start: GuestAddr(TARGET),
            size: 4,
        });
        let missing_target = analyzed(&map, &image, &site);
        assert!(analyzed_site(&missing_target, &site).candidates.is_empty());

        let (mut map, image, site) = fixture();
        map.blocks.retain(|block| block.start.pc.0 != TARGET);
        let unmapped = analyzed(&map, &image, &site);
        let site = analyzed_site(&unmapped, &site);
        assert!(site.candidates.contains_key(&code("synthetic", 7, TARGET)));
        assert!(site.closed_proof.is_none());
        assert!(!verify(&unmapped, &image, &site));
    }

    #[test]
    fn certificate_schema_rejects_unknown_fields() {
        let (map, image, site) = fixture();
        let analyzed = analyzed(&map, &image, &site);
        let site = analyzed_site(&analyzed, &site);
        let certificate = certificate(&MapIndex::new(&analyzed), &image, &site).unwrap();
        let mut value = serde_json::to_value(certificate).unwrap();
        value
            .as_object_mut()
            .unwrap()
            .insert("unknown".into(), serde_json::Value::Null);
        assert!(serde_json::from_value::<TailCellCertificate>(value).is_err());
    }
}
