#!/usr/bin/env python3
"""Execute the exact-pinned ares KSU/X-bit exception-root matrix.

The checker deliberately keeps two models separate:
1. the mode/segment model declared by ares Context/segment helpers;
2. the actual implementation-order model, including devirtualize's early RDRAM fast path.
A disagreement between those models is evidence, not something to normalize away.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-ksu-exception-roots-gpt56sol"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


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
    return (base + offset) & 0xFFFFFFFFFFFFFFFF


def sign_extend_32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value | (0xFFFFFFFF00000000 if value & 0x80000000 else 0)


def segment_model(mode: str, bits: int, va: int) -> str:
    """Mirror the exact pinned ares Context/segment helper classification.

    This intentionally excludes the devirtualize RDRAM fast path so we can detect
    when implementation order bypasses the declared privilege segmentation.
    """
    if bits == 32:
        if sign_extend_32(va) != va:
            return "address_error"
        low = va & 0xFFFFFFFF
        if mode == "kernel":
            if low <= 0x7FFFFFFF:
                return "mapped"
            if low <= 0x9FFFFFFF:
                return "cached"
            if low <= 0xBFFFFFFF:
                return "direct"
            return "mapped"
        if mode == "supervisor":
            if low <= 0x7FFFFFFF:
                return "mapped"
            if low <= 0xBFFFFFFF:
                return "unused"
            if low <= 0xDFFFFFFF:
                return "mapped"
            return "unused"
        if mode == "user":
            return "mapped" if low <= 0x7FFFFFFF else "unused"
        raise AssertionError(mode)

    if mode == "kernel":
        if va <= 0x000000FFFFFFFFFF:
            return "mapped"
        if va <= 0x3FFFFFFFFFFFFFFF:
            return "unused"
        if va <= 0x400000FFFFFFFFFF:
            return "mapped"
        if va <= 0x7FFFFFFFFFFFFFFF:
            return "unused"
        # xkphys alternates admissible 32-bit windows and unused gaps.
        for upper, kind in [
            (0x80000000FFFFFFFF, "cached32"),
            (0x87FFFFFFFFFFFFFF, "unused"),
            (0x88000000FFFFFFFF, "cached32"),
            (0x8FFFFFFFFFFFFFFF, "unused"),
            (0x90000000FFFFFFFF, "direct32"),
            (0x97FFFFFFFFFFFFFF, "unused"),
            (0x98000000FFFFFFFF, "cached32"),
            (0x9FFFFFFFFFFFFFFF, "unused"),
            (0xA0000000FFFFFFFF, "cached32"),
            (0xA7FFFFFFFFFFFFFF, "unused"),
            (0xA8000000FFFFFFFF, "cached32"),
            (0xAFFFFFFFFFFFFFFF, "unused"),
            (0xB0000000FFFFFFFF, "cached32"),
            (0xB7FFFFFFFFFFFFFF, "unused"),
            (0xB8000000FFFFFFFF, "cached32"),
            (0xBFFFFFFFFFFFFFFF, "unused"),
        ]:
            if va <= upper:
                return kind
        if va <= 0xC00000FF7FFFFFFF:
            return "mapped"
        if va <= 0xFFFFFFFF7FFFFFFF:
            return "unused"
        if va <= 0xFFFFFFFF9FFFFFFF:
            return "cached"
        if va <= 0xFFFFFFFFBFFFFFFF:
            return "direct"
        if va <= 0xFFFFFFFFDFFFFFFF:
            return "mapped"
        return "mapped"

    if mode == "supervisor":
        if va <= 0x000000FFFFFFFFFF:
            return "mapped"
        if va <= 0x3FFFFFFFFFFFFFFF:
            return "unused"
        if va <= 0x400000FFFFFFFFFF:
            return "mapped"
        if va <= 0xFFFFFFFFBFFFFFFF:
            return "unused"
        if va <= 0xFFFFFFFFDFFFFFFF:
            return "mapped"
        return "unused"

    if mode == "user":
        return "mapped" if va <= 0x000000FFFFFFFFFF else "unused"
    raise AssertionError(mode)


def source_outcome(mode: str, bits: int, va: int) -> str:
    segment = segment_model(mode, bits, va)
    if segment == "mapped":
        return "tlb_refill_64" if bits == 64 else "tlb_refill_32"
    if segment in {"unused", "address_error"}:
        return "address_error"
    # Only direct/cached test addresses whose masked physical address is zero are
    # included in this matrix, so successful execution is deterministic.
    if (va & (0xFFFFFFFF if segment.endswith("32") else 0x1FFFFFFF)) == 0:
        return "execute"
    return "direct_other"


def implementation_outcome(mode: str, bits: int, va: int) -> str:
    # vaddrAlignedError runs first. In 32-bit context, non-sign-extended values
    # fault before the fast path.
    if bits == 32 and sign_extend_32(va) != va:
        return "address_error"
    # Exact pinned ares memory.cpp checks this before segment(vaddr), so privilege
    # segmentation is bypassed for this RDRAM window.
    if 0xFFFFFFFF80000000 <= va <= 0xFFFFFFFF83EFFFFF:
        return "execute"
    return source_outcome(mode, bits, va)


def classify_actual(state: dict) -> str:
    if state["final_exl"] == 0 and state["v0"] == 1:
        return "execute"
    if state["final_exl"] != 1:
        return f"unexpected_no_exception_v0_{state['v0']}"
    if state["cause"] == 4:
        return "address_error"
    if state["cause"] == 2:
        if state["pc"] in {vector(state["bev"], 0x80)}:
            return "tlb_refill_64"
        if state["pc"] in {vector(state["bev"], 0x00)}:
            return "tlb_refill_32"
        return "tlb_other_vector"
    return f"exception_{state['cause']}"


def cases():
    # label, mode, bits, bev, VA
    return [
        ("k32_kuseg_miss", "kernel", 32, 0, 0x0000000000004000),
        ("s32_suseg_miss", "supervisor", 32, 0, 0x0000000000004000),
        ("u32_useg_miss", "user", 32, 1, 0x0000000000004000),
        ("s32_sseg_miss", "supervisor", 32, 0, 0xFFFFFFFFC0004000),
        ("u32_sseg_forbidden", "user", 32, 0, 0xFFFFFFFFC0004000),
        ("k32_noncanonical", "kernel", 32, 1, 0x0000000080000000),
        ("k64_xkuseg_miss", "kernel", 64, 0, 0x0000000100004000),
        ("s64_xsuseg_miss", "supervisor", 64, 0, 0x0000000100004000),
        ("u64_xuseg_miss", "user", 64, 1, 0x0000000100004000),
        ("k64_xksseg_miss", "kernel", 64, 0, 0x4000000000004000),
        ("s64_xsseg_miss", "supervisor", 64, 0, 0x4000000000004000),
        ("u64_xsseg_forbidden", "user", 64, 0, 0x4000000000004000),
        ("s64_csseg_miss", "supervisor", 64, 1, 0xFFFFFFFFC0004000),
        ("u64_csseg_forbidden", "user", 64, 1, 0xFFFFFFFFC0004000),
        ("k32_rdram_fastpath_control", "kernel", 32, 0, 0xFFFFFFFF80000000),
        ("s32_rdram_fastpath_privilege_attack", "supervisor", 32, 0, 0xFFFFFFFF80000000),
        ("u32_rdram_fastpath_privilege_attack", "user", 32, 0, 0xFFFFFFFF80000000),
        ("s64_rdram_fastpath_privilege_attack", "supervisor", 64, 0, 0xFFFFFFFF80000000),
        ("u64_rdram_fastpath_privilege_attack", "user", 64, 0, 0xFFFFFFFF80000000),
        ("s32_after_fastpath_forbidden", "supervisor", 32, 0, 0xFFFFFFFF83F00000),
        ("u32_after_fastpath_forbidden", "user", 32, 0, 0xFFFFFFFF83F00000),
        ("s64_after_fastpath_forbidden", "supervisor", 64, 0, 0xFFFFFFFF83F00000),
        ("u64_after_fastpath_forbidden", "user", 64, 0, 0xFFFFFFFF83F00000),
    ]


def check_state(case, state):
    label, mode, bits, bev, va = case
    assert state["mode"] == mode and state["requested_bits"] == bits, (case, state)
    assert state["bev"] == bev and state["va"] == va, (case, state)
    assert state["initial_context_bits"] == bits, (case, state)
    expected_mode = {"kernel": 0, "supervisor": 1, "user": 2}[mode]
    assert state["initial_context_mode"] == expected_mode, (case, state)

    actual = classify_actual(state)
    impl = implementation_outcome(mode, bits, va)
    declared = source_outcome(mode, bits, va)
    assert actual == impl, (label, declared, impl, actual, state)

    if actual == "execute":
        assert state["final_exl"] == 0 and state["v0"] == 1, (case, state)
    else:
        assert state["final_exl"] == 1 and state["v0"] == 0, (case, state)
        assert state["epc"] == va, (case, state)
        assert state["badva"] == va, (case, state)
        if actual == "address_error":
            assert state["cause"] == 4 and state["pc"] == vector(bev, 0x180), (case, state)
        elif actual == "tlb_refill_32":
            assert state["cause"] == 2 and state["pc"] == vector(bev, 0), (case, state)
        elif actual == "tlb_refill_64":
            assert state["cause"] == 2 and state["pc"] == vector(bev, 0x80), (case, state)
    return declared, impl, actual


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch the exact pinned reference first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")

    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    rows = []
    disagreements = []
    for case in cases():
        label, mode, bits, bev, va = case
        args = [str(exe), mode, str(bits), str(bev), hex(va)]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case, first, second)
        state = json.loads(first)
        declared, impl, actual = check_state(case, state)
        row = {
            "label": label,
            "declared_segment_outcome": declared,
            "implementation_order_outcome": impl,
            "actual_outcome": actual,
            "declared_vs_actual_disagreement": declared != actual,
            **state,
        }
        if declared != actual:
            disagreements.append(label)
        rows.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))

    expected_attacks = {
        "s32_rdram_fastpath_privilege_attack",
        "u32_rdram_fastpath_privilege_attack",
        "s64_rdram_fastpath_privilege_attack",
        "u64_rdram_fastpath_privilege_attack",
    }
    assert set(disagreements) == expected_attacks, disagreements

    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "ares_revision": ARES_REV,
        "case_count": len(rows),
        "declared_vs_actual_disagreements": disagreements,
        "results": rows,
    }
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"PASS: {len(rows)} cases repeated byte-identically; "
        f"{len(disagreements)} deliberate privilege/fast-path disagreements preserved"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
