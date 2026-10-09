//! Actual read-only PIF-ROM backing and delegated no-effect write attempts.
use crate::{
    fetch, history, pi_history, pi_queue_history as queue, program::*, rom::CanonicalRom,
    sp_history as sp,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{self, BufRead, Read, Seek},
};

pub const FORMAT: &str = "plaid-ares-access-history-v4";
pub const POLICY: &str = "identity_ram_pi_queue_sp_and_observed_pif_backing";
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PifBackingFetchSample {
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub offset: u32,
    pub matches_supplied_firmware: bool,
    pub first_fetch: u64,
    pub last_fetch: u64,
    pub first_read_ordinal: u64,
    pub last_read_ordinal: u64,
    pub observations: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PifWriteAttempt {
    pub ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub offset: u32,
    pub value: u32,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PifHistoryReport {
    pub format: String,
    pub scope: String,
    pub history_sha256: String,
    pub projection: sp::SpHistoryReport,
    pub records: u64,
    pub v3_records: u64,
    #[serde(with = "crate::program::unique_map")]
    pub event_counts: BTreeMap<String, u64>,
    pub fetches: u64,
    pub pif_backed_fetches: u64,
    pub supplied_firmware_matching_fetches: u64,
    pub other_or_unwitnessed_fetches: u64,
    pub samples: Vec<PifBackingFetchSample>,
    pub write_attempts: Vec<PifWriteAttempt>,
    pub ordered_fetch_backing_sha256: String,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}
#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum Wire {
    Pif(PifRecord),
    Legacy(sp::Wire),
}
#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum PifRecord {
    PifRomWord {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write: bool,
        offset: u32,
        bytes: u32,
        value: u32,
    },
    PifRomWriteAttempt {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write: bool,
        offset: u32,
        bytes: u32,
        value: u32,
    },
}
struct ReadWitness {
    ordinal: u64,
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
type SampleKey = (GuestVirtualAddr, PhysicalAddr, u32, u32);
struct Projection<'a, H> {
    input: H,
    firmware: &'a [u8],
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
    matching: u64,
    writes: Vec<PifWriteAttempt>,
    samples: BTreeMap<SampleKey, PifBackingFetchSample>,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl<'a, H: BufRead> Projection<'a, H> {
    fn new(input: H, firmware: &'a [u8]) -> Self {
        Self {
            input,
            firmware,
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
            matching: 0,
            writes: Vec::new(),
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
            "v4 record ordinal/header mismatch",
        )?;
        require(
            self.pending.is_none() || kind == "fetch",
            "v4 return lacks immediate prologue",
        )?;
        require(
            context == self.active.as_ref().map_or(0, |s| s.raw)
                && self.active.as_ref().is_none_or(|s| s.pc == pc),
            "v4 raw fetch context/PC mismatch",
        )?;
        self.records += 1;
        *self.counts.entry(kind.into()).or_default() += 1;
        Ok(())
    }
    fn pif(&mut self, row: PifRecord) -> Result<(), String> {
        let (ordinal, context, pc, write, offset, bytes, value, attempt) = match row {
            PifRecord::PifRomWord {
                ordinal,
                context,
                pc,
                write,
                offset,
                bytes,
                value,
            } => (ordinal, context, pc, write, offset, bytes, value, false),
            PifRecord::PifRomWriteAttempt {
                ordinal,
                context,
                pc,
                write,
                offset,
                bytes,
                value,
            } => (ordinal, context, pc, write, offset, bytes, value, true),
        };
        require(
            write == attempt,
            "PIF read/write-attempt kind disagrees with direction",
        )?;
        require(!self.copying, "PIF row inside buffered PI copy")?;
        self.identity(
            ordinal,
            context,
            pc,
            if attempt {
                "pif_rom_write_attempt"
            } else {
                "pif_rom_word"
            },
        )?;
        require(
            bytes == 4 && offset <= 0x7bc && offset.is_multiple_of(4),
            "invalid normalized PIF ROM backing offset/width",
        )?;
        if write {
            require(
                self.active.is_none(),
                "PIF write attempt inside instruction fetch",
            )?;
            require(
                self.writes.len() < queue::MAX_IDENTITIES as usize,
                "too many PIF write attempts",
            )?;
            self.writes.push(PifWriteAttempt {
                ordinal,
                pc,
                offset,
                value,
            });
        } else if let Some(s) = &mut self.active
            && (0x1fc00000..=0x1fcfffff).contains(&s.bus.0)
            && offset == s.bus.0 & 0x7fc
        {
            s.eligible += 1;
            s.read = Some(ReadWitness {
                ordinal,
                offset,
                value,
            });
        }
        Ok(())
    }
    fn legacy(&mut self, mut row: sp::Wire) -> Result<(), String> {
        use history::Record as R;
        if let Some(R::Header {
            format,
            policy,
            lifecycle_policy,
            ..
        }) = row.base_mut()
        {
            require(
                !self.header
                    && format == FORMAT
                    && policy == POLICY
                    && lifecycle_policy == history::LIFECYCLE_POLICY,
                "unsupported/repeated v4 header",
            )?;
            self.header = true;
            *format = sp::FORMAT.into();
            *policy = sp::POLICY.into();
        } else if let Some(R::End {
            record_count,
            fetch_count,
            ..
        }) = row.base_mut()
        {
            require(
                self.header
                    && *record_count == self.records
                    && *fetch_count == self.fetches
                    && self.active.is_none()
                    && self.pending.is_none()
                    && !self.copying,
                "incomplete v4 footer",
            )?;
            *record_count = self.projected;
            self.ended = true;
        } else {
            let (ordinal, context, pc, kind) =
                row.identity().ok_or("missing v4 legacy identity")?;
            if let Some(R::FetchBegin {
                vaddr,
                translated,
                bus,
                cached,
                ..
            }) = row.base()
            {
                require(
                    self.active.is_none() && self.pending.is_none() && context == ordinal,
                    "invalid v4 fetch begin",
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
                sp::Wire::Legacy(queue::Wire::Legacy(pi_history::Wire::Pi(
                    pi_history::PiRecord::PiDma { event: 1, .. },
                ))) => self.copying = true,
                sp::Wire::Legacy(queue::Wire::Legacy(pi_history::Wire::Pi(
                    pi_history::PiRecord::PiDma { event: 7, .. },
                ))) => self.copying = false,
                _ => {}
            }
            self.projected += 1;
            row.renumber(self.projected, self.active.as_ref().map_or(0, |s| s.mapped));
            if let Some(R::FetchEnd {
                vaddr,
                translated,
                bus,
                cached,
                value,
                ..
            }) = row.base()
            {
                let mut s = self.active.take().ok_or("v4 return without begin")?;
                require(
                    (s.vaddr, s.translated, s.bus, s.cached)
                        == (*vaddr, *translated, *bus, *cached),
                    "v4 return differs from begin",
                )?;
                s.value = Some(*value);
                self.pending = Some(s);
            }
            if let Some(R::Fetch {
                fetch_context,
                fetch_seq,
                word,
                physical,
                cached,
                ..
            }) = row.base_mut()
            {
                let s = self.pending.take().ok_or("v4 prologue without return")?;
                require(
                    *fetch_context == s.raw
                        && *fetch_seq == self.fetches
                        && s.value == Some(*word)
                        && (*physical, *cached) == (s.bus, s.cached),
                    "v4 prologue differs from fetch",
                )?;
                *fetch_context = s.mapped;
                let read = if !s.cached && s.eligible == 1 {
                    s.read
                } else {
                    None
                };
                for n in [self.fetches, pc.0, physical.0 as u64, *word as u64] {
                    self.ordered.update(n.to_be_bytes());
                }
                self.ordered.update([u8::from(read.is_some())]);
                if let Some(r) = read {
                    require(r.value == *word, "PIF bank read differs from fetched word")?;
                    let offset = r.offset as usize;
                    let equals = u32::from_be_bytes(
                        self.firmware[offset..offset + 4]
                            .try_into()
                            .map_err(|_| "invalid firmware Word")?,
                    ) == *word;
                    self.witnesses += 1;
                    self.matching += u64::from(equals);
                    for n in [r.offset as u64, r.ordinal] {
                        self.ordered.update(n.to_be_bytes());
                    }
                    self.ordered.update([u8::from(equals)]);
                    let sample = self
                        .samples
                        .entry((pc, *physical, *word, r.offset))
                        .or_insert(PifBackingFetchSample {
                            pc,
                            physical: *physical,
                            word: *word,
                            offset: r.offset,
                            matches_supplied_firmware: equals,
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
                require(self.ended, "v4 lacks complete footer")?;
                return Ok(false);
            }
            require(
                !self.ended && self.raw.ends_with(b"\n"),
                "truncated or trailing v4 record",
            )?;
            self.hash.update(&self.raw);
            match serde_json::from_slice::<Wire>(&self.raw).map_err(|e| e.to_string())? {
                Wire::Pif(r) => self.pif(r)?,
                Wire::Legacy(r) => {
                    self.legacy(r)?;
                    return Ok(true);
                }
            }
        }
    }
}
impl<H: BufRead> Read for Projection<'_, H> {
    fn read(&mut self, output: &mut [u8]) -> io::Result<usize> {
        let data = self.fill_buf()?;
        let count = data.len().min(output.len());
        output[..count].copy_from_slice(&data[..count]);
        self.consume(count);
        Ok(count)
    }
}
impl<H: BufRead> BufRead for Projection<'_, H> {
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
pub fn inspect_pif_boot_history<H: BufRead, F: BufRead + Seek>(
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<PifHistoryReport, String> {
    require(firmware.len() == 1984, "unsupported PIF firmware size")?;
    let mut stream = Projection::new(history, firmware);
    let projection = sp::inspect_sp_boot_history(&mut stream, fetched, rom, firmware)?;
    require(
        stream.ended && stream.fill_buf().map_err(|e| e.to_string())?.is_empty(),
        "incomplete v4 source",
    )?;
    Ok(PifHistoryReport {
        format: "plaid-observed-pif-backing-report-v0".into(),
        scope: "finite_actual_pif_bank_reads_and_write_attempts".into(),
        history_sha256: format!("{:x}", stream.hash.finalize()),
        projection,
        records: stream.records,
        v3_records: stream.projected,
        event_counts: stream.counts,
        fetches: stream.fetches,
        pif_backed_fetches: stream.witnesses,
        supplied_firmware_matching_fetches: stream.matching,
        other_or_unwitnessed_fetches: stream.fetches - stream.witnesses,
        samples: stream.samples.into_values().collect(),
        write_attempts: stream.writes,
        ordered_fetch_backing_sha256: format!("{:x}", stream.ordered.finalize()),
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}
pub fn verify_pif_boot_history_report<H: BufRead, F: BufRead + Seek>(
    report: &PifHistoryReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_pif_boot_history(history, fetched, rom, firmware)?,
        "PIF report differs from complete sources/inputs",
    )
}
