//! Target-scoped executable-root policy facts.
//!
//! These helpers encode reviewed architectural exclusions only. They are not a
//! substitute for proving reachability, handler bytes, root completeness, or an
//! executable lifetime.
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
    ExcludedByTargetHardware {
        authority: String,
        section: String,
    },
    Unresolved {
        reason: String,
    },
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

#[cfg(test)]
mod tests {
    use super::*;

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

        let mut encoded = serde_json::to_value(cache_error_root_report(
            RootTarget::Nintendo64Vr4300,
        ))
        .unwrap();
        encoded["extra"] = serde_json::Value::Bool(true);
        assert!(serde_json::from_value::<CacheErrorRootReport>(encoded).is_err());
    }
}
