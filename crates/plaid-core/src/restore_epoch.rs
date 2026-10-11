//! Snapshot-qualified restore epochs for compiler-time exploration.
//!
//! A synchronized analysis-time load can reinstall executable-relevant state without
//! replaying the live operations that originally produced it. This module therefore
//! treats a load as a fresh causal boundary instead of reconnecting restored values to
//! the latest matching live generation.
//!
//! The bounded v0 contract covers exactly three validated components: installed TLB
//! state, active translation context, and resident instruction-cache state. It does not
//! claim a complete savestate/sensor census, guest reset/NMI semantics, executable
//! lifetime closure, or native completeness.
use crate::rom::sha256;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const FORMAT: &str = "plaid-restore-epoch-history-v0";
pub const REPORT_FORMAT: &str = "plaid-restore-epoch-report-v0";

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RestoreComponent {
    InstalledTlb,
    TranslationContext,
    ResidentInstructionCache,
}

impl RestoreComponent {
    const ALL: [Self; 3] = [
        Self::InstalledTlb,
        Self::TranslationContext,
        Self::ResidentInstructionCache,
    ];
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ComponentState {
    component: RestoreComponent,
    state_digest: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
enum Event {
    LiveGeneration {
        ordinal: u64,
        component: RestoreComponent,
        generation: u64,
        state_digest: String,
    },
    SnapshotSave {
        ordinal: u64,
        snapshot_id: String,
        components: Vec<ComponentState>,
    },
    SnapshotLoad {
        ordinal: u64,
        snapshot_id: String,
        components: Vec<ComponentState>,
    },
}

impl Event {
    fn ordinal(&self) -> u64 {
        match self {
            Self::LiveGeneration { ordinal, .. }
            | Self::SnapshotSave { ordinal, .. }
            | Self::SnapshotLoad { ordinal, .. } => *ordinal,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct History {
    format: String,
    events: Vec<Event>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum ComponentOrigin {
    LiveGeneration { generation: u64 },
    RestoreRoot {
        restore_epoch: u64,
        snapshot_id: String,
        load_ordinal: u64,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CurrentComponentState {
    pub component: RestoreComponent,
    pub state_digest: String,
    pub origin: ComponentOrigin,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreRoot {
    pub component: RestoreComponent,
    pub state_digest: String,
    pub snapshot_id: String,
    pub save_ordinal: u64,
    pub load_ordinal: u64,
    pub restore_epoch: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreEpoch {
    pub restore_epoch: u64,
    pub snapshot_id: String,
    pub save_ordinal: u64,
    pub load_ordinal: u64,
    pub roots: Vec<RestoreRoot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RestoreEpochReport {
    pub format: String,
    pub source_sha256: String,
    pub events: usize,
    pub live_generations: usize,
    pub snapshots_saved: usize,
    pub restores: Vec<RestoreEpoch>,
    pub current_components: Vec<CurrentComponentState>,
    pub source_receipt_verified: bool,
    pub sensor_completeness_certified: bool,
    pub full_system_restore_coverage_certified: bool,
    pub executable_lifetime_certified: bool,
    pub native_complete: bool,
}

#[derive(Clone)]
struct Snapshot {
    save_ordinal: u64,
    components: BTreeMap<RestoreComponent, String>,
}

fn require(ok: bool, message: &str) -> Result<(), String> {
    if ok {
        Ok(())
    } else {
        Err(message.into())
    }
}

fn valid_digest(value: &str) -> bool {
    value.len() == 64
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn valid_snapshot_id(value: &str) -> bool {
    !value.is_empty() && value.len() <= 256 && !value.chars().any(char::is_control)
}

fn component_map(states: &[ComponentState]) -> Result<BTreeMap<RestoreComponent, String>, String> {
    require(
        states.len() == RestoreComponent::ALL.len(),
        "restore snapshot must contain exactly three validated components",
    )?;
    let mut result = BTreeMap::new();
    for state in states {
        require(
            valid_digest(&state.state_digest),
            "invalid restore component state digest",
        )?;
        require(
            result
                .insert(state.component, state.state_digest.clone())
                .is_none(),
            "duplicate restore component state",
        )?;
    }
    for component in RestoreComponent::ALL {
        require(
            result.contains_key(&component),
            "missing validated restore component state",
        )?;
    }
    Ok(result)
}

/// Replay a finite, externally authenticated analysis-time snapshot chronology.
///
/// `expected_sha256` must come from a separately trusted complete-source receipt.
/// Matching it authenticates the supplied bytes but does not establish that every
/// executable-relevant emulator component or every save/load path was captured.
///
/// Each accepted `snapshot_load` always mints a new restore epoch, even when all
/// restored component digests equal current or later live-generation values.
/// Consumers must use the emitted restore roots rather than reconnecting those values
/// to an older live generation by equality.
pub fn inspect_restore_epoch_history(
    source: &[u8],
    expected_sha256: &str,
) -> Result<RestoreEpochReport, String> {
    let digest = sha256(source);
    require(
        digest == expected_sha256,
        "restore epoch source receipt mismatch",
    )?;
    let history: History = serde_json::from_slice(source).map_err(|error| error.to_string())?;
    require(
        history.format == FORMAT,
        "unsupported restore epoch history format",
    )?;

    let mut snapshots = BTreeMap::<String, Snapshot>::new();
    let mut max_live_generation = BTreeMap::<RestoreComponent, u64>::new();
    let mut current = BTreeMap::<RestoreComponent, CurrentComponentState>::new();
    let mut restores = Vec::new();
    let mut live_generations = 0usize;

    for (index, event) in history.events.iter().enumerate() {
        require(
            event.ordinal() == index as u64 + 1,
            "noncontiguous restore epoch source ordinals",
        )?;
        match event {
            Event::LiveGeneration {
                component,
                generation,
                state_digest,
                ..
            } => {
                require(
                    valid_digest(state_digest),
                    "invalid live component state digest",
                )?;
                require(*generation != 0, "zero live component generation")?;
                if let Some(previous) = max_live_generation.get(component) {
                    require(
                        generation > previous,
                        "reused or reordered live component generation",
                    )?;
                }
                max_live_generation.insert(*component, *generation);
                current.insert(
                    *component,
                    CurrentComponentState {
                        component: *component,
                        state_digest: state_digest.clone(),
                        origin: ComponentOrigin::LiveGeneration {
                            generation: *generation,
                        },
                    },
                );
                live_generations += 1;
            }
            Event::SnapshotSave {
                ordinal,
                snapshot_id,
                components,
            } => {
                require(valid_snapshot_id(snapshot_id), "invalid snapshot identity")?;
                require(
                    !snapshots.contains_key(snapshot_id),
                    "reused snapshot identity",
                )?;
                let captured = component_map(components)?;
                for (component, captured_digest) in &captured {
                    if let Some(observed) = current.get(component) {
                        require(
                            &observed.state_digest == captured_digest,
                            "snapshot save disagrees with observed component state",
                        )?;
                    }
                }
                snapshots.insert(
                    snapshot_id.clone(),
                    Snapshot {
                        save_ordinal: *ordinal,
                        components: captured,
                    },
                );
            }
            Event::SnapshotLoad {
                ordinal,
                snapshot_id,
                components,
            } => {
                require(valid_snapshot_id(snapshot_id), "invalid snapshot identity")?;
                let restored = component_map(components)?;
                let snapshot = snapshots
                    .get(snapshot_id)
                    .ok_or("snapshot load references unknown snapshot identity")?;
                require(
                    restored == snapshot.components,
                    "snapshot load component state mismatch",
                )?;

                let restore_epoch = restores.len() as u64 + 1;
                let mut roots = Vec::with_capacity(RestoreComponent::ALL.len());
                for component in RestoreComponent::ALL {
                    let state_digest = restored
                        .get(&component)
                        .expect("validated component set")
                        .clone();
                    roots.push(RestoreRoot {
                        component,
                        state_digest: state_digest.clone(),
                        snapshot_id: snapshot_id.clone(),
                        save_ordinal: snapshot.save_ordinal,
                        load_ordinal: *ordinal,
                        restore_epoch,
                    });
                    current.insert(
                        component,
                        CurrentComponentState {
                            component,
                            state_digest,
                            origin: ComponentOrigin::RestoreRoot {
                                restore_epoch,
                                snapshot_id: snapshot_id.clone(),
                                load_ordinal: *ordinal,
                            },
                        },
                    );
                }
                restores.push(RestoreEpoch {
                    restore_epoch,
                    snapshot_id: snapshot_id.clone(),
                    save_ordinal: snapshot.save_ordinal,
                    load_ordinal: *ordinal,
                    roots,
                });
            }
        }
    }

    Ok(RestoreEpochReport {
        format: REPORT_FORMAT.into(),
        source_sha256: digest,
        events: history.events.len(),
        live_generations,
        snapshots_saved: snapshots.len(),
        restores,
        current_components: current.into_values().collect(),
        source_receipt_verified: true,
        sensor_completeness_certified: false,
        full_system_restore_coverage_certified: false,
        executable_lifetime_certified: false,
        native_complete: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    const TLB_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const CTX_A: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const CACHE_A: &str = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    const TLB_B: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
    const CTX_B: &str = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";
    const CACHE_B: &str = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff";

    fn states(tlb: &str, context: &str, cache: &str) -> serde_json::Value {
        json!([
            {"component":"installed_tlb","state_digest":tlb},
            {"component":"translation_context","state_digest":context},
            {"component":"resident_instruction_cache","state_digest":cache}
        ])
    }

    fn inspect(events: serde_json::Value) -> Result<RestoreEpochReport, String> {
        let source = serde_json::to_vec(&json!({"format":FORMAT,"events":events})).unwrap();
        let digest = sha256(&source);
        inspect_restore_epoch_history(&source, &digest)
    }

    #[test]
    fn changed_future_is_cut_by_one_composed_restore_epoch() {
        let report = inspect(json!([
            {"kind":"live_generation","ordinal":1,"component":"installed_tlb","generation":1,"state_digest":TLB_A},
            {"kind":"live_generation","ordinal":2,"component":"translation_context","generation":1,"state_digest":CTX_A},
            {"kind":"live_generation","ordinal":3,"component":"resident_instruction_cache","generation":1,"state_digest":CACHE_A},
            {"kind":"snapshot_save","ordinal":4,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"live_generation","ordinal":5,"component":"installed_tlb","generation":2,"state_digest":TLB_B},
            {"kind":"live_generation","ordinal":6,"component":"translation_context","generation":2,"state_digest":CTX_B},
            {"kind":"live_generation","ordinal":7,"component":"resident_instruction_cache","generation":2,"state_digest":CACHE_B},
            {"kind":"snapshot_load","ordinal":8,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap();
        assert_eq!(report.restores.len(), 1);
        let epoch = &report.restores[0];
        assert_eq!(epoch.restore_epoch, 1);
        assert_eq!(epoch.snapshot_id, "S0");
        assert_eq!(epoch.roots.len(), 3);
        assert!(epoch.roots.iter().all(|root| root.restore_epoch == 1));
        assert!(report.current_components.iter().all(|state| matches!(state.origin, ComponentOrigin::RestoreRoot { restore_epoch: 1, .. })));
        assert!(!report.executable_lifetime_certified);
        assert!(!report.native_complete);
    }

    #[test]
    fn equal_value_newer_generations_are_not_reused_after_load() {
        let report = inspect(json!([
            {"kind":"live_generation","ordinal":1,"component":"installed_tlb","generation":1,"state_digest":TLB_A},
            {"kind":"live_generation","ordinal":2,"component":"translation_context","generation":1,"state_digest":CTX_A},
            {"kind":"live_generation","ordinal":3,"component":"resident_instruction_cache","generation":1,"state_digest":CACHE_A},
            {"kind":"snapshot_save","ordinal":4,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"live_generation","ordinal":5,"component":"installed_tlb","generation":2,"state_digest":TLB_A},
            {"kind":"live_generation","ordinal":6,"component":"translation_context","generation":2,"state_digest":CTX_A},
            {"kind":"live_generation","ordinal":7,"component":"resident_instruction_cache","generation":2,"state_digest":CACHE_A},
            {"kind":"snapshot_load","ordinal":8,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap();
        for state in &report.current_components {
            assert!(matches!(state.origin, ComponentOrigin::RestoreRoot { restore_epoch: 1, .. }));
        }
    }

    #[test]
    fn repeated_load_of_identical_snapshot_mints_fresh_epoch() {
        let report = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":2,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":3,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap();
        assert_eq!(report.restores.len(), 2);
        assert_eq!(report.restores[0].restore_epoch, 1);
        assert_eq!(report.restores[1].restore_epoch, 2);
        assert_eq!(report.restores[0].roots[0].state_digest, report.restores[1].roots[0].state_digest);
        assert_ne!(report.restores[0].roots[0].restore_epoch, report.restores[1].roots[0].restore_epoch);
    }

    #[test]
    fn post_restore_live_generation_must_continue_external_history() {
        let report = inspect(json!([
            {"kind":"live_generation","ordinal":1,"component":"installed_tlb","generation":7,"state_digest":TLB_A},
            {"kind":"snapshot_save","ordinal":2,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":3,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"live_generation","ordinal":4,"component":"installed_tlb","generation":8,"state_digest":TLB_B}
        ])).unwrap();
        let tlb = report.current_components.iter().find(|state| state.component == RestoreComponent::InstalledTlb).unwrap();
        assert_eq!(tlb.state_digest, TLB_B);
        assert_eq!(tlb.origin, ComponentOrigin::LiveGeneration { generation: 8 });
    }

    #[test]
    fn reused_or_rewound_live_generation_is_rejected_even_for_equal_values() {
        let error = inspect(json!([
            {"kind":"live_generation","ordinal":1,"component":"installed_tlb","generation":2,"state_digest":TLB_A},
            {"kind":"live_generation","ordinal":2,"component":"installed_tlb","generation":2,"state_digest":TLB_A}
        ])).unwrap_err();
        assert!(error.contains("reused or reordered"));
    }

    #[test]
    fn unknown_and_reused_snapshot_identities_are_rejected() {
        let unknown = inspect(json!([
            {"kind":"snapshot_load","ordinal":1,"snapshot_id":"missing","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(unknown.contains("unknown snapshot identity"));

        let reused = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_save","ordinal":2,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(reused.contains("reused snapshot identity"));
    }

    #[test]
    fn load_must_match_the_saved_component_state() {
        let error = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":2,"snapshot_id":"S0","components":states(TLB_B,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(error.contains("component state mismatch"));
    }

    #[test]
    fn save_cannot_disagree_with_an_observed_component() {
        let error = inspect(json!([
            {"kind":"live_generation","ordinal":1,"component":"translation_context","generation":1,"state_digest":CTX_B},
            {"kind":"snapshot_save","ordinal":2,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(error.contains("save disagrees"));
    }

    #[test]
    fn missing_or_duplicate_component_state_is_rejected() {
        let missing = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":[
                {"component":"installed_tlb","state_digest":TLB_A},
                {"component":"translation_context","state_digest":CTX_A}
            ]}
        ])).unwrap_err();
        assert!(missing.contains("exactly three"));

        let duplicate = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":[
                {"component":"installed_tlb","state_digest":TLB_A},
                {"component":"translation_context","state_digest":CTX_A},
                {"component":"translation_context","state_digest":CTX_A}
            ]}
        ])).unwrap_err();
        assert!(duplicate.contains("duplicate restore component"));
    }

    #[test]
    fn reordered_or_deleted_source_events_fail_closed() {
        let reordered = inspect(json!([
            {"kind":"snapshot_save","ordinal":2,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(reordered.contains("noncontiguous"));

        let deleted = inspect(json!([
            {"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)},
            {"kind":"snapshot_load","ordinal":3,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}
        ])).unwrap_err();
        assert!(deleted.contains("noncontiguous"));
    }

    #[test]
    fn complete_source_receipt_mismatch_is_rejected() {
        let source = serde_json::to_vec(&json!({
            "format": FORMAT,
            "events": [{"kind":"snapshot_save","ordinal":1,"snapshot_id":"S0","components":states(TLB_A,CTX_A,CACHE_A)}]
        })).unwrap();
        let error = inspect_restore_epoch_history(&source, &"0".repeat(64)).unwrap_err();
        assert!(error.contains("source receipt mismatch"));
    }
}
