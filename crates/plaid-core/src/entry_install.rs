//! Source-bound recheck for discovery-trace entry installation provenance.
//!
//! Generic Trace evidence is intentionally shared across derived CFG facts, so a
//! ProgramMap alone cannot infer which Trace reference denotes EntryInstalled.
//! Recheck the exact trace instead of guessing an evidence role from topology or
//! human-readable detail.

use crate::{
    discovery::CodeImage,
    merge::{import_trace, import_trace_with_rom},
    program::{CodeAddress, ProgramMap},
    rom::{CanonicalRom, sha256},
    trace::{DiscoveryTrace, TraceEvent},
};
use std::collections::BTreeSet;

/// Re-import a validated discovery trace and verify only its EntryInstalled
/// projection against `map`. Other merged/static facts may coexist.
pub fn verify_entry_install_projection(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    map: &ProgramMap,
    budget: usize,
) -> Result<(), String> {
    let expected = import_trace(trace, known, budget)?;
    verify_projection(trace, map, &expected)
}

/// ROM-backed counterpart for maps produced with `import_trace_with_rom`.
pub fn verify_entry_install_projection_with_rom(
    trace: &DiscoveryTrace,
    known: &[CodeImage],
    rom: &CanonicalRom,
    map: &ProgramMap,
    budget: usize,
) -> Result<(), String> {
    let expected = import_trace_with_rom(trace, known, rom, budget)?;
    verify_projection(trace, map, &expected)
}

fn entry_uses(map: &ProgramMap, id: &str) -> BTreeSet<CodeAddress> {
    map.entries
        .iter()
        .filter(|(_, refs)| refs.contains(id))
        .map(|(entry, _)| entry.clone())
        .collect()
}

fn verify_projection(
    trace: &DiscoveryTrace,
    map: &ProgramMap,
    expected: &ProgramMap,
) -> Result<(), String> {
    map.validate()?;
    if &map.rom != &trace.header.rom {
        return Err("entry-install source trace does not match ProgramMap ROM".into());
    }

    let session = sha256(trace.to_ndjson()?.as_bytes());
    for event in &trace.events {
        if !matches!(event.data, TraceEvent::EntryInstalled { .. }) {
            continue;
        }
        let id = format!("trace:{session}:{}", event.seq);
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
        let actual_entries = entry_uses(map, &id);
        if actual_entries != expected_entries {
            return Err("EntryInstalled event is missing or bound to a different entry identity".into());
        }
    }
    Ok(())
}
