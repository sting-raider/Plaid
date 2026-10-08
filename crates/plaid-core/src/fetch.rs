//! Bounded, streaming import of the exact-word ares research observer.
//! Coalesced samples retain raw capture hash and exact first/last indices/count;
//! they never manufacture compiled units, generations or executable lifetimes.
use crate::{EvidenceKind, program::*, rom::CanonicalRom, trace::MAX_RECORD_BYTES};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{BufRead, Read},
};

pub const FORMAT: &str = "plaid-ares-fetch-research-v0";
pub const PHYSICAL_FORMAT: &str = "plaid-ares-fetch-research-v1";
pub const SOURCE_FORMAT: &str = "plaid-ares-fetch-research-v2";
pub const SOURCE_POLICY: &str = "delegated_rom_halves_before_prologue";
pub const REVISION: &str = "9408cb43d4948fc3ea6e152a307a34348df3fe04";
pub const INITIAL_STATE: &str = "declared_post_ipl2_sp_entry";
pub const MAX_BUDGET: u64 = 10_000_000;

// Missing optional version fields default to None; explicit null is invalid.
fn present<'de, D: serde::Deserializer<'de>, T: Deserialize<'de>>(
    deserializer: D,
) -> Result<Option<T>, D::Error> {
    T::deserialize(deserializer).map(Some)
}

#[derive(Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Record {
    Header {
        format: String,
        revision: String,
        rom_sha256: String,
        budget: u64,
        initial_state: String,
        #[serde(default, deserialize_with = "present")]
        mapped_cartridge_size: Option<u32>,
        #[serde(default, deserialize_with = "present")]
        source_policy: Option<String>,
    },
    Fetch {
        seq: u64,
        pc: GuestVirtualAddr,
        word: u32,
        delay_slot: bool,
        #[serde(default, deserialize_with = "present")]
        physical: Option<PhysicalAddr>,
        #[serde(default, deserialize_with = "present")]
        cached: Option<bool>,
        #[serde(default, deserialize_with = "present")]
        source: Option<FetchSource>,
    },
    End {
        fetch_count: u64,
        reason: String,
    },
}

fn line<R: BufRead>(reader: &mut R, bytes: &mut Vec<u8>) -> Result<bool, String> {
    bytes.clear();
    let size = reader
        .take(MAX_RECORD_BYTES as u64 + 1)
        .read_until(b'\n', bytes)
        .map_err(|e| e.to_string())?;
    if size > MAX_RECORD_BYTES {
        return Err("oversized fetch record".into());
    }
    Ok(size != 0)
}

