//! Recheck the bounded pinned-ares SD/SDL/SDR mutation contract.
//!
//! This module does not promote one emulator into hardware truth. It preserves the
//! exact source contract that was independently exercised at the pinned revision:
//! one architectural store may produce multiple ordered writes, and a cacheable
//! store's immediate effect is cache-resident rather than a backing-RDRAM write.
//! Physical sink identity is supplied by observation and is never inferred from
//! the guest virtual address, payload equality, or the decomposition below.

use crate::{GuestAddr, program::PhysicalAddr};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const ARES_REVISION: &str = "9408cb43d4948fc3ea6e152a307a34348df3fe04";
pub const MODEL_SHA256: &str = "768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Store64Kind {
    Sd,
    Sdl,
    Sdr,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StoreEndian {
    Big,
    Little,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MutationLayer {
    DcacheResident,
    IdentityRdramBacking,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StoreOutcome {
    Completed,
    RejectedBeforeMutation,
}

/// One concrete write produced by an architectural store.
///
/// `handler_address` is the address passed by the instruction handler to the
/// ordinary memory write path. `sink_physical` is a separately observed sink;
/// validation deliberately does not derive one from the other because endian,
/// translation, alias, and cache context are independent proof obligations.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct StoreSubwriteReceipt {
    pub sequence: u8,
    pub event: String,
    pub handler_address: GuestAddr,
    pub sink_physical: PhysicalAddr,
    pub bytes: u8,
    pub value: u64,
    pub layer: MutationLayer,
}

/// A bounded receipt for one pinned-ares SD/SDL/SDR attempt.
///
/// The reference/model identifiers prevent this source-specific rechecker from
/// silently accepting another implementation or semantic revision. They do not
/// establish complete sensing, source-byte ancestry, executable lifetime, or
/// hardware equivalence.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AresStore64Receipt {
    pub reference_revision: String,
    pub model_sha256: String,
    pub operation_event: String,
    pub site: GuestAddr,
    pub address: GuestAddr,
    pub source_value: u64,
    pub kind: Store64Kind,
    pub endian: StoreEndian,
    pub cached: bool,
    pub outcome: StoreOutcome,
    pub subwrites: Vec<StoreSubwriteReceipt>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct SubwriteSpec {
    offset: u32,
    bytes: u8,
    shift: u8,
}

impl SubwriteSpec {
    const fn new(offset: u32, bytes: u8, shift: u8) -> Self {
        Self {
            offset,
            bytes,
            shift,
        }
    }
}

fn expected_subwrites(kind: Store64Kind, endian: StoreEndian, offset: u32) -> Vec<SubwriteSpec> {
    use Store64Kind::{Sd, Sdl, Sdr};
    use StoreEndian::{Big, Little};

    match (kind, endian, offset) {
        (Sd, _, 0) => vec![SubwriteSpec::new(0, 8, 0)],
        (Sd, _, _) => Vec::new(),

        (Sdl, Big, 0) => vec![SubwriteSpec::new(0, 8, 0)],
        (Sdl, Big, 1) => vec![
            SubwriteSpec::new(1, 1, 56),
            SubwriteSpec::new(2, 2, 40),
            SubwriteSpec::new(4, 4, 8),
        ],
        (Sdl, Big, 2) => vec![SubwriteSpec::new(2, 2, 48), SubwriteSpec::new(4, 4, 16)],
        (Sdl, Big, 3) => vec![SubwriteSpec::new(3, 1, 56), SubwriteSpec::new(4, 4, 24)],
        (Sdl, Big, 4) => vec![SubwriteSpec::new(4, 4, 32)],
        (Sdl, Big, 5) => vec![SubwriteSpec::new(5, 1, 56), SubwriteSpec::new(6, 2, 40)],
        (Sdl, Big, 6) => vec![SubwriteSpec::new(6, 2, 48)],
        (Sdl, Big, 7) => vec![SubwriteSpec::new(7, 1, 56)],

        (Sdr, Big, 0) => vec![SubwriteSpec::new(0, 1, 0)],
        (Sdr, Big, 1) => vec![SubwriteSpec::new(0, 2, 0)],
        (Sdr, Big, 2) => vec![SubwriteSpec::new(0, 2, 8), SubwriteSpec::new(2, 1, 0)],
        (Sdr, Big, 3) => vec![SubwriteSpec::new(0, 4, 0)],
        (Sdr, Big, 4) => vec![SubwriteSpec::new(0, 4, 8), SubwriteSpec::new(4, 1, 0)],
        (Sdr, Big, 5) => vec![SubwriteSpec::new(0, 4, 16), SubwriteSpec::new(4, 2, 0)],
        (Sdr, Big, 6) => vec![
            SubwriteSpec::new(0, 4, 24),
            SubwriteSpec::new(4, 2, 8),
            SubwriteSpec::new(6, 1, 0),
        ],
        (Sdr, Big, 7) => vec![SubwriteSpec::new(0, 8, 0)],

        (Sdl, Little, 0) => vec![SubwriteSpec::new(0, 1, 56)],
        (Sdl, Little, 1) => vec![SubwriteSpec::new(0, 2, 48)],
        (Sdl, Little, 2) => vec![SubwriteSpec::new(2, 1, 56), SubwriteSpec::new(0, 2, 40)],
        (Sdl, Little, 3) => vec![SubwriteSpec::new(0, 4, 32)],
        (Sdl, Little, 4) => vec![SubwriteSpec::new(4, 1, 56), SubwriteSpec::new(0, 4, 24)],
        (Sdl, Little, 5) => vec![SubwriteSpec::new(4, 2, 48), SubwriteSpec::new(0, 4, 16)],
        (Sdl, Little, 6) => vec![
            SubwriteSpec::new(6, 1, 56),
            SubwriteSpec::new(4, 2, 40),
            SubwriteSpec::new(0, 4, 8),
        ],
        (Sdl, Little, 7) => vec![SubwriteSpec::new(0, 8, 0)],

        (Sdr, Little, 0) => vec![SubwriteSpec::new(0, 8, 0)],
        (Sdr, Little, 1) => vec![
            SubwriteSpec::new(4, 4, 24),
            SubwriteSpec::new(2, 2, 8),
            SubwriteSpec::new(1, 1, 0),
        ],
        (Sdr, Little, 2) => vec![SubwriteSpec::new(4, 4, 16), SubwriteSpec::new(2, 2, 0)],
        (Sdr, Little, 3) => vec![SubwriteSpec::new(4, 4, 8), SubwriteSpec::new(3, 1, 0)],
        (Sdr, Little, 4) => vec![SubwriteSpec::new(4, 4, 0)],
        (Sdr, Little, 5) => vec![SubwriteSpec::new(6, 2, 8), SubwriteSpec::new(5, 1, 0)],
        (Sdr, Little, 6) => vec![SubwriteSpec::new(6, 2, 0)],
        (Sdr, Little, 7) => vec![SubwriteSpec::new(7, 1, 0)],
        _ => unreachable!("offset is masked to three bits"),
    }
}

fn lane_value(source: u64, spec: SubwriteSpec) -> u64 {
    let mask = if spec.bytes == 8 {
        u64::MAX
    } else {
        (1u64 << (u32::from(spec.bytes) * 8)) - 1
    };
    (source >> spec.shift) & mask
}

fn validate_source_id(value: &str, expected: &str, label: &str) -> Result<(), String> {
    if value == expected {
        Ok(())
    } else {
        Err(format!("unexpected {label}"))
    }
}

impl AresStore64Receipt {
    pub fn validate(&self) -> Result<(), String> {
        validate_source_id(&self.reference_revision, ARES_REVISION, "ares revision")?;
        validate_source_id(&self.model_sha256, MODEL_SHA256, "store model hash")?;
        if self.operation_event.is_empty() {
            return Err("store receipt lacks operation identity".into());
        }
        if !self.site.0.is_multiple_of(4) {
            return Err("store receipt has unaligned instruction site".into());
        }

        if self.outcome == StoreOutcome::RejectedBeforeMutation {
            return if self.subwrites.is_empty() {
                Ok(())
            } else {
                Err("rejected store carries mutation effects".into())
            };
        }

        let offset = self.address.0 & 7;
        let base = self.address.0 & !7;
        let expected = expected_subwrites(self.kind, self.endian, offset);
        if expected.is_empty() {
            return Err("completed store has no valid decomposition".into());
        }
        if self.subwrites.len() != expected.len() {
            return Err("store subwrite count differs from pinned source contract".into());
        }

        let required_layer = if self.cached {
            MutationLayer::DcacheResident
        } else {
            MutationLayer::IdentityRdramBacking
        };
        let mut events = BTreeSet::new();
        for (index, (actual, spec)) in self.subwrites.iter().zip(expected).enumerate() {
            if actual.sequence != index as u8 {
                return Err("store subwrite sequence is not contiguous".into());
            }
            if actual.event.is_empty()
                || actual.event == self.operation_event
                || !events.insert(actual.event.as_str())
            {
                return Err("store subwrite identity is missing or reused".into());
            }
            let address = base
                .checked_add(spec.offset)
                .ok_or("store handler address overflow")?;
            if actual.handler_address != GuestAddr(address)
                || actual.bytes != spec.bytes
                || actual.value != lane_value(self.source_value, spec)
            {
                return Err("store subwrite differs from pinned source contract".into());
            }
            if actual.layer != required_layer {
                return Err("store mutation layer disagrees with cache policy".into());
            }
            if actual
                .sink_physical
                .0
                .checked_add(u32::from(actual.bytes))
                .is_none()
            {
                return Err("store sink span overflows physical address space".into());
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const VALUE: u64 = 0x1122_3344_5566_7788;

    fn receipt(
        kind: Store64Kind,
        endian: StoreEndian,
        address: u32,
        cached: bool,
    ) -> AresStore64Receipt {
        let base = address & !7;
        let specs = expected_subwrites(kind, endian, address & 7);
        let layer = if cached {
            MutationLayer::DcacheResident
        } else {
            MutationLayer::IdentityRdramBacking
        };
        let subwrites = specs
            .iter()
            .enumerate()
            .map(|(index, spec)| StoreSubwriteReceipt {
                sequence: index as u8,
                event: format!("write-{index}"),
                handler_address: GuestAddr(base + spec.offset),
                // The sink is deliberately not derived from handler_address.
                sink_physical: PhysicalAddr(0x1000 + index as u32 * 0x20),
                bytes: spec.bytes,
                value: lane_value(VALUE, *spec),
                layer,
            })
            .collect();
        AresStore64Receipt {
            reference_revision: ARES_REVISION.into(),
            model_sha256: MODEL_SHA256.into(),
            operation_event: "store-op".into(),
            site: GuestAddr(0x8000_0100),
            address: GuestAddr(address),
            source_value: VALUE,
            kind,
            endian,
            cached,
            outcome: StoreOutcome::Completed,
            subwrites,
        }
    }

    #[test]
    fn validates_all_completed_sdl_sdr_offsets_and_aligned_sd() {
        for endian in [StoreEndian::Big, StoreEndian::Little] {
            receipt(Store64Kind::Sd, endian, 0x8000_2000, false)
                .validate()
                .unwrap();
            for offset in 0..8 {
                for kind in [Store64Kind::Sdl, Store64Kind::Sdr] {
                    receipt(kind, endian, 0x8000_2000 + offset, false)
                        .validate()
                        .unwrap();
                    receipt(kind, endian, 0x8000_2000 + offset, true)
                        .validate()
                        .unwrap();
                }
            }
        }
    }

    #[test]
    fn preserves_known_three_write_decompositions() {
        let big = receipt(Store64Kind::Sdl, StoreEndian::Big, 0x8000_2001, false);
        let big_shape: Vec<_> = big
            .subwrites
            .iter()
            .map(|w| (w.handler_address.0 & 7, w.bytes, w.value))
            .collect();
        assert_eq!(
            big_shape,
            vec![(1, 1, 0x11), (2, 2, 0x2233), (4, 4, 0x4455_6677)]
        );

        let little = receipt(Store64Kind::Sdr, StoreEndian::Little, 0x8000_2001, false);
        let little_shape: Vec<_> = little
            .subwrites
            .iter()
            .map(|w| (w.handler_address.0 & 7, w.bytes, w.value))
            .collect();
        assert_eq!(
            little_shape,
            vec![(4, 4, 0x4455_6677), (2, 2, 0x6677), (1, 1, 0x88)]
        );
    }

    #[test]
    fn cache_resident_and_backing_effects_are_not_interchangeable() {
        let mut cached = receipt(Store64Kind::Sd, StoreEndian::Big, 0x8000_2000, true);
        cached.subwrites[0].layer = MutationLayer::IdentityRdramBacking;
        assert!(cached.validate().is_err());

        let mut uncached = receipt(Store64Kind::Sd, StoreEndian::Big, 0xa000_2000, false);
        uncached.subwrites[0].layer = MutationLayer::DcacheResident;
        assert!(uncached.validate().is_err());
    }

    #[test]
    fn explicit_sink_identity_is_not_inferred_from_guest_address() {
        let mut r = receipt(Store64Kind::Sdr, StoreEndian::Little, 0x8000_2001, false);
        for (index, write) in r.subwrites.iter_mut().enumerate() {
            write.sink_physical = PhysicalAddr(0x0030_0100 + index as u32 * 0x40);
        }
        r.validate().unwrap();
    }

    #[test]
    fn same_value_subwrites_do_not_collapse_identity() {
        let mut r = receipt(Store64Kind::Sdl, StoreEndian::Big, 0x8000_2001, false);
        r.source_value = 0;
        for (write, spec) in
            r.subwrites
                .iter_mut()
                .zip(expected_subwrites(r.kind, r.endian, r.address.0 & 7))
        {
            write.value = lane_value(0, spec);
        }
        r.validate().unwrap();
        r.subwrites[1].event = r.subwrites[0].event.clone();
        assert!(r.validate().is_err());
    }

    #[test]
    fn rejects_deleted_reordered_and_forged_subwrites() {
        let base = receipt(Store64Kind::Sdl, StoreEndian::Big, 0x8000_2001, false);

        let mut deleted = base.clone();
        deleted.subwrites.remove(1);
        assert!(deleted.validate().is_err());

        let mut reordered = base.clone();
        reordered.subwrites.swap(0, 1);
        assert!(reordered.validate().is_err());

        let mut forged = base;
        forged.subwrites[2].value ^= 1;
        assert!(forged.validate().is_err());
    }

    #[test]
    fn rejected_and_misaligned_sd_cannot_smuggle_mutations() {
        let mut rejected = receipt(Store64Kind::Sdr, StoreEndian::Big, 0x8000_2005, false);
        rejected.outcome = StoreOutcome::RejectedBeforeMutation;
        assert!(rejected.validate().is_err());
        rejected.subwrites.clear();
        rejected.validate().unwrap();

        let misaligned = receipt(Store64Kind::Sd, StoreEndian::Big, 0x8000_2001, false);
        assert!(misaligned.validate().is_err());
    }

    #[test]
    fn rejects_source_contract_and_span_forgeries() {
        let mut wrong_revision = receipt(Store64Kind::Sd, StoreEndian::Big, 0x8000_2000, false);
        wrong_revision.reference_revision = "different".into();
        assert!(wrong_revision.validate().is_err());

        let mut wrong_model = receipt(Store64Kind::Sd, StoreEndian::Big, 0x8000_2000, false);
        wrong_model.model_sha256 = "0".repeat(64);
        assert!(wrong_model.validate().is_err());

        let mut overflow = receipt(Store64Kind::Sd, StoreEndian::Big, 0x8000_2000, false);
        overflow.subwrites[0].sink_physical = PhysicalAddr(u32::MAX - 3);
        assert!(overflow.validate().is_err());
    }
}
