#!/usr/bin/env python3
"""Fail-closed causal replay for SI producer -> MI -> CPU-root composition."""
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
    last_live_producer: str | None = None


def step(s: State, event: tuple[str, bool | None]) -> dict:
    kind, value = event
    if kind == "request":
        pass
    elif kind in {"complete_dma", "complete_bus"}:
        s.completion_generation += 1
        s.si_pending = True
        s.last_live_completion = s.completion_generation
        s.last_live_producer = "dma" if kind == "complete_dma" else "bus"
        s.rcp_pending = s.mi_mask
    elif kind == "ack":
        s.clear_generation += 1
        s.si_pending = False
        s.last_live_completion = None
        s.last_live_producer = None
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
        "root_producer": s.last_live_producer if take else None,
        "final": asdict(s),
    }


def require_certificate(events, claimed_generation: int | None, claimed_producer: str | None, **gate) -> dict:
    result = replay(events, **gate)
    if result["take"]:
        if claimed_generation is None or claimed_generation != result["root_completion_generation"]:
            raise ValueError("CPU root is not bound to the live SI completion generation")
        if claimed_producer is None or claimed_producer != result["root_producer"]:
            raise ValueError("CPU root is bound to a different SI producer kind")
    elif claimed_generation is not None or claimed_producer is not None:
        raise ValueError("claimed SI-root transfer but CPU gate did not take")
    return result


def must_reject(events, claimed_generation, claimed_producer, **gate) -> str:
    try:
        require_certificate(events, claimed_generation, claimed_producer, **gate)
    except ValueError as exc:
        return str(exc)
    raise AssertionError((events, claimed_generation, claimed_producer, gate))


def main() -> int:
    gate = dict(cpu_im=True, ie=True, exl=False, erl=False)
    cases = {}

    cases["dma_completion_takes"] = require_certificate(
        [("mi_mask", True), ("request", None), ("complete_dma", None)], 1, "dma", **gate
    )
    cases["bus_completion_is_distinct_root"] = require_certificate(
        [("mi_mask", True), ("request", None), ("complete_bus", None)], 1, "bus", **gate
    )
    assert cases["dma_completion_takes"]["final"]["si_pending"] == cases["bus_completion_is_distinct_root"]["final"]["si_pending"]
    assert cases["dma_completion_takes"]["final"]["rcp_pending"] == cases["bus_completion_is_distinct_root"]["final"]["rcp_pending"]

    cases["request_only_suppressed"] = require_certificate(
        [("mi_mask", True), ("request", None)], None, None, **gate
    )
    cases["ack_cuts_live_generation"] = require_certificate(
        [("mi_mask", True), ("complete_dma", None), ("ack", None)], None, None, **gate
    )
    cases["second_completion_is_distinct"] = require_certificate(
        [("mi_mask", True), ("complete_dma", None), ("ack", None), ("complete_dma", None)], 2, "dma", **gate
    )
    cases["same_value_mask_write_has_new_operation_generation"] = require_certificate(
        [("mi_mask", True), ("mi_mask", True), ("complete_dma", None)], 1, "dma", **gate
    )
    assert cases["same_value_mask_write_has_new_operation_generation"]["final"]["mask_write_generation"] == 2

    for name, override in {
        "mi_mask_off": [("mi_mask", False), ("complete_dma", None)],
        "cpu_im_off": [("mi_mask", True), ("complete_dma", None)],
        "ie_off": [("mi_mask", True), ("complete_dma", None)],
        "exl_on": [("mi_mask", True), ("complete_dma", None)],
        "erl_on": [("mi_mask", True), ("complete_dma", None)],
    }.items():
        gates = dict(gate)
        if name == "cpu_im_off": gates["cpu_im"] = False
        if name == "ie_off": gates["ie"] = False
        if name == "exl_on": gates["exl"] = True
        if name == "erl_on": gates["erl"] = True
        cases[name] = require_certificate(override, None, None, **gates)

    rejects = {
        "deleted_completion": must_reject([("mi_mask", True), ("request", None)], 1, "dma", **gate),
        "bus_completion_relabelled_as_dma": must_reject(
            [("mi_mask", True), ("request", None), ("complete_bus", None)], 1, "dma", **gate
        ),
        "stale_generation_after_ack_and_recomplete": must_reject(
            [("mi_mask", True), ("complete_dma", None), ("ack", None), ("complete_dma", None)], 1, "dma", **gate
        ),
        "claimed_after_ack": must_reject(
            [("mi_mask", True), ("complete_dma", None), ("ack", None)], 1, "dma", **gate
        ),
        "claimed_with_mask_off": must_reject(
            [("mi_mask", False), ("complete_dma", None)], 1, "dma", **gate
        ),
        "claimed_with_cpu_mask_off": must_reject(
            [("mi_mask", True), ("complete_dma", None)], 1, "dma", cpu_im=False, ie=True, exl=False, erl=False
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
