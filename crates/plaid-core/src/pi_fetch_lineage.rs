//! Byte chains in the observed chronology, with no complete mutation census.
use crate::{
    fetch, history,
    pi_history::{self, PiRecord},
    pi_queue_history::{self, PiQueueHistoryReport},
    program::*,
    rom::CanonicalRom,
    sp_history::{self, SpHistoryReport},
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    io::{BufRead, Seek, SeekFrom},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedPiByteChain {
    pub rom_offset: RomOffset,
    /// Ordinal of the successful scalar writer in the containing raw source.
    pub writer_ordinal: u64,
    pub transfer: u64,
    /// Independently witnessed SP installation, after the captured RAM read.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub sp_writer: Option<sp_history::CapturedSpByteWriter>,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedPiFetch {
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub cached: bool,
    pub fill_ordinal: Option<u64>,
    pub read_ordinal: Option<u64>,
    pub bytes: [Option<ObservedPiByteChain>; 4],
    /// Discrete sample endpoints, never a continuous interval or lifetime.
    pub first_fetch: u64,
    pub last_fetch: u64,
    pub observations: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ObservedRspInstruction {
    pub rsp_pc: u32,
    pub read_address: u32,
    pub fetch_offset: u32,
    pub word: u32,
    pub next_pc: u32,
    pub begin_halted: bool,
    pub halted: bool,
    pub bytes: [Option<ObservedPiByteChain>; 4],
    /// Discrete instruction occurrences, never a continuous executable lifetime.
    pub first_read_ordinal: u64,
    pub first_begin_ordinal: u64,
    pub first_end_ordinal: u64,
    pub last_begin_ordinal: u64,
    pub last_read_ordinal: u64,
    pub last_end_ordinal: u64,
    pub observations: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspInstructionLineage {
    pub instructions: u64,
    pub fully_attributed_instructions: u64,
    pub partially_attributed_instructions: u64,
    pub unattributed_instructions: u64,
    pub samples: Vec<ObservedRspInstruction>,
    pub ordered_instruction_chains_sha256: String,
}
#[derive(Serialize)]
struct RspOccurrence {
    read_ordinal: u64,
    begin_ordinal: u64,
    end_ordinal: u64,
    rsp_pc: u32,
    read_address: u32,
    fetch_offset: u32,
    word: u32,
    next_pc: u32,
    begin_halted: bool,
    halted: bool,
    bytes: [Option<ObservedPiByteChain>; 4],
}
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
struct RspSampleKey {
    rsp_pc: u32,
    read_address: u32,
    fetch_offset: u32,
    word: u32,
    next_pc: u32,
    begin_halted: bool,
    halted: bool,
    bytes: [Option<ObservedPiByteChain>; 4],
}
struct RspReadParents {
    address: u32,
    offset: u32,
    word: u32,
    bytes: [Option<ObservedPiByteChain>; 4],
}
struct PendingRspInstruction {
    read_ordinal: u64,
    begin_ordinal: u64,
    rsp_pc: u32,
    begin_halted: bool,
    read: RspReadParents,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PiFetchLineageReport<P = PiQueueHistoryReport> {
    pub format: String,
    pub scope: String,
    pub projection: P,
    pub fetches: u64,
    pub fully_attributed_fetches: u64,
    pub partially_attributed_fetches: u64,
    pub unattributed_fetches: u64,
    pub observed_rom_byte_fetches: u64,
    pub single_transfer_word_fetches: u64,
    pub contradicted_backing_bytes: u64,
    pub samples: Vec<ObservedPiFetch>,
    pub ordered_fetch_chains_sha256: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rsp_consumption: Option<RspInstructionLineage>,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

/// Byte-chain ordinals belong to the complete raw v3/v5 source, not its renumbered
/// v2 projection. SP observations are validated but supply no RAM byte origins.
pub type SpPiFetchLineageReport = PiFetchLineageReport<SpHistoryReport>;

#[derive(Clone)]
struct Resident {
    tag: u32,
    words: [u32; 8],
    origins: [Option<ObservedPiByteChain>; 32],
    fill: Option<u64>,
}
#[derive(Default)]
struct Access {
    reads: u64,
    read: Option<(u64, PhysicalAddr, u64)>,
    bus: Option<PhysicalAddr>,
    sp_origins: Option<[Option<ObservedPiByteChain>; 4]>,
}
struct StorageAttempt {
    ordinal: u64,
    pc: GuestVirtualAddr,
    value: u64,
    effect: Option<(PhysicalAddr, u64)>,
}
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
struct SampleKey {
    pc: GuestVirtualAddr,
    physical: PhysicalAddr,
    word: u32,
    cached: bool,
    fill: Option<u64>,
    read: Option<u64>,
    bytes: [Option<ObservedPiByteChain>; 4],
}
struct Lineage<'a> {
    source: &'a [u8],
    // Only touched RAM pages are allocated; the supported RAM domain is bounded.
    pages: BTreeMap<u32, Box<[Option<ObservedPiByteChain>; 4096]>>,
    resident: BTreeMap<u16, Resident>,
    burst: Option<(u64, u64, PhysicalAddr, [u32; 8])>,
    last_fill: Option<(u64, u16)>,
    active: Option<Access>,
    pending: Option<Access>,
    half: Option<(u64, u64, u32, u32, u16)>,
    buffer: [Option<u32>; 128],
    attempt_writer: Option<(u64, u32, u64)>,
    storage_attempt: Option<StorageAttempt>,
    sp: sp_history::WriterLineage,
    sp_origins: Vec<Option<ObservedPiByteChain>>,
    dma_links: BTreeMap<u64, u64>,
    dma_reads: BTreeMap<u64, Vec<Option<ObservedPiByteChain>>>,
    sp_attributed: bool,
    rsp_active: Option<PendingRspInstruction>,
    rsp_reads: BTreeMap<u64, RspReadParents>,
    rsp_samples: BTreeMap<RspSampleKey, ObservedRspInstruction>,
    rsp_digest: Sha256,
    rsp_instructions: u64,
    rsp_full: u64,
    rsp_partial: u64,
    samples: BTreeMap<SampleKey, ObservedPiFetch>,
    digest: Sha256,
    fetches: u64,
    full: u64,
    partial: u64,
    byte_fetches: u64,
    words: u64,
    contradictions: u64,
}
fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}
impl<'a> Lineage<'a> {
    fn new(source: &'a [u8]) -> Self {
        Self {
            source,
            pages: BTreeMap::new(),
            resident: BTreeMap::new(),
            burst: None,
            last_fill: None,
            active: None,
            pending: None,
            half: None,
            buffer: [None; 128],
            attempt_writer: None,
            storage_attempt: None,
            sp: sp_history::WriterLineage::new(),
            sp_origins: vec![None; 8192],
            dma_links: BTreeMap::new(),
            dma_reads: BTreeMap::new(),
            sp_attributed: false,
            rsp_active: None,
            rsp_reads: BTreeMap::new(),
            rsp_samples: BTreeMap::new(),
            rsp_digest: Sha256::new(),
            rsp_instructions: 0,
            rsp_full: 0,
            rsp_partial: 0,
            samples: BTreeMap::new(),
            digest: Sha256::new(),
            fetches: 0,
            full: 0,
            partial: 0,
            byte_fetches: 0,
            words: 0,
            contradictions: 0,
        }
    }
    fn set(&mut self, address: u32, origin: Option<ObservedPiByteChain>) -> Result<(), String> {
        require(address < 8_388_608, "lineage effect outside supported RAM")?;
        let page = address >> 12;
        if origin.is_some() || self.pages.contains_key(&page) {
            self.pages
                .entry(page)
                .or_insert_with(|| Box::new([None; 4096]))[(address & 4095) as usize] = origin;
        }
        Ok(())
    }
    fn read(
        &mut self,
        address: u32,
        values: &[u8],
    ) -> Result<Vec<Option<ObservedPiByteChain>>, String> {
        require(
            address
                .checked_add(values.len() as u32)
                .is_some_and(|end| end <= 8_388_608),
            "lineage read outside supported RAM",
        )?;
        let mut origins = Vec::with_capacity(values.len());
        for (n, value) in values.iter().enumerate() {
            let a = address + n as u32;
            let mut origin = self
                .pages
                .get(&(a >> 12))
                .and_then(|p| p[(a & 4095) as usize]);
            if let Some(o) = origin
                && self.source.get(o.rom_offset.0 as usize) != Some(value)
            {
                self.contradictions += 1;
                self.set(a, None)?;
                origin = None;
            }
            origins.push(origin);
        }
        Ok(origins)
    }
    fn pi(&mut self, record: &PiRecord) -> Result<(), String> {
        match *record {
            PiRecord::PiRomHalf {
                ordinal,
                transfer,
                block,
                offset,
                value,
                ..
            } => {
                self.half = Some((ordinal, transfer, block, offset, value));
            }
            PiRecord::PiDma {
                ordinal,
                transfer,
                block,
                event,
                lane,
                pbus,
                dram,
                value,
                pc,
                ..
            } => match event {
                2 => self.buffer.fill(None),
                3 => {
                    require(
                        lane < 128 && lane % 2 == 0,
                        "lineage buffer lane outside bound",
                    )?;
                    let offset = self
                        .half
                        .take()
                        .filter(|h| {
                            h.0.checked_add(1) == Some(ordinal)
                                && h.1 == transfer
                                && h.2 == block
                                && h.3.checked_add(0x10000000) == Some(pbus.0)
                                && u32::from(h.4) == value
                        })
                        .map(|h| h.3);
                    self.buffer[lane as usize] = offset;
                    self.buffer[lane as usize + 1] = offset.and_then(|o| o.checked_add(1));
                }
                4 => {
                    self.attempt_writer = None;
                    self.storage_attempt = Some(StorageAttempt {
                        ordinal,
                        pc,
                        value: u64::from(value),
                        effect: None,
                    });
                }
                5 => {
                    // Validated PI copies forbid intervening fetches; select the
                    // completed physical sink only after its attempt returns.
                    let storage = self.storage_attempt.take().and_then(|a| a.effect);
                    let scalar = self.attempt_writer.take();
                    if let Some((address, writer)) = storage {
                        require(
                            writer.checked_add(if scalar.is_some() { 2 } else { 1 })
                                == Some(ordinal)
                                && (scalar.is_none() || address == dram),
                            "PI storage effect/return or wrapper sink mismatch",
                        )?;
                    }
                    let origin = self.buffer.get(lane as usize).copied().flatten();
                    if let Some((id, l, writer)) = scalar {
                        require(
                            id == transfer && l == lane,
                            "lineage PI scalar/return mismatch",
                        )?;
                        let origin = origin.map(|offset| ObservedPiByteChain {
                            rom_offset: RomOffset(u64::from(offset)),
                            writer_ordinal: writer,
                            transfer,
                            sp_writer: None,
                        });
                        self.set(dram.0, origin)?;
                    } else if let Some((address, writer)) = storage {
                        self.set(
                            address.0,
                            origin.map(|offset| ObservedPiByteChain {
                                rom_offset: RomOffset(u64::from(offset)),
                                writer_ordinal: writer,
                                transfer,
                                sp_writer: None,
                            }),
                        )?;
                    }
                }
                _ => {}
            },
        }
        Ok(())
    }
    fn access(&mut self, record: &history::Record) -> Result<(), String> {
        use history::Record as R;
        match record {
            R::Scalar {
                ordinal,
                write,
                aligned_address,
                address,
                bytes,
                value,
                device,
                ..
            } => {
                require(
                    matches!(bytes, 1 | 2 | 4 | 8),
                    "lineage scalar width outside supported bound",
                )?;
                if !write && *device == 4 {
                    let payload = value.to_be_bytes();
                    let origins = if !write
                        && *device == 4
                        && address == aligned_address
                        && aligned_address
                            .0
                            .checked_add(*bytes)
                            .is_some_and(|end| end <= 8_388_608)
                    {
                        self.read(aligned_address.0, &payload[8 - *bytes as usize..])?
                    } else {
                        vec![None; *bytes as usize]
                    };
                    if self.dma_reads.contains_key(ordinal) {
                        self.dma_reads.insert(*ordinal, origins);
                    }
                }
                if *write {
                    for n in 0..*bytes {
                        self.set(
                            aligned_address
                                .0
                                .checked_add(n)
                                .ok_or("lineage address overflow")?,
                            None,
                        )?;
                    }
                } else if *bytes == 4
                    && *device == 3
                    && let Some(a) = &mut self.active
                {
                    a.reads += 1;
                    a.read = Some((*ordinal, *address, *value));
                }
            }
            R::Burst {
                ordinal,
                context,
                write,
                address,
                bytes,
                device,
                words,
                ..
            } => {
                require(
                    matches!(bytes, 16 | 32) && words.len() == (*bytes / 4) as usize,
                    "lineage burst width mismatch",
                )?;
                let values: Vec<_> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
                if *write {
                    for n in 0..*bytes {
                        self.set(
                            address.0.checked_add(n).ok_or("lineage burst overflow")?,
                            None,
                        )?;
                    }
                } else if *bytes == 32 && *device == 1 {
                    self.read(address.0, &values)?;
                    self.burst = Some((
                        *ordinal,
                        *context,
                        *address,
                        words
                            .as_slice()
                            .try_into()
                            .map_err(|_| "lineage fill payload width")?,
                    ));
                }
            }
            R::Fill {
                ordinal,
                context,
                slot,
                physical,
                index,
                words,
                ..
            } => {
                require(*slot < 512, "lineage cache slot outside bound")?;
                let address = (physical.0 & !0xfff) | u32::from(*index);
                let joined = self.burst.as_ref().is_some_and(|b| {
                    b.0.checked_add(1) == Some(*ordinal)
                        && b.1 == *context
                        && b.2.0 == address
                        && b.3 == *words
                });
                let origins = if joined {
                    let values: Vec<_> = words.iter().flat_map(|w| w.to_be_bytes()).collect();
                    self.read(address, &values)?
                        .try_into()
                        .map_err(|_| "lineage resident width")?
                } else {
                    [None; 32]
                };
                self.resident.insert(
                    *slot,
                    Resident {
                        tag: (physical.0 & !0xfff) | 1,
                        words: *words,
                        origins,
                        fill: joined.then_some(*ordinal),
                    },
                );
                self.last_fill = Some((*ordinal, *slot));
            }
            R::CacheOperation {
                ordinal,
                operation,
                vaddr,
                before_tag,
                after_tag,
                before_words,
                after_words,
                ..
            } => {
                let slot = ((vaddr.0 >> 5) & 511) as u16;
                let keep = self.resident.get(&slot).is_some_and(|r| {
                    let completed_fill = *operation == 20
                        && ordinal
                            .checked_sub(1)
                            .is_some_and(|previous| self.last_fill == Some((previous, slot)));
                    r.tag == *after_tag
                        && r.words == *after_words
                        && (completed_fill
                            || (*before_tag == *after_tag && *before_words == *after_words))
                });
                if !keep {
                    self.resident.remove(&slot);
                }
            }
            R::FetchBegin { bus, .. } => {
                self.active = Some(Access {
                    bus: Some(*bus),
                    ..Access::default()
                })
            }
            R::FetchEnd { .. } => self.pending = self.active.take(),
            _ => {}
        }
        Ok(())
    }
    fn sp_parents(
        &mut self,
        bank: u32,
        offset: u32,
        word: u32,
    ) -> [Option<ObservedPiByteChain>; 4] {
        let writers = self.sp.read(bank, offset, word);
        std::array::from_fn(|n| {
            self.sp_origins[bank as usize * 4096 + offset as usize + n]
                .filter(|parent| parent.sp_writer == writers[n] && writers[n].is_some())
        })
    }
    fn sp(&mut self, record: &sp_history::SpRecord) -> Result<(), String> {
        use sp_history::{CapturedSpByteWriter, CapturedSpWriterKind, SpRecord};
        match *record {
            // Operand roots cut register parents in the shared projection;
            // they never change already frozen executable-byte reads.
            SpRecord::RspOperandRoot { .. } => {}
            SpRecord::ImemStorageEffect { offset, bytes, .. } => {
                self.sp.cut(1, offset, bytes);
            }
            SpRecord::RspImemRead {
                ordinal,
                address,
                offset,
                word,
                ..
            } => {
                if self.rsp_active.is_none() {
                    self.rsp_reads.clear();
                }
                let bytes = self.sp_parents(1, offset, word);
                self.rsp_reads.insert(
                    ordinal,
                    RspReadParents {
                        address,
                        offset,
                        word,
                        bytes,
                    },
                );
            }
            SpRecord::RspInstruction {
                ordinal,
                begin,
                rsp_pc,
                read_ordinal,
                word,
                next_pc,
                halted,
                ..
            } => {
                if begin {
                    let read = self
                        .rsp_reads
                        .remove(&read_ordinal)
                        .ok_or("RSP consumption lacks its actual IMEM read")?;
                    require(read.word == word, "RSP fetched word differs from its read")?;
                    self.rsp_active = Some(PendingRspInstruction {
                        read_ordinal,
                        begin_ordinal: ordinal,
                        rsp_pc,
                        begin_halted: halted,
                        read,
                    });
                } else {
                    let pending = self
                        .rsp_active
                        .take()
                        .ok_or("RSP consumption lacks its captured begin")?;
                    require(
                        (pending.rsp_pc, pending.read.word, pending.read_ordinal)
                            == (rsp_pc, word, read_ordinal),
                        "RSP consumption changed during instruction",
                    )?;
                    let begin_ordinal = pending.begin_ordinal;
                    let bytes = pending.read.bytes;
                    let read_address = pending.read.address;
                    let fetch_offset = pending.read.offset;
                    let begin_halted = pending.begin_halted;
                    let known = bytes.iter().flatten().count();
                    self.rsp_instructions += 1;
                    self.rsp_full += u64::from(known == 4);
                    self.rsp_partial += u64::from(known > 0 && known < 4);
                    let occurrence = RspOccurrence {
                        read_ordinal,
                        begin_ordinal,
                        end_ordinal: ordinal,
                        rsp_pc,
                        read_address,
                        fetch_offset,
                        word,
                        next_pc,
                        begin_halted,
                        halted,
                        bytes,
                    };
                    self.rsp_digest
                        .update(serde_json::to_vec(&occurrence).map_err(|e| e.to_string())?);
                    self.rsp_digest.update(b"\n");
                    let sample = self
                        .rsp_samples
                        .entry(RspSampleKey {
                            rsp_pc,
                            read_address,
                            fetch_offset,
                            word,
                            next_pc,
                            begin_halted,
                            halted,
                            bytes,
                        })
                        .or_insert(ObservedRspInstruction {
                            rsp_pc,
                            read_address,
                            fetch_offset,
                            word,
                            next_pc,
                            begin_halted,
                            halted,
                            bytes,
                            first_read_ordinal: read_ordinal,
                            first_begin_ordinal: begin_ordinal,
                            first_end_ordinal: ordinal,
                            last_begin_ordinal: begin_ordinal,
                            last_read_ordinal: read_ordinal,
                            last_end_ordinal: ordinal,
                            observations: 0,
                        });
                    sample.last_begin_ordinal = begin_ordinal;
                    sample.last_read_ordinal = read_ordinal;
                    sample.last_end_ordinal = ordinal;
                    sample.observations += 1;
                }
            }
            SpRecord::RspDmemEffect { offset, bytes, .. } => {
                self.sp.cut(0, offset, bytes);
            }
            SpRecord::SpWord {
                ordinal,
                write,
                address,
                bank,
                offset,
                value,
                cpu,
                ..
            } => {
                if write {
                    self.sp.write(
                        bank,
                        offset,
                        &value.to_be_bytes(),
                        ordinal,
                        CapturedSpWriterKind::WordSink { cpu },
                    );
                } else {
                    let parents = self.sp_parents(bank, offset, value);
                    if let Some(active) = &mut self.active
                        && cpu
                        && active.bus == Some(address)
                    {
                        active.reads += 1;
                        active.read = Some((ordinal, address, u64::from(value)));
                        active.sp_origins = Some(parents);
                    }
                }
            }
            SpRecord::SpDmaStore {
                ordinal,
                dram,
                bank,
                offset,
                bytes,
                value,
                ..
            } => {
                let read_ordinal = self.dma_links.remove(&ordinal);
                let origins = read_ordinal.and_then(|r| self.dma_reads.remove(&r));
                let payload = value.to_be_bytes();
                let kind = CapturedSpWriterKind::DmaSink { dram, read_ordinal };
                self.sp
                    .write(bank, offset, &payload[8 - bytes as usize..], ordinal, kind);
                for n in 0..bytes as usize {
                    self.sp_origins[bank as usize * 4096 + offset as usize + n] = origins
                        .as_ref()
                        .and_then(|o| o.get(n).copied().flatten())
                        .map(|mut parent| {
                            parent.sp_writer = Some(CapturedSpByteWriter {
                                write_ordinal: ordinal,
                                byte_index: n as u8,
                                kind,
                            });
                            parent
                        });
                }
            }
        }
        Ok(())
    }
    fn storage(&mut self, record: &sp_history::StorageRecord) -> Result<(), String> {
        record.validate()?;
        let sp_history::StorageRecord::StorageEffect {
            ordinal,
            context,
            pc,
            kind,
            address,
            bytes,
            value,
        } = record;
        if let Some(attempt) = &mut self.storage_attempt {
            require(
                *kind == 0
                    && *bytes == 1
                    && *context == 0
                    && *pc == attempt.pc
                    && *value == attempt.value
                    && attempt.ordinal.checked_add(1) == Some(*ordinal)
                    && attempt.effect.is_none()
                    && self.attempt_writer.is_none(),
                "PI byte attempt lacks one immediate matching storage primitive",
            )?;
            attempt.effect = Some((*address, *ordinal));
        }
        if *kind == 0 {
            for n in 0..*bytes {
                self.set(address.0 + n, None)?;
            }
        } else {
            self.pages.clear();
        }
        // Ordinary backing mutations never refresh or retire surviving I-cache
        // generations. Restore/retirement reject before this state can change.
        Ok(())
    }
    fn fetched(&mut self, record: &history::Record, paired: fetch::Record) -> Result<(), String> {
        let history::Record::Fetch {
            fetch_seq,
            pc,
            word,
            physical,
            cached,
            ..
        } = record
        else {
            return Err("lineage requires fetch row".into());
        };
        let fetch::Record::Fetch {
            seq,
            pc: paired_pc,
            word: paired_word,
            physical: paired_pa,
            cached: paired_cached,
            cache_line,
            ..
        } = paired
        else {
            return Err("lineage lacks paired fetch".into());
        };
        require(
            (*fetch_seq, *pc, *word, Some(*physical), Some(*cached))
                == (seq, paired_pc, paired_word, paired_pa, paired_cached)
                && seq == self.fetches
                && self.fetches < history::MAX_BUDGET,
            "lineage paired fetch changed",
        )?;
        let access = self
            .pending
            .take()
            .ok_or("lineage fetch without completed access")?;
        let (mut bytes, mut fill, mut read) = ([None; 4], None, None);
        if *cached {
            if let Some(line) = cache_line
                && let Some(r) = self.resident.get(&line.slot)
            {
                if r.tag == line.tag_key && r.words == line.words {
                    let lane = ((physical.0 >> 2) & 7) as usize;
                    bytes.copy_from_slice(&r.origins[lane * 4..lane * 4 + 4]);
                    fill = r.fill;
                } else {
                    self.resident.remove(&line.slot);
                }
            }
        } else if access.reads == 1
            && let Some((ordinal, address, value)) = access.read
            && address == *physical
            && value == u64::from(*word)
        {
            bytes = if let Some(origins) = access.sp_origins {
                origins
            } else {
                self.read(physical.0, &word.to_be_bytes())?
                    .try_into()
                    .map_err(|_| "lineage fetched width")?
            };
            // Unused SP paths retain the legacy PI-only report and digest.
            if access.sp_origins.is_none() || bytes.iter().any(Option::is_some) {
                read = Some(ordinal);
            }
        }
        let known = bytes.iter().flatten().count() as u64;
        self.sp_attributed |= bytes.iter().flatten().any(|b| b.sp_writer.is_some());
        self.byte_fetches += known;
        self.full += u64::from(known == 4);
        self.partial += u64::from(known > 0 && known < 4);
        if let Some(first) = bytes[0]
            && bytes.iter().enumerate().all(|(n, b)| {
                b.is_some_and(|b| {
                    b.transfer == first.transfer
                        && Some(b.rom_offset.0) == first.rom_offset.0.checked_add(n as u64)
                })
            })
        {
            self.words += 1;
        }
        for value in [
            seq,
            pc.0,
            u64::from(physical.0),
            u64::from(*word),
            u64::from(*cached),
            fill.unwrap_or(u64::MAX),
            read.unwrap_or(u64::MAX),
        ] {
            self.digest.update(value.to_be_bytes());
        }
        for byte in bytes {
            self.digest.update([u8::from(byte.is_some())]);
            if let Some(o) = byte {
                self.digest.update(o.rom_offset.0.to_be_bytes());
                self.digest.update(o.writer_ordinal.to_be_bytes());
                self.digest.update(o.transfer.to_be_bytes());
                if let Some(writer) = o.sp_writer {
                    let encoded = serde_json::to_vec(&writer).map_err(|e| e.to_string())?;
                    self.digest.update([0xff]);
                    self.digest.update((encoded.len() as u32).to_be_bytes());
                    self.digest.update(encoded);
                }
            }
        }
        if known > 0 {
            let key = SampleKey {
                pc: *pc,
                physical: *physical,
                word: *word,
                cached: *cached,
                fill,
                read,
                bytes,
            };
            let sample = self.samples.entry(key).or_insert(ObservedPiFetch {
                pc: *pc,
                physical: *physical,
                word: *word,
                cached: *cached,
                fill_ordinal: fill,
                read_ordinal: read,
                bytes,
                first_fetch: seq,
                last_fetch: seq,
                observations: 0,
            });
            sample.last_fetch = seq;
            sample.observations += 1;
        }
        self.fetches += 1;
        Ok(())
    }
}
fn paired<F: BufRead>(
    input: &mut F,
    raw: &mut Vec<u8>,
    hash: &mut Sha256,
) -> Result<fetch::Record, String> {
    require(fetch::line(input, raw)?, "lineage paired source truncated")?;
    hash.update(&*raw);
    serde_json::from_slice(raw).map_err(|e| e.to_string())
}

/// Revalidate complete sources first, then replay them with a second digest.
/// The resulting byte chains describe observed records, never unseen mutation.
pub fn inspect_pi_fetch_lineage<H: BufRead + Seek, F: BufRead + Seek>(
    mut history: H,
    mut fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<PiFetchLineageReport, String> {
    require(
        history.stream_position().map_err(|e| e.to_string())? == 0,
        "lineage history must begin at zero",
    )?;
    let projection =
        pi_queue_history::inspect_pi_queue_boot_history(&mut history, &mut fetched, rom, firmware)?;
    let hashes = (
        projection.history_sha256.clone(),
        projection.projection.projection.fetch_sha256.clone(),
    );
    replay_lineage(
        history,
        fetched,
        rom,
        projection,
        (&hashes.0, &hashes.1),
        false,
        BTreeMap::new(),
    )
}

/// Compose the existing PI writer/fill/fetch consumer with complete v3/v5 source
/// validation. Require independent receipts and retain original event ordinals.
/// Compatible finite chains never certify a complete mutation census/lifetime.
pub fn inspect_sp_pi_fetch_lineage<H: BufRead + Seek, F: BufRead + Seek>(
    mut history: H,
    mut fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
    expected_history_sha256: &str,
    expected_fetch_sha256: &str,
) -> Result<SpPiFetchLineageReport, String> {
    require(
        history.stream_position().map_err(|e| e.to_string())? == 0,
        "lineage history must begin at zero",
    )?;
    let projection =
        sp_history::inspect_sp_boot_history(&mut history, &mut fetched, rom, firmware)?;
    require(
        projection.history_sha256 == expected_history_sha256
            && projection.projection.projection.projection.fetch_sha256 == expected_fetch_sha256,
        "SP/PI lineage source receipt mismatch",
    )?;
    let dma_links = projection
        .dma_store_receipts
        .iter()
        .filter_map(|receipt| {
            receipt
                .read_ordinal
                .map(|read| (receipt.write_ordinal, read))
        })
        .collect();
    replay_lineage(
        history,
        fetched,
        rom,
        projection,
        (expected_history_sha256, expected_fetch_sha256),
        true,
        dma_links,
    )
}

fn replay_lineage<H: BufRead + Seek, F: BufRead + Seek, P>(
    mut history: H,
    mut fetched: F,
    rom: &CanonicalRom,
    projection: P,
    source_hashes: (&str, &str),
    sp_clock: bool,
    dma_links: BTreeMap<u64, u64>,
) -> Result<PiFetchLineageReport<P>, String> {
    history
        .seek(SeekFrom::Start(0))
        .map_err(|e| e.to_string())?;
    fetched
        .seek(SeekFrom::Start(0))
        .map_err(|e| e.to_string())?;
    let mut ledger = Lineage::new(rom.bytes());
    ledger.dma_links = dma_links;
    for read in ledger.dma_links.values() {
        ledger.dma_reads.insert(*read, Vec::new());
    }
    let (mut raw, mut fetch_raw) = (Vec::new(), Vec::new());
    let (mut hash, mut fetch_hash) = (Sha256::new(), Sha256::new());
    require(
        matches!(
            paired(&mut fetched, &mut fetch_raw, &mut fetch_hash)?,
            fetch::Record::Header { .. }
        ),
        "missing lineage paired header",
    )?;
    let mut lines = 0;
    while fetch::line(&mut history, &mut raw)? {
        lines += 1;
        require(
            lines <= history::MAX_RECORDS + 2,
            "lineage replay exceeds record bound",
        )?;
        hash.update(&raw);
        let record = if sp_clock {
            match serde_json::from_slice::<sp_history::Wire>(&raw).map_err(|e| e.to_string())? {
                sp_history::Wire::Legacy(r) => Some(r),
                sp_history::Wire::Sp(s) => {
                    ledger.sp(&s)?;
                    None
                }
                sp_history::Wire::Storage(s) => {
                    ledger.storage(&s)?;
                    None
                }
            }
        } else {
            Some(
                serde_json::from_slice::<pi_queue_history::Wire>(&raw)
                    .map_err(|e| e.to_string())?,
            )
        };
        if let Some(pi_queue_history::Wire::Legacy(record)) = record {
            match record {
                pi_history::Wire::Pi(p) => ledger.pi(&p)?,
                pi_history::Wire::Scalar(s) => {
                    ledger.access(&s.access())?;
                    let (transfer, _, lane) = s.lane_identity();
                    ledger.attempt_writer = Some((transfer, lane, record_identity(&s.access())?));
                }
                pi_history::Wire::Base(r) => {
                    ledger.access(&r)?;
                    if matches!(r, history::Record::Fetch { .. }) {
                        let p = paired(&mut fetched, &mut fetch_raw, &mut fetch_hash)?;
                        ledger.fetched(&r, p)?;
                    }
                }
            }
        }
    }
    require(
        matches!(
            paired(&mut fetched, &mut fetch_raw, &mut fetch_hash)?,
            fetch::Record::End { .. }
        ) && !fetch::line(&mut fetched, &mut fetch_raw)?,
        "lineage paired footer/EOF changed",
    )?;
    require(
        format!("{:x}", hash.finalize()) == source_hashes.0
            && format!("{:x}", fetch_hash.finalize()) == source_hashes.1,
        "complete source changed between validation and lineage replay",
    )?;
    Ok(PiFetchLineageReport {
        format: if ledger.rsp_instructions > 0 {
            "plaid-sp-pi-fetch-lineage-report-v2"
        } else if ledger.sp_attributed {
            "plaid-sp-pi-fetch-lineage-report-v1"
        } else if sp_clock {
            "plaid-sp-pi-fetch-lineage-report-v0"
        } else {
            "plaid-pi-fetch-lineage-report-v0"
        }
        .into(),
        scope: if ledger.rsp_instructions > 0 {
            "finite_observed_pi_ram_sp_cpu_rsp_consumption_without_mutation_census"
        } else if ledger.sp_attributed {
            "finite_observed_pi_ram_sp_dma_byte_chains_without_mutation_census"
        } else if sp_clock {
            "finite_observed_pi_byte_chains_on_raw_sp_clock_without_mutation_census"
        } else {
            "finite_observed_pi_byte_chains_without_mutation_census"
        }
        .into(),
        projection,
        fetches: ledger.fetches,
        fully_attributed_fetches: ledger.full,
        partially_attributed_fetches: ledger.partial,
        unattributed_fetches: ledger.fetches - ledger.full - ledger.partial,
        observed_rom_byte_fetches: ledger.byte_fetches,
        single_transfer_word_fetches: ledger.words,
        contradicted_backing_bytes: ledger.contradictions,
        samples: ledger.samples.into_values().collect(),
        ordered_fetch_chains_sha256: format!("{:x}", ledger.digest.finalize()),
        rsp_consumption: (ledger.rsp_instructions > 0).then(|| RspInstructionLineage {
            instructions: ledger.rsp_instructions,
            fully_attributed_instructions: ledger.rsp_full,
            partially_attributed_instructions: ledger.rsp_partial,
            unattributed_instructions: ledger.rsp_instructions
                - ledger.rsp_full
                - ledger.rsp_partial,
            samples: ledger.rsp_samples.into_values().collect(),
            ordered_instruction_chains_sha256: format!("{:x}", ledger.rsp_digest.finalize()),
        }),
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}
fn record_identity(record: &history::Record) -> Result<u64, String> {
    record
        .identity()
        .map(|r| r.0)
        .ok_or_else(|| "missing lineage writer identity".into())
}
pub fn verify_sp_pi_fetch_lineage_report<H: BufRead + Seek, F: BufRead + Seek>(
    report: &SpPiFetchLineageReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
    expected_history_sha256: &str,
    expected_fetch_sha256: &str,
) -> Result<(), String> {
    require(
        *report
            == inspect_sp_pi_fetch_lineage(
                history,
                fetched,
                rom,
                firmware,
                expected_history_sha256,
                expected_fetch_sha256,
            )?,
        "SP/PI lineage report does not match complete sources/inputs/receipts",
    )
}
pub fn verify_pi_fetch_lineage_report<H: BufRead + Seek, F: BufRead + Seek>(
    report: &PiFetchLineageReport,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *report == inspect_pi_fetch_lineage(history, fetched, rom, firmware)?,
        "lineage report does not match complete sources/inputs",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    const PA: u32 = 0x1000;
    const PC: GuestVirtualAddr = GuestVirtualAddr(0xffffffff80001000);
    fn seed(ledger: &mut Lineage<'_>, transfer: u64, offset: u64) {
        for n in 0..32 {
            ledger
                .set(
                    PA + n,
                    Some(ObservedPiByteChain {
                        rom_offset: RomOffset(offset + u64::from(n)),
                        writer_ordinal: transfer * 100 + u64::from(n),
                        transfer,
                        sp_writer: None,
                    }),
                )
                .unwrap();
        }
    }
    fn fill(ledger: &mut Lineage<'_>, ordinal: u64, value: u32, witnessed: bool) {
        if witnessed {
            ledger
                .access(&history::Record::Burst {
                    ordinal: ordinal - 1,
                    context: 1,
                    pc: PC,
                    write: false,
                    address: PhysicalAddr(PA),
                    bytes: 32,
                    device: 1,
                    words: vec![value; 8],
                })
                .unwrap();
        }
        ledger
            .access(&history::Record::Fill {
                ordinal,
                context: 1,
                pc: PC,
                slot: 128,
                physical: PhysicalAddr(PA),
                index: 0,
                words: [value; 8],
            })
            .unwrap();
    }
    fn sample(ledger: &mut Lineage<'_>, value: u32, cached: bool) {
        let pc = if cached {
            PC
        } else {
            GuestVirtualAddr(0xffffffffa0001000)
        };
        let seq = ledger.fetches;
        ledger
            .access(&history::Record::FetchBegin {
                ordinal: 200 + seq * 4,
                context: 1,
                pc,
                vaddr: pc,
                translated: PhysicalAddr(PA),
                bus: PhysicalAddr(PA),
                cached,
                value: 0,
            })
            .unwrap();
        if !cached {
            ledger
                .access(&history::Record::Scalar {
                    ordinal: 201 + seq * 4,
                    context: 1,
                    pc,
                    write: false,
                    address: PhysicalAddr(PA),
                    aligned_address: PhysicalAddr(PA),
                    bytes: 4,
                    device: 3,
                    value: u64::from(value),
                })
                .unwrap();
        }
        ledger
            .access(&history::Record::FetchEnd {
                ordinal: 202 + seq * 4,
                context: 1,
                pc,
                vaddr: pc,
                translated: PhysicalAddr(PA),
                bus: PhysicalAddr(PA),
                cached,
                value,
            })
            .unwrap();
        let record = history::Record::Fetch {
            ordinal: 203 + seq * 4,
            context: 0,
            pc,
            fetch_context: 1,
            fetch_seq: seq,
            word: value,
            physical: PhysicalAddr(PA),
            cached,
        };
        let paired = fetch::Record::Fetch {
            seq,
            pc,
            word: value,
            delay_slot: false,
            physical: Some(PhysicalAddr(PA)),
            cached: Some(cached),
            source: Some(FetchSource::Unknown {}),
            cache_line: cached.then_some(FetchCacheLine {
                slot: 128,
                index: 0,
                tag_key: PA | 1,
                words: [value; 8],
            }),
        };
        ledger.fetched(&record, paired).unwrap();
    }
    fn cache(ledger: &mut Lineage<'_>, ordinal: u64, op: u32, before: u32, after: u32, value: u32) {
        ledger
            .access(&history::Record::CacheOperation {
                ordinal,
                context: 0,
                pc: PC,
                operation: op,
                vaddr: PC,
                physical: PhysicalAddr(PA),
                before_tag: before,
                after_tag: after,
                before_words: [value; 8],
                after_words: [value; 8],
            })
            .unwrap();
    }
    #[test]
    fn resident_origins_survive_equal_and_changed_backing_reload() {
        let mut source = vec![0x11; 64];
        source.extend([0x33; 32]);
        let mut ledger = Lineage::new(&source);
        seed(&mut ledger, 1, 0);
        fill(&mut ledger, 100, 0x11111111, true);
        sample(&mut ledger, 0x11111111, true);
        seed(&mut ledger, 2, 32);
        sample(&mut ledger, 0x11111111, true);
        sample(&mut ledger, 0x11111111, false);
        seed(&mut ledger, 3, 64);
        sample(&mut ledger, 0x11111111, true);
        sample(&mut ledger, 0x33333333, false);
        let samples: Vec<_> = ledger.samples.values().collect();
        let resident = samples.iter().find(|s| s.cached).unwrap();
        assert_eq!(
            (
                resident.first_fetch,
                resident.last_fetch,
                resident.observations,
                resident.fill_ordinal
            ),
            (0, 3, 3, Some(100))
        );
        assert!(resident.bytes.iter().flatten().all(|b| b.transfer == 1));
        assert!(
            samples
                .iter()
                .any(|s| !s.cached && s.bytes[0].unwrap().transfer == 2)
        );
        assert!(
            samples
                .iter()
                .any(|s| !s.cached && s.bytes[0].unwrap().transfer == 3)
        );
        assert_eq!((ledger.full, ledger.byte_fetches, ledger.words), (5, 20, 5));
    }
    #[test]
    fn equal_scalar_and_burst_writes_kill_backing_chains_without_rewriting_residency() {
        let source = [0x11; 64];
        let mut ledger = Lineage::new(&source);
        seed(&mut ledger, 1, 0);
        fill(&mut ledger, 100, 0x11111111, true);
        // Even an equal successful CPU byte write removes its prior PI chain.
        ledger
            .access(&history::Record::Scalar {
                ordinal: 101,
                context: 0,
                pc: PC,
                write: true,
                address: PhysicalAddr(PA + 3),
                aligned_address: PhysicalAddr(PA + 3),
                bytes: 1,
                device: 3,
                value: 0x11,
            })
            .unwrap();
        sample(&mut ledger, 0x11111111, false);
        sample(&mut ledger, 0x11111111, true);
        let partial = ledger.samples.values().find(|s| !s.cached).unwrap();
        assert!(partial.bytes[..3].iter().all(Option::is_some));
        assert!(partial.bytes[3].is_none());
        assert_eq!(ledger.partial, 1);
        // Whole outgoing D-cache payload replaces clean lanes too.
        ledger
            .access(&history::Record::Burst {
                ordinal: 120,
                context: 0,
                pc: PC,
                write: true,
                address: PhysicalAddr(PA),
                bytes: 16,
                device: 2,
                words: vec![0x11111111; 4],
            })
            .unwrap();
        sample(&mut ledger, 0x11111111, false);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!((ledger.full, ledger.partial, ledger.fetches), (2, 1, 4));
        assert_eq!(
            ledger
                .samples
                .values()
                .find(|s| s.cached)
                .unwrap()
                .observations,
            2
        );
    }
    #[test]
    fn retag_invalidation_unknown_fills_and_contradictions_do_not_borrow_equal_origins() {
        let source = [0x11; 64];
        let mut ledger = Lineage::new(&source);
        seed(&mut ledger, 1, 0);
        fill(&mut ledger, 100, 0x11111111, true);
        // Miss/unchanged completion preserves the complete resident tuple.
        cache(&mut ledger, 101, 16, PA | 1, PA | 1, 0x11111111);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!(ledger.full, 1);
        cache(&mut ledger, 110, 8, PA | 1, 0x2001, 0x11111111);
        cache(&mut ledger, 111, 8, 0x2001, PA | 1, 0x11111111);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!(ledger.full, 1);
        fill(&mut ledger, 120, 0x11111111, false);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!(ledger.full, 1);
        fill(&mut ledger, 130, 0x11111111, true);
        cache(&mut ledger, 131, 20, 0, PA | 1, 0x11111111);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!(ledger.full, 2);
        cache(&mut ledger, 140, 16, PA | 1, PA, 0x11111111);
        sample(&mut ledger, 0x11111111, true);
        assert_eq!(ledger.full, 2);
        // An unexplained different observed read becomes unknown; it is not forged ROM.
        sample(&mut ledger, 0x33333333, false);
        assert_eq!(ledger.contradictions, 4);
        sample(&mut ledger, 0x11111111, false);
        assert_eq!(ledger.full, 2);
    }
}
