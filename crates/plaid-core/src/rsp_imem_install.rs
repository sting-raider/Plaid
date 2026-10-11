//! Bounded compiler-time replay of observed RSP IMEM installation effects.
//!
//! A promoted SP-DMA request groups only its measured completed DMA sinks. It is
//! not an atomic executable residency generation: later CPU/DMA writers supersede
//! only the bytes they actually touch, including same-value writes.
use crate::{history, program::PhysicalAddr, rom::sha256};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-rsp-imem-install-history-v0";
const IMEM_BYTES: usize = 4096;
const RDRAM_LIMIT: u32 = 0x0100_0000;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Promote {
        ordinal: u64,
        request: u64,
        pbus: u16,
        dram: PhysicalAddr,
        length: u32,
        count: u32,
        skip: u32,
    },
    DmaSink {
        ordinal: u64,
        request: u64,
        pbus: u16,
        dram: PhysicalAddr,
        value: u64,
    },
    CpuSink {
        ordinal: u64,
        pbus: u16,
        value: u32,
    },
    Complete {
        ordinal: u64,
        request: u64,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Promote { ordinal, .. }
            | Self::DmaSink { ordinal, .. }
            | Self::CpuSink { ordinal, .. }
            | Self::Complete { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", tag = "writer", deny_unknown_fields)]
pub enum RspImemWriterKind {
    Dma { request: u64 },
    Cpu,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspImemWriterEffect {
    pub generation: u64,
    pub ordinal: u64,
    pub kind: RspImemWriterKind,
    pub offset: u16,
    pub bytes: u16,
    pub dram: Option<PhysicalAddr>,
    pub value: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspImemRequest {
    pub request: u64,
    pub promote_ordinal: u64,
    pub complete_ordinal: u64,
    pub initial_pbus: u16,
    pub initial_dram: PhysicalAddr,
    pub length: u32,
    pub count: u32,
    pub skip: u32,
    pub effect_generations: Vec<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspImemOwnerSpan {
    pub offset: u16,
    pub bytes: u16,
    pub generation: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspImemInstallReport {
    pub format: String,
    pub source_sha256: String,
    pub events: u64,
    pub requests: Vec<RspImemRequest>,
    pub writer_effects: Vec<RspImemWriterEffect>,
    pub current_owner_spans: Vec<RspImemOwnerSpan>,
    pub source_backing_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub rsp_closure_certified: bool,
    pub native_complete: bool,
}

struct ActiveRequest {
    request: u64,
    promote_ordinal: u64,
    initial_pbus: u16,
    initial_dram: PhysicalAddr,
    length: u32,
    count: u32,
    skip: u32,
    effect_generations: Vec<u64>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn valid_dma_endpoint(pbus: u16, dram: PhysicalAddr) -> bool {
    pbus < IMEM_BYTES as u16
        && pbus.is_multiple_of(8)
        && dram.0 < RDRAM_LIMIT
        && dram.0.is_multiple_of(8)
}

fn apply_owner(owners: &mut [Option<u64>; IMEM_BYTES], offset: u16, bytes: u16, generation: u64) {
    for lane in 0..bytes {
        let byte = usize::from(offset.wrapping_add(lane) & 0x0fff);
        owners[byte] = Some(generation);
    }
}

fn compact_owners(owners: &[Option<u64>; IMEM_BYTES]) -> Vec<RspImemOwnerSpan> {
    let mut spans = Vec::new();
    let mut offset = 0usize;
    while offset < owners.len() {
        let Some(generation) = owners[offset] else {
            offset += 1;
            continue;
        };
        let start = offset;
        offset += 1;
        while offset < owners.len() && owners[offset] == Some(generation) {
            offset += 1;
        }
        spans.push(RspImemOwnerSpan {
            offset: start as u16,
            bytes: (offset - start) as u16,
            generation,
        });
    }
    spans
}

/// Replay one separately authenticated complete observation source.
///
/// Success proves only internal chronology and request/effect ownership for the
/// supplied source. It does not prove capture completeness, RDRAM byte ancestry,
/// hardware-wide FIFO policy, reset/save-state continuity, or executable closure.
pub fn inspect_rsp_imem_install_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspImemInstallReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP IMEM installation source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(history.format == FORMAT, "unsupported RSP IMEM installation format")?;
    require(
        history.events.len() as u64 <= history::MAX_RECORDS,
        "RSP IMEM installation history exceeds record bound",
    )?;

    let mut active: Option<ActiveRequest> = None;
    let mut last_promoted = 0u64;
    let mut generation = 0u64;
    let mut owners = [None; IMEM_BYTES];
    let mut requests = Vec::new();
    let mut effects = Vec::new();

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "non-contiguous RSP IMEM installation ordinal",
        )?;
        match event {
            Event::Promote {
                ordinal,
                request,
                pbus,
                dram,
                length,
                count,
                skip,
            } => {
                require(active.is_none(), "RSP IMEM request promoted while another is active")?;
                require(
                    *request > last_promoted,
                    "RSP IMEM request generation is not strictly monotonic",
                )?;
                require(
                    valid_dma_endpoint(*pbus, *dram),
                    "invalid promoted RSP IMEM DMA endpoint",
                )?;
                last_promoted = *request;
                active = Some(ActiveRequest {
                    request: *request,
                    promote_ordinal: *ordinal,
                    initial_pbus: *pbus,
                    initial_dram: *dram,
                    length: *length,
                    count: *count,
                    skip: *skip,
                    effect_generations: Vec::new(),
                });
            }
            Event::DmaSink {
                ordinal,
                request,
                pbus,
                dram,
                value,
            } => {
                require(
                    active.as_ref().map(|r| r.request) == Some(*request),
                    "RSP IMEM DMA sink is not owned by the active request",
                )?;
                require(
                    valid_dma_endpoint(*pbus, *dram),
                    "invalid completed RSP IMEM DMA sink",
                )?;
                generation = generation
                    .checked_add(1)
                    .ok_or("RSP IMEM writer generation overflow")?;
                apply_owner(&mut owners, *pbus, 8, generation);
                effects.push(RspImemWriterEffect {
                    generation,
                    ordinal: *ordinal,
                    kind: RspImemWriterKind::Dma { request: *request },
                    offset: *pbus,
                    bytes: 8,
                    dram: Some(*dram),
                    value: *value,
                });
                active
                    .as_mut()
                    .expect("validated active request")
                    .effect_generations
                    .push(generation);
            }
            Event::CpuSink {
                ordinal,
                pbus,
                value,
            } => {
                require(
                    *pbus < IMEM_BYTES as u16 && pbus.is_multiple_of(4),
                    "invalid completed CPU RSP IMEM sink",
                )?;
                generation = generation
                    .checked_add(1)
                    .ok_or("RSP IMEM writer generation overflow")?;
                apply_owner(&mut owners, *pbus, 4, generation);
                effects.push(RspImemWriterEffect {
                    generation,
                    ordinal: *ordinal,
                    kind: RspImemWriterKind::Cpu,
                    offset: *pbus,
                    bytes: 4,
                    dram: None,
                    value: u64::from(*value),
                });
            }
            Event::Complete { ordinal, request } => {
                let request_state = active.take().ok_or("RSP IMEM completion without active request")?;
                require(
                    request_state.request == *request,
                    "RSP IMEM completion does not match active request",
                )?;
                require(
                    !request_state.effect_generations.is_empty(),
                    "RSP IMEM request completed without a measured DMA sink",
                )?;
                requests.push(RspImemRequest {
                    request: request_state.request,
                    promote_ordinal: request_state.promote_ordinal,
                    complete_ordinal: *ordinal,
                    initial_pbus: request_state.initial_pbus,
                    initial_dram: request_state.initial_dram,
                    length: request_state.length,
                    count: request_state.count,
                    skip: request_state.skip,
                    effect_generations: request_state.effect_generations,
                });
            }
        }
    }
    require(active.is_none(), "RSP IMEM history ended with an active request")?;

    Ok(RspImemInstallReport {
        format: history.format,
        source_sha256: digest,
        events: history.events.len() as u64,
        requests,
        writer_effects: effects,
        current_owner_spans: compact_owners(&owners),
        source_backing_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        rsp_closure_certified: false,
        native_complete: false,
    })
}

pub fn verify_rsp_imem_install_report(
    report: &RspImemInstallReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_rsp_imem_install_history(source, expected_sha256)?,
        "RSP IMEM installation report differs from complete source replay",
    )
}
