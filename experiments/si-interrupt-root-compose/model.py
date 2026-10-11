#!/usr/bin/env python3
"""Small fail-closed causal model for SI completion -> MI -> CPU root composition."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json


@dataclass
class State:
    si_pending: bool = False
    mi_mask: bool = False
    rcp_pending: bool = False
    completion_generation: int = 0
    clear_generation: int = 0
    mask_write_generation: int = 0
    last_live_completion: int | None = None


def step(s: State, event: tuple[str, bool | None]) -> dict:
    kind, value = event
    if kind == "request":
        pass
    elif kind == "complete":
        s.completion_generation += 1
        s.si_pending = True
        s.last_live_completion = s.completion_generation
        s.rcp_pending = s.mi_mask
    elif kind == "ack":
        s.clear_generation += 1
        s.si_pending = False
        s.last_live_completion = None
        s.rcp_pending = False
    elif kind == "mi_mask":
        assert value is not None
        s.mask_write_generation += 1
        s.mi_mask = bool(value)
        s.rcp_pending = s.si_pending and s.mi_mask
    else:
        raise ValueError(kind)
    return asdict(s)


def replay(events: list[tuple[str, bool | None]], *, cpu_im: bool, ie: bool, exl: bool, erl: bool) -> dict:
    s = State()
    trace = []
    for event in events:
        trace.append({"event": event[0], "value": event[1], "state": step(s, event)})
    take = s.rcp_pending and cpu_im and ie and not exl and not erl
    return {
        "trace": trace,
        "take": take,
        "root_completion_generation": s.last_live_completion if take else None,
        "final": asdict(s),
    }


def require_certificate(events, claimed_generation: int | None, **gate) -> dict:
    result = replay(events, **gate)
    if result["take"]:
        if claimed_generation is None or claimed_generation != result["root_completion_generation"]:
            raise ValueError("CPU root is not bound to the live SI completion generation")
    elif claimed_generation is not None:
        raise ValueError("claimed SI-root transfer but CPU gate did not take")
    return result


def must_reject(events, claimed_generation, **gate) -> str:
    try:
        require_certificate(events, claimed_generation, **gate)
    except ValueError as exc:
        return str(exc)
    raise AssertionError((events, claimed_generation, gate))


def main() -> int:
    gate = dict(cpu_im=True, ie=True, exl=False, erl=False)
    cases = {}

    cases["completion_takes"] = require_certificate(
        [("mi_mask", True), ("request", None), ("complete", None)], 1, **gate
    )
    cases["request_only_suppressed"] = require_certificate(
        [("mi_mask", True), ("request", None)], None, **gate
    )
    cases["ack_cuts_live_generation"] = require_certificate(
        [("mi_mask", True), ("complete", None), ("ack", None)], None, **gate
    )
    cases["second_completion_is_distinct"] = require_certificate(
        [("mi_mask", True), ("complete", None), ("ack", None), ("complete", None)], 2, **gate
    )
    cases["same_value_mask_write_has_new_operation_generation"] = require_certificate(
        [("mi_mask", True), ("mi_mask", True), ("complete", None)], 1, **gate
    )
    assert cases["same_value_mask_write_has_new_operation_generation"]["final"]["mask_write_generation"] == 2

    for name, override in {
        "mi_mask_off": [("mi_mask", False), ("complete", None)],
        "cpu_im_off": [("mi_mask", True), ("complete", None)],
        "ie_off": [("mi_mask", True), ("complete", None)],
        "exl_on": [("mi_mask", True), ("complete", None)],
        "erl_on": [("mi_mask", True), ("complete", None)],
    }.items():
        gates = dict(gate)
        if name == "cpu_im_off": gates["cpu_im"] = False
        if name == "ie_off": gates["ie"] = False
        if name == "exl_on": gates["exl"] = True
        if name == "erl_on": gates["erl"] = True
        cases[name] = require_certificate(override, None, **gates)

    rejects = {
        "deleted_completion": must_reject([("mi_mask", True), ("request", None)], 1, **gate),
        "stale_generation_after_ack_and_recomplete": must_reject(
            [("mi_mask", True), ("complete", None), ("ack", None), ("complete", None)], 1, **gate
        ),
        "claimed_after_ack": must_reject(
            [("mi_mask", True), ("complete", None), ("ack", None)], 1, **gate
        ),
        "claimed_with_mask_off": must_reject(
            [("mi_mask", False), ("complete", None)], 1, **gate
        ),
        "claimed_with_cpu_mask_off": must_reject(
            [("mi_mask", True), ("complete", None)], 1, cpu_im=False, ie=True, exl=False, erl=False
        ),
    }

    payload = {"cases": cases, "forged_rejections": rejects}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    print(f"MODEL_SHA256={digest}")
    print(f"PASS: {len(cases)} causal controls and {len(rejects)} forged histories")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
