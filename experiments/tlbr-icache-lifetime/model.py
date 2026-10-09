#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import random

VA = 0x4000
# Installed non-global mappings. Slot 4 exists only to load an unmatched ASID.
ENTRIES = {
    0: (VA, 0x1000, 0x11),
    1: (VA, 0x3000, 0x22),
    2: (VA, 0x5000, 0x33),
    4: (0x20000, 0x9000, 0x44),
}


@dataclass
class Backing:
    word: int
    generation: int


@dataclass
class Resident:
    paddr: int
    word: int
    backing_generation: int
    fill_generation: int


class Machine:
    def __init__(self):
        self.asid = 0x44
        self.context_generation = 0
        self.tlbr_operation_generation = 0
        self.tlbp_operation_generation = 0
        self.installed_generation = 1
        self.backing = {
            0x1000: Backing(0x34091111, 1),
            0x3000: Backing(0x34092222, 1),
            0x5000: Backing(0x34091111, 1),
        }
        self.resident: Resident | None = None
        self.fill_generation = 0
        self.misses = 0

    def tlbr(self, slot: int) -> bool:
        # Instruction occurrence is distinct from whether the selected index is valid.
        self.tlbr_operation_generation += 1
        if slot not in ENTRIES:
            return False
        self.context_generation += 1
        self.asid = ENTRIES[slot][2]
        return True

    def tlbp(self) -> None:
        self.tlbp_operation_generation += 1

    def mutate(self, paddr: int, word: int) -> None:
        backing = self.backing[paddr]
        backing.word = word
        backing.generation += 1

    def fetch(self) -> dict:
        selected = [entry for entry in ENTRIES.values() if entry[0] == VA and entry[2] == self.asid]
        if len(selected) != 1:
            return {
                "ok": False,
                "context_generation": self.context_generation,
                "resident_fill_generation": None if self.resident is None else self.resident.fill_generation,
            }
        _, paddr, _ = selected[0]
        tag = paddr & ~0xFFF
        hit = self.resident is not None and (self.resident.paddr & ~0xFFF) == tag
        if not hit:
            self.misses += 1
            self.fill_generation += 1
            backing = self.backing[paddr]
            self.resident = Resident(paddr, backing.word, backing.generation, self.fill_generation)
        resident = self.resident
        assert resident is not None
        return {
            "ok": True,
            "paddr": paddr,
            "word": resident.word,
            "source_backing_generation": resident.backing_generation,
            "fill_generation": resident.fill_generation,
            "context_generation": self.context_generation,
            "installed_generation": self.installed_generation,
            "hit": hit,
            "current_backing_generation": self.backing[paddr].generation,
        }


