use plaid_core::{rom::sha256, software_interrupt::*};
use serde_json::{Value, json};

fn fixture(zero: bool, raw: u32, before: u8, after: u8) -> Value {
    let word = if zero { 0x40806800u32 } else { 0x40886800u32 };
    json!({"format":FORMAT,"events":[
        {"record":"begin","ordinal":1,"context":1,"epoch":1,"pc":0xffffffffa0000000u64,
            "word":word,"raw_cause":raw,"before_pending":before},
        {"record":"write","ordinal":2,"context":1,"raw_cause":raw,
            "before_pending":before,"after_pending":after},
        {"record":"end","ordinal":3,"context":1,"epoch":1,"pc":0xffffffffa0000000u64,"exception_code":0}
    ]})
}
fn inspect(data: &Value) -> Result<SoftwareInterruptHistoryReport, String> {
    let bytes = serde_json::to_vec(data).unwrap();
    inspect_software_interrupt_history(&bytes, &sha256(&bytes))
}

#[test]
fn zero_register_cause_clear_cannot_carry_nonzero_operand() {
    let report = inspect(&fixture(true, 0, 0x85, 0x84)).unwrap();
    assert_eq!(report.generations[0].source_register, 0);
    assert_eq!(report.generations[0].after_pending, 0x84);
    assert!(inspect(&fixture(true, 0x100, 0, 1)).is_err());
}

#[test]
fn source_and_report_deletion_cannot_erase_producer_or_scope() {
    let source = serde_json::to_vec(&fixture(false, 0x100, 0x84, 0x85)).unwrap();
    let digest = sha256(&source);
    let report = inspect_software_interrupt_history(&source, &digest).unwrap();
    verify_software_interrupt_report(&report, &source, &digest).unwrap();
    let deleted = serde_json::to_vec(&json!({"format":FORMAT,"events":[]})).unwrap();
    assert!(inspect_software_interrupt_history(&deleted, &digest).is_err());
    for field in [
        "generations",
        "native_complete",
        "hardware_pending_producers_certified",
        "sensor_coverage_certified",
        "interrupt_gate_chronology_certified",
        "handler_provenance_certified",
        "whole_rom_roots_certified",
    ] {
        let mut value = serde_json::to_value(&report).unwrap();
        value[field] = if field == "generations" {
            json!([])
        } else {
            json!(true)
        };
        let forged: SoftwareInterruptHistoryReport = serde_json::from_value(value).unwrap();
        assert!(verify_software_interrupt_report(&forged, &source, &digest).is_err());
    }
}

#[test]
fn typed_event_protocol_rejects_aliases_bounds_and_false_effect_fields() {
    let base = fixture(false, 0x100, 0, 1);
    for (index, field, value) in [
        (0, "ordinal", json!(true)),
        (0, "raw_cause", json!(1u64 << 32)),
        (0, "before_pending", json!(256)),
        (0, "context", json!(0)),
        (1, "producer", json!("hardware")),
        (1, "after_pending", json!(true)),
        (1, "context", json!(0)),
        (2, "exception_code", json!(32)),
    ] {
        let mut forged = base.clone();
        forged["events"][index][field] = value;
        assert!(inspect(&forged).is_err(), "accepted {index}:{field}");
    }
}
