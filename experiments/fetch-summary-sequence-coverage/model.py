#!/usr/bin/env python3
"""Deterministic model for the raw-fetch summary coverage invariant."""
from __future__ import annotations

from hashlib import sha256
from itertools import product
import json


def summarize(history: tuple[str, ...]) -> tuple[tuple[str, int, int, int], ...]:
    out = []
    for symbol in sorted(set(history)):
        positions = [i for i, value in enumerate(history) if value == symbol]
        out.append((symbol, positions[0], positions[-1], len(positions)))
    return tuple(out)


def legacy_accepts(count: int, summaries: tuple[tuple[str, int, int, int], ...]) -> bool:
    if len({symbol for symbol, *_ in summaries}) != len(summaries):
        return False
    endpoints: dict[int, str] = {}
    total = 0
    for symbol, first, last, occurrences in summaries:
        if first > last or last >= count or occurrences == 0:
            return False
        if occurrences > last - first + 1:
            return False
        if occurrences == 1 and first != last:
            return False
        for endpoint in (first, last):
            prior = endpoints.setdefault(endpoint, symbol)
            if prior != symbol:
                return False
        total += occurrences
    return total == count


def coverage_accepts(count: int, summaries: tuple[tuple[str, int, int, int], ...]) -> bool:
    if not legacy_accepts(count, summaries):
        return False
    intervals = sorted((first, last) for _, first, last, _ in summaries)
    covered_until = 0
    for start, end in intervals:
        if start > covered_until:
            return False
        if end >= covered_until:
            covered_until = end + 1
    return covered_until == count


def main() -> None:
    tail_hole = (("A", 0, 4, 4), ("B", 1, 3, 2))
    internal_hole = (
        ("A", 0, 3, 4),
        ("B", 1, 2, 2),
        ("C", 5, 7, 2),
    )
    full_coverage_unrealizable = (
        ("A", 0, 2, 3),
        ("B", 1, 3, 2),
        ("C", 4, 6, 2),
    )

    assert legacy_accepts(6, tail_hole)
    assert not coverage_accepts(6, tail_hole)
    assert not any(summarize(history) == tail_hole for history in product("AB", repeat=6))

    assert legacy_accepts(8, internal_hole)
    assert not coverage_accepts(8, internal_hole)

    # Coverage is deliberately only a necessary invariant. This set covers all
    # seven sequence positions and passes the candidate predicate, yet no exact
    # history exists: A's count forces sequence 1 to be A while B requires it as
    # B's first occurrence. Keep this counterexample so the bounded fix is not
    # later mistaken for a global summary-realizability proof.
    assert legacy_accepts(7, full_coverage_unrealizable)
    assert coverage_accepts(7, full_coverage_unrealizable)
    assert not any(
        summarize(history) == full_coverage_unrealizable
        for history in product("ABC", repeat=7)
    )

    forged_family = []
    for count in range(5, 13):
        forged = (("A", 0, count - 2, count - 2), ("B", 1, count - 3, 2))
        assert legacy_accepts(count, forged)
        assert not coverage_accepts(count, forged)
        forged_family.append(count)

    genuine_histories = 0
    for count in range(0, 8):
        for history in product("ABC", repeat=count):
            summaries = summarize(history)
            assert legacy_accepts(count, summaries)
            assert coverage_accepts(count, summaries)
            genuine_histories += 1

    result = {
        "tail_hole_legacy_accepts": True,
        "tail_hole_coverage_accepts": False,
        "tail_hole_concrete_histories": 0,
        "internal_hole_legacy_accepts": True,
        "internal_hole_coverage_accepts": False,
        "full_coverage_unrealizable_legacy_accepts": True,
        "full_coverage_unrealizable_coverage_accepts": True,
        "full_coverage_unrealizable_concrete_histories": 0,
        "forged_tail_hole_counts": forged_family,
        "genuine_histories_checked": genuine_histories,
    }
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps(result, sort_keys=True))
    print(f"sha256={sha256(encoded).hexdigest()}")


if __name__ == "__main__":
    main()
