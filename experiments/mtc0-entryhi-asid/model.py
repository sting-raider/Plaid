#!/usr/bin/env python3
import hashlib
import json
import random

ENTRIES = [
    {"asid": 0x11, "pa": 0x1000, "value": 0x34091111, "global": False},
    {"asid": 0x22, "pa": 0x3000, "value": 0x34092222, "global": False},
    {"asid": 0x33, "pa": 0x5000, "value": 0x34091111, "global": False},
]
GLOBAL = {"asid": 0x77, "pa": 0x7000, "value": 0x340A7777, "global": True}


def resolve(asid, global_only=False):
    if global_only:
        return GLOBAL
    for entry in ENTRIES:
        if entry["global"] or entry["asid"] == asid:
            return entry
    return None


def run(seed=0x504C414944, histories=20000):
    rng = random.Random(seed)
    stale_wrong = 0
    stale_missing = 0
    same_value_writes = 0
    same_value_invisible = 0
    equal_payload_switches = 0
    global_switch_checks = 0
    generated_fetches = 0
    for _ in range(histories):
        asid = rng.choice([0x11, 0x22, 0x33, 0x44])
        cached = None
        for __ in range(rng.randint(4, 18)):
            if rng.random() < 0.48:
                new_asid = rng.choice([0x11, 0x22, 0x33, 0x44])
                if new_asid == asid:
                    same_value_writes += 1
                    same_value_invisible += 1
                old = resolve(asid)
                new = resolve(new_asid)
                if old and new and old["value"] == new["value"] and old["pa"] != new["pa"]:
                    equal_payload_switches += 1
                asid = new_asid
            else:
                generated_fetches += 1
                truth = resolve(asid)
                # Deliberately unsound policy: installed TLB entries did not mutate,
                # so reuse the last resolution for this virtual address.
                if cached is None:
                    cached = truth
                else:
                    if truth is None and cached is not None:
                        stale_wrong += 1
                    elif truth is not None and cached is None:
                        stale_missing += 1
                    elif truth is not None and cached is not None and truth["pa"] != cached["pa"]:
                        stale_wrong += 1
                assert resolve(asid, global_only=True)["pa"] == GLOBAL["pa"]
                global_switch_checks += 1
    report = {
        "seed": seed,
        "histories": histories,
        "generated_fetches": generated_fetches,
        "naive_entry_only_wrong_backing": stale_wrong,
        "naive_entry_only_missing": stale_missing,
        "same_value_entryhi_writes": same_value_writes,
        "same_value_writes_invisible_to_state_diff": same_value_invisible,
        "equal_payload_different_backing_context_switches": equal_payload_switches,
        "global_asid_independence_checks": global_switch_checks,
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["sha256"] = hashlib.sha256(canonical).hexdigest()
    return report


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
