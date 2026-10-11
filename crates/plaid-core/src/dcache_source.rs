//! Bounded compiler-time replay for source-bound D-cache Word reads.
//!
//! This module authenticates a supplied finite history. It does not prove that the
//! history observed every cache/backing operation, mapping change, reset/restore
//! boundary, or executable lifetime required by a whole-ROM certificate.
use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-dcache-word-source-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    initial_backing: Vec<InitialWord>,
    records: Vec<Record>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct InitialWord {
    address: PhysicalAddr,
    value: u32,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", content = "event", rename_all = "snake_case")]
enum Record {
    BackingWrite(BackingWrite),
    BackingBurstRead(BackingBurstRead),
    CacheRead(CacheRead),
    CacheWrite(CacheWrite),
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct BackingWrite {
    ordinal: u64,
    pc: GuestVirtualAddr,
    address: PhysicalAddr,
    value: u32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct BackingBurstRead {
    ordinal: u64,
    address: PhysicalAddr,
    words: [u32; 4],
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CacheRead {
    ordinal: u64,
    pc: GuestVirtualAddr,
    vaddr: GuestVirtualAddr,
    paddr: PhysicalAddr,
    value: u32,
    slot: u16,
    tag: u32,
    dirty: u16,
    hit_before: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CacheWrite {
    ordinal: u64,
    pc: GuestVirtualAddr,
    vaddr: GuestVirtualAddr,
    paddr: PhysicalAddr,
    value: u32,
    slot: u16,
    tag: u32,
    dirty: u16,
    hit_before: bool,
}

impl Record {
    fn ordinal(&self) -> u64 {
        match self {
            Self::BackingWrite(event) => event.ordinal,
            Self::BackingBurstRead(event) => event.ordinal,
            Self::CacheRead(event) => event.ordinal,
            Self::CacheWrite(event) => event.ordinal,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WordGenerationKind {
    InitialBacking,
    BackingWrite,
    CacheFill,
    ResidentWrite,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WordGeneration {
    pub kind: WordGenerationKind,
    pub ordinal: Option<u64>,
    pub address: PhysicalAddr,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct GenerationRecord {
    pub generation: WordGeneration,
    pub value: u32,
    /// Exact value source where the bounded history establishes one. A cache fill
    /// points to the backing generation captured by its successful burst read.
    pub source: Option<WordGeneration>,
    /// Prior storage generation replaced by a successful write. This is chronology,
    /// not a claim that the new payload was derived from the replaced bytes.
    pub replaced: Option<WordGeneration>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CacheLineGeneration {
    pub fill_ordinal: u64,
    pub line_base: PhysicalAddr,
    pub slot: u16,
    pub tag: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheReadWitness {
    pub ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub vaddr: GuestVirtualAddr,
    pub paddr: PhysicalAddr,
    pub value: u32,
    pub hit_before: bool,
    pub slot: u16,
    pub tag: u32,
    pub dirty: u16,
    pub line_generation: CacheLineGeneration,
    pub source_generation: WordGeneration,
    pub current_backing_generation: WordGeneration,
    pub current_backing_value: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheSourceReport {
    pub format: String,
    pub source_sha256: String,
    pub records: usize,
    pub backing_writes: usize,
    pub backing_burst_reads: usize,
    pub resident_writes: usize,
    pub generations: Vec<GenerationRecord>,
    pub reads: Vec<DcacheReadWitness>,
    pub source_history_coverage_certified: bool,
    pub mapping_history_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Clone)]
struct PendingFill {
    ordinal: u64,
    base: PhysicalAddr,
    words: [(u32, WordGeneration); 4],
}

#[derive(Clone)]
struct ResidentLine {
    generation: CacheLineGeneration,
    tag: u32,
    dirty: u16,
    words: [(u32, WordGeneration); 4],
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn line_base(address: PhysicalAddr) -> PhysicalAddr {
    PhysicalAddr(address.0 & !0x0f)
}

fn word_lane(address: PhysicalAddr) -> usize {
    ((address.0 & 0x0f) / 4) as usize
}

fn generation(
    kind: WordGenerationKind,
    ordinal: Option<u64>,
    address: PhysicalAddr,
) -> WordGeneration {
    WordGeneration {
        kind,
        ordinal,
        address,
    }
}

fn record_generation(
    generations: &mut BTreeMap<WordGeneration, GenerationRecord>,
    record: GenerationRecord,
) -> Result<(), String> {
    require(
        generations.insert(record.generation, record).is_none(),
        "duplicate D-cache word generation identity",
    )
}

fn validate_word_access(
    pc: GuestVirtualAddr,
    vaddr: GuestVirtualAddr,
    paddr: PhysicalAddr,
) -> Result<(), String> {
    require(
        pc.0.is_multiple_of(4) && vaddr.0.is_multiple_of(4) && paddr.0.is_multiple_of(4),
        "unaligned D-cache Word access",
    )
}

fn install_fill(
    event_ordinal: u64,
    paddr: PhysicalAddr,
    slot: u16,
    tag: u32,
    pending: &mut BTreeMap<PhysicalAddr, PendingFill>,
    slots: &mut BTreeMap<u16, ResidentLine>,
    generations: &mut BTreeMap<WordGeneration, GenerationRecord>,
) -> Result<(), String> {
    let base = line_base(paddr);
    let fill = pending
        .remove(&base)
        .ok_or("D-cache miss lacks a successful backing burst")?;
    require(
        fill.ordinal.checked_add(1) == Some(event_ordinal),
        "D-cache miss does not immediately follow its backing burst",
    )?;
    if let Some(old) = slots.get(&slot) {
        require(
            old.dirty == 0,
            "dirty D-cache replacement lacks writeback evidence",
        )?;
        require(
            old.tag != tag,
            "same-tag D-cache miss lacks invalidation/replacement evidence",
        )?;
    }
    let mut words = fill.words;
    for (lane, word) in words.iter_mut().enumerate() {
        let address = PhysicalAddr(base.0 + lane as u32 * 4);
        let source = word.1;
        let fill_generation =
            generation(WordGenerationKind::CacheFill, Some(fill.ordinal), address);
        record_generation(
            generations,
            GenerationRecord {
                generation: fill_generation,
                value: word.0,
                source: Some(source),
                replaced: None,
            },
        )?;
        word.1 = fill_generation;
    }
    slots.insert(
        slot,
        ResidentLine {
            generation: CacheLineGeneration {
                fill_ordinal: fill.ordinal,
                line_base: fill.base,
                slot,
                tag,
            },
            tag,
            dirty: 0,
            words,
        },
    );
    Ok(())
}

/// Replay one externally authenticated finite source. The expected hash must come
/// from a separate complete-source receipt; recomputing it from untrusted input
/// does not establish capture completeness.
pub fn inspect_dcache_source_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<DcacheSourceReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "D-cache source receipt mismatch")?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported D-cache source history format",
    )?;

    let mut backing = BTreeMap::<PhysicalAddr, (u32, WordGeneration)>::new();
    let mut generations = BTreeMap::<WordGeneration, GenerationRecord>::new();
    for word in history.initial_backing {
        require(
            word.address.0.is_multiple_of(4),
            "unaligned initial backing Word",
        )?;
        let identity = generation(WordGenerationKind::InitialBacking, None, word.address);
        require(
            backing
                .insert(word.address, (word.value, identity))
                .is_none(),
            "duplicate initial backing Word",
        )?;
        record_generation(
            &mut generations,
            GenerationRecord {
                generation: identity,
                value: word.value,
                source: None,
                replaced: None,
            },
        )?;
    }

    let mut pending = BTreeMap::<PhysicalAddr, PendingFill>::new();
    let mut slots = BTreeMap::<u16, ResidentLine>::new();
    let mut reads = Vec::new();
    let mut backing_writes = 0usize;
    let mut backing_burst_reads = 0usize;
    let mut resident_writes = 0usize;

    for (index, record) in history.records.iter().enumerate() {
        require(
            record.ordinal() == index as u64 + 1,
            "noncontiguous D-cache source ordinals",
        )?;
        match record {
            Record::BackingWrite(event) => {
                require(
                    event.pc.0.is_multiple_of(4) && event.address.0.is_multiple_of(4),
                    "unaligned backing write",
                )?;
                let (_, previous) = *backing
                    .get(&event.address)
                    .ok_or("backing write lacks initial/current Word")?;
                let identity = generation(
                    WordGenerationKind::BackingWrite,
                    Some(event.ordinal),
                    event.address,
                );
                record_generation(
                    &mut generations,
                    GenerationRecord {
                        generation: identity,
                        value: event.value,
                        source: None,
                        replaced: Some(previous),
                    },
                )?;
                backing.insert(event.address, (event.value, identity));
                backing_writes += 1;
            }
            Record::BackingBurstRead(event) => {
                require(
                    event.address.0.is_multiple_of(16),
                    "unaligned D-cache backing burst",
                )?;
                let mut words = [(
                    0u32,
                    generation(WordGenerationKind::InitialBacking, None, PhysicalAddr(0)),
                ); 4];
                for (lane, entry) in words.iter_mut().enumerate() {
                    let address = PhysicalAddr(event.address.0 + lane as u32 * 4);
                    let current = *backing
                        .get(&address)
                        .ok_or("D-cache burst lacks current backing Word")?;
                    require(
                        current.0 == event.words[lane],
                        "D-cache burst payload disagrees with current backing generation",
                    )?;
                    *entry = current;
                }
                require(
                    pending
                        .insert(
                            event.address,
                            PendingFill {
                                ordinal: event.ordinal,
                                base: event.address,
                                words,
                            },
                        )
                        .is_none(),
                    "ambiguous repeated backing burst before cache fill",
                )?;
                backing_burst_reads += 1;
            }
            Record::CacheRead(event) => {
                validate_word_access(event.pc, event.vaddr, event.paddr)?;
                if !event.hit_before {
                    install_fill(
                        event.ordinal,
                        event.paddr,
                        event.slot,
                        event.tag,
                        &mut pending,
                        &mut slots,
                        &mut generations,
                    )?;
                }
                let line = slots
                    .get(&event.slot)
                    .ok_or("D-cache hit lacks resident slot")?;
                require(
                    line.tag == event.tag,
                    "D-cache read tag/generation mismatch",
                )?;
                require(
                    line.generation.line_base == line_base(event.paddr),
                    "D-cache read physical line disagrees with resident generation",
                )?;
                require(
                    line.dirty == event.dirty,
                    "D-cache read dirty state mismatch",
                )?;
                let (value, source_generation) = line.words[word_lane(event.paddr)];
                require(
                    value == event.value,
                    "D-cache read value disagrees with resident generation",
                )?;
                let (backing_value, current_backing_generation) = *backing
                    .get(&event.paddr)
                    .ok_or("D-cache read lacks current backing Word")?;
                reads.push(DcacheReadWitness {
                    ordinal: event.ordinal,
                    pc: event.pc,
                    vaddr: event.vaddr,
                    paddr: event.paddr,
                    value,
                    hit_before: event.hit_before,
                    slot: event.slot,
                    tag: event.tag,
                    dirty: event.dirty,
                    line_generation: line.generation,
                    source_generation,
                    current_backing_generation,
                    current_backing_value: backing_value,
                });
            }
            Record::CacheWrite(event) => {
                validate_word_access(event.pc, event.vaddr, event.paddr)?;
                if !event.hit_before {
                    install_fill(
                        event.ordinal,
                        event.paddr,
                        event.slot,
                        event.tag,
                        &mut pending,
                        &mut slots,
                        &mut generations,
                    )?;
                }
                let line = slots
                    .get_mut(&event.slot)
                    .ok_or("D-cache write lacks resident slot")?;
                require(
                    line.tag == event.tag,
                    "D-cache write tag/generation mismatch",
                )?;
                require(
                    line.generation.line_base == line_base(event.paddr),
                    "D-cache write physical line disagrees with resident generation",
                )?;
                require(
                    event.dirty != 0,
                    "completed D-cache write did not leave dirty state",
                )?;
                let lane = word_lane(event.paddr);
                let previous = line.words[lane].1;
                let identity = generation(
                    WordGenerationKind::ResidentWrite,
                    Some(event.ordinal),
                    event.paddr,
                );
                record_generation(
                    &mut generations,
                    GenerationRecord {
                        generation: identity,
                        value: event.value,
                        source: None,
                        replaced: Some(previous),
                    },
                )?;
                line.words[lane] = (event.value, identity);
                line.dirty = event.dirty;
                resident_writes += 1;
            }
        }
    }
    require(pending.is_empty(), "unconsumed D-cache backing burst")?;

    Ok(DcacheSourceReport {
        format: history.format,
        source_sha256: digest,
        records: history.records.len(),
        backing_writes,
        backing_burst_reads,
        resident_writes,
        generations: generations.into_values().collect(),
        reads,
        source_history_coverage_certified: false,
        mapping_history_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_dcache_source_report(
    report: &DcacheSourceReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_dcache_source_history(source, expected_sha256)?,
        "D-cache source report differs from complete source replay",
    )
}
