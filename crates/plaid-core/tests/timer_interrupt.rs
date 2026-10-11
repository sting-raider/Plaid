use plaid_core::rom::sha256;
use plaid_core::timer_interrupt::{FORMAT, inspect_timer_interrupt_history};
use serde_json::json;

#[test]
fn unrepresented_elapsed_count_cannot_be_silently_treated_as_a_write() {
    let source = serde_json::to_vec(&json!({
        "format": FORMAT,
        "initial_count": 100,
        "initial_compare": 103,
        "initial_pending": false,
        "events": [{
            "record": "timer_assert",
            "ordinal": 1,
            "count": 103,
            "compare": 103,
            "pending_before": false,
            "pending_after": true,
        }],
    }))
    .unwrap();
    assert!(inspect_timer_interrupt_history(&source, &sha256(&source)).is_err());
}
