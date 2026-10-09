#!/usr/bin/env python3
"""Deterministic selected-edge model for the pointer-table guard delay-slot bug.

This does not replace the Rust regression test. It records the proof obligation:
only a delay slot that executes on the selected guard edge may invalidate that edge.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "crates/plaid-core/src/tables.rs"
DISCOVERY = ROOT / "crates/plaid-core/src/discovery.rs"


def source_guards() -> None:
    tables = TABLES.read_text(encoding="utf-8")
    discovery = DISCOVERY.read_text(encoding="utf-8")
    assert 'if edge.delay_slot != DelaySlot::None {' in tables
    assert 'instruction.is_trap()' in tables
    assert 'matches!(instruction.opcode_name(), "syscall" | "break" | "eret")' in tables
    assert 'kind: "unsupported_delay_slot".into()' in discovery
    assert 'DelaySlot::None' in discovery
    assert 'DelaySlot::TakenOnly' in discovery
    assert 'DelaySlot::Always' in discovery


def current_pre_fix_accept(*, selected_edge_executes_slot: bool, exceptional: bool) -> bool:
    # Pre-fix table logic checked validity/control/index clobber, but not exceptionality.
    del exceptional
    if not selected_edge_executes_slot:
        return True
    return True


def corrected_accept(*, selected_edge_executes_slot: bool, exceptional: bool) -> bool:
    if not selected_edge_executes_slot:
        return True
    return not exceptional


def main() -> None:
    source_guards()
    cases = [
        ("beq_nop", True, False, True),
        ("beq_teq", True, True, False),
        ("beq_syscall", True, True, False),
        ("beq_break", True, True, False),
        ("beq_eret", True, True, False),
        # BEQL selected fallthrough is not-taken, so its physical delay slot is annulled.
        ("beql_teq_annulled", False, True, True),
    ]
    rows = []
    for name, executes, exceptional, expected in cases:
        before = current_pre_fix_accept(
            selected_edge_executes_slot=executes, exceptional=exceptional
        )
        after = corrected_accept(
            selected_edge_executes_slot=executes, exceptional=exceptional
        )
        assert after == expected, name
        rows.append(
            {
                "case": name,
                "pre_fix_accept": before,
                "post_fix_accept": after,
                "selected_edge_executes_slot": executes,
                "exceptional": exceptional,
            }
        )
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    print(payload)
    print("payload_sha256=" + hashlib.sha256(payload.encode()).hexdigest())


if __name__ == "__main__":
    main()
