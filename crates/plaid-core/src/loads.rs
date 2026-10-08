//! Executable copy evidence is accepted only against canonical source bytes.
use crate::{
    EvidenceKind,
    discovery::CodeImage,
    program::*,
    rom::{CanonicalRom, sha256},
};

#[derive(Debug, Clone)]
pub struct LoadObservation {
    pub rom_offset: RomOffset,
    /// Executable subset of a transfer, not all DMA data marked executable.
    pub destination: GuestRange,
    pub physical_start: Option<PhysicalAddr>,
    pub generation: u64,
    /// Guest big-endian bytes captured after the copy, before execution.
    pub snapshot: Vec<u8>,
    pub producer: String,
    pub revision: String,
    pub event: u64,
}

pub fn record_load(
    map: &ProgramMap,
    rom: &CanonicalRom,
    observation: &LoadObservation,
) -> Result<ProgramMap, String> {
    map.validate()?;
    if map.rom != rom.identity {
        return Err("load evidence belongs to another ROM".into());
    }
    observation.destination.validate(true)?;
    if observation.snapshot.len() != observation.destination.size as usize
        || observation.producer.is_empty()
        || observation.revision.is_empty()
    {
        return Err("incomplete executable load snapshot".into());
    }
    let image = CodeImage::from_rom(rom, observation.rom_offset, observation.destination.clone())?;
    let id = format!(
        "load:{}:{}:{:08x}:{}:{}",
        observation.producer,
        observation.event,
        observation.destination.start.0,
        observation.generation,
        sha256(&observation.snapshot)
    );
    let evidence: EvidenceRefs = [id.clone()].into();
    let mut out = map.clone();
    let e = Evidence {
        kind: EvidenceKind::Trace,
        producer: observation.producer.clone(),
        revision: observation.revision.clone(),
        detail: format!(
            "executable copy event {}; ROM offset {}; post-copy snapshot SHA256 {}; generation {}",
            observation.event,
            observation.rom_offset.0,
            sha256(&observation.snapshot),
            observation.generation
        ),
    };
    if out.evidence.get(&id).is_some_and(|old| old != &e) {
        return Err("conflicting load evidence identity".into());
    }
    out.evidence.insert(id, e);
    let mut captured = Vec::with_capacity(observation.snapshot.len());
    for word in &image.words {
        captured.extend(word.to_be_bytes());
    }
    if captured != observation.snapshot {
        out.unresolved.insert(Unresolved { kind:"executable_load_bytes_mismatch".into(), site:None,
            detail:"post-copy bytes differ from canonical ROM; relocation, patching or generated code must be explained".into(), evidence:evidence.clone() });
        out.executable_writes.insert(ExecutableWrite {
            range: Some(observation.destination.clone()),
            kind: WriteKind::Unknown,
            evidence,
        });
        out.validate()?;
        return Ok(out);
    }
    let load = LoadMapping {
        rom_offset: observation.rom_offset,
        destination: observation.destination.clone(),
        image: image.base.image.clone(),
        generation: observation.generation,
        evidence: evidence.clone(),
    };
    let prior: Vec<_> = out
        .loads
        .iter()
        .filter(|old| {
            u64::from(old.destination.start.0) < load.destination.end()
                && u64::from(load.destination.start.0) < old.destination.end()
        })
        .cloned()
        .collect();
    let reused = prior.iter().any(|old| {
        old.destination == load.destination
            && old.rom_offset == load.rom_offset
            && old.image == load.image
    });
    if reused {
        // This event is an observed exact ROM reload. It does not classify
        // unrelated invalidation events or prove all future copies are known.
        out.executable_writes.insert(ExecutableWrite {
            range: Some(load.destination.clone()),
            kind: WriteKind::OverlayReload,
            evidence: evidence.clone(),
        });
    }
    let alternatives: Vec<_> = prior
        .iter()
        .filter(|old| old.rom_offset != load.rom_offset || old.image != load.image)
        .cloned()
        .collect();
    let mut overlay_id = None;
    if !alternatives.is_empty() {
        for l in alternatives.iter().chain(std::iter::once(&load)) {
            let key = format!(
                "candidate:{}:{}:{:08x}:{}",
                l.image, l.rom_offset.0, l.destination.start.0, l.destination.size
            );
            out.overlays
                .entry(key.clone())
                .and_modify(|o| o.evidence.extend(l.evidence.clone()))
                .or_insert(Overlay {
                    image: l.image.clone(),
                    rom_offset: l.rom_offset,
                    size: l.destination.size,
                    load_address: l.destination.start,
                    candidate: true,
                    evidence: l.evidence.clone(),
                });
            if l == &load {
                overlay_id = Some(key);
            }
        }
        let refs = alternatives.iter().fold(evidence.clone(), |mut refs, l| {
            refs.extend(l.evidence.clone());
            refs
        });
        out.unresolved.insert(Unresolved { kind:"overlay_candidate_lifecycle_unknown".into(), site:None,
            detail:"different canonical executable sources overlap in guest RAM; unload/relocation/dispatch lifecycle is unproven".into(), evidence:refs });
    }
    out.regions.insert(Region {
        image: load.image.clone(),
        generation: load.generation,
        range: load.destination.clone(),
        rom_offset: Some(load.rom_offset),
        physical_start: observation.physical_start,
        overlay: overlay_id,
        evidence,
    });
    out.loads.insert(load);
    out.validate()?;
    Ok(out)
}
