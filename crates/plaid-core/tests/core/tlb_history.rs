use plaid_core::{
    rom::sha256,
    tlb_history::{self, TlbwiHistoryReport, TlbwiNoWriteKind},
};
use serde_json::{Value, json};

const SAME: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const OTHER: &str = "2222222222222222222222222222222222222222222222222222222222222222";

fn fp(value: &str) -> Value {
    json!({"sha256": value})
}

fn begin(ordinal: u64, epoch: u64, index: u32, staged: &str) -> Value {
    json!({
        "record":"begin",
        "ordinal":ordinal,
        "context":ordinal,
        "epoch":epoch,
        "pc":0xffff_ffff_a000_1000u64 + ordinal * 4,
        "word":0x4200_0002u32,
        "cp0_index":index,
        "staged_entry":fp(staged)
    })
}

fn write(ordinal: u64, context: u64, slot: u32, before: &str, after: &str) -> Value {
    json!({
        "record":"write",
        "ordinal":ordinal,
        "context":context,
        "slot":slot,
        "before_entry":fp(before),
        "after_entry":fp(after)
    })
}

fn end(ordinal: u64, context: u64, epoch: u64, exception_code: u8) -> Value {
    json!({
        "record":"end",
        "ordinal":ordinal,
        "context":context,
        "epoch":epoch,
        "pc":0xffff_ffff_a000_1000u64 + context * 4,
        "exception_code":exception_code
    })
}

fn history(events: Vec<Value>) -> Value {
    json!({"format":tlb_history::FORMAT,"events":events})
}

fn inspect(value: &Value) -> Result<TlbwiHistoryReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    tlb_history::inspect_tlbwi_history(&bytes, &sha256(&bytes))
}

#[test]
fn same_value_writes_mint_fresh_operation_generations() {
    let value = history(vec![
        begin(1, 1, 5, SAME),
        write(2, 1, 5, SAME, SAME),
        end(3, 1, 1, 0),
        begin(4, 1, 5, SAME),
        write(5, 4, 5, SAME, SAME),
        end(6, 4, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 2);
    assert_eq!(report.write_boundaries, 2);
    assert_eq!(report.same_content_generations, 2);
    assert_eq!(
        report
            .generations
            .iter()
            .map(|generation| generation.operation_generation)
            .collect::<Vec<_>>(),
        [1, 2]
    );
    assert!(report.generations.iter().all(|generation| {
        generation.selected_slot == 5
            && generation.same_entry_content
            && generation.before_entry == generation.after_entry
    }));
    assert!(
        !report.sensor_coverage_certified
            && !report.mapping_semantics_certified
            && !report.translation_context_certified
            && !report.cache_residency_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );
}

#[test]
fn equal_payload_in_another_slot_cannot_steal_write_identity() {
    let value = history(vec![
        begin(1, 1, 5, SAME),
        write(2, 1, 7, SAME, SAME),
        end(3, 1, 1, 0),
    ]);
    assert!(inspect(&value).is_err());
}

#[test]
fn out_of_range_and_exception_attempts_mint_no_generation() {
    let value = history(vec![
        begin(1, 1, 63, SAME),
        end(2, 1, 1, 0),
        begin(3, 1, 5, OTHER),
        end(4, 3, 1, 11),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 2);
    assert!(report.generations.is_empty());
    assert_eq!(report.no_write_attempts.len(), 2);
    assert_eq!(
        report.no_write_attempts[0].kind,
        TlbwiNoWriteKind::OutOfRangeIndex
    );
    assert_eq!(
        report.no_write_attempts[1].kind,
        TlbwiNoWriteKind::Exception { code: 11 }
    );
}

#[test]
fn missing_or_fabricated_boundaries_fail_closed() {
    let cases = [
        history(vec![begin(1, 1, 5, SAME), end(2, 1, 1, 0)]),
        history(vec![
            begin(1, 1, 63, SAME),
            write(2, 1, 31, SAME, OTHER),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, SAME),
            write(2, 1, 5, SAME, OTHER),
            write(3, 1, 5, OTHER, SAME),
            end(4, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, SAME),
            write(2, 999, 5, SAME, OTHER),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, SAME),
            write(2, 1, 5, SAME, OTHER),
            end(3, 1, 1, 11),
        ]),
    ];
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn ordering_opcode_fingerprint_and_schema_forgeries_reject() {
    let original = history(vec![
        begin(1, 2, 5, SAME),
        write(2, 1, 5, SAME, OTHER),
        end(3, 1, 2, 0),
    ]);
    let mut cases = Vec::new();

    let mut value = original.clone();
    value["events"][1]["ordinal"] = json!(3);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["word"] = json!(0x4200_0006u32);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["pc"] = json!(0xffff_ffff_a000_1001u64);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["staged_entry"]["sha256"] = json!("ABC");
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["extra"] = json!(true);
    cases.push(value);

    let mut value = original.clone();
    value["events"][2]["epoch"] = json!(1);
    cases.push(value);

    let value = history(vec![
        begin(1, 2, 5, SAME),
        write(2, 1, 5, SAME, OTHER),
        end(3, 1, 2, 0),
        begin(4, 1, 7, OTHER),
        write(5, 4, 7, OTHER, SAME),
        end(6, 4, 1, 0),
    ]);
    cases.push(value);

    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn complete_source_and_report_rechecking_resist_deletion_and_flag_forgery() {
    let value = history(vec![
        begin(1, 1, 5, SAME),
        write(2, 1, 5, SAME, SAME),
        end(3, 1, 1, 0),
    ]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = tlb_history::inspect_tlbwi_history(&bytes, &expected).unwrap();
    tlb_history::verify_tlbwi_report(&report, &bytes, &expected).unwrap();

    let shortened = serde_json::to_vec(&history(vec![])).unwrap();
    assert!(tlb_history::inspect_tlbwi_history(&shortened, &expected).is_err());

    let mut forged = report.clone();
    forged.generations.clear();
    assert!(tlb_history::verify_tlbwi_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.native_complete = true;
    assert!(tlb_history::verify_tlbwi_report(&forged, &bytes, &expected).is_err());
}

#[test]
fn identical_mapping_content_in_distinct_slots_remains_distinct_operations() {
    let value = history(vec![
        begin(1, 1, 5, SAME),
        write(2, 1, 5, SAME, SAME),
        end(3, 1, 1, 0),
        begin(4, 1, 7, SAME),
        write(5, 4, 7, SAME, SAME),
        end(6, 4, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(
        report
            .generations
            .iter()
            .map(|generation| (generation.operation_generation, generation.selected_slot))
            .collect::<Vec<_>>(),
        [(1, 5), (2, 7)]
    );
}
