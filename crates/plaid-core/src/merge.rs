//! Facts union monotonically; contradictions produce diagnostics, never winners.
use crate::{
    EvidenceKind, GuestAddr,
    discovery::{CodeImage, direct_cfg},
    loads::{LoadObservation, record_load},
    program::*,
    rom::{CanonicalRom, sha256},
    trace::*,
};
use std::collections::{BTreeMap, BTreeSet};

trait Fact: Clone + Ord {
    fn refs(&mut self) -> &mut EvidenceRefs;
}
macro_rules! facts { ($($t:ty),*) => { $(impl Fact for $t { fn refs(&mut self) -> &mut EvidenceRefs { &mut self.evidence } })* }; }
facts!(
    ObservedDma,
    ObservedIndirect,
    ObservedTargetDispatch,
    ObservedWordStore,
    ObservedEntryVerification,
    ObservedFetch,
    Region,
    BasicBlock,
    DirectEdge,
    LoadMapping,
    Relocation,
    ExecutableWrite,
    Microcode,
    Unresolved
);

fn union<T: Fact>(left: &BTreeSet<T>, right: &BTreeSet<T>) -> BTreeSet<T> {
    let mut facts = BTreeMap::<T, EvidenceRefs>::new();
    for mut fact in left.iter().chain(right).cloned() {
        let refs = std::mem::take(fact.refs());
        facts.entry(fact).or_default().extend(refs);
    }
    facts
        .into_iter()
        .map(|(mut fact, refs)| {
            *fact.refs() = refs;
            fact
        })
        .collect()
}

fn canonicalize<T: Fact>(facts: &mut BTreeSet<T>) {
    *facts = union(facts, &BTreeSet::new());
}

