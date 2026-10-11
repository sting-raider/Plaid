use plaid_core::{
    rom::sha256,
    tlbwr_history::{self, TlbwrHistoryReport, TlbwrNoWriteKind},
};
use serde_json::{Value, json};

const SAME: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const OTHER: &str = "2222222222222222222222222222222222222222222222222222222222222222";

fn fp(value: &str) -> Value {
    json!({"sha256": value})
}

fn begin(ordinal: u64, epoch: u64, index: u32, wired: u8, staged: &str) -> Value {
    json!({
        "record":"begin",
        "ordinal":ordinal,
        "context":ordinal,
        "epoch":epoch,
        "pc":0xffff_ffff_a000_1000u64 + ordinal * 4,
        "word":0x4200_0006u32,
        "cp0_index":index,
        "wired":wired,
        "staged_entry":fp(staged)
    })
}

fn select(ordinal: u64, context: u64, slot: u8) -> Value {
    json!({
        "record":"select",
        "ordinal":ordinal,
        "context":context,
        "slot":slot
    })
}

fn write(ordinal: u64, context: u64, slot: u8, before: &str, after: &str) -> Value {
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
    json!({"format":tlbwr_history::FORMAT,"events":events})
}

fn inspect(value: &Value) -> Result<TlbwrHistoryReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    tlbwr_history::inspect_tlbwr_history(&bytes, &sha256(&bytes))
}

