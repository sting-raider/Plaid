//! Recheck retained ProgramMap facts against their complete DiscoveryTrace source.
//!
//! This authenticates typed source-event projections without parsing mutable
//! `Evidence.detail`, inferring provenance from equal values, or claiming the
//! trace sensors are complete hardware observations.

use crate::{
    EvidenceKind, GuestAddr,
    discovery::CodeImage,
    merge::{import_trace, import_trace_with_rom},
    program::{
        CodeAddress, ObservedDma, ObservedEntryVerification, ObservedIndirect, ObservedWordStore,
        PhysicalAddr, ProgramMap, RomOffset,
    },
    rom::{CanonicalRom, sha256},
    trace::{DiscoveryTrace, TraceEvent},
};
use std::collections::{BTreeMap, BTreeSet};

#[derive(Debug, Clone, PartialEq, Eq)]
enum PrimitiveWitness {
    Dma {
        rom_offset: RomOffset,
        physical_destination: PhysicalAddr,
        size: u32,
    },
    WordStore {
        site: GuestAddr,
        destination: GuestAddr,
        value: u32,
        generation: u64,
    },
    Indirect {
        site: GuestAddr,
        target: GuestAddr,
        delay_slot_pc: Option<GuestAddr>,
        generation: u64,
        source_unit: Option<String>,
    },
    EntryVerification {
        pc: GuestAddr,
        entry_generation: u64,
        register_mask: u32,
        source_unit: String,
        generation: u64,
    },
}

#[derive(Debug, Clone)]
struct UnitWitness {
    source_unit: String,
    generation: u64,
}

fn source_event_id(session: &str, seq: u64) -> String {
    format!("trace:{session}:{seq}")
}

fn record_use(
    expected: &BTreeMap<String, PrimitiveWitness>,
    seen: &mut BTreeMap<String, usize>,
    prefix: &str,
    refs: impl Iterator<Item = String>,
    actual: PrimitiveWitness,
) -> Result<(), String> {
    for id in refs {
        if !id.starts_with(prefix) {
            continue;
        }
        let Some(witness) = expected.get(&id) else {
            return Err(format!(
                "trace source event {id} is not a primitive event of the claimed role"
            ));
        };
        if witness != &actual {
            return Err(format!(
                "trace source event {id} does not match retained primitive semantics"
            ));
        }
        *seen.entry(id).or_default() += 1;
    }
    Ok(())
}

/// Authenticate the raw primitive projection of one complete discovery trace.
///
/// Facts from other trace sessions may coexist in `map`; only IDs belonging to
/// `trace` are checked. Every primitive event in this source session must appear
/// exactly once in its corresponding raw ProgramMap fact after canonicalization.
/// Generic derived facts may carry the same provenance without being another
/// primitive event.
pub fn verify_discovery_trace_projection(
    map: &ProgramMap,
    trace: &DiscoveryTrace,
) -> Result<(), String> {
    trace.validate()?;
    map.validate()?;
    if map.rom != trace.header.rom {
        return Err("ProgramMap and discovery trace use different canonical ROM identities".into());
    }

    let session = sha256(trace.to_ndjson()?.as_bytes());
    let prefix = format!("trace:{session}:");
    let mut expected = BTreeMap::<String, PrimitiveWitness>::new();
    let mut units = BTreeMap::<u64, UnitWitness>::new();
    let mut generation = 0u64;

    for event in &trace.events {
        let id = source_event_id(&session, event.seq);
        match &event.data {
            TraceEvent::CpuWordStoreObserved {
                site,
                destination,
                value,
            } => {
                expected.insert(
                    id,
                    PrimitiveWitness::WordStore {
                        site: *site,
                        destination: *destination,
                        value: *value,
                        generation,
                    },
                );
            }
            TraceEvent::RomDmaObserved {
                rom_offset,
                physical_destination,
                size,
            } => {
                expected.insert(
                    id,
                    PrimitiveWitness::Dma {
                        rom_offset: *rom_offset,
                        physical_destination: *physical_destination,
                        size: *size,
                    },
                );
            }
            TraceEvent::CompileBegin { unit, .. } => {
                units.insert(
                    *unit,
                    UnitWitness {
                        source_unit: id,
                        generation,
                    },
                );
            }
            TraceEvent::EntryBytesVerified {
                unit,
                pc,
                register_mask,
                ..
            } => {
                let unit = units
                    .get(unit)
                    .ok_or("validated trace lost entry-verification source unit")?;
                expected.insert(
                    id,
                    PrimitiveWitness::EntryVerification {
                        pc: *pc,
                        entry_generation: unit.generation,
                        register_mask: *register_mask,
                        source_unit: unit.source_unit.clone(),
                        generation,
                    },
                );
            }
            TraceEvent::IndirectTargetObserved {
                site,
                target,
                delay_slot_pc,
                source_unit,
            } => {
                expected.insert(
                    id,
                    PrimitiveWitness::Indirect {
                        site: *site,
                        target: *target,
                        delay_slot_pc: *delay_slot_pc,
                        generation,
                        source_unit: source_unit.map(|unit| {
                            units
                                .get(&unit)
                                .expect("validated trace indirect source unit")
                                .source_unit
                                .clone()
                        }),
                    },
                );
            }
            TraceEvent::Invalidate { .. } => {
                generation = generation
                    .checked_add(1)
                    .ok_or("trace generation overflow during source recheck")?;
            }
            TraceEvent::UnitCompiled { .. }
            | TraceEvent::EntryInstalled { .. }
            | TraceEvent::TargetLookup { .. }
            | TraceEvent::RuntimeLink { .. } => {}
        }
    }

    for id in expected.keys() {
        let evidence = map
            .evidence
            .get(id)
            .ok_or_else(|| format!("missing source trace evidence {id}"))?;
        if evidence.kind != EvidenceKind::Trace
            || evidence.producer != trace.header.engine
            || evidence.revision != trace.header.revision
        {
            return Err(format!("source trace evidence metadata mismatch for {id}"));
        }
    }

    let mut seen = BTreeMap::<String, usize>::new();
    for dma in &map.dma_observations {
        record_use(
            &expected,
            &mut seen,
            &prefix,
            dma.evidence.iter().cloned(),
            dma_witness(dma),
        )?;
    }
    for store in &map.word_store_observations {
        record_use(
            &expected,
            &mut seen,
            &prefix,
            store.evidence.iter().cloned(),
            store_witness(store),
        )?;
    }
    for indirect in &map.indirect_observations {
        record_use(
            &expected,
            &mut seen,
            &prefix,
            indirect.evidence.iter().cloned(),
            indirect_witness(indirect),
        )?;
    }
    for verification in &map.entry_verifications {
        record_use(
            &expected,
            &mut seen,
            &prefix,
            verification.evidence.iter().cloned(),
            verification_witness(verification),
        )?;
    }

    for id in expected.keys() {
        match seen.get(id).copied().unwrap_or(0) {
            1 => {}
            0 => {
                return Err(format!(
                    "source primitive event {id} is missing from ProgramMap"
                ));
            }
            count => {
                return Err(format!(
                    "source primitive event {id} appears in {count} raw ProgramMap facts"
                ));
            }
        }
    }
    Ok(())
}