pub fn merge_maps(left: &ProgramMap, right: &ProgramMap) -> Result<ProgramMap, String> {
    left.validate()?;
    right.validate()?;
    if left.rom != right.rom {
        return Err("cannot merge different canonical ROM identities".into());
    }
    let mut out = left.clone();
    for (id, e) in &right.evidence {
        if out.evidence.get(id).is_some_and(|old| old != e) {
            return Err(format!("conflicting provenance identity: {id}"));
        }
        out.evidence.insert(id.clone(), e.clone());
    }
    out.regions = union(&left.regions, &right.regions);
    out.blocks = union(&left.blocks, &right.blocks);
    out.direct_edges = union(&left.direct_edges, &right.direct_edges);
    out.loads = union(&left.loads, &right.loads);
    out.dma_observations = union(&left.dma_observations, &right.dma_observations);
    out.indirect_observations = union(&left.indirect_observations, &right.indirect_observations);
    out.target_dispatch_observations = union(
        &left.target_dispatch_observations,
        &right.target_dispatch_observations,
    );
    out.entry_verifications = union(&left.entry_verifications, &right.entry_verifications);
    out.fetch_observations = union(&left.fetch_observations, &right.fetch_observations);
    for (id, capture) in &right.fetch_captures {
        if out.fetch_captures.get(id).is_some_and(|old| old != capture) {
            return Err(format!("conflicting fetch capture identity: {id}"));
        }
        out.fetch_captures.insert(id.clone(), capture.clone());
    }
    out.word_store_observations = union(
        &left.word_store_observations,
        &right.word_store_observations,
    );
    out.relocations = union(&left.relocations, &right.relocations);
    out.executable_writes = union(&left.executable_writes, &right.executable_writes);
    out.rsp_microcodes = union(&left.rsp_microcodes, &right.rsp_microcodes);
    out.unresolved = union(&left.unresolved, &right.unresolved);
    for (a, f) in &right.runtime_functions {
        if out
            .runtime_functions
            .get(a)
            .is_some_and(|old| old.name != f.name)
        {
            return Err(format!(
                "conflicting runtime function name at {:08x}",
                a.pc.0
            ));
        }
        out.runtime_functions
            .entry(a.clone())
            .and_modify(|old| old.evidence.extend(f.evidence.clone()))
            .or_insert_with(|| f.clone());
    }
    for (id, spec) in &right.load_images {
        if out.load_images.get(id).is_some_and(|old| old != spec) {
            return Err(format!("conflicting load declarations for image {id}"));
        }
        out.load_images.insert(id.clone(), spec.clone());
    }
    if out.cop1_fr0 != right.cop1_fr0 {
        return Err("conflicting COP1 register mode declarations (Status.FR)".into());
    }
    for (a, refs) in &right.address_taken {
        out.address_taken
            .entry(a.clone())
            .or_default()
            .extend(refs.clone());
    }
    for (a, refs) in &right.entries {
        out.entries
            .entry(a.clone())
            .or_default()
            .extend(refs.clone());
    }
    for (id, o) in &right.overlays {
        if let Some(old) = out.overlays.get_mut(id) {
            let mut a = old.clone();
            a.evidence.clear();
            let mut b = o.clone();
            b.evidence.clear();
            if a != b {
                return Err(format!("conflicting overlay identity: {id}"));
            }
            old.evidence.extend(o.evidence.clone());
        } else {
            out.overlays.insert(id.clone(), o.clone());
        }
    }
    let mut indirect = BTreeMap::<IndirectSite, IndirectSite>::new();
    for s in left.indirect_sites.iter().chain(&right.indirect_sites) {
        let mut key = s.clone();
        key.evidence.clear();
        key.candidates.clear();
        key.observed.clear();
        key.closed_proof = None;
        let slot = indirect.entry(key).or_insert_with(|| {
            let mut s = s.clone();
            s.candidates.clear();
            s.observed.clear();
            s.evidence.clear();
            s
        });
        slot.evidence.extend(s.evidence.clone());
        for (a, refs) in &s.candidates {
            slot.candidates
                .entry(a.clone())
                .or_default()
                .extend(refs.clone());
        }
        for (a, refs) in &s.observed {
            slot.observed
                .entry(a.clone())
                .or_default()
                .extend(refs.clone());
        }
    }
    out.indirect_sites = indirect.into_values().collect();
    // An unproved observation does not contradict a static proof. Distinct
    // proof identities are retained as an explicit conflict for verification.
    out.indirect_sites = out
        .indirect_sites
        .into_iter()
        .map(|mut merged| {
            let proofs: BTreeSet<_> = left
                .indirect_sites
                .iter()
                .chain(&right.indirect_sites)
                .filter(|s| {
                    s.site == merged.site
                        && s.link_register == merged.link_register
                        && s.delay_slot == merged.delay_slot
                })
                .filter_map(|s| s.closed_proof.clone())
                .collect();
            merged.closed_proof = if proofs.len() == 1 {
                proofs.first().cloned()
            } else {
                None
            };
            if proofs.len() > 1 {
                out.unresolved.insert(Unresolved {
                    kind: "conflicting_indirect_proofs".into(),
                    site: Some(merged.site.clone()),
                    detail: "distinct closure certificates require reconciliation".into(),
                    evidence: proofs,
                });
            }
            merged
        })
        .collect();
    out.derived_entries.clear();
    for entry in left.entries.keys().chain(right.entries.keys()) {
        let left_present = left.entries.contains_key(entry);
        let right_present = right.entries.contains_key(entry);
        let left_sources = left.derived_entries.get(entry);
        let right_sources = right.derived_entries.get(entry);
        // An entry with no origin classification on either side is external or
        // unknown. Preserve that uncertainty across merge in either direction.
        if out.address_taken.contains_key(entry)
            || (left_present && left_sources.is_none())
            || (right_present && right_sources.is_none())
        {
            continue;
        }
        let sources: BTreeSet<_> = left_sources
            .into_iter()
            .chain(right_sources)
            .flat_map(|sources| sources.iter().cloned())
            .collect();
        if !sources.is_empty() {
            out.derived_entries.insert(entry.clone(), sources);
        }
    }
    // Multiple byte extents or direct destinations for an identical identity
    // remain visible. Different generations/images are intentionally distinct.
    // Index only the exact identity keys used by the quadratic conflict scan.
    // Every participating evidence reference is retained if a key has >1
    // semantic variant; no byte/value equality is consulted.
    let mut block_groups = BTreeMap::<CodeAddress, ((u32, bool), bool, EvidenceRefs)>::new();
    for block in &out.blocks {
        let signature = (block.size, block.delay_slot_entry);
        let slot = block_groups
            .entry(block.start.clone())
            .or_insert_with(|| (signature, false, EvidenceRefs::new()));
        if slot.0 != signature {
            slot.1 = true;
        }
        slot.2.extend(block.evidence.clone());
    }
    for (start, (_, conflicting, evidence)) in block_groups {
        if conflicting {
            out.unresolved.insert(Unresolved {
                kind: "conflicting_block".into(),
                site: Some(start),
                detail: "same execution identity has different block extent or entry semantics"
                    .into(),
                evidence,
            });
        }
    }
    let mut edge_groups =
        BTreeMap::<(CodeAddress, EdgeKind), ((CodeAddress, DelaySlot), bool, EvidenceRefs)>::new();
    for edge in &out.direct_edges {
        let signature = (edge.target.clone(), edge.delay_slot);
        let slot = edge_groups
            .entry((edge.site.clone(), edge.kind))
            .or_insert_with(|| (signature.clone(), false, EvidenceRefs::new()));
        if slot.0 != signature {
            slot.1 = true;
        }
        slot.2.extend(edge.evidence.clone());
    }
    for ((site, _), (_, conflicting, evidence)) in edge_groups {
        if conflicting {
            out.unresolved.insert(Unresolved {
                kind: "conflicting_direct_edge".into(),
                site: Some(site),
                detail: "same direct site/kind has contradictory target or slot semantics".into(),
                evidence,
            });
        }
    }
    // Diagnostics added after the initial union can repeat a semantic fact
    // with expanded provenance. Normalize those additions as well.
    canonicalize(&mut out.unresolved);
    out.validate()?;
    Ok(out)
}

