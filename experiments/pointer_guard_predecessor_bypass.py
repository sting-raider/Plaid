#!/usr/bin/env python3
"""Deterministic adversary for guarded pointer-table predecessor reachability.

Models only the control/data fact needed by the Plaid table recognizer: SLTIU
sets a boolean bound flag and BEQ flag,zero exits, so dispatch fallthrough is
sound only if the compare dominates the branch. This is deliberately independent
of Rust implementation details.
"""
from __future__ import annotations

import hashlib
import json

COUNT = 3
COMPARE_PC = 0x80000000
BRANCH_PC = 0x80000004
DELAY_PC = 0x80000008
DISPATCH_PC = 0x8000000C
IMAGE = "guard-predecessor-bypass"
GENERATION = 0


def normal_dispatch(index: int) -> bool:
    # SLTIU t1,a0,3; BEQ t1,zero,exit. Dispatch is the not-taken fallthrough.
    flag = int((index & 0xFFFFFFFF) < COUNT)
    return flag != 0


def branch_entry_dispatch(stale_flag: int) -> bool:
    # Entering at BEQ skips the producer of t1 entirely.
    return (stale_flag & 0xFFFFFFFF) != 0


def delay_entry_dispatch() -> bool:
    # Entering the physical delay-slot word as an ordinary instruction executes
    # it and then reaches the sequential dispatch block.
    return True


def bypasses_compare(
    pc: int,
    *,
    image: str = IMAGE,
    generation: int = GENERATION,
    branch_pc: int = BRANCH_PC,
    dispatch_pc: int = DISPATCH_PC,
) -> bool:
    if image != IMAGE or generation != GENERATION:
        return False
    if pc == branch_pc:
        return True
    return dispatch_pc == branch_pc + 8 and pc == branch_pc + 4


def main() -> None:
    semantic_cases = []
    for index in [0, 2, 3, 0xFFFFFFFF]:
        semantic_cases.append(
            {
                "index": index,
                "normal_dispatch": normal_dispatch(index),
                "branch_entry_stale_zero": branch_entry_dispatch(0),
                "branch_entry_stale_one": branch_entry_dispatch(1),
                "delay_entry_dispatch": delay_entry_dispatch(),
            }
        )

    # The actual counterexamples: out-of-range indices cannot dispatch after the
    # compare, but do dispatch if execution starts at BEQ with stale t1=1 or at
    # the sequential delay-slot instruction.
    for case in semantic_cases:
        if case["index"] >= COUNT:
            assert case["normal_dispatch"] is False
            assert case["branch_entry_stale_one"] is True
            assert case["delay_entry_dispatch"] is True

    reachability_cases = [
        ("entry_branch", BRANCH_PC, IMAGE, 0, BRANCH_PC, DISPATCH_PC, True),
        ("direct_branch", BRANCH_PC, IMAGE, 0, BRANCH_PC, DISPATCH_PC, True),
        ("indirect_branch", BRANCH_PC, IMAGE, 0, BRANCH_PC, DISPATCH_PC, True),
        ("entry_delay_fallthrough", DELAY_PC, IMAGE, 0, BRANCH_PC, DISPATCH_PC, True),
        ("compare_entry", COMPARE_PC, IMAGE, 0, BRANCH_PC, DISPATCH_PC, False),
        ("other_generation_branch", BRANCH_PC, IMAGE, 1, BRANCH_PC, DISPATCH_PC, False),
        ("other_image_branch", BRANCH_PC, "other", 0, BRANCH_PC, DISPATCH_PC, False),
        ("unrelated_pc", 0x80000040, IMAGE, 0, BRANCH_PC, DISPATCH_PC, False),
        # If a selected taken branch targets somewhere non-sequential, entering
        # its delay slot alone does not recreate the taken transfer.
        ("remote_target_delay", DELAY_PC, IMAGE, 0, BRANCH_PC, 0x80000040, False),
    ]
    evaluated = []
    for name, pc, image, generation, branch_pc, dispatch_pc, expected in reachability_cases:
        actual = bypasses_compare(
            pc,
            image=image,
            generation=generation,
            branch_pc=branch_pc,
            dispatch_pc=dispatch_pc,
        )
        assert actual is expected, (name, actual, expected)
        evaluated.append({"name": name, "bypass": actual})

    report = {
        "count": COUNT,
        "semantic_cases": semantic_cases,
        "reachability_cases": evaluated,
        "counterexamples": sum(
            1
            for case in semantic_cases
            if case["index"] >= COUNT
            and not case["normal_dispatch"]
            and case["branch_entry_stale_one"]
        ),
    }
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    print(payload.decode())
    print(f"report_sha256={digest}")


if __name__ == "__main__":
    main()
