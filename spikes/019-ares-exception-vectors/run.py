#!/usr/bin/env python3
"""Exercise pinned ares exception-vector selection with guest-triggered faults."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-exception-vectors"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
EPC_SENTINEL = 0x123456789ABCDEF0


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vector(bev: int, offset: int) -> int:
    base = 0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000
    return base + offset


def expected_offset(kind: str, bits: int, initial_exl: int) -> int:
    if kind in {"tlb_load_miss", "tlb_store_miss", "tlb_fetch_miss"} and not initial_exl:
        return 0x80 if bits == 64 else 0
    return 0x180


def expected_cause(kind: str) -> int:
    if kind == "syscall":
        return 8
    if kind == "tlb_store_miss":
        return 3
    return 2


def expected_epc(kind: str, initial_exl: int, delay: int) -> int:
    if initial_exl:
        return EPC_SENTINEL
    if kind == "tlb_fetch_miss":
        return 0x4000
    # Every non-fetch fixture begins at A0000000. Delay-slot faults must point EPC
    # back at the branch, which is the same address.
    return 0xFFFFFFFFA0000000


def cases():
    out = []
    for bits in (32, 64):
        for bev in (0, 1):
            out.append(("syscall", bits, bev, 0, 0))
            out.append(("tlb_invalid", bits, bev, 0, 0))
            for kind in ("tlb_fetch_miss", "tlb_store_miss"):
                out.append((kind, bits, bev, 0, 0))
            for exl in (0, 1):
                out.append(("tlb_load_miss", bits, bev, exl, 0))
    for bev in (0, 1):
        out.append(("syscall", 32, bev, 0, 1))
    for bits in (32, 64):
        out.append(("tlb_load_miss", bits, 0, 0, 1))
    return out


def check(case, state):
    kind, bits, bev, initial_exl, delay = case
    assert state["kind"] == kind and state["requested_bits"] == bits
    assert state["bev"] == bev and state["initial_exl"] == initial_exl and state["delay"] == delay
    assert state["pc"] == vector(bev, expected_offset(kind, bits, initial_exl)), (case, state)
    assert state["cause"] == expected_cause(kind), (case, state)
    assert state["final_exl"] == 1 and state["context_bits"] == bits, (case, state)
    assert state["epc"] == expected_epc(kind, initial_exl, delay), (case, state)
    if initial_exl:
        assert state["bd"] == 1, (case, state)  # preset sentinel must survive nested entry
    else:
        assert state["bd"] == delay, (case, state)
    if kind.startswith("tlb_"):
        assert state["badva"] == 0x4000, (case, state)


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch the pinned refs first (scripts/fetch_refs.py)")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    results = []
    for case in cases():
        args = [str(exe), case[0], *map(str, case[1:])]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case, first, second)
        state = json.loads(first)
        check(case, state)
        results.append(state)
        print(json.dumps(state, sort_keys=True, separators=(",", ":")))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps({
        "ares_revision": ARES_REV,
        "gopher64_source_revision": GOPHER_REV,
        "case_count": len(results),
        "results": results,
    }, indent=2) + "\n")
    print(f"PASS: {len(results)} guest-triggered cases match the pinned ares exception-vector truth table; every case repeated byte-identically")
    return 0


if __name__ == "__main__":
    sys.exit(main())
