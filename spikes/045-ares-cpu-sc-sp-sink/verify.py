#!/usr/bin/env python3
"""Fail-closed verifier for decoded SC -> completed CPU-visible SP Word sinks."""
from __future__ import annotations
import copy

CODE_VA = 0xFFFFFFFFA0006000
INITIAL = 0x11223344
CHANGED = INITIAL ^ 0x00FF
SUCCESS_IDS = {3, 4, 7, 8}
FAIL_IDS = {1, 5}
FAULT_IDS = {2, 6}


def verify(doc: dict) -> dict:
    facts = {f["id"]: f for f in doc["facts"]}
    assert set(facts) == set(range(1, 9))
    events = doc["events"]
    assert [e["ordinal"] for e in events] == list(range(1, len(events) + 1))
    assert [e["case"] for e in events] == [3, 4, 7, 8, 0], events

    attributed = {e["case"]: e for e in events if e["case"]}
    assert set(attributed) == SUCCESS_IDS
    assert not any(e["case"] in FAIL_IDS | FAULT_IDS for e in events)

    for cid in FAIL_IDS:
        f = facts[cid]
        assert f["kind"] == "fail" and f["result"] == 0 and f["exception"] == 0
        assert f["final"] == INITIAL

    for cid in FAULT_IDS:
        f = facts[cid]
        assert f["kind"] == "fault" and f["result"] == 0 and f["exception"] == 5
        expected_bad = (0xFFFFFFFFA4001000 if f["bank"] else 0xFFFFFFFFA4000000) + 1
        assert f["badva"] == expected_bad, (f, expected_bad)
        assert f["final"] == INITIAL

    for cid in SUCCESS_IDS:
        f, e = facts[cid], attributed[cid]
        assert f["result"] == 1 and f["exception"] == 0
        expected = CHANGED if f["kind"] == "changed" else INITIAL
        assert f["source"] == expected and f["final"] == expected
        assert e["pc"] == CODE_VA and e["instruction"] >> 26 == 0x38
        assert e["pre_rt"] == expected and e["value"] == expected
        assert e["llbit_before"] is True
        assert e["bank"] == f["bank"] and e["offset"] == 0

    # Successful same-value SC is still a fresh completed sink generation.
    for cid in (4, 8):
        assert facts[cid]["initial"] == facts[cid]["final"] == INITIAL
        assert attributed[cid]["value"] == INITIAL

    # Equal payload outside decoded SC execution cannot steal SC attribution.
    decoy = next(e for e in events if e["case"] == 0)
    assert decoy["pc"] == 0 and decoy["instruction"] == 0
    assert decoy["bank"] == 1 and decoy["offset"] == 0 and decoy["value"] == INITIAL
    assert decoy["value"] == attributed[8]["value"]

    return {
        "events": len(events),
        "successful_sc_sinks": 4,
        "failed_sc_without_sink": 2,
        "faulting_sc_without_sink": 2,
        "same_value_successes_missed_by_diff": 2,
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
    reject("erase_sc_opcode", lambda d: next(e for e in d["events"] if e["case"] == 3).__setitem__("instruction", 0xAC220000))
    reject("erase_reservation_context", lambda d: next(e for e in d["events"] if e["case"] == 7).__setitem__("llbit_before", False))
    return names


if __name__ == "__main__":
    import json, sys
    doc = json.load(sys.stdin)
    print(json.dumps({"summary": verify(doc), "forged": forged_rejections(doc)}, sort_keys=True))
