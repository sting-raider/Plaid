#!/usr/bin/env python3
"""Fail-closed verifier for measured decoded-CPU -> SP Word sink contexts."""
from __future__ import annotations

CODE_VA = 0xFFFFFFFFA0006000
FINAL_IMEM = [0x77,0x88,0x00,0x00, 0x55,0x66,0x77,0x88, 0x11,0x22,0x33,0x44, 0xDD,0xEE,0xFF,0x00]


def selected_payload(e: dict) -> int:
    op = e["instruction"] >> 26
    if op == 0x2B:  # SW
        return e["gpr"] & 0xFFFFFFFF
    if op == 0x28:  # SB, normalized at the actual RCP Word sink
        lane = e["address"] & 3
        return (e["gpr"] << (24 - lane * 8)) & 0xFFFFFFFF
    if op == 0x39:  # SWC1
        ft = e["rt"]
        if e["fr"]:
            return e["fpr_named"] & 0xFFFFFFFF
        if ft & 1:
            return (e["fpr_even"] >> 32) & 0xFFFFFFFF
        return e["fpr_even"] & 0xFFFFFFFF
    raise AssertionError(f"unexpected producer opcode {op:#x}")


def verify(doc: dict) -> dict:
    events = doc["events"]
    outcomes = {x["phase"]: x for x in doc["outcomes"]}
    assert [e["phase"] for e in events] == [1, 2, 0, 3, 4, 5, 6], events
    assert [e["ordinal"] for e in events] == list(range(1, 8))
    assert all(e["bank"] == 1 for e in events)

    by_phase = {e["phase"]: e for e in events if e["phase"]}
    for phase in range(1, 7):
        e = by_phase[phase]
        assert e["pc"] == CODE_VA
        assert e["value"] == selected_payload(e), (phase, e, selected_payload(e))
        assert outcomes[phase]["exception"] == 0

    # Same PC, instruction, address and value are still separate writer generations.
    a, b = by_phase[1], by_phase[2]
    assert a["pc"] == b["pc"] and a["instruction"] == b["instruction"]
    assert a["address"] == b["address"] and a["value"] == b["value"] == 0x55667788
    assert a["ordinal"] != b["ordinal"] and a["phase"] != b["phase"]

    # Equal-address/equal-value direct CPU write outside decoded execution must not inherit a producer.
    decoy = next(e for e in events if e["phase"] == 0)
    assert decoy["address"] == a["address"] and decoy["value"] == a["value"]
    assert decoy["instruction"] == 0 and decoy["pc"] == 0

    # SB +1 widens to the full RCP Word sink and carries more than the nominal low byte.
    assert by_phase[3]["instruction"] >> 26 == 0x28
    assert by_phase[3]["value"] == 0x77880000

    # FR-sensitive SWC1 selection: even-low, paired odd-high, named odd-low.
    assert by_phase[4]["value"] == 0x55667788 and not by_phase[4]["fr"] and by_phase[4]["rt"] == 0
    assert by_phase[5]["value"] == 0x11223344 and not by_phase[5]["fr"] and by_phase[5]["rt"] == 1
    assert by_phase[6]["value"] == 0xDDEEFF00 and by_phase[6]["fr"] and by_phase[6]["rt"] == 1

    # CU1-disabled decoded SWC1 faults before any SP sink.
    assert outcomes[7]["exception"] == 11 and outcomes[7]["cop_error"] == 1
    assert not any(e["phase"] == 7 for e in events)
    assert doc["facts"]["imem"] == FINAL_IMEM
    return {
        "events": len(events),
        "attributed": 6,
        "out_of_context": 1,
        "fault_without_sink": 1,
        "same_value_distinct_generations": 2,
    }


if __name__ == "__main__":
    import json, sys
    data = json.load(sys.stdin)
    print(json.dumps(verify(data), sort_keys=True))
