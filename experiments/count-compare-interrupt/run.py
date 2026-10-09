#!/usr/bin/env python3
"""Build and execute the exact pinned ares Count/Compare producer matrix."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/count-compare-interrupt"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PLAID_BASE = "211176e7a489fecf8331d02915ee982cd279cb62"
START_PC = 0xFFFFFFFFA0000000
NORMAL_VECTOR = 0xFFFFFFFF80000180
BOOT_VECTOR = 0xFFFFFFFFBFC00380
EXECUTED_S0 = 0x1234
EPC_SENTINEL = 0x123456789ABCDEF0
CAUSE_SENTINEL = 13

CASES = [
    "near_exact_bev0",
    "cross_bev1",
    "before_deadline",
    "masked",
    "ie0",
    "exl1",
    "erl1",
    "compare_clear_new_value",
    "compare_clear_same_value",
    "count_write_keeps_pending",
    "count_forward_changes_deadline",
    "count_backward_changes_deadline",
    "wrap_cross",
    "equal_compare_no_immediate",
    "guest_compare_ack",
    "guest_count_not_ack",
]

GATES = {
    "near_exact_bev0": (0, 1, 0, 0, 0x80),
    "cross_bev1": (1, 1, 0, 0, 0x80),
    "before_deadline": (0, 0, 0, 0, 0),
    "masked": (0, 1, 0, 0, 0),
    "ie0": (0, 0, 0, 0, 0x80),
    "exl1": (0, 1, 1, 0, 0x80),
    "erl1": (0, 1, 0, 1, 0x80),
    "compare_clear_new_value": (0, 1, 0, 0, 0x80),
    "compare_clear_same_value": (0, 1, 0, 0, 0x80),
    "count_write_keeps_pending": (0, 1, 0, 0, 0x80),
    "count_forward_changes_deadline": (0, 0, 0, 0, 0),
    "count_backward_changes_deadline": (0, 0, 0, 0, 0),
    "wrap_cross": (0, 0, 0, 0, 0),
    "equal_compare_no_immediate": (0, 0, 0, 0, 0),
    # The guest MTC0 retires while IM7 is masked, then IM7 is enabled for the
    # final boundary check. These tuples describe that final boundary.
    "guest_compare_ack": (0, 1, 0, 0, 0x80),
    "guest_count_not_ack": (0, 1, 0, 0, 0x80),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_taken(state: dict, vector: int, epc: int) -> None:
    assert state["pending_before_instruction"] == 1, state
    assert state["pc"] == vector, state
    assert state["s0"] == 0, state
    assert state["cause"] == 0, state
    assert state["bd"] == 0, state
    assert state["epc"] == epc, state
    assert state["final_exl"] == 1, state


def check_retired(state: dict, pc: int) -> None:
    assert state["pc"] == pc, state
    assert state["s0"] == EXECUTED_S0, state
    assert state["cause"] == CAUSE_SENTINEL, state
    assert state["bd"] == 1, state
    assert state["epc"] == EPC_SENTINEL, state


def check(name: str, s: dict) -> None:
    assert s["name"] == name, s
    assert (s["bev"], s["ie"], s["exl"], s["erl"], s["im"]) == GATES[name], s

    if name == "near_exact_bev0":
        check_taken(s, NORMAL_VECTOR, START_PC)
    elif name == "cross_bev1":
        check_taken(s, BOOT_VECTOR, START_PC)
    elif name == "before_deadline":
        assert s["pending_final"] == 0 and s["count"] == 102 and s["compare"] == 103, s
        assert s["pc"] == START_PC and s["s0"] == 0, s
    elif name in {"masked", "ie0", "exl1", "erl1"}:
        assert s["pending_before_instruction"] == 1 and s["pending_final"] == 1, s
        check_retired(s, START_PC + 4)
    elif name in {"compare_clear_new_value", "compare_clear_same_value"}:
        assert s["pending_before_write"] == 1, s
        assert s["pending_after_write"] == 0, s
        assert s["pending_before_instruction"] == 0, s
        check_retired(s, START_PC + 4)
        if name == "compare_clear_same_value":
            assert s["compare"] == 103, s
        else:
            assert s["compare"] == 1000, s
    elif name == "count_write_keeps_pending":
        assert s["pending_before_write"] == 1 and s["pending_after_write"] == 1, s
        check_taken(s, NORMAL_VECTOR, START_PC)
    elif name == "count_forward_changes_deadline":
        # ares recomputes the implicit modular deadline from rewritten Count=108;
        # advancing two visible Count ticks reaches Compare=110 and latches IP7.
        assert s["pending_final"] == 1 and s["count"] == 110 and s["compare"] == 110, s
        assert s["pc"] == START_PC, s
    elif name == "count_backward_changes_deadline":
        # Rewriting Count from 100 back to 0 moves ares away from Compare=105.
        assert s["pending_final"] == 0 and s["count"] == 5 and s["compare"] == 105, s
        assert s["pc"] == START_PC, s
    elif name == "wrap_cross":
        assert s["pending_final"] == 1 and s["count"] == 1 and s["compare"] == 1, s
    elif name == "equal_compare_no_immediate":
        assert s["pending_final"] == 0 and s["count"] == 101 and s["compare"] == 100, s
    elif name == "guest_compare_ack":
        assert s["guest_write_executed"] == 1 and s["second_instruction_attempted"] == 1, s
        assert s["pending_before_write"] == 1 and s["pending_after_write"] == 0, s
        assert s["pending_before_instruction"] == 0, s
        check_retired(s, START_PC + 8)
    elif name == "guest_count_not_ack":
        assert s["guest_write_executed"] == 1 and s["second_instruction_attempted"] == 1, s
        assert s["pending_before_write"] == 1 and s["pending_after_write"] == 1, s
        check_taken(s, NORMAL_VECTOR, START_PC + 4)
    else:
        raise AssertionError(name)


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch exact refs first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for name in CASES:
        args = [str(exe), name]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (name, first, second)
        state = json.loads(first)
        check(name, state)
        results.append(state)
        print(json.dumps(state, sort_keys=True, separators=(",", ":")))

    model_stdout = subprocess.check_output([sys.executable, str(HERE / "model.py")], text=True)
    model_hash = next(line.split()[1] for line in model_stdout.splitlines() if line.startswith("MODEL_SHA256 "))
    (OUTPUT / "model.out").write_text(model_stdout)

    source_guard = OUTPUT / "source_guard.json"
    if not source_guard.exists():
        raise SystemExit("source_guard.json missing; run source_guard.py first")

    payload = {
        "schema": "plaid-count-compare-exact-ares/v0",
        "plaid_base": PLAID_BASE,
        "ares_revision": ARES_REV,
        "case_count": len(results),
        "model_sha256": model_hash,
        "source_guard_sha256": sha256(source_guard),
        "results": results,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "results.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = sha256(target)
    print(model_stdout, end="")
    print(f"RESULT_SHA256 {digest}")
    print("PASS: exact pinned ares Count/Compare producer, acknowledgement, wrap, gate/root and guest-MTC0 cases repeat byte-identically")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
