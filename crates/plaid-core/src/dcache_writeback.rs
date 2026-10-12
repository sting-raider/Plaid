//! Bounded source-bound D-cache resident-to-backing writeback lineage.
//!
//! This module proves only a finite causal promotion: an already-authenticated
//! cache-resident aligned word mutation may become backing-memory provenance when
//! the same resident generation/revision is exported by an exact successful
//! 16-byte RDRAM writeback. Equal bytes, addresses, tags, or a later resident line
//! never substitute for that chronology. Sensor completeness, TLB/cacheability
//! semantics, executable lifetime, and native readiness remain separate.

use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
    store_mutation::{AresStore64Receipt, Store64Kind, StoreEndian, StoreOutcome},
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-dcache-writeback-history-v0";
pub const READ_FORMAT: &str = "plaid-dcache-resident-read-history-v1";
pub const STORE64_FORMAT: &str = "plaid-dcache-store64-writeback-history-v2";
const REPORT_FORMAT: &str = "plaid-dcache-writeback-report-v0";
const SCOPE: &str = "finite_direct_kseg0_identity_rdram_aligned_word_writeback";
const LINE_BYTES: usize = 16;
const DCACHE_SLOTS: u16 = 512;
const RDRAM_BYTES: u32 = 0x0080_0000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum DcacheByteOrigin {
    BackingFill {
        backing_read_ordinal: u64,
        fill_ordinal: u64,
        physical: PhysicalAddr,
    },
    ResidentWordMutation {
        mutation_ordinal: u64,
        byte_index: u8,
    },
    Store64Subwrite {
        operation_ordinal: u64,
        subwrite_ordinal: u64,
        sequence: u8,
        byte_index: u8,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheWritebackReceipt {
    pub begin_ordinal: u64,
    pub backing_write_ordinal: u64,
    pub slot: u16,
    /// Source-derived resident generation: the fill event ordinal.
    pub resident_generation: u64,
    /// Source-derived revision: the latest fill/mutation event ordinal.
    pub resident_revision: u64,
    pub physical_line: PhysicalAddr,
    pub origins: [DcacheByteOrigin; LINE_BYTES],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheWritebackReport {
    pub format: String,
    pub scope: String,
    pub source_sha256: String,
    pub events: usize,
    pub backing_reads: usize,
    pub fills: usize,
    pub resident_word_mutations: usize,
    pub invalidations: usize,
    pub retired_unexported_mutations: usize,
    pub successful_backing_writebacks: usize,
    pub receipts: Vec<DcacheWritebackReceipt>,
    pub sensor_coverage_certified: bool,
    pub cache_semantics_complete: bool,
    pub tlb_cacheability_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

/// A captured backing write is diagnostic context, never the resident source.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheBackingWord {
    pub write_ordinal: u64,
    pub from_writeback: bool,
    pub payload: [u8; 4],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheResidentReadReceipt {
    pub read_ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub effective_virtual: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub slot: u16,
    pub payload: [u8; 4],
    pub resident_generation: u64,
    pub resident_revision: u64,
    pub origins: [DcacheByteOrigin; 4],
    pub current_captured_backing: Option<DcacheBackingWord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheResidentReadReport {
    pub format: String,
    pub writeback: DcacheWritebackReport,
    pub observed_backing_word_mutations: usize,
    pub reads: Vec<DcacheResidentReadReceipt>,
    pub cpu_operand_dataflow_certified: bool,
    pub pointer_table_immutability_certified: bool,
    pub executable_target_identity_certified: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub store64_operations: Option<Vec<DcacheStore64Operation>>,
}

/// Already observed decoded context in the bounded kernel32/BEV1 fixture scope.
/// Register snapshots bind operands, not the ancestry of their definitions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheStore64Context {
    pub pc: GuestVirtualAddr,
    pub word: u32,
    pub gpr: [u64; 32],
    pub after_gpr: [u64; 32],
    pub after_pc: GuestVirtualAddr,
    pub little: bool,
    pub exception: u8,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DcacheStore64Operation {
    pub ordinal: u64,
    pub context: DcacheStore64Context,
    pub receipt: AresStore64Receipt,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Store64 {
        ordinal: u64,
        context: Box<DcacheStore64Context>,
        receipt: AresStore64Receipt,
    },
    Store64Subwrite {
        ordinal: u64,
        sequence: u8,
        event: String,
        physical: PhysicalAddr,
        slot: u16,
        payload: Vec<u8>,
        resident_after: [u8; LINE_BYTES],
    },
    BackingWordMutation {
        ordinal: u64,
        physical: PhysicalAddr,
        payload: [u8; 4],
    },
    CachedWordRead {
        ordinal: u64,
        pc: GuestVirtualAddr,
        effective_virtual: GuestVirtualAddr,
        physical: PhysicalAddr,
        slot: u16,
        payload: [u8; 4],
    },
    BackingRead {
        ordinal: u64,
        physical_line: PhysicalAddr,
        payload: [u8; LINE_BYTES],
    },
    Fill {
        ordinal: u64,
        slot: u16,
        physical_line: PhysicalAddr,
        payload: [u8; LINE_BYTES],
    },
    ResidentWordMutation {
        ordinal: u64,
        slot: u16,
        physical: PhysicalAddr,
        payload: [u8; 4],
    },
    WritebackBegin {
        ordinal: u64,
        slot: u16,
        physical_line: PhysicalAddr,
    },
    BackingWrite {
        ordinal: u64,
        physical_line: PhysicalAddr,
        payload: [u8; LINE_BYTES],
    },
    WritebackEnd {
        ordinal: u64,
        slot: u16,
    },
    Invalidate {
        ordinal: u64,
        slot: u16,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Store64 { ordinal, .. }
            | Self::Store64Subwrite { ordinal, .. }
            | Self::BackingWordMutation { ordinal, .. }
            | Self::CachedWordRead { ordinal, .. }
            | Self::BackingRead { ordinal, .. }
            | Self::Fill { ordinal, .. }
            | Self::ResidentWordMutation { ordinal, .. }
            | Self::WritebackBegin { ordinal, .. }
            | Self::BackingWrite { ordinal, .. }
            | Self::WritebackEnd { ordinal, .. }
            | Self::Invalidate { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Clone)]
struct ResidentLine {
    generation: u64,
    revision: u64,
    physical_line: PhysicalAddr,
    payload: [u8; LINE_BYTES],
    origins: [DcacheByteOrigin; LINE_BYTES],
    unexported_dirty: bool,
}

#[derive(Clone)]
struct PendingWriteback {
    begin_ordinal: u64,
    slot: u16,
    generation: u64,
    revision: u64,
    physical_line: PhysicalAddr,
    payload: [u8; LINE_BYTES],
    origins: [DcacheByteOrigin; LINE_BYTES],
    exported: bool,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn validate_line_address(address: PhysicalAddr) -> Result<(), String> {
    require(
        address.0.is_multiple_of(LINE_BYTES as u32)
            && address
                .0
                .checked_add(LINE_BYTES as u32)
                .is_some_and(|end| end <= RDRAM_BYTES),
        "D-cache line outside bounded aligned RDRAM",
    )
}

fn canonical32(value: u64) -> bool {
    let low = value as u32;
    value == u64::from(low) || value == (low as i32 as i64) as u64
}

fn validate_store64_context(
    context: &DcacheStore64Context,
    receipt: &AresStore64Receipt,
) -> Result<(), String> {
    receipt.validate()?;
    let kind = match context.word >> 26 {
        0x3f => Store64Kind::Sd,
        0x2c => Store64Kind::Sdl,
        0x2d => Store64Kind::Sdr,
        _ => return Err("store64 context contains an unsupported decoded instruction".into()),
    };
    let base = ((context.word >> 21) & 31) as usize;
    let source = ((context.word >> 16) & 31) as usize;
    let address = context.gpr[base].wrapping_add((context.word as i16 as i64) as u64);
    let low = address as u32;
    require(
        canonical32(context.pc.0)
            && canonical32(context.after_pc.0)
            && context.pc.0.is_multiple_of(4)
            && context.gpr[0] == 0
            && context.gpr == context.after_gpr,
        "store64 context has invalid PC/register boundaries",
    )?;
    require(
        canonical32(address)
            && (0x8000_0000..0xa000_0000).contains(&low)
            && (low & 0x1fff_fff8)
                .checked_add(8)
                .is_some_and(|end| end <= RDRAM_BYTES)
            && receipt.cached
            && receipt.site.0 == context.pc.0 as u32
            && receipt.address.0 == low
            && receipt.source_value == context.gpr[source]
            && receipt.kind == kind
            && receipt.endian
                == if context.little {
                    StoreEndian::Little
                } else {
                    StoreEndian::Big
                },
        "store64 receipt disagrees with decoded direct cached operand context",
    )?;
    if kind == Store64Kind::Sd && low & 7 != 0 {
        use crate::exception_roots::{
            ExceptionClass, ExceptionRootInput, KernelAddressMode, resolve_exception_root,
        };
        let root = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        })
        .root;
        require(
            receipt.outcome == StoreOutcome::RejectedBeforeMutation
                && context.exception == 5
                && context.after_pc.0 as u32 == root.0 as u32,
            "store64 alignment failure contradicts bounded BEV1 exception result",
        )?;
    } else {
        require(
            receipt.outcome == StoreOutcome::Completed
                && context.exception == 0
                && context.after_pc.0 as u32 == (context.pc.0 as u32).wrapping_add(4),
            "store64 completion contradicts instruction/control result",
        )?;
    }
    Ok(())
}

/// Replays a separately authenticated finite source.
///
/// `expected_sha256` is an external trust input, not a digest copied from the
/// supplied JSON. This validates only the bounded direct-KSEG0, identity-RDRAM,
/// aligned-word mutation contract represented by the source.
pub fn inspect_dcache_writeback_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<DcacheWritebackReport, String> {
    Ok(replay(source, expected_sha256, false, false)?.writeback)
}

/// Normalized completed Word operations, not a decoded LW/register/dispatch proof.
/// Reads and exports consume the same resident generations and byte origins.
pub fn inspect_dcache_resident_read_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<DcacheResidentReadReport, String> {
    replay(source, expected_sha256, true, false)
}

pub fn inspect_dcache_store64_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<DcacheResidentReadReport, String> {
    replay(source, expected_sha256, true, true)
}

pub fn verify_dcache_store64_report(
    report: &DcacheResidentReadReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_dcache_store64_history(source, expected_sha256)?,
        "D-cache store64 report does not match complete source/receipt",
    )
}

pub fn verify_dcache_resident_read_report(
    report: &DcacheResidentReadReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_dcache_resident_read_history(source, expected_sha256)?,
        "D-cache resident read report does not match complete source/receipt",
    )
}

fn replay(
    source: &[u8],
    expected_sha256: &str,
    with_reads: bool,
    with_store64: bool,
) -> Result<DcacheResidentReadReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "D-cache writeback source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format
            == if with_store64 {
                STORE64_FORMAT
            } else if with_reads {
                READ_FORMAT
            } else {
                FORMAT
            },
        "unsupported D-cache writeback history format",
    )?;

    let mut next_ordinal = 1u64;
    let mut lines: BTreeMap<u16, ResidentLine> = BTreeMap::new();
    let mut pending: Option<PendingWriteback> = None;
    let mut pending_read: Option<(u64, PhysicalAddr, [u8; LINE_BYTES])> = None;
    let mut receipts = Vec::new();
    let mut backing_reads = 0usize;
    let mut fills = 0usize;
    let mut mutations = 0usize;
    let mut invalidations = 0usize;
    let mut retired_unexported = 0usize;
    let mut backing_words = BTreeMap::<PhysicalAddr, DcacheBackingWord>::new();
    let mut backing_mutations = 0usize;
    let mut reads = Vec::new();
    let mut store64_operations = Vec::new();
    let mut pending_store: Option<(u64, AresStore64Receipt, usize)> = None;
    let mut store_ids = std::collections::BTreeSet::new();

    for event in history.events {
        let ordinal = event.ordinal();
        require(
            ordinal == next_ordinal,
            "noncontiguous D-cache writeback event ordinals",
        )?;
        next_ordinal += 1;
        if pending_read.is_some() && !matches!(&event, Event::Fill { .. }) {
            return Err("backing read was not immediately consumed by a fill".into());
        }
        require(
            pending_store.is_none() || matches!(&event, Event::Store64Subwrite { .. }),
            "store64 operation missing its next ordered subwrite",
        )?;

        match event {
            Event::Store64 {
                ordinal,
                context,
                receipt,
            } => {
                require(with_store64, "store64 event outside explicit v2 scope")?;
                require(
                    pending.is_none(),
                    "store64 operation during active writeback",
                )?;
                validate_store64_context(&context, &receipt)?;
                require(
                    store_ids.insert(receipt.operation_event.clone()),
                    "reused store64 operation identity",
                )?;
                for write in &receipt.subwrites {
                    require(
                        store_ids.insert(write.event.clone()),
                        "reused store64 subwrite identity",
                    )?;
                }
                if !receipt.subwrites.is_empty() {
                    pending_store = Some((ordinal, receipt.clone(), 0));
                }
                store64_operations.push(DcacheStore64Operation {
                    ordinal,
                    context: *context,
                    receipt,
                });
            }
            Event::Store64Subwrite {
                ordinal,
                sequence,
                event,
                physical,
                slot,
                payload,
                resident_after,
            } => {
                require(with_store64, "store64 subwrite outside explicit v2 scope")?;
                let (operation_ordinal, receipt, next) = pending_store
                    .as_mut()
                    .ok_or("store64 subwrite without an active operation")?;
                let expected = &receipt.subwrites[*next];
                let raw = expected.value.to_be_bytes();
                let width = usize::from(expected.bytes);
                require(
                    sequence == expected.sequence
                        && event == expected.event
                        && physical == expected.sink_physical
                        && payload == raw[8 - width..],
                    "store64 subwrite differs from its exact ordered effect",
                )?;
                let handler = expected.handler_address.0;
                let selected = (handler & 0x1fff_ffff)
                    ^ if receipt.endian == StoreEndian::Little {
                        8 - u32::from(expected.bytes)
                    } else {
                        0
                    };
                require(
                    physical.0 == selected
                        && physical.0.is_multiple_of(u32::from(expected.bytes))
                        && physical.0 < RDRAM_BYTES
                        && u32::from(slot) == (physical.0 >> 4) & 0x1ff,
                    "store64 subwrite violates direct/endian/index sink identity",
                )?;
                let line = lines
                    .get_mut(&slot)
                    .ok_or("store64 subwrite lacks prefetched resident line")?;
                let offset = physical
                    .0
                    .checked_sub(line.physical_line.0)
                    .ok_or("store64 subwrite precedes resident line")?
                    as usize;
                require(
                    offset + width <= LINE_BYTES,
                    "store64 subwrite crosses resident line",
                )?;
                line.payload[offset..offset + width].copy_from_slice(&payload);
                require(
                    line.payload == resident_after,
                    "store64 subwrite/full resident snapshot mismatch",
                )?;
                for index in 0..width {
                    line.origins[offset + index] = DcacheByteOrigin::Store64Subwrite {
                        operation_ordinal: *operation_ordinal,
                        subwrite_ordinal: ordinal,
                        sequence,
                        byte_index: index as u8,
                    };
                }
                line.revision = ordinal;
                line.unexported_dirty = true;
                *next += 1;
                if *next == receipt.subwrites.len() {
                    pending_store = None;
                }
            }
            Event::BackingWordMutation {
                ordinal,
                physical,
                payload,
            } => {
                require(with_reads, "resident-read event in v0 writeback history")?;
                require(
                    pending.is_none(),
                    "external backing mutation during active writeback",
                )?;
                require(
                    physical.0.is_multiple_of(4) && physical.0 < RDRAM_BYTES,
                    "backing word mutation outside aligned RDRAM",
                )?;
                backing_words.insert(
                    physical,
                    DcacheBackingWord {
                        write_ordinal: ordinal,
                        from_writeback: false,
                        payload,
                    },
                );
                backing_mutations += 1;
            }
            Event::CachedWordRead {
                ordinal,
                pc,
                effective_virtual,
                physical,
                slot,
                payload,
            } => {
                require(with_reads, "resident-read event in v0 writeback history")?;
                require(pending.is_none(), "cached read during active writeback")?;
                require(pc.0.is_multiple_of(4), "unaligned cached read PC")?;
                let low = effective_virtual.0 as u32;
                require(
                    (effective_virtual.0 == u64::from(low)
                        || effective_virtual.0 == (low as i32 as i64) as u64)
                        && (0x8000_0000..0xa000_0000).contains(&low)
                        && low & 0x1fff_ffff == physical.0
                        && physical.0.is_multiple_of(4)
                        && physical.0 < RDRAM_BYTES,
                    "cached read outside direct KSEG0 identity aligned RDRAM",
                )?;
                require(
                    u32::from(slot) == (physical.0 >> 4) & 0x1ff,
                    "cached read slot contradicts direct identity address",
                )?;
                let line = lines
                    .get(&slot)
                    .ok_or("cached read without captured resident line")?;
                let offset = physical
                    .0
                    .checked_sub(line.physical_line.0)
                    .ok_or("cached read precedes resident line")?
                    as usize;
                require(
                    offset <= LINE_BYTES - 4,
                    "cached read selects a different resident line",
                )?;
                require(
                    line.payload[offset..offset + 4] == payload,
                    "cached read differs from captured resident bytes",
                )?;
                reads.push(DcacheResidentReadReceipt {
                    read_ordinal: ordinal,
                    pc,
                    effective_virtual,
                    physical,
                    slot,
                    payload,
                    resident_generation: line.generation,
                    resident_revision: line.revision,
                    origins: line.origins[offset..offset + 4].try_into().unwrap(),
                    current_captured_backing: backing_words.get(&physical).cloned(),
                });
            }
            Event::BackingRead {
                ordinal,
                physical_line,
                payload,
            } => {
                require(pending.is_none(), "backing read during active writeback")?;
                validate_line_address(physical_line)?;
                backing_reads += 1;
                pending_read = Some((ordinal, physical_line, payload));
            }
            Event::Fill {
                ordinal,
                slot,
                physical_line,
                payload,
            } => {
                require(
                    slot < DCACHE_SLOTS,
                    "D-cache fill slot outside bounded cache",
                )?;
                require(pending.is_none(), "fill during active writeback")?;
                validate_line_address(physical_line)?;
                // Only the declared direct-KSEG0 identity scope makes the
                // virtual cache index equal these low physical address bits.
                // TLB/alias cases require a separate authenticated virtual index.
                require(
                    u32::from(slot) == (physical_line.0 >> 4) & 0x1ff,
                    "D-cache slot contradicts direct identity fill address",
                )?;
                let (read_ordinal, read_line, read_payload) = pending_read
                    .take()
                    .ok_or("fill without immediately preceding backing read")?;
                require(
                    read_ordinal.checked_add(1) == Some(ordinal)
                        && read_line == physical_line
                        && read_payload == payload,
                    "fill/backing-read identity mismatch",
                )?;
                for lane in 0..if with_reads { 4 } else { 0 } {
                    if let Some(word) = backing_words.get(&PhysicalAddr(physical_line.0 + lane * 4))
                    {
                        let start = lane as usize * 4;
                        require(
                            payload[start..start + 4] == word.payload,
                            "fill contradicts captured backing word mutation",
                        )?;
                    }
                }
                if lines.get(&slot).is_some_and(|line| line.unexported_dirty) {
                    return Err("dirty replacement without successful writeback".into());
                }
                let origins = std::array::from_fn(|index| DcacheByteOrigin::BackingFill {
                    backing_read_ordinal: read_ordinal,
                    fill_ordinal: ordinal,
                    physical: PhysicalAddr(physical_line.0 + index as u32),
                });
                lines.insert(
                    slot,
                    ResidentLine {
                        generation: ordinal,
                        revision: ordinal,
                        physical_line,
                        payload,
                        origins,
                        unexported_dirty: false,
                    },
                );
                fills += 1;
            }
            Event::ResidentWordMutation {
                ordinal,
                slot,
                physical,
                payload,
            } => {
                require(
                    slot < DCACHE_SLOTS,
                    "D-cache mutation slot outside bounded cache",
                )?;
                require(
                    physical.0.is_multiple_of(4),
                    "resident word mutation is not 4-byte aligned",
                )?;
                let line = lines
                    .get_mut(&slot)
                    .ok_or("resident word mutation without a resident line")?;
                let offset = physical
                    .0
                    .checked_sub(line.physical_line.0)
                    .ok_or("resident word mutation precedes line backing")?
                    as usize;
                require(
                    offset <= LINE_BYTES - payload.len(),
                    "resident word mutation crosses the resident line",
                )?;
                line.payload[offset..offset + payload.len()].copy_from_slice(&payload);
                for index in 0..payload.len() {
                    line.origins[offset + index] = DcacheByteOrigin::ResidentWordMutation {
                        mutation_ordinal: ordinal,
                        byte_index: index as u8,
                    };
                }
                line.revision = ordinal;
                line.unexported_dirty = true;
                mutations += 1;
            }
            Event::WritebackBegin {
                ordinal,
                slot,
                physical_line,
            } => {
                require(
                    slot < DCACHE_SLOTS,
                    "D-cache writeback slot outside bounded cache",
                )?;
                require(pending.is_none(), "nested D-cache writeback")?;
                validate_line_address(physical_line)?;
                let line = lines
                    .get(&slot)
                    .ok_or("writeback begin without a resident line")?;
                require(
                    line.physical_line == physical_line,
                    "writeback begin selected the wrong resident line",
                )?;
                require(
                    line.unexported_dirty,
                    "writeback begin without unexported resident mutation",
                )?;
                pending = Some(PendingWriteback {
                    begin_ordinal: ordinal,
                    slot,
                    generation: line.generation,
                    revision: line.revision,
                    physical_line,
                    payload: line.payload,
                    origins: line.origins,
                    exported: false,
                });
            }
            Event::BackingWrite {
                ordinal,
                physical_line,
                payload,
            } => {
                validate_line_address(physical_line)?;
                let writeback = pending
                    .as_mut()
                    .ok_or("backing write without active D-cache writeback")?;
                require(
                    !writeback.exported,
                    "duplicate backing write in one writeback",
                )?;
                require(
                    writeback.physical_line == physical_line && writeback.payload == payload,
                    "backing write does not match the captured resident snapshot",
                )?;
                let line = lines
                    .get_mut(&writeback.slot)
                    .ok_or("writeback resident line disappeared")?;
                require(
                    line.generation == writeback.generation
                        && line.revision == writeback.revision
                        && line.physical_line == writeback.physical_line,
                    "resident generation/revision changed after writeback begin",
                )?;
                receipts.push(DcacheWritebackReceipt {
                    begin_ordinal: writeback.begin_ordinal,
                    backing_write_ordinal: ordinal,
                    slot: writeback.slot,
                    resident_generation: writeback.generation,
                    resident_revision: writeback.revision,
                    physical_line,
                    origins: writeback.origins,
                });
                line.unexported_dirty = false;
                for lane in 0..if with_reads { 4 } else { 0 } {
                    let start = lane as usize * 4;
                    backing_words.insert(
                        PhysicalAddr(physical_line.0 + lane * 4),
                        DcacheBackingWord {
                            write_ordinal: ordinal,
                            from_writeback: true,
                            payload: payload[start..start + 4].try_into().unwrap(),
                        },
                    );
                }
                writeback.exported = true;
            }
            Event::WritebackEnd { slot, .. } => {
                let writeback = pending
                    .take()
                    .ok_or("writeback end without active D-cache writeback")?;
                require(writeback.slot == slot, "writeback end slot mismatch")?;
                require(
                    writeback.exported,
                    "writeback ended without an exact successful backing write",
                )?;
            }
            Event::Invalidate { slot, .. } => {
                require(
                    slot < DCACHE_SLOTS,
                    "D-cache invalidate slot outside bounded cache",
                )?;
                require(
                    pending
                        .as_ref()
                        .is_none_or(|writeback| writeback.slot != slot),
                    "invalidate during active writeback",
                )?;
                if let Some(line) = lines.remove(&slot)
                    && line.unexported_dirty
                {
                    retired_unexported += 1;
                }
                invalidations += 1;
            }
        }
    }

    require(
        pending_read.is_none(),
        "source ended after unmatched backing read",
    )?;
    require(
        pending.is_none(),
        "source ended during active D-cache writeback",
    )?;
    require(
        pending_store.is_none(),
        "source ended during an incomplete store64 operation",
    )?;

    Ok(DcacheResidentReadReport {
        format: if with_store64 {
            "plaid-dcache-store64-writeback-report-v2"
        } else {
            "plaid-dcache-resident-read-report-v1"
        }
        .into(),
        observed_backing_word_mutations: backing_mutations,
        reads,
        cpu_operand_dataflow_certified: false,
        pointer_table_immutability_certified: false,
        executable_target_identity_certified: false,
        store64_operations: with_store64.then_some(store64_operations),
        writeback: DcacheWritebackReport {
            format: REPORT_FORMAT.into(),
            scope: if with_store64 {
                "finite_prefilled_direct_kseg0_kernel32_bev1_store64_writeback"
            } else {
                SCOPE
            }
            .into(),
            source_sha256: digest,
            events: (next_ordinal - 1) as usize,
            backing_reads,
            fills,
            resident_word_mutations: mutations,
            invalidations,
            retired_unexported_mutations: retired_unexported,
            successful_backing_writebacks: receipts.len(),
            receipts,
            sensor_coverage_certified: false,
            cache_semantics_complete: false,
            tlb_cacheability_certified: false,
            executable_lifetime_certified: false,
            native_complete: false,
        },
    })
}

pub fn verify_dcache_writeback_report(
    report: &DcacheWritebackReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_dcache_writeback_history(source, expected_sha256)?,
        "D-cache writeback report does not match complete source/receipt",
    )
}
