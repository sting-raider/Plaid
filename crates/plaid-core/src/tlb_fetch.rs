//! Source-bound replay for bounded TLB-mapped uncached instruction fetches.
//!
//! This module certifies only a finite fetch-to-backing join for execution-backed
//! low-region 4 KiB, 16 KiB, and 64 KiB PageMask geometry. It does not mint TLB
//! mapping or translation-context generations, prove sensor completeness, model
//! cached I-cache residency, establish executable lifetime, or discharge
//! closed-world obligations.

use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-tlb-uncached-fetch-v0";
const MASK40: u64 = (1u64 << 40) - 1;
const PAGEMASK_PAIR_BITS: u64 = 0b101010101010u64 << 13;
const PAGE_MASK_16K: u64 = 0b11u64 << 13;
const PAGE_MASK_64K: u64 = 0b1111u64 << 13;
const WORD_BYTES: u8 = 4;
const RDRAM_BUS_MAX: u32 = 0x03ff_ffff;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbFetchHalf {
    pub valid: bool,
    pub cca: u8,
    pub physical_base: PhysicalAddr,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbFetchMapping {
    /// Opaque upstream identity. This replay preserves it but does not mint or
    /// independently certify a mapping generation.
    pub mapping_ref: String,
    pub raw_page_mask: u32,
    /// Synchronized low-40-bit EntryHi virtual address.
    pub virtual_address: u64,
    pub asid: u8,
    pub region: u8,
    pub global0: bool,
    pub global1: bool,
    pub lo0: TlbFetchHalf,
    pub lo1: TlbFetchHalf,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RdramReadRequestor {
    Vr4300Uncached,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbFetchWitness {
    pub epoch: u64,
    pub context: u64,
    pub begin_ordinal: u64,
    pub read_ordinal: u64,
    pub end_ordinal: u64,
    pub vaddr: GuestVirtualAddr,
    pub mapping_ref: String,
    /// Opaque upstream context identity, preserved for later composition only.
    pub translation_context_ref: String,
    pub normalized_page_mask: u32,
    pub selected_half: u8,
    pub translated_paddr: PhysicalAddr,
    pub bus_paddr: PhysicalAddr,
    pub reverse_endian: bool,
    pub word: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlbFetchReport {
    pub format: String,
    pub source_sha256: String,
    pub fetches: usize,
    pub outside_fetch_reads: usize,
    pub witnesses: Vec<TlbFetchWitness>,
    pub sensor_coverage_certified: bool,
    pub mapping_history_certified: bool,
    pub translation_context_certified: bool,
    pub cache_residency_certified: bool,
    pub executable_lifetime_certified: bool,
    pub whole_rom_closed: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    Begin {
        ordinal: u64,
        context: u64,
        epoch: u64,
        vaddr: GuestVirtualAddr,
        current_asid: u8,
        translation_context_ref: String,
        mapping: TlbFetchMapping,
        translated_paddr: PhysicalAddr,
        bus_paddr: PhysicalAddr,
        reverse_endian: bool,
    },
    RdramRead {
        ordinal: u64,
        address: PhysicalAddr,
        bytes: u8,
        requestor: RdramReadRequestor,
        value: u32,
    },
    End {
        ordinal: u64,
        context: u64,
        epoch: u64,
        vaddr: GuestVirtualAddr,
        word: u32,
    },
}

struct Geometry {
    normalized_page_mask: u64,
    address_mask_hi: u64,
    address_mask_lo: u64,
    address_select: u64,
}

struct Active {
    begin_ordinal: u64,
    context: u64,
    epoch: u64,
    vaddr: GuestVirtualAddr,
    mapping_ref: String,
    translation_context_ref: String,
    normalized_page_mask: u32,
    selected_half: u8,
    translated_paddr: PhysicalAddr,
    bus_paddr: PhysicalAddr,
    reverse_endian: bool,
    read: Option<ObservedRead>,
}

struct ObservedRead {
    ordinal: u64,
    address: PhysicalAddr,
    value: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn validate_ref(value: &str, field: &str) -> Result<(), String> {
    require(
        !value.is_empty() && value.len() <= 256 && !value.chars().any(char::is_control),
        field,
    )
}

fn geometry(raw_page_mask: u32) -> Result<Geometry, String> {
    let mut normalized = u64::from(raw_page_mask) & PAGEMASK_PAIR_BITS;
    normalized |= normalized >> 1;
    require(
        matches!(normalized, 0 | PAGE_MASK_16K | PAGE_MASK_64K),
        "PageMask outside execution-backed 4K/16K/64K scope",
    )?;
    let pair_mask = normalized | 0x1fff;
    Ok(Geometry {
        normalized_page_mask: normalized,
        address_mask_hi: (!pair_mask) & MASK40,
        address_mask_lo: pair_mask >> 1,
        address_select: (pair_mask >> 1) + 1,
    })
}

fn validate_mapping(
    vaddr: GuestVirtualAddr,
    current_asid: u8,
    mapping: &TlbFetchMapping,
    translated_paddr: PhysicalAddr,
    bus_paddr: PhysicalAddr,
    reverse_endian: bool,
) -> Result<(u32, u8), String> {
    validate_ref(&mapping.mapping_ref, "invalid mapping reference")?;
    require(
        mapping.region == 0 && vaddr.0 <= MASK40,
        "mapped fetch is outside execution-backed low-region address scope",
    )?;
    require(mapping.lo0.cca <= 7 && mapping.lo1.cca <= 7, "invalid TLB CCA")?;

    let geometry = geometry(mapping.raw_page_mask)?;
    require(
        !reverse_endian || geometry.normalized_page_mask == 0,
        "reverse-endian large-PageMask composition is outside execution-backed scope",
    )?;
    require(
        mapping.virtual_address <= MASK40
            && mapping.virtual_address == (mapping.virtual_address & geometry.address_mask_hi),
        "mapping virtual address is not synchronized to PageMask geometry",
    )?;
    require(
        mapping.global0 == mapping.global1,
        "mapping global bits are not synchronized",
    )?;

    let v40 = vaddr.0 & MASK40;
    require(
        (v40 & geometry.address_mask_hi) == mapping.virtual_address,
        "virtual address does not match supplied TLB mapping",
    )?;
    if !mapping.global0 {
        require(mapping.asid == current_asid, "non-global TLB ASID mismatch")?;
    }

    let selected_half = u8::from((v40 & geometry.address_select) != 0);
    let half = if selected_half == 0 {
        &mapping.lo0
    } else {
        &mapping.lo1
    };
    require(half.valid, "selected TLB half is invalid")?;
    require(half.cca == 2, "selected TLB mapping is not CCA=2 uncached")?;

    let translated = u64::from(half.physical_base.0) + (v40 & geometry.address_mask_lo);
    require(translated <= u64::from(u32::MAX), "translated TLB address overflow")?;
    require(
        translated_paddr.0 == translated as u32,
        "captured translated physical address contradicts PageMask mapping",
    )?;
    require(
        translated_paddr.0.is_multiple_of(4),
        "unaligned translated instruction address",
    )?;

    let expected_bus = if reverse_endian {
        translated_paddr.0 ^ 4
    } else {
        translated_paddr.0
    };
    require(
        bus_paddr.0 == expected_bus,
        "captured bus physical address contradicts endian lane selection",
    )?;
    require(
        bus_paddr.0 <= RDRAM_BUS_MAX && bus_paddr.0.is_multiple_of(4),
        "bus physical address is outside ordinary aligned RDRAM Word scope",
    )?;

    Ok((geometry.normalized_page_mask as u32, selected_half))
}

/// Replays a complete, separately authenticated finite source. The expected hash
/// is the trust boundary for collection completeness; this function does not
/// claim that the producer observed every future or architecturally possible
/// mapping/fetch event.
pub fn inspect_tlb_fetch_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<TlbFetchReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "TLB fetch source receipt mismatch")?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(history.format == FORMAT, "unsupported TLB fetch history format")?;

    let mut next_ordinal = 1u64;
    let mut last_epoch = 0u64;
    let mut active: Option<Active> = None;
    let mut witnesses = Vec::new();
    let mut outside_fetch_reads = 0usize;

    for event in history.events {
        match event {
            Event::Begin {
                ordinal,
                context,
                epoch,
                vaddr,
                current_asid,
                translation_context_ref,
                mapping,
                translated_paddr,
                bus_paddr,
                reverse_endian,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLB fetch event ordinals")?;
                next_ordinal += 1;
                require(active.is_none(), "nested TLB fetch begin")?;
                require(context == ordinal, "TLB fetch context must equal begin ordinal")?;
                require(epoch != 0 && epoch >= last_epoch, "invalid or reordered TLB fetch epoch")?;
                require(vaddr.0.is_multiple_of(4), "unaligned mapped instruction vaddr")?;
                validate_ref(
                    &translation_context_ref,
                    "invalid translation context reference",
                )?;
                let (normalized_page_mask, selected_half) = validate_mapping(
                    vaddr,
                    current_asid,
                    &mapping,
                    translated_paddr,
                    bus_paddr,
                    reverse_endian,
                )?;
                last_epoch = epoch;
                active = Some(Active {
                    begin_ordinal: ordinal,
                    context,
                    epoch,
                    vaddr,
                    mapping_ref: mapping.mapping_ref,
                    translation_context_ref,
                    normalized_page_mask,
                    selected_half,
                    translated_paddr,
                    bus_paddr,
                    reverse_endian,
                    read: None,
                });
            }
            Event::RdramRead {
                ordinal,
                address,
                bytes,
                requestor,
                value,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLB fetch event ordinals")?;
                next_ordinal += 1;
                require(bytes == WORD_BYTES, "TLB fetch backing read is not one Word")?;
                require(
                    requestor == RdramReadRequestor::Vr4300Uncached,
                    "TLB fetch backing read has wrong requestor",
                )?;
                require(
                    address.0 <= RDRAM_BUS_MAX && address.0.is_multiple_of(4),
                    "backing read is outside ordinary aligned RDRAM Word scope",
                )?;
                if let Some(current) = active.as_mut() {
                    require(current.read.is_none(), "multiple backing reads inside one fetch")?;
                    current.read = Some(ObservedRead {
                        ordinal,
                        address,
                        value,
                    });
                } else {
                    outside_fetch_reads += 1;
                }
            }
            Event::End {
                ordinal,
                context,
                epoch,
                vaddr,
                word,
            } => {
                require(ordinal == next_ordinal, "noncontiguous TLB fetch event ordinals")?;
                next_ordinal += 1;
                let current = active.take().ok_or("TLB fetch end without active begin")?;
                require(
                    (context, epoch, vaddr) == (current.context, current.epoch, current.vaddr),
                    "TLB fetch end context mismatch",
                )?;
                let read = current.read.ok_or("mapped uncached fetch lacks backing Word read")?;
                require(
                    read.address == current.bus_paddr,
                    "mapped uncached fetch backing address mismatch",
                )?;
                require(read.value == word, "mapped uncached fetch backing value mismatch")?;
                witnesses.push(TlbFetchWitness {
                    epoch: current.epoch,
                    context: current.context,
                    begin_ordinal: current.begin_ordinal,
                    read_ordinal: read.ordinal,
                    end_ordinal: ordinal,
                    vaddr: current.vaddr,
                    mapping_ref: current.mapping_ref,
                    translation_context_ref: current.translation_context_ref,
                    normalized_page_mask: current.normalized_page_mask,
                    selected_half: current.selected_half,
                    translated_paddr: current.translated_paddr,
                    bus_paddr: current.bus_paddr,
                    reverse_endian: current.reverse_endian,
                    word,
                });
            }
        }
    }

    require(active.is_none(), "truncated TLB fetch context")?;

    Ok(TlbFetchReport {
        format: history.format,
        source_sha256: digest,
        fetches: witnesses.len(),
        outside_fetch_reads,
        witnesses,
        sensor_coverage_certified: false,
        mapping_history_certified: false,
        translation_context_certified: false,
        cache_residency_certified: false,
        executable_lifetime_certified: false,
        whole_rom_closed: false,
        native_complete: false,
    })
}

pub fn verify_tlb_fetch_report(
    report: &TlbFetchReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_tlb_fetch_history(source, expected_sha256)?,
        "TLB fetch report differs from complete source replay",
    )
}
