//! Bounded source-bound D-cache resident-to-backing writeback lineage.
//!
//! This module proves only a finite causal promotion: an already-authenticated
//! cache-resident aligned word mutation may become backing-memory provenance when
//! the same resident generation/revision is exported by an exact successful
//! 16-byte RDRAM writeback. Equal bytes, addresses, tags, or a later resident line
//! never substitute for that chronology. Sensor completeness, TLB/cacheability
//! semantics, executable lifetime, and native readiness remain separate.

use crate::{program::PhysicalAddr, rom::sha256};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-dcache-writeback-history-v0";
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

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
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
            Self::BackingRead { ordinal, .. }
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

/// Replays a separately authenticated finite source.
///
/// `expected_sha256` is an external trust input, not a digest copied from the
/// supplied JSON. This validates only the bounded direct-KSEG0, identity-RDRAM,
/// aligned-word mutation contract represented by the source.
pub fn inspect_dcache_writeback_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<DcacheWritebackReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "D-cache writeback source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
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

        match event {
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

    Ok(DcacheWritebackReport {
        format: REPORT_FORMAT.into(),
        scope: SCOPE.into(),
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