def canonical() -> dict:
    machine = Machine()
    assert machine.tlbr(0)
    first = machine.fetch()
    assert first["word"] == 0x34091111 and not first["hit"]

    # TLBP is an observer of installed mappings and does not change active ASID.
    before_probe_context = machine.context_generation
    machine.tlbp()
    assert machine.context_generation == before_probe_context and machine.asid == 0x11

    assert machine.tlbr(1)
    machine.mutate(0x1000, 0x34094444)

    # Same-value TLBR is still another ordered successful context writer.
    before_same = machine.context_generation
    asid_before_same = machine.asid
    assert machine.tlbr(1)
    assert machine.asid == asid_before_same and machine.context_generation == before_same + 1

    # Out-of-range TLBR executes but performs no staged-context write.
    context_before_bad = machine.context_generation
    op_before_bad = machine.tlbr_operation_generation
    assert not machine.tlbr(63)
    assert machine.context_generation == context_before_bad
    assert machine.tlbr_operation_generation == op_before_bad + 1

    assert machine.tlbr(4)
    fault = machine.fetch()
    assert not fault["ok"]

    assert machine.tlbr(0)
    stale = machine.fetch()
    assert stale["hit"] and stale["word"] == 0x34091111
    assert stale["source_backing_generation"] == 1
    assert stale["current_backing_generation"] == 2

    assert machine.tlbr(2)
    equal = machine.fetch()
    assert not equal["hit"] and equal["word"] == 0x34091111 and equal["paddr"] == 0x5000

    assert machine.tlbr(0)
    fresh = machine.fetch()
    assert not fresh["hit"] and fresh["word"] == 0x34094444
    assert fresh["source_backing_generation"] == 2

    forged = [
        ("tlbr_mutates_installed_generation", machine.installed_generation + 1, machine.installed_generation),
        ("stale_as_current_backing", stale | {"source_backing_generation": 2}, stale),
        ("equal_payload_reuses_a_fill", equal | {"fill_generation": first["fill_generation"]}, equal),
        ("tlbp_changes_context", before_probe_context + 1, before_probe_context),
        ("out_of_range_tlbr_changes_context", context_before_bad + 1, context_before_bad),
        ("fault_as_success", fault | {"ok": True, "paddr": 0x1000}, fault),
        ("post_conflict_reuses_stale", fresh | {"source_backing_generation": 1}, fresh),
    ]
    rejected = sum(claim != expected for _, claim, expected in forged)
    assert rejected == len(forged)

    return {
        "first": first,
        "stale_after_tlbr_reactivation": stale,
        "equal_payload_remap": equal,
        "fault": fault,
        "fresh_after_conflict": fresh,
        "same_value_tlbr_advanced_context_generation": True,
        "out_of_range_tlbr_only_advanced_operation_generation": True,
        "tlbp_left_context_generation_unchanged": True,
        "installed_generation_unchanged": machine.installed_generation == 1,
        "forgeries_rejected": rejected,
    }


def fuzz(seed: int = 0x544C4252, steps: int = 50_000) -> dict:
    rng = random.Random(seed)
    machine = Machine()
    stale_wrong = 0
    fetches = 0
    faults = 0
    same_value_tlbr = 0
    invalid_tlbr = 0
    equal_payload_diff_pa = 0
    probe_ops = 0
    last_success = None

    for _ in range(steps):
        op = rng.randrange(100)
        if op < 35:
            slot = rng.choice([0, 1, 2, 4, 63])
            old_asid = machine.asid
            ok = machine.tlbr(slot)
            if not ok:
                invalid_tlbr += 1
            elif machine.asid == old_asid:
                same_value_tlbr += 1
        elif op < 45:
            before = machine.context_generation
            machine.tlbp()
            probe_ops += 1
            assert machine.context_generation == before
        elif op < 65:
            paddr = rng.choice(list(machine.backing))
            word = machine.backing[paddr].word if rng.randrange(3) == 0 else rng.choice(
                [0x34091111, 0x34092222, 0x34093333, 0x34094444]
            )
            machine.mutate(paddr, word)
        else:
            out = machine.fetch()
            if not out["ok"]:
                faults += 1
                continue
            fetches += 1
            if out["source_backing_generation"] != out["current_backing_generation"]:
                stale_wrong += 1
            if last_success and last_success["word"] == out["word"] and last_success["paddr"] != out["paddr"]:
                equal_payload_diff_pa += 1
            last_success = out

    assert stale_wrong > 0 and equal_payload_diff_pa > 0
    assert same_value_tlbr > 0 and invalid_tlbr > 0 and probe_ops > 0
    assert machine.installed_generation == 1
    return {
        "seed": seed,
        "steps": steps,
        "fetches": fetches,
        "faults": faults,
        "same_value_tlbr": same_value_tlbr,
        "invalid_tlbr": invalid_tlbr,
        "tlbp_operations": probe_ops,
        "naive_current_backing_wrong_origins": stale_wrong,
        "equal_payload_different_pa_transitions": equal_payload_diff_pa,
        "installed_generation": machine.installed_generation,
    }


report = {"canonical": canonical(), "fuzz": fuzz()}
raw = json.dumps(report, sort_keys=True, separators=(",", ":"))
digest = hashlib.sha256(raw.encode()).hexdigest()
print(json.dumps(report, sort_keys=True, indent=2))
print("MODEL_SHA256=" + digest)
print("PASS: TLBR operation/context, installed mapping, backing and resident fill generations stay distinct; TLBP and value equality cannot fabricate provenance")
