//! Bounded replay for cached exception-root executable identity.
//!
//! This source-bound consumer composes an already-rechecked architectural
//! exception root with an ordered identity-RDRAM backing/fill/fetch history. It
//! deliberately does not infer resident bytes from the vector address, current
//! backing contents, or equal payloads. Successful replay is not a mutation
//! census, executable-lifetime proof, root-set proof, or native-complete claim.
use crate::{
    exception_roots::{
        ExceptionClass, ExceptionRootReceipt, ExceptionVectorClass, resolve_exception_root,
    },
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-exception-root-history-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    BackingWrite {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    Fill {
        ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
    },
    Invalidate {
        ordinal: u64,
        physical: PhysicalAddr,
    },
    RootFetch {
        ordinal: u64,
        pc: GuestVirtualAddr,
        physical: PhysicalAddr,
        cached: bool,
        word: u32,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::BackingWrite { ordinal, .. }
            | Self::Fill { ordinal, .. }
            | Self::Invalidate { ordinal, .. }
            | Self::RootFetch { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Clone, Copy)]
struct Backing {
    generation: u64,
    write_ordinal: u64,
    word: u32,
}

#[derive(Debug, Clone, Copy)]
struct Resident {
    physical: PhysicalAddr,
    generation: u64,
    fill_ordinal: u64,
    word: u32,
    source: Option<Backing>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RootHistoryUnknownReason {
    MissingResidentGeneration,
    MissingBackingGenerationForResident,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CachedExceptionRootBinding {
    pub root: ExceptionRootReceipt,
    pub fetch_ordinal: u64,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub resident_generation: u64,
    pub fill_ordinal: u64,
    pub backing_generation_at_fill: u64,
    pub backing_write_ordinal_at_fill: u64,
    /// Diagnostic current backing generation at fetch time. This is not the
    /// cached fetch source and may be newer than `backing_generation_at_fill`.
    pub current_backing_generation: Option<u64>,
    pub current_backing_write_ordinal: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case", deny_unknown_fields)]
pub enum ExceptionRootFetchResolution {
    Bound {
        binding: CachedExceptionRootBinding,
    },
    Unknown {
        reason: RootHistoryUnknownReason,
        fetch_ordinal: u64,
        physical: PhysicalAddr,
        word: u32,
        current_backing_generation: Option<u64>,
        current_backing_write_ordinal: Option<u64>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExceptionRootHistoryReport {
    pub format: String,
    pub scope: String,
    pub source_sha256: String,
    pub root: ExceptionRootReceipt,
    pub records: u64,
    pub backing_generations: u64,
    pub resident_generations: u64,
    pub resolution: ExceptionRootFetchResolution,
    pub ultimate_byte_origin_certified: bool,
    pub mutation_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub root_set_complete: bool,
    pub native_complete: bool,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn valid_identity_rdram_word(physical: PhysicalAddr) -> bool {
    physical.0 <= 0x007f_fffc && physical.0.is_multiple_of(4)
}

// The VR4300 instruction cache is 16 KiB, direct-mapped, with 32-byte lines.
// Within this bounded identity-RDRAM scope, these nine index bits determine the
// resident slot. Physical identity remains separate and is checked at fetch.
fn icache_slot(physical: PhysicalAddr) -> u16 {
    ((physical.0 >> 5) & 0x01ff) as u16
}

fn direct_physical(root: GuestVirtualAddr) -> PhysicalAddr {
    PhysicalAddr((root.0 & 0x1fff_ffff) as u32)
}

/// Recheck a finite, source-bound cache history for one validated BEV=0 general
/// exception root.
///
/// The expected hash must come from a separately trusted complete-source receipt.
/// This function authenticates the supplied bytes against that receipt and then
/// replays generations from operation chronology. It mints a backing generation
/// for every observed write even when the value is unchanged, and a resident
/// generation for every completed fill. A cached root fetch binds only to the
/// currently resident generation and that fill's backing generation. Current
/// backing state is retained only as a diagnostic and can never substitute for
/// missing resident/fill evidence.
///
/// The bounded production scope intentionally accepts only the dynamically
/// validated BEV=0 general-vector, identity-RDRAM cached case. TLB refill roots,
/// BEV=1, aliases/mappings, restore epochs and broader cache behavior remain
/// separate obligations.
pub fn inspect_cached_general_exception_root_history(
    source: &[u8],
    expected_sha256: &str,
    root: ExceptionRootReceipt,
) -> Result<ExceptionRootHistoryReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "exception-root history source receipt mismatch",
    )?;
    require(
        resolve_exception_root(root.input) == root,
        "exception-root receipt does not recheck",
    )?;
    require(
        !root.input.bev
            && !root.input.exl
            && root.input.class == ExceptionClass::General
            && root.vector_class == ExceptionVectorClass::General,
        "unsupported exception-root history scope",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported exception-root history format",
    )?;
    require(!history.events.is_empty(), "empty exception-root history")?;

    let expected_physical = direct_physical(root.root);
    require(
        valid_identity_rdram_word(expected_physical),
        "exception root is outside bounded identity-RDRAM scope",
    )?;

    let mut backing = BTreeMap::<PhysicalAddr, Backing>::new();
    let mut resident = BTreeMap::<u16, Resident>::new();
    let mut backing_generation = 0u64;
    let mut resident_generation = 0u64;
    let mut resolution = None;

    for (index, event) in history.events.iter().enumerate() {
        let ordinal = event.ordinal();
        require(
            ordinal == index as u64 + 1,
            "noncontiguous exception-root history ordinals",
        )?;
        require(
            resolution.is_none(),
            "event appears after exception-root fetch",
        )?;
        match *event {
            Event::BackingWrite { physical, word, .. } => {
                require(
                    valid_identity_rdram_word(physical),
                    "invalid identity-RDRAM backing write",
                )?;
                backing_generation += 1;
                backing.insert(
                    physical,
                    Backing {
                        generation: backing_generation,
                        write_ordinal: ordinal,
                        word,
                    },
                );
            }
            Event::Fill { physical, word, .. } => {
                require(
                    valid_identity_rdram_word(physical),
                    "invalid identity-RDRAM cache fill",
                )?;
                let source = backing.get(&physical).copied();
                if let Some(source) = source {
                    require(
                        source.word == word,
                        "cache fill payload disagrees with current backing generation",
                    )?;
                }
                resident_generation += 1;
                resident.insert(
                    icache_slot(physical),
                    Resident {
                        physical,
                        generation: resident_generation,
                        fill_ordinal: ordinal,
                        word,
                        source,
                    },
                );
            }
            Event::Invalidate { physical, .. } => {
                require(
                    valid_identity_rdram_word(physical),
                    "invalid identity-RDRAM cache invalidation",
                )?;
                resident.remove(&icache_slot(physical));
            }
            Event::RootFetch {
                pc,
                physical,
                cached,
                word,
                ..
            } => {
                require(
                    cached
                        && pc == root.root
                        && physical == expected_physical
                        && valid_identity_rdram_word(physical),
                    "root fetch does not match bounded cached exception root",
                )?;
                let current = backing.get(&physical).copied();
                let resident_line = resident
                    .get(&icache_slot(physical))
                    .copied()
                    .filter(|line| line.physical == physical);
                resolution = Some(match resident_line {
                    None => ExceptionRootFetchResolution::Unknown {
                        reason: RootHistoryUnknownReason::MissingResidentGeneration,
                        fetch_ordinal: ordinal,
                        physical,
                        word,
                        current_backing_generation: current.map(|b| b.generation),
                        current_backing_write_ordinal: current.map(|b| b.write_ordinal),
                    },
                    Some(line) => {
                        require(
                            line.fill_ordinal < ordinal && line.word == word,
                            "root fetch payload/order disagrees with resident generation",
                        )?;
                        match line.source {
                            None => ExceptionRootFetchResolution::Unknown {
                                reason:
                                    RootHistoryUnknownReason::MissingBackingGenerationForResident,
                                fetch_ordinal: ordinal,
                                physical,
                                word,
                                current_backing_generation: current.map(|b| b.generation),
                                current_backing_write_ordinal: current.map(|b| b.write_ordinal),
                            },
                            Some(source) => ExceptionRootFetchResolution::Bound {
                                binding: CachedExceptionRootBinding {
                                    root,
                                    fetch_ordinal: ordinal,
                                    physical,
                                    word,
                                    resident_generation: line.generation,
                                    fill_ordinal: line.fill_ordinal,
                                    backing_generation_at_fill: source.generation,
                                    backing_write_ordinal_at_fill: source.write_ordinal,
                                    current_backing_generation: current.map(|b| b.generation),
                                    current_backing_write_ordinal: current.map(|b| b.write_ordinal),
                                },
                            },
                        }
                    }
                });
            }
        }
    }

    let resolution = resolution.ok_or("missing exception-root fetch")?;
    Ok(ExceptionRootHistoryReport {
        format: "plaid-exception-root-history-report-v0".into(),
        scope: "bev0_general_identity_rdram_cached_root".into(),
        source_sha256: digest,
        root,
        records: history.events.len() as u64,
        backing_generations: backing_generation,
        resident_generations: resident_generation,
        resolution,
        ultimate_byte_origin_certified: false,
        mutation_coverage_certified: false,
        executable_lifetime_certified: false,
        root_set_complete: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::exception_roots::{ExceptionClass, ExceptionRootInput, KernelAddressMode};

    const ROOT: GuestVirtualAddr = GuestVirtualAddr(0xffff_ffff_8000_0180);
    const PHYS: PhysicalAddr = PhysicalAddr(0x180);
    const OLD: u32 = 0x2402_0001;
    const NEW: u32 = 0x2402_0002;

    fn root() -> ExceptionRootReceipt {
        resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        })
    }

    fn inspect(events: Vec<Event>) -> Result<ExceptionRootHistoryReport, String> {
        let source = serde_json::to_vec(&History {
            format: FORMAT.into(),
            events,
        })
        .unwrap();
        let digest = sha256(&source);
        inspect_cached_general_exception_root_history(&source, &digest, root())
    }

    fn bound(report: &ExceptionRootHistoryReport) -> &CachedExceptionRootBinding {
        let ExceptionRootFetchResolution::Bound { binding } = &report.resolution else {
            panic!("expected bound root fetch");
        };
        binding
    }

    #[test]
    fn stale_resident_beats_newer_current_backing() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 3,
                physical: PHYS,
                word: NEW,
            },
            Event::RootFetch {
                ordinal: 4,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        let binding = bound(&report);
        assert_eq!(binding.resident_generation, 1);
        assert_eq!(binding.backing_generation_at_fill, 1);
        assert_eq!(binding.current_backing_generation, Some(2));
        assert_eq!(binding.word, OLD);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn post_write_refill_moves_binding_to_new_backing_generation() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 3,
                physical: PHYS,
                word: NEW,
            },
            Event::Invalidate {
                ordinal: 4,
                physical: PHYS,
            },
            Event::Fill {
                ordinal: 5,
                physical: PHYS,
                word: NEW,
            },
            Event::RootFetch {
                ordinal: 6,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: NEW,
            },
        ])
        .unwrap();
        let binding = bound(&report);
        assert_eq!(binding.resident_generation, 2);
        assert_eq!(binding.backing_generation_at_fill, 2);
        assert_eq!(binding.current_backing_generation, Some(2));
    }

    #[test]
    fn refill_before_write_remains_stale() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::Invalidate {
                ordinal: 3,
                physical: PHYS,
            },
            Event::Fill {
                ordinal: 4,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 5,
                physical: PHYS,
                word: NEW,
            },
            Event::RootFetch {
                ordinal: 6,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        let binding = bound(&report);
        assert_eq!(binding.resident_generation, 2);
        assert_eq!(binding.backing_generation_at_fill, 1);
        assert_eq!(binding.current_backing_generation, Some(2));
    }

    #[test]
    fn same_value_rewrite_still_mints_new_backing_generation() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 3,
                physical: PHYS,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 4,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        let binding = bound(&report);
        assert_eq!(report.backing_generations, 2);
        assert_eq!(binding.backing_generation_at_fill, 1);
        assert_eq!(binding.current_backing_generation, Some(2));
    }

    #[test]
    fn current_backing_without_resident_stays_unknown() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: NEW,
            },
            Event::RootFetch {
                ordinal: 2,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: NEW,
            },
        ])
        .unwrap();
        assert_eq!(
            report.resolution,
            ExceptionRootFetchResolution::Unknown {
                reason: RootHistoryUnknownReason::MissingResidentGeneration,
                fetch_ordinal: 2,
                physical: PHYS,
                word: NEW,
                current_backing_generation: Some(1),
                current_backing_write_ordinal: Some(1),
            }
        );
    }

    #[test]
    fn fill_without_backing_ancestry_stays_unknown() {
        let report = inspect(vec![
            Event::Fill {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 2,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        assert_eq!(
            report.resolution,
            ExceptionRootFetchResolution::Unknown {
                reason: RootHistoryUnknownReason::MissingBackingGenerationForResident,
                fetch_ordinal: 2,
                physical: PHYS,
                word: OLD,
                current_backing_generation: None,
                current_backing_write_ordinal: None,
            }
        );
    }

    #[test]
    fn invalidation_without_refill_keeps_cached_root_unknown() {
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::Invalidate {
                ordinal: 3,
                physical: PHYS,
            },
            Event::RootFetch {
                ordinal: 4,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        assert!(matches!(
            report.resolution,
            ExceptionRootFetchResolution::Unknown {
                reason: RootHistoryUnknownReason::MissingResidentGeneration,
                ..
            }
        ));
    }

    #[test]
    fn equal_value_decoy_at_other_backing_cannot_steal_lineage() {
        let decoy = PhysicalAddr(0x1180);
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 3,
                physical: decoy,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 4,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        let binding = bound(&report);
        assert_eq!(binding.backing_generation_at_fill, 1);
        assert_eq!(binding.current_backing_generation, Some(1));
        assert_eq!(report.backing_generations, 2);
    }

    #[test]
    fn conflicting_direct_mapped_fill_evicts_equal_value_root_residency() {
        let alias = PhysicalAddr(0x4180);
        assert_eq!(icache_slot(PHYS), icache_slot(alias));
        let report = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::BackingWrite {
                ordinal: 3,
                physical: alias,
                word: OLD,
            },
            Event::Fill {
                ordinal: 4,
                physical: alias,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 5,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap();
        assert!(matches!(
            report.resolution,
            ExceptionRootFetchResolution::Unknown {
                reason: RootHistoryUnknownReason::MissingResidentGeneration,
                ..
            }
        ));
    }

    #[test]
    fn tampered_source_hash_and_reordered_ordinals_are_rejected() {
        let events = vec![
            Event::BackingWrite {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 1,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ];
        let source = serde_json::to_vec(&History {
            format: FORMAT.into(),
            events,
        })
        .unwrap();
        let digest = sha256(&source);
        assert!(
            inspect_cached_general_exception_root_history(&source, &digest, root())
                .unwrap_err()
                .contains("ordinals")
        );
        assert!(
            inspect_cached_general_exception_root_history(&source, &"0".repeat(64), root())
                .unwrap_err()
                .contains("receipt mismatch")
        );
    }

    #[test]
    fn wrong_root_or_resident_payload_is_rejected() {
        let wrong_root = GuestVirtualAddr(ROOT.0 + 4);
        let error = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 3,
                pc: wrong_root,
                physical: PHYS,
                cached: true,
                word: OLD,
            },
        ])
        .unwrap_err();
        assert!(error.contains("does not match"));

        let error = inspect(vec![
            Event::BackingWrite {
                ordinal: 1,
                physical: PHYS,
                word: OLD,
            },
            Event::Fill {
                ordinal: 2,
                physical: PHYS,
                word: OLD,
            },
            Event::RootFetch {
                ordinal: 3,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: NEW,
            },
        ])
        .unwrap_err();
        assert!(error.contains("payload/order"));
    }

    #[test]
    fn unsupported_bev_or_tlb_refill_scope_is_rejected() {
        let source = serde_json::to_vec(&History {
            format: FORMAT.into(),
            events: vec![Event::RootFetch {
                ordinal: 1,
                pc: ROOT,
                physical: PHYS,
                cached: true,
                word: OLD,
            }],
        })
        .unwrap();
        let digest = sha256(&source);
        let bev = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        });
        assert!(
            inspect_cached_general_exception_root_history(&source, &digest, bev)
                .unwrap_err()
                .contains("unsupported")
        );
        let refill = resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::TlbMiss,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        });
        assert!(
            inspect_cached_general_exception_root_history(&source, &digest, refill)
                .unwrap_err()
                .contains("unsupported")
        );
    }
}
