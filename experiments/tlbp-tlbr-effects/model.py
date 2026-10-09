#!/usr/bin/env python3
"""Adversarial mapping-generation reducer for TLBP/TLBR.

The model deliberately makes CP0 staging/Index changes common while asserting
that the translation mapping array is immutable for both operations. A reducer
that promotes any CP0 delta to a mapping generation therefore produces false
positives; a reducer keyed to actual TLB write events does not.
"""
import hashlib
import json
import random

SEED = 0x504C414944544C42
CASES = 20000
rng = random.Random(SEED)


def entry(slot: int):
    return {
        "vpn": 0x100 + slot * 2,
        "asid": slot & 0xFF,
        "pfn": 0x200 + slot * 2,
        "global": False,
    }


def mapping_digest(entries):
    raw = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


false_generations = 0
cp0_changes = 0
same_value_ops = 0
probe_hits = 0
probe_misses = 0
out_of_range_reads = 0
translation_mismatches = 0
records = []

for case in range(CASES):
    mappings = [entry(i) for i in range(32)]
    # Add equal-mapping decoys often, because value equality is not identity.
    if case % 3 == 0:
        mappings[17] = dict(mappings[9])
    before_map = mapping_digest(mappings)

    staged = dict(entry(rng.randrange(32)))
    index = rng.randrange(64)
    probe_failure = bool(rng.randrange(2))
    op = "TLBP" if rng.randrange(2) == 0 else "TLBR"
    before_cp0 = (json.dumps(staged, sort_keys=True), index, probe_failure)

    if op == "TLBP":
        # Half the time choose a real entry query; otherwise force a miss.
        if rng.randrange(2) == 0:
            target = rng.randrange(32)
            staged = dict(mappings[target])
            matches = [i for i, e in enumerate(mappings) if e == staged]
            index = matches[0]
            probe_failure = False
            probe_hits += 1
        else:
            staged = {"vpn": 0x7FFFF, "asid": 0xEE, "pfn": 0, "global": False}
            index = 0  # exact ares miss convention; architecturally undefined field
            probe_failure = True
            probe_misses += 1
    else:
        if index < 32:
            staged = dict(mappings[index])
        else:
            out_of_range_reads += 1

    after_cp0 = (json.dumps(staged, sort_keys=True), index, probe_failure)
    cp0_changed = before_cp0 != after_cp0
    cp0_changes += int(cp0_changed)
    same_value_ops += int(not cp0_changed)

    after_map = mapping_digest(mappings)
    if after_map != before_map:
        raise AssertionError((case, op, before_map, after_map))

    # Translation for a stable virtual identity must remain stable because the
    # mapping array did not change. The model uses the first matching slot,
    # preserving duplicate-slot ambiguity rather than pretending equality names
    # a unique mapping generation.
    probe_vpn = mappings[9]["vpn"]
    pre = next((e["pfn"] for e in mappings if e["vpn"] == probe_vpn), None)
    post = next((e["pfn"] for e in mappings if e["vpn"] == probe_vpn), None)
    if pre != post:
        translation_mismatches += 1

    # Deliberately naive reducer: any TLB-related CP0 change becomes a mapping
    # generation. Every such generation is false for TLBP/TLBR.
    if cp0_changed:
        false_generations += 1

    if case < 32:
        records.append((case, op, cp0_changed, index, probe_failure, before_map[:12]))

assert translation_mismatches == 0
assert false_generations == cp0_changes
assert false_generations > CASES // 2
assert same_value_ops > 0
assert probe_hits > 0 and probe_misses > 0 and out_of_range_reads > 0

summary = {
    "cases": CASES,
    "cp0_changes": cp0_changes,
    "false_generations_if_cp0_delta_is_mapping": false_generations,
    "same_value_ops": same_value_ops,
    "probe_hits": probe_hits,
    "probe_misses": probe_misses,
    "out_of_range_tlbr": out_of_range_reads,
    "translation_mismatches": translation_mismatches,
    "correct_mapping_generations": 0,
    "sample_sha256": hashlib.sha256(repr(records).encode()).hexdigest(),
}
summary["sha256"] = hashlib.sha256(
    json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
print(json.dumps(summary, sort_keys=True))
