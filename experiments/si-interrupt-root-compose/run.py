#!/usr/bin/env python3
"""Build exact pinned ares and execute SI/PIF -> MI -> CPU root composition cases."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/si-interrupt-root-compose"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
PLAID_BASE = "211176e7a489fecf8331d02915ee982cd279cb62"
START_PC = 0xFFFFFFFFA0000000
EPC_SENTINEL = 0x123456789ABCDEF0
CAUSE_SENTINEL = 13
EXECUTED_S0 = 0x1234
RCP_IP = 1 << 2
MI_SI = 1 << 1


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
        case("read_completion_bev0", "complete_read", bev=0),
        case("read_completion_bev1", "complete_read", bev=1),
        case("write_completion", "complete_write"),
        case("request_only", "request_read"),
        case("mi_mask_off", "complete_read", mi=0),
        case("cpu_im_off", "complete_read", cpu_im=0),
        case("ie_off", "complete_read", ie=0),
        case("exl_on", "complete_read", exl=1),
        case("erl_on", "complete_read", erl=1),
        case("completion_then_ack", "complete_ack"),
        case("empty_ack", "ack_empty"),
        case("second_completion_after_ack", "double_complete"),
        # Equal final SI/MI state to a DMA completion, but a different producer.
        case("direct_pif_bus_completion_decoy", "bus_complete"),
    ]


def pending_mode(mode: str) -> bool:
    return mode in {"complete_read", "complete_write", "double_complete", "bus_complete"}


def should_take(c) -> bool:
    _name, mode, _bev, mi, cpu_im, ie, exl, erl = c
    return pending_mode(mode) and bool(mi) and bool(cpu_im) and bool(ie) and not exl and not erl


def assert_source_snapshot(s, pending: bool, mi_mask: bool):
    assert bool(s["si_interrupt"]) is pending, s
    assert bool(s["mi_intr"] & MI_SI) is pending, s
    assert bool(s["mi_mask"] & MI_SI) is mi_mask, s
    assert bool(s["cause_ip"] & RCP_IP) is (pending and mi_mask), s


def check(c, state):
    name, mode, bev, mi_mask, cpu_im, ie, exl, erl = c
    assert state["name"] == name and state["mode"] == mode, (c, state)
    assert (state["bev"], state["mi_mask_enabled"], state["cpu_im_enabled"], state["ie"], state["initial_exl"], state["initial_erl"]) == (bev, mi_mask, cpu_im, ie, exl, erl), (c, state)

    assert_source_snapshot(state["initial"], False, bool(mi_mask))

    if mode in {"request_read", "complete_read", "complete_write", "complete_ack", "double_complete"}:
        assert state["did_request"] == 1, state
        assert state["after_request"]["dma_busy"] == 1, state
        assert_source_snapshot(state["after_request"], False, bool(mi_mask))
    if mode == "bus_complete":
        assert state["did_request"] == 1, state
        assert state["after_request"]["dma_busy"] == 1 and state["after_request"]["io_busy"] == 1, state
        assert_source_snapshot(state["after_request"], False, bool(mi_mask))

    if mode in {"complete_read", "complete_write", "complete_ack", "double_complete", "bus_complete"}:
        assert state["did_complete"] == 1, state
        assert state["after_complete"]["dma_busy"] == 0, state
        assert_source_snapshot(state["after_complete"], True, bool(mi_mask))

    if mode in {"complete_ack", "double_complete"}:
        assert state["did_ack"] == 1, state
        assert_source_snapshot(state["after_ack"], False, bool(mi_mask))
    if mode == "ack_empty":
        assert state["did_ack"] == 1 and state["did_complete"] == 0, state
        assert_source_snapshot(state["after_ack"], False, bool(mi_mask))

    # The second completion in the double case must reassert after the observed clear.
    assert_source_snapshot(state["before_cpu"], pending_mode(mode), bool(mi_mask))

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

    # Architectural interrupt entry does not acknowledge the SI producer.
    assert_source_snapshot(state["after_cpu"], pending_mode(mode), bool(mi_mask))


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

    # Deliberate equality decoy: final producer-visible state is the same, but the
    # bus-write completion is not a DMA completion and must never authenticate one.
    read = next(r for r in results if r["name"] == "read_completion_bev0")
    decoy = next(r for r in results if r["name"] == "direct_pif_bus_completion_decoy")
    for key in ("si_interrupt", "mi_intr", "mi_mask", "cause_ip"):
        assert read["before_cpu"][key] == decoy["before_cpu"][key], (key, read, decoy)
    assert read["producer"] == "dma_read_completion"
    assert decoy["producer"] == "direct_pif_bus_write_completion"

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
    print(f"PASS: {len(results)} exact-pinned SI/MI/CPU composition cases repeat byte-identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
