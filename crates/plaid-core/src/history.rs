//! Inspect a bounded reference access chronology against both complete sources.
//! This creates no ProgramMap images, generations, lifetime or closure proof.
use crate::{fetch, program::*, rom::CanonicalRom};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{BufRead, Seek, SeekFrom},
};

pub const FORMAT: &str = "plaid-ares-access-history-v0";
pub const POLICY: &str = "identity_ram_successful_access_and_fetch_boundaries";
pub const LIFECYCLE_POLICY: &str = "single_run_no_host_restore";
pub const MAX_BUDGET: u64 = 1_000_000;
pub const MAX_RECORDS: u64 = 100_000_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AccessHistoryReport {
    pub format: String,
    pub scope: String,
    pub rom: RomIdentity,
    pub firmware_sha256: String,
    pub fetch_sha256: String,
    pub history_sha256: String,
    pub instruction_call_budget: u64,
    pub records: u64,
    pub fetches: u64,
    #[serde(with = "crate::program::unique_map")]
    pub event_counts: BTreeMap<String, u64>,
    pub scalar_fetch_witnesses: u64,
    pub outside_uncached_cpu_reads: u64,
    pub matched_context_ram_fills: u64,
    pub unknown_context_fills: u64,
}

#[derive(Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Record {
    Header {
        format: String,
        revision: String,
        rom_sha256: String,
        budget: u64,
        mapped_cartridge_size: u32,
        firmware_sha256: String,
        policy: String,
        lifecycle_policy: String,
        paired_fetch_format: String,
    },
    Scalar {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write: bool,
        address: PhysicalAddr,
        aligned_address: PhysicalAddr,
        bytes: u32,
        device: u32,
        value: u64,
    },
    Burst {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write: bool,
        address: PhysicalAddr,
        bytes: u32,
        device: u32,
        words: Vec<u32>,
    },
    Fill {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        slot: u16,
        physical: PhysicalAddr,
        index: u16,
        words: [u32; 8],
    },
    CacheOperation {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        operation: u32,
        vaddr: GuestVirtualAddr,
        physical: PhysicalAddr,
        before_tag: u32,
        after_tag: u32,
        before_words: [u32; 8],
        after_words: [u32; 8],
    },
    FetchBegin {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        vaddr: GuestVirtualAddr,
        translated: PhysicalAddr,
        bus: PhysicalAddr,
        cached: bool,
        value: u32,
    },
    FetchEnd {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        vaddr: GuestVirtualAddr,
        translated: PhysicalAddr,
        bus: PhysicalAddr,
        cached: bool,
        value: u32,
    },
    Fetch {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        fetch_context: u64,
        fetch_seq: u64,
        word: u32,
        physical: PhysicalAddr,
        cached: bool,
    },
    End {
        record_count: u64,
        fetch_count: u64,
        reason: String,
    },
}

impl Record {
    fn identity(&self) -> Option<(u64, u64, GuestVirtualAddr, &'static str)> {
        let (a, b, c, k) = match self {
            Self::Scalar {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "scalar"),
            Self::Burst {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "burst"),
            Self::Fill {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "fill"),
            Self::CacheOperation {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "cache_operation"),
            Self::FetchBegin {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "fetch_begin"),
            Self::FetchEnd {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "fetch_end"),
            Self::Fetch {
                ordinal,
                context,
                pc,
                ..
            } => (ordinal, context, pc, "fetch"),
            Self::Header { .. } | Self::End { .. } => return None,
        };
        Some((*a, *b, *c, k))
    }
}

#[derive(Clone, Copy)]
struct Boundary {
    context: u64,
    pc: GuestVirtualAddr,
    vaddr: GuestVirtualAddr,
    translated: PhysicalAddr,
    bus: PhysicalAddr,
    cached: bool,
}
#[derive(Clone, Copy)]
struct Burst {
    ordinal: u64,
    address: PhysicalAddr,
    write: bool,
    bytes: u32,
    device: u32,
    words: [u32; 8],
}
#[derive(Clone, Copy)]
struct Fill {
    slot: u16,
    physical: PhysicalAddr,
    index: u16,
    words: [u32; 8],
}
struct Active {
    boundary: Boundary,
    eligible: u64,
    read: Option<(PhysicalAddr, u64)>,
    last_burst: Option<Burst>,
    fills: u64,
    matched_fill: Option<Fill>,
}
struct Pending {
    active: Active,
    word: u32,
}

