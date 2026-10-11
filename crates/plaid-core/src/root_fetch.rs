//! Source-bound replay for cached exception-root executable generations.
//!
//! The architectural vector selected by [`crate::exception_roots`] is not the
//! executable handler identity. This bounded verifier keeps backing generations,
//! resident I-cache generations, root transfers, and actual root fetches separate.
//! It creates no reachability, mutation-census, mapping/cache-lifetime,
//! whole-ROM closure, or native-completeness proof.
use crate::{
    exception_roots::{resolve_exception_root, ExceptionRootReceipt},
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-cached-exception-root-history-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Clone, Copy, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    /// A newly authenticated storage generation at one physical word.
    /// Equal payloads remain distinct because the generation event is distinct.
    BackingGeneration {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    /// A completed fill tied to one exact prior backing-generation event.
    /// The triggering virtual address identifies the direct-mapped I-cache slot.
    CacheFill {
        ordinal: u64,
        vaddr: GuestVirtualAddr,
        physical: PhysicalAddr,
        word: u32,
        backing_ordinal: u64,
    },
    /// A completed invalidation of the exact currently resident fill.
    CacheInvalidate {
        ordinal: u64,
        vaddr: GuestVirtualAddr,
        fill_ordinal: u64,
    },
    /// An observed residency-affecting boundary whose byte source is not proven.
    /// It destroys the reusable resident witness for that slot.
    ResidencyCut {
        ordinal: u64,
        vaddr: GuestVirtualAddr,
    },
    /// The already-classified architectural transfer to the selected root.
    RootTransfer {
        ordinal: u64,
        root: GuestVirtualAddr,
    },
    /// The actual cached handler fetch from one exact resident fill.
    RootFetch {
        ordinal: u64,
        root: GuestVirtualAddr,
        physical: PhysicalAddr,
        word: u32,
        fill_ordinal: u64,
    },
}

impl Event {
    fn ordinal(self) -> u64 {
        match self {
            Self::BackingGeneration { ordinal, .. }
            | Self::CacheFill { ordinal, .. }
            | Self::CacheInvalidate { ordinal, .. }
            | Self::ResidencyCut { ordinal, .. }
            | Self::RootTransfer { ordinal, .. }
            | Self::RootFetch { ordinal, .. } => ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RootFetchWitness {
    pub root: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub slot: u16,
    pub transfer_ordinal: u64,
    pub fetch_ordinal: u64,
    pub resident_generation: u64,
    pub fill_ordinal: u64,
    pub backing_generation: u64,
    pub backing_ordinal: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CachedExceptionRootReport {
    pub format: String,
    pub source_sha256: String,
    pub events: usize,
    pub backing_generations: u64,
    pub resident_generations: u64,
    pub witnesses: Vec<RootFetchWitness>,
    pub reachability_certified: bool,
    pub mapping_lifetime_certified: bool,
    pub cache_lifetime_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy)]
struct BackingState {
    generation: u64,
    ordinal: u64,
    word: u32,
}

#[derive(Debug, Clone, Copy)]
struct ResidentState {
    generation: u64,
    fill_ordinal: u64,
    physical: PhysicalAddr,
    backing_generation: u64,
    backing_ordinal: u64,
    word: u32,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok {
        Ok(())
    } else {
        Err(message.into())
    }
}

fn cache_slot(vaddr: GuestVirtualAddr) -> u16 {
    ((vaddr.0 >> 5) & 0x1ff) as u16
}

fn validate_fill_address(
    vaddr: GuestVirtualAddr,
    physical: PhysicalAddr,
) -> Result<u16, String> {
    require(
        vaddr.0.is_multiple_of(4) && physical.0.is_multiple_of(4),
        "unaligned cache fill evidence",
    )?;
    let slot = cache_slot(vaddr);
    let index = (u32::from(slot) << 5) & 0xfe0;
    require(
        index == (physical.0 & 0xfe0),
        "cache fill virtual slot and physical index disagree",
    )?;
    Ok(slot)
}

fn cached_direct_physical(root: GuestVirtualAddr) -> Result<PhysicalAddr, String> {
    require(
        (0xffff_ffff_8000_0000..=0xffff_ffff_9fff_ffff).contains(&root.0),
        "exception root is not in the cached direct segment",
    )?;
    Ok(PhysicalAddr((root.0 & 0x1fff_ffff) as u32))
}

/// Recheck a bounded cached-root history against a separately trusted complete
/// source receipt.
///
/// The source hash authenticates this supplied finite history; it does not prove
/// the sensor was complete. Each fill must point to the exact live backing event,
/// and each root fetch must point to the exact live fill. A later equal or changed
/// backing generation cannot retroactively relabel resident code. A fill into the
/// same direct-mapped cache slot replaces the prior witness even when its physical
/// address differs. Missing or explicitly unknown residency evidence fails closed.
pub fn inspect_cached_exception_root_history(
    source: &[u8],
    expected_sha256: &str,
    root_receipt: ExceptionRootReceipt,
) -> Result<CachedExceptionRootReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "cached exception-root source receipt mismatch",
    )?;
    require(
        resolve_exception_root(root_receipt.input) == root_receipt,
        "forged exception-root receipt",
    )?;
    let root_physical = cached_direct_physical(root_receipt.root)?;
    let root_slot = validate_fill_address(root_receipt.root, root_physical)?;

    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported cached exception-root history format",
    )?;

    let mut backing = BTreeMap::<PhysicalAddr, BackingState>::new();
    let mut resident = BTreeMap::<u16, ResidentState>::new();
    let mut next_backing_generation = 0u64;
    let mut next_resident_generation = 0u64;
    let mut pending_transfer: Option<u64> = None;
    let mut witnesses = Vec::new();

    for (index, event) in history.events.iter().copied().enumerate() {
        let ordinal = event.ordinal();
        require(
            ordinal == index as u64 + 1,
            "noncontiguous cached exception-root ordinals",
        )?;
        match event {
            Event::BackingGeneration {
                physical, word, ..
            } => {
                next_backing_generation = next_backing_generation
                    .checked_add(1)
                    .ok_or("backing generation overflow")?;
                backing.insert(
                    physical,
                    BackingState {
                        generation: next_backing_generation,
                        ordinal,
                        word,
                    },
                );
            }
            Event::CacheFill {
                vaddr,
                physical,
                word,
                backing_ordinal,
                ..
            } => {
                let slot = validate_fill_address(vaddr, physical)?;
                let source_state = backing
                    .get(&physical)
                    .ok_or("cache fill without backing generation")?;
                require(
                    source_state.ordinal == backing_ordinal && source_state.word == word,
                    "cache fill source does not match live backing generation",
                )?;
                next_resident_generation = next_resident_generation
                    .checked_add(1)
                    .ok_or("resident generation overflow")?;
                resident.insert(
                    slot,
                    ResidentState {
                        generation: next_resident_generation,
                        fill_ordinal: ordinal,
                        physical,
                        backing_generation: source_state.generation,
                        backing_ordinal: source_state.ordinal,
                        word,
                    },
                );
            }
            Event::CacheInvalidate {
                vaddr,
                fill_ordinal,
                ..
            } => {
                let slot = cache_slot(vaddr);
                let current = resident
                    .get(&slot)
                    .ok_or("cache invalidation without resident generation")?;
                require(
                    current.fill_ordinal == fill_ordinal,
                    "cache invalidation targets the wrong resident generation",
                )?;
                resident.remove(&slot);
            }
            Event::ResidencyCut { vaddr, .. } => {
                resident.remove(&cache_slot(vaddr));
            }
            Event::RootTransfer { root, .. } => {
                require(root == root_receipt.root, "root transfer address mismatch")?;
                require(
                    pending_transfer.is_none(),
                    "root transfer occurred before prior root fetch completed",
                )?;
                pending_transfer = Some(ordinal);
            }
            Event::RootFetch {
                root,
                physical,
                word,
                fill_ordinal,
                ..
            } => {
                let transfer_ordinal = pending_transfer
                    .take()
                    .ok_or("root fetch without architectural transfer")?;
                require(
                    root == root_receipt.root && physical == root_physical,
                    "root fetch address does not match selected cached vector",
                )?;
                let current = resident
                    .get(&root_slot)
                    .ok_or("cached root fetch without resident provenance")?;
                require(
                    current.fill_ordinal == fill_ordinal
                        && current.physical == physical
                        && current.word == word,
                    "root fetch does not match the live resident generation",
                )?;
                witnesses.push(RootFetchWitness {
                    root,
                    physical,
                    word,
                    slot: root_slot,
                    transfer_ordinal,
                    fetch_ordinal: ordinal,
                    resident_generation: current.generation,
                    fill_ordinal: current.fill_ordinal,
                    backing_generation: current.backing_generation,
                    backing_ordinal: current.backing_ordinal,
                });
            }
        }
    }

    require(
        pending_transfer.is_none(),
        "root transfer has no authenticated handler fetch",
    )?;
    require(
        !witnesses.is_empty(),
        "cached exception-root history contains no root fetch witness",
    )?;

    Ok(CachedExceptionRootReport {
        format: FORMAT.into(),
        source_sha256: digest,
        events: history.events.len(),
        backing_generations: next_backing_generation,
        resident_generations: next_resident_generation,
        witnesses,
        reachability_certified: false,
        mapping_lifetime_certified: false,
        cache_lifetime_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::exception_roots::{ExceptionClass, ExceptionRootInput, KernelAddressMode};
    use serde_json::{json, Value};

    const ROOT_PA: u32 = 0x180;
    const ROOT_VA: u64 = 0xffff_ffff_8000_0180;

    fn root() -> ExceptionRootReceipt {
        resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        })
    }

    fn inspect(events: Vec<Value>) -> Result<CachedExceptionRootReport, String> {
        let bytes = serde_json::to_vec(&json!({
            "format": FORMAT,
            "events": events
        }))
        .unwrap();
        let digest = sha256(&bytes);
        inspect_cached_exception_root_history(&bytes, &digest, root())
    }

    fn backing(ordinal: u64, physical: u32, word: u32) -> Value {
        json!({
            "kind": "backing_generation",
            "ordinal": ordinal,
            "physical": physical,
            "word": word
        })
    }

    fn fill(
        ordinal: u64,
        vaddr: u64,
        physical: u32,
        word: u32,
        backing_ordinal: u64,
    ) -> Value {
        json!({
            "kind": "cache_fill",
            "ordinal": ordinal,
            "vaddr": vaddr,
            "physical": physical,
            "word": word,
            "backing_ordinal": backing_ordinal
        })
    }

    fn invalidate(ordinal: u64, vaddr: u64, fill_ordinal: u64) -> Value {
        json!({
            "kind": "cache_invalidate",
            "ordinal": ordinal,
            "vaddr": vaddr,
            "fill_ordinal": fill_ordinal
        })
    }

    fn cut(ordinal: u64, vaddr: u64) -> Value {
        json!({
            "kind": "residency_cut",
            "ordinal": ordinal,
            "vaddr": vaddr
        })
    }

    fn transfer(ordinal: u64) -> Value {
        json!({
            "kind": "root_transfer",
            "ordinal": ordinal,
            "root": root().root.0
        })
    }

    fn fetch(ordinal: u64, word: u32, fill_ordinal: u64) -> Value {
        json!({
            "kind": "root_fetch",
            "ordinal": ordinal,
            "root": root().root.0,
            "physical": ROOT_PA,
            "word": word,
            "fill_ordinal": fill_ordinal
        })
    }

    #[test]
    fn stale_resident_generation_survives_changed_backing() {
        let report = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            backing(3, ROOT_PA, 0x2402_0002),
            transfer(4),
            fetch(5, 0x2402_0001, 2),
        ])
        .unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(witness.backing_generation, 1);
        assert_eq!(witness.backing_ordinal, 1);
        assert_eq!(witness.resident_generation, 1);
        assert_eq!(witness.word, 0x2402_0001);
        assert_eq!(report.backing_generations, 2);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn invalidate_then_refill_moves_to_new_backing_generation() {
        let report = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            backing(3, ROOT_PA, 0x2402_0002),
            invalidate(4, ROOT_VA, 2),
            transfer(5),
            fill(6, ROOT_VA, ROOT_PA, 0x2402_0002, 3),
            fetch(7, 0x2402_0002, 6),
        ])
        .unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(witness.backing_generation, 2);
        assert_eq!(witness.backing_ordinal, 3);
        assert_eq!(witness.resident_generation, 2);
    }

    #[test]
    fn refill_before_later_write_remains_stale() {
        let report = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            invalidate(3, ROOT_VA, 2),
            fill(4, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            backing(5, ROOT_PA, 0x2402_0002),
            transfer(6),
            fetch(7, 0x2402_0001, 4),
        ])
        .unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(witness.resident_generation, 2);
        assert_eq!(witness.backing_generation, 1);
        assert_eq!(report.backing_generations, 2);
    }

    #[test]
    fn same_value_backing_replacement_does_not_relabel_resident_code() {
        let report = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            backing(3, ROOT_PA, 0x2402_0001),
            transfer(4),
            fetch(5, 0x2402_0001, 2),
        ])
        .unwrap();
        assert_eq!(report.backing_generations, 2);
        assert_eq!(report.witnesses[0].backing_generation, 1);
        assert_eq!(report.witnesses[0].backing_ordinal, 1);
    }

    #[test]
    fn index_conflicting_fill_replaces_root_resident_identity() {
        const OTHER_VA: u64 = ROOT_VA + 0x4000;
        const OTHER_PA: u32 = ROOT_PA + 0x4000;
        let error = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            backing(3, OTHER_PA, 0x2402_0001),
            fill(4, OTHER_VA, OTHER_PA, 0x2402_0001, 3),
            transfer(5),
            fetch(6, 0x2402_0001, 2),
        ])
        .unwrap_err();
        assert!(error.contains("live resident generation"));
    }

    #[test]
    fn equal_value_foreign_backing_cannot_be_stolen_as_fill_source() {
        let error = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            backing(2, ROOT_PA + 0x1000, 0x2402_0001),
            fill(3, ROOT_VA, ROOT_PA, 0x2402_0001, 2),
            transfer(4),
            fetch(5, 0x2402_0001, 3),
        ])
        .unwrap_err();
        assert!(error.contains("fill source"));
    }

    #[test]
    fn deleted_missing_or_unknown_resident_provenance_fails_closed() {
        let missing = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0002),
            transfer(2),
            fetch(3, 0x2402_0002, 1),
        ])
        .unwrap_err();
        assert!(missing.contains("resident provenance"));

        let cut_history = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            cut(3, ROOT_VA),
            transfer(4),
            fetch(5, 0x2402_0001, 2),
        ])
        .unwrap_err();
        assert!(cut_history.contains("resident provenance"));
    }

    #[test]
    fn wrong_equal_value_resident_generation_is_rejected() {
        let error = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            invalidate(3, ROOT_VA, 2),
            fill(4, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            transfer(5),
            fetch(6, 0x2402_0001, 2),
        ])
        .unwrap_err();
        assert!(error.contains("live resident generation"));
    }

    #[test]
    fn invalidation_must_name_exact_live_fill() {
        let error = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            invalidate(3, ROOT_VA, 1),
        ])
        .unwrap_err();
        assert!(error.contains("wrong resident generation"));
    }

    #[test]
    fn malformed_slot_relationship_and_reordered_history_are_rejected() {
        let slot_error = inspect(vec![
            backing(1, ROOT_PA + 0x20, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA + 0x20, 0x2402_0001, 1),
        ])
        .unwrap_err();
        assert!(slot_error.contains("physical index disagree"));

        let reordered = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(3, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            transfer(2),
            fetch(4, 0x2402_0001, 3),
        ])
        .unwrap_err();
        assert!(reordered.contains("noncontiguous"));
    }

    #[test]
    fn source_tampering_forged_root_and_bev_root_are_rejected() {
        let bytes = serde_json::to_vec(&json!({
            "format": FORMAT,
            "events": [
                backing(1, ROOT_PA, 0x2402_0001),
                fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
                transfer(3),
                fetch(4, 0x2402_0001, 2)
            ]
        }))
        .unwrap();
        let hash_error =
            inspect_cached_exception_root_history(&bytes, &"0".repeat(64), root()).unwrap_err();
        assert!(hash_error.contains("source receipt mismatch"));

        let mut forged = root();
        forged.root = GuestVirtualAddr(forged.root.0 + 4);
        let digest = sha256(&bytes);
        let forged_error =
            inspect_cached_exception_root_history(&bytes, &digest, forged).unwrap_err();
        assert!(forged_error.contains("forged exception-root receipt"));

        let bev = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        });
        let bev_error =
            inspect_cached_exception_root_history(&bytes, &digest, bev).unwrap_err();
        assert!(bev_error.contains("cached direct segment"));
    }

    #[test]
    fn transfer_without_fetch_is_not_silently_certified() {
        let error = inspect(vec![
            backing(1, ROOT_PA, 0x2402_0001),
            fill(2, ROOT_VA, ROOT_PA, 0x2402_0001, 1),
            transfer(3),
        ])
        .unwrap_err();
        assert!(error.contains("no authenticated handler fetch"));
    }
}