pub fn import_fetch<R: BufRead>(mut reader: R, rom: &CanonicalRom) -> Result<ProgramMap, String> {
    let mut bytes = Vec::new();
    if !line(&mut reader, &mut bytes)? {
        return Err("missing fetch header".into());
    }
    let mut hash = Sha256::new();
    hash.update(&bytes);
    let Record::Header {
        format,
        revision,
        rom_sha256,
        budget,
        initial_state,
        mapped_cartridge_size,
        source_policy,
    } = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?
    else {
        return Err("fetch stream must begin with header".into());
    };
    if (format != FORMAT && format != PHYSICAL_FORMAT && format != SOURCE_FORMAT)
        || revision != REVISION
        || initial_state != INITIAL_STATE
        || budget == 0
        || budget > MAX_BUDGET
    {
        return Err("unsupported fetch format, revision, initial state or budget".into());
    }
    if rom_sha256 != rom.identity.sha256 {
        return Err("fetch stream does not match canonical ROM".into());
    }
    let source_format = format == SOURCE_FORMAT;
    let physical_format = format != FORMAT;
    if source_policy.as_deref() != source_format.then_some(SOURCE_POLICY) {
        return Err("invalid fetch source policy for format".into());
    }
    if physical_format != mapped_cartridge_size.is_some()
        || mapped_cartridge_size
            .is_some_and(|size| u64::from(size) != (rom.identity.size & !7) || size < 64)
    {
        return Err("invalid mapped cartridge capacity for fetch format".into());
    }
    let mut samples = BTreeMap::<
        (
            GuestVirtualAddr,
            u32,
            bool,
            Option<FetchAccess>,
            Option<FetchSource>,
        ),
        (u64, u64, u64),
    >::new();
    let mut count = 0;
    loop {
        if !line(&mut reader, &mut bytes)? {
            return Err("truncated fetch stream: missing end record".into());
        }
        hash.update(&bytes);
        match serde_json::from_slice(&bytes).map_err(|e| e.to_string())? {
            Record::Fetch {
                seq,
                pc,
                word,
                delay_slot,
                physical,
                cached,
                source,
            } => {
                let access = match (physical_format, physical, cached) {
                    (true, Some(physical), Some(cached)) if physical.0.is_multiple_of(4) => {
                        Some(FetchAccess { physical, cached })
                    }
                    (false, None, None) => None,
                    _ => return Err("invalid physical fetch metadata for format".into()),
                };
                if source.is_some() != source_format {
                    return Err("invalid fetch source metadata for format".into());
                }
                if let Some(FetchSource::CartridgeRom { offset }) = source {
                    let start =
                        usize::try_from(offset.0).map_err(|_| "ROM source offset overflow")?;
                    let end = start.checked_add(4).ok_or("ROM source offset overflow")?;
                    if rom.bytes().get(start..end) != Some(word.to_be_bytes().as_slice()) {
                        return Err("cartridge fetch source word differs from canonical ROM".into());
                    }
                }
                if seq != count || count >= budget || !pc.0.is_multiple_of(4) {
                    return Err("invalid fetch sequence, address or budget".into());
                }
                let sample = samples
                    .entry((pc, word, delay_slot, access, source))
                    .or_insert((seq, seq, 0));
                sample.1 = seq;
                sample.2 += 1;
                count += 1;
            }
            Record::End {
                fetch_count,
                reason,
            } => {
                if fetch_count != count || reason != "instruction_call_budget" {
                    return Err("invalid fetch footer or stop policy".into());
                }
                if line(&mut reader, &mut bytes)? {
                    return Err("data after fetch footer".into());
                }
                break;
            }
            Record::Header { .. } => return Err("repeated fetch header".into()),
        }
    }
    let digest = format!("{:x}", hash.finalize());
    let id = format!("fetch:{digest}");
    let mut map = ProgramMap::new(rom.identity.clone());
    map.evidence.insert(id.clone(), Evidence {
        kind: EvidenceKind::Trace, producer: format, revision: revision.clone(),
        detail: format!("raw fetch stream SHA256 {digest}; {count} fetched words; instruction-call budget {budget}; initial state {initial_state}; finite samples, no generation/lifetime/retirement proof"),
    });
    map.fetch_captures.insert(
        id.clone(),
        FetchCapture {
            trace_sha256: digest,
            revision,
            initial_state,
            instruction_call_budget: budget,
            fetch_count: count,
            mapped_cartridge_size,
            source_policy,
        },
    );
    map.fetch_observations = samples
        .into_iter()
        .map(
            |((pc, word, delay_slot, access, source), (first_seq, last_seq, occurrences))| {
                ObservedFetch {
                    pc,
                    word,
                    delay_slot,
                    access,
                    source,
                    capture: id.clone(),
                    first_seq,
                    last_seq,
                    occurrences,
                    evidence: [id.clone()].into(),
                }
            },
        )
        .collect();
    map.validate()?;
    Ok(map)
}

/// Rebuild summaries from their complete raw source, checking hash, bounds,
/// fields/counts and provenance. Additional facts from other captures may coexist.
pub fn verify_fetch_capture<R: BufRead>(
    map: &ProgramMap,
    reader: R,
    rom: &CanonicalRom,
) -> Result<(), String> {
    map.validate()?;
    if map.rom != rom.identity {
        return Err("map does not match canonical ROM".into());
    }
    let expected = import_fetch(reader, rom)?;
    let (id, capture) = expected.fetch_captures.first_key_value().unwrap();
    if map.fetch_captures.get(id) != Some(capture)
        || map.evidence.get(id) != expected.evidence.get(id)
    {
        return Err("fetch capture metadata or provenance does not match raw source".into());
    }
    let actual: std::collections::BTreeSet<_> = map
        .fetch_observations
        .iter()
        .filter(|f| &f.capture == id)
        .cloned()
        .map(|mut f| {
            f.evidence.clear();
            f
        })
        .collect();
    let wanted: std::collections::BTreeSet<_> = expected
        .fetch_observations
        .into_iter()
        .map(|mut f| {
            f.evidence.clear();
            f
        })
        .collect();
    if actual != wanted {
        return Err("fetch summaries do not match raw source".into());
    }
    Ok(())
}