/// Import a finite observed trace. Optional known images are matched by every
/// captured instruction word, never by PC alone. Invalidation advances an epoch.
pub fn import_trace(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    budget: usize,
) -> Result<ProgramMap, String> {
    import(trace, known, None, budget)
}

pub fn import_trace_with_rom(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    rom: &CanonicalRom,
    budget: usize,
) -> Result<ProgramMap, String> {
    if trace.header.rom != rom.identity {
        return Err("trace does not match canonical ROM".into());
    }
    import(trace, known, Some(rom), budget)
}

fn import(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    rom: Option<&CanonicalRom>,
    budget: usize,
) -> Result<ProgramMap, String> {
    trace.validate()?;
    let mut out = ProgramMap::new(trace.header.rom.clone());
    let session = sha256(trace.to_ndjson()?.as_bytes());
    let mut epoch = 0u64;
    let mut units = BTreeMap::new();
    let mut unit_images = BTreeMap::new();
    let mut recent = Vec::<CodeImage>::new();
    let mut observations = Vec::<PendingIndirect>::new();
    let mut transfers = Vec::<(u64, RomOffset, PhysicalAddr, u32)>::new();
    // Successful stores are causal writers even when they leave equal bytes.
    // Keep their trace order so a later store can revoke an older DMA origin.
    let mut word_stores = Vec::<(u64, PhysicalAddr, EvidenceRefs)>::new();
    for event in &trace.events {
        let id = format!("trace:{session}:{}", event.seq);
        let evidence: EvidenceRefs = [id.clone()].into();
        out.evidence.insert(
            id,
            Evidence {
                kind: EvidenceKind::Trace,
                producer: trace.header.engine.clone(),
                revision: trace.header.revision.clone(),
                detail: format!("session {session}, event {}: {:?}", event.seq, event.data),
            },
        );
        match &event.data {
            TraceEvent::CpuWordStoreObserved {
                site,
                destination,
                value,
            } => {
                out.word_store_observations.insert(ObservedWordStore {
                    site: *site,
                    destination: *destination,
                    value: *value,
                    generation: epoch,
                    evidence: evidence.clone(),
                });
                let physical = destination.0 & 0x1fffffff;
                word_stores.push((event.seq, PhysicalAddr(physical), evidence.clone()));
                if out.regions.iter().any(|r| {
                    r.physical_start.is_some_and(|p| {
                        u64::from(p.0) < u64::from(physical) + 4
                            && u64::from(physical) < u64::from(p.0) + u64::from(r.range.size)
                    })
                }) {
                    out.executable_writes.insert(ExecutableWrite {
                        range: Some(GuestRange {
                            start: *destination,
                            size: 4,
                        }),
                        kind: WriteKind::Unknown,
                        evidence,
                    });
                }
            }
            TraceEvent::RomDmaObserved {
                rom_offset,
                physical_destination,
                size,
            } => {
                transfers.push((event.seq, *rom_offset, *physical_destination, *size));
                out.dma_observations.insert(ObservedDma {
                    rom_offset: *rom_offset,
                    physical_destination: *physical_destination,
                    size: *size,
                    evidence,
                });
            }
            TraceEvent::CompileBegin {
                unit,
                start,
                physical_start,
                delay_slot_entry,
            } => {
                units.insert(
                    *unit,
                    (
                        *start,
                        *physical_start,
                        *delay_slot_entry,
                        epoch,
                        Vec::new(),
                        evidence,
                    ),
                );
            }
            TraceEvent::EntryInstalled {
                unit,
                pc,
                register_mask,
            } => {
                units.get_mut(unit).expect("validated trace unit").4.push((
                    *pc,
                    *register_mask,
                    evidence,
                ));
            }
            TraceEvent::UnitCompiled { unit, start, words } => {
                let state = units.get(unit).expect("validated trace unit");
                let matching: Vec<_> = known
                    .iter()
                    .filter(|i| {
                        words
                            .iter()
                            .enumerate()
                            .all(|(n, w)| i.word(GuestAddr(start.0 + n as u32 * 4)) == Some(*w))
                    })
                    .collect();
                let mut bytes = Vec::with_capacity(words.len() * 4);
                for w in words {
                    bytes.extend(w.to_be_bytes());
                }
                let (transfer, intervening_store_evidence, intervening_dma_evidence) =
                    if let Some(physical) = state.1 {
                        let compiled_end = u64::from(physical.0) + words.len() as u64 * 4;
                        if let Some((seq, offset, dest, _)) =
                            transfers.iter().rev().find(|(_, _, dest, size)| {
                                dest.0 <= physical.0
                                    && u64::from(dest.0) + u64::from(*size) >= compiled_end
                            })
                        {
                            let store_evidence: EvidenceRefs = word_stores
                                .iter()
                                .filter(|(store_seq, store, _)| {
                                    *store_seq > *seq
                                        && u64::from(store.0) < compiled_end
                                        && u64::from(physical.0) < u64::from(store.0) + 4
                                })
                                .flat_map(|(_, _, refs)| refs.iter().cloned())
                                .collect();
                            // A later partial DMA is also a writer. Selecting only
                            // covering transfers must not hide changes to a subset
                            // of the compiled span, even when payloads are equal.
                            let dma_evidence: EvidenceRefs = transfers
                                .iter()
                                .filter(|(later, _, destination, size)| {
                                    *later > *seq
                                        && u64::from(destination.0) < compiled_end
                                        && u64::from(physical.0)
                                            < u64::from(destination.0) + u64::from(*size)
                                })
                                .map(|(later, _, _, _)| format!("trace:{session}:{later}"))
                                .collect();
                            let transfer = (store_evidence.is_empty() && dma_evidence.is_empty())
                                .then(|| {
                                    (*seq, RomOffset(offset.0 + u64::from(physical.0 - dest.0)))
                                });
                            (transfer, store_evidence, dma_evidence)
                        } else {
                            (None, EvidenceRefs::new(), EvidenceRefs::new())
                        }
                    } else {
                        (None, EvidenceRefs::new(), EvidenceRefs::new())
                    };
                let source_tainted =
                    !intervening_store_evidence.is_empty() || !intervening_dma_evidence.is_empty();
                let dma_image = match (rom, transfer) {
                    (Some(rom), Some((dma_seq, offset))) => {
                        let mut mapped = CodeImage::from_rom(
                            rom,
                            offset,
                            GuestRange {
                                start: *start,
                                size: words.len() as u32 * 4,
                            },
                        )?;
                        out = record_load(
                            &out,
                            rom,
                            &LoadObservation {
                                rom_offset: offset,
                                destination: GuestRange {
                                    start: *start,
                                    size: words.len() as u32 * 4,
                                },
                                physical_start: state.1,
                                generation: state.3,
                                snapshot: bytes.clone(),
                                producer: trace.header.engine.clone(),
                                revision: trace.header.revision.clone(),
                                event: dma_seq,
                                copy_event: Some(format!("trace:{session}:{dma_seq}")),
                            },
                        )?;
                        if mapped.words == *words {
                            mapped.base.generation = state.3;
                            Some(mapped)
                        } else {
                            None
                        }
                    }
                    _ => None,
                };
                let base = if let Some(mapped) = &dma_image {
                    mapped.base.clone()
                } else if !source_tainted && state.3 == 0 && matching.len() == 1 {
                    matching[0].address(*start)
                } else {
                    CodeAddress {
                        pc: *start,
                        image: format!("trace-{}", sha256(&bytes)),
                        generation: state.3,
                    }
                };
                let image = CodeImage {
                    base: base.clone(),
                    words: words.clone(),
                    rom_offset: if let Some(mapped) = &dma_image {
                        mapped.rom_offset
                    } else if !source_tainted && matching.len() == 1 {
                        matching[0]
                            .rom_offset
                            .map(|o| RomOffset(o.0 + u64::from(start.0 - matching[0].base.pc.0)))
                    } else {
                        None
                    },
                    physical_start: state.1,
                    holes: Vec::new(),
                    slots: Vec::new(),
                };
                let refs: EvidenceRefs = evidence.union(&state.5).cloned().collect();
                let mut imported = ProgramMap::new(out.rom.clone());
                imported.evidence = out.evidence.clone();
                if !intervening_store_evidence.is_empty() {
                    imported.unresolved.insert(Unresolved {
                        kind: "intervening_executable_store".into(),
                        site: Some(base.clone()),
                        detail: "successful CPU store after candidate DMA overlaps compiled physical bytes; equal content cannot restore superseded copy provenance".into(),
                        evidence: intervening_store_evidence.clone(),
                    });
                }
                if !intervening_dma_evidence.is_empty() {
                    imported.unresolved.insert(Unresolved {
                        kind: "intervening_executable_dma".into(),
                        site: Some(base.clone()),
                        detail: "later partial DMA overlaps compiled physical bytes; an older covering copy cannot explain the current complete span".into(),
                        evidence: intervening_dma_evidence,
                    });
                }
                imported.regions.insert(Region {
                    image: base.image.clone(),
                    generation: base.generation,
                    range: GuestRange {
                        start: *start,
                        size: image.size()?,
                    },
                    rom_offset: image.rom_offset,
                    physical_start: image.physical_start,
                    overlay: None,
                    evidence: refs.clone(),
                });
                let entries: Vec<_> = state
                    .4
                    .iter()
                    .map(|(pc, _, _)| *pc)
                    .chain([*start])
                    .collect();
                for (pc, mask, refs) in &state.4 {
                    imported.entries.insert(image.address(*pc), refs.clone());
                    if *mask != 0 {
                        imported.unresolved.insert(Unresolved {
                            kind: "restricted_entry".into(),
                            site: Some(image.address(*pc)),
                            detail: format!(
                                "Mupen register-state entry mask {mask:08x} needs modeling"
                            ),
                            evidence: refs.clone(),
                        });
                    }
                }
                if state.2 {
                    imported.unresolved.insert(Unresolved {
                        kind: "delay_slot_entry".into(),
                        site: Some(base),
                        detail: "Mupen pagespan entry requires predecessor branch state".into(),
                        evidence: refs,
                    });
                } else {
                    let mut cfg = direct_cfg(out.rom.clone(), &image, &entries, budget)?.map;
                    // Every derived CFG fact retains both decoder and trace evidence.
                    for e in cfg.evidence.values_mut() {
                        e.detail.push_str(&format!(
                            "; input captured in trace session {session}, unit {unit}"
                        ));
                    }
                    // direct_cfg's evidence IDs must be unique per sensor unit.
                    cfg = namespace_static(cfg, &format!("{session}:{unit}"));
                    cfg.evidence.extend(out.evidence.clone());
                    cfg = add_provenance(cfg, &refs);
                    imported = merge_maps(&imported, &cfg)?;
                }
                if image.rom_offset.is_none() || (matching.len() != 1 && dma_image.is_none()) {
                    imported.unresolved.insert(Unresolved {
                        kind: "unknown_executable_source".into(),
                        site: Some(image.base.clone()),
                        detail: "observed bytes have no unique supplied ROM/load mapping".into(),
                        evidence: evidence.clone(),
                    });
                }
                out = merge_maps(&out, &imported)?;
                unit_images.insert(*unit, image.clone());
                recent.push(image);
            }
            TraceEvent::Invalidate { range } => {
                correlate_indirect(&mut out, &recent, &mut observations, epoch);
                epoch = epoch.checked_add(1).ok_or("trace generation overflow")?;
                out.executable_writes.insert(ExecutableWrite {
                    range: range.clone(),
                    kind: WriteKind::Unknown,
                    evidence,
                });
            }
            TraceEvent::EntryBytesVerified {
                unit,
                pc,
                register_mask,
                ..
            } => {
                let entry = unit_images[unit].address(*pc);
                out.entry_verifications.insert(ObservedEntryVerification {
                    entry: entry.clone(),
                    register_mask: *register_mask,
                    source_unit: units[unit]
                        .5
                        .first()
                        .expect("compile-begin evidence")
                        .clone(),
                    generation: epoch,
                    evidence: evidence.clone(),
                });
                // Explain only pending targets in this epoch. A lookup is not
                // execution and cannot attach itself to a future observation.
                for observation in &mut observations {
                    if observation.target == *pc {
                        observation
                            .verified_targets
                            .entry(entry.clone())
                            .or_default()
                            .extend(evidence.clone());
                    }
                }
            }
            TraceEvent::IndirectTargetObserved {
                site,
                target,
                delay_slot_pc,
                source_unit,
            } => {
                out.indirect_observations.insert(ObservedIndirect {
                    site: *site,
                    target: *target,
                    delay_slot_pc: *delay_slot_pc,
                    generation: epoch,
                    source_unit: source_unit.map(|unit| {
                        units[&unit]
                            .5
                            .first()
                            .expect("compile-begin evidence")
                            .clone()
                    }),
                    evidence: evidence.clone(),
                });
                // Freeze possible source identities at execution time. The
                // target's first compilation may follow this event; defer that
                // join until the epoch ends, never across an invalidation.
                // Explicit unit context can identify an older unit which is
                // still executing; it says nothing about the target's lifecycle.
                let explicit_source = source_unit.map(|unit| unit_images[&unit].address(*site));
                let sources = out
                    .indirect_sites
                    .iter()
                    .filter(|s| match &explicit_source {
                        Some(source) => s.site == *source,
                        None => s.site.pc == *site && s.site.generation == epoch,
                    })
                    .map(|s| s.site.clone())
                    .collect();
                observations.push(PendingIndirect {
                    sources,
                    target: *target,
                    verified_targets: BTreeMap::new(),
                    evidence,
                });
            }
            TraceEvent::TargetLookup {
                target,
                delay_slot_entry,
            } => {
                out.target_dispatch_observations
                    .insert(ObservedTargetDispatch {
                        target: *target,
                        generation: epoch,
                        kind: TargetDispatchKind::TargetLookup {
                            delay_slot_entry: *delay_slot_entry,
                        },
                        evidence: evidence.clone(),
                    });
                // Lookups never establish source-correlated indirect targets.
                out.unresolved.insert(Unresolved {
                    kind: "uncorrelated_target".into(),
                    site: None,
                    detail: format!("target {:08x} has no source-site correlation", target.0),
                    evidence,
                });
            }
            TraceEvent::RuntimeLink { target } => {
                out.target_dispatch_observations
                    .insert(ObservedTargetDispatch {
                        target: *target,
                        generation: epoch,
                        kind: TargetDispatchKind::RuntimeLink,
                        evidence: evidence.clone(),
                    });
                // Runtime links likewise lack a source-site identity.
                out.unresolved.insert(Unresolved {
                    kind: "uncorrelated_target".into(),
                    site: None,
                    detail: format!("target {:08x} has no source-site correlation", target.0),
                    evidence,
                });
            }
        }
    }
    correlate_indirect(&mut out, &recent, &mut observations, epoch);
    // Imports append sensor facts in execution order. Normalize once after
    // correlation, preserving every event ID without rescanning on each event.
    canonicalize(&mut out.dma_observations);
    canonicalize(&mut out.indirect_observations);
    canonicalize(&mut out.target_dispatch_observations);
    canonicalize(&mut out.entry_verifications);
    canonicalize(&mut out.word_store_observations);
    canonicalize(&mut out.executable_writes);
    canonicalize(&mut out.unresolved);
    out.validate()?;
    Ok(out)
}

