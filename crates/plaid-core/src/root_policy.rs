//! Target-scoped executable-root policy facts.
//!
//! These helpers encode reviewed architectural exclusions only. They are not a
//! substitute for proving reachability, handler bytes, root completeness, or an
//! executable lifetime.
use crate::exception_roots::{ExceptionRootInput, ExceptionRootReceipt, resolve_exception_root};
use serde::{Deserialize, Serialize};

pub const VR4300_MANUAL: &str = "NEC VR4300/VR4305/VR4310 User's Manual U10504EJ7V0UM00";
pub const VR4300_CACHE_ERROR_SECTION: &str = "Appendix B.1.7 / Table B-1";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RootTarget {
    Nintendo64Vr4300,
    GenericMipsIii,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case", deny_unknown_fields)]
pub enum CacheErrorRootDisposition {
    ExcludedByTargetHardware { authority: String, section: String },
    Unresolved { reason: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CacheErrorRootReport {
    pub target: RootTarget,
    pub disposition: CacheErrorRootDisposition,
    /// This bounded exclusion never certifies the complete executable-root set.
    pub whole_rom_roots_certified: bool,
    pub native_complete: bool,
}

/// Return the reviewed cache-error root disposition for an explicit CPU target.
///
/// The VR4300 exclusion comes from target hardware documentation, not from the
/// absence of an event in an emulator or finite trace. Other MIPS III targets
/// remain unresolved because the hardware fact is deliberately target-specific.
pub fn cache_error_root_report(target: RootTarget) -> CacheErrorRootReport {
    let disposition = match target {
        RootTarget::Nintendo64Vr4300 => CacheErrorRootDisposition::ExcludedByTargetHardware {
            authority: VR4300_MANUAL.into(),
            section: VR4300_CACHE_ERROR_SECTION.into(),
        },
        RootTarget::GenericMipsIii => CacheErrorRootDisposition::Unresolved {
            reason: "VR4300 cache-error exclusion is not valid for a generic MIPS III target"
                .into(),
        },
    };
    CacheErrorRootReport {
        target,
        disposition,
        whole_rom_roots_certified: false,
        native_complete: false,
    }
}

/// Recompute the target-scoped policy instead of trusting a serialized report.
pub fn verify_cache_error_root_report(report: &CacheErrorRootReport) -> Result<(), String> {
    if *report == cache_error_root_report(report.target) {
        Ok(())
    } else {
        Err("cache-error root report differs from target hardware policy".into())
    }
}

/// A requested exception class is distinct from a proven executable handler.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(
    tag = "class",
    content = "input",
    rename_all = "snake_case",
    deny_unknown_fields
)]
pub enum RootClassRequest {
    GeneralOrTlb(ExceptionRootInput),
    CacheError,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum RootClassDisposition {
    NumericCandidate { receipt: ExceptionRootReceipt },
    CacheErrorPolicy { report: CacheErrorRootReport },
    UnresolvedTarget { reason: String },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RootClassificationReport {
    pub target: RootTarget,
    pub request: RootClassRequest,
    pub disposition: RootClassDisposition,
    pub handler_bytes_certified: bool,
    pub root_census_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

/// Compose target hardware policy with the existing numeric vector resolver.
/// A numeric result never grants reachability, handler identity or root coverage.
/// The canonical VR4300 vector contract is not silently applied to other CPUs.
pub fn classify_execution_root(
    target: RootTarget,
    request: RootClassRequest,
) -> RootClassificationReport {
    let disposition = match request {
        RootClassRequest::CacheError => RootClassDisposition::CacheErrorPolicy {
            report: cache_error_root_report(target),
        },
        RootClassRequest::GeneralOrTlb(input) => match target {
            RootTarget::Nintendo64Vr4300 => RootClassDisposition::NumericCandidate {
                receipt: resolve_exception_root(input),
            },
            RootTarget::GenericMipsIii => RootClassDisposition::UnresolvedTarget {
                reason: "canonical VR4300 vector contract is not certified for generic MIPS III"
                    .into(),
            },
        },
    };
    RootClassificationReport {
        target,
        request,
        disposition,
        handler_bytes_certified: false,
        root_census_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    }
}

pub fn verify_execution_root_classification(
    report: &RootClassificationReport,
) -> Result<(), String> {
    if *report == classify_execution_root(report.target, report.request) {
        Ok(())
    } else {
        Err("execution-root classification differs from target/class/context contract".into())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::exception_roots::{ExceptionClass, KernelAddressMode};

    #[test]
    fn target_policy_and_numeric_vectors_remain_distinct_proof_results() {
        let excluded =
            classify_execution_root(RootTarget::Nintendo64Vr4300, RootClassRequest::CacheError);
        assert!(matches!(
            excluded.disposition,
            RootClassDisposition::CacheErrorPolicy {
                report: CacheErrorRootReport {
                    disposition: CacheErrorRootDisposition::ExcludedByTargetHardware { .. },
                    ..
                }
            }
        ));
        for class in [
            ExceptionClass::General,
            ExceptionClass::TlbInvalid,
            ExceptionClass::TlbMiss,
        ] {
            for bev in [false, true] {
                for exl in [false, true] {
                    for kernel_mode in [KernelAddressMode::Bits32, KernelAddressMode::Bits64] {
                        let input = ExceptionRootInput {
                            class,
                            bev,
                            exl,
                            kernel_mode,
                        };
                        let report = classify_execution_root(
                            RootTarget::Nintendo64Vr4300,
                            RootClassRequest::GeneralOrTlb(input),
                        );
                        assert_eq!(
                            report.disposition,
                            RootClassDisposition::NumericCandidate {
                                receipt: resolve_exception_root(input)
                            }
                        );
                        assert!(
                            !report.root_census_certified
                                && !report.handler_bytes_certified
                                && !report.native_complete
                        );
                        verify_execution_root_classification(&report).unwrap();
                    }
                }
            }
        }
    }

    #[test]
    fn target_and_class_substitution_cannot_borrow_a_vr4300_exclusion_or_vector() {
        let mut forged =
            classify_execution_root(RootTarget::Nintendo64Vr4300, RootClassRequest::CacheError);
        forged.target = RootTarget::GenericMipsIii;
        assert!(verify_execution_root_classification(&forged).is_err());
        let input = ExceptionRootInput {
            class: ExceptionClass::General,
            bev: false,
            exl: false,
            kernel_mode: KernelAddressMode::Bits32,
        };
        forged = classify_execution_root(
            RootTarget::Nintendo64Vr4300,
            RootClassRequest::GeneralOrTlb(input),
        );
        forged.request = RootClassRequest::CacheError;
        assert!(verify_execution_root_classification(&forged).is_err());
        let generic = classify_execution_root(
            RootTarget::GenericMipsIii,
            RootClassRequest::GeneralOrTlb(input),
        );
        assert!(matches!(
            generic.disposition,
            RootClassDisposition::UnresolvedTarget { .. }
        ));
    }

    #[test]
    fn numeric_candidate_cannot_certify_lifetime_or_accept_unknown_report_fields() {
        let input = ExceptionRootInput {
            class: ExceptionClass::TlbMiss,
            bev: true,
            exl: false,
            kernel_mode: KernelAddressMode::Bits64,
        };
        let mut report = classify_execution_root(
            RootTarget::Nintendo64Vr4300,
            RootClassRequest::GeneralOrTlb(input),
        );
        report.executable_lifetime_certified = true;
        assert!(verify_execution_root_classification(&report).is_err());
        let mut value = serde_json::to_value(classify_execution_root(
            RootTarget::Nintendo64Vr4300,
            RootClassRequest::CacheError,
        ))
        .unwrap();
        value["disposition"]["cache_error_observations"] = serde_json::json!(0);
        assert!(serde_json::from_value::<RootClassificationReport>(value).is_err());
    }

    #[test]
    fn vr4300_exclusion_is_explicit_but_does_not_close_root_coverage() {
        let report = cache_error_root_report(RootTarget::Nintendo64Vr4300);
        assert_eq!(
            report.disposition,
            CacheErrorRootDisposition::ExcludedByTargetHardware {
                authority: VR4300_MANUAL.into(),
                section: VR4300_CACHE_ERROR_SECTION.into(),
            }
        );
        assert!(!report.whole_rom_roots_certified);
        assert!(!report.native_complete);
        verify_cache_error_root_report(&report).unwrap();
    }

    #[test]
    fn generic_mips_iii_stays_unresolved() {
        let report = cache_error_root_report(RootTarget::GenericMipsIii);
        assert!(matches!(
            report.disposition,
            CacheErrorRootDisposition::Unresolved { .. }
        ));
        assert!(verify_cache_error_root_report(&report).is_ok());
    }

    #[test]
    fn forged_or_deleted_hardware_basis_is_rejected() {
        let mut report = cache_error_root_report(RootTarget::Nintendo64Vr4300);
        report.disposition = CacheErrorRootDisposition::Unresolved {
            reason: "emulator did not observe cache errors".into(),
        };
        assert!(verify_cache_error_root_report(&report).is_err());

        let mut encoded =
            serde_json::to_value(cache_error_root_report(RootTarget::Nintendo64Vr4300)).unwrap();
        encoded["extra"] = serde_json::Value::Bool(true);
        assert!(serde_json::from_value::<CacheErrorRootReport>(encoded).is_err());
    }
}
