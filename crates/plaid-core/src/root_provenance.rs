//! Source-bound reset/NMI root transfer and first-fetch provenance replay.
//!
//! This bounded compiler-time consumer keeps three facts separate: architectural
//! transfer to the reset/NMI root, occurrence of a root fetch after NMI is no
//! longer pending, and byte provenance for that fetch. It does not prove reset
//! delivery, producer/deassertion completeness, root-set completeness,
//! executable lifetime, or native completeness.
use crate::{
    program::{GuestVirtualAddr, PhysicalAddr},
    rom::sha256,
};
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-nmi-root-history-v0";
pub const NMI_ROOT: GuestVirtualAddr = GuestVirtualAddr(0xffff_ffff_bfc0_0000);
pub const NMI_ROOT_PHYSICAL: PhysicalAddr = PhysicalAddr(0x1fc0_0000);
pub const PIF_FIRMWARE_BYTES: usize = 1984;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    NmiTransfer {
        ordinal: u64,
        context: u64,
        interrupted_pc: GuestVirtualAddr,
        root: GuestVirtualAddr,
        pending_after: bool,
    },
    NmiPending {
        ordinal: u64,
        context: u64,
        asserted: bool,
    },
    FetchBegin {
        ordinal: u64,
        context: u64,
        transfer_context: u64,
        pc: GuestVirtualAddr,
        physical: PhysicalAddr,
        cached: bool,
    },
    PifRomRead {
        ordinal: u64,
        context: u64,
        pc: GuestVirtualAddr,
        offset: u32,
        bytes: u32,
        value: u32,
    },
    FetchEnd {
        ordinal: u64,
        context: u64,
        transfer_context: u64,
        pc: GuestVirtualAddr,
        physical: PhysicalAddr,
        cached: bool,
        value: u32,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::NmiTransfer { ordinal, .. }
            | Self::NmiPending { ordinal, .. }
            | Self::FetchBegin { ordinal, .. }
            | Self::PifRomRead { ordinal, .. }
            | Self::FetchEnd { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PifRootSourceReceipt {
    pub read_ordinal: u64,
    pub offset: u32,
    pub word: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootFetchReceipt {
    pub transfer_context: u64,
    pub fetch_context: u64,
    pub begin_ordinal: u64,
    pub end_ordinal: u64,
    pub pc: GuestVirtualAddr,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub pif_rom_source: Option<PifRootSourceReceipt>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootTransferReceipt {
    pub transfer_context: u64,
    pub transfer_ordinal: u64,
    pub interrupted_pc: GuestVirtualAddr,
    pub root: GuestVirtualAddr,
    pub pending_after: bool,
    pub final_pending: bool,
    pub pending_observations: u64,
    pub first_deassert_ordinal: Option<u64>,
    pub root_fetch: Option<NmiRootFetchReceipt>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NmiRootReport {
    pub format: String,
    pub source_sha256: String,
    pub firmware_sha256: String,
    pub transfers: Vec<NmiRootTransferReceipt>,
    pub root_fetches: u64,
    pub source_bound_root_fetches: u64,
    pub pif_reads: u64,
    pub unattributed_pif_reads: u64,
    pub producer_lifecycle_certified: bool,
    pub root_reachability_complete: bool,
    pub root_set_complete: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

struct TransferState {
    context: u64,
    ordinal: u64,
    interrupted_pc: GuestVirtualAddr,
    root: GuestVirtualAddr,
    pending_after: bool,
    pending: bool,
    pending_observations: u64,
    first_deassert_ordinal: Option<u64>,
}

impl TransferState {
    fn receipt(self, root_fetch: Option<NmiRootFetchReceipt>) -> NmiRootTransferReceipt {
        NmiRootTransferReceipt {
            transfer_context: self.context,
            transfer_ordinal: self.ordinal,
            interrupted_pc: self.interrupted_pc,
            root: self.root,
            pending_after: self.pending_after,
            final_pending: self.pending,
            pending_observations: self.pending_observations,
            first_deassert_ordinal: self.first_deassert_ordinal,
            root_fetch,
        }
    }
}

#[derive(Clone, Copy)]
struct PifRead {
    ordinal: u64,
    offset: u32,
    value: u32,
}

struct FetchState {
    transfer_context: u64,
    context: u64,
    begin_ordinal: u64,
    reads: Vec<PifRead>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

/// Replay a complete finite NMI-root history against separately trusted source
/// and supplied-firmware receipts.
///
/// Successful replay authenticates only relationships present in this source. It
/// never upgrades the capture into a producer census, hardware timing claim,
/// executable lifetime, root-set completeness, or closed-world certificate.
pub fn inspect_nmi_root_history(
    source: &[u8],
    expected_source_sha256: &str,
    firmware: &[u8],
    expected_firmware_sha256: &str,
) -> Result<NmiRootReport, String> {
    let source_sha256 = sha256(source);
    require(
        source_sha256 == expected_source_sha256,
        "NMI root source receipt mismatch",
    )?;
    let firmware_sha256 = sha256(firmware);
    require(
        firmware_sha256 == expected_firmware_sha256,
        "NMI root firmware receipt mismatch",
    )?;
    require(
        firmware.len() == PIF_FIRMWARE_BYTES,
        "unsupported PIF firmware size",
    )?;
    let firmware_word = u32::from_be_bytes(
        firmware[..4]
            .try_into()
            .map_err(|_| "invalid PIF root Word")?,
    );

    let history: History = serde_json::from_slice(source).map_err(|e| e.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported NMI root history format",
    )?;

    let mut transfers = Vec::new();
    let mut active_transfer: Option<TransferState> = None;
    let mut active_fetch: Option<FetchState> = None;
    let mut pif_reads = 0_u64;
    let mut attributed_pif_reads = 0_u64;

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous NMI root source ordinals",
        )?;
        match event {
            Event::NmiTransfer {
                ordinal,
                context,
                interrupted_pc,
                root,
                pending_after,
            } => {
                require(
                    active_fetch.is_none(),
                    "NMI transfer occurred inside an active root fetch",
                )?;
                if let Some(previous) = active_transfer.take() {
                    transfers.push(previous.receipt(None));
                }
                require(
                    *context == *ordinal && interrupted_pc.0.is_multiple_of(4) && *root == NMI_ROOT,
                    "invalid NMI root transfer",
                )?;
                active_transfer = Some(TransferState {
                    context: *context,
                    ordinal: *ordinal,
                    interrupted_pc: *interrupted_pc,
                    root: *root,
                    pending_after: *pending_after,
                    pending: *pending_after,
                    pending_observations: 0,
                    first_deassert_ordinal: None,
                });
            }
            Event::NmiPending {
                ordinal,
                context,
                asserted,
            } => {
                require(
                    active_fetch.is_none(),
                    "NMI pending state changed inside an active root fetch",
                )?;
                let transfer = active_transfer
                    .as_mut()
                    .ok_or("NMI pending state without active root transfer")?;
                require(
                    *context == transfer.context,
                    "NMI pending state has wrong transfer context",
                )?;
                if transfer.pending && !*asserted && transfer.first_deassert_ordinal.is_none() {
                    transfer.first_deassert_ordinal = Some(*ordinal);
                }
                transfer.pending = *asserted;
                transfer.pending_observations += 1;
            }
            Event::FetchBegin {
                ordinal,
                context,
                transfer_context,
                pc,
                physical,
                cached,
            } => {
                require(active_fetch.is_none(), "nested NMI root fetch")?;
                let transfer = active_transfer
                    .as_ref()
                    .ok_or("root fetch without active NMI transfer")?;
                require(
                    *context == *ordinal
                        && *transfer_context == transfer.context
                        && !transfer.pending,
                    "root fetch began while NMI was pending or with wrong context",
                )?;
                require(
                    *pc == NMI_ROOT && *physical == NMI_ROOT_PHYSICAL && !*cached,
                    "root fetch address/cache identity mismatch",
                )?;
                active_fetch = Some(FetchState {
                    transfer_context: *transfer_context,
                    context: *context,
                    begin_ordinal: *ordinal,
                    reads: Vec::new(),
                });
            }
            Event::PifRomRead {
                ordinal,
                context,
                pc,
                offset,
                bytes,
                value,
            } => {
                require(
                    *bytes == 4
                        && offset.is_multiple_of(4)
                        && (*offset as usize) <= PIF_FIRMWARE_BYTES - 4
                        && pc.0.is_multiple_of(4),
                    "invalid normalized PIF ROM read",
                )?;
                pif_reads += 1;
                if let Some(fetch) = active_fetch.as_mut()
                    && *context == fetch.context
                    && *pc == NMI_ROOT
                {
                    fetch.reads.push(PifRead {
                        ordinal: *ordinal,
                        offset: *offset,
                        value: *value,
                    });
                }
            }
            Event::FetchEnd {
                ordinal,
                context,
                transfer_context,
                pc,
                physical,
                cached,
                value,
            } => {
                let fetch = active_fetch
                    .take()
                    .ok_or("root fetch end without matching begin")?;
                require(
                    *context == fetch.context
                        && *transfer_context == fetch.transfer_context
                        && *pc == NMI_ROOT
                        && *physical == NMI_ROOT_PHYSICAL
                        && !*cached,
                    "root fetch completion identity mismatch",
                )?;
                let transfer = active_transfer
                    .take()
                    .ok_or("root fetch completion without NMI transfer")?;
                require(
                    transfer.context == fetch.transfer_context && !transfer.pending,
                    "root fetch completion lost its deasserted NMI transfer",
                )?;

                let pif_rom_source = if fetch.reads.len() == 1 {
                    let read = fetch.reads[0];
                    if read.offset == 0 && read.value == *value && firmware_word == *value {
                        attributed_pif_reads += 1;
                        Some(PifRootSourceReceipt {
                            read_ordinal: read.ordinal,
                            offset: read.offset,
                            word: read.value,
                        })
                    } else {
                        None
                    }
                } else {
                    None
                };
                let root_fetch = NmiRootFetchReceipt {
                    transfer_context: transfer.context,
                    fetch_context: fetch.context,
                    begin_ordinal: fetch.begin_ordinal,
                    end_ordinal: *ordinal,
                    pc: *pc,
                    physical: *physical,
                    word: *value,
                    pif_rom_source,
                };
                transfers.push(transfer.receipt(Some(root_fetch)));
            }
        }
    }

    require(active_fetch.is_none(), "truncated NMI root fetch")?;
    if let Some(transfer) = active_transfer {
        transfers.push(transfer.receipt(None));
    }
    require(
        !transfers.is_empty(),
        "NMI history contains no root transfer",
    )?;

    let root_fetches = transfers
        .iter()
        .filter(|transfer| transfer.root_fetch.is_some())
        .count() as u64;
    let source_bound_root_fetches = transfers
        .iter()
        .filter(|transfer| {
            transfer
                .root_fetch
                .as_ref()
                .is_some_and(|fetch| fetch.pif_rom_source.is_some())
        })
        .count() as u64;

    Ok(NmiRootReport {
        format: history.format,
        source_sha256,
        firmware_sha256,
        transfers,
        root_fetches,
        source_bound_root_fetches,
        pif_reads,
        unattributed_pif_reads: pif_reads - attributed_pif_reads,
        producer_lifecycle_certified: false,
        root_reachability_complete: false,
        root_set_complete: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_nmi_root_report(
    report: &NmiRootReport,
    source: &[u8],
    expected_source_sha256: &str,
    firmware: &[u8],
    expected_firmware_sha256: &str,
) -> Result<(), String> {
    require(
        *report
            == inspect_nmi_root_history(
                source,
                expected_source_sha256,
                firmware,
                expected_firmware_sha256,
            )?,
        "NMI root report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    const WORD: u32 = 0x3c09_3400;
    const INTERRUPTED: u64 = 0xffff_ffff_a000_0104;

    fn firmware(word: u32) -> Vec<u8> {
        let mut bytes = vec![0; PIF_FIRMWARE_BYTES];
        bytes[..4].copy_from_slice(&word.to_be_bytes());
        bytes
    }

    fn transfer(ordinal: u64, interrupted_pc: u64) -> Value {
        json!({
            "kind": "nmi_transfer",
            "ordinal": ordinal,
            "context": ordinal,
            "interrupted_pc": interrupted_pc,
            "root": NMI_ROOT.0,
            "pending_after": true
        })
    }

    fn pending(ordinal: u64, context: u64, asserted: bool) -> Value {
        json!({
            "kind": "nmi_pending",
            "ordinal": ordinal,
            "context": context,
            "asserted": asserted
        })
    }

    fn begin(ordinal: u64, transfer_context: u64) -> Value {
        json!({
            "kind": "fetch_begin",
            "ordinal": ordinal,
            "context": ordinal,
            "transfer_context": transfer_context,
            "pc": NMI_ROOT.0,
            "physical": NMI_ROOT_PHYSICAL.0,
            "cached": false
        })
    }

    fn read(ordinal: u64, context: u64, offset: u32, value: u32) -> Value {
        json!({
            "kind": "pif_rom_read",
            "ordinal": ordinal,
            "context": context,
            "pc": NMI_ROOT.0,
            "offset": offset,
            "bytes": 4,
            "value": value
        })
    }

    fn end(ordinal: u64, context: u64, transfer_context: u64, value: u32) -> Value {
        json!({
            "kind": "fetch_end",
            "ordinal": ordinal,
            "context": context,
            "transfer_context": transfer_context,
            "pc": NMI_ROOT.0,
            "physical": NMI_ROOT_PHYSICAL.0,
            "cached": false,
            "value": value
        })
    }

    fn encode(events: Vec<Value>) -> Vec<u8> {
        serde_json::to_vec(&json!({ "format": FORMAT, "events": events }))
            .expect("serialize test history")
    }

    fn inspect(events: Vec<Value>, firmware: &[u8]) -> Result<NmiRootReport, String> {
        let source = encode(events);
        inspect_nmi_root_history(&source, &sha256(&source), firmware, &sha256(firmware))
    }

    fn correct() -> Vec<Value> {
        vec![
            transfer(1, INTERRUPTED),
            pending(2, 1, false),
            begin(3, 1),
            read(4, 3, 0, WORD),
            end(5, 3, 1, WORD),
        ]
    }

    #[test]
    fn source_bound_fetch_requires_transfer_deassert_and_matching_read() {
        let firmware = firmware(WORD);
        let report = inspect(correct(), &firmware).expect("valid source-bound root fetch");
        assert_eq!(report.transfers.len(), 1);
        assert_eq!(report.root_fetches, 1);
        assert_eq!(report.source_bound_root_fetches, 1);
        assert_eq!(report.pif_reads, 1);
        assert_eq!(report.unattributed_pif_reads, 0);
        let transfer = &report.transfers[0];
        assert_eq!(transfer.first_deassert_ordinal, Some(2));
        let fetch = transfer.root_fetch.as_ref().expect("root fetch");
        assert_eq!(fetch.word, WORD);
        assert_eq!(
            fetch.pif_rom_source.as_ref().expect("source").read_ordinal,
            4
        );
        assert!(!report.producer_lifecycle_certified);
        assert!(!report.root_reachability_complete);
        assert!(!report.root_set_complete);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn transfer_only_and_persistent_reentry_do_not_fabricate_fetches() {
        let firmware = firmware(WORD);
        let transfer_only = inspect(vec![transfer(1, INTERRUPTED)], &firmware).expect("transfer");
        assert_eq!(transfer_only.root_fetches, 0);
        assert_eq!(transfer_only.source_bound_root_fetches, 0);

        let repeated = inspect(
            vec![transfer(1, INTERRUPTED), transfer(2, NMI_ROOT.0)],
            &firmware,
        )
        .expect("persistent NMI history");
        assert_eq!(repeated.transfers.len(), 2);
        assert_eq!(repeated.root_fetches, 0);
        assert!(
            repeated
                .transfers
                .iter()
                .all(|receipt| receipt.final_pending)
        );
    }

    #[test]
    fn equal_payload_without_matching_read_is_not_pif_provenance() {
        let firmware = firmware(WORD);
        let report = inspect(
            vec![
                transfer(1, INTERRUPTED),
                pending(2, 1, false),
                begin(3, 1),
                end(4, 3, 1, WORD),
            ],
            &firmware,
        )
        .expect("equal non-PIF fetch");
        assert_eq!(report.root_fetches, 1);
        assert_eq!(report.source_bound_root_fetches, 0);
    }

    #[test]
    fn earlier_equal_read_cannot_be_recycled() {
        let firmware = firmware(WORD);
        let report = inspect(
            vec![
                read(1, 77, 0, WORD),
                transfer(2, INTERRUPTED),
                pending(3, 2, false),
                begin(4, 2),
                end(5, 4, 2, WORD),
            ],
            &firmware,
        )
        .expect("foreign read history");
        assert_eq!(report.root_fetches, 1);
        assert_eq!(report.source_bound_root_fetches, 0);
        assert_eq!(report.unattributed_pif_reads, 1);
    }

    #[test]
    fn wrong_context_offset_or_ambiguous_reads_stay_unattributed() {
        let firmware = firmware(WORD);
        for events in [
            vec![
                transfer(1, INTERRUPTED),
                pending(2, 1, false),
                begin(3, 1),
                read(4, 4, 0, WORD),
                end(5, 3, 1, WORD),
            ],
            vec![
                transfer(1, INTERRUPTED),
                pending(2, 1, false),
                begin(3, 1),
                read(4, 3, 4, WORD),
                end(5, 3, 1, WORD),
            ],
            vec![
                transfer(1, INTERRUPTED),
                pending(2, 1, false),
                begin(3, 1),
                read(4, 3, 0, WORD),
                read(5, 3, 4, WORD),
                end(6, 3, 1, WORD),
            ],
        ] {
            let report = inspect(events, &firmware).expect("valid ambiguous history");
            assert_eq!(report.root_fetches, 1);
            assert_eq!(report.source_bound_root_fetches, 0);
        }
    }

    #[test]
    fn supplied_firmware_identity_must_match_the_read_word() {
        let firmware = firmware(0);
        let report = inspect(correct(), &firmware).expect("mismatched firmware history");
        assert_eq!(report.root_fetches, 1);
        assert_eq!(report.source_bound_root_fetches, 0);
        assert_eq!(report.unattributed_pif_reads, 1);
    }

    #[test]
    fn fetch_while_nmi_is_pending_is_rejected() {
        let firmware = firmware(WORD);
        let error = inspect(vec![transfer(1, INTERRUPTED), begin(2, 1)], &firmware)
            .expect_err("pending fetch must reject");
        assert!(error.contains("pending"));
    }

    #[test]
    fn complete_source_and_firmware_receipts_reject_substitution() {
        let firmware = firmware(WORD);
        let source = encode(correct());
        let source_hash = sha256(&source);
        let firmware_hash = sha256(&firmware);
        let deleted = encode(vec![
            transfer(1, INTERRUPTED),
            pending(2, 1, false),
            begin(3, 1),
            end(4, 3, 1, WORD),
        ]);
        assert!(
            inspect_nmi_root_history(&deleted, &source_hash, &firmware, &firmware_hash)
                .expect_err("deleted source row")
                .contains("source receipt")
        );
        let changed_firmware = self::firmware(0);
        assert!(
            inspect_nmi_root_history(&source, &source_hash, &changed_firmware, &firmware_hash,)
                .expect_err("changed firmware")
                .contains("firmware receipt")
        );
    }

    #[test]
    fn reordered_history_is_rejected() {
        let firmware = firmware(WORD);
        let error = inspect(
            vec![transfer(1, INTERRUPTED), pending(3, 1, false), begin(2, 1)],
            &firmware,
        )
        .expect_err("reordered source");
        assert!(error.contains("noncontiguous"));
    }

    #[test]
    fn report_verification_replays_complete_source() {
        let firmware = firmware(WORD);
        let source = encode(correct());
        let source_hash = sha256(&source);
        let firmware_hash = sha256(&firmware);
        let mut report = inspect_nmi_root_history(&source, &source_hash, &firmware, &firmware_hash)
            .expect("report");
        verify_nmi_root_report(&report, &source, &source_hash, &firmware, &firmware_hash)
            .expect("recheck");
        report.source_bound_root_fetches = 0;
        assert!(
            verify_nmi_root_report(&report, &source, &source_hash, &firmware, &firmware_hash,)
                .expect_err("tampered report")
                .contains("complete source replay")
        );
    }
}