struct PendingIndirect {
    sources: BTreeSet<CodeAddress>,
    target: GuestAddr,
    verified_targets: BTreeMap<CodeAddress, EvidenceRefs>,
    evidence: EvidenceRefs,
}

fn correlate_indirect(
    out: &mut ProgramMap,
    images: &[CodeImage],
    pending: &mut Vec<PendingIndirect>,
    epoch: u64,
) {
    for observation in pending.drain(..) {
        let mut targets: BTreeSet<_> = images
            .iter()
            .filter(|image| {
                image.base.generation == epoch && image.word(observation.target).is_some()
            })
            .map(|image| image.address(observation.target))
            .collect();
        targets.extend(observation.verified_targets.keys().cloned());
        if observation.sources.len() == 1 && targets.len() == 1 {
            let source = observation.sources.first().expect("one source");
            let sites: Vec<_> = out
                .indirect_sites
                .iter()
                .filter(|s| &s.site == source)
                .cloned()
                .collect();
            if sites.len() == 1 {
                let mut site = sites[0].clone();
                out.indirect_sites.remove(&site);
                let target = targets.first().expect("one target");
                let refs = site.observed.entry(target.clone()).or_default();
                refs.extend(observation.evidence);
                if let Some(verification) = observation.verified_targets.get(target) {
                    refs.extend(verification.clone());
                }
                out.indirect_sites.insert(site);
                continue;
            }
        }
        out.unresolved.insert(Unresolved {
            kind: "uncorrelated_indirect_observation".into(),
            site: if observation.sources.len() == 1 { observation.sources.first().cloned() } else { None },
            detail: format!("no unique decoded source/target identity for observed target {:?} in epoch {epoch}", observation.target),
            evidence: observation.evidence,
        });
    }
}

