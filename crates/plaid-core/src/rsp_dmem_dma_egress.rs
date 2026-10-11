//! Bounded source-bound replay of RSP DMEM writer ancestry through completed SP DMA egress.
//!
//! The completed DMA descriptor selects the source bytes before payload comparison.
//! Same-value writes therefore remain distinct writer generations. Missing or
//! unclassified DMEM ancestry stays unknown. This module does not certify a
//! complete mutation census, SP request lifetime, hardware timing, RDRAM lifetime,
//! executable consumption, or native completeness.

use crate::{
    history,
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-rsp-dmem-dma-egress-v0";
const DMEM_BYTES: u32 = 4096;
const SP_BANK_BIT: u32 = 0x1000;
const MAX_SP_PHYSICAL: u32 = 0x0100_0000;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DmemByteOrigin {
    /// No authenticated writer for this byte has appeared in this bounded source.
    Unobserved,
    Rsp {
        writer_generation: u64,
        context: u64,
        pc: GuestVirtualAddr,
        write_ordinal: u64,
    },
    /// A separately authenticated non-RSP writer. The label is an evidence identity,
    /// not proof of ultimate byte origin.
    External {
        writer_generation: u64,
        source_id: String,
        write_ordinal: u64,
    },
    /// A concrete mutation was observed but its producer ancestry is not certified.
    Unknown { cut_ordinal: u64 },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemEgressByte {
    pub source_offset: u32,
    pub value: u8,
    pub origin: DmemByteOrigin,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DmemDmaEgressReceipt {
    pub write_ordinal: u64,
    pub origin_pc: GuestVirtualAddr,
    pub dram: PhysicalAddr,
    pub dma_pbus: u32,
    pub dma_dram: PhysicalAddr,
    pub dma_count: u32,
    pub dma_skip: u32,
    pub source_offset: u32,
    pub value: u32,
    pub payload_fully_replayed: bool,
    pub lineage_fully_known: bool,
    pub bytes: [DmemEgressByte; 4],
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RspDmemDmaEgressReport {
    pub format: String,
    pub source_sha256: String,
    pub events: usize,
    pub rsp_writes: usize,
    pub external_writes: usize,
    pub unknown_writes: usize,
    pub known_writer_generations: u64,
    pub same_value_known_writes: usize,
    pub dma_word_writes: usize,
    pub unknown_exported_bytes: usize,
    pub receipts: Vec<DmemDmaEgressReceipt>,
    pub mutation_census_certified: bool,
    pub sp_dma_lifecycle_certified: bool,
    pub hardware_timing_certified: bool,
    pub rdram_lifetime_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum Producer {
    Rsp,
    External { source_id: String },
    Unknown,
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
    RspBegin {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        word: u32,
    },
    DmemWrite {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        producer: Producer,
        offset: u32,
        bytes: u8,
        value: u64,
    },
    RspEnd {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        word: u32,
    },
    SpDmaWrite {
        ordinal: u64,
        context: u64,
        origin_pc: GuestVirtualAddr,
        dram: PhysicalAddr,
        dma_pbus: u32,
        dma_dram: PhysicalAddr,
        dma_count: u32,
        dma_skip: u32,
        source_offset: u32,
        bytes: u8,
        value: u32,
    },
}

#[derive(Debug, Clone)]
struct ActiveRsp {
    context: u64,
    pc: GuestVirtualAddr,
    word: u32,
}

#[derive(Debug, Clone)]
struct Cell {
    value: Option<u8>,
    origin: DmemByteOrigin,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn payload(value: u64, bytes: u8) -> Result<Vec<u8>, String> {
    require(
        matches!(bytes, 1 | 2 | 4 | 8),
        "unsupported DMEM write width",
    )?;
    if bytes < 8 {
        let limit = 1u64 << (u32::from(bytes) * 8);
        require(value < limit, "DMEM write value exceeds declared width")?;
    }
    let raw = value.to_be_bytes();
    Ok(raw[8 - usize::from(bytes)..].to_vec())
}

fn validate_source_id(source_id: &str) -> Result<(), String> {
    require(
        !source_id.is_empty()
            && source_id.len() <= 128
            && source_id
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || b"._:-".contains(&byte)),
        "invalid external DMEM writer identity",
    )
}

fn is_unknown(origin: &DmemByteOrigin) -> bool {
    matches!(
        origin,
        DmemByteOrigin::Unobserved | DmemByteOrigin::Unknown { .. }
    )
}

/// Replays a bounded, externally authenticated complete source. `expected_sha256`
/// must come from a separately trusted receipt. Hash agreement authenticates this
/// supplied history; it does not prove that the sensor observed every N64 mutation.
pub fn inspect_rsp_dmem_dma_egress(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RspDmemDmaEgressReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "RSP DMEM egress source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported RSP DMEM egress history format",
    )?;
    require(
        history.events.len() <= history::MAX_RECORDS as usize,
        "too many RSP DMEM egress events",
    )?;

    let event_count = history.events.len();
    let mut active: Option<ActiveRsp> = None;
    let mut writer_generation = 0u64;
    let mut rsp_writes = 0usize;
    let mut external_writes = 0usize;
    let mut unknown_writes = 0usize;
    let mut same_value_known_writes = 0usize;
    let mut dmem = vec![
        Cell {
            value: None,
            origin: DmemByteOrigin::Unobserved,
        };
        DMEM_BYTES as usize
    ];
    let mut receipts = Vec::new();

    for (next_ordinal, event) in (1u64..).zip(history.events) {
        let ordinal = match &event {
            Event::RspBegin { ordinal, .. }
            | Event::DmemWrite { ordinal, .. }
            | Event::RspEnd { ordinal, .. }
            | Event::SpDmaWrite { ordinal, .. } => *ordinal,
        };
        require(
            ordinal == next_ordinal,
            "noncontiguous RSP DMEM egress event ordinals",
        )?;

        match event {
            Event::RspBegin {
                ordinal,
                context,
                pc,
                word,
            } => {
                require(active.is_none(), "nested RSP instruction context")?;
                require(
                    context == ordinal && context != 0,
                    "invalid RSP instruction context",
                )?;
                require(pc.0.is_multiple_of(4), "unaligned RSP instruction PC")?;
                active = Some(ActiveRsp { context, pc, word });
            }
            Event::DmemWrite {
                ordinal,
                context,
                pc,
                producer,
                offset,
                bytes,
                value,
            } => {
                require(offset < DMEM_BYTES, "DMEM write offset outside bank")?;
                let data = payload(value, bytes)?;
                let before_equal = data.iter().enumerate().all(|(index, byte)| {
                    dmem[((offset + index as u32) & 0xfff) as usize].value == Some(*byte)
                });

                let origin = match producer {
                    Producer::Rsp => {
                        let current = active
                            .as_ref()
                            .ok_or("RSP DMEM write outside instruction")?;
                        require(
                            (context, pc) == (current.context, current.pc),
                            "RSP DMEM write context mismatch",
                        )?;
                        writer_generation += 1;
                        rsp_writes += 1;
                        if before_equal {
                            same_value_known_writes += 1;
                        }
                        DmemByteOrigin::Rsp {
                            writer_generation,
                            context,
                            pc,
                            write_ordinal: ordinal,
                        }
                    }
                    Producer::External { source_id } => {
                        require(
                            active.is_none(),
                            "external DMEM write inside RSP instruction",
                        )?;
                        require(context == 0, "external DMEM write has RSP context")?;
                        validate_source_id(&source_id)?;
                        writer_generation += 1;
                        external_writes += 1;
                        if before_equal {
                            same_value_known_writes += 1;
                        }
                        DmemByteOrigin::External {
                            writer_generation,
                            source_id,
                            write_ordinal: ordinal,
                        }
                    }
                    Producer::Unknown => {
                        match &active {
                            Some(current) => require(
                                (context, pc) == (current.context, current.pc),
                                "unknown DMEM write context mismatch",
                            )?,
                            None => require(context == 0, "unknown DMEM write has stale context")?,
                        }
                        unknown_writes += 1;
                        DmemByteOrigin::Unknown {
                            cut_ordinal: ordinal,
                        }
                    }
                };

                for (index, byte) in data.into_iter().enumerate() {
                    let cell = &mut dmem[((offset + index as u32) & 0xfff) as usize];
                    cell.value = Some(byte);
                    cell.origin = origin.clone();
                }
            }
            Event::RspEnd {
                context, pc, word, ..
            } => {
                let current = active.take().ok_or("RSP instruction end without begin")?;
                require(
                    (context, pc, word) == (current.context, current.pc, current.word),
                    "RSP instruction end context mismatch",
                )?;
            }
            Event::SpDmaWrite {
                ordinal,
                context,
                origin_pc,
                dram,
                dma_pbus,
                dma_dram,
                dma_count,
                dma_skip,
                source_offset,
                bytes,
                value,
            } => {
                require(
                    active.is_none(),
                    "SP DMA effect inside RSP instruction context",
                )?;
                require(context == 0, "SP DMA effect has RSP instruction context")?;
                require(bytes == 4, "SP DMA egress receipt is not a Word effect")?;
                require(
                    dma_pbus < 0x2000 && dma_pbus & SP_BANK_BIT == 0 && dma_pbus.is_multiple_of(8),
                    "SP DMA egress does not identify an aligned DMEM fragment",
                )?;
                require(
                    dma_dram.0 < MAX_SP_PHYSICAL
                        && dram.0 < MAX_SP_PHYSICAL
                        && dma_dram.0.is_multiple_of(8)
                        && dram.0.is_multiple_of(4),
                    "invalid SP DMA RDRAM fragment address",
                )?;
                let delta = dram
                    .0
                    .checked_sub(dma_dram.0)
                    .ok_or("SP DMA effect precedes current fragment")?;
                require(
                    matches!(delta, 0 | 4),
                    "SP DMA effect is outside current 8-byte fragment",
                )?;
                let derived_source = (dma_pbus + delta) & 0xfff;
                require(
                    source_offset == derived_source && source_offset < DMEM_BYTES,
                    "SP DMA source does not match current descriptor fragment",
                )?;

                let data = value.to_be_bytes();
                let mut replayed = true;
                let mut lineage_known = true;
                let mut lanes = Vec::with_capacity(4);
                for (index, byte) in data.into_iter().enumerate() {
                    let source = (derived_source + index as u32) & 0xfff;
                    let cell = &dmem[source as usize];
                    if let Some(observed) = cell.value {
                        require(
                            observed == byte,
                            "SP DMA payload disagrees with observed DMEM byte",
                        )?;
                    } else {
                        replayed = false;
                    }
                    lineage_known &= !is_unknown(&cell.origin);
                    lanes.push(DmemEgressByte {
                        source_offset: source,
                        value: byte,
                        origin: cell.origin.clone(),
                    });
                }
                let bytes: [DmemEgressByte; 4] = lanes
                    .try_into()
                    .map_err(|_| "internal SP DMA lane reconstruction failure".to_string())?;
                receipts.push(DmemDmaEgressReceipt {
                    write_ordinal: ordinal,
                    origin_pc,
                    dram,
                    dma_pbus,
                    dma_dram,
                    dma_count,
                    dma_skip,
                    source_offset,
                    value,
                    payload_fully_replayed: replayed,
                    lineage_fully_known: lineage_known,
                    bytes,
                });
            }
        }
    }

    require(active.is_none(), "truncated RSP instruction context")?;
    let unknown_exported_bytes = receipts
        .iter()
        .flat_map(|receipt| receipt.bytes.iter())
        .filter(|byte| is_unknown(&byte.origin))
        .count();

    Ok(RspDmemDmaEgressReport {
        format: history.format,
        source_sha256: digest,
        events: event_count,
        rsp_writes,
        external_writes,
        unknown_writes,
        known_writer_generations: writer_generation,
        same_value_known_writes,
        dma_word_writes: receipts.len(),
        unknown_exported_bytes,
        receipts,
        mutation_census_certified: false,
        sp_dma_lifecycle_certified: false,
        hardware_timing_certified: false,
        rdram_lifetime_certified: false,
        executable_lifetime_certified: false,
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
        "RSP DMEM egress report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pc(value: u64) -> GuestVirtualAddr {
        GuestVirtualAddr(value)
    }

    fn begin(ordinal: u64, address: u64, word: u32) -> Event {
        Event::RspBegin {
            ordinal,
            context: ordinal,
            pc: pc(address),
            word,
        }
    }

    fn rsp_write(
        ordinal: u64,
        context: u64,
        address: u64,
        offset: u32,
        bytes: u8,
        value: u64,
    ) -> Event {
        Event::DmemWrite {
            ordinal,
            context,
            pc: pc(address),
            producer: Producer::Rsp,
            offset,
            bytes,
            value,
        }
    }

    fn end(ordinal: u64, context: u64, address: u64, word: u32) -> Event {
        Event::RspEnd {
            ordinal,
            context,
            pc: pc(address),
            word,
        }
    }

    fn dma(ordinal: u64, pbus: u32, dram: u32, value: u32) -> Event {
        Event::SpDmaWrite {
            ordinal,
            context: 0,
            origin_pc: pc(0x8000_1000),
            dram: PhysicalAddr(dram),
            dma_pbus: pbus,
            dma_dram: PhysicalAddr(dram & !7),
            dma_count: 0,
            dma_skip: 0,
            source_offset: (pbus + (dram & 4)) & 0xfff,
            bytes: 4,
            value,
        }
    }

    fn source(events: Vec<Event>) -> (Vec<u8>, String) {
        let bytes = serde_json::to_vec(&History {
            format: FORMAT.into(),
            events,
        })
        .unwrap();
        let digest = sha256(&bytes);
        (bytes, digest)
    }

    #[test]
    fn same_value_write_mints_fresh_generation() {
        let word = 0xac22_0000;
        let (source, digest) = source(vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0x40, 4, 0x1122_3344),
            end(3, 1, 0, word),
            begin(4, 4, word),
            rsp_write(5, 4, 4, 0x40, 4, 0x1122_3344),
            end(6, 4, 4, word),
            dma(7, 0x40, 0x1000, 0x1122_3344),
        ]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        assert_eq!(report.known_writer_generations, 2);
        assert_eq!(report.same_value_known_writes, 1);
        assert!(report.receipts[0].payload_fully_replayed);
        assert!(report.receipts[0].lineage_fully_known);
        for byte in &report.receipts[0].bytes {
            assert!(matches!(
                byte.origin,
                DmemByteOrigin::Rsp {
                    writer_generation: 2,
                    write_ordinal: 5,
                    ..
                }
            ));
        }
    }

    #[test]
    fn external_and_unknown_writes_replace_only_touched_lanes() {
        let word = 0xac22_0000;
        let (source, digest) = source(vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0x40, 4, 0x1122_3344),
            end(3, 1, 0, word),
            Event::DmemWrite {
                ordinal: 4,
                context: 0,
                pc: pc(0x8000_2000),
                producer: Producer::External {
                    source_id: "cpu-sp-word-7".into(),
                },
                offset: 0x41,
                bytes: 1,
                value: 0xaa,
            },
            Event::DmemWrite {
                ordinal: 5,
                context: 0,
                pc: pc(0),
                producer: Producer::Unknown,
                offset: 0x42,
                bytes: 1,
                value: 0xbb,
            },
            dma(6, 0x40, 0x1000, 0x11aa_bb44),
        ]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        let lanes = &report.receipts[0].bytes;
        assert!(matches!(lanes[0].origin, DmemByteOrigin::Rsp { .. }));
        assert!(matches!(lanes[1].origin, DmemByteOrigin::External { .. }));
        assert_eq!(lanes[2].origin, DmemByteOrigin::Unknown { cut_ordinal: 5 });
        assert!(matches!(lanes[3].origin, DmemByteOrigin::Rsp { .. }));
        assert_eq!(report.unknown_exported_bytes, 1);
        assert!(!report.receipts[0].lineage_fully_known);
        assert!(report.receipts[0].payload_fully_replayed);
    }

    #[test]
    fn descriptor_selects_equal_payload_source_not_latest_value() {
        let word = 0xac22_0000;
        let (source, digest) = source(vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0x40, 4, 0xdead_beef),
            end(3, 1, 0, word),
            begin(4, 4, word),
            rsp_write(5, 4, 4, 0x80, 4, 0xdead_beef),
            end(6, 4, 4, word),
            dma(7, 0x40, 0x1000, 0xdead_beef),
        ]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        for byte in &report.receipts[0].bytes {
            assert!(matches!(
                byte.origin,
                DmemByteOrigin::Rsp {
                    writer_generation: 1,
                    write_ordinal: 2,
                    ..
                }
            ));
        }
    }

    #[test]
    fn wrapped_dmem_write_preserves_per_byte_lineage() {
        let word = 0xac22_0000;
        let (source, digest) = source(vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0xffe, 4, 0xa1b2_c3d4),
            end(3, 1, 0, word),
            Event::SpDmaWrite {
                ordinal: 4,
                context: 0,
                origin_pc: pc(0x8000_1000),
                dram: PhysicalAddr(0x2000),
                dma_pbus: 0,
                dma_dram: PhysicalAddr(0x2000),
                dma_count: 0,
                dma_skip: 0,
                source_offset: 0,
                bytes: 4,
                value: 0xc3d4_0000,
            },
        ]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        assert!(matches!(
            report.receipts[0].bytes[0].origin,
            DmemByteOrigin::Rsp {
                write_ordinal: 2,
                ..
            }
        ));
        assert!(matches!(
            report.receipts[0].bytes[1].origin,
            DmemByteOrigin::Rsp {
                write_ordinal: 2,
                ..
            }
        ));
        assert!(matches!(
            report.receipts[0].bytes[2].origin,
            DmemByteOrigin::Unobserved
        ));
        assert!(!report.receipts[0].payload_fully_replayed);
    }

    #[test]
    fn forged_descriptor_bank_source_payload_and_order_fail_closed() {
        let word = 0xac22_0000;
        let base = vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0x40, 4, 0x1122_3344),
            end(3, 1, 0, word),
            dma(4, 0x40, 0x1000, 0x1122_3344),
        ];

        let mut bank = base.clone();
        if let Event::SpDmaWrite { dma_pbus, .. } = &mut bank[3] {
            *dma_pbus |= SP_BANK_BIT;
        }
        let (bytes, digest) = source(bank);
        assert!(inspect_rsp_dmem_dma_egress(&bytes, &digest).is_err());

        let mut source_forgery = base.clone();
        if let Event::SpDmaWrite { source_offset, .. } = &mut source_forgery[3] {
            *source_offset ^= 4;
        }
        let (bytes, digest) = source(source_forgery);
        assert!(inspect_rsp_dmem_dma_egress(&bytes, &digest).is_err());

        let mut payload_forgery = base.clone();
        if let Event::SpDmaWrite { value, .. } = &mut payload_forgery[3] {
            *value ^= 1;
        }
        let (bytes, digest) = source(payload_forgery);
        assert!(inspect_rsp_dmem_dma_egress(&bytes, &digest).is_err());

        let mut order_forgery = base;
        if let Event::DmemWrite { ordinal, .. } = &mut order_forgery[1] {
            *ordinal = 3;
        }
        let (bytes, digest) = source(order_forgery);
        assert!(inspect_rsp_dmem_dma_egress(&bytes, &digest).is_err());
    }

    #[test]
    fn missing_initial_ancestry_remains_unknown_even_when_payload_exists() {
        let (source, digest) = source(vec![dma(1, 0x40, 0x1000, 0x0102_0304)]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        assert!(!report.receipts[0].payload_fully_replayed);
        assert!(!report.receipts[0].lineage_fully_known);
        assert_eq!(report.unknown_exported_bytes, 4);
        assert!(
            report.receipts[0]
                .bytes
                .iter()
                .all(|byte| byte.origin == DmemByteOrigin::Unobserved)
        );
    }

    #[test]
    fn report_and_source_receipts_are_rechecked() {
        let word = 0xac22_0000;
        let (source, digest) = source(vec![
            begin(1, 0, word),
            rsp_write(2, 1, 0, 0x40, 4, 0x1122_3344),
            end(3, 1, 0, word),
            dma(4, 0x40, 0x1000, 0x1122_3344),
        ]);
        let report = inspect_rsp_dmem_dma_egress(&source, &digest).unwrap();
        verify_rsp_dmem_dma_egress_report(&report, &source, &digest).unwrap();

        let mut forged = report.clone();
        forged.receipts[0].bytes[0].source_offset ^= 1;
        assert!(verify_rsp_dmem_dma_egress_report(&forged, &source, &digest).is_err());
        assert!(inspect_rsp_dmem_dma_egress(&source, &"0".repeat(64)).is_err());
    }
}
