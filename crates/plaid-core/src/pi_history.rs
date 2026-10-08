//! Finite buffered PI source effects, with separate observed status contexts.
//! No queue completion, mutation census, executable image or lifetime certificate.
use crate::{fetch, history, program::*, rom::CanonicalRom};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::{BTreeMap, BTreeSet},
    io::{self, BufRead, Read, Seek},
};

pub const FORMAT: &str = "plaid-ares-access-history-v1";
pub const POLICY: &str = "identity_ram_fetch_and_buffered_pi_contexts";
pub const MAX_TRANSFERS: u64 = 1_000_000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiHistoryReport {
    pub format: String,
    pub scope: String,
    pub history_sha256: String,
    pub projection: history::AccessHistoryReport,
    pub records: u64,
    #[serde(with = "crate::program::unique_map")]
    pub event_counts: BTreeMap<String, u64>,
    pub source_half_reads: u64,
    pub byte_attempts: u64,
    pub successful_pi_writes: u64,
    pub canonical_rom_byte_origins: u64,
    pub unknown_pi_byte_origins: u64,
    pub failed_destination_witnesses: u64,
    pub returned_transfers: u64,
    pub completion_status_transitions: u64,
    pub observer_write_contexts_at_status: Vec<u64>,
    pub writes_without_observer_status: Vec<u64>,
    pub transfer_completion_certified: bool,
    pub unassociated_completions: u64,
    pub pi_origin_effects_sha256: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub(crate) enum Wire {
    Pi(PiRecord),
    Scalar(PiScalar),
    Base(history::Record),
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum PiRecord {
    PiDma {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        event: u32,
        transfer: u64,
        block: u32,
        dram: PhysicalAddr,
        pbus: PhysicalAddr,
        length: u32,
        lane: u32,
        value: u32,
    },
    PiRomHalf {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        transfer: u64,
        block: u32,
        offset: u32,
        value: u16,
    },
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct PiScalar {
    record: String,
    ordinal: u64,
    context: u64,
    pc: GuestVirtualAddr,
    write: bool,
    address: PhysicalAddr,
    aligned_address: PhysicalAddr,
    bytes: u32,
    device: u32,
    value: u64,
    pi: PiContext,
}
#[derive(Debug, Deserialize, Serialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
struct PiContext {
    transfer: u64,
    block: u32,
    lane: u32,
}

impl Wire {
    pub(crate) fn identity(&self) -> Option<(u64, u64, GuestVirtualAddr, &'static str)> {
        let (ordinal, context, pc, kind) = match self {
            Self::Base(record) => return record.identity(),
            Self::Scalar(s) => (s.ordinal, s.context, s.pc, "scalar"),
            Self::Pi(PiRecord::PiDma {
                ordinal,
                context,
                pc,
                ..
            }) => (*ordinal, *context, *pc, "pi_dma"),
            Self::Pi(PiRecord::PiRomHalf {
                ordinal,
                context,
                pc,
                ..
            }) => (*ordinal, *context, *pc, "pi_rom_half"),
        };
        Some((ordinal, context, pc, kind))
    }

    pub(crate) fn renumber(&mut self, next: u64, scope: u64) {
        let (ordinal, context) = match self {
            Self::Pi(PiRecord::PiDma {
                ordinal, context, ..
            })
            | Self::Pi(PiRecord::PiRomHalf {
                ordinal, context, ..
            }) => (ordinal, context),
            Self::Scalar(s) => (&mut s.ordinal, &mut s.context),
            Self::Base(history::Record::Scalar {
                ordinal, context, ..
            })
            | Self::Base(history::Record::Burst {
                ordinal, context, ..
            })
            | Self::Base(history::Record::Fill {
                ordinal, context, ..
            })
            | Self::Base(history::Record::CacheOperation {
                ordinal, context, ..
            })
            | Self::Base(history::Record::FetchBegin {
                ordinal, context, ..
            })
            | Self::Base(history::Record::FetchEnd {
                ordinal, context, ..
            })
            | Self::Base(history::Record::Fetch {
                ordinal, context, ..
            }) => (ordinal, context),
            Self::Base(_) => return,
        };
        *ordinal = next;
        *context = scope;
    }
}

#[derive(Clone, Copy)]
struct Origin {
    value: u8,
    offset: Option<u32>,
}
#[derive(Clone, Copy)]
struct Attempt {
    dram: PhysicalAddr,
    pbus: PhysicalAddr,
    length: u32,
    lane: u32,
    value: u32,
    writer: Option<u64>,
}
struct Copy {
    id: u64,
    pc: GuestVirtualAddr,
    block: Option<u32>,
    blocks: u32,
    buffer: [Option<Origin>; 128],
    attempt: Option<Attempt>,
}
#[derive(Clone, Copy)]
struct Half {
    ordinal: u64,
    transfer: u64,
    block: u32,
    offset: u32,
    value: u16,
}

#[derive(Default)]
struct Stats {
    records: u64,
    counts: BTreeMap<String, u64>,
    source_reads: u64,
    attempts: u64,
    writes: u64,
    known: u64,
    failed: u64,
    transfers: u64,
    returned: BTreeSet<u64>,
    statuses: Vec<u64>,
    unassociated: u64,
}
struct Projection<'a, H> {
    input: H,
    source: &'a [u8],
    raw: Vec<u8>,
    output: Vec<u8>,
    position: usize,
    hash: Sha256,
    effects: Sha256,
    stats: Stats,
    header: bool,
    ended: bool,
    old_ordinal: u64,
    active: Option<(u64, GuestVirtualAddr, u64)>,
    pending: Option<(u64, u64)>,
    copy: Option<Copy>,
    half: Option<Half>,
    status_candidate: Option<u64>,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl<'a, H: BufRead> Projection<'a, H> {
    fn new(input: H, source: &'a [u8]) -> Self {
        Self {
            input,
            source,
            raw: Vec::new(),
            output: Vec::new(),
            position: 0,
            hash: Sha256::new(),
            effects: Sha256::new(),
            stats: Stats::default(),
            header: false,
            ended: false,
            old_ordinal: 0,
            active: None,
            pending: None,
            copy: None,
            half: None,
            status_candidate: None,
        }
    }
    fn identity(
        &mut self,
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        kind: &str,
        begin: bool,
    ) -> Result<(), String> {
        require(
            self.stats.records < history::MAX_RECORDS,
            "PI history exceeds record bound",
        )?;
        self.stats.records += 1;
        require(
            ordinal == self.stats.records,
            "PI history ordinal is not contiguous",
        )?;
        require(
            self.pending.is_none() || kind == "fetch",
            "PI history prologue must immediately follow return",
        )?;
        if begin {
            require(
                self.active.is_none() && self.pending.is_none() && context == ordinal,
                "invalid PI history fetch begin",
            )?;
            self.active = Some((ordinal, pc, self.old_ordinal + 1));
        } else {
            require(
                context == self.active.map_or(0, |a| a.0),
                "PI history access context mismatch",
            )?;
            if let Some(a) = self.active {
                require(pc == a.1, "PI history context PC mismatch")?;
            }
        }
        *self.stats.counts.entry(kind.into()).or_default() += 1;
        Ok(())
    }
    fn encode(&mut self, record: &history::Record) -> Result<(), String> {
        self.output = serde_json::to_vec(record).map_err(|e| e.to_string())?;
        self.output.push(b'\n');
        self.position = 0;
        Ok(())
    }
    fn base(&mut self, mut record: history::Record, sensed_scalar: bool) -> Result<(), String> {
        use history::Record as R;
        match &mut record {
            R::Header { format, policy, .. } => {
                require(
                    !self.header && self.stats.records == 0,
                    "repeated PI history header",
                )?;
                require(
                    format == FORMAT && policy == POLICY,
                    "unsupported PI history version/policy",
                )?;
                *format = history::FORMAT.into();
                *policy = history::POLICY.into();
                self.header = true;
            }
            R::End { record_count, .. } => {
                require(
                    self.header
                        && *record_count == self.stats.records
                        && self.copy.is_none()
                        && self.half.is_none()
                        && self.active.is_none()
                        && self.pending.is_none(),
                    "incomplete PI history footer",
                )?;
                *record_count = self.old_ordinal;
                self.ended = true;
            }
            _ => {
                require(self.header, "PI history lacks header")?;
                let (ordinal, context, pc, kind) = record.identity().unwrap();
                if kind == "fetch_begin" {
                    require(
                        self.copy.is_none(),
                        "fetch begins inside synchronous PI copy",
                    )?;
                }
                self.identity(ordinal, context, pc, kind, kind == "fetch_begin")?;
                require(self.half.is_none(), "orphan PI ROM result")?;
                require(
                    self.copy.as_ref().is_none_or(|c| c.attempt.is_none()) || sensed_scalar,
                    "interposed PI byte write record",
                )?;
                if let R::Scalar {
                    write: true,
                    device: 5,
                    ..
                } = record
                {
                    require(sensed_scalar, "PI write lacks transfer/lane context")?;
                }
                self.old_ordinal += 1;
                let new_context = self.active.map_or(0, |a| a.2);
                match &mut record {
                    R::Scalar {
                        ordinal, context, ..
                    }
                    | R::Burst {
                        ordinal, context, ..
                    }
                    | R::Fill {
                        ordinal, context, ..
                    }
                    | R::CacheOperation {
                        ordinal, context, ..
                    }
                    | R::FetchBegin {
                        ordinal, context, ..
                    }
                    | R::FetchEnd {
                        ordinal, context, ..
                    }
                    | R::Fetch {
                        ordinal, context, ..
                    } => {
                        *ordinal = self.old_ordinal;
                        *context = new_context;
                    }
                    _ => unreachable!(),
                }
                if kind == "fetch_end" {
                    let a = self
                        .active
                        .take()
                        .ok_or("PI history return without begin")?;
                    self.pending = Some((a.0, a.2));
                } else if let R::Fetch { fetch_context, .. } = &mut record {
                    let p = self
                        .pending
                        .take()
                        .ok_or("PI history prologue without return")?;
                    require(
                        *fetch_context == p.0,
                        "PI history raw fetch context mismatch",
                    )?;
                    *fetch_context = p.1;
                }
            }
        }
        self.encode(&record)
    }
    fn scalar(&mut self, s: PiScalar) -> Result<(), String> {
        require(
            s.record == "scalar"
                && s.context == 0
                && s.write
                && s.bytes == 1
                && s.device == 5
                && s.address == s.aligned_address
                && s.address.0 < 8_388_608
                && s.value <= 255,
            "invalid PI scalar effect",
        )?;
        let c = self.copy.as_mut().ok_or("PI scalar outside copy")?;
        require(c.pc == s.pc, "PI scalar copy PC mismatch")?;
        let a = c.attempt.as_mut().ok_or("PI scalar without attempt")?;
        require(
            s.pi == (PiContext {
                transfer: c.id,
                block: c.block.ok_or("PI scalar outside block")?,
                lane: a.lane,
            }) && s.address == a.dram
                && s.value == u64::from(a.value)
                && a.writer.is_none(),
            "PI scalar disagrees with attempt",
        )?;
        a.writer = Some(s.ordinal);
        self.base(
            history::Record::Scalar {
                ordinal: s.ordinal,
                context: s.context,
                pc: s.pc,
                write: s.write,
                address: s.address,
                aligned_address: s.aligned_address,
                bytes: s.bytes,
                device: s.device,
                value: s.value,
            },
            true,
        )
    }
    fn pi(&mut self, record: PiRecord) -> Result<(), String> {
        require(self.header, "PI record before header")?;
        match record {
            PiRecord::PiRomHalf {
                ordinal,
                context,
                pc,
                transfer,
                block,
                offset,
                value,
            } => {
                self.identity(ordinal, context, pc, "pi_rom_half", false)?;
                require(
                    context == 0,
                    "PI ROM result inside fetch interval is unsupported",
                )?;
                require(self.half.is_none(), "orphan PI ROM result")?;
                let c = self.copy.as_ref().ok_or("PI ROM read outside copy")?;
                require(
                    c.id == transfer && c.block == Some(block) && c.pc == pc && c.attempt.is_none(),
                    "PI ROM context mismatch",
                )?;
                let mapped = self.source.len() & !7;
                let start = offset as usize;
                require(
                    offset.is_multiple_of(2)
                        && start.checked_add(2).is_some_and(|end| end <= mapped),
                    "PI ROM read outside mapped source",
                )?;
                require(
                    u16::from_be_bytes(self.source[start..start + 2].try_into().unwrap()) == value,
                    "PI ROM result disagrees with canonical source",
                )?;
                self.stats.source_reads += 1;
                self.half = Some(Half {
                    ordinal,
                    transfer,
                    block,
                    offset,
                    value,
                });
            }
            PiRecord::PiDma {
                ordinal,
                context,
                pc,
                event,
                transfer,
                block,
                dram,
                pbus,
                length,
                lane,
                value,
            } => {
                self.identity(ordinal, context, pc, "pi_dma", false)?;
                require(context == 0, "PI DMA inside fetch interval is unsupported")?;
                require((1..=8).contains(&event), "unsupported PI DMA event")?;
                require(self.half.is_none() || event == 3, "orphan PI ROM result")?;
                require(
                    self.copy.as_ref().is_none_or(|c| c.attempt.is_none()) || event == 5,
                    "PI byte attempt lacks immediate return",
                )?;
                if event == 1 {
                    require(
                        self.copy.is_none() && block == 0 && self.stats.transfers < MAX_TRANSFERS,
                        "invalid PI copy begin",
                    )?;
                    self.stats.transfers += 1;
                    require(
                        transfer == self.stats.transfers,
                        "PI transfer ordinal mismatch",
                    )?;
                    self.status_candidate = Some(transfer);
                    self.copy = Some(Copy {
                        id: transfer,
                        pc,
                        block: None,
                        blocks: 0,
                        buffer: [None; 128],
                        attempt: None,
                    });
                } else if event == 8 {
                    require(
                        self.copy.is_none() && lane == 0 && value == 1,
                        "invalid PI status transition",
                    )?;
                    require(
                        transfer == self.status_candidate.unwrap_or(0),
                        "PI status observer context mismatch",
                    )?;
                    self.status_candidate = None;
                    if transfer == 0 {
                        self.stats.unassociated += 1;
                    } else {
                        require(
                            self.stats.returned.contains(&transfer),
                            "PI status context lacks returned copy",
                        )?;
                        self.stats.statuses.push(transfer);
                    }
                } else {
                    let c = self.copy.as_mut().ok_or("PI event outside copy")?;
                    require(
                        c.id == transfer && c.pc == pc,
                        "PI event transfer/PC mismatch",
                    )?;
                    if event == 2 {
                        require(
                            c.block.is_none()
                                && c.attempt.is_none()
                                && (1..=128).contains(&length)
                                && lane <= 7,
                            "invalid PI block begin",
                        )?;
                        c.blocks = c.blocks.checked_add(1).ok_or("PI block overflow")?;
                        require(block == c.blocks, "PI block ordinal mismatch")?;
                        c.block = Some(block);
                        c.buffer = [None; 128];
                    } else if event == 7 {
                        require(
                            c.block.is_none() && c.attempt.is_none(),
                            "PI copy returns inside block",
                        )?;
                        self.stats.returned.insert(transfer);
                        self.copy = None;
                    } else {
                        require(c.block == Some(block), "PI event block mismatch")?;
                        match event {
                            3 => {
                                require(
                                    c.attempt.is_none()
                                        && lane.is_multiple_of(2)
                                        && lane < length
                                        && lane < 128
                                        && value <= 65535
                                        && c.buffer[lane as usize].is_none(),
                                    "invalid returned PI buffer half",
                                )?;
                                let half = self.half.take();
                                let offset = half
                                    .filter(|h| {
                                        h.ordinal + 1 == ordinal
                                            && h.transfer == transfer
                                            && h.block == block
                                            && h.offset.checked_add(0x10000000) == Some(pbus.0)
                                            && u32::from(h.value) == value
                                    })
                                    .map(|h| h.offset);
                                for i in 0..2 {
                                    c.buffer[lane as usize + i] = Some(Origin {
                                        value: (value >> (8 * (1 - i))) as u8,
                                        offset: offset.map(|o| o + i as u32),
                                    });
                                }
                            }
                            4 => {
                                require(
                                    lane < 128 && c.attempt.is_none(),
                                    "invalid PI byte attempt",
                                )?;
                                let origin = c.buffer[lane as usize]
                                    .ok_or("PI byte lacks returned buffer lane")?;
                                require(
                                    value == u32::from(origin.value),
                                    "PI byte attempt disagrees with buffer",
                                )?;
                                c.attempt = Some(Attempt {
                                    dram,
                                    pbus,
                                    length,
                                    lane,
                                    value,
                                    writer: None,
                                });
                                self.stats.attempts += 1;
                            }
                            5 => {
                                let a = c.attempt.take().ok_or("PI byte return without attempt")?;
                                require(
                                    (a.dram, a.pbus, a.length, a.lane, a.value)
                                        == (dram, pbus, length, lane, value),
                                    "PI byte return disagrees with attempt",
                                )?;
                                if let Some(writer) = a.writer {
                                    let origin = c.buffer[lane as usize].unwrap();
                                    self.stats.writes += 1;
                                    self.stats.known += u64::from(origin.offset.is_some());
                                    for bytes in [
                                        dram.0.to_be_bytes(),
                                        origin.offset.unwrap_or(u32::MAX).to_be_bytes(),
                                        value.to_be_bytes(),
                                    ] {
                                        self.effects.update(bytes);
                                    }
                                    self.effects.update(writer.to_be_bytes());
                                } else {
                                    self.stats.failed += 1;
                                }
                            }
                            6 => {
                                require(c.attempt.is_none(), "PI block returns during byte write")?;
                                c.block = None;
                            }
                            _ => return Err("invalid PI block event".into()),
                        }
                    }
                }
            }
        }
        Ok(())
    }
    fn next(&mut self) -> Result<bool, String> {
        self.output.clear();
        self.position = 0;
        loop {
            if !fetch::line(&mut self.input, &mut self.raw)? {
                require(self.ended, "truncated PI history")?;
                return Ok(false);
            }
            require(
                !self.ended && self.raw.ends_with(b"\n"),
                "extra or truncated PI history data",
            )?;
            self.hash.update(&self.raw);
            let record: Wire = serde_json::from_slice(&self.raw).map_err(|e| e.to_string())?;
            match record {
                Wire::Pi(r) => self.pi(r)?,
                Wire::Scalar(s) => {
                    self.scalar(s)?;
                    return Ok(true);
                }
                Wire::Base(r) => {
                    self.base(r, false)?;
                    return Ok(true);
                }
            }
        }
    }
}
impl<H: BufRead> Read for Projection<'_, H> {
    fn read(&mut self, buffer: &mut [u8]) -> io::Result<usize> {
        let source = self.fill_buf()?;
        let len = buffer.len().min(source.len());
        buffer[..len].copy_from_slice(&source[..len]);
        self.consume(len);
        Ok(len)
    }
}
impl<H: BufRead> BufRead for Projection<'_, H> {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        if self.position == self.output.len() {
            self.next()
                .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        }
        Ok(&self.output[self.position..])
    }
    fn consume(&mut self, amount: usize) {
        self.position = (self.position + amount).min(self.output.len());
    }
}

