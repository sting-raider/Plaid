//! Closure of a declared finite CFG is distinct from whole-ROM native readiness.
use crate::{
    discovery::{CodeImage, decode, direct_cfg},
    indirect::verify_constant,
    program::*,
    rom::sha256,
};
use serde::Serialize;
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    WholeRom,
    DeclaredStaticImages,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ClosureStatus {
    Open,
    Closed,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Serialize)]
pub struct Blocker {
    pub kind: String,
    pub site: Option<CodeAddress>,
    pub detail: String,
    pub evidence: EvidenceRefs,
}

#[derive(Debug, Clone, Serialize)]
pub struct SolveReport {
    pub schema_version: u32,
    pub scope: Scope,
    pub status: ClosureStatus,
    /// Discovery is necessary but insufficient for a verified native package.
    pub native_complete: bool,
    pub assumptions: Vec<String>,
    pub blockers: BTreeSet<Blocker>,
    pub discharged: BTreeSet<Unresolved>,
}

fn source<'a>(images: &'a [CodeImage], address: &CodeAddress) -> Option<&'a CodeImage> {
    let mut found = images.iter().filter(|i| {
        i.base.image == address.image
            && i.base.generation == address.generation
            && i.word(address.pc).is_some()
    });
    let first = found.next()?;
    if found.next().is_some() {
        return None;
    }
    Some(first)
}

fn content_digest_claim(image: &str) -> Option<&str> {
    let digest = image.strip_prefix("trace-").unwrap_or(image);
    (digest.len() == 64
        && digest
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)))
    .then_some(digest)
}

fn content_digest(image: &CodeImage) -> String {
    let mut bytes = Vec::with_capacity(image.words.len() * 4);
    for word in &image.words {
        bytes.extend(word.to_be_bytes());
    }
    sha256(&bytes)
}

fn conflicting_region_provenance(a: &Region, b: &Region) -> Option<CodeAddress> {
    if a.image != b.image || a.generation != b.generation {
        return None;
    }
    let overlap_start = u64::from(a.range.start.0).max(u64::from(b.range.start.0));
    let overlap_end = a.range.end().min(b.range.end());
    if overlap_start >= overlap_end {
        return None;
    }
    let a_delta = overlap_start - u64::from(a.range.start.0);
    let b_delta = overlap_start - u64::from(b.range.start.0);
    let rom_conflict = match (a.rom_offset, b.rom_offset) {
        (Some(a_offset), Some(b_offset)) => a_offset.0 + a_delta != b_offset.0 + b_delta,
        _ => false,
    };
    let physical_conflict = match (a.physical_start, b.physical_start) {
        (Some(a_start), Some(b_start)) => {
            u64::from(a_start.0) + a_delta != u64::from(b_start.0) + b_delta
        }
        _ => false,
    };
    (rom_conflict || physical_conflict).then_some(CodeAddress {
        pc: crate::GuestAddr(overlap_start as u32),
        image: a.image.clone(),
        generation: a.generation,
    })
}

fn supplied_region_provenance_conflict(
    image: &CodeImage,
    region: &Region,
    pc: crate::GuestAddr,
) -> bool {
    let Some(image_delta) = pc.0.checked_sub(image.base.pc.0) else {
        return false;
    };
    let Some(region_delta) = pc.0.checked_sub(region.range.start.0) else {
        return false;
    };
    let rom_conflict = match (image.rom_offset, region.rom_offset) {
        (Some(image_offset), Some(region_offset)) => {
            image_offset.0.checked_add(u64::from(image_delta))
                != region_offset.0.checked_add(u64::from(region_delta))
        }
        _ => false,
    };
    let physical_conflict = match (image.physical_start, region.physical_start) {
        (Some(image_start), Some(region_start)) => {
            u64::from(image_start.0) + u64::from(image_delta)
                != u64::from(region_start.0) + u64::from(region_delta)
        }
        _ => false,
    };
    rom_conflict || physical_conflict
}

