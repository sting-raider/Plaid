#!/usr/bin/env python3
"""Adversarial reducer for TLBP/TLBR mapping-entry vs translation-context effects."""
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


def digest(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def translate(entries, vpn, active_asid):
    for e in entries:
        if e["vpn"] == vpn and (e["global"] or e["asid"] == active_asid):
            return e["pfn"]
    return None


cp0_changes = 0
false_entry_generations = 0
entry_mutations = 0
tlbp_translation_flips = 0
tlbr_translation_flips = 0
tlbr_asid_changes = 0
same_value_ops = 0
probe_hits = 0
probe_misses = 0
out_of_range_reads = 0
records = []

for case in range(CASES):
    mappings = [entry(i) for i in range(32)]
    if case % 3 == 0:
        mappings[17] = dict(mappings[9])  # equality does not identify a unique slot
    before_map = digest(mappings)

    staged = dict(entry(rng.randrange(32)))
    index = rng.randrange(64)
    probe_failure = bool(rng.randrange(2))
    op = "TLBP" if rng.randrange(2) == 0 else "TLBR"
    target_vpn = mappings[9]["vpn"]
    active_asid_before = staged["asid"]
    before_translation = translate(mappings, target_vpn, active_asid_before)
    before_cp0 = (json.dumps(staged, sort_keys=True), index, probe_failure)

    if op == "TLBP":
        if rng.randrange(2) == 0:
            target = rng.randrange(32)
            # TLBP queries staged EntryHi; choosing a hit changes Index only.
            staged = dict(mappings[target])
            active_asid_before = staged["asid"]
            before_translation = translate(mappings, target_vpn, active_asid_before)
            matches = [i for i, e in enumerate(mappings) if e == staged]
            index = matches[0]
            probe_failure = False
            probe_hits += 1
        else:
            staged = {"vpn": 0x7FFFF, "asid": 0xEE, "pfn": 0, "global": False}
            active_asid_before = staged["asid"]
            before_translation = translate(mappings, target_vpn, active_asid_before)
            index = 0  # exact ares miss convention; field is architecturally undefined
            probe_failure = True
            probe_misses += 1
    else:
        if index < 32:
            staged = dict(mappings[index])
        else:
            out_of_range_reads += 1

    active_asid_after = staged["asid"]
    after_translation = translate(mappings, target_vpn, active_asid_after)
    after_cp0 = (json.dumps(staged, sort_keys=True), index, probe_failure)
    cp0_changed = before_cp0 != after_cp0
    cp0_changes += int(cp0_changed)
    same_value_ops += int(not cp0_changed)

    after_map = digest(mappings)
    if after_map != before_map:
        entry_mutations += 1

    # Treating arbitrary COP0 deltas as TLB-entry replacement is wrong for both
    # operations, even when the delta matters to translation context.
    false_entry_generations += int(cp0_changed)

    if op == "TLBP":
        tlbp_translation_flips += int(before_translation != after_translation)
    else:
        asid_changed = active_asid_before != active_asid_after
        tlbr_asid_changes += int(asid_changed)
        tlbr_translation_flips += int(before_translation != after_translation)

    if case < 32:
        records.append((case, op, cp0_changed, active_asid_before, active_asid_after,
                        before_translation, after_translation, index, probe_failure, before_map[:12]))

assert entry_mutations == 0
assert tlbp_translation_flips == 0
assert tlbr_asid_changes > 0
assert tlbr_translation_flips > 0
assert false_entry_generations == cp0_changes
assert same_value_ops > 0
assert probe_hits > 0 and probe_misses > 0 and out_of_range_reads > 0

summary = {
    "cases": CASES,
    "mapping_entry_mutations": entry_mutations,
    "cp0_changes": cp0_changes,
    "false_entry_generations_if_any_cp0_delta_is_entry_write": false_entry_generations,
    "same_value_ops": same_value_ops,
    "probe_hits": probe_hits,
    "probe_misses": probe_misses,
    "out_of_range_tlbr": out_of_range_reads,
    "tlbp_translation_flips": tlbp_translation_flips,
    "tlbr_active_asid_changes": tlbr_asid_changes,
    "tlbr_sampled_translation_flips": tlbr_translation_flips,
    "sample_sha256": hashlib.sha256(repr(records).encode()).hexdigest(),
}
summary["sha256"] = hashlib.sha256(json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
print(json.dumps(summary, sort_keys=True))
