//! Source-bound PIF provenance for the validated BEV=1 general-exception root.
//!
//! This composes two independently bounded facts: numeric general-vector
//! selection and the existing complete-source PIF boot-history replayer. It
//! deliberately does not infer exception reachability from the vector address,
//! fetched bits, an earlier equal-valued PIF read, or a coalesced sample.
use crate::{
    exception_roots::{
        ExceptionClass, ExceptionRootReceipt, ExceptionVectorClass, KernelAddressMode,
    },
    pif_history::{PifBackingFetchSample, PifHistoryReport, inspect_pif_boot_history},
    program::PhysicalAddr,
    rom::CanonicalRom,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::io::{BufRead, Seek};

const BEV1_GENERAL_ROOT: u64 = 0xffff_ffff_bfc0_0380;
const BEV1_GENERAL_PHYSICAL: PhysicalAddr = PhysicalAddr(0x1fc0_0380);
const BEV1_GENERAL_PIF_OFFSET: u32 = 0x380;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Bev1GeneralPifRootSourceReceipt {
    pub root: ExceptionRootReceipt,
    pub fetch_seq: u64,
    pub physical: PhysicalAddr,
    pub word: u32,
    pub pif_offset: u32,
    pub backing_read_ordinal: u64,
    pub pif_history_sha256: String,
    pub ordered_fetch_backing_sha256: String,
    pub supplied_firmware_sha256: String,
}

struct BindingEvidence<'a> {
    fetches: u64,
    samples: &'a [PifBackingFetchSample],
    history_sha256: &'a str,
    ordered_fetch_backing_sha256: &'a str,
    firmware_sha256: &'a str,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn bind_source(
    root: ExceptionRootReceipt,
    fetch_seq: u64,
    evidence: BindingEvidence<'_>,
) -> Result<Bev1GeneralPifRootSourceReceipt, String> {
    require(
        root.input.class == ExceptionClass::General
            && root.input.bev
            && !root.input.exl
            && root.input.kernel_mode == KernelAddressMode::Bits32
            && root.vector_class == ExceptionVectorClass::General
            && root.root.0 == BEV1_GENERAL_ROOT,
        "root is outside the validated BEV=1 32-bit general-exception scope",
    )?;
    require(
        fetch_seq < evidence.fetches,
        "selected fetch is outside the history",
    )?;

    let mut exact = evidence.samples.iter().filter(|sample| {
        sample.observations == 1
            && sample.first_fetch == fetch_seq
            && sample.last_fetch == fetch_seq
            && sample.first_read_ordinal == sample.last_read_ordinal
    });
    let sample = exact
        .next()
        .ok_or("selected root fetch lacks a unique PIF backing witness")?;
    require(
        exact.next().is_none(),
        "selected root fetch has multiple PIF backing witnesses",
    )?;
    require(
        sample.pc == root.root
            && sample.physical == BEV1_GENERAL_PHYSICAL
            && sample.offset == BEV1_GENERAL_PIF_OFFSET,
        "selected PIF witness does not describe the validated BEV=1 general root",
    )?;
    require(
        sample.matches_supplied_firmware,
        "selected root fetch does not match the supplied PIF firmware",
    )?;

    Ok(Bev1GeneralPifRootSourceReceipt {
        root,
        fetch_seq,
        physical: sample.physical,
        word: sample.word,
        pif_offset: sample.offset,
        backing_read_ordinal: sample.first_read_ordinal,
        pif_history_sha256: evidence.history_sha256.into(),
        ordered_fetch_backing_sha256: evidence.ordered_fetch_backing_sha256.into(),
        supplied_firmware_sha256: evidence.firmware_sha256.into(),
    })
}

