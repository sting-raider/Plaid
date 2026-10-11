//! Source-bound replay for cached exception-root executable generations.
//!
//! The architectural vector selected by [`crate::exception_roots`] is not the
//! executable handler identity. This bounded verifier keeps backing generations,
//! resident I-cache generations, root transfers, and actual root fetches separate.
//! It intentionally creates no reachability, mutation-census, mapping-lifetime,
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
    /// Repeated equal values remain distinct generations because the event is distinct.
    BackingGeneration {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    /// A completed fill tied to one exact prior backing-generation event.
    CacheFill {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
        backing_ordinal: u64,
    },
    /// A completed invalidation of the exact currently resident fill.
    CacheInvalidate {
        ordinal: u64,
        physical: PhysicalAddr,
        fill_ordinal: u64,
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
/// and each root fetch must point to the exact live fill. Consequently a later
/// equal or changed backing generation cannot retroactively relabel resident code.
/// Missing resident/fill evidence fails closed.
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
    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported cached exception-root history format",
    )?;

    let mut backing = BTreeMap::<PhysicalAddr, BackingState>::new();
    let mut resident = BTreeMap::<PhysicalAddr, ResidentState>::new();
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
                physical,
                word,
                backing_ordinal,
                ..
            } => {
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
                    physical,
                    ResidentState {
                        generation: next_resident_generation,
                        fill_ordinal: ordinal,
                        backing_generation: source_state.generation,
                        backing_ordinal: source_state.ordinal,
                        word,
                    },
                );
            }
            Event::CacheInvalidate {
                physical,
                fill_ordinal,
                ..
            } => {
                let current = resident
                    .get(&physical)
                    .ok_or("cache invalidation without resident generation")?;
                require(
                    current.fill_ordinal == fill_ordinal,
                    "cache invalidation targets the wrong resident generation",
                )?;
                resident.remove(&physical);
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
                    .get(&physical)
                    .ok_or("cached root fetch without resident provenance")?;
                require(
                    current.fill_ordinal == fill_ordinal && current.word == word,
                    "root fetch does not match the live resident generation",
                )?;
                witnesses.push(RootFetchWitness {
                    root,
                    physical,
                    word,
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

    fn root() -> ExceptionRootReceipt {
        resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        })
    }

    fn inspect(events: Vec<Value>) -> Result<CachedExceptionRootReport, String> {
        let bytes = serde_json::to_vec(&json!({ "format": FORMAT, "events": events })).unwrap();
        let digest = sha256(&bytes);
        inspect_cached_exception_root_history(&bytes, &digest, root())
    }

    fn backing(ordinal: u64, physical: u32, word: u32) -> Value {
        json!({"kind":"backing_generation","ordinal":ordinal,"physical":physical,"word":word})
    }

    fn fill(ordinal: u64, physical: u32, word: u32, backing_ordinal: u64) -> Value {
        json!({"kind":"cache_fill","ordinal":ordinal,"physical":physical,"word":word,"backing_ordinal":backing_ordinal})
    }

    fn invalidate(ordinal: u64, physical: u32, fill_ordinal: u64) -> Value {
        json!({"kind":"cache_invalidate","ordinal":ordinal,"physical":physical,"fill_ordinal":fill_ordinal})
    }

    fn transfer(ordinal: u64) -> Value {
        json!({"kind":"root_transfer","ordinal":ordinal,"root":root().root.0})
    }

    fn fetch(ordinal: u64, word: u32, fill_ordinal: u64) -> Value {
        json!({"kind":"root_fetch","ordinal":ordinal,"root":root().root.0,"physical":0x180,"word":word,"fill_ordinal":fill_ordinal})
    }

    #[test]
    fn stale_resident_generation_survives_changed_backing() {
        let report = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            backing(3, 0x180, 0x2402_0002),
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
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            backing(3, 0x180, 0x2402_0002),
            invalidate(4, 0x180, 2),
            transfer(5),
            fill(6, 0x180, 0x2402_0002, 3),
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
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            invalidate(3, 0x180, 2),
            fill(4, 0x180, 0x2402_0001, 1),
            backing(5, 0x180, 0x2402_0002),
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
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            backing(3, 0x180, 0x2402_0001),
            transfer(4),
            fetch(5, 0x2402_0001, 2),
        ])
        .unwrap();
        assert_eq!(report.backing_generations, 2);
        assert_eq!(report.witnesses[0].backing_generation, 1);
        assert_eq!(report.witnesses[0].backing_ordinal, 1);
    }

    #[test]
    fn equal_value_foreign_backing_cannot_be_stolen_as_fill_source() {
        let error = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            backing(2, 0x1180, 0x2402_0001),
            fill(3, 0x180, 0x2402_0001, 2),
            transfer(4),
            fetch(5, 0x2402_0001, 3),
        ])
        .unwrap_err();
        assert!(error.contains("fill source"));
    }

    #[test]
    fn deleted_or_missing_resident_provenance_fails_closed() {
        let error = inspect(vec![
            backing(1, 0x180, 0x2402_0002),
            transfer(2),
            fetch(3, 0x2402_0002, 1),
        ])
        .unwrap_err();
        assert!(error.contains("resident provenance"));
    }

    #[test]
    fn wrong_equal_value_resident_generation_is_rejected() {
        let error = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            invalidate(3, 0x180, 2),
            fill(4, 0x180, 0x2402_0001, 1),
            transfer(5),
            fetch(6, 0x2402_0001, 2),
        ])
        .unwrap_err();
        assert!(error.contains("live resident generation"));
    }

    #[test]
    fn invalidation_must_name_exact_live_fill() {
        let error = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            invalidate(3, 0x180, 1),
        ])
        .unwrap_err();
        assert!(error.contains("wrong resident generation"));
    }

    #[test]
    fn reordered_history_and_source_tampering_are_rejected() {
        let reordered = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            fill(3, 0x180, 0x2402_0001, 1),
            transfer(2),
            fetch(4, 0x2402_0001, 3),
        ])
        .unwrap_err();
        assert!(reordered.contains("noncontiguous"));

        let bytes = serde_json::to_vec(&json!({
            "format": FORMAT,
            "events": [
                backing(1, 0x180, 0x2402_0001),
                fill(2, 0x180, 0x2402_0001, 1),
                transfer(3),
                fetch(4, 0x2402_0001, 2)
            ]
        }))
        .unwrap();
        let error = inspect_cached_exception_root_history(&bytes, &"0".repeat(64), root())
            .unwrap_err();
        assert!(error.contains("source receipt mismatch"));
    }

    #[test]
    fn forged_root_receipt_and_uncached_bev_root_are_rejected() {
        let mut forged = root();
        forged.root = GuestVirtualAddr(forged.root.0 + 4);
        let bytes = serde_json::to_vec(&json!({"format":FORMAT,"events":[]})).unwrap();
        let digest = sha256(&bytes);
        let error = inspect_cached_exception_root_history(&bytes, &digest, forged).unwrap_err();
        assert!(error.contains("forged exception-root receipt"));

        let bev = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        });
        let error = inspect_cached_exception_root_history(&bytes, &digest, bev).unwrap_err();
        assert!(error.contains("cached direct segment"));
    }

    #[test]
    fn transfer_without_fetch_is_not_silently_certified() {
        let error = inspect(vec![
            backing(1, 0x180, 0x2402_0001),
            fill(2, 0x180, 0x2402_0001, 1),
            transfer(3),
        ])
        .unwrap_err();
        assert!(error.contains("no authenticated handler fetch"));
    }
}
