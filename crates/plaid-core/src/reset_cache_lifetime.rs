//! Source-bound replay for a bounded pinned-reference reset/cache lifetime contract.
//!
//! The validated reference result distinguishes backing-byte state from resident
//! instruction-cache state. This module preserves that distinction without
//! pretending the finite receipt is a reset/NMI census, a hardware-wide rule, or
//! an executable-lifetime certificate. Save-state restore is intentionally not
//! represented here because restore selects an earlier chronology rather than a
//! monotonic lifetime transition.

use crate::rom::sha256;
use serde::{Deserialize, Serialize};

pub const FORMAT: &str = "plaid-reset-cache-lifetime-v0";
pub const PROFILE: &str = "ares-9408cb43d4948fc3ea6e152a307a34348df3fe04-reset-cache-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResetCacheTransitionKind {
    Nmi,
    SystemReset,
    FullPower,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetCacheTransitionWitness {
    pub transition_generation: u64,
    pub ordinal: u64,
    pub kind: ResetCacheTransitionKind,
    pub resident_generation_before: u64,
    pub resident_generation_after: u64,
    pub backing_generation_before: u64,
    pub backing_generation_after: u64,
    pub resident_reinitialized: bool,
    pub backing_reinitialized: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResetCacheLifetimeReport {
    pub format: String,
    pub profile: String,
    pub source_sha256: String,
    pub transitions: usize,
    pub resident_reinitializations: usize,
    pub backing_reinitializations: usize,
    pub witnesses: Vec<ResetCacheTransitionWitness>,
    pub transition_census_certified: bool,
    pub hardware_semantics_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    profile: String,
    events: Vec<Event>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Event {
    ordinal: u64,
    kind: ResetCacheTransitionKind,
    resident_reinitialized: bool,
    backing_reinitialized: bool,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

pub(crate) fn expected_effects(kind: ResetCacheTransitionKind) -> (bool, bool) {
    match kind {
        ResetCacheTransitionKind::Nmi => (false, false),
        ResetCacheTransitionKind::SystemReset => (true, false),
        ResetCacheTransitionKind::FullPower => (true, true),
    }
}

/// Replay one externally authenticated finite source for the pinned-reference
/// profile.
///
/// The expected hash must come from a separately trusted complete-source receipt.
/// Receipt-local generation numbers are minted from observed reinitialization
/// operations, not from payload equality. They do not establish reset/NMI sensor
/// completeness, physical-hardware semantics, or a complete executable lifetime.
pub fn inspect_reset_cache_lifetime(
    source: &[u8],
    expected_sha256: &str,
) -> Result<ResetCacheLifetimeReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "reset/cache lifetime source receipt mismatch",
    )?;

    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported reset/cache lifetime history format",
    )?;
    require(
        history.profile == PROFILE,
        "unsupported reset/cache lifetime reference profile",
    )?;

    let mut next_ordinal = 1u64;
    let mut resident_generation = 1u64;
    let mut backing_generation = 1u64;
    let mut resident_reinitializations = 0usize;
    let mut backing_reinitializations = 0usize;
    let mut witnesses = Vec::with_capacity(history.events.len());

    for event in history.events {
        require(
            event.ordinal == next_ordinal,
            "noncontiguous reset/cache lifetime event ordinals",
        )?;
        next_ordinal = next_ordinal
            .checked_add(1)
            .ok_or("reset/cache lifetime ordinal overflow")?;

        let (expected_resident, expected_backing) = expected_effects(event.kind);
        require(
            event.resident_reinitialized == expected_resident
                && event.backing_reinitialized == expected_backing,
            "reset/cache transition effects disagree with pinned-reference profile",
        )?;

        let resident_generation_before = resident_generation;
        let backing_generation_before = backing_generation;

        if event.resident_reinitialized {
            resident_generation = resident_generation
                .checked_add(1)
                .ok_or("resident generation overflow")?;
            resident_reinitializations += 1;
        }
        if event.backing_reinitialized {
            backing_generation = backing_generation
                .checked_add(1)
                .ok_or("backing generation overflow")?;
            backing_reinitializations += 1;
        }

        witnesses.push(ResetCacheTransitionWitness {
            transition_generation: event.ordinal,
            ordinal: event.ordinal,
            kind: event.kind,
            resident_generation_before,
            resident_generation_after: resident_generation,
            backing_generation_before,
            backing_generation_after: backing_generation,
            resident_reinitialized: event.resident_reinitialized,
            backing_reinitialized: event.backing_reinitialized,
        });
    }

    Ok(ResetCacheLifetimeReport {
        format: history.format,
        profile: history.profile,
        source_sha256: digest,
        transitions: witnesses.len(),
        resident_reinitializations,
        backing_reinitializations,
        witnesses,
        transition_census_certified: false,
        hardware_semantics_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

pub fn verify_reset_cache_lifetime_report(
    report: &ResetCacheLifetimeReport,
    source: &[u8],
    expected_sha256: &str,
) -> Result<(), String> {
    require(
        *report == inspect_reset_cache_lifetime(source, expected_sha256)?,
        "reset/cache lifetime report differs from complete source replay",
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn source(events: &str) -> Vec<u8> {
        format!(r#"{{"format":"{FORMAT}","profile":"{PROFILE}","events":[{events}]}}"#).into_bytes()
    }

    fn inspect(source: &[u8]) -> Result<ResetCacheLifetimeReport, String> {
        inspect_reset_cache_lifetime(source, &sha256(source))
    }

    #[test]
    fn nmi_preserves_resident_and_backing_generations() {
        let source = source(
            r#"{"ordinal":1,"kind":"nmi","resident_reinitialized":false,"backing_reinitialized":false}"#,
        );
        let report = inspect(&source).unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(
            (
                witness.resident_generation_before,
                witness.resident_generation_after,
                witness.backing_generation_before,
                witness.backing_generation_after,
            ),
            (1, 1, 1, 1)
        );
        assert_eq!(report.resident_reinitializations, 0);
        assert_eq!(report.backing_reinitializations, 0);
    }

    #[test]
    fn system_reset_cuts_residency_without_cutting_backing() {
        let source = source(
            r#"{"ordinal":1,"kind":"nmi","resident_reinitialized":false,"backing_reinitialized":false},{"ordinal":2,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":false}"#,
        );
        let report = inspect(&source).unwrap();
        let witness = &report.witnesses[1];
        assert_eq!(
            (
                witness.resident_generation_before,
                witness.resident_generation_after,
                witness.backing_generation_before,
                witness.backing_generation_after,
            ),
            (1, 2, 1, 1)
        );
    }

    #[test]
    fn repeated_system_resets_are_distinct_residency_operations() {
        let source = source(
            r#"{"ordinal":1,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":false},{"ordinal":2,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":false}"#,
        );
        let report = inspect(&source).unwrap();
        assert_eq!(report.witnesses[0].resident_generation_after, 2);
        assert_eq!(report.witnesses[1].resident_generation_after, 3);
        assert_eq!(report.witnesses[1].backing_generation_after, 1);
    }

    #[test]
    fn full_power_cuts_both_domains_by_operation_occurrence() {
        let source = source(
            r#"{"ordinal":1,"kind":"full_power","resident_reinitialized":true,"backing_reinitialized":true}"#,
        );
        let report = inspect(&source).unwrap();
        let witness = &report.witnesses[0];
        assert_eq!(witness.resident_generation_after, 2);
        assert_eq!(witness.backing_generation_after, 2);
        assert_eq!(report.resident_reinitializations, 1);
        assert_eq!(report.backing_reinitializations, 1);
    }

    #[test]
    fn rejects_nmi_that_forges_a_residency_cut() {
        let source = source(
            r#"{"ordinal":1,"kind":"nmi","resident_reinitialized":true,"backing_reinitialized":false}"#,
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_system_reset_that_forges_a_backing_cut() {
        let source = source(
            r#"{"ordinal":1,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":true}"#,
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_full_power_without_both_reinitializations() {
        let source = source(
            r#"{"ordinal":1,"kind":"full_power","resident_reinitialized":true,"backing_reinitialized":false}"#,
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_missing_or_reordered_events() {
        for events in [
            r#"{"ordinal":2,"kind":"nmi","resident_reinitialized":false,"backing_reinitialized":false}"#,
            r#"{"ordinal":1,"kind":"nmi","resident_reinitialized":false,"backing_reinitialized":false},{"ordinal":3,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":false}"#,
        ] {
            assert!(inspect(&source(events)).is_err());
        }
    }

    #[test]
    fn rejects_restore_as_a_fake_monotonic_transition() {
        let source = source(
            r#"{"ordinal":1,"kind":"restore","resident_reinitialized":false,"backing_reinitialized":false}"#,
        );
        assert!(inspect(&source).is_err());
    }

    #[test]
    fn rejects_wrong_source_receipt_or_profile() {
        let source = source(
            r#"{"ordinal":1,"kind":"nmi","resident_reinitialized":false,"backing_reinitialized":false}"#,
        );
        assert!(inspect_reset_cache_lifetime(&source, &"0".repeat(64)).is_err());

        let wrong_profile =
            format!(r#"{{"format":"{FORMAT}","profile":"other","events":[]}}"#).into_bytes();
        assert!(inspect(&wrong_profile).is_err());
    }

    #[test]
    fn complete_source_replay_rejects_report_tampering() {
        let source = source(
            r#"{"ordinal":1,"kind":"system_reset","resident_reinitialized":true,"backing_reinitialized":false}"#,
        );
        let receipt = sha256(&source);
        let mut report = inspect_reset_cache_lifetime(&source, &receipt).unwrap();
        report.witnesses[0].backing_generation_after = 2;
        assert!(verify_reset_cache_lifetime_report(&report, &source, &receipt).is_err());
    }

    #[test]
    fn report_never_claims_missing_global_proofs() {
        let source = source("");
        let report = inspect(&source).unwrap();
        assert!(!report.transition_census_certified);
        assert!(!report.hardware_semantics_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }
}
