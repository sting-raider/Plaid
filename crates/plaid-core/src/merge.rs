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
    ObservedWordStore,
    ObservedEntryVerification,
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
    out.entry_verifications = union(&left.entry_verifications, &right.entry_verifications);
    out.word_store_observations = union(
        &left.word_store_observations,
        &right.word_store_observations,
    );
    out.relocations = union(&left.relocations, &right.relocations);
    out.executable_writes = union(&left.executable_writes, &right.executable_writes);
    out.rsp_microcodes = union(&left.rsp_microcodes, &right.rsp_microcodes);
    out.unresolved = union(&left.unresolved, &right.unresolved);
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
    // Multiple byte extents or direct destinations for an identical identity
    // remain visible. Different generations/images are intentionally distinct.
    for a in &out.blocks {
        for b in &out.blocks {
            if a.start == b.start && (a.size != b.size || a.delay_slot_entry != b.delay_slot_entry)
            {
                let evidence = a.evidence.union(&b.evidence).cloned().collect();
                out.unresolved.insert(Unresolved {
                    kind: "conflicting_block".into(),
                    site: Some(a.start.clone()),
                    detail: "same execution identity has different block extent or entry semantics"
                        .into(),
                    evidence,
                });
            }
        }
    }
    for a in &out.direct_edges {
        for b in &out.direct_edges {
            if a.site == b.site
                && a.kind == b.kind
                && (a.target != b.target || a.delay_slot != b.delay_slot)
            {
                out.unresolved.insert(Unresolved {
                    kind: "conflicting_direct_edge".into(),
                    site: Some(a.site.clone()),
                    detail: "same direct site/kind has contradictory target or slot semantics"
                        .into(),
                    evidence: a.evidence.union(&b.evidence).cloned().collect(),
                });
            }
        }
    }
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
                let transfer = state.1.and_then(|physical| {
                    transfers
                        .iter()
                        .rev()
                        .find(|(_, _, dest, size)| {
                            dest.0 <= physical.0
                                && u64::from(dest.0) + u64::from(*size)
                                    >= u64::from(physical.0) + words.len() as u64 * 4
                        })
                        .map(|(seq, offset, dest, _)| {
                            (*seq, RomOffset(offset.0 + u64::from(physical.0 - dest.0)))
                        })
                });
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
                } else if state.3 == 0 && matching.len() == 1 {
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
                    } else if matching.len() == 1 {
                        matching[0]
                            .rom_offset
                            .map(|o| RomOffset(o.0 + u64::from(start.0 - matching[0].base.pc.0)))
                    } else {
                        None
                    },
                    physical_start: state.1,
                };
                let refs: EvidenceRefs = evidence.union(&state.5).cloned().collect();
                let mut imported = ProgramMap::new(out.rom.clone());
                imported.evidence = out.evidence.clone();
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
            TraceEvent::TargetLookup { target, .. } | TraceEvent::RuntimeLink { target } => {
                // Lookups never establish source-correlated indirect targets.
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
