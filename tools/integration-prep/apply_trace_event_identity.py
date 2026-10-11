#!/usr/bin/env python3
from pathlib import Path

path = Path("crates/plaid-core/src/program.rs")
text = path.read_text()
if "fn validate_trace_event_identities(map: &ProgramMap)" in text:
    raise SystemExit(0)

marker = "/// Raw source-correlated execution evidence survives missing/ambiguous image\n"
if marker not in text:
    raise SystemExit("program.rs insertion marker not found")

helper = r'''#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PrimitiveTraceRole {
    DmaCopy,
    WordStoreEvent,
    IndirectEvent,
    EntryVerificationEvent,
    SourceUnit,
}

fn validate_trace_event_identities(map: &ProgramMap) -> Result<(), String> {
    let is_trace = |id: &str| {
        map.evidence
            .get(id)
            .is_some_and(|e| e.kind == EvidenceKind::Trace)
    };
    let mut roles = BTreeMap::<String, PrimitiveTraceRole>::new();
    let mut claim_role = |id: &str, role: PrimitiveTraceRole| -> Result<(), String> {
        if is_trace(id)
            && roles
                .insert(id.to_string(), role)
                .is_some_and(|old| old != role)
        {
            return Err("trace evidence reused across incompatible primitive roles".into());
        }
        Ok(())
    };

    let mut dma_events = BTreeMap::<String, (RomOffset, PhysicalAddr, u32)>::new();
    for load in &map.loads {
        let Some(copy) = &load.copy_event else {
            continue;
        };
        claim_role(copy, PrimitiveTraceRole::DmaCopy)?;
        for dma in map
            .dma_observations
            .iter()
            .filter(|dma| dma.evidence.contains(copy))
        {
            let semantics = (dma.rom_offset, dma.physical_destination, dma.size);
            if dma_events
                .insert(copy.clone(), semantics)
                .is_some_and(|old| old != semantics)
            {
                return Err("load copy event has conflicting observed DMA identity".into());
            }
        }
    }

    let mut store_events = BTreeMap::<String, (GuestAddr, GuestAddr, u32, u64)>::new();
    for store in &map.word_store_observations {
        let semantics = (
            store.site,
            store.destination,
            store.value,
            store.generation,
        );
        for id in &store.evidence {
            if !is_trace(id) {
                continue;
            }
            claim_role(id, PrimitiveTraceRole::WordStoreEvent)?;
            if store_events
                .insert(id.clone(), semantics)
                .is_some_and(|old| old != semantics)
            {
                return Err("word store trace event has conflicting semantics".into());
            }
        }
    }

    let mut indirect_events =
        BTreeMap::<String, (GuestAddr, GuestAddr, Option<GuestAddr>, u64, Option<String>)>::new();
    for observation in &map.indirect_observations {
        if let Some(unit) = &observation.source_unit {
            claim_role(unit, PrimitiveTraceRole::SourceUnit)?;
        }
        let semantics = (
            observation.site,
            observation.target,
            observation.delay_slot_pc,
            observation.generation,
            observation.source_unit.clone(),
        );
        for id in &observation.evidence {
            if observation.source_unit.as_ref() == Some(id) || !is_trace(id) {
                continue;
            }
            claim_role(id, PrimitiveTraceRole::IndirectEvent)?;
            if indirect_events
                .insert(id.clone(), semantics.clone())
                .is_some_and(|old| old != semantics)
            {
                return Err("indirect trace event has conflicting semantics".into());
            }
        }
    }

    let mut verification_events =
        BTreeMap::<String, (CodeAddress, u32, String, u64)>::new();
    for verification in &map.entry_verifications {
        claim_role(&verification.source_unit, PrimitiveTraceRole::SourceUnit)?;
        let semantics = (
            verification.entry.clone(),
            verification.register_mask,
            verification.source_unit.clone(),
            verification.generation,
        );
        for id in &verification.evidence {
            if id == &verification.source_unit || !is_trace(id) {
                continue;
            }
            claim_role(id, PrimitiveTraceRole::EntryVerificationEvent)?;
            if verification_events
                .insert(id.clone(), semantics.clone())
                .is_some_and(|old| old != semantics)
            {
                return Err("entry verification trace event has conflicting semantics".into());
            }
        }
    }

    Ok(())
}

'''
text = text.replace(marker, helper + marker, 1)

anchor = "        let refs = |r: &EvidenceRefs| -> Result<(), String> {\n"
if anchor not in text:
    raise SystemExit("ProgramMap::validate insertion marker not found")
text = text.replace(
    anchor,
    "        validate_trace_event_identities(self)?;\n" + anchor,
    1,
)
path.write_text(text)