/// Recheck raw trace primitives and exact EntryInstalled projections by
/// re-importing the same complete source with the same known image set.
pub fn verify_discovery_trace_projection_with_entries(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    map: &ProgramMap,
    budget: usize,
) -> Result<(), String> {
    verify_discovery_trace_projection(map, trace)?;
    let expected = import_trace(trace, known, budget)?;
    verify_entry_projection(trace, map, &expected)
}

/// ROM-backed counterpart for maps produced with `import_trace_with_rom`.
pub fn verify_discovery_trace_projection_with_entries_and_rom(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    rom: &CanonicalRom,
    map: &ProgramMap,
    budget: usize,
) -> Result<(), String> {
    verify_discovery_trace_projection(map, trace)?;
    let expected = import_trace_with_rom(trace, known, rom, budget)?;
    verify_entry_projection(trace, map, &expected)
}

fn entry_uses(map: &ProgramMap, id: &str) -> BTreeSet<CodeAddress> {
    map.entries
        .iter()
        .filter(|(_, refs)| refs.contains(id))
        .map(|(entry, _)| entry.clone())
        .collect()
}

fn verify_entry_projection(
    trace: &DiscoveryTrace,
    map: &ProgramMap,
    expected: &ProgramMap,
) -> Result<(), String> {
    if map.rom != trace.header.rom {
        return Err("entry-install source trace does not match ProgramMap ROM".into());
    }

    let session = sha256(trace.to_ndjson()?.as_bytes());
    for event in &trace.events {
        if !matches!(event.data, TraceEvent::EntryInstalled { .. }) {
            continue;
        }
        let id = source_event_id(&session, event.seq);
        let expected_evidence = expected
            .evidence
            .get(&id)
            .ok_or("re-import lost EntryInstalled evidence")?;
        if map.evidence.get(&id) != Some(expected_evidence) {
            return Err("EntryInstalled evidence disagrees with complete source trace".into());
        }

        let expected_entries = entry_uses(expected, &id);
        if expected_entries.len() != 1 {
            return Err("re-import produced ambiguous EntryInstalled projection".into());
        }
        if entry_uses(map, &id) != expected_entries {
            return Err(
                "EntryInstalled event is missing or bound to a different entry identity".into(),
            );
        }
    }
    Ok(())
}

fn dma_witness(dma: &ObservedDma) -> PrimitiveWitness {
    PrimitiveWitness::Dma {
        rom_offset: dma.rom_offset,
        physical_destination: dma.physical_destination,
        size: dma.size,
    }
}

fn store_witness(store: &ObservedWordStore) -> PrimitiveWitness {
    PrimitiveWitness::WordStore {
        site: store.site,
        destination: store.destination,
        value: store.value,
        generation: store.generation,
    }
}

fn indirect_witness(indirect: &ObservedIndirect) -> PrimitiveWitness {
    PrimitiveWitness::Indirect {
        site: indirect.site,
        target: indirect.target,
        delay_slot_pc: indirect.delay_slot_pc,
        generation: indirect.generation,
        source_unit: indirect.source_unit.clone(),
    }
}

fn verification_witness(verification: &ObservedEntryVerification) -> PrimitiveWitness {
    PrimitiveWitness::EntryVerification {
        pc: verification.entry.pc,
        entry_generation: verification.entry.generation,
        register_mask: verification.register_mask,
        source_unit: verification.source_unit.clone(),
        generation: verification.generation,
    }
}
