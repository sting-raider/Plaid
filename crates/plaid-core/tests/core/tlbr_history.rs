use plaid_core::{
    rom::sha256,
    tlbr_history::{self, TlbrHistoryReport, TlbrNoLoadKind},
};
use serde_json::{Value, json};

const A: &str = "1111111111111111111111111111111111111111111111111111111111111111";
const B: &str = "2222222222222222222222222222222222222222222222222222222222222222";

fn fp(hash: &str, asid: u8) -> Value {
    json!({"sha256":hash,"asid":asid})
}

fn begin(ordinal: u64, epoch: u64, index: u32, hash: &str, asid: u8) -> Value {
    json!({
        "record":"begin",
        "ordinal":ordinal,
        "context":ordinal,
        "epoch":epoch,
        "pc":0xffff_ffff_a000_2000u64 + ordinal * 4,
        "word":0x4200_0001u32,
        "cp0_index":index,
        "before_context":fp(hash, asid)
    })
}

fn load(
    ordinal: u64,
    context: u64,
    slot: u32,
    selected_hash: &str,
    selected_asid: u8,
    after_hash: &str,
    after_asid: u8,
) -> Value {
    json!({
        "record":"load",
        "ordinal":ordinal,
        "context":context,
        "slot":slot,
        "selected_entry":fp(selected_hash, selected_asid),
        "after_context":fp(after_hash, after_asid)
    })
}

fn end(ordinal: u64, context: u64, epoch: u64, exception_code: u8) -> Value {
    json!({
        "record":"end",
        "ordinal":ordinal,
        "context":context,
        "epoch":epoch,
        "pc":0xffff_ffff_a000_2000u64 + context * 4,
        "exception_code":exception_code
    })
}

fn history(events: Vec<Value>) -> Value {
    json!({"format":tlbr_history::FORMAT,"events":events})
}

fn inspect(value: &Value) -> Result<TlbrHistoryReport, String> {
    let bytes = serde_json::to_vec(value).unwrap();
    tlbr_history::inspect_tlbr_history(&bytes, &sha256(&bytes))
}

#[test]
fn same_value_successful_tlbr_mints_fresh_operation_generations() {
    let value = history(vec![
        begin(1, 1, 5, A, 0x55),
        load(2, 1, 5, A, 0x55, A, 0x55),
        end(3, 1, 1, 0),
        begin(4, 1, 5, A, 0x55),
        load(5, 4, 5, A, 0x55, A, 0x55),
        end(6, 4, 1, 0),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 2);
    assert_eq!(report.load_boundaries, 2);
    assert_eq!(report.same_context_generations, 2);
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
            && generation.same_context_content
            && generation.before_context == generation.after_context
    }));
    assert!(
        !report.sensor_coverage_certified
            && !report.installed_mapping_certified
            && !report.translation_context_census_certified
            && !report.cache_residency_certified
            && !report.executable_lifetime_certified
            && !report.native_complete
    );
}

#[test]
fn successful_tlbr_preserves_context_change_without_minting_mapping_claims() {
    let value = history(vec![
        begin(1, 7, 9, A, 0x22),
        load(2, 1, 9, B, 0x55, B, 0x55),
        end(3, 1, 7, 0),
    ]);
    let report = inspect(&value).unwrap();
    let generation = &report.generations[0];
    assert_eq!(generation.before_context.asid, 0x22);
    assert_eq!(generation.after_context.asid, 0x55);
    assert!(!generation.same_context_content);
    assert!(!report.installed_mapping_certified);
    assert!(!report.translation_context_census_certified);
}

#[test]
fn equal_payload_or_asid_cannot_steal_selected_slot_identity() {
    let cases = [
        history(vec![
            begin(1, 1, 5, A, 0x55),
            load(2, 1, 7, A, 0x55, A, 0x55),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, A, 0x55),
            load(2, 1, 5, A, 0x55, B, 0x55),
            end(3, 1, 1, 0),
        ]),
    ];
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "identity forgery {index} accepted");
    }
}

