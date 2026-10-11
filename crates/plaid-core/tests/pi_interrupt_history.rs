use plaid_core::{
    pi_interrupt_history::{
        self, CpuRcpPendingEvidence, PiInterruptHistoryReport, PiPollCause, RawPiEvidence,
    },
    rom::sha256,
};
use serde_json::{Value, json};

fn completion(ordinal: u64, request: u64, token: u64) -> Value {
    json!({
        "record":"completion",
        "ordinal":ordinal,
        "request":request,
        "token":token,
        "dispatch_event":1
    })
}

fn mask(ordinal: u64, enabled: bool) -> Value {
    json!({"record":"mask_write","ordinal":ordinal,"enabled":enabled})
}

fn clear(ordinal: u64) -> Value {
    json!({"record":"interrupt_clear","ordinal":ordinal})
}

fn restore(ordinal: u64) -> Value {
    json!({"record":"restore_boundary","ordinal":ordinal})
}

fn history(events: Vec<Value>) -> Value {
    json!({"format":pi_interrupt_history::FORMAT,"events":events})
}

fn inspect(value: &Value) -> Result<PiInterruptHistoryReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    pi_interrupt_history::inspect_pi_interrupt_history(&bytes, &sha256(&bytes))
}

#[test]
fn masked_completion_requires_observed_mask_operation_before_pending_is_certified() {
    let value = history(vec![completion(1, 1, 11), mask(2, true)]);
    let report = inspect(&value).unwrap();

    assert_eq!(report.completions.len(), 1);
    assert_eq!(report.polls.len(), 2);
    assert_eq!(report.unknown_polls, 1);
    assert_eq!(report.certified_pending_assertions, 1);
    assert_eq!(
        report.polls[0].cpu_rcp_pending,
        CpuRcpPendingEvidence::Unknown
    );
    assert_eq!(
        report.polls[1].cpu_rcp_pending,
        CpuRcpPendingEvidence::Asserted {
            completion_generation: 1,
            request: 1,
            token: 11,
            dispatch_event: 1,
        }
    );
    assert_eq!(
        report.polls[1].cause,
        PiPollCause::MaskWrite { same_value: false }
    );
    assert_eq!(
        report.final_raw_pi,
        RawPiEvidence::Completion {
            completion_generation: 1,
            request: 1,
            token: 11,
            dispatch_event: 1,
        }
    );
    assert_eq!(report.final_mi_pi_mask, Some(true));
    assert!(
        !report.sensor_coverage_certified
            && !report.hardware_timing_certified
            && !report.cpu_interrupt_gate_certified
            && !report.root_transfer_certified
            && !report.handler_provenance_certified
            && !report.native_complete
    );
}

#[test]
fn same_value_mask_repoll_is_fresh_but_does_not_steal_raw_producer() {
    let value = history(vec![mask(1, true), completion(2, 7, 70), mask(3, true)]);
    let report = inspect(&value).unwrap();

    assert_eq!(report.same_value_mask_writes, 1);
    assert_eq!(
        report
            .polls
            .iter()
            .map(|poll| poll.poll_generation)
            .collect::<Vec<_>>(),
        [1, 2, 3]
    );
    assert_eq!(
        report.polls[2].cause,
        PiPollCause::MaskWrite { same_value: true }
    );
    assert_eq!(report.polls[1].raw_pi, report.polls[2].raw_pi);
    assert_eq!(
        report.polls[2].cpu_rcp_pending,
        CpuRcpPendingEvidence::Asserted {
            completion_generation: 1,
            request: 7,
            token: 70,
            dispatch_event: 1,
        }
    );
}