/// Recheck complete PIF history sources and bind one exact observed fetch to the
/// validated BEV=1 32-bit general-exception vector.
///
/// The selected fetch must survive the existing PIF history's same-fetch backing
/// join as a singleton sample. Coalesced repeated observations are intentionally
/// rejected because they no longer identify a particular occurrence. This
/// receipt authenticates handler-byte source for that fetch only. It does not
/// prove that the fetch was caused by an exception, that all exception roots are
/// known, or that the fetched bytes remain executable for any later lifetime.
pub fn inspect_bev1_general_pif_root_source<H: BufRead, F: BufRead + Seek>(
    root: ExceptionRootReceipt,
    fetch_seq: u64,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<Bev1GeneralPifRootSourceReceipt, String> {
    let report = inspect_pif_boot_history(history, fetched, rom, firmware)?;
    bind_report(root, fetch_seq, &report, firmware)
}

fn bind_report(
    root: ExceptionRootReceipt,
    fetch_seq: u64,
    report: &PifHistoryReport,
    firmware: &[u8],
) -> Result<Bev1GeneralPifRootSourceReceipt, String> {
    let firmware_sha256 = format!("{:x}", Sha256::digest(firmware));
    bind_source(
        root,
        fetch_seq,
        BindingEvidence {
            fetches: report.fetches,
            samples: &report.samples,
            history_sha256: &report.history_sha256,
            ordered_fetch_backing_sha256: &report.ordered_fetch_backing_sha256,
            firmware_sha256: &firmware_sha256,
        },
    )
}

/// Recompute a BEV=1 PIF-root source receipt from the complete original sources.
pub fn verify_bev1_general_pif_root_source<H: BufRead, F: BufRead + Seek>(
    receipt: &Bev1GeneralPifRootSourceReceipt,
    history: H,
    fetched: F,
    rom: &CanonicalRom,
    firmware: &[u8],
) -> Result<(), String> {
    require(
        *receipt
            == inspect_bev1_general_pif_root_source(
                receipt.root,
                receipt.fetch_seq,
                history,
                fetched,
                rom,
                firmware,
            )?,
        "BEV=1 PIF root receipt differs from complete sources/inputs",
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::exception_roots::{ExceptionRootInput, resolve_exception_root};
    use crate::program::GuestVirtualAddr;

    fn root() -> ExceptionRootReceipt {
        resolve_exception_root(ExceptionRootInput {
            class: ExceptionClass::General,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        })
    }

    fn sample() -> PifBackingFetchSample {
        PifBackingFetchSample {
            pc: GuestVirtualAddr(BEV1_GENERAL_ROOT),
            physical: BEV1_GENERAL_PHYSICAL,
            word: 0x2402_0007,
            offset: BEV1_GENERAL_PIF_OFFSET,
            matches_supplied_firmware: true,
            first_fetch: 4,
            last_fetch: 4,
            first_read_ordinal: 19,
            last_read_ordinal: 19,
            observations: 1,
        }
    }

    fn bind(
        samples: &[PifBackingFetchSample],
        fetch_seq: u64,
    ) -> Result<Bev1GeneralPifRootSourceReceipt, String> {
        bind_source(
            root(),
            fetch_seq,
            BindingEvidence {
                fetches: 9,
                samples,
                history_sha256: "history",
                ordered_fetch_backing_sha256: "ordered",
                firmware_sha256: "firmware",
            },
        )
    }

    #[test]
    fn binds_only_the_selected_singleton_root_fetch() {
        let receipt = bind(&[sample()], 4).unwrap();
        assert_eq!(receipt.fetch_seq, 4);
        assert_eq!(receipt.physical, BEV1_GENERAL_PHYSICAL);
        assert_eq!(receipt.pif_offset, BEV1_GENERAL_PIF_OFFSET);
        assert_eq!(receipt.backing_read_ordinal, 19);
        assert_eq!(receipt.word, 0x2402_0007);
    }

    #[test]
    fn rejects_unwitnessed_or_prior_equal_value_fetches() {
        let prior = sample();
        assert!(bind(&[], 5).is_err());
        assert!(bind(&[prior], 5).is_err());
    }

    #[test]
    fn rejects_coalesced_identical_observations() {
        let mut coalesced = sample();
        coalesced.last_fetch = 8;
        coalesced.last_read_ordinal = 41;
        coalesced.observations = 2;
        assert!(bind(&[coalesced.clone()], 4).is_err());
        assert!(bind(&[coalesced], 8).is_err());
    }

    #[test]
    fn rejects_wrong_backing_identity_or_firmware() {
        let mut wrong = sample();
        wrong.physical = PhysicalAddr(0x1fc0_0200);
        assert!(bind(&[wrong], 4).is_err());

        let mut wrong = sample();
        wrong.offset = 0x100;
        assert!(bind(&[wrong], 4).is_err());

        let mut wrong = sample();
        wrong.matches_supplied_firmware = false;
        assert!(bind(&[wrong], 4).is_err());
    }

    #[test]
    fn rejects_duplicate_exact_witnesses() {
        let one = sample();
        let mut two = sample();
        two.word = 0x2402_0008;
        assert!(bind(&[one, two], 4).is_err());
    }

    #[test]
    fn rejects_unvalidated_root_modes_and_classes() {
        for input in [
            ExceptionRootInput {
                class: ExceptionClass::General,
                bev: false,
                exl: false,
                kernel_mode: KernelAddressMode::Bits32,
            },
            ExceptionRootInput {
                class: ExceptionClass::General,
                bev: true,
                exl: true,
                kernel_mode: KernelAddressMode::Bits32,
            },
            ExceptionRootInput {
                class: ExceptionClass::General,
                bev: true,
                exl: false,
                kernel_mode: KernelAddressMode::Bits64,
            },
            ExceptionRootInput {
                class: ExceptionClass::TlbInvalid,
                bev: true,
                exl: false,
                kernel_mode: KernelAddressMode::Bits32,
            },
        ] {
            let result = bind_source(
                resolve_exception_root(input),
                4,
                BindingEvidence {
                    fetches: 9,
                    samples: &[sample()],
                    history_sha256: "history",
                    ordered_fetch_backing_sha256: "ordered",
                    firmware_sha256: "firmware",
                },
            );
            assert!(result.is_err());
        }
    }
}