fn static_identity_blockers(
    map: &ProgramMap,
    images: &[CodeImage],
    scope: Scope,
) -> BTreeSet<Blocker> {
    let mut blockers = BTreeSet::new();

    // Production image constructors currently use raw SHA-256 identities for
    // ROM/load images and `trace-<SHA-256>` for trace-only images. Opaque v0
    // labels remain compatible until CodeImage grows a mandatory content digest.
    for image in images {
        if let Some(claimed) = content_digest_claim(&image.base.image)
            && content_digest(image) != claimed
        {
            blockers.insert(Blocker {
                kind: "instruction_source_identity_mismatch".into(),
                site: Some(image.base.clone()),
                detail:
                    "supplied instruction bytes do not match their content-derived image identity"
                        .into(),
                evidence: EvidenceRefs::new(),
            });
        }
    }

    // Fragment boundaries cannot hide two values for one exact execution
    // identity and guest PC. Check supplied words before selecting block roots.
    let mut words: BTreeMap<(&str, u64, u32), u32> = BTreeMap::new();
    for image in images {
        for (index, word) in image.words.iter().copied().enumerate() {
            let pc = crate::GuestAddr(image.base.pc.0 + (index as u32) * 4);
            let key = (image.base.image.as_str(), image.base.generation, pc.0);
            if let Some(previous) = words.get(&key) {
                if *previous != word {
                    let site = image.address(pc);
                    let evidence = map
                        .regions
                        .iter()
                        .filter(|region| {
                            region.image == site.image
                                && region.generation == site.generation
                                && region.range.contains(site.pc)
                        })
                        .flat_map(|region| region.evidence.iter().cloned())
                        .collect();
                    blockers.insert(Blocker {
                        kind: "conflicting_instruction_sources".into(),
                        site: Some(site),
                        detail: "supplied CodeImage fragments disagree on bytes for one execution identity"
                            .into(),
                        evidence,
                    });
                }
            } else {
                words.insert(key, word);
            }
        }
    }

    if scope != Scope::DeclaredStaticImages {
        return blockers;
    }

    // Two distinct immutable identities cannot simultaneously own the same
    // decoded guest instruction bytes without a mapping/lifetime selector.
    let blocks: Vec<_> = map.blocks.iter().collect();
    for (index, a) in blocks.iter().enumerate() {
        for b in &blocks[index + 1..] {
            if a.start.image == b.start.image && a.start.generation == b.start.generation {
                continue;
            }
            let a_start = u64::from(a.start.pc.0);
            let a_end = a_start + u64::from(a.size);
            let b_start = u64::from(b.start.pc.0);
            let b_end = b_start + u64::from(b.size);
            if a_start < b_end && b_start < a_end {
                blockers.insert(Blocker {
                    kind: "ambiguous_guest_executable_identity".into(),
                    site: None,
                    detail: "distinct decoded executable image/generation identities overlap guest address space; mapping/lifetime selection is unproven"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
            }
        }
    }

    // Region rows are independent observations. For one identity, all
    // simultaneously-known affine backing facts must agree over their guest
    // intersection. Across identities, overlapping known physical backing needs
    // an alias/lifetime relation; absent backing remains unknown rather than
    // being inferred from virtual address shape or equal payloads.
    let regions: Vec<_> = map.regions.iter().collect();
    for (index, a) in regions.iter().enumerate() {
        for b in &regions[index + 1..] {
            if a.image == b.image && a.generation == b.generation {
                if let Some(site) = conflicting_region_provenance(a, b) {
                    blockers.insert(Blocker {
                        kind: "conflicting_region_provenance".into(),
                        site: Some(site),
                        detail: "overlapping regions for one executable identity assert incompatible ROM or physical backing"
                            .into(),
                        evidence: a.evidence.union(&b.evidence).cloned().collect(),
                    });
                }
                continue;
            }

            let (Some(a_physical), Some(b_physical)) = (a.physical_start, b.physical_start) else {
                continue;
            };
            let a_start = u64::from(a_physical.0);
            let a_end = a_start + u64::from(a.range.size);
            let b_start = u64::from(b_physical.0);
            let b_end = b_start + u64::from(b.range.size);
            if a_start < b_end && b_start < a_end {
                blockers.insert(Blocker {
                    kind: "ambiguous_physical_executable_identity".into(),
                    site: None,
                    detail: "distinct executable image/generation identities overlap explicit physical backing; alias/lifetime equivalence is unproven"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
            }
        }
    }

    blockers
}

fn allowed_static_effect(word: u32, pc: crate::GuestAddr) -> bool {
    let i = decode(word, pc);
    if !i.is_valid() || i.is_trap() || i.is_float() {
        return false;
    }
    if i.is_branch() {
        return matches!(word >> 26, 1 | 4..=7 | 20..=23);
    }
    if i.is_jump() {
        return matches!(word >> 26, 2 | 3) || (word >> 26 == 0 && matches!(word & 63, 8 | 9));
    }
    match word >> 26 {
        9 | 12 | 13 | 14 | 15 | 25 => true,
        0 => matches!(word & 63, 0 | 2 | 3 | 33 | 35 | 36 | 37 | 38 | 39 | 45),
        _ => false,
    }
}

pub fn solve(map: &ProgramMap, images: &[CodeImage], scope: Scope) -> Result<SolveReport, String> {
    map.validate()?;
    for image in images {
        GuestRange {
            start: image.base.pc,
            size: image.size()?,
        }
        .validate(true)?;
    }
    let mut blockers = static_identity_blockers(map, images, scope);
    let mut discharged = BTreeSet::new();
    let mut add = |kind: &str, site: Option<CodeAddress>, detail: &str, evidence: EvidenceRefs| {
        blockers.insert(Blocker {
            kind: kind.into(),
            site,
            detail: detail.into(),
            evidence,
        });
    };
    let starts: BTreeSet<_> = map
        .blocks
        .iter()
        .filter(|b| !b.delay_slot_entry)
        .map(|b| b.start.clone())
        .collect();
    if !map.fetch_observations.is_empty() {
        add(
            "fetch_execution_identity_unknown",
            None,
            "raw fetched words have no established image generation, lifetime or retirement identity",
            map.fetch_observations
                .iter()
                .flat_map(|f| f.evidence.clone())
                .collect(),
        );
    }
    if map.entries.is_empty() {
        add(
            "missing_entry_universe",
            None,
            "no executable roots are declared",
            EvidenceRefs::new(),
        );
    }
    for (entry, refs) in &map.entries {
        if !starts.contains(entry) {
            add(
                "missing_entry_block",
                Some(entry.clone()),
                "entry has no normal decoded block",
                refs.clone(),
            );
        }
    }
    for b in &map.blocks {
        if b.delay_slot_entry {
            add(
                "unsupported_delay_slot_entry",
                Some(b.start.clone()),
                "special predecessor state is not modeled",
                b.evidence.clone(),
            );
        }
        let Some(image) = source(images, &b.start) else {
            add(
                "missing_instruction_source",
                Some(b.start.clone()),
                "no unique instruction image supplied for this block",
                b.evidence.clone(),
            );
            continue;
        };
        let range = GuestRange {
            start: b.start.pc,
            size: b.size,
        };
        for offset in (0..b.size).step_by(4) {
            let pc = crate::GuestAddr(b.start.pc.0 + offset);
            let Some(word) = image.word(pc) else {
                add(
                    "missing_instruction_source",
                    Some(image.address(pc)),
                    "block extends beyond supplied instruction bytes",
                    b.evidence.clone(),
                );
                continue;
            };
            if scope == Scope::DeclaredStaticImages && !allowed_static_effect(word, pc) {
                add(
                    "unsupported_scope_effect",
                    Some(image.address(pc)),
                    "declared immutable integer scope excludes memory, COP, trapping and unsupported effects",
                    b.evidence.clone(),
                );
            }
        }
        let covering_regions: Vec<_> = map
            .regions
            .iter()
            .filter(|r| {
                r.image == b.start.image
                    && r.generation == b.start.generation
                    && r.range.start.0 <= b.start.pc.0
                    && r.range.end() >= range.end()
            })
            .collect();
        if covering_regions.is_empty() {
            add(
                "unknown_executable_region",
                Some(b.start.clone()),
                "block is not contained by a matching executable region",
                b.evidence.clone(),
            );
        } else {
            for region in covering_regions {
                if supplied_region_provenance_conflict(image, region, b.start.pc) {
                    add(
                        "supplied_image_provenance_conflict",
                        Some(b.start.clone()),
                        "supplied instruction image contradicts explicit executable Region provenance",
                        region.evidence.clone(),
                    );
                }
            }
        }
    }
    for edge in &map.direct_edges {
        if !map.blocks.iter().any(|b| {
            b.start.image == edge.site.image
                && b.start.generation == edge.site.generation
                && GuestRange {
                    start: b.start.pc,
                    size: b.size,
                }
                .contains(edge.site.pc)
        }) {
            add(
                "unmapped_direct_site",
                Some(edge.site.clone()),
                "edge source is outside all decoded blocks",
                edge.evidence.clone(),
            );
        }
        if !starts.contains(&edge.target) {
            add(
                "unresolved_direct_target",
                Some(edge.site.clone()),
                &format!("no decoded block at target {:?}", edge.target),
                edge.evidence.clone(),
            );
        }
    }
    for site in &map.indirect_sites {
        let proof_valid =
            source(images, &site.site).is_some_and(|image| verify_constant(map, image, site));
        if !proof_valid {
            add(
                "unresolved_indirect_site",
                Some(site.site.clone()),
                "finite candidates or samples are insufficient; no rechecked closed-target certificate",
                site.evidence.clone(),
            );
        }
        for target in site.candidates.keys().chain(site.observed.keys()) {
            if !starts.contains(target) {
                add(
                    "unresolved_indirect_target",
                    Some(site.site.clone()),
                    &format!("candidate/observed target {:?} has no block", target),
                    site.evidence.clone(),
                );
            }
        }
        // Candidate hypotheses may be incomplete, including an empty set.
        // Only a claimed exhaustive set can contradict execution evidence.
        // Rechecking still rejects a certificate with an out-of-set sample.
        if site.closed_proof.is_some()
            && site
                .observed
                .keys()
                .any(|a| !site.candidates.contains_key(a))
        {
            add(
                "indirect_evidence_disagreement",
                Some(site.site.clone()),
                "observed target is outside the claimed closed target set",
                site.evidence.clone(),
            );
        }
    }
    // Re-derive instruction control flow. A hand-edited/partial map cannot close
    // merely by deleting its missing edges or indirect sites.
    for image in images {
        let roots: BTreeSet<_> = starts
            .iter()
            .chain(map.entries.keys())
            .filter(|a| {
                a.image == image.base.image
                    && a.generation == image.base.generation
                    && image.word(a.pc).is_some()
            })
            .map(|a| a.pc)
            .collect();
        if roots.is_empty() {
            continue;
        }
        let expected = direct_cfg(
            map.rom.clone(),
            image,
            &roots.into_iter().collect::<Vec<_>>(),
            image.words.len(),
        )?
        .map;
        let provenance: EvidenceRefs = map
            .regions
            .iter()
            .filter(|r| r.image == image.base.image && r.generation == image.base.generation)
            .flat_map(|r| r.evidence.iter().cloned())
            .collect();
        for edge in &expected.direct_edges {
            if !map.direct_edges.iter().any(|e| {
                e.site == edge.site
                    && e.target == edge.target
                    && e.kind == edge.kind
                    && e.delay_slot == edge.delay_slot
            }) {
                add(
                    "missing_decoded_edge",
                    Some(edge.site.clone()),
                    "instruction bytes require a direct edge absent from the map",
                    provenance.clone(),
                );
            }
        }
        for site in &expected.indirect_sites {
            if !map.indirect_sites.iter().any(|s| {
                s.site == site.site
                    && s.link_register == site.link_register
                    && s.delay_slot == site.delay_slot
            }) {
                add(
                    "missing_decoded_indirect_site",
                    Some(site.site.clone()),
                    "instruction bytes require an indirect site absent from the map",
                    provenance.clone(),
                );
            }
        }
        for b in &expected.blocks {
            if !map.blocks.iter().any(|old| {
                old.start == b.start
                    && old.size == b.size
                    && old.delay_slot_entry == b.delay_slot_entry
            }) {
                add(
                    "missing_decoded_block",
                    Some(b.start.clone()),
                    "reachable instruction bytes require a block/extent absent from the map",
                    provenance.clone(),
                );
            }
        }
        for b in &map.blocks {
            if b.start.image == image.base.image
                && b.start.generation == image.base.generation
                && image.word(b.start.pc).is_some()
                && !expected.blocks.iter().any(|e| {
                    e.start == b.start
                        && e.size == b.size
                        && e.delay_slot_entry == b.delay_slot_entry
                })
            {
                add(
                    "unexpected_block_extent",
                    Some(b.start.clone()),
                    "declared block disagrees with re-derived block boundaries",
                    b.evidence.clone(),
                );
            }
        }
        for edge in &map.direct_edges {
            if edge.site.image == image.base.image
                && edge.site.generation == image.base.generation
                && image.word(edge.site.pc).is_some()
                && !expected.direct_edges.iter().any(|e| {
                    e.site == edge.site
                        && e.target == edge.target
                        && e.kind == edge.kind
                        && e.delay_slot == edge.delay_slot
                })
            {
                add(
                    "unexpected_decoded_edge",
                    Some(edge.site.clone()),
                    "declared direct edge contradicts instruction-derived control flow",
                    edge.evidence.clone(),
                );
            }
        }
        for u in &expected.unresolved {
            if !(u.kind == "unmapped_target" && u.site.as_ref().is_some_and(|a| starts.contains(a)))
            {
                add(&u.kind, u.site.clone(), &u.detail, provenance.clone());
            }
        }
    }
    for u in &map.unresolved {
        if u.kind == "unmapped_target" && u.site.as_ref().is_some_and(|a| starts.contains(a)) {
            discharged.insert(u.clone());
        } else {
            add(&u.kind, u.site.clone(), &u.detail, u.evidence.clone());
        }
    }
    for o in map.overlays.values() {
        add(
            "unresolved_overlay_lifecycle",
            None,
            if o.candidate {
                "overlay is a candidate; load/unload/relocation policy is unproven"
            } else {
                "overlay lifecycle certificate verifier is not implemented"
            },
            o.evidence.clone(),
        );
    }
    for r in &map.relocations {
        add(
            "unverified_relocation",
            Some(r.site.clone()),
            "relocation semantics certificate verifier is not implemented",
            r.evidence.clone(),
        );
    }
    for w in &map.executable_writes {
        add(
            "unresolved_executable_write",
            None,
            &format!(
                "{:?} event needs a complete executable modification policy",
                w.kind
            ),
            w.evidence.clone(),
        );
    }
    if scope == Scope::DeclaredStaticImages
        && (!map.loads.is_empty()
            || !map.dma_observations.is_empty()
            || !map.rsp_microcodes.is_empty())
    {
        add(
            "dynamic_effect_outside_scope",
            None,
            "declared static scope cannot include loads or RSP execution",
            EvidenceRefs::new(),
        );
    }
    if scope == Scope::WholeRom {
        for (kind, detail) in [
            (
                "unproven_executable_universe",
                "whole-ROM executable roots, boot and mapping universe have no verified closure certificate",
            ),
            (
                "unmodeled_exception_paths",
                "exception/interrupt entry coverage and dispatch are unproven",
            ),
            (
                "unproven_load_overlay_policy",
                "all future executable DMA, copies, overlays and relocations are unproven",
            ),
            (
                "unproven_executable_write_policy",
                "absence or complete representation of future executable writes is unproven",
            ),
            (
                "unproven_rsp_policy",
                "required RSP microcode execution identities and coverage are unproven",
            ),
            (
                "unsupported_execution_modes",
                "full R4300 execution/address/TLB modes are not represented by v0",
            ),
        ] {
            add(kind, None, detail, EvidenceRefs::new());
        }
    }
    let assumptions = if scope == Scope::DeclaredStaticImages {
        vec![
            "Only explicitly declared image entries execute; code bytes stay immutable.".into(),
            "Interrupts, exceptions, DMA, MMIO, overlays, RSP and external entry sources are excluded."
                .into(),
            "32-bit guest address compatibility model and the supported integer/control-flow subset only."
                .into(),
        ]
    } else {
        Vec::new()
    };
    Ok(SolveReport {
        schema_version: 0,
        scope,
        status: if blockers.is_empty() {
            ClosureStatus::Closed
        } else {
            ClosureStatus::Open
        },
        native_complete: false,
        assumptions,
        blockers,
        discharged,
    })
}
