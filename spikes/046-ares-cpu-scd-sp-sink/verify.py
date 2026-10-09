#!/usr/bin/env python3
"""Fail-closed verifier for decoded SCD -> completed CPU-visible SP Word sinks."""
from __future__ import annotations
import copy

CODE_VA = 0xFFFFFFFFA0006000
INITIAL_HI = 0x11223344
INITIAL_LO = 0xFFFFFFFF
INITIAL64 = 0x11223344FFFFFFFF
CHANGED64 = 0x1122334500000000
SUCCESS_IDS = {3, 4, 7, 8}
FAIL_IDS = {1, 5}
FAULT_IDS = {2, 6}


def upper_word(value: int) -> int:
    return (value >> 32) & 0xFFFFFFFF


def verify(doc: dict) -> dict:
    facts = {f["id"]: f for f in doc["facts"]}
    assert set(facts) == set(range(1, 9))

    freezes = sorted(doc["freeze_controls"], key=lambda f: f["bank"])
    assert freezes == [
        {"bank": 0, "loaded": 0, "llbit_after": True, "sysad_frozen": True},
        {"bank": 1, "loaded": 0, "llbit_after": True, "sysad_frozen": True},
    ], freezes

    events = doc["events"]
    assert [e["ordinal"] for e in events] == list(range(1, len(events) + 1))
    assert [e["case"] for e in events] == [3, 4, 7, 8, 0], events

    attributed = {e["case"]: e for e in events if e["case"]}
    assert set(attributed) == SUCCESS_IDS
    assert not any(e["case"] in FAIL_IDS | FAULT_IDS for e in events)

    for cid in FAIL_IDS:
        f = facts[cid]
        assert f["kind"] == "fail" and f["result"] == 0 and f["exception"] == 0
        assert f["source"] == INITIAL64 and f["llbit_after"] is False
        assert f["final_hi"] == INITIAL_HI and f["final_lo"] == INITIAL_LO

    for cid in FAULT_IDS:
        f = facts[cid]
        assert f["kind"] == "fault" and f["result"] == 0 and f["exception"] == 5
        expected_bad = (0xFFFFFFFFA4001000 if f["bank"] else 0xFFFFFFFFA4000000) + 1
        assert f["badva"] == expected_bad, (f, expected_bad)
        assert f["source"] == INITIAL64 and f["llbit_after"] is True
        assert f["final_hi"] == INITIAL_HI and f["final_lo"] == INITIAL_LO

    for cid in SUCCESS_IDS:
        f, e = facts[cid], attributed[cid]
        assert f["result"] == 1 and f["exception"] == 0 and f["llbit_after"] is True
        source = CHANGED64 if f["kind"] == "changed" else INITIAL64
        assert f["source"] == source
        # Exact pinned ares RCP Dual writes commit only the upper source Word.
        assert f["final_hi"] == upper_word(source)
        assert f["final_lo"] == INITIAL_LO
        assert e["pc"] == CODE_VA and e["instruction"] >> 26 == 0x3C
        assert e["pre_rt"] == source and e["value"] == upper_word(source)
        assert e["llbit_before"] is True
        assert e["bank"] == f["bank"] and e["offset"] == 0

    # Changed source proves the lower 32 bits of the architectural Dual payload did not reach SP storage.
    for cid in (3, 7):
        f = facts[cid]
        final64 = (f["final_hi"] << 32) | f["final_lo"]
        assert f["source"] == CHANGED64
        assert final64 == 0x11223345FFFFFFFF
        assert final64 != f["source"]

    # Same-value successful SCD is a fresh completed sink despite no byte difference.
    for cid in (4, 8):
        f, e = facts[cid], attributed[cid]
        assert f["source"] == INITIAL64
        assert f["final_hi"] == f["initial_hi"] == INITIAL_HI
        assert f["final_lo"] == f["initial_lo"] == INITIAL_LO
        assert e["value"] == INITIAL_HI

    # Equal payload outside decoded SCD execution cannot steal SCD attribution.
    decoy = next(e for e in events if e["case"] == 0)
    assert decoy["pc"] == 0 and decoy["instruction"] == 0
    assert decoy["bank"] == 1 and decoy["offset"] == 0 and decoy["value"] == INITIAL_HI
    assert decoy["value"] == attributed[8]["value"]

    return {
        "events": len(events),
        "successful_scd_sinks": 4,
        "failed_scd_without_sink": 2,
        "faulting_scd_without_sink": 2,
        "successful_scd_word_sinks": 4,
        "successful_scd_second_word_sinks": 0,
        "same_value_successes_missed_by_diff": 2,
        "truncated_dual_payload_successes": 2,
        "sp_lld_freeze_controls": 2,
        "out_of_context_equal_value_decoys": 1,
    }


def forged_rejections(doc: dict) -> list[str]:
    names = []

    def reject(name, mutate):
        forged = copy.deepcopy(doc)
        mutate(forged)
        try:
            verify(forged)
        except (AssertionError, KeyError, StopIteration):
            names.append(name)
            return
        raise AssertionError(f"forged history accepted: {name}")

    reject("drop_same_value_success", lambda d: d["events"].__setitem__(slice(None), [e for e in d["events"] if e["case"] != 4]))
    reject("fabricate_failed_sink", lambda d: d["events"].insert(0, {**d["events"][0], "ordinal": 0, "case": 1}))
    reject("steal_equal_value_decoy", lambda d: next(e for e in d["events"] if e["case"] == 8).__setitem__("case", 0))
    reject("erase_scd_opcode", lambda d: next(e for e in d["events"] if e["case"] == 3).__setitem__("instruction", 0xFC220000))
    reject("erase_reservation_context", lambda d: next(e for e in d["events"] if e["case"] == 7).__setitem__("llbit_before", False))
    reject("pretend_lower_word_reached_sink", lambda d: next(e for e in d["events"] if e["case"] == 3).__setitem__("value", CHANGED64 & 0xFFFFFFFF))
    reject("hide_sp_lld_freeze", lambda d: d["freeze_controls"][0].__setitem__("sysad_frozen", False))
    return names


if __name__ == "__main__":
    import json, sys
    doc = json.load(sys.stdin)
    print(json.dumps({"summary": verify(doc), "forged": forged_rejections(doc)}, sort_keys=True))
