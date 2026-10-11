//! Bounded compiler-time replay of captured RSP IMEM reverse-SP-DMA lineage.
//!
//! This module authenticates only the supplied finite history. It deliberately
//! keeps captured IMEM writer identity separate from a complete mutation census,
//! SP-DMA request lifecycle, executable lifetime, and hardware-wide semantics.
use crate::{program::PhysicalAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-rsp-imem-dma-egress-v0";
const IMEM_BYTES: usize = 4096;
const MAX_EVENTS: usize = 1_000_000;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    ImemWordSink {
        ordinal: u64,
        region: u32,
        offset: u32,
        bytes: u32,
        value: u32,
        cpu: bool,
    },
    DmaRdramWrite {
        ordinal: u64,
        region: u32,
        dma_region: u32,
        source: u32,
        dma_pbus: u32,
        dram: PhysicalAddr,
        dma_dram: PhysicalAddr,
        bytes: u32,
        value: u64,
        dma_count: u32,
        dma_skip: u32,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::ImemWordSink { ordinal, .. } | Self::DmaRdramWrite { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaEgressByte {
    pub source_offset: u32,
    pub destination: PhysicalAddr,
    pub sink_value: u8,
    pub writer_ordinal: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaEgressReceipt {
    pub write_ordinal: u64,
    pub source_region: u32,
    pub source_offset: u32,
    pub destination: PhysicalAddr,
    pub bytes: u32,
    pub value: u64,
    pub descriptor_count: u32,
    pub descriptor_skip: u32,
    pub source_bytes: [SpDmaEgressByte; 8],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaEgressReport {
    pub format: String,
    pub scope: String,
    pub source_sha256: String,
    pub events: usize,
    pub imem_word_sinks: usize,
    pub dma_rdram_writes: usize,
    pub fully_attributed_bytes: usize,
    pub unknown_source_bytes: usize,
    pub receipts: Vec<SpDmaEgressReceipt>,
    pub dma_request_lifecycle_certified: bool,
    pub imem_mutation_census_certified: bool,
    pub executable_lifetime_certified: bool,
    pub hardware_semantics_certified: bool,
    pub native_complete: bool,
}

#[derive(Clone, Copy, Default)]
struct Cell {
    value: Option<u8>,
    writer_ordinal: Option<u64>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Replay a bounded captured history whose SHA-256 was authenticated separately.
///
/// Initial IMEM contents are deliberately UNKNOWN. A completed full-Word IMEM
/// sink establishes four captured byte writers. A reverse-DMA sink may retain
/// its descriptor-selected IMEM location even when some source bytes remain
/// unknown, but payload equality never invents a missing writer generation.
pub fn inspect_sp_dma_egress_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<SpDmaEgressReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP IMEM DMA egress source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported RSP IMEM DMA egress format",
    )?;
    require(
        !history.events.is_empty() && history.events.len() <= MAX_EVENTS,
        "invalid RSP IMEM DMA egress event count",
    )?;

    let mut imem = [Cell::default(); IMEM_BYTES];
    let mut imem_word_sinks = 0usize;
    let mut dma_rdram_writes = 0usize;
    let mut fully_attributed_bytes = 0usize;
    let mut unknown_source_bytes = 0usize;
    let mut receipts = Vec::new();

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous RSP IMEM DMA egress chronology",
        )?;
        match event {
            Event::ImemWordSink {
                ordinal,
                region,
                offset,
                bytes,
                value,
                cpu,
            } => {
                require(
                    *cpu && *region == 1
                        && *bytes == 4
                        && *offset <= 0xffc
                        && offset.is_multiple_of(4),
                    "invalid captured CPU-visible IMEM Word sink",
                )?;
                for (lane, byte) in value.to_be_bytes().into_iter().enumerate() {
                    imem[*offset as usize + lane] = Cell {
                        value: Some(byte),
                        writer_ordinal: Some(*ordinal),
                    };
                }
                imem_word_sinks += 1;
            }
            Event::DmaRdramWrite {
                ordinal,
                region,
                dma_region,
                source,
                dma_pbus,
                dram,
                dma_dram,
                bytes,
                value,
                dma_count,
                dma_skip,
            } => {
                require(
                    *region == 1
                        && *dma_region == 1
                        && *bytes == 8
                        && *dma_pbus < 0x1000
                        && *source == (*dma_pbus & 0xff8)
                        && source.is_multiple_of(8)
                        && *source <= 0xff8
                        && *dram == *dma_dram
                        && dram.0.is_multiple_of(8)
                        && dram.0 <= 0x007f_fff8,
                    "invalid descriptor-bound IMEM reverse-DMA sink",
                )?;
                let sink = value.to_be_bytes();
                for lane in 0..8 {
                    if let Some(source_value) = imem[*source as usize + lane].value {
                        require(
                            source_value == sink[lane],
                            "captured IMEM writer payload differs from reverse-DMA sink",
                        )?;
                    }
                }
                let source_bytes = std::array::from_fn(|lane| {
                    let cell = imem[*source as usize + lane];
                    SpDmaEgressByte {
                        source_offset: *source + lane as u32,
                        destination: PhysicalAddr(dram.0 + lane as u32),
                        sink_value: sink[lane],
                        writer_ordinal: cell.writer_ordinal,
                    }
                });
                let attributed = source_bytes
                    .iter()
                    .filter(|byte| byte.writer_ordinal.is_some())
                    .count();
                fully_attributed_bytes += attributed;
                unknown_source_bytes += 8 - attributed;
                receipts.push(SpDmaEgressReceipt {
                    write_ordinal: *ordinal,
                    source_region: 1,
                    source_offset: *source,
                    destination: *dram,
                    bytes: 8,
                    value: *value,
                    descriptor_count: *dma_count,
                    descriptor_skip: *dma_skip,
                    source_bytes,
                });
                dma_rdram_writes += 1;
            }
        }
    }

    Ok(SpDmaEgressReport {
        format: history.format,
        scope: "finite_descriptor_bound_cpu_imem_reverse_sp_dma".into(),
        source_sha256: digest,
        events: history.events.len(),
        imem_word_sinks,
        dma_rdram_writes,
        fully_attributed_bytes,
        unknown_source_bytes,
        receipts,
        dma_request_lifecycle_certified: false,
        imem_mutation_census_certified: false,
        executable_lifetime_certified: false,
        hardware_semantics_certified: false,
        native_complete: false,
    })
}

pub fn verify_sp_dma_egress_report(
    report: &SpDmaEgressReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_sp_dma_egress_history(source, expected_sha256)?,
        "RSP IMEM DMA egress report differs from complete source replay",
    )
}
