#!/usr/bin/env python3
"""Deterministic adversarial model for TLBWR generation inference."""
import hashlib
import json
import random

rng = random.Random(0x544C425752)
trials = 10000
same_value = 0
diff_invisible = 0
index_wrong = 0
payload_ambiguous = 0

for _ in range(trials):
    wired = rng.randrange(0, 32)
    selected = rng.randrange(wired, 32)
    cp0_index = rng.randrange(0, 32)
    is_same = rng.randrange(5) == 0
    duplicate = rng.randrange(4) == 0

    # Actual mutation boundary has the selected slot even if old==new.
    actual = {"selected": selected, "same": is_same}
    # Snapshot-only inference sees a slot only when payload/state changes.
    snapshot_candidates = [] if is_same else [selected]
    # Index-register inference is independent of TLBWR's local random slot.
    inferred_index = cp0_index
    # Payload matching is ambiguous whenever an equal decoy exists.
    payload_candidates = [selected] + ([rng.randrange(0, 32)] if duplicate else [])

    if is_same:
        same_value += 1
        if not snapshot_candidates:
            diff_invisible += 1
    if inferred_index != actual["selected"]:
        index_wrong += 1
    if len(set(payload_candidates)) > 1:
        payload_ambiguous += 1

summary = {
    "trials": trials,
    "same_value": same_value,
    "snapshot_diff_invisible": diff_invisible,
    "cp0_index_wrong": index_wrong,
    "payload_ambiguous": payload_ambiguous,
}
blob = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
summary["sha256"] = hashlib.sha256(blob).hexdigest()

assert diff_invisible == same_value
assert index_wrong > trials * 0.9
assert payload_ambiguous > trials * 0.15
print(json.dumps(summary, sort_keys=True))
