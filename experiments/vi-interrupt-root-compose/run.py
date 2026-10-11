#!/usr/bin/env python3
"""Build exact pinned ares and execute VI -> MI -> CPU root composition cases."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/vi-interrupt-root-compose"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
PLAID_BASE = "211176e7a489fecf8331d02915ee982cd279cb62"
START_PC = 0xFFFFFFFFA0000000
EPC_SENTINEL = 0x123456789ABCDEF0
CAUSE_SENTINEL = 13
EXECUTED_S0 = 0x1234
RCP_IP = 1 << 2
MI_AI = 1 << 2
MI_VI = 1 << 3


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(bev: int) -> int:
    return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000) + 0x180


def case(name, mode, bev=0, mi=1, cpu_im=1, ie=1, exl=0, erl=0):
    return (name, mode, bev, mi, cpu_im, ie, exl, erl)


def cases():
    return [
        case("vi_trigger_bev0", "trigger", bev=0),
        case("vi_trigger_bev1", "trigger", bev=1),
        case("config_only", "config_only"),
        case("vi_mask_off", "trigger", mi=0),
        case("cpu_im_off", "trigger", cpu_im=0),
        case("ie_off", "trigger", ie=0),
        case("exl_on", "trigger", exl=1),
        case("erl_on", "trigger", erl=1),
        case("trigger_then_ack_zero", "trigger_ack0"),
        case("trigger_then_ack_arbitrary_payload", "trigger_ack_dead"),
        case("ack_without_trigger", "ack_empty"),
        case("fresh_trigger_after_ack", "retrigger"),
        case("direct_mi_vi_equal_state_decoy", "direct_mi_vi"),
        case("ai_same_ip2_decoy", "ai_decoy", mi=0),
    ]


def source_pending(mode: str) -> bool:
    return mode in {"trigger", "retrigger", "direct_mi_vi"}


def should_take(c) -> bool:
    _name, mode, _bev, vi_mask, cpu_im, ie, exl, erl = c
    if mode == "ai_decoy":
        pending = True
        source_mask = True
    else:
        pending = source_pending(mode)
        source_mask = bool(vi_mask)
    return pending and source_mask and bool(cpu_im) and bool(ie) and not exl and not erl


def check(c, state):
    name, mode, bev, vi_mask, cpu_im, ie, exl, erl = c
    assert state["name"] == name and state["mode"] == mode, (c, state)
    assert (state["bev"], state["vi_mask_enabled"], state["cpu_im_enabled"], state["ie"], state["initial_exl"], state["initial_erl"]) == (bev, vi_mask, cpu_im, ie, exl, erl), (c, state)
    assert state["initial"]["coincidence"] == 2, state
    assert not (state["initial"]["mi_intr"] & (MI_VI | MI_AI)), state
    assert bool(state["initial"]["mi_mask"] & MI_VI) is bool(vi_mask), state

    if mode in {"trigger", "trigger_ack0", "trigger_ack_dead", "retrigger"}:
        assert state["trigger_count"] >= 1, state
        assert state["after_trigger"]["mi_intr"] & MI_VI, state
        assert bool(state["after_trigger"]["cause_ip"] & RCP_IP) is bool(vi_mask), state
    if mode in {"trigger_ack0", "trigger_ack_dead", "retrigger"}:
        assert state["ack_count"] == 1, state
        assert not (state["after_ack"]["mi_intr"] & MI_VI), state
        assert not (state["after_ack"]["cause_ip"] & RCP_IP), state
    if mode == "retrigger":
        assert state["trigger_count"] == 2, state
        assert state["before_cpu"]["mi_intr"] & MI_VI, state
    if mode in {"trigger_ack0", "trigger_ack_dead", "ack_empty", "config_only"}:
        assert not (state["before_cpu"]["mi_intr"] & MI_VI), state
    if mode == "direct_mi_vi":
        assert state["trigger_count"] == 0, state
        assert state["before_cpu"]["mi_intr"] & MI_VI, state
        assert state["before_cpu"]["cause_ip"] & RCP_IP, state
    if mode == "ai_decoy":
        assert state["trigger_count"] == 0, state
        assert not (state["before_cpu"]["mi_intr"] & MI_VI), state
        assert state["before_cpu"]["mi_intr"] & MI_AI, state
        assert state["before_cpu"]["cause_ip"] & RCP_IP, state

    if should_take(c):
        assert state["pc"] == vector(bev), (c, state)
        assert state["s0"] == 0, (c, state)
        assert state["cause"] == 0 and state["bd"] == 0, (c, state)
        assert state["epc"] == START_PC, (c, state)
        assert state["final_exl"] == 1 and state["final_erl"] == 0, (c, state)
    else:
        assert state["pc"] == START_PC + 4, (c, state)
        assert state["s0"] == EXECUTED_S0, (c, state)
        assert state["cause"] == CAUSE_SENTINEL and state["bd"] == 1, (c, state)
        assert state["epc"] == EPC_SENTINEL, (c, state)
        assert state["final_exl"] == exl and state["final_erl"] == erl, (c, state)

    # Interrupt entry itself does not acknowledge the VI or AI producer.
    assert state["after_cpu"]["mi_intr"] == state["before_cpu"]["mi_intr"], state


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch exact pins first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for c in cases():
        args = [str(exe), *map(str, c)]
        first = subprocess.check_output(args, text=True, timeout=20)
        second = subprocess.check_output(args, text=True, timeout=20)
        assert first == second, (c, first, second)
        state = json.loads(first)
        check(c, state)
        row = {"taken": should_take(c), **state}
        results.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))

    actual = next(r for r in results if r["name"] == "vi_trigger_bev0")
    direct = next(r for r in results if r["name"] == "direct_mi_vi_equal_state_decoy")
    # Equal final MI.VI and CPU-IP2 state does not authenticate the VI timing producer.
    for key in ("mi_intr", "mi_mask", "cause_ip"):
        assert actual["before_cpu"][key] == direct["before_cpu"][key], (key, actual, direct)
    assert actual["trigger_count"] == 1 and direct["trigger_count"] == 0
    assert actual["producer"] == "vi_coincidence" and direct["producer"] == "direct_mi_vi_decoy"

    ai = next(r for r in results if r["name"] == "ai_same_ip2_decoy")
    assert bool(actual["before_cpu"]["cause_ip"] & RCP_IP) == bool(ai["before_cpu"]["cause_ip"] & RCP_IP)
    assert (actual["before_cpu"]["mi_intr"] & MI_VI) and not (ai["before_cpu"]["mi_intr"] & MI_VI)

    ack0 = next(r for r in results if r["name"] == "trigger_then_ack_zero")
    ackdead = next(r for r in results if r["name"] == "trigger_then_ack_arbitrary_payload")
    assert ack0["ack_payload"] != ackdead["ack_payload"]
    assert ack0["before_cpu"] == ackdead["before_cpu"]

    payload = {
        "plaid_base": PLAID_BASE,
        "ares_revision": ARES_REV,
        "gopher64_source_revision": GOPHER_REV,
        "case_count": len(results),
        "taken_count": sum(1 for row in results if row["taken"]),
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(f"RESULT_SHA256={digest}")
    print(f"PASS: {len(results)} exact-pinned VI/MI/CPU composition cases repeat byte-identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
