//! Actual CPU SP backing-read observations and completed normalized stores.
//! Bank identity is not ultimate byte origin or a certified executable lifetime.
use crate::{fetch, history, pi_history, pi_queue_history as queue, program::*, rom::CanonicalRom};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{self, BufRead, Read, Seek},
};

pub const FORMAT: &str = "plaid-ares-access-history-v3";
pub const POLICY: &str = "identity_ram_pi_queue_and_observed_sp_backing";
pub const STORAGE_FORMAT: &str = "plaid-ares-access-history-v5";
pub const STORAGE_POLICY: &str = "observed_ordinary_storage_mutations_and_pi_queue_sp_backing";
pub const DMEM_STORAGE_FORMAT: &str = "plaid-ares-access-history-v6";
pub const DMEM_STORAGE_POLICY: &str =
    "observed_ordinary_storage_and_dmem_mutations_with_pi_queue_sp_backing";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpBackingFetchSample {
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub bank: u32,
    pub offset: u32,
    pub first_fetch: u64,
    pub last_fetch: u64,
    pub first_read_ordinal: u64,
    pub last_read_ordinal: u64,
    pub observations: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpDmaStoreReceipt {
    pub write_ordinal: u64,
    pub read_ordinal: Option<u64>,
    pub dram: PhysicalAddr,
    pub bank: u32,
    pub offset: u32,
    pub bytes: u32,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpHistoryReport {
    pub format: String,
    pub scope: String,
    pub history_sha256: String,
    pub projection: queue::PiQueueHistoryReport,
    pub records: u64,
    pub v2_records: u64,
    #[serde(with = "crate::program::unique_map")]
    pub event_counts: BTreeMap<String, u64>,
    pub fetches: u64,
    pub sp_backed_fetches: u64,
    pub other_or_unwitnessed_fetches: u64,
    pub samples: Vec<SpBackingFetchSample>,
    pub dma_store_receipts: Vec<SpDmaStoreReceipt>,
    pub unconsumed_dma_read_receipts: u64,
    pub ordered_fetch_backing_sha256: String,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum CapturedSpWriterKind {
    WordSink {
        cpu: bool,
    },
    DmaSink {
        dram: PhysicalAddr,
        read_ordinal: Option<u64>,
    },
}

/// Compatible latest *captured* writer, not ultimate byte ancestry. Ordinals
/// belong to the complete v3 history identified by the containing report.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CapturedSpByteWriter {
    pub write_ordinal: u64,
    pub byte_index: u8,
    pub kind: CapturedSpWriterKind,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpWriterFetchSample {
    pub backing: SpBackingFetchSample,
    pub writers: [Option<CapturedSpByteWriter>; 4],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SpWriterFetchReport {
    pub format: String,
    pub projection: SpHistoryReport,
    pub captured_writes: u64,
    pub contradicted_byte_candidates: u64,
    pub fully_compatible_fetches: u64,
    pub partially_compatible_fetches: u64,
    pub unknown_sp_fetches: u64,
    pub samples: Vec<SpWriterFetchSample>,
    pub ordered_candidates_sha256: String,
    pub ultimate_ancestry_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

type WriterSampleKey = (SampleKey, [Option<CapturedSpByteWriter>; 4]);
pub(crate) struct WriterLineage {
    bytes: Vec<Option<(u8, CapturedSpByteWriter)>>,
    captured_writes: u64,
    contradictions: u64,
    full: u64,
    partial: u64,
    unknown: u64,
    samples: BTreeMap<WriterSampleKey, SpWriterFetchSample>,
    ordered: Sha256,
}
impl WriterLineage {
    pub(crate) fn cut_dmem(&mut self, offset: u32, bytes: u32) {
        self.bytes[offset as usize..(offset + bytes) as usize].fill(None);
    }
    pub(crate) fn new() -> Self {
        Self {
            bytes: vec![None; 8192],
            captured_writes: 0,
            contradictions: 0,
            full: 0,
            partial: 0,
            unknown: 0,
            samples: BTreeMap::new(),
            ordered: Sha256::new(),
        }
    }
    pub(crate) fn write(
        &mut self,
        bank: u32,
        offset: u32,
        payload: &[u8],
        ordinal: u64,
        kind: CapturedSpWriterKind,
    ) {
        self.captured_writes += 1;
        for (index, value) in payload.iter().copied().enumerate() {
            self.bytes[bank as usize * 4096 + offset as usize + index] = Some((
                value,
                CapturedSpByteWriter {
                    write_ordinal: ordinal,
                    byte_index: index as u8,
                    kind,
                },
            ));
        }
    }
    pub(crate) fn read(
        &mut self,
        bank: u32,
        offset: u32,
        word: u32,
    ) -> [Option<CapturedSpByteWriter>; 4] {
        let mut writers = [None; 4];
        for (index, value) in word.to_be_bytes().into_iter().enumerate() {
            let candidate = &mut self.bytes[bank as usize * 4096 + offset as usize + index];
            if candidate.is_some_and(|(captured, _)| captured != value) {
                *candidate = None;
                self.contradictions += 1;
            }
            writers[index] = candidate.map(|(_, writer)| writer);
        }
        writers
    }
    fn fetched(
        &mut self,
        sample: SpBackingFetchSample,
        writers: [Option<CapturedSpByteWriter>; 4],
    ) -> Result<(), String> {
        let count = writers.iter().flatten().count();
        if count == 4 {
            self.full += 1;
        } else if count == 0 {
            self.unknown += 1;
        } else {
            self.partial += 1;
        }
        // Commit actual discrete fetch/read occurrences, not an inferred interval.
        self.ordered
            .update(serde_json::to_vec(&(&sample, &writers)).map_err(|e| e.to_string())?);
        self.ordered.update(b"\n");
        let key = (
            (
                sample.pc,
                sample.physical,
                sample.word,
                sample.bank,
                sample.offset,
            ),
            writers,
        );
        let retained = self
            .samples
            .entry(key)
            .or_insert_with(|| SpWriterFetchSample {
                backing: sample.clone(),
                writers,
            });
        retained.backing.last_fetch = sample.last_fetch;
        retained.backing.last_read_ordinal = sample.last_read_ordinal;
        retained.backing.observations += 1;
        Ok(())
    }
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(untagged)]
pub(crate) enum Wire {
    Sp(SpRecord),
    Storage(StorageRecord),
    Legacy(queue::Wire),
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum StorageRecord {
    StorageEffect {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        kind: u32,
        address: PhysicalAddr,
        bytes: u32,
        value: u64,
    },
}
impl StorageRecord {
    pub(crate) fn validate(&self) -> Result<(), String> {
        let Self::StorageEffect {
            kind,
            address,
            bytes,
            value,
            ..
        } = self;
        match *kind {
            0 => require(
                matches!(bytes, 1 | 2 | 4)
                    && address.0.is_multiple_of(*bytes)
                    && address
                        .0
                        .checked_add(*bytes)
                        .is_some_and(|end| end <= 8_388_608)
                    && *value < (1u64 << (*bytes * 8)),
                "invalid completed ordinary storage effect",
            ),
            1 | 2 => require(
                address.0 == 0 && *bytes == 8_388_608 && *value == 0,
                "invalid whole-RAM storage cut",
            ),
            _ => Err("storage restore/retirement needs an execution-epoch source contract".into()),
        }
    }
}
#[derive(Debug, Deserialize, Serialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
pub(crate) enum SpRecord {
    RspDmemEffect {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        offset: u32,
        bytes: u32,
        value: u64,
    },
    SpWord {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write: bool,
        address: PhysicalAddr,
        bank: u32,
        offset: u32,
        bytes: u32,
        value: u32,
        cpu: bool,
    },
    SpDmaStore {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        dram: PhysicalAddr,
        bank: u32,
        offset: u32,
        bytes: u32,
        value: u64,
    },
}
impl Wire {
    pub(crate) fn base(&self) -> Option<&history::Record> {
        match self {
            Self::Legacy(queue::Wire::Legacy(pi_history::Wire::Base(r))) => Some(r),
            _ => None,
        }
    }
    pub(crate) fn base_mut(&mut self) -> Option<&mut history::Record> {
        match self {
            Self::Legacy(queue::Wire::Legacy(pi_history::Wire::Base(r))) => Some(r),
            _ => None,
        }
    }
    pub(crate) fn identity(&self) -> Option<(u64, u64, GuestVirtualAddr, &'static str)> {
        match self {
            Self::Sp(SpRecord::RspDmemEffect {
                ordinal,
                context,
                pc,
                ..
            }) => Some((*ordinal, *context, *pc, "rsp_dmem_effect")),
            Self::Sp(SpRecord::SpWord {
                ordinal,
                context,
                pc,
                ..
            }) => Some((*ordinal, *context, *pc, "sp_word")),
            Self::Sp(SpRecord::SpDmaStore {
                ordinal,
                context,
                pc,
                ..
            }) => Some((*ordinal, *context, *pc, "sp_dma_store")),
            Self::Storage(StorageRecord::StorageEffect {
                ordinal,
                context,
                pc,
                ..
            }) => Some((*ordinal, *context, *pc, "storage_effect")),
            Self::Legacy(queue::Wire::Schedule(s)) => Some(s.identity()),
            Self::Legacy(queue::Wire::Legacy(r)) => r.identity(),
        }
    }
    pub(crate) fn renumber(&mut self, next: u64, scope: u64) {
        match self {
            Self::Sp(SpRecord::SpWord {
                ordinal, context, ..
            })
            | Self::Sp(SpRecord::SpDmaStore {
                ordinal, context, ..
            })
            | Self::Sp(SpRecord::RspDmemEffect {
                ordinal, context, ..
            }) => {
                *ordinal = next;
                *context = scope;
            }
            Self::Storage(StorageRecord::StorageEffect {
                ordinal, context, ..
            }) => {
                *ordinal = next;
                *context = scope;
            }
            Self::Legacy(queue::Wire::Schedule(s)) => s.renumber(next, scope),
            Self::Legacy(queue::Wire::Legacy(r)) => r.renumber(next, scope),
        }
    }
}
struct ReadWitness {
    ordinal: u64,
    bank: u32,
    offset: u32,
    value: u32,
    writers: [Option<CapturedSpByteWriter>; 4],
}
struct Span {
    raw: u64,
    mapped: u64,
    pc: GuestVirtualAddr,
    vaddr: GuestVirtualAddr,
    translated: PhysicalAddr,
    bus: PhysicalAddr,
    cached: bool,
    eligible: u64,
    read: Option<ReadWitness>,
    value: Option<u32>,
}
struct Receipt {
    ordinal: u64,
    pc: GuestVirtualAddr,
    address: PhysicalAddr,
    bytes: u32,
    value: u64,
}
type SampleKey = (GuestVirtualAddr, PhysicalAddr, u32, u32, u32);
struct Projection<H> {
    input: H,
    raw: Vec<u8>,
    output: Vec<u8>,
    position: usize,
    hash: Sha256,
    ordered: Sha256,
    header: bool,
    storage: bool,
    dmem_storage: bool,
    ended: bool,
    records: u64,
    projected: u64,
    counts: BTreeMap<String, u64>,
    active: Option<Span>,
    pending: Option<Span>,
    copying: bool,
    fetches: u64,
    witnesses: u64,
    receipts: Vec<Receipt>,
    unconsumed: u64,
    links: Vec<SpDmaStoreReceipt>,
    samples: BTreeMap<SampleKey, SpBackingFetchSample>,
    lineage: Option<WriterLineage>,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl<H: BufRead> Projection<H> {
    fn new(input: H) -> Self {
        Self {
            input,
            raw: Vec::new(),
            output: Vec::new(),
            position: 0,
            hash: Sha256::new(),
            ordered: Sha256::new(),
            header: false,
            storage: false,
            dmem_storage: false,
            ended: false,
            records: 0,
            projected: 0,
            counts: BTreeMap::new(),
            active: None,
            pending: None,
            copying: false,
            fetches: 0,
            witnesses: 0,
            receipts: Vec::new(),
            unconsumed: 0,
            links: Vec::new(),
            samples: BTreeMap::new(),
            lineage: None,
        }
    }
    fn identity(
        &mut self,
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        kind: &str,
    ) -> Result<(), String> {
        require(
            self.header && self.records < history::MAX_RECORDS && ordinal == self.records + 1,
            "v3 record ordinal/header mismatch",
        )?;
        require(
            self.pending.is_none() || kind == "fetch",
            "v3 fetch return lacks immediate prologue",
        )?;
        require(
            context == self.active.as_ref().map_or(0, |s| s.raw)
                && self.active.as_ref().is_none_or(|s| s.pc == pc),
            "v3 raw fetch context/PC mismatch",
        )?;
        self.records += 1;
        *self.counts.entry(kind.into()).or_default() += 1;
        Ok(())
    }
    fn sp(&mut self, row: SpRecord) -> Result<(), String> {
        require(!self.copying, "SP row inside buffered PI copy")?;
        match row {
            SpRecord::RspDmemEffect {
                ordinal,
                context,
                pc,
                offset,
                bytes,
                value,
            } => {
                require(
                    self.dmem_storage
                        && self.active.is_none()
                        && matches!(bytes, 1 | 2 | 4 | 8)
                        && offset.is_multiple_of(bytes)
                        && offset.checked_add(bytes).is_some_and(|end| end <= 4096)
                        && (bytes == 8 || value < (1u64 << (bytes * 8))),
                    "invalid or unsupported lower DMEM storage effect",
                )?;
                self.identity(ordinal, context, pc, "rsp_dmem_effect")?;
                if let Some(lineage) = &mut self.lineage {
                    lineage.cut_dmem(offset, bytes);
                }
            }
            SpRecord::SpWord {
                ordinal,
                context,
                pc,
                write,
                address,
                bank,
                offset,
                bytes,
                value,
                cpu,
            } => {
                self.unconsumed += self.receipts.len() as u64;
                self.receipts.clear();
                self.identity(ordinal, context, pc, "sp_word")?;
                require(
                    (0x04000000..=0x0403ffff).contains(&address.0)
                        && bytes == 4
                        && bank == (address.0 >> 12 & 1)
                        && offset == address.0 & 0xffc,
                    "SP word does not identify actual bank/aligned backing",
                )?;
                require(
                    !write || self.active.is_none(),
                    "SP store inside instruction fetch",
                )?;
                let mut writers = [None; 4];
                if let Some(lineage) = &mut self.lineage {
                    if write {
                        lineage.write(
                            bank,
                            offset,
                            &value.to_be_bytes(),
                            ordinal,
                            CapturedSpWriterKind::WordSink { cpu },
                        );
                    } else {
                        writers = lineage.read(bank, offset, value);
                    }
                }
                if !write
                    && cpu
                    && let Some(span) = &mut self.active
                    && address == span.bus
                {
                    span.eligible += 1;
                    span.read = Some(ReadWitness {
                        ordinal,
                        bank,
                        offset,
                        value,
                        writers,
                    });
                }
            }
            SpRecord::SpDmaStore {
                ordinal,
                context,
                pc,
                dram,
                bank,
                offset,
                bytes,
                value,
            } => {
                self.identity(ordinal, context, pc, "sp_dma_store")?;
                require(
                    self.active.is_none()
                        && bank <= 1
                        && matches!(bytes, 4 | 8)
                        && offset < 4096
                        && offset.is_multiple_of(bytes)
                        && dram.0 < 0x1000000
                        && (bytes == 8 || value <= u32::MAX as u64),
                    "invalid normalized SP DMA store",
                )?;
                require(
                    self.links.len() < (history::MAX_RECORDS as usize),
                    "too many SP DMA stores",
                )?;
                let mut matches = self.receipts.iter().enumerate().filter(|(_, r)| {
                    (r.pc, r.address, r.bytes, r.value) == (pc, dram, bytes, value)
                });
                let first = matches.next().map(|(i, _)| i);
                let index = if matches.next().is_none() {
                    first
                } else {
                    None
                };
                let read_ordinal = index.map(|i| self.receipts.remove(i).ordinal);
                if let Some(lineage) = &mut self.lineage {
                    let payload = value.to_be_bytes();
                    lineage.write(
                        bank,
                        offset,
                        &payload[8 - bytes as usize..],
                        ordinal,
                        CapturedSpWriterKind::DmaSink { dram, read_ordinal },
                    );
                }
                self.links.push(SpDmaStoreReceipt {
                    write_ordinal: ordinal,
                    read_ordinal,
                    dram,
                    bank,
                    offset,
                    bytes,
                });
            }
        }
        Ok(())
    }
    fn legacy(&mut self, mut row: queue::Wire) -> Result<(), String> {
        use history::Record as R;
        if !matches!(
            &row,
            queue::Wire::Legacy(pi_history::Wire::Base(R::Scalar {
                write: false,
                device: 4,
                ..
            }))
        ) {
            self.unconsumed += self.receipts.len() as u64;
            self.receipts.clear();
        }
        if let queue::Wire::Legacy(pi_history::Wire::Base(R::Header {
            format,
            policy,
            lifecycle_policy,
            ..
        })) = &mut row
        {
            let dmem_storage = format == DMEM_STORAGE_FORMAT && policy == DMEM_STORAGE_POLICY;
            let storage = (format == STORAGE_FORMAT && policy == STORAGE_POLICY) || dmem_storage;
            require(
                !self.header
                    && ((format == FORMAT && policy == POLICY) || storage)
                    && lifecycle_policy == history::LIFECYCLE_POLICY,
                "unsupported/repeated v3 header",
            )?;
            self.header = true;
            self.storage = storage;
            self.dmem_storage = dmem_storage;
            *format = queue::FORMAT.into();
            *policy = queue::POLICY.into();
        } else if let queue::Wire::Legacy(pi_history::Wire::Base(R::End {
            record_count,
            fetch_count,
            ..
        })) = &mut row
        {
            require(
                self.header
                    && *record_count == self.records
                    && *fetch_count == self.fetches
                    && self.active.is_none()
                    && self.pending.is_none()
                    && !self.copying,
                "incomplete v3 footer",
            )?;
            *record_count = self.projected;
            self.ended = true;
        } else {
            let (ordinal, context, pc, kind) = match &row {
                queue::Wire::Schedule(s) => s.identity(),
                queue::Wire::Legacy(r) => r.identity().ok_or("missing v3 legacy identity")?,
            };
            if let queue::Wire::Legacy(pi_history::Wire::Base(R::FetchBegin {
                vaddr,
                translated,
                bus,
                cached,
                ..
            })) = &row
            {
                require(
                    self.active.is_none() && self.pending.is_none() && context == ordinal,
                    "invalid v3 fetch begin",
                )?;
                self.active = Some(Span {
                    raw: ordinal,
                    mapped: self.projected + 1,
                    pc,
                    vaddr: *vaddr,
                    translated: *translated,
                    bus: *bus,
                    cached: *cached,
                    eligible: 0,
                    read: None,
                    value: None,
                });
            }
            self.identity(ordinal, context, pc, kind)?;
            match &row {
                queue::Wire::Legacy(pi_history::Wire::Pi(pi_history::PiRecord::PiDma {
                    event: 1,
                    ..
                })) => self.copying = true,
                queue::Wire::Legacy(pi_history::Wire::Pi(pi_history::PiRecord::PiDma {
                    event: 7,
                    ..
                })) => self.copying = false,
                queue::Wire::Legacy(pi_history::Wire::Base(R::Scalar {
                    ordinal,
                    pc,
                    write: false,
                    address,
                    bytes,
                    device: 4,
                    value,
                    ..
                })) => {
                    require(
                        self.receipts.len() < queue::MAX_IDENTITIES as usize,
                        "too many unconsumed SP DMA reads",
                    )?;
                    self.receipts.push(Receipt {
                        ordinal: *ordinal,
                        pc: *pc,
                        address: *address,
                        bytes: *bytes,
                        value: *value,
                    });
                }
                _ => {}
            }
            self.projected += 1;
            let scope = self.active.as_ref().map_or(0, |s| s.mapped);
            match &mut row {
                queue::Wire::Schedule(s) => s.renumber(self.projected, scope),
                queue::Wire::Legacy(r) => r.renumber(self.projected, scope),
            }
            if let queue::Wire::Legacy(pi_history::Wire::Base(R::FetchEnd {
                vaddr,
                translated,
                bus,
                cached,
                value,
                ..
            })) = &row
            {
                let mut span = self.active.take().ok_or("v3 return without begin")?;
                require(
                    (span.vaddr, span.translated, span.bus, span.cached)
                        == (*vaddr, *translated, *bus, *cached),
                    "v3 return differs from fetch begin",
                )?;
                span.value = Some(*value);
                self.pending = Some(span);
            }
            if let queue::Wire::Legacy(pi_history::Wire::Base(R::Fetch {
                fetch_context,
                fetch_seq,
                word,
                physical,
                cached,
                ..
            })) = &mut row
            {
                let span = self.pending.take().ok_or("v3 prologue without return")?;
                require(
                    *fetch_context == span.raw
                        && *fetch_seq == self.fetches
                        && span.value == Some(*word)
                        && (*physical, *cached) == (span.bus, span.cached),
                    "v3 prologue differs from actual fetch",
                )?;
                *fetch_context = span.mapped;
                let read = if !span.cached && span.eligible == 1 {
                    span.read
                } else {
                    None
                };
                for n in [self.fetches, pc.0, physical.0 as u64, *word as u64] {
                    self.ordered.update(n.to_be_bytes());
                }
                self.ordered.update([u8::from(read.is_some())]);
                if let Some(r) = read {
                    require(
                        r.value == *word,
                        "SP backing read differs from fetched word",
                    )?;
                    self.witnesses += 1;
                    if let Some(lineage) = &mut self.lineage {
                        lineage.fetched(
                            SpBackingFetchSample {
                                pc,
                                physical: *physical,
                                word: *word,
                                bank: r.bank,
                                offset: r.offset,
                                first_fetch: self.fetches,
                                last_fetch: self.fetches,
                                first_read_ordinal: r.ordinal,
                                last_read_ordinal: r.ordinal,
                                observations: 0,
                            },
                            r.writers,
                        )?;
                    }
                    for n in [r.bank as u64, r.offset as u64, r.ordinal] {
                        self.ordered.update(n.to_be_bytes());
                    }
                    let key = (pc, *physical, *word, r.bank, r.offset);
                    let sample = self.samples.entry(key).or_insert(SpBackingFetchSample {
                        pc,
                        physical: *physical,
                        word: *word,
                        bank: r.bank,
                        offset: r.offset,
                        first_fetch: self.fetches,
                        last_fetch: self.fetches,
                        first_read_ordinal: r.ordinal,
                        last_read_ordinal: r.ordinal,
                        observations: 0,
                    });
                    sample.last_fetch = self.fetches;
                    sample.last_read_ordinal = r.ordinal;
                    sample.observations += 1;
                }
                self.fetches += 1;
            }
        }
        self.output = serde_json::to_vec(&row).map_err(|e| e.to_string())?;
        self.output.push(b'\n');
        self.position = 0;
        Ok(())
    }
    fn next(&mut self) -> Result<bool, String> {
        loop {
            if !fetch::line(&mut self.input, &mut self.raw)? {
                require(self.ended, "v3 history lacks complete footer")?;
                return Ok(false);
            }
            require(
                !self.ended && self.raw.ends_with(b"\n"),
                "truncated or trailing v3 record",
            )?;
            self.hash.update(&self.raw);
            match serde_json::from_slice::<Wire>(&self.raw).map_err(|e| e.to_string())? {
                Wire::Sp(s) => self.sp(s)?,
                Wire::Storage(s) => {
                    require(self.storage, "storage effect outside v5 source policy")?;
                    s.validate()?;
                    let StorageRecord::StorageEffect {
                        ordinal,
                        context,
                        pc,
                        ..
                    } = s;
                    self.identity(ordinal, context, pc, "storage_effect")?;
                }
                Wire::Legacy(r) => {
                    self.legacy(r)?;
                    return Ok(true);
                }
            }
        }
    }
}
impl<H: BufRead> Read for Projection<H> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        let data = self.fill_buf()?;
        let count = data.len().min(output.len());
        output[..count].copy_from_slice(&data[..count]);
        self.consume(count);
        Ok(count)
    }
}
impl<H: BufRead> BufRead for Projection<H> {
    fn fill_buf(&mut self) -> io::Result<&[u8]> {
        if self.position == self.output.len() {
            self.output.clear();
            self.position = 0;
            self.next().map_err(io::Error::other)?;
        }
        Ok(&self.output[self.position..])
    }
    fn consume(&mut self, amount: usize) {
        self.position = (self.position + amount).min(self.output.len());
    }
}

pub fn inspect_sp_boot_history<H: BufRead, F: BufRead + Seek>(
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<SpHistoryReport, String> {
    let mut stream = Projection::new(history);
    let projection = queue::inspect_pi_queue_boot_history(&mut stream, fetched, rom, firmware)?;
    require(
        stream.ended && stream.fill_buf().map_err(|e| e.to_string())?.is_empty(),
        "incomplete v3 source",
    )?;
    Ok(finish_report(stream, projection))
}

fn finish_report<H>(
    stream: Projection<H>,
    projection: queue::PiQueueHistoryReport,
) -> SpHistoryReport {
    SpHistoryReport {
        format: if stream.dmem_storage {
            "plaid-observed-sp-backing-report-v2"
        } else if stream.storage {
            "plaid-observed-sp-backing-report-v1"
        } else {
            "plaid-observed-sp-backing-report-v0"
        }
        .into(),
        scope: if stream.storage {
            "finite_actual_sp_backing_with_observed_ordinary_storage_effects"
        } else {
            "finite_actual_cpu_sp_reads_and_observed_stores"
        }
        .into(),
        history_sha256: format!("{:x}", stream.hash.finalize()),
        projection,
        records: stream.records,
        v2_records: stream.projected,
        event_counts: stream.counts,
        fetches: stream.fetches,
        sp_backed_fetches: stream.witnesses,
        other_or_unwitnessed_fetches: stream.fetches - stream.witnesses,
        samples: stream.samples.into_values().collect(),
        dma_store_receipts: stream.links,
        unconsumed_dma_read_receipts: stream.unconsumed + stream.receipts.len() as u64,
        ordered_fetch_backing_sha256: format!("{:x}", stream.ordered.finalize()),
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    }
}

/// Compose captured normalized SP writers with actual CPU executable backing
/// reads. Both complete sources must match independently retained receipts.
/// Ordinary RSP writers and out-of-band initialization are not fully sensed by
/// v3: compatibility with a captured writer never proves ultimate ancestry.
pub fn inspect_sp_writer_fetch_history<H: BufRead, F: BufRead + Seek>(
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
    expected_history_sha256: &str,
    expected_fetch_sha256: &str,
) -> Result<SpWriterFetchReport, String> {
    let mut stream = Projection::new(history);
    stream.lineage = Some(WriterLineage::new());
    let projection = queue::inspect_pi_queue_boot_history(&mut stream, fetched, rom, firmware)?;
    require(
        stream.ended && stream.fill_buf().map_err(|e| e.to_string())?.is_empty(),
        "incomplete v3 source",
    )?;
    let lineage = stream.lineage.take().expect("requested writer lineage");
    let projection = finish_report(stream, projection);
    require(
        projection.history_sha256 == expected_history_sha256
            && projection.projection.projection.projection.fetch_sha256 == expected_fetch_sha256,
        "SP writer/fetch source receipt mismatch",
    )?;
    Ok(SpWriterFetchReport {
        format: "plaid-observed-sp-writer-fetch-report-v0".into(),
        projection,
        captured_writes: lineage.captured_writes,
        contradicted_byte_candidates: lineage.contradictions,
        fully_compatible_fetches: lineage.full,
        partially_compatible_fetches: lineage.partial,
        unknown_sp_fetches: lineage.unknown,
        samples: lineage.samples.into_values().collect(),
        ordered_candidates_sha256: format!("{:x}", lineage.ordered.finalize()),
        ultimate_ancestry_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_sp_writer_fetch_report<H: BufRead, F: BufRead + Seek>(
    report: &SpWriterFetchReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
    expected_history_sha256: &str,
    expected_fetch_sha256: &str,
) -> Result<(), String> {
    require(
        *report
            == inspect_sp_writer_fetch_history(
                history,
                fetched,
                rom,
                firmware,
                expected_history_sha256,
                expected_fetch_sha256,
            )?,
        "SP writer/fetch report differs from complete sources/inputs",
    )
}
pub fn verify_sp_boot_history_report<H: BufRead, F: BufRead + Seek>(
    report: &SpHistoryReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_sp_boot_history(history, fetched, rom, firmware)?,
        "SP report differs from complete sources/inputs",
    )
}

#[cfg(test)]
mod writer_tests {
    use super::*;
    fn cpu() -> CapturedSpWriterKind {
        CapturedSpWriterKind::WordSink { cpu: true }
    }
    fn dma() -> CapturedSpWriterKind {
        CapturedSpWriterKind::DmaSink {
            dram: PhysicalAddr(4096),
            read_ordinal: Some(1),
        }
    }
    #[test]
    fn same_value_word_sink_replaces_dma_byte_candidates() {
        let mut lineage = WriterLineage::new();
        lineage.write(1, 0, &[1, 2, 3, 4, 5, 6, 7, 8], 2, dma());
        lineage.write(1, 0, &[1, 2, 3, 4], 3, cpu());
        let first = lineage.read(1, 0, 0x01020304);
        let second = lineage.read(1, 4, 0x05060708);
        assert!(
            first
                .into_iter()
                .flatten()
                .all(|w| w.write_ordinal == 3 && w.kind == cpu())
        );
        assert!(
            second
                .into_iter()
                .flatten()
                .all(|w| w.write_ordinal == 2 && w.kind == dma())
        );
    }
    #[test]
    fn contradictory_byte_never_revives_without_a_fresh_write() {
        let mut lineage = WriterLineage::new();
        lineage.write(1, 0, &[1, 2, 3, 4], 2, cpu());
        assert!(lineage.read(1, 0, 0x09020304)[0].is_none());
        let later = lineage.read(1, 0, 0x01020304);
        assert!(later[0].is_none());
        assert!(later[1..].iter().all(Option::is_some));
        assert_eq!(lineage.contradictions, 1);
        lineage.write(1, 0, &[1, 2, 3, 4], 5, cpu());
        assert!(
            lineage
                .read(1, 0, 0x01020304)
                .into_iter()
                .flatten()
                .all(|w| w.write_ordinal == 5)
        );
    }
    #[test]
    fn banks_and_full_word_sinks_stay_distinct_at_bank_end() {
        let mut lineage = WriterLineage::new();
        lineage.write(0, 4092, &[1, 2, 3, 4], 1, cpu());
        assert_eq!(lineage.read(1, 4092, 0x01020304), [None; 4]);
        lineage.write(1, 4088, &[0, 0, 0, 0, 1, 2, 3, 4], 2, dma());
        assert_eq!(
            lineage.read(0, 4092, 0x01020304)[0].unwrap().write_ordinal,
            1
        );
        let last = lineage.read(1, 4092, 0x01020304);
        assert_eq!(last[0].unwrap().byte_index, 4);
        assert_eq!(last[3].unwrap().byte_index, 7);
    }
    #[test]
    fn partial_and_unknown_reads_keep_candidate_counts_separate() {
        let mut lineage = WriterLineage::new();
        lineage.write(1, 0, &[1, 2, 3, 4], 1, cpu());
        let candidates = lineage.read(1, 0, 0x09020304);
        let sample = SpBackingFetchSample {
            pc: GuestVirtualAddr(0xffffffffa4001000),
            physical: PhysicalAddr(0x04001000),
            word: 0x09020304,
            bank: 1,
            offset: 0,
            first_fetch: 1,
            last_fetch: 1,
            first_read_ordinal: 9,
            last_read_ordinal: 9,
            observations: 0,
        };
        lineage.fetched(sample.clone(), candidates).unwrap();
        lineage.fetched(sample, [None; 4]).unwrap();
        assert_eq!((lineage.full, lineage.partial, lineage.unknown), (0, 1, 1));
        assert_eq!(lineage.samples.len(), 2);
    }
}
