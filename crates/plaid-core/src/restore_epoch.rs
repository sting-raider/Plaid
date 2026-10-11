//! Snapshot-qualified restore roots for compiler-time exploration.
//!
//! A synchronized restore can reinstall executable-relevant state without replaying
//! the live operations that originally produced it. Equal values therefore do not
//! identify a causal predecessor across load. This module binds a finite restore
//! history to a trusted source receipt and mints fresh snapshot-qualified roots.
use crate::rom::sha256;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub const FORMAT: &str = "plaid-restore-epoch-history-v0";
pub const REPORT_FORMAT: &str = "plaid-restore-epoch-report-v0";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    records: Vec<Record>,
}

#[derive(Debug, Deserialize)]
#[serde(tag = "record", rename_all = "snake_case", deny_unknown_fields)]
enum Record {
    SnapshotSave {
        ordinal: u64,
        snapshot_id: String,
        installed_tlb_sha256: String,
        translation_context_sha256: String,
        instruction_cache_sha256: String,
    },
    SnapshotLoad {
        ordinal: u64,
        snapshot_id: String,
        restore_epoch: u64,
    },
    ComponentRestore {
        ordinal: u64,
        load_ordinal: u64,
        snapshot_id: String,
        restore_epoch: u64,
        component: RestoreComponent,
        state_sha256: String,
    },
}

