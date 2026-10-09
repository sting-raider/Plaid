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

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum Wire {
    Sp(SpRecord),
    Legacy(queue::Wire),
}
#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum SpRecord {
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
struct ReadWitness {
    ordinal: u64,
    bank: u32,
    offset: u32,
    value: u32,
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
            require(
                !self.header
                    && format == FORMAT
                    && policy == POLICY
                    && lifecycle_policy == history::LIFECYCLE_POLICY,
                "unsupported/repeated v3 header",
            )?;
            self.header = true;
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
    Ok(SpHistoryReport {
        format: "plaid-observed-sp-backing-report-v0".into(),
        scope: "finite_actual_cpu_sp_reads_and_observed_stores".into(),
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
    })
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
