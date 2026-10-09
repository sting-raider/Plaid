#!/usr/bin/env python3
"""Adversarial Count/Compare producer model.

This is deliberately not a hardware oracle.  It captures only the source-level
contracts exercised by the exact pinned references so equality/value-only
histories can be falsified without pretending emulator agreement is hardware truth.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json

MOD = 1 << 32
MASK = MOD - 1


def delta32(count: int, compare: int) -> int:
    return (compare - count) & MASK


@dataclass
class TimerState:
    count: int
    compare: int
    pending: bool = False
    count_write_generation: int = 0
    compare_write_generation: int = 0

    def ares_compare_write(self, value: int) -> None:
        self.compare = value & MASK
        self.compare_write_generation += 1
        self.pending = False

    def ares_count_write(self, value: int) -> None:
        self.count = value & MASK
        self.count_write_generation += 1

    def ares_advance(self, ticks: int) -> None:
        # ares stores Count/Compare shifted left one bit; this external-register
        # model is equivalent for ordinary positive tick advances.  Equality at
        # the start is not an immediate match because ares requires remaining != 0.
        remaining = delta32(self.count, self.compare)
        if remaining and ticks >= remaining:
            self.pending = True
        self.count = (self.count + ticks) & MASK


def queued_deadline_after_count_write(old_count: int, compare: int, new_count: int) -> dict:
    """Contrast the exact source contracts after an MTC0 Count write.

    ares: Compare stays fixed while Count changes -> new modular delta.
    Mupen64Plus: translate_event_queue removes/recreates COMPARE_INT at the
      Compare register value -> same new modular delta, modulo its event-order shim.
    Gopher64: translate_events shifts every enabled event, including Compare,
      by new_count-old_count -> old relative delta is preserved.
    """
    old_delta = delta32(old_count, compare)
    return {
        "old_delta": old_delta,
        "ares_delta": delta32(new_count, compare),
        "mupen_delta": delta32(new_count, compare),
        "gopher_delta": old_delta,
    }


def main() -> int:
    rows = []

    # Ordinary crossing and wrap crossing.
    s = TimerState(100, 103)
    s.ares_advance(3)
    assert s.pending and s.count == 103
    rows.append({"case": "ordinary_cross", **asdict(s)})

    s = TimerState(0xFFFFFFFE, 1)
    s.ares_advance(3)
    assert s.pending and s.count == 1
    rows.append({"case": "wrap_cross", **asdict(s)})

    # Equality does not create an immediate pending edge in pinned ares.
    s = TimerState(100, 100)
    s.ares_compare_write(100)
    before = asdict(s)
    s.ares_advance(1)
    assert not s.pending and s.count == 101
    rows.append({"case": "equal_write_no_immediate", "before": before, "after": asdict(s)})

    # Same-value Compare write is still a distinct causal acknowledgement.
    s = TimerState(103, 103, pending=True, compare_write_generation=7)
    before = asdict(s)
    s.ares_compare_write(103)
    assert not s.pending
    assert s.compare == before["compare"]
    assert s.compare_write_generation == before["compare_write_generation"] + 1
    rows.append({"case": "same_value_compare_ack", "before": before, "after": asdict(s)})

    # Count writes do not acknowledge a latched timer in ares.
    s = TimerState(103, 103, pending=True, count_write_generation=4)
    s.ares_count_write(500)
    assert s.pending and s.count_write_generation == 5
    rows.append({"case": "count_write_not_ack", **asdict(s)})

    # Two Count-write counterexamples distinguish current-value reconstruction
    # from ordered producer history and expose the reference disagreement.
    forward = queued_deadline_after_count_write(100, 110, 108)
    assert forward == {"old_delta": 10, "ares_delta": 2, "mupen_delta": 2, "gopher_delta": 10}
    rows.append({"case": "count_forward_reference_disagreement", **forward})

    backward = queued_deadline_after_count_write(100, 105, 0)
    assert backward == {"old_delta": 5, "ares_delta": 105, "mupen_delta": 105, "gopher_delta": 5}
    rows.append({"case": "count_backward_reference_disagreement", **backward})

    # A value-only projection cannot distinguish the pre/post same-value Compare
    # histories even though only the latter clears pending and advances producer identity.
    pre = TimerState(103, 103, pending=True, compare_write_generation=9)
    post = TimerState(**asdict(pre))
    post.ares_compare_write(103)
    value_projection_pre = (pre.count, pre.compare)
    value_projection_post = (post.count, post.compare)
    assert value_projection_pre == value_projection_post
    assert (pre.pending, pre.compare_write_generation) != (post.pending, post.compare_write_generation)
    rows.append({
        "case": "value_only_history_collision",
        "value_projection": list(value_projection_pre),
        "pre": asdict(pre),
        "post": asdict(post),
    })

    payload = {
        "schema": "plaid-count-compare-model/v0",
        "purpose": "adversarial causal model; not hardware truth",
        "rows": rows,
    }
    encoded = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    digest = hashlib.sha256(encoded).hexdigest()
    print(encoded.decode(), end="")
    print(f"MODEL_SHA256 {digest}")
    print("PASS: ordered Compare-write identity is required; exact pinned references disagree on Count-write timer rescheduling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