impl Record {
    fn ordinal(&self) -> u64 {
        match self {
            Self::SnapshotSave { ordinal, .. }
            | Self::SnapshotLoad { ordinal, .. }
            | Self::ComponentRestore { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RestoreComponent {
    InstalledTlb,
    TranslationContext,
    InstructionCache,
}

impl RestoreComponent {
    const ALL: [Self; 3] = [
        Self::InstalledTlb,
        Self::TranslationContext,
        Self::InstructionCache,
    ];
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreRoot {
    pub snapshot_id: String,
    pub restore_epoch: u64,
    pub load_ordinal: u64,
    pub component: RestoreComponent,
    pub state_sha256: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreEpoch {
    pub snapshot_id: String,
    pub restore_epoch: u64,
    pub load_ordinal: u64,
    pub roots: Vec<RestoreRoot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreEpochReport {
    pub format: String,
    pub source_sha256: String,
    pub snapshots_saved: usize,
    pub loads: Vec<RestoreEpoch>,
    pub source_receipt_verified: bool,
    pub declared_three_component_scope_complete: bool,
    pub full_system_restore_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoredExecutionContext {
    pub snapshot_id: String,
    pub restore_epoch: u64,
    pub load_ordinal: u64,
    pub installed_tlb_sha256: String,
    pub translation_context_sha256: String,
    pub instruction_cache_sha256: String,
}

#[derive(Debug, Clone)]
struct SavedSnapshot {
    digests: BTreeMap<RestoreComponent, String>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok { Ok(()) } else { Err(message.into()) }
}

fn valid_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}

fn valid_snapshot_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b':' | b'-'))
}

fn snapshot(
    installed_tlb_sha256: &str,
    translation_context_sha256: &str,
    instruction_cache_sha256: &str,
) -> Result<SavedSnapshot, String> {
    for digest in [
        installed_tlb_sha256,
        translation_context_sha256,
        instruction_cache_sha256,
    ] {
        require(valid_digest(digest), "invalid snapshot component digest")?;
    }
    Ok(SavedSnapshot {
        digests: BTreeMap::from([
            (RestoreComponent::InstalledTlb, installed_tlb_sha256.into()),
            (
                RestoreComponent::TranslationContext,
                translation_context_sha256.into(),
            ),
            (
                RestoreComponent::InstructionCache,
                instruction_cache_sha256.into(),
            ),
        ]),
    })
}

/// Replay a finite synchronized-restore history against an externally trusted
/// complete-source receipt.
///
/// Every accepted load creates a fresh restore epoch and exactly one root for each
/// of the three components validated by the bounded reference experiment. This
/// authenticates the supplied history only; it does not prove that other emulator
/// state, devices, queues, RSP state, hidden memories, or frontend sidecars were
/// captured or restored completely.
pub fn inspect_restore_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RestoreEpochReport, String> {
    let digest = sha256(source);
    require(digest == expected_sha256, "restore source receipt mismatch")?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported restore history format",
    )?;

    for (index, record) in history.records.iter().enumerate() {
        require(
            record.ordinal() == index as u64 + 1,
            "noncontiguous restore source ordinals",
        )?;
    }

    let mut snapshots = BTreeMap::<String, SavedSnapshot>::new();
    let mut loads = Vec::new();
    let mut last_epoch = 0_u64;
    let mut index = 0_usize;

    while index < history.records.len() {
        match &history.records[index] {
            Record::SnapshotSave {
                snapshot_id,
                installed_tlb_sha256,
                translation_context_sha256,
                instruction_cache_sha256,
                ..
            } => {
                require(
                    valid_snapshot_id(snapshot_id),
                    "invalid restore snapshot identity",
                )?;
                let saved = snapshot(
                    installed_tlb_sha256,
                    translation_context_sha256,
                    instruction_cache_sha256,
                )?;
                require(
                    snapshots.insert(snapshot_id.clone(), saved).is_none(),
                    "duplicate restore snapshot identity",
                )?;
                index += 1;
            }
            Record::SnapshotLoad {
                ordinal,
                snapshot_id,
                restore_epoch,
            } => {
                require(
                    valid_snapshot_id(snapshot_id),
                    "invalid restore snapshot identity",
                )?;
                let saved = snapshots
                    .get(snapshot_id)
                    .ok_or("restore references unsaved snapshot")?;
                require(
                    *restore_epoch != 0 && *restore_epoch > last_epoch,
                    "restore epoch reused or reordered",
                )?;

                let mut roots = Vec::with_capacity(RestoreComponent::ALL.len());
                let mut seen = BTreeSet::new();
                for offset in 1..=RestoreComponent::ALL.len() {
                    let Some(Record::ComponentRestore {
                        load_ordinal,
                        snapshot_id: component_snapshot,
                        restore_epoch: component_epoch,
                        component,
                        state_sha256,
                        ..
                    }) = history.records.get(index + offset)
                    else {
                        return Err("synchronized restore missing component root".into());
                    };
                    require(
                        *load_ordinal == *ordinal
                            && component_snapshot == snapshot_id
                            && *component_epoch == *restore_epoch,
                        "restore component boundary identity mismatch",
                    )?;
                    require(seen.insert(*component), "duplicate restore component root")?;
                    require(
                        valid_digest(state_sha256),
                        "invalid restored component digest",
                    )?;
                    let expected = saved
                        .digests
                        .get(component)
                        .expect("all validated restore components are saved");
                    require(
                        state_sha256 == expected,
                        "restored component differs from saved snapshot",
                    )?;
                    roots.push(RestoreRoot {
                        snapshot_id: snapshot_id.clone(),
                        restore_epoch: *restore_epoch,
                        load_ordinal: *ordinal,
                        component: *component,
                        state_sha256: state_sha256.clone(),
                    });
                }
                require(
                    RestoreComponent::ALL
                        .iter()
                        .all(|component| seen.contains(component)),
                    "synchronized restore component set incomplete",
                )?;
                roots.sort_by_key(|root| root.component);
                loads.push(RestoreEpoch {
                    snapshot_id: snapshot_id.clone(),
                    restore_epoch: *restore_epoch,
                    load_ordinal: *ordinal,
                    roots,
                });
                last_epoch = *restore_epoch;
                index += RestoreComponent::ALL.len() + 1;
            }
            Record::ComponentRestore { .. } => {
                return Err("orphan restore component root".into());
            }
        }
    }

    Ok(RestoreEpochReport {
        format: REPORT_FORMAT.into(),
        source_sha256: digest,
        snapshots_saved: snapshots.len(),
        loads,
        source_receipt_verified: true,
        declared_three_component_scope_complete: true,
        full_system_restore_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

/// Compose the three bounded restored components for a later executable-context
/// proof. All roots must come from the same snapshot load and restore epoch.
/// Value equality never repairs a mixed-epoch or mixed-snapshot history.
pub fn compose_restored_execution_context(
    installed_tlb: &RestoreRoot,
    translation_context: &RestoreRoot,
    instruction_cache: &RestoreRoot,
) -> Result<RestoredExecutionContext, String> {
    require(
        installed_tlb.component == RestoreComponent::InstalledTlb
            && translation_context.component == RestoreComponent::TranslationContext
            && instruction_cache.component == RestoreComponent::InstructionCache,
        "restore composition component kind mismatch",
    )?;
    require(
        installed_tlb.snapshot_id == translation_context.snapshot_id
            && installed_tlb.snapshot_id == instruction_cache.snapshot_id,
        "restore composition mixes snapshot identities",
    )?;
    require(
        installed_tlb.restore_epoch == translation_context.restore_epoch
            && installed_tlb.restore_epoch == instruction_cache.restore_epoch,
        "restore composition mixes restore epochs",
    )?;
    require(
        installed_tlb.load_ordinal == translation_context.load_ordinal
            && installed_tlb.load_ordinal == instruction_cache.load_ordinal,
        "restore composition mixes load boundaries",
    )?;
    Ok(RestoredExecutionContext {
        snapshot_id: installed_tlb.snapshot_id.clone(),
        restore_epoch: installed_tlb.restore_epoch,
        load_ordinal: installed_tlb.load_ordinal,
        installed_tlb_sha256: installed_tlb.state_sha256.clone(),
        translation_context_sha256: translation_context.state_sha256.clone(),
        instruction_cache_sha256: instruction_cache.state_sha256.clone(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{Value, json};

    const TLB: &str = "1111111111111111111111111111111111111111111111111111111111111111";
    const CTX: &str = "2222222222222222222222222222222222222222222222222222222222222222";
    const CACHE: &str = "3333333333333333333333333333333333333333333333333333333333333333";
    const OTHER: &str = "4444444444444444444444444444444444444444444444444444444444444444";

    fn save(ordinal: u64, id: &str, tlb: &str, ctx: &str, cache: &str) -> Value {
        json!({
            "record":"snapshot_save",
            "ordinal":ordinal,
            "snapshot_id":id,
            "installed_tlb_sha256":tlb,
            "translation_context_sha256":ctx,
            "instruction_cache_sha256":cache
        })
    }

    fn load_records(
        start: u64,
        id: &str,
        epoch: u64,
        tlb: &str,
        ctx: &str,
        cache: &str,
    ) -> Vec<Value> {
        vec![
            json!({"record":"snapshot_load","ordinal":start,"snapshot_id":id,"restore_epoch":epoch}),
            json!({"record":"component_restore","ordinal":start+1,"load_ordinal":start,"snapshot_id":id,"restore_epoch":epoch,"component":"installed_tlb","state_sha256":tlb}),
            json!({"record":"component_restore","ordinal":start+2,"load_ordinal":start,"snapshot_id":id,"restore_epoch":epoch,"component":"translation_context","state_sha256":ctx}),
            json!({"record":"component_restore","ordinal":start+3,"load_ordinal":start,"snapshot_id":id,"restore_epoch":epoch,"component":"instruction_cache","state_sha256":cache}),
        ]
    }

    fn inspect(records: Vec<Value>) -> Result<RestoreEpochReport, String> {
        let bytes = serde_json::to_vec(&json!({"format":FORMAT,"records":records})).unwrap();
        let digest = sha256(&bytes);
        inspect_restore_history(&bytes, &digest)
    }

    fn roots(load: &RestoreEpoch) -> (&RestoreRoot, &RestoreRoot, &RestoreRoot) {
        (&load.roots[0], &load.roots[1], &load.roots[2])
    }

    #[test]
    fn repeated_equal_state_loads_mint_distinct_restore_roots() {
        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        records.extend(load_records(2, "S0", 1, TLB, CTX, CACHE));
        records.extend(load_records(6, "S0", 2, TLB, CTX, CACHE));
        let report = inspect(records).unwrap();
        assert_eq!(report.loads.len(), 2);
        assert_eq!(
            report.loads[0].roots[2].state_sha256,
            report.loads[1].roots[2].state_sha256
        );
        assert_ne!(report.loads[0].roots[2], report.loads[1].roots[2]);
        assert_eq!(report.loads[0].restore_epoch, 1);
        assert_eq!(report.loads[1].restore_epoch, 2);
        assert!(!report.full_system_restore_coverage_certified);
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn valid_roots_compose_only_within_one_load() {
        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        records.extend(load_records(2, "S0", 1, TLB, CTX, CACHE));
        let report = inspect(records).unwrap();
        let (tlb, context, cache) = roots(&report.loads[0]);
        let composed = compose_restored_execution_context(tlb, context, cache).unwrap();
        assert_eq!(composed.snapshot_id, "S0");
        assert_eq!(composed.restore_epoch, 1);
    }

    #[test]
    fn equal_values_do_not_allow_cross_epoch_composition() {
        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        records.extend(load_records(2, "S0", 1, TLB, CTX, CACHE));
        records.extend(load_records(6, "S0", 2, TLB, CTX, CACHE));
        let report = inspect(records).unwrap();
        let (old_tlb, _, _) = roots(&report.loads[0]);
        let (_, new_context, new_cache) = roots(&report.loads[1]);
        let error =
            compose_restored_execution_context(old_tlb, new_context, new_cache).unwrap_err();
        assert!(error.contains("mixes restore epochs"));
    }

    #[test]
    fn equal_values_do_not_allow_cross_snapshot_composition() {
        let mut records = vec![
            save(1, "S0", TLB, CTX, CACHE),
            save(2, "S1", TLB, CTX, CACHE),
        ];
        records.extend(load_records(3, "S0", 1, TLB, CTX, CACHE));
        records.extend(load_records(7, "S1", 2, TLB, CTX, CACHE));
        let report = inspect(records).unwrap();
        let (first_tlb, _, _) = roots(&report.loads[0]);
        let (_, second_context, second_cache) = roots(&report.loads[1]);
        let error = compose_restored_execution_context(first_tlb, second_context, second_cache)
            .unwrap_err();
        assert!(error.contains("mixes snapshot identities"));
    }

    #[test]
    fn deleted_or_duplicate_component_roots_reject() {
        let mut missing = vec![save(1, "S0", TLB, CTX, CACHE)];
        let mut load = load_records(2, "S0", 1, TLB, CTX, CACHE);
        load.pop();
        missing.extend(load);
        assert!(
            inspect(missing)
                .unwrap_err()
                .contains("missing component root")
        );

        let mut duplicate = vec![save(1, "S0", TLB, CTX, CACHE)];
        let mut load = load_records(2, "S0", 1, TLB, CTX, CACHE);
        load[3]["component"] = json!("translation_context");
        duplicate.extend(load);
        assert!(
            inspect(duplicate)
                .unwrap_err()
                .contains("duplicate restore component")
        );
    }

    #[test]
    fn restored_digest_must_match_saved_snapshot() {
        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        records.extend(load_records(2, "S0", 1, TLB, CTX, OTHER));
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("differs from saved snapshot")
        );
    }

    #[test]
    fn unsaved_snapshot_and_reused_epoch_reject() {
        let records = load_records(1, "missing", 1, TLB, CTX, CACHE);
        assert!(inspect(records).unwrap_err().contains("unsaved snapshot"));

        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        records.extend(load_records(2, "S0", 1, TLB, CTX, CACHE));
        records.extend(load_records(6, "S0", 1, TLB, CTX, CACHE));
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("reused or reordered")
        );
    }

    #[test]
    fn component_boundary_metadata_cannot_be_reassigned() {
        let mut records = vec![save(1, "S0", TLB, CTX, CACHE)];
        let mut load = load_records(2, "S0", 1, TLB, CTX, CACHE);
        load[1]["load_ordinal"] = json!(99u64);
        records.extend(load);
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("boundary identity mismatch")
        );
    }

    #[test]
    fn source_receipt_and_order_are_bound() {
        let records = vec![save(1, "S0", TLB, CTX, CACHE)];
        let bytes = serde_json::to_vec(&json!({"format":FORMAT,"records":records})).unwrap();
        assert!(
            inspect_restore_history(&bytes, &"0".repeat(64))
                .unwrap_err()
                .contains("source receipt mismatch")
        );

        let records = vec![save(2, "S0", TLB, CTX, CACHE)];
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("noncontiguous restore source ordinals")
        );
    }

    #[test]
    fn invalid_snapshot_identity_and_orphan_component_reject() {
        let records = vec![save(1, "bad id", TLB, CTX, CACHE)];
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("invalid restore snapshot identity")
        );

        let records = vec![json!({
            "record":"component_restore","ordinal":1,"load_ordinal":1,
            "snapshot_id":"S0","restore_epoch":1,"component":"installed_tlb",
            "state_sha256":TLB
        })];
        assert!(
            inspect(records)
                .unwrap_err()
                .contains("orphan restore component")
        );
    }
}