#[test]
fn interrupt_clear_cuts_completion_ancestry_before_later_repoll() {
    let value = history(vec![
        mask(1, true),
        completion(2, 1, 10),
        clear(3),
        mask(4, true),
    ]);
    let report = inspect(&value).unwrap();

    assert!(matches!(
        report.polls[1].cpu_rcp_pending,
        CpuRcpPendingEvidence::Asserted { .. }
    ));
    assert_eq!(
        report.polls[2].cpu_rcp_pending,
        CpuRcpPendingEvidence::Deasserted
    );
    assert_eq!(report.polls[2].raw_pi, RawPiEvidence::Low);
    assert_eq!(report.polls[3].raw_pi, RawPiEvidence::Low);
    assert_eq!(
        report.final_cpu_rcp_pending,
        CpuRcpPendingEvidence::Deasserted
    );
}

#[test]
fn restore_boundary_forgets_equal_looking_state_until_new_operations_reestablish_it() {
    let value = history(vec![
        mask(1, true),
        completion(2, 1, 10),
        restore(3),
        mask(4, true),
        completion(5, 2, 20),
    ]);
    let report = inspect(&value).unwrap();

    assert_eq!(report.restore_cuts, [3]);
    assert_eq!(report.polls[2].ordinal, 4);
    assert_eq!(
        report.polls[2].cpu_rcp_pending,
        CpuRcpPendingEvidence::Unknown
    );
    assert_eq!(
        report.polls[3].cpu_rcp_pending,
        CpuRcpPendingEvidence::Asserted {
            completion_generation: 2,
            request: 2,
            token: 20,
            dispatch_event: 1,
        }
    );
}

#[test]
fn mask_off_deasserts_even_when_raw_producer_is_known_and_later_unmask_reuses_it() {
    let value = history(vec![mask(1, false), completion(2, 3, 30), mask(3, true)]);
    let report = inspect(&value).unwrap();

    assert_eq!(
        report.polls[1].cpu_rcp_pending,
        CpuRcpPendingEvidence::Deasserted
    );
    assert_eq!(
        report.polls[2].cpu_rcp_pending,
        CpuRcpPendingEvidence::Asserted {
            completion_generation: 1,
            request: 3,
            token: 30,
            dispatch_event: 1,
        }
    );
}

#[test]
fn copy_payload_and_current_snapshot_fields_cannot_be_smuggled_into_producer_history() {
    let mut value = history(vec![completion(1, 1, 10)]);
    value["events"][0]["payload"] = json!(0x66);
    assert!(inspect(&value).is_err());

    let value = json!({
        "format":pi_interrupt_history::FORMAT,
        "events":[{"record":"pi_copy","ordinal":1,"request":1,"payload":0x66}]
    });
    assert!(inspect(&value).is_err());
}

#[test]
fn reused_missing_or_reordered_completion_identities_fail_closed() {
    let cases = [
        history(vec![completion(1, 0, 10)]),
        history(vec![completion(1, 1, 0)]),
        history(vec![completion(1, 1, 10), completion(2, 1, 11)]),
        history(vec![completion(1, 1, 10), completion(2, 2, 10)]),
        history(vec![completion(2, 1, 10)]),
        json!({
            "format":pi_interrupt_history::FORMAT,
            "events":[{
                "record":"completion",
                "ordinal":1,
                "request":1,
                "token":10,
                "dispatch_event":2
            }]
        }),
    ];

    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn complete_source_hash_and_report_replay_resist_deletion_and_flag_forgery() {
    let value = history(vec![mask(1, true), completion(2, 1, 10)]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = pi_interrupt_history::inspect_pi_interrupt_history(&bytes, &expected).unwrap();
    pi_interrupt_history::verify_pi_interrupt_report(&report, &bytes, &expected).unwrap();

    let shortened = serde_json::to_vec(&history(vec![mask(1, true)])).unwrap();
    assert!(pi_interrupt_history::inspect_pi_interrupt_history(&shortened, &expected).is_err());

    let mut forged = report.clone();
    forged.completions.clear();
    assert!(pi_interrupt_history::verify_pi_interrupt_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.native_complete = true;
    assert!(pi_interrupt_history::verify_pi_interrupt_report(&forged, &bytes, &expected).is_err());
}