fn history_record<R: BufRead>(
    reader: &mut R,
    bytes: &mut Vec<u8>,
    hash: &mut Sha256,
) -> Result<Record, String> {
    if !fetch::line(reader, bytes)? || !bytes.ends_with(b"\n") {
        return Err("missing, oversized or truncated history record".into());
    }
    hash.update(&*bytes);
    serde_json::from_slice(bytes).map_err(|e| e.to_string())
}
fn fetch_record<R: BufRead>(
    reader: &mut R,
    bytes: &mut Vec<u8>,
    hash: &mut Sha256,
) -> Result<fetch::Record, String> {
    if !fetch::line(reader, bytes)? {
        return Err("missing paired fetch record".into());
    }
    hash.update(&*bytes);
    serde_json::from_slice(bytes).map_err(|e| e.to_string())
}
fn require(condition: bool, message: &str) -> Result<(), String> {
    if condition {
        Ok(())
    } else {
        Err(message.into())
    }
}

/// Validate the existing v5 source with supplied inputs, then replay each fetch
/// against the sidecar. A second source digest prevents changes between passes.
/// Counts describe finite observed accesses, never complete mutation coverage.
pub fn inspect_boot_history<H: BufRead, F: BufRead + Seek>(
    mut history: H,
    mut fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<AccessHistoryReport, String> {
    require(
        fetched.stream_position().map_err(|e| e.to_string())? == 0,
        "paired fetch reader must begin at zero",
    )?;
    let map = fetch::import_boot_fetch(&mut fetched, rom, firmware)?;
    let capture = map.fetch_captures.first_key_value().unwrap().1.clone();
    drop(map);
    require(
        capture.cache_policy.as_deref() == Some(fetch::CACHE_POLICY)
            && capture.instruction_call_budget <= MAX_BUDGET,
        "history requires bounded v5 boot capture",
    )?;
    fetched
        .seek(SeekFrom::Start(0))
        .map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    let mut paired_bytes = Vec::new();
    let mut hash = Sha256::new();
    let mut paired_hash = Sha256::new();
    require(
        matches!(
            fetch_record(&mut fetched, &mut paired_bytes, &mut paired_hash)?,
            fetch::Record::Header { .. }
        ),
        "missing paired header",
    )?;
    let Record::Header {
        format,
        revision,
        rom_sha256,
        budget,
        mapped_cartridge_size,
        firmware_sha256,
        policy,
        lifecycle_policy,
        paired_fetch_format,
    } = history_record(&mut history, &mut bytes, &mut hash)?
    else {
        return Err("history must begin with header".into());
    };
    let boot = capture.boot_inputs.as_ref().unwrap();
    require(
        format == FORMAT
            && revision == fetch::REVISION
            && rom_sha256 == rom.identity.sha256
            && budget == capture.instruction_call_budget
            && Some(mapped_cartridge_size) == capture.mapped_cartridge_size
            && firmware_sha256 == boot.firmware_sha256
            && policy == POLICY
            && lifecycle_policy == LIFECYCLE_POLICY
            && paired_fetch_format == fetch::CACHE_FORMAT,
        "history header does not match supported paired inputs/policy",
    )?;
    let mut report = AccessHistoryReport {
        format: "plaid-access-history-report-v0".into(),
        scope: "finite_reference_access_inspection".into(),
        rom: rom.identity.clone(),
        firmware_sha256,
        fetch_sha256: capture.trace_sha256.clone(),
        history_sha256: String::new(),
        instruction_call_budget: budget,
        records: 0,
        fetches: 0,
        event_counts: BTreeMap::new(),
        scalar_fetch_witnesses: 0,
        outside_uncached_cpu_reads: 0,
        matched_context_ram_fills: 0,
        unknown_context_fills: 0,
    };
    let mut active: Option<Active> = None;
    let mut pending: Option<Pending> = None;
    loop {
        let row = history_record(&mut history, &mut bytes, &mut hash)?;
        if let Record::End {
            record_count,
            fetch_count,
            reason,
        } = row
        {
            require(
                active.is_none()
                    && pending.is_none()
                    && record_count == report.records
                    && fetch_count == report.fetches
                    && fetch_count == capture.fetch_count
                    && reason == "instruction_call_budget",
                "incomplete history or invalid footer",
            )?;
            require(
                !fetch::line(&mut history, &mut bytes)?,
                "data after history footer",
            )?;
            break;
        }
        let Some((ordinal, context, pc, kind)) = row.identity() else {
            return Err("repeated history header".into());
        };
        report.records += 1;
        require(
            report.records <= MAX_RECORDS && ordinal == report.records,
            "history ordinal/order/limit mismatch",
        )?;
        require(
            pending.is_none() || kind == "fetch",
            "event between fetch completion and prologue",
        )?;
        *report.event_counts.entry(kind.into()).or_default() += 1;
        if kind != "fetch_begin" {
            require(
                context == active.as_ref().map_or(0, |a| a.boundary.context),
                "event does not belong to active fetch context",
            )?;
            if let Some(a) = &active {
                require(pc == a.boundary.pc, "context PC changed")?;
            }
        }
        match row {
            Record::FetchBegin {
                vaddr,
                translated,
                bus,
                cached,
                value,
                ..
            } => {
                require(
                    active.is_none()
                        && context == ordinal
                        && value == 0
                        && bus.0.is_multiple_of(4)
                        && pc == vaddr,
                    "nested/malformed successful fetch boundary",
                )?;
                active = Some(Active {
                    boundary: Boundary {
                        context,
                        pc,
                        vaddr,
                        translated,
                        bus,
                        cached,
                    },
                    eligible: 0,
                    read: None,
                    last_burst: None,
                    fills: 0,
                    matched_fill: None,
                });
            }
            Record::Scalar {
                write,
                address,
                aligned_address,
                bytes,
                device,
                value,
                ..
            } => {
                require(
                    matches!(bytes, 1 | 2 | 4 | 8) && device < 14 && address.0 < boot.rdram_size,
                    "invalid successful RAM scalar",
                )?;
                require(
                    aligned_address.0 == address.0 & !(bytes - 1),
                    "scalar backing alignment mismatch",
                )?;
                if !write && bytes < 8 {
                    require(value >> (bytes * 8) == 0, "scalar read exceeds its width")?;
                }
                if let Some(a) = &mut active {
                    if !write && bytes == 4 && device == 3 {
                        a.eligible += 1;
                        a.read = Some((address, value));
                    }
                } else if !write && device == 3 {
                    report.outside_uncached_cpu_reads += 1;
                }
            }
            Record::Burst {
                write,
                address,
                bytes,
                device,
                words,
                ..
            } => {
                require(
                    matches!(bytes, 16 | 32)
                        && device < 14
                        && address.0 < boot.rdram_size
                        && address.0.is_multiple_of(bytes)
                        && words.len() == (bytes / 4) as usize,
                    "invalid successful RAM burst",
                )?;
                if let Some(a) = &mut active {
                    let mut payload = [0; 8];
                    payload[..words.len()].copy_from_slice(&words);
                    a.last_burst = Some(Burst {
                        ordinal,
                        address,
                        write,
                        bytes,
                        device,
                        words: payload,
                    });
                }
            }
            Record::Fill {
                slot,
                physical,
                index,
                words,
                ..
            } => {
                require(
                    slot < 512
                        && index == ((slot << 5) & 0xfe0)
                        && u32::from(index) == physical.0 & 0xfe0,
                    "invalid fill slot/index",
                )?;
                if let Some(a) = &mut active {
                    a.fills += 1;
                    if a.last_burst.is_some_and(|b| {
                        b.ordinal + 1 == ordinal
                            && !b.write
                            && b.bytes == 32
                            && b.device == 1
                            && b.address.0 == (physical.0 & !0xfff) | u32::from(index)
                            && b.words == words
                    }) {
                        a.matched_fill = Some(Fill {
                            slot,
                            physical,
                            index,
                            words,
                        });
                    }
                }
            }
            Record::CacheOperation {
                operation,
                vaddr,
                physical,
                before_tag,
                after_tag,
                before_words,
                after_words,
                ..
            } => {
                require(
                    active.is_none() && matches!(operation, 0 | 8 | 16 | 20 | 24),
                    "unsupported/nested CACHE completion",
                )?;
                // Preserve/check every payload through the complete source digest;
                // transitions themselves issue no lifetime or mutation certificate.
                let _ = (
                    vaddr,
                    physical,
                    before_tag,
                    after_tag,
                    before_words,
                    after_words,
                );
            }
            Record::FetchEnd {
                vaddr,
                translated,
                bus,
                cached,
                value,
                ..
            } => {
                let a = active.take().ok_or("fetch end without begin")?;
                let b = a.boundary;
                require(
                    (context, pc, vaddr, translated, bus, cached)
                        == (b.context, b.pc, b.vaddr, b.translated, b.bus, b.cached),
                    "fetch boundary fields disagree",
                )?;
                if !cached && a.eligible == 1 && a.read == Some((bus, u64::from(value))) {
                    report.scalar_fetch_witnesses += 1;
                }
                pending = Some(Pending {
                    active: a,
                    word: value,
                });
            }
            Record::Fetch {
                fetch_context,
                fetch_seq,
                word,
                physical,
                cached,
                ..
            } => {
                let p = pending.take().ok_or("prologue without completed fetch")?;
                let b = p.active.boundary;
                require(
                    active.is_none()
                        && (fetch_context, pc, physical, cached, word, fetch_seq)
                            == (b.context, b.pc, b.bus, b.cached, p.word, report.fetches),
                    "prologue does not match completed access",
                )?;
                let fetch::Record::Fetch {
                    seq,
                    pc: paired_pc,
                    word: paired_word,
                    physical: paired_pa,
                    cached: paired_cached,
                    cache_line,
                    ..
                } = fetch_record(&mut fetched, &mut paired_bytes, &mut paired_hash)?
                else {
                    return Err("missing paired fetch".into());
                };
                require(
                    (seq, paired_pc, paired_word, paired_pa, paired_cached)
                        == (fetch_seq, pc, word, Some(physical), Some(cached)),
                    "history word/access disagrees with complete fetch source",
                )?;
                if cached
                    && p.active.fills == 1
                    && let (Some(f), Some(line)) = (p.active.matched_fill, cache_line)
                    && f.physical == physical
                    && u64::from(f.slot) == (pc.0 >> 5) & 0x1ff
                    && f.slot == line.slot
                    && f.index == line.index
                    && f.words == line.words
                {
                    report.matched_context_ram_fills += 1;
                }
                report.fetches += 1;
            }
            Record::Header { .. } | Record::End { .. } => unreachable!(),
        }
    }
    require(
        matches!(fetch_record(&mut fetched,&mut paired_bytes,&mut paired_hash)?,fetch::Record::End { fetch_count,reason }
        if fetch_count == report.fetches && reason == "instruction_call_budget"),
        "paired footer mismatch",
    )?;
    require(
        !fetch::line(&mut fetched, &mut paired_bytes)?,
        "extra paired fetch data",
    )?;
    require(
        format!("{:x}", paired_hash.finalize()) == capture.trace_sha256,
        "paired fetch source changed during inspection",
    )?;
    report.history_sha256 = format!("{:x}", hash.finalize());
    report.unknown_context_fills =
        report.event_counts.get("fill").copied().unwrap_or(0) - report.matched_context_ram_fills;
    Ok(report)
}

pub fn verify_boot_history_report<H: BufRead, F: BufRead + Seek>(
    report: &AccessHistoryReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_boot_history(history, fetched, rom, firmware)?,
        "history report does not match its complete sources/inputs",
    )
}