/// Inspect complete v1/v5 sources and actual ROM/firmware. The projected v0
/// validator retains all prior access/fetch checks and paired replay digest.
pub fn inspect_pi_boot_history<H: BufRead, F: BufRead + Seek>(
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<PiHistoryReport, String> {
    let mut projection = Projection::new(history, rom.bytes());
    let inspected = history::inspect_boot_history(&mut projection, fetched, rom, firmware)?;
    require(
        projection.ended && projection.output.is_empty(),
        "PI source was not completely consumed",
    )?;
    let stats = projection.stats;
    let statuses: BTreeSet<_> = stats.statuses.iter().copied().collect();
    Ok(PiHistoryReport {
        format: "plaid-pi-history-report-v0".into(),
        scope: "finite_reference_pi_effect_inspection".into(),
        history_sha256: format!("{:x}", projection.hash.finalize()),
        projection: inspected,
        records: stats.records,
        event_counts: stats.counts,
        source_half_reads: stats.source_reads,
        byte_attempts: stats.attempts,
        successful_pi_writes: stats.writes,
        canonical_rom_byte_origins: stats.known,
        unknown_pi_byte_origins: stats.writes - stats.known,
        failed_destination_witnesses: stats.failed,
        returned_transfers: stats.returned.len() as u64,
        completion_status_transitions: stats.statuses.len() as u64 + stats.unassociated,
        observer_write_contexts_at_status: stats.statuses,
        writes_without_observer_status: stats.returned.difference(&statuses).copied().collect(),
        transfer_completion_certified: false,
        unassociated_completions: stats.unassociated,
        pi_origin_effects_sha256: format!("{:x}", projection.effects.finalize()),
    })
}
pub fn verify_pi_boot_history_report<H: BufRead, F: BufRead + Seek>(
    report: &PiHistoryReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_pi_boot_history(history, fetched, rom, firmware)?,
        "PI report does not match complete sources/inputs",
    )
}
