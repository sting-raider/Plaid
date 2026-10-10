#!/usr/bin/env python3
"""Adversarial lifetime reducer for RSP reset/NMI transitions."""
from dataclasses import dataclass
import hashlib
import json

@dataclass(frozen=True)
class State:
    epoch: int
    payload: str
    resident_install: int | None
    dma_live: bool


def install(s: State, token: int, payload: str) -> State:
    return State(s.epoch, payload, token, False)


def start_dma(s: State) -> State:
    return State(s.epoch, s.payload, s.resident_install, True)


def nmi(s: State) -> State:
    # CPU NMI has no RSP storage/state transition in pinned ares.
    return s


def ares_soft_reset(s: State) -> State:
    # Explicit RSP::power(true) transition. The new zero state is not descended
    # from any prior installation even when the payload was already zero.
    return State(s.epoch + 1, "zero", None, False)


def cold_power(s: State) -> State:
    return State(s.epoch + 1, "zero", None, False)


def preserve_every_reset_like(before: State, kind: str) -> State:
    return before


def retire_every_reset_like(before: State, kind: str) -> State:
    return State(before.epoch + 1, "zero", None, False)


def expected(before: State, kind: str) -> State:
    return {"nmi": nmi, "ares_soft_reset": ares_soft_reset, "cold_power": cold_power}[kind](before)


cases = []
base = install(State(4, "A", None, False), 17, "A")
base = start_dma(base)
for kind in ("nmi", "ares_soft_reset", "cold_power"):
    want = expected(base, kind)
    cases.append({
        "kind": kind,
        "before": base.__dict__,
        "expected": want.__dict__,
        "preserve_policy_ok": preserve_every_reset_like(base, kind) == want,
        "retire_policy_ok": retire_every_reset_like(base, kind) == want,
    })

# Same-value adversary: equality cannot prove that no reset happened.
zero_live = State(9, "zero", 23, True)
zero_after = ares_soft_reset(zero_live)
assert zero_after.payload == zero_live.payload
assert zero_after.epoch != zero_live.epoch
assert zero_after.resident_install is None and not zero_after.dma_live

# Same address/hash across NMI must preserve causal identity, not fabricate a new one.
nmi_after = nmi(base)
assert nmi_after == base

# Both tempting blanket policies are disproved by the exact-pinned-ares contract.
assert not next(c for c in cases if c["kind"] == "nmi")["retire_policy_ok"]
assert not next(c for c in cases if c["kind"] == "ares_soft_reset")["preserve_policy_ok"]

report = {
    "cases": cases,
    "equal_payload_reset": {"before": zero_live.__dict__, "after": zero_after.__dict__},
    "portable_soft_reset": "UNKNOWN_WHEN_REFERENCE_SEMANTICS_DISAGREE",
    "obligation": (
        "Treat NMI, soft reset and cold power as separate typed transitions. "
        "Retire/preserve RSP executable provenance only from proven storage/state effects; "
        "never from payload equality or a generic reset-like label."
    ),
}
blob = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
print(json.dumps(report, sort_keys=True, indent=2))
print("MODEL_SHA256=" + hashlib.sha256(blob).hexdigest())
print("MODEL_PASS")
