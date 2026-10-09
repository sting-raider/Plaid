#!/usr/bin/env python3
"""Adversarial model for simultaneous VR4300 maskable-interrupt/NMI ordering."""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path

START = 0xFFFFFFFFA0000000
NMI_ROOT = 0xFFFFFFFFBFC00000

def irq_root(bev: int) -> int:
    return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000) + 0x180

@dataclass
class State:
    pc: int = START
    bev: int = 0
    ie: int = 1
    exl: int = 0
    erl: int = 0
    ip: int = 0
    im: int = 0
    nmi: int = 0
    epc: int = 0x123456789ABCDEF0
    errorepc: int = 0x5555666677778888
    fetches: int = 0


def eligible_irq(s: State) -> bool:
    return bool(s.ip & s.im) and bool(s.ie) and not s.exl and not s.erl


def boundary(s: State) -> str:
    if eligible_irq(s):
        s.epc = s.pc
        s.exl = 1
        s.pc = irq_root(s.bev)
        return "irq"
    if s.nmi:
        s.bev = 1
        s.erl = 1
        s.errorepc = s.pc
        s.pc = NMI_ROOT
        return "nmi"
    s.fetches += 1
    s.pc += 4
    return "fetch"


def run_case(name: str, **kw):
    s = State(**kw)
    first = boundary(s)
    first_state = asdict(s)
    second = boundary(s)
    return {"name": name, "first": first, "second": second, "first_state": first_state, "final": asdict(s)}


def main() -> int:
    collision = run_case("collision", bev=0, ie=1, exl=0, erl=0, ip=4, im=4, nmi=1)
    assert collision["first"] == "irq" and collision["second"] == "nmi"
    assert collision["first_state"]["pc"] == irq_root(0)
    assert collision["first_state"]["fetches"] == 0
    assert collision["final"]["pc"] == NMI_ROOT
    assert collision["final"]["errorepc"] == irq_root(0)
    assert collision["final"]["fetches"] == 0

    masked = run_case("masked_plus_nmi", bev=0, ie=1, exl=0, erl=0, ip=4, im=8, nmi=1)
    assert masked["first"] == "nmi"
    for gate, args in {
        "ie0": dict(ie=0, exl=0, erl=0),
        "exl1": dict(ie=1, exl=1, erl=0),
        "erl1": dict(ie=1, exl=0, erl=1),
    }.items():
        row = run_case(gate, bev=0, ip=4, im=4, nmi=1, **args)
        assert row["first"] == "nmi"

    rng = random.Random(0x4E4D4951)
    counts = {"irq_then_nmi": 0, "nmi_first": 0, "fetch_first": 0}
    same_value_rechecks = 0
    for _ in range(100_000):
        s = State(
            bev=rng.randrange(2), ie=rng.randrange(2), exl=rng.randrange(2), erl=rng.randrange(2),
            ip=rng.randrange(256), im=rng.randrange(256), nmi=rng.randrange(2)
        )
        before = (s.ip, s.nmi)
        first = boundary(s)
        after_first = (s.ip, s.nmi)
        second = boundary(s)
        if before == after_first:
            same_value_rechecks += 1
        if first == "irq" and before[1]:
            assert second == "nmi", (before, s)
            counts["irq_then_nmi"] += 1
        elif first == "nmi":
            counts["nmi_first"] += 1
        elif first == "fetch":
            counts["fetch_first"] += 1

    forged = {
        "nmi_always_wins_collision": collision["first"] != "nmi",
        "interrupt_root_transfer_implies_fetch": collision["first_state"]["fetches"] == 0,
        "nmi_disappears_after_irq_without_clear": collision["second"] == "nmi",
        "persistent_irq_reenters_despite_exl": collision["second"] != "irq",
        "masked_pending_becomes_irq": masked["first"] != "irq",
        "epc_can_stand_in_for_errorepc": collision["final"]["errorepc"] != collision["final"]["epc"],
        "equal_pending_values_mean_no_new_boundary_check": same_value_rechecks > 0 and counts["irq_then_nmi"] > 0,
    }
    assert all(forged.values()), forged

    payload = {
        "cases": [collision, masked],
        "fuzz_seed": "0x4e4d4951",
        "fuzz_cases": 100_000,
        "counts": counts,
        "same_value_pending_rechecks": same_value_rechecks,
        "forged_histories_rejected": sorted(forged),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    out = Path(__file__).with_name("model-results.json")
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))
    print(f"PASS: 100000 adversarial states; rejected {len(forged)} forged ordering/closure policies")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
