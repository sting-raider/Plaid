//! Fail-closed composition of bounded NMI root-transfer, fetch, and byte-source evidence.
//!
//! A numeric NMI root is not execution evidence. This module consumes an ordered,
//! capture-bound finite history and only certifies the first root word when the
//! architectural transfer, observed progress to a fetch, and an in-context PIF-ROM
//! backing read all compose causally. It does not prove NMI producer/deassertion
//! completeness, hardware reset timing, executable lifetime, or whole-ROM closure.

use crate::program::{GuestVirtualAddr, PhysicalAddr};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

pub const NMI_ROOT: GuestVirtualAddr = GuestVirtualAddr(0xffff_ffff_bfc0_0000);
pub const NMI_ROOT_PHYSICAL: PhysicalAddr = PhysicalAddr(0x1fc0_0000);
pub const NMI_ROOT_PIF_OFFSET: u32 = 0;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RootFetchSource {
    PifRom,
    SiLatch,
    PifLockout,
    Unknown,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum NmiRootRecord {
    Transfer {
        ordinal: u64,
        root: GuestVirtualAddr,
    },
    Pending {
        ordinal: u64,
        pending: bool,
    },
    FetchBegin {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        physical: PhysicalAddr,
        cached: bool,
    },
    PifRomRead {
        ordinal: u64,
        context: u64,
        offset: u32,
        word: u32,
    },
    FetchEnd {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        physical: PhysicalAddr,
        word: u32,
        source: RootFetchSource,
    },
}

impl NmiRootRecord {
    fn ordinal(&self) -> u64 {
        match self {
            Self::Transfer { ordinal, .. }
            | Self::Pending { ordinal, .. }
            | Self::FetchBegin { ordinal, .. }
            | Self::PifRomRead { ordinal, .. }
            | Self::FetchEnd { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootHistory {
    /// SHA-256 of the complete external capture that supplied these records.
    ///
    /// This binds receipts to one source namespace. The caller must independently
    /// recheck that capture; this verifier does not turn a hash string into source
    /// completeness.
    pub capture_sha256: String,
    pub records: Vec<NmiRootRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootExecutionReceipt {
    pub capture_sha256: String,
    pub transfer_ordinal: u64,
    pub deassert_ordinal: u64,
    pub fetch_begin_ordinal: u64,
    pub source_read_ordinal: u64,
    pub fetch_end_ordinal: u64,
    pub context: u64,
    pub root: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub pif_offset: u32,
    pub word: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootExecutionReport {
    pub capture_sha256: String,
    pub transfers: u64,
    pub root_fetches: u64,
    pub certified_fetches: Vec<NmiRootExecutionReceipt>,
    pub unresolved_transfers: u64,
    pub nmi_lifecycle_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, Copy)]
struct SourceRead {
    ordinal: u64,
    word: u32,
}

#[derive(Debug, Clone, Copy)]
struct ActiveFetch {
    transfer_ordinal: u64,
    deassert_ordinal: u64,
    begin_ordinal: u64,
    context: u64,
    witness: Option<SourceRead>,
    ambiguous_source: bool,
}

fn valid_sha256(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Verify one externally source-bound finite NMI-root chronology.
///
/// Records must retain their original contiguous ordinals. A transfer becomes
/// eligible for a root fetch only after an explicit observed `pending=false`
/// boundary. The first root word is attributed to PIF ROM only when an actual
/// offset-zero PIF read occurs inside the same unique fetch context before a
/// matching `PifRom` fetch completion. Equal words, root addresses, foreign reads,
/// or earlier transfers never substitute for that causal chain.
pub fn verify_nmi_root_history(history: &NmiRootHistory) -> Result<NmiRootExecutionReport, String> {
    require(
        valid_sha256(&history.capture_sha256),
        "invalid capture SHA-256",
    )?;
    require(!history.records.is_empty(), "empty NMI root history")?;

    let mut transfers = 0_u64;
    let mut root_fetches = 0_u64;
    let mut certificates = Vec::new();
    let mut current_transfer = None;
    let mut deassert_ordinal = None;
    let mut active: Option<ActiveFetch> = None;
    let mut used_contexts = BTreeSet::new();

    for (index, record) in history.records.iter().enumerate() {
        let expected = u64::try_from(index)
            .map_err(|_| "NMI history index exceeds u64".to_string())?
            .checked_add(1)
            .ok_or_else(|| "NMI history ordinal overflow".to_string())?;
        require(
            record.ordinal() == expected,
            "NMI root history ordinal gap/reorder",
        )?;

        match record {
            NmiRootRecord::Transfer { ordinal, root } => {
                require(*root == NMI_ROOT, "unexpected NMI architectural root")?;
                require(
                    active.is_none(),
                    "NMI transfer overlaps an active root fetch",
                )?;
                transfers += 1;
                current_transfer = Some(*ordinal);
                deassert_ordinal = None;
            }
            NmiRootRecord::Pending { ordinal, pending } => {
                require(active.is_none(), "NMI pending transition inside root fetch")?;
                if current_transfer.is_some() {
                    deassert_ordinal = if *pending { None } else { Some(*ordinal) };
                }
            }
            NmiRootRecord::FetchBegin {
                ordinal,
                context,
                pc,
                physical,
                cached,
            } => {
                require(active.is_none(), "overlapping NMI root fetch contexts")?;
                require(*context != 0, "zero NMI root fetch context")?;
                require(
                    used_contexts.insert(*context),
                    "reused NMI root fetch context",
                )?;
                require(*pc == NMI_ROOT, "unexpected NMI root fetch PC")?;
                require(
                    *physical == NMI_ROOT_PHYSICAL,
                    "unexpected NMI root physical address",
                )?;
                require(!cached, "NMI PIF root fetch must be uncached in this scope")?;

                if let (Some(transfer_ordinal), Some(deassert_ordinal)) =
                    (current_transfer, deassert_ordinal)
                {
                    active = Some(ActiveFetch {
                        transfer_ordinal,
                        deassert_ordinal,
                        begin_ordinal: *ordinal,
                        context: *context,
                        witness: None,
                        ambiguous_source: false,
                    });
                }
            }
            NmiRootRecord::PifRomRead {
                ordinal,
                context,
                offset,
                word,
            } => {
                let matching = active
                    .as_mut()
                    .filter(|fetch| fetch.context == *context && *offset == NMI_ROOT_PIF_OFFSET);
                if let Some(fetch) = matching {
                    if fetch.witness.is_some() {
                        fetch.ambiguous_source = true;
                    } else {
                        fetch.witness = Some(SourceRead {
                            ordinal: *ordinal,
                            word: *word,
                        });
                    }
                }
            }
            NmiRootRecord::FetchEnd {
                ordinal,
                context,
                pc,
                physical,
                word,
                source,
            } => {
                require(*pc == NMI_ROOT, "unexpected completed NMI root fetch PC")?;
                require(
                    *physical == NMI_ROOT_PHYSICAL,
                    "unexpected completed NMI root physical address",
                )?;
                root_fetches += 1;

                if let Some(fetch) = active.take() {
                    require(fetch.context == *context, "NMI root fetch context mismatch")?;
                    let witness = if *source == RootFetchSource::PifRom && !fetch.ambiguous_source {
                        fetch.witness.filter(|candidate| candidate.word == *word)
                    } else {
                        None
                    };
                    if let Some(witness) = witness {
                        certificates.push(NmiRootExecutionReceipt {
                            capture_sha256: history.capture_sha256.clone(),
                            transfer_ordinal: fetch.transfer_ordinal,
                            deassert_ordinal: fetch.deassert_ordinal,
                            fetch_begin_ordinal: fetch.begin_ordinal,
                            source_read_ordinal: witness.ordinal,
                            fetch_end_ordinal: *ordinal,
                            context: *context,
                            root: *pc,
                            physical: *physical,
                            pif_offset: NMI_ROOT_PIF_OFFSET,
                            word: *word,
                        });
                    }
                }
                current_transfer = None;
                deassert_ordinal = None;
            }
        }
    }

    require(active.is_none(), "truncated NMI root fetch context")?;
    let certified = u64::try_from(certificates.len())
        .map_err(|_| "too many NMI root certificates".to_string())?;
    let unresolved_transfers = transfers.saturating_sub(certified);

    Ok(NmiRootExecutionReport {
        capture_sha256: history.capture_sha256.clone(),
        transfers,
        root_fetches,
        certified_fetches: certificates,
        unresolved_transfers,
        nmi_lifecycle_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const HASH: &str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
    const WORD: u32 = 0x3c09_3400;

    fn history(records: Vec<NmiRootRecord>) -> NmiRootHistory {
        NmiRootHistory {
            capture_sha256: HASH.into(),
            records,
        }
    }

    fn transfer(ordinal: u64) -> NmiRootRecord {
        NmiRootRecord::Transfer {
            ordinal,
            root: NMI_ROOT,
        }
    }

    fn pending(ordinal: u64, value: bool) -> NmiRootRecord {
        NmiRootRecord::Pending {
            ordinal,
            pending: value,
        }
    }

    fn begin(ordinal: u64, context: u64) -> NmiRootRecord {
        NmiRootRecord::FetchBegin {
            ordinal,
            context,
            pc: NMI_ROOT,
            physical: NMI_ROOT_PHYSICAL,
            cached: false,
        }
    }

    fn read(ordinal: u64, context: u64, offset: u32, word: u32) -> NmiRootRecord {
        NmiRootRecord::PifRomRead {
            ordinal,
            context,
            offset,
            word,
        }
    }

    fn end(ordinal: u64, context: u64, word: u32, source: RootFetchSource) -> NmiRootRecord {
        NmiRootRecord::FetchEnd {
            ordinal,
            context,
            pc: NMI_ROOT,
            physical: NMI_ROOT_PHYSICAL,
            word,
            source,
        }
    }

    #[test]
    fn certifies_only_the_source_bound_positive_chain() {
        let report = verify_nmi_root_history(&history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            read(4, 7, 0, WORD),
            end(5, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert_eq!(report.transfers, 1);
        assert_eq!(report.root_fetches, 1);
        assert_eq!(report.unresolved_transfers, 0);
        assert_eq!(report.certified_fetches.len(), 1);
        let receipt = &report.certified_fetches[0];
        assert_eq!(receipt.transfer_ordinal, 1);
        assert_eq!(receipt.deassert_ordinal, 2);
        assert_eq!(receipt.fetch_begin_ordinal, 3);
        assert_eq!(receipt.source_read_ordinal, 4);
        assert_eq!(receipt.fetch_end_ordinal, 5);
        assert_eq!(receipt.context, 7);
        assert_eq!(receipt.word, WORD);
        assert!(!report.nmi_lifecycle_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn transfer_only_and_persistent_reentry_stay_unresolved() {
        let transfer_only = verify_nmi_root_history(&history(vec![transfer(1)])).unwrap();
        assert!(transfer_only.certified_fetches.is_empty());
        assert_eq!(transfer_only.unresolved_transfers, 1);

        let persistent = verify_nmi_root_history(&history(vec![transfer(1), transfer(2)])).unwrap();
        assert!(persistent.certified_fetches.is_empty());
        assert_eq!(persistent.transfers, 2);
        assert_eq!(persistent.root_fetches, 0);
        assert_eq!(persistent.unresolved_transfers, 2);
    }

    #[test]
    fn equal_foreign_read_or_equal_si_latch_payload_cannot_supply_provenance() {
        let foreign = verify_nmi_root_history(&history(vec![
            read(1, 3, 0, WORD),
            transfer(2),
            pending(3, false),
            begin(4, 7),
            end(5, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(foreign.certified_fetches.is_empty());
        assert_eq!(foreign.root_fetches, 1);

        let latch = verify_nmi_root_history(&history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            end(4, 7, WORD, RootFetchSource::SiLatch),
        ]))
        .unwrap();
        assert!(latch.certified_fetches.is_empty());
        assert_eq!(latch.unresolved_transfers, 1);
    }

    #[test]
    fn pending_wrong_context_wrong_offset_and_ambiguous_reads_fail_closed() {
        let while_pending = verify_nmi_root_history(&history(vec![
            transfer(1),
            begin(2, 7),
            read(3, 7, 0, WORD),
            end(4, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(while_pending.certified_fetches.is_empty());

        let wrong_context = verify_nmi_root_history(&history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            read(4, 8, 0, WORD),
            end(5, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(wrong_context.certified_fetches.is_empty());

        let wrong_offset = verify_nmi_root_history(&history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            read(4, 7, 4, WORD),
            end(5, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(wrong_offset.certified_fetches.is_empty());

        let ambiguous = verify_nmi_root_history(&history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            read(4, 7, 0, WORD),
            read(5, 7, 0, WORD),
            end(6, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(ambiguous.certified_fetches.is_empty());
    }

    #[test]
    fn source_word_mismatch_does_not_get_repaired_by_payload_equality_elsewhere() {
        let report = verify_nmi_root_history(&history(vec![
            read(1, 3, 0, WORD),
            transfer(2),
            pending(3, false),
            begin(4, 7),
            read(5, 7, 0, WORD ^ 1),
            end(6, 7, WORD, RootFetchSource::PifRom),
        ]))
        .unwrap();
        assert!(report.certified_fetches.is_empty());
        assert_eq!(report.unresolved_transfers, 1);
    }

    #[test]
    fn deleted_reordered_and_reused_context_histories_are_rejected() {
        let deleted = history(vec![transfer(1), pending(3, false)]);
        assert!(verify_nmi_root_history(&deleted).is_err());

        let reordered = history(vec![pending(2, false), transfer(1)]);
        assert!(verify_nmi_root_history(&reordered).is_err());

        let reused = history(vec![
            transfer(1),
            pending(2, false),
            begin(3, 7),
            read(4, 7, 0, WORD),
            end(5, 7, WORD, RootFetchSource::PifRom),
            transfer(6),
            pending(7, false),
            begin(8, 7),
        ]);
        assert!(verify_nmi_root_history(&reused).is_err());
    }

    #[test]
    fn malformed_capture_identity_and_truncated_fetch_are_rejected() {
        let malformed = NmiRootHistory {
            capture_sha256: "same-value-is-not-provenance".into(),
            records: vec![transfer(1)],
        };
        assert!(verify_nmi_root_history(&malformed).is_err());

        let truncated = history(vec![transfer(1), pending(2, false), begin(3, 7)]);
        assert!(verify_nmi_root_history(&truncated).is_err());
    }
}
