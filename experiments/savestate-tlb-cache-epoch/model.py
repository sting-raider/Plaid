#!/usr/bin/env python3
"""Adversarial restore-epoch model for TLB/context/I-cache provenance composition."""
from dataclasses import dataclass, asdict
import hashlib, json

@dataclass(frozen=True)
class Component:
    value: str
    generation: int
    epoch: int
    origin: str

@dataclass(frozen=True)
class Machine:
    mapping: Component
    context: Component
    residency: Component


def restore(snapshot_id: str, snapshot: Machine, restore_epoch: int) -> Machine:
    def r(c: Component, kind: str) -> Component:
        return Component(c.value, c.generation, restore_epoch,
                         f"restore:{snapshot_id}:{kind}:epoch{restore_epoch}")
    return Machine(r(snapshot.mapping, "mapping"),
                   r(snapshot.context, "context"),
                   r(snapshot.residency, "residency"))

# S0 is a coherent executable state captured after one operation/fill on each axis.
s0 = Machine(
    Component("slot0:va4000/asid11->pa1000", 1, 0, "tlbwi:1"),
    Component("entryhi:va4000/asid11", 1, 0, "mtc0-entryhi:1"),
    Component("line128:tag-pa1000:word=34091111", 1, 0, "icache-fill:1"),
)

# Distinct S1 state proves restore really rolls all three axes back.
s1 = Machine(
    Component("slot0:va4000/asid22->pa3000", 2, 0, "tlbwi:2"),
    Component("entryhi:va4000/asid22", 2, 0, "mtc0-entryhi:2"),
    Component("line128:tag-pa3000:word=34092222", 2, 0, "icache-fill:2"),
)
r1 = restore("S0", s0, 1)
assert (r1.mapping.value, r1.context.value, r1.residency.value) == (
    s0.mapping.value, s0.context.value, s0.residency.value)
assert r1.mapping.epoch == r1.context.epoch == r1.residency.epoch == 1

# Equal-state adversary: new operations/fill recreate exactly the S0 values.
# If an external sidecar is not rewound on load, these are its latest generations.
same_live = Machine(
    Component(s0.mapping.value, 3, 1, "tlbwi:3-same-value"),
    Component(s0.context.value, 3, 1, "mtc0-entryhi:3-same-value"),
    Component(s0.residency.value, 3, 1, "icache-fill:3-equal-tuple"),
)
r2 = restore("S0", s0, 2)
assert (r2.mapping.value, r2.context.value, r2.residency.value) == (
    same_live.mapping.value, same_live.context.value, same_live.residency.value)

# Naive latest/current-value join is attractive and wrong after restore.
naive = {
    "mapping_generation": same_live.mapping.generation,
    "context_generation": same_live.context.generation,
    "residency_generation": same_live.residency.generation,
}
correct = {
    "mapping": r2.mapping.origin,
    "context": r2.context.origin,
    "residency": r2.residency.origin,
}
assert set(naive.values()) == {3}
assert all(v.startswith("restore:S0:") for v in correct.values())

# A minimal verifier must bind all restored components to the same capture+epoch.
def accepts_restore_tuple(mapping_origin: str, context_origin: str, residency_origin: str) -> bool:
    parts = [mapping_origin.split(":"), context_origin.split(":"), residency_origin.split(":")]
    if any(len(p) != 4 or p[0] != "restore" for p in parts):
        return False
    return len({p[1] for p in parts}) == 1 and len({p[3] for p in parts}) == 1

assert accepts_restore_tuple(r2.mapping.origin, r2.context.origin, r2.residency.origin)
for forged in [
    (same_live.mapping.origin, r2.context.origin, r2.residency.origin),
    (r2.mapping.origin, same_live.context.origin, r2.residency.origin),
    (r2.mapping.origin, r2.context.origin, same_live.residency.origin),
    ("restore:S1:mapping:epoch2", r2.context.origin, r2.residency.origin),
    ("restore:S0:mapping:epoch1", r2.context.origin, r2.residency.origin),
    ("tlbwi:3-same-value", "mtc0-entryhi:3-same-value", "icache-fill:3-equal-tuple"),
]:
    assert not accepts_restore_tuple(*forged)

report = {
    "snapshot": asdict(s0),
    "distinct_live_before_restore": asdict(s1),
    "after_distinct_restore": asdict(r1),
    "equal_live_before_restore": asdict(same_live),
    "after_equal_restore": asdict(r2),
    "naive_latest_join": naive,
    "correct_restore_roots": correct,
    "forged_rejected": 6,
}
blob = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
report["sha256"] = hashlib.sha256(blob).hexdigest()
print(json.dumps(report, sort_keys=True, indent=2))