#[test]
fn random_selection_not_cp0_index_names_the_written_slot() {
    let value = history(vec![
        begin(1, 1, 7, 31, SAME),
        select(2, 1, 31),
        write(3, 1, 31, OTHER, SAME),
        end(4, 1, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 1);
    assert_eq!(report.selection_boundaries, 1);
    assert_eq!(report.write_boundaries, 1);
    let generation = &report.generations[0];
    assert_eq!(generation.cp0_index, 7);
    assert_eq!(generation.wired, 31);
    assert_eq!(generation.selected_slot, 31);
    assert_eq!(generation.select_ordinal, 2);
    assert!(!generation.same_entry_content);
    assert!(
        !report.sensor_coverage_certified
            && !report.mapping_semantics_certified
            && !report.hardware_random_distribution_certified
            && !report.translation_context_certified
            && !report.cache_residency_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );
}

#[test]
fn same_value_writes_mint_fresh_operation_generations() {
    let value = history(vec![
        begin(1, 1, 7, 31, SAME),
        select(2, 1, 31),
        write(3, 1, 31, SAME, SAME),
        end(4, 1, 1, 0),
        begin(5, 1, 5, 31, SAME),
        select(6, 5, 31),
        write(7, 5, 31, SAME, SAME),
        end(8, 5, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.same_content_generations, 2);
    assert_eq!(
        report
            .generations
            .iter()
            .map(|generation| (generation.operation_generation, generation.selected_slot))
            .collect::<Vec<_>>(),
        [(1, 31), (2, 31)]
    );
}

#[test]
fn captured_wired_bounds_selection_without_predicting_random_choice() {
    let good = history(vec![
        begin(1, 1, 5, 30, SAME),
        select(2, 1, 31),
        write(3, 1, 31, SAME, OTHER),
        end(4, 1, 1, 0),
    ]);
    assert!(inspect(&good).is_ok());
    let below = history(vec![
        begin(1, 1, 5, 31, SAME),
        select(2, 1, 30),
        write(3, 1, 30, SAME, OTHER),
        end(4, 1, 1, 0),
    ]);
    assert!(inspect(&below).is_err());
    assert!(inspect(&history(vec![begin(1, 1, 5, 32, SAME), end(2, 1, 1, 11)])).is_err());
}

#[test]
fn out_of_range_selection_rejects_and_exception_mints_no_generation() {
    let unsupported = history(vec![
        begin(1, 1, 5, 63, SAME),
        select(2, 1, 63),
        end(3, 1, 1, 0),
    ]);
    assert!(inspect(&unsupported).is_err());
    let value = history(vec![begin(1, 1, 9, 2, OTHER), end(2, 1, 1, 11)]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 1);
    assert_eq!(report.selection_boundaries, 0);
    assert!(report.generations.is_empty());
    assert_eq!(report.no_write_attempts.len(), 1);
    assert_eq!(
        report.no_write_attempts[0].kind,
        TlbwrNoWriteKind::Exception {
            code: 11,
            selected_slot: None
        }
    );
}

#[test]
fn missing_or_fabricated_selection_and_write_boundaries_fail_closed() {
    let cases = [
        history(vec![begin(1, 1, 7, 31, SAME), end(2, 1, 1, 0)]),
        history(vec![
            begin(1, 1, 7, 31, SAME),
            select(2, 1, 31),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 7, 31, SAME),
            write(2, 1, 31, SAME, OTHER),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 7, 31, SAME),
            select(2, 1, 31),
            write(3, 1, 7, SAME, OTHER),
            end(4, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 7, 63, SAME),
            select(2, 1, 63),
            write(3, 1, 31, SAME, OTHER),
            end(4, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 7, 31, SAME),
            select(2, 1, 31),
            select(3, 1, 31),
            write(4, 1, 31, SAME, OTHER),
            end(5, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 7, 31, SAME),
            select(2, 1, 31),
            write(3, 1, 31, SAME, OTHER),
            end(4, 1, 1, 11),
        ]),
    ];
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn ordering_opcode_context_field_and_schema_forgeries_reject() {
    let original = history(vec![
        begin(1, 2, 7, 31, SAME),
        select(2, 1, 31),
        write(3, 1, 31, SAME, OTHER),
        end(4, 1, 2, 0),
    ]);
    let mut cases = Vec::new();

    let mut value = original.clone();
    value["events"][1]["ordinal"] = json!(3);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["word"] = json!(0x4200_0002u32);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["cp0_index"] = json!(64);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["wired"] = json!(64);
    cases.push(value);

    let mut value = original.clone();
    value["events"][1]["slot"] = json!(64);
    cases.push(value);

    let mut value = original.clone();
    value["events"][1]["context"] = json!(999);
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

    let value = history(vec![
        begin(1, 2, 7, 31, SAME),
        select(2, 1, 31),
        write(3, 1, 31, SAME, OTHER),
        end(4, 1, 2, 0),
        begin(5, 1, 5, 30, OTHER),
        select(6, 5, 30),
        write(7, 5, 30, OTHER, SAME),
        end(8, 5, 1, 0),
    ]);
    cases.push(value);

    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "forgery {index} accepted");
    }
}

#[test]
fn complete_source_and_report_rechecking_resist_deletion_and_flag_forgery() {
    let value = history(vec![
        begin(1, 1, 7, 31, SAME),
        select(2, 1, 31),
        write(3, 1, 31, SAME, SAME),
        end(4, 1, 1, 0),
    ]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = tlbwr_history::inspect_tlbwr_history(&bytes, &expected).unwrap();
    tlbwr_history::verify_tlbwr_report(&report, &bytes, &expected).unwrap();

    let shortened = serde_json::to_vec(&history(vec![])).unwrap();
    assert!(tlbwr_history::inspect_tlbwr_history(&shortened, &expected).is_err());

    let mut forged = report.clone();
    forged.generations.clear();
    assert!(tlbwr_history::verify_tlbwr_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.hardware_random_distribution_certified = true;
    assert!(tlbwr_history::verify_tlbwr_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.native_complete = true;
    assert!(tlbwr_history::verify_tlbwr_report(&forged, &bytes, &expected).is_err());
}

#[test]
fn identical_mapping_content_in_distinct_selected_slots_remains_distinct() {
    let value = history(vec![
        begin(1, 1, 31, 30, SAME),
        select(2, 1, 30),
        write(3, 1, 30, SAME, SAME),
        end(4, 1, 1, 0),
        begin(5, 1, 30, 30, SAME),
        select(6, 5, 31),
        write(7, 5, 31, SAME, SAME),
        end(8, 5, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(
        report
            .generations
            .iter()
            .map(|generation| {
                (
                    generation.operation_generation,
                    generation.cp0_index,
                    generation.selected_slot,
                )
            })
            .collect::<Vec<_>>(),
        [(1, 31, 30), (2, 30, 31)]
    );
}
