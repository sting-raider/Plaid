//! Bounded compiler-time replay of captured COP1 load/write/store lineage.
//!
//! This consumer deliberately does not derive physical FPR storage from FR/ft.
//! The capture must provide the actual physical register and byte lanes selected
//! by each completed operation. This avoids turning reference-specific odd-FR
//! behavior into an architectural claim while still preserving byte generations.
use crate::{program::PhysicalAddr, rom::sha256};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const FORMAT: &str = "plaid-cop1-fpr-lineage-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    initial_fprs: [u64; 32],
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", content = "event", rename_all = "snake_case")]
enum Event {
    CompletedRead(CompletedRead),
    FprWrite(FprWrite),
    Store(Store),
    FailedLoad(FailedLoad),
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::CompletedRead(event) => event.ordinal,
            Self::FprWrite(event) => event.ordinal,
            Self::Store(event) => event.ordinal,
            Self::FailedLoad(event) => event.ordinal,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CompletedRead {
    ordinal: u64,
    context: u64,
    phase: u32,
    address: PhysicalAddr,
    bytes: u32,
    uncached_cpu: bool,
    value: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FprWriteKind {
    Lwc1,
    Ldc1,
    Mtc1,
    Dmtc1,
}

impl FprWriteKind {
    fn width(self) -> u32 {
        match self {
            Self::Lwc1 | Self::Mtc1 => 4,
            Self::Ldc1 | Self::Dmtc1 => 8,
        }
    }

    fn is_load(self) -> bool {
        matches!(self, Self::Lwc1 | Self::Ldc1)
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct FprWrite {
    ordinal: u64,
    context: u64,
    phase: u32,
    operation: FprWriteKind,
    architectural_fpr: u8,
    fr: bool,
    physical_fpr: u8,
    slots: Vec<u8>,
    value: u64,
    #[serde(default)]
    source_read_ordinal: Option<u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FprStoreKind {
    Swc1,
    Sdc1,
}

impl FprStoreKind {
    fn width(self) -> u32 {
        match self {
            Self::Swc1 => 4,
            Self::Sdc1 => 8,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Store {
    ordinal: u64,
    context: u64,
    phase: u32,
    operation: FprStoreKind,
    architectural_fpr: u8,
    fr: bool,
    physical_fpr: u8,
    slots: Vec<u8>,
    destination: PhysicalAddr,
    bytes: u32,
    uncached_cpu: bool,
    value: u64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailedLoadKind {
    Lwc1,
    Ldc1,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailedLoadReason {
    Cu1Disabled,
    Misaligned,
    TlbMiss,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct FailedLoad {
    ordinal: u64,
    context: u64,
    phase: u32,
    operation: FailedLoadKind,
    architectural_fpr: u8,
    fr: bool,
    reason: FailedLoadReason,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum FprByteOrigin {
    Initial {
        physical_fpr: u8,
        slot: u8,
    },
    RdramRead {
        read_ordinal: u64,
        source: PhysicalAddr,
        source_byte: u8,
    },
    CapturedWriter {
        writer_ordinal: u64,
        operation: FprWriteKind,
        source_byte: u8,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cop1StoreWitness {
    pub store_ordinal: u64,
    pub context: u64,
    pub phase: u32,
    pub operation: FprStoreKind,
    pub architectural_fpr: u8,
    pub fr: bool,
    pub physical_fpr: u8,
    pub slots: Vec<u8>,
    pub destination: PhysicalAddr,
    pub value: u64,
    pub byte_origins: Vec<FprByteOrigin>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cop1LineageReport {
    pub format: String,
    pub source_sha256: String,
    pub event_count: usize,
    pub completed_reads: usize,
    pub fpr_writes: usize,
    pub failed_loads: usize,
    pub stores: Vec<Cop1StoreWitness>,
    pub rdram_source_ancestry_certified: bool,
    pub fpr_writer_census_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone)]
struct Cell {
    value: u8,
    origin: FprByteOrigin,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ContextState {
    Read(u64),
    Load,
    Move,
    Store,
    FailedLoad,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn payload_bytes(value: u64, width: u32) -> Result<Vec<u8>, String> {
    let bytes = value.to_be_bytes();
    match width {
        4 => {
            require(u32::try_from(value).is_ok(), "COP1 Word value exceeds 32 bits")?;
            Ok(bytes[4..].to_vec())
        }
        8 => Ok(bytes.to_vec()),
        _ => Err("unsupported COP1 width".into()),
    }
}

fn validate_rdram(address: PhysicalAddr, width: u32) -> Result<(), String> {
    require(matches!(width, 4 | 8), "unsupported COP1 RDRAM width")?;
    let last = address
        .0
        .checked_add(width - 1)
        .ok_or("COP1 RDRAM span overflow")?;
    require(
        address.0.is_multiple_of(width) && last < 0x0080_0000,
        "COP1 effect outside aligned identity RDRAM",
    )
}

fn validate_selection(
    architectural_fpr: u8,
    physical_fpr: u8,
    slots: &[u8],
    width: u32,
) -> Result<(), String> {
    require(
        architectural_fpr < 32 && physical_fpr < 32,
        "COP1 register index out of range",
    )?;
    let valid = match width {
        4 => slots == [0, 1, 2, 3] || slots == [4, 5, 6, 7],
        8 => slots == [0, 1, 2, 3, 4, 5, 6, 7],
        _ => false,
    };
    require(valid, "invalid COP1 physical byte-lane selection")
}

/// Replay a source-bound captured COP1 history.
///
/// The expected hash must come from a separately trusted complete-source receipt.
/// A successful replay authenticates the supplied finite history only. It does not
/// certify that every FPR writer, memory producer, executable mutation, or lifetime
/// boundary was sensed.
pub fn inspect_cop1_lineage_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<Cop1LineageReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "COP1 lineage source receipt mismatch")?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(history.format == FORMAT, "unsupported COP1 lineage history format")?;

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous COP1 lineage ordinals",
        )?;
    }

    let mut fprs: [[Cell; 8]; 32] = std::array::from_fn(|physical_fpr| {
        let bytes = history.initial_fprs[physical_fpr].to_be_bytes();
        std::array::from_fn(|slot| Cell {
            value: bytes[slot],
            origin: FprByteOrigin::Initial {
                physical_fpr: physical_fpr as u8,
                slot: slot as u8,
            },
        })
    });
    let mut reads = BTreeMap::<u64, &CompletedRead>::new();
    let mut used_reads = BTreeSet::<u64>::new();
    let mut contexts = BTreeMap::<u64, ContextState>::new();
    let mut completed_reads = 0usize;
    let mut fpr_writes = 0usize;
    let mut failed_loads = 0usize;
    let mut stores = Vec::new();

    for event in &history.events {
        match event {
            Event::CompletedRead(read) => {
                require(
                    read.context != 0 && read.phase != 0 && read.uncached_cpu,
                    "invalid completed COP1 source read context",
                )?;
                validate_rdram(read.address, read.bytes)?;
                payload_bytes(read.value, read.bytes)?;
                require(
                    contexts
                        .insert(read.context, ContextState::Read(read.ordinal))
                        .is_none(),
                    "reused COP1 context identity",
                )?;
                require(reads.insert(read.ordinal, read).is_none(), "duplicate COP1 read ordinal")?;
                completed_reads += 1;
            }
            Event::FprWrite(write) => {
                require(
                    write.context != 0 && write.phase != 0,
                    "invalid completed COP1 FPR write context",
                )?;
                let width = write.operation.width();
                validate_selection(
                    write.architectural_fpr,
                    write.physical_fpr,
                    &write.slots,
                    width,
                )?;
                let bytes = payload_bytes(write.value, width)?;
                let origins = if write.operation.is_load() {
                    let read_ordinal = write
                        .source_read_ordinal
                        .ok_or("completed COP1 load missing source read")?;
                    let read = reads
                        .get(&read_ordinal)
                        .copied()
                        .ok_or("COP1 load references missing or future source read")?;
                    require(
                        (read.context, read.phase, read.bytes, read.value)
                            == (write.context, write.phase, width, write.value),
                        "COP1 load/source read mismatch",
                    )?;
                    require(
                        matches!(
                            contexts.get(&write.context),
                            Some(ContextState::Read(ordinal)) if *ordinal == read_ordinal
                        ),
                        "COP1 load context does not own source read",
                    )?;
                    require(
                        used_reads.insert(read_ordinal),
                        "COP1 source read reused by multiple FPR definitions",
                    )?;
                    contexts.insert(write.context, ContextState::Load);
                    (0..width)
                        .map(|source_byte| FprByteOrigin::RdramRead {
                            read_ordinal,
                            source: PhysicalAddr(read.address.0 + source_byte),
                            source_byte: source_byte as u8,
                        })
                        .collect::<Vec<_>>()
                } else {
                    require(
                        write.source_read_ordinal.is_none(),
                        "non-load COP1 writer carries a memory source read",
                    )?;
                    require(
                        contexts
                            .insert(write.context, ContextState::Move)
                            .is_none(),
                        "reused COP1 context identity",
                    )?;
                    (0..width)
                        .map(|source_byte| FprByteOrigin::CapturedWriter {
                            writer_ordinal: write.ordinal,
                            operation: write.operation,
                            source_byte: source_byte as u8,
                        })
                        .collect::<Vec<_>>()
                };
                for (index, slot) in write.slots.iter().copied().enumerate() {
                    fprs[usize::from(write.physical_fpr)][usize::from(slot)] = Cell {
                        value: bytes[index],
                        origin: origins[index].clone(),
                    };
                }
                fpr_writes += 1;
            }
            Event::Store(store) => {
                require(
                    store.context != 0 && store.phase != 0 && store.uncached_cpu,
                    "invalid completed COP1 store context",
                )?;
                require(
                    contexts
                        .insert(store.context, ContextState::Store)
                        .is_none(),
                    "reused COP1 context identity",
                )?;
                let width = store.operation.width();
                require(store.bytes == width, "COP1 store width mismatch")?;
                validate_rdram(store.destination, width)?;
                validate_selection(
                    store.architectural_fpr,
                    store.physical_fpr,
                    &store.slots,
                    width,
                )?;
                let expected = payload_bytes(store.value, width)?;
                let selected = store
                    .slots
                    .iter()
                    .map(|slot| &fprs[usize::from(store.physical_fpr)][usize::from(*slot)])
                    .collect::<Vec<_>>();
                require(
                    selected
                        .iter()
                        .map(|cell| cell.value)
                        .eq(expected.iter().copied()),
                    "COP1 store payload does not match selected physical lanes",
                )?;
                stores.push(Cop1StoreWitness {
                    store_ordinal: store.ordinal,
                    context: store.context,
                    phase: store.phase,
                    operation: store.operation,
                    architectural_fpr: store.architectural_fpr,
                    fr: store.fr,
                    physical_fpr: store.physical_fpr,
                    slots: store.slots.clone(),
                    destination: store.destination,
                    value: store.value,
                    byte_origins: selected.iter().map(|cell| cell.origin.clone()).collect(),
                });
            }
            Event::FailedLoad(failed) => {
                require(
                    failed.context != 0
                        && failed.phase != 0
                        && failed.architectural_fpr < 32,
                    "invalid failed COP1 load context",
                )?;
                require(
                    contexts
                        .insert(failed.context, ContextState::FailedLoad)
                        .is_none(),
                    "reused COP1 context identity",
                )?;
                let _ = (failed.operation, failed.fr, failed.reason);
                failed_loads += 1;
            }
        }
    }

    Ok(Cop1LineageReport {
        format: history.format,
        source_sha256: digest,
        event_count: history.events.len(),
        completed_reads,
        fpr_writes,
        failed_loads,
        stores,
        rdram_source_ancestry_certified: false,
        fpr_writer_census_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_cop1_lineage_report(
    report: &Cop1LineageReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_cop1_lineage_history(source, expected_sha256)?,
        "COP1 lineage report differs from complete source replay",
    )
}
