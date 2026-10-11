//! Bounded source-bound replay for RSP DMEM bytes exported by SP write-DMA.
//!
//! This module consumes an externally authenticated, complete-for-declared-scope
//! chronology expressed in logical DMEM byte addresses. It derives DMA source
//! offsets from the active descriptor and carries measured per-byte DMEM writer
//! generations into completed RDRAM effects. Payload equality is only an integrity
//! check and never selects provenance.
//!
//! The replay does not authenticate the upstream RSP/CPU writer sensor, prove that
//! every architectural mutation was captured, establish DMA hardware timing, or
//! certify downstream executable consumption/cache lifetime/native completeness.

use crate::{program::PhysicalAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-rsp-dmem-dma-egress-v0";
const DMEM_BYTES: usize = 4096;
const DMA_FRAGMENT_BYTES: usize = 8;
const MAX_DMA_ROWS: u16 = 256;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "producer", deny_unknown_fields)]
pub enum DmemWriterSource {
    RspSink { context: u64 },
    CpuSpSink { context: u64 },
    OtherMeasured { context: u64 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "origin", deny_unknown_fields)]
pub enum DmemByteOrigin {
    InitialSnapshot {
        snapshot_ordinal: u64,
    },
    MeasuredWrite {
        event_ordinal: u64,
        source: DmemWriterSource,
    },
    Unknown {
        event_ordinal: u64,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExportedDmemByte {
    pub dmem_offset: u16,
    pub rdram_address: PhysicalAddr,
    pub value: u8,
    pub origin: DmemByteOrigin,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmaFragmentReceipt {
    pub transfer_generation: u64,
    pub begin_ordinal: u64,
    pub effect_ordinal: u64,
    pub fragment_index: u32,
    pub dmem_start: u16,
    pub rdram_start: PhysicalAddr,
    pub exports: Vec<ExportedDmemByte>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspDmemDmaEgressReport {
    pub format: String,
    pub source_sha256: String,
    pub measured_dmem_writes: usize,
    pub unknown_dmem_writes: usize,
    pub dma_transfers: usize,
    pub dma_fragments: usize,
    pub exported_bytes: usize,
    pub fragments: Vec<DmaFragmentReceipt>,
    pub writer_sensor_coverage_certified: bool,
    pub writer_source_ancestry_certified: bool,
    pub dma_request_lifecycle_certified: bool,
    pub hardware_timing_certified: bool,
    pub rdram_lifetime_certified: bool,
    pub executable_consumption_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    DmemSnapshot {
        ordinal: u64,
        bytes: Vec<u8>,
    },
    DmemWrite {
        ordinal: u64,
        start: u16,
        bytes: Vec<u8>,
        source: DmemWriterSource,
    },
    UnknownDmemWrite {
        ordinal: u64,
        start: u16,
        size: u16,
    },
    DmaBegin {
        ordinal: u64,
        dmem_start: u16,
        rdram_start: PhysicalAddr,
        row_bytes: u16,
        rows: u16,
        skip: u16,
    },
    DmaFragment {
        ordinal: u64,
        context: u64,
        current_dmem: u16,
        current_rdram: PhysicalAddr,
        bytes: Vec<u8>,
    },
    DmaEnd {
        ordinal: u64,
        context: u64,
    },
}

#[derive(Debug, Clone)]
struct DmemCell {
    value: Option<u8>,
    origin: DmemByteOrigin,
}

#[derive(Debug)]
struct ActiveDma {
    transfer_generation: u64,
    begin_ordinal: u64,
    dmem_start: u16,
    rdram_start: PhysicalAddr,
    row_bytes: u16,
    rows: u16,
    skip: u16,
    next_fragment: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn checked_dmem_index(start: u16, lane: usize) -> usize {
    (usize::from(start) + lane) & (DMEM_BYTES - 1)
}

fn expected_fragment(active: &ActiveDma) -> Result<(u16, PhysicalAddr), String> {
    let fragments_per_row = u64::from(active.row_bytes / DMA_FRAGMENT_BYTES as u16);
    let index = u64::from(active.next_fragment);
    let row = index / fragments_per_row;
    let fragment_in_row = index % fragments_per_row;
    require(row < u64::from(active.rows), "too many SP DMA fragments")?;

    let dmem_delta = index
        .checked_mul(DMA_FRAGMENT_BYTES as u64)
        .ok_or("SP DMA DMEM offset overflow")?;
    let dmem = ((u64::from(active.dmem_start) + dmem_delta) % DMEM_BYTES as u64) as u16;

    let row_stride = u64::from(active.row_bytes)
        .checked_add(u64::from(active.skip))
        .ok_or("SP DMA row stride overflow")?;
    let rdram_delta = row
        .checked_mul(row_stride)
        .and_then(|base| {
            fragment_in_row
                .checked_mul(DMA_FRAGMENT_BYTES as u64)
                .and_then(|within| base.checked_add(within))
        })
        .ok_or("SP DMA RDRAM offset overflow")?;
    let rdram = u64::from(active.rdram_start.0)
        .checked_add(rdram_delta)
        .ok_or("SP DMA RDRAM address overflow")?;
    require(
        rdram <= u64::from(u32::MAX),
        "SP DMA RDRAM address overflow",
    )?;

    Ok((dmem, PhysicalAddr(rdram as u32)))
}

fn expected_fragment_count(active: &ActiveDma) -> u32 {
    u32::from(active.rows) * u32::from(active.row_bytes / DMA_FRAGMENT_BYTES as u16)
}

/// Replay a finite, externally SHA-bound DMEM/SP-DMA chronology.
///
/// `expected_sha256` must come from a separately trusted complete-source receipt.
/// A successful replay authenticates internal chronology and descriptor/effect joins
/// only; it does not certify that the producer observed every real mutation.
pub fn inspect_rsp_dmem_dma_egress(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspDmemDmaEgressReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP DMEM DMA source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported RSP DMEM DMA history format",
    )?;

    let mut next_ordinal = 1u64;
    let mut dmem: Option<Vec<DmemCell>> = None;
    let mut active: Option<ActiveDma> = None;
    let mut measured_dmem_writes = 0usize;
    let mut unknown_dmem_writes = 0usize;
    let mut dma_transfers = 0usize;
    let mut fragments = Vec::new();

    for event in history.events {
        let ordinal = match &event {
            Event::DmemSnapshot { ordinal, .. }
            | Event::DmemWrite { ordinal, .. }
            | Event::UnknownDmemWrite { ordinal, .. }
            | Event::DmaBegin { ordinal, .. }
            | Event::DmaFragment { ordinal, .. }
            | Event::DmaEnd { ordinal, .. } => *ordinal,
        };
        require(
            ordinal == next_ordinal,
            "noncontiguous RSP DMEM DMA event ordinals",
        )?;
        next_ordinal += 1;

        match event {
            Event::DmemSnapshot { ordinal, bytes } => {
                require(active.is_none(), "DMEM snapshot during active SP DMA")?;
                require(dmem.is_none(), "duplicate DMEM snapshot")?;
                require(
                    bytes.len() == DMEM_BYTES,
                    "DMEM snapshot must contain 4096 bytes",
                )?;
                dmem = Some(
                    bytes
                        .into_iter()
                        .map(|value| DmemCell {
                            value: Some(value),
                            origin: DmemByteOrigin::InitialSnapshot {
                                snapshot_ordinal: ordinal,
                            },
                        })
                        .collect(),
                );
            }
            Event::DmemWrite {
                ordinal,
                start,
                bytes,
                source,
            } => {
                require(
                    active.is_none(),
                    "DMEM mutation interleaved with active SP DMA",
                )?;
                let state = dmem.as_mut().ok_or("DMEM write before initial snapshot")?;
                require(
                    usize::from(start) < DMEM_BYTES,
                    "DMEM write start out of range",
                )?;
                require(
                    !bytes.is_empty() && bytes.len() <= DMEM_BYTES,
                    "invalid DMEM write size",
                )?;
                for (lane, value) in bytes.into_iter().enumerate() {
                    let index = checked_dmem_index(start, lane);
                    state[index] = DmemCell {
                        value: Some(value),
                        origin: DmemByteOrigin::MeasuredWrite {
                            event_ordinal: ordinal,
                            source: source.clone(),
                        },
                    };
                }
                measured_dmem_writes += 1;
            }
            Event::UnknownDmemWrite {
                ordinal,
                start,
                size,
            } => {
                require(
                    active.is_none(),
                    "unknown DMEM mutation interleaved with active SP DMA",
                )?;
                let state = dmem
                    .as_mut()
                    .ok_or("unknown DMEM write before initial snapshot")?;
                require(
                    usize::from(start) < DMEM_BYTES,
                    "unknown DMEM write start out of range",
                )?;
                require(
                    size != 0 && usize::from(size) <= DMEM_BYTES,
                    "invalid unknown DMEM write size",
                )?;
                for lane in 0..usize::from(size) {
                    let index = checked_dmem_index(start, lane);
                    state[index] = DmemCell {
                        value: None,
                        origin: DmemByteOrigin::Unknown {
                            event_ordinal: ordinal,
                        },
                    };
                }
                unknown_dmem_writes += 1;
            }
            Event::DmaBegin {
                ordinal,
                dmem_start,
                rdram_start,
                row_bytes,
                rows,
                skip,
            } => {
                require(dmem.is_some(), "SP DMA before initial DMEM snapshot")?;
                require(active.is_none(), "nested SP DMA transfer")?;
                require(
                    usize::from(dmem_start) < DMEM_BYTES
                        && dmem_start.is_multiple_of(DMA_FRAGMENT_BYTES as u16),
                    "unsupported unaligned SP DMA DMEM start",
                )?;
                require(
                    rdram_start.0.is_multiple_of(DMA_FRAGMENT_BYTES as u32),
                    "unsupported unaligned SP DMA RDRAM start",
                )?;
                require(
                    row_bytes != 0
                        && usize::from(row_bytes) <= DMEM_BYTES
                        && row_bytes.is_multiple_of(DMA_FRAGMENT_BYTES as u16),
                    "unsupported SP DMA row size",
                )?;
                require(
                    rows != 0 && rows <= MAX_DMA_ROWS,
                    "unsupported SP DMA row count",
                )?;
                require(
                    skip.is_multiple_of(DMA_FRAGMENT_BYTES as u16),
                    "unsupported unaligned SP DMA skip",
                )?;
                dma_transfers += 1;
                active = Some(ActiveDma {
                    transfer_generation: dma_transfers as u64,
                    begin_ordinal: ordinal,
                    dmem_start,
                    rdram_start,
                    row_bytes,
                    rows,
                    skip,
                    next_fragment: 0,
                });
            }
            Event::DmaFragment {
                ordinal,
                context,
                current_dmem,
                current_rdram,
                bytes,
            } => {
                let state = dmem
                    .as_ref()
                    .ok_or("SP DMA fragment before DMEM snapshot")?;
                let current = active
                    .as_mut()
                    .ok_or("SP DMA fragment without active transfer")?;
                require(
                    context == current.begin_ordinal,
                    "SP DMA fragment context mismatch",
                )?;
                require(
                    bytes.len() == DMA_FRAGMENT_BYTES,
                    "SP DMA fragment must contain eight bytes",
                )?;
                let (expected_dmem, expected_rdram) = expected_fragment(current)?;
                require(
                    (current_dmem, current_rdram) == (expected_dmem, expected_rdram),
                    "SP DMA fragment does not match current descriptor chronology",
                )?;

                let mut exports = Vec::with_capacity(DMA_FRAGMENT_BYTES);
                for (lane, value) in bytes.into_iter().enumerate() {
                    let dmem_index = checked_dmem_index(current_dmem, lane);
                    let cell = &state[dmem_index];
                    if let Some(expected) = cell.value {
                        require(
                            expected == value,
                            "SP DMA payload disagrees with measured DMEM state",
                        )?;
                    }
                    let rdram_address = current_rdram
                        .0
                        .checked_add(lane as u32)
                        .map(PhysicalAddr)
                        .ok_or("SP DMA byte address overflow")?;
                    exports.push(ExportedDmemByte {
                        dmem_offset: dmem_index as u16,
                        rdram_address,
                        value,
                        origin: cell.origin.clone(),
                    });
                }

                fragments.push(DmaFragmentReceipt {
                    transfer_generation: current.transfer_generation,
                    begin_ordinal: current.begin_ordinal,
                    effect_ordinal: ordinal,
                    fragment_index: current.next_fragment,
                    dmem_start: current_dmem,
                    rdram_start: current_rdram,
                    exports,
                });
                current.next_fragment += 1;
            }
            Event::DmaEnd { context, .. } => {
                let current = active.take().ok_or("SP DMA end without active transfer")?;
                require(
                    context == current.begin_ordinal,
                    "SP DMA end context mismatch",
                )?;
                require(
                    current.next_fragment == expected_fragment_count(&current),
                    "SP DMA ended before all descriptor fragments completed",
                )?;
            }
        }
    }

    require(dmem.is_some(), "missing initial DMEM snapshot")?;
    require(active.is_none(), "truncated SP DMA transfer")?;
    let exported_bytes = fragments
        .len()
        .checked_mul(DMA_FRAGMENT_BYTES)
        .ok_or("export count overflow")?;

    Ok(RspDmemDmaEgressReport {
        format: history.format,
        source_sha256: digest,
        measured_dmem_writes,
        unknown_dmem_writes,
        dma_transfers,
        dma_fragments: fragments.len(),
        exported_bytes,
        fragments,
        writer_sensor_coverage_certified: false,
        writer_source_ancestry_certified: false,
        dma_request_lifecycle_certified: false,
        hardware_timing_certified: false,
        rdram_lifetime_certified: false,
        executable_consumption_certified: false,
        native_complete: false,
    })
}

pub fn verify_rsp_dmem_dma_egress_report(
    report: &RspDmemDmaEgressReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_rsp_dmem_dma_egress(source, expected_sha256)?,
        "RSP DMEM DMA report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn snapshot() -> Vec<u8> {
        (0..DMEM_BYTES)
            .map(|index| ((index * 37 + 11) & 0xff) as u8)
            .collect()
    }

    fn encode(events: Vec<Event>) -> Vec<u8> {
        serde_json::to_vec(&History {
            format: FORMAT.into(),
            events,
        })
        .unwrap()
    }

    fn source(kind: &str, context: u64) -> DmemWriterSource {
        match kind {
            "rsp" => DmemWriterSource::RspSink { context },
            "cpu" => DmemWriterSource::CpuSpSink { context },
            _ => DmemWriterSource::OtherMeasured { context },
        }
    }

    fn research_shape_history() -> Vec<u8> {
        let initial = snapshot();
        let mut state = initial.clone();
        let same = vec![state[0x40]];
        let scalar = vec![0x11, 0x22, 0x33, 0x44];
        let vector = vec![0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6, 0xa7];
        let cpu = vec![0xde, 0xad, 0xbe, 0xef];

        state[0x40] = same[0];
        state[0x44..0x48].copy_from_slice(&scalar);
        state[0x48..0x50].copy_from_slice(&vector);
        state[0x4c..0x50].copy_from_slice(&cpu);
        let first = state[0x40..0x48].to_vec();
        let second = state[0x48..0x50].to_vec();

        let wrap = vec![0x91, 0x92, 0x93, 0x94];
        state[0xffe] = wrap[0];
        state[0xfff] = wrap[1];
        state[0x000] = wrap[2];
        state[0x001] = wrap[3];
        let wrap_first = state[0xff8..0x1000].to_vec();
        let wrap_second = state[0x000..0x008].to_vec();
        debug_assert_eq!(wrap_first.len(), DMA_FRAGMENT_BYTES);
        debug_assert_eq!(wrap_second.len(), DMA_FRAGMENT_BYTES);

        encode(vec![
            Event::DmemSnapshot {
                ordinal: 1,
                bytes: initial,
            },
            Event::DmemWrite {
                ordinal: 2,
                start: 0x040,
                bytes: same,
                source: source("rsp", 100),
            },
            Event::DmemWrite {
                ordinal: 3,
                start: 0x044,
                bytes: scalar,
                source: source("rsp", 101),
            },
            Event::DmemWrite {
                ordinal: 4,
                start: 0x048,
                bytes: vector,
                source: source("rsp", 102),
            },
            Event::DmemWrite {
                ordinal: 5,
                start: 0x04c,
                bytes: cpu,
                source: source("cpu", 200),
            },
            Event::DmaBegin {
                ordinal: 6,
                dmem_start: 0x040,
                rdram_start: PhysicalAddr(0x1000),
                row_bytes: 8,
                rows: 2,
                skip: 8,
            },
            Event::DmaFragment {
                ordinal: 7,
                context: 6,
                current_dmem: 0x040,
                current_rdram: PhysicalAddr(0x1000),
                bytes: first,
            },
            Event::DmaFragment {
                ordinal: 8,
                context: 6,
                current_dmem: 0x048,
                current_rdram: PhysicalAddr(0x1010),
                bytes: second,
            },
            Event::DmaEnd {
                ordinal: 9,
                context: 6,
            },
            Event::DmemWrite {
                ordinal: 10,
                start: 0xffe,
                bytes: wrap,
                source: source("rsp", 103),
            },
            Event::DmaBegin {
                ordinal: 11,
                dmem_start: 0xff8,
                rdram_start: PhysicalAddr(0x2000),
                row_bytes: 16,
                rows: 1,
                skip: 0,
            },
            Event::DmaFragment {
                ordinal: 12,
                context: 11,
                current_dmem: 0xff8,
                current_rdram: PhysicalAddr(0x2000),
                bytes: wrap_first,
            },
            Event::DmaFragment {
                ordinal: 13,
                context: 11,
                current_dmem: 0x000,
                current_rdram: PhysicalAddr(0x2008),
                bytes: wrap_second,
            },
            Event::DmaEnd {
                ordinal: 14,
                context: 11,
            },
        ])
    }

    #[test]
    fn reproduces_research_shape_without_value_based_origin_selection() {
        let bytes = research_shape_history();
        let digest = sha256(&bytes);
        let report = inspect_rsp_dmem_dma_egress(&bytes, &digest).unwrap();

        assert_eq!(report.measured_dmem_writes, 5);
        assert_eq!(report.unknown_dmem_writes, 0);
        assert_eq!(report.dma_transfers, 2);
        assert_eq!(report.dma_fragments, 4);
        assert_eq!(report.exported_bytes, 32);
        assert_eq!(report.fragments[0].dmem_start, 0x040);
        assert_eq!(report.fragments[1].dmem_start, 0x048);
        assert_eq!(report.fragments[2].dmem_start, 0xff8);
        assert_eq!(report.fragments[3].dmem_start, 0x000);
        assert_eq!(report.fragments[0].rdram_start, PhysicalAddr(0x1000));
        assert_eq!(report.fragments[1].rdram_start, PhysicalAddr(0x1010));
        assert_eq!(report.fragments[2].rdram_start, PhysicalAddr(0x2000));
        assert_eq!(report.fragments[3].rdram_start, PhysicalAddr(0x2008));

        let mut rsp = 0usize;
        let mut cpu = 0usize;
        let mut initial = 0usize;
        let mut unknown = 0usize;
        for export in report
            .fragments
            .iter()
            .flat_map(|fragment| &fragment.exports)
        {
            match &export.origin {
                DmemByteOrigin::MeasuredWrite {
                    source: DmemWriterSource::RspSink { .. },
                    ..
                } => rsp += 1,
                DmemByteOrigin::MeasuredWrite {
                    source: DmemWriterSource::CpuSpSink { .. },
                    ..
                } => cpu += 1,
                DmemByteOrigin::InitialSnapshot { .. } => initial += 1,
                DmemByteOrigin::Unknown { .. } => unknown += 1,
                DmemByteOrigin::MeasuredWrite {
                    source: DmemWriterSource::OtherMeasured { .. },
                    ..
                } => unreachable!(),
            }
        }
        assert_eq!((rsp, cpu, initial, unknown), (13, 4, 15, 0));

        assert!(matches!(
            report.fragments[0].exports[0].origin,
            DmemByteOrigin::MeasuredWrite {
                event_ordinal: 2,
                source: DmemWriterSource::RspSink { context: 100 }
            }
        ));
        assert!(!report.writer_sensor_coverage_certified);
        assert!(!report.executable_consumption_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn unknown_same_value_source_stays_unknown() {
        let initial = snapshot();
        let effect = initial[0..8].to_vec();
        let bytes = encode(vec![
            Event::DmemSnapshot {
                ordinal: 1,
                bytes: initial,
            },
            Event::UnknownDmemWrite {
                ordinal: 2,
                start: 0,
                size: 1,
            },
            Event::DmaBegin {
                ordinal: 3,
                dmem_start: 0,
                rdram_start: PhysicalAddr(0x3000),
                row_bytes: 8,
                rows: 1,
                skip: 0,
            },
            Event::DmaFragment {
                ordinal: 4,
                context: 3,
                current_dmem: 0,
                current_rdram: PhysicalAddr(0x3000),
                bytes: effect,
            },
            Event::DmaEnd {
                ordinal: 5,
                context: 3,
            },
        ]);
        let digest = sha256(&bytes);
        let report = inspect_rsp_dmem_dma_egress(&bytes, &digest).unwrap();
        assert!(matches!(
            report.fragments[0].exports[0].origin,
            DmemByteOrigin::Unknown { event_ordinal: 2 }
        ));
        assert!(matches!(
            report.fragments[0].exports[1].origin,
            DmemByteOrigin::InitialSnapshot {
                snapshot_ordinal: 1
            }
        ));
    }

    #[test]
    fn rejects_descriptor_payload_ordering_and_interleaving_forgery() {
        let initial = snapshot();
        let effect = initial[0..8].to_vec();
        let base = vec![
            Event::DmemSnapshot {
                ordinal: 1,
                bytes: initial.clone(),
            },
            Event::DmaBegin {
                ordinal: 2,
                dmem_start: 0,
                rdram_start: PhysicalAddr(0x4000),
                row_bytes: 8,
                rows: 1,
                skip: 0,
            },
            Event::DmaFragment {
                ordinal: 3,
                context: 2,
                current_dmem: 0,
                current_rdram: PhysicalAddr(0x4000),
                bytes: effect.clone(),
            },
            Event::DmaEnd {
                ordinal: 4,
                context: 2,
            },
        ];

        let mut wrong_descriptor = base.clone();
        if let Event::DmaFragment { current_dmem, .. } = &mut wrong_descriptor[2] {
            *current_dmem = 8;
        }
        let encoded = encode(wrong_descriptor);
        let digest = sha256(&encoded);
        assert!(inspect_rsp_dmem_dma_egress(&encoded, &digest).is_err());

        let mut wrong_payload = base.clone();
        if let Event::DmaFragment { bytes, .. } = &mut wrong_payload[2] {
            bytes[0] ^= 0xff;
        }
        let encoded = encode(wrong_payload);
        let digest = sha256(&encoded);
        assert!(inspect_rsp_dmem_dma_egress(&encoded, &digest).is_err());

        let mut reordered = base.clone();
        if let Event::DmaFragment { ordinal, .. } = &mut reordered[2] {
            *ordinal = 4;
        }
        let encoded = encode(reordered);
        let digest = sha256(&encoded);
        assert!(inspect_rsp_dmem_dma_egress(&encoded, &digest).is_err());

        let interleaved = encode(vec![
            Event::DmemSnapshot {
                ordinal: 1,
                bytes: initial,
            },
            Event::DmaBegin {
                ordinal: 2,
                dmem_start: 0,
                rdram_start: PhysicalAddr(0x4000),
                row_bytes: 8,
                rows: 1,
                skip: 0,
            },
            Event::DmemWrite {
                ordinal: 3,
                start: 0,
                bytes: vec![0],
                source: source("rsp", 1),
            },
        ]);
        let digest = sha256(&interleaved);
        assert!(inspect_rsp_dmem_dma_egress(&interleaved, &digest).is_err());
    }

    #[test]
    fn rejects_truncation_boolean_ordinal_and_forged_report() {
        let bytes = research_shape_history();
        let mut history: History = serde_json::from_slice(&bytes).unwrap();
        history.events.pop();
        let truncated = serde_json::to_vec(&history).unwrap();
        let digest = sha256(&truncated);
        assert!(inspect_rsp_dmem_dma_egress(&truncated, &digest).is_err());

        let boolean_ordinal = format!(
            "{{\"format\":\"{FORMAT}\",\"events\":[{{\"record\":\"dmem_snapshot\",\"ordinal\":false,\"bytes\":[]}}]}}"
        );
        let digest = sha256(boolean_ordinal.as_bytes());
        assert!(inspect_rsp_dmem_dma_egress(boolean_ordinal.as_bytes(), &digest).is_err());

        let digest = sha256(&bytes);
        let mut report = inspect_rsp_dmem_dma_egress(&bytes, &digest).unwrap();
        report.fragments[0].exports[0].origin = DmemByteOrigin::Unknown { event_ordinal: 999 };
        assert!(verify_rsp_dmem_dma_egress_report(&report, &bytes, &digest).is_err());
    }
}
