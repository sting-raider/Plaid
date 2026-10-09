#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import random

VA = 0x4000
ENTRIES = {0x11: 0x1000, 0x22: 0x3000, 0x33: 0x5000}


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
        self.asid = 0x11
        self.context_generation = 0
        self.backing = {
            0x1000: Backing(0x34091111, 1),
            0x3000: Backing(0x34092222, 1),
            0x5000: Backing(0x34091111, 1),
        }
        self.resident: Resident | None = None
        self.fill_generation = 0
        self.misses = 0

    def write_asid(self, asid: int) -> None:
        self.context_generation += 1
        self.asid = asid

    def mutate(self, paddr: int, word: int) -> None:
        backing = self.backing[paddr]
        backing.word = word
        backing.generation += 1

    def fetch(self) -> dict:
        if self.asid not in ENTRIES:
            return {
                "ok": False,
                "context_generation": self.context_generation,
                "resident_fill_generation": None if self.resident is None else self.resident.fill_generation,
            }
        paddr = ENTRIES[self.asid]
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
            "hit": hit,
            "current_backing_generation": self.backing[paddr].generation,
        }


def canonical() -> dict:
    machine = Machine()
    first = machine.fetch()
    assert first["word"] == 0x34091111 and not first["hit"]

    machine.write_asid(0x22)
    machine.mutate(0x1000, 0x34094444)
    before_same = machine.context_generation
    machine.write_asid(0x22)
    assert machine.context_generation == before_same + 1

    machine.write_asid(0x44)
    fault = machine.fetch()
    assert not fault["ok"]

    machine.write_asid(0x11)
    stale = machine.fetch()
    assert stale["hit"] and stale["word"] == 0x34091111
    assert stale["source_backing_generation"] == 1
    assert stale["current_backing_generation"] == 2

    machine.write_asid(0x33)
    equal = machine.fetch()
    assert not equal["hit"] and equal["word"] == 0x34091111 and equal["paddr"] == 0x5000

    machine.write_asid(0x11)
    fresh = machine.fetch()
    assert not fresh["hit"] and fresh["word"] == 0x34094444
    assert fresh["source_backing_generation"] == 2

    forged = [
        ("stale_as_current", stale | {"source_backing_generation": 2}, stale),
        ("equal_payload_reuse_old_fill", equal | {"fill_generation": first["fill_generation"]}, equal),
        ("fault_as_success", fault | {"ok": True, "paddr": 0x1000}, fault),
        ("post_conflict_reuse_stale", fresh | {"source_backing_generation": 1}, fresh),
    ]
    rejected = sum(claim != expected for _, claim, expected in forged)
    assert rejected == len(forged)

    return {
        "first": first,
        "stale": stale,
        "equal_payload_remap": equal,
        "fault": fault,
        "fresh_after_conflict": fresh,
        "same_value_context_write_advanced_generation": True,
        "forgeries_rejected": rejected,
    }


def fuzz(seed: int = 0xA51D, steps: int = 50_000) -> dict:
    rng = random.Random(seed)
    machine = Machine()
    mismatches = 0
    fetches = 0
    same_asid = 0
    equal_payload_diff_pa = 0
    faults = 0
    stale_hits = 0
    last_success = None

    for _ in range(steps):
        op = rng.randrange(100)
        if op < 35:
            new = rng.choice([0x11, 0x22, 0x33, 0x44])
            if new == machine.asid:
                same_asid += 1
            machine.write_asid(new)
        elif op < 60:
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
                mismatches += 1
                if out["hit"]:
                    stale_hits += 1
            if last_success and last_success["word"] == out["word"] and last_success["paddr"] != out["paddr"]:
                equal_payload_diff_pa += 1
            last_success = out

    assert mismatches > 0 and stale_hits > 0 and equal_payload_diff_pa > 0 and same_asid > 0
    return {
        "seed": seed,
        "steps": steps,
        "fetches": fetches,
        "faults": faults,
        "same_value_asid_writes": same_asid,
        "naive_current_backing_wrong_origins": mismatches,
        "stale_hit_wrong_origins": stale_hits,
        "equal_payload_different_pa_transitions": equal_payload_diff_pa,
    }


report = {"canonical": canonical(), "fuzz": fuzz()}
raw = json.dumps(report, sort_keys=True, separators=(",", ":"))
digest = hashlib.sha256(raw.encode()).hexdigest()
print(json.dumps(report, sort_keys=True, indent=2))
print("MODEL_SHA256=" + digest)
print("PASS: ASID context, installed mapping and resident generation must compose; current backing/value equality is unsound provenance")