fn add_provenance(mut p: ProgramMap, refs: &EvidenceRefs) -> ProgramMap {
    // The trace evidence records are already in the surrounding importer map.
    let extend = |old: &mut EvidenceRefs| old.extend(refs.clone());
    p.regions = p
        .regions
        .into_iter()
        .map(|mut x| {
            extend(&mut x.evidence);
            x
        })
        .collect();
    p.blocks = p
        .blocks
        .into_iter()
        .map(|mut x| {
            extend(&mut x.evidence);
            x
        })
        .collect();
    p.direct_edges = p
        .direct_edges
        .into_iter()
        .map(|mut x| {
            extend(&mut x.evidence);
            x
        })
        .collect();
    p.indirect_sites = p
        .indirect_sites
        .into_iter()
        .map(|mut x| {
            extend(&mut x.evidence);
            x
        })
        .collect();
    p.unresolved = p
        .unresolved
        .into_iter()
        .map(|mut x| {
            extend(&mut x.evidence);
            x
        })
        .collect();
    for e in p.entries.values_mut() {
        extend(e);
    }
    p
}

fn namespace_static(mut p: ProgramMap, prefix: &str) -> ProgramMap {
    let replacements: BTreeMap<_, _> = p
        .evidence
        .keys()
        .map(|id| (id.clone(), format!("{prefix}:{id}")))
        .collect();
    let rewrite = |refs: &mut EvidenceRefs| {
        *refs = refs
            .iter()
            .map(|id| replacements.get(id).unwrap_or(id).clone())
            .collect();
    };
    p.evidence = p
        .evidence
        .into_iter()
        .map(|(id, e)| (replacements[&id].clone(), e))
        .collect();
    p.regions = p
        .regions
        .into_iter()
        .map(|mut x| {
            rewrite(&mut x.evidence);
            x
        })
        .collect();
    p.blocks = p
        .blocks
        .into_iter()
        .map(|mut x| {
            rewrite(&mut x.evidence);
            x
        })
        .collect();
    p.direct_edges = p
        .direct_edges
        .into_iter()
        .map(|mut x| {
            rewrite(&mut x.evidence);
            x
        })
        .collect();
    p.indirect_sites = p
        .indirect_sites
        .into_iter()
        .map(|mut x| {
            rewrite(&mut x.evidence);
            x
        })
        .collect();
    p.unresolved = p
        .unresolved
        .into_iter()
        .map(|mut x| {
            rewrite(&mut x.evidence);
            x
        })
        .collect();
    for e in p.entries.values_mut() {
        rewrite(e);
    }
    p
}
