#!/usr/bin/env python3
"""Fail-closed causal replay for VI coincidence -> MI -> CPU-root composition."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass
class State:
    vi_line: bool = False
    ai_line: bool = False
    vi_mask: bool = False
    ai_mask: bool = False
    rcp_pending: bool = False
    trigger_generation: int = 0
    ack_generation: int = 0
    intr_program_generation: int = 0
    mask_write_generation: int = 0
    last_live_trigger: int | None = None
    vi_line_origin: str | None = None


def repoll(s: State) -> None:
    s.rcp_pending = (s.vi_line and s.vi_mask) or (s.ai_line and s.ai_mask)


def step(s: State, event: tuple[str, int | bool | None]) -> dict:
    kind, value = event
    if kind == "program_intr":
        s.intr_program_generation += 1
    elif kind == "vi_trigger":
        s.trigger_generation += 1
        s.vi_line = True
        s.last_live_trigger = s.trigger_generation
        s.vi_line_origin = "vi_coincidence"
    elif kind == "direct_mi_vi":
        # Deliberate causal decoy: identical MI.VI line without a VI timing witness.
        s.vi_line = True
        s.last_live_trigger = None
        s.vi_line_origin = "direct_mi_vi"
    elif kind == "ai_raise":
        s.ai_line = True
    elif kind == "ack":
        # VI_CURRENT write payload is deliberately irrelevant to the clear operation.
        s.ack_generation += 1
        s.vi_line = False
        s.last_live_trigger = None
        s.vi_line_origin = None
    elif kind == "vi_mask":
        assert value is not None
        s.mask_write_generation += 1
        s.vi_mask = bool(value)
    elif kind == "ai_mask":
        assert value is not None
        s.mask_write_generation += 1
        s.ai_mask = bool(value)
    else:
        raise ValueError(kind)
    repoll(s)
    return asdict(s)


def replay(events: list[tuple[str, int | bool | None]], *, cpu_im: bool, ie: bool, exl: bool, erl: bool) -> dict:
    s = State()
    trace = []
    for event in events:
        trace.append({"event": event[0], "value": event[1], "state": step(s, event)})
    take = s.rcp_pending and cpu_im and ie and not exl and not erl
    vi_root_generation = (
        s.last_live_trigger
        if take and s.vi_line and s.vi_mask and s.vi_line_origin == "vi_coincidence"
        else None
    )
    return {
        "trace": trace,
        "take": take,
        "vi_root_generation": vi_root_generation,
        "final": asdict(s),
    }


def require_certificate(events, claimed_generation: int | None, **gate) -> dict:
    result = replay(events, **gate)
    if claimed_generation != result["vi_root_generation"]:
        if claimed_generation is not None and result["vi_root_generation"] is None:
            raise ValueError("CPU root is not causally bound to a live VI coincidence generation")
        raise ValueError("CPU root is bound to a different VI coincidence generation")
    return result


def must_reject(events, claimed_generation: int | None, **gate) -> str:
    try:
        require_certificate(events, claimed_generation, **gate)
    except ValueError as exc:
        return str(exc)
    raise AssertionError((events, claimed_generation, gate))


def main() -> int:
    gate = dict(cpu_im=True, ie=True, exl=False, erl=False)
    cases = {}

    cases["vi_trigger_takes"] = require_certificate(
        [("vi_mask", True), ("program_intr", 2), ("vi_trigger", None)], 1, **gate
    )
    cases["programming_alone_does_not_raise"] = require_certificate(
        [("vi_mask", True), ("program_intr", 2)], None, **gate
    )
    cases["ack_cuts_live_trigger"] = require_certificate(
        [("vi_mask", True), ("vi_trigger", None), ("ack", 0)], None, **gate
    )
    cases["arbitrary_ack_payload_has_same_clear_semantics"] = require_certificate(
        [("vi_mask", True), ("vi_trigger", None), ("ack", 0xDEADBEEF)], None, **gate
    )
    cases["retrigger_after_ack_is_new_generation"] = require_certificate(
        [("vi_mask", True), ("vi_trigger", None), ("ack", 0), ("vi_trigger", None)], 2, **gate
    )
    cases["same_value_intr_program_is_distinct_operation_not_trigger"] = require_certificate(
        [("vi_mask", True), ("program_intr", 2), ("program_intr", 2), ("vi_trigger", None)], 1, **gate
    )
    assert cases["same_value_intr_program_is_distinct_operation_not_trigger"]["final"]["intr_program_generation"] == 2

    for name, events, gates in [
        ("vi_mask_off", [("vi_mask", False), ("vi_trigger", None)], gate),
        ("cpu_im_off", [("vi_mask", True), ("vi_trigger", None)], dict(cpu_im=False, ie=True, exl=False, erl=False)),
        ("ie_off", [("vi_mask", True), ("vi_trigger", None)], dict(cpu_im=True, ie=False, exl=False, erl=False)),
        ("exl_on", [("vi_mask", True), ("vi_trigger", None)], dict(cpu_im=True, ie=True, exl=True, erl=False)),
        ("erl_on", [("vi_mask", True), ("vi_trigger", None)], dict(cpu_im=True, ie=True, exl=False, erl=True)),
    ]:
        cases[name] = require_certificate(events, None, **gates)

    # Both decoys can cause the generic CPU RCP gate to take, but neither authenticates VI.
    cases["direct_mi_vi_decoy"] = require_certificate(
        [("vi_mask", True), ("direct_mi_vi", None)], None, **gate
    )
    assert cases["direct_mi_vi_decoy"]["take"]
    cases["ai_ip2_decoy"] = require_certificate(
        [("ai_mask", True), ("ai_raise", None)], None, **gate
    )
    assert cases["ai_ip2_decoy"]["take"]

    rejects = {
        "deleted_trigger": must_reject([("vi_mask", True), ("program_intr", 2)], 1, **gate),
        "direct_mi_vi_relabelled_as_timing_trigger": must_reject(
            [("vi_mask", True), ("direct_mi_vi", None)], 1, **gate
        ),
        "ai_root_relabelled_as_vi": must_reject(
            [("ai_mask", True), ("ai_raise", None)], 1, **gate
        ),
        "stale_generation_after_ack_and_retrigger": must_reject(
            [("vi_mask", True), ("vi_trigger", None), ("ack", 0), ("vi_trigger", None)], 1, **gate
        ),
        "claimed_after_ack": must_reject(
            [("vi_mask", True), ("vi_trigger", None), ("ack", 0)], 1, **gate
        ),
        "claimed_with_vi_mask_off": must_reject(
            [("vi_mask", False), ("vi_trigger", None)], 1, **gate
        ),
        "claimed_with_cpu_im_off": must_reject(
            [("vi_mask", True), ("vi_trigger", None)], 1,
            cpu_im=False, ie=True, exl=False, erl=False
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