#[test]
fn out_of_range_and_exception_attempts_mint_no_context_generation() {
    let value = history(vec![
        begin(1, 1, 63, A, 0x11),
        end(2, 1, 1, 0),
        begin(3, 1, 5, A, 0x11),
        end(4, 3, 1, 11),
    ]);
    let report = inspect(&value).unwrap();
    assert_eq!(report.attempts, 2);
    assert!(report.generations.is_empty());
    assert_eq!(report.no_load_attempts.len(), 2);
    assert_eq!(
        report.no_load_attempts[0].kind,
        TlbrNoLoadKind::OutOfRangeIndex
    );
    assert_eq!(
        report.no_load_attempts[1].kind,
        TlbrNoLoadKind::Exception { code: 11 }
    );
}

#[test]
fn missing_reordered_or_fabricated_load_boundaries_fail_closed() {
    let cases = [
        history(vec![begin(1, 1, 5, A, 1), end(2, 1, 1, 0)]),
        history(vec![
            begin(1, 1, 63, A, 1),
            load(2, 1, 31, A, 1, A, 1),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, A, 1),
            load(2, 1, 5, B, 2, B, 2),
            load(3, 1, 5, B, 2, B, 2),
            end(4, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, A, 1),
            load(2, 999, 5, B, 2, B, 2),
            end(3, 1, 1, 0),
        ]),
        history(vec![
            begin(1, 1, 5, A, 1),
            load(2, 1, 5, B, 2, B, 2),
            end(3, 1, 1, 11),
        ]),
    ];
    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "boundary forgery {index} accepted");
    }
}

#[test]
fn opcode_ordering_fingerprint_epoch_and_schema_forgeries_reject() {
    let original = history(vec![
        begin(1, 2, 5, A, 1),
        load(2, 1, 5, B, 2, B, 2),
        end(3, 1, 2, 0),
    ]);
    let mut cases = Vec::new();

    let mut value = original.clone();
    value["events"][1]["ordinal"] = json!(3);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["word"] = json!(0x4200_0008u32);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["pc"] = json!(0xffff_ffff_a000_2001u64);
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["before_context"]["sha256"] = json!("ABC");
    cases.push(value);

    let mut value = original.clone();
    value["events"][0]["extra"] = json!(true);
    cases.push(value);

    let mut value = original.clone();
    value["events"][2]["epoch"] = json!(1);
    cases.push(value);

    let value = history(vec![
        begin(1, 2, 5, A, 1),
        load(2, 1, 5, B, 2, B, 2),
        end(3, 1, 2, 0),
        begin(4, 1, 7, B, 2),
        load(5, 4, 7, A, 1, A, 1),
        end(6, 4, 1, 0),
    ]);
    cases.push(value);

    for (index, value) in cases.iter().enumerate() {
        assert!(inspect(value).is_err(), "schema forgery {index} accepted");
    }
}

#[test]
fn complete_source_and_report_rechecking_resist_deletion_and_flag_forgery() {
    let value = history(vec![
        begin(1, 1, 5, A, 0x55),
        load(2, 1, 5, A, 0x55, A, 0x55),
        end(3, 1, 1, 0),
    ]);
    let bytes = serde_json::to_vec(&value).unwrap();
    let expected = sha256(&bytes);
    let report = tlbr_history::inspect_tlbr_history(&bytes, &expected).unwrap();
    tlbr_history::verify_tlbr_report(&report, &bytes, &expected).unwrap();

    let shortened = serde_json::to_vec(&history(vec![])).unwrap();
    assert!(tlbr_history::inspect_tlbr_history(&shortened, &expected).is_err());

    let mut forged = report.clone();
    forged.generations.clear();
    assert!(tlbr_history::verify_tlbr_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.installed_mapping_certified = true;
    assert!(tlbr_history::verify_tlbr_report(&forged, &bytes, &expected).is_err());

    let mut forged = report.clone();
    forged.native_complete = true;
    assert!(tlbr_history::verify_tlbr_report(&forged, &bytes, &expected).is_err());
}
