#!/usr/bin/env python3
"""Independent adversarial model for TLBWI generation-vs-snapshot inference."""
import hashlib
import json
import random

SEED = 0x544C425749
CASES = 20000
rng = random.Random(SEED)

legal = 0
out_of_range = 0
same_value = 0
snapshot_false_negative = 0
payload_ambiguous = 0
wrong_slot_if_payload_first = 0

for _ in range(CASES):
    entries = [rng.randrange(1 << 24) for _ in range(32)]
    index = rng.randrange(64)
    staged = rng.randrange(1 << 24)

    # Force useful adversaries often enough to make the counterexamples stable.
    if index < 32 and rng.randrange(4) == 0:
        staged = entries[index]
    if rng.randrange(3) == 0:
        decoy = rng.randrange(32)
        entries[decoy] = staged

    before = list(entries)
    if index >= 32:
        out_of_range += 1
        actual_generation = False
    else:
        legal += 1
        actual_generation = True
        if entries[index] == staged:
            same_value += 1
        entries[index] = staged

    changed = [i for i, (a, b) in enumerate(zip(before, entries)) if a != b]
    snapshot_generation = bool(changed)
    if actual_generation and not snapshot_generation:
        snapshot_false_negative += 1

    matching = [i for i, value in enumerate(entries) if value == staged]
    if actual_generation and len(matching) > 1:
        payload_ambiguous += 1
        if matching[0] != index:
            wrong_slot_if_payload_first += 1

    if index >= 32:
        assert entries == before
        assert not actual_generation
    else:
        assert actual_generation
        assert entries[index] == staged

# Fixed forgeries: the verifier rule is legal Index + actual TLBWI write boundary.
def accepts(index, boundary_slot):
    return 0 <= index < 32 and boundary_slot == index

forged = [
    (5, None),     # missing same-value boundary
    (5, 7),        # equal-payload decoy slot stolen
    (63, 31),      # fabricated generation for OOB Index
    (31, 30),      # wrong legal slot
]
forged_rejected = sum(not accepts(i, b) for i, b in forged)
assert forged_rejected == len(forged)
assert snapshot_false_negative == same_value

report = {
    "cases": CASES,
    "seed": SEED,
    "legal_writes": legal,
    "out_of_range": out_of_range,
    "same_value_writes": same_value,
    "snapshot_false_negatives": snapshot_false_negative,
    "payload_ambiguous": payload_ambiguous,
    "payload_first_wrong_slot": wrong_slot_if_payload_first,
    "forgeries_rejected": forged_rejected,
}
canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
report["sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
print(json.dumps(report, sort_keys=True))
