#!/usr/bin/env python3
"""Falsify/validate an interval-quota sweep for finite fetch summaries.

This model deliberately ignores fetch values/provenance. It asks only whether a
set of exact (first_seq, last_seq, occurrences) facts can describe any concrete
sequence of the declared length.
"""

from __future__ import annotations

from functools import lru_cache
import hashlib
import itertools
import json
import random

SEED = 0x4653524C


def structurally_valid(n: int, summaries: tuple[tuple[int, int, int], ...]) -> bool:
    if n == 0:
        return not summaries
    if sum(count for _, _, count in summaries) != n:
        return False
    owners: dict[int, int] = {}
    for index, (first, last, count) in enumerate(summaries):
        if not (0 <= first <= last < n):
            return False
        if count <= 0 or count > last - first + 1:
            return False
        if count == 1 and first != last:
            return False
        for seq in {first, last}:
            old = owners.setdefault(seq, index)
            if old != index:
                return False
    return True


def exact_oracle(n: int, summaries: tuple[tuple[int, int, int], ...]) -> bool:
    """Independent exponential oracle for small candidate sets."""
    if not structurally_valid(n, summaries):
        return False
    if n == 0:
        return True

    owners: dict[int, int] = {}
    remaining: list[int] = []
    for index, (first, last, count) in enumerate(summaries):
        for seq in {first, last}:
            owners[seq] = index
        remaining.append(count - (1 if first == last else 2))

    free = tuple(seq for seq in range(n) if seq not in owners)

    @lru_cache(maxsize=None)
    def assign(offset: int, quotas: tuple[int, ...]) -> bool:
        if offset == len(free):
            return all(quota == 0 for quota in quotas)
        seq = free[offset]
        for index, (first, last, _) in enumerate(summaries):
            if quotas[index] == 0 or not (first < seq < last):
                continue
            updated = list(quotas)
            updated[index] -= 1
            if assign(offset + 1, tuple(updated)):
                return True
        return False

    return assign(0, tuple(remaining))


def sweep(n: int, summaries: tuple[tuple[int, int, int], ...]) -> bool:
    """O(summary_count log summary_count) earliest-deadline quota sweep."""
    if not structurally_valid(n, summaries):
        return False
    if n == 0:
        return True

    endpoints: dict[int, int] = {}
    interior: list[int] = []
    for index, (first, last, count) in enumerate(summaries):
        endpoints[first] = index
        endpoints[last] = index
        interior.append(count - (1 if first == last else 2))

    # last_seq -> remaining interior occurrences. Endpoint uniqueness makes each
    # deadline unique, so a tiny dict is enough for the model.
    active: dict[int, int] = {}
    previous: int | None = None

    for seq in sorted(endpoints):
        start = 0 if previous is None else previous + 1
        slots = seq - start
        while slots:
            if not active:
                return False
            deadline = min(active)
            if deadline < seq:
                return False
            used = min(slots, active[deadline])
            slots -= used
            active[deadline] -= used
            if active[deadline] == 0:
                del active[deadline]

        owner = endpoints[seq]
        first, last, _ = summaries[owner]
        # A summary reaching last_seq with unmet interior quota is impossible.
        if last == seq and seq in active:
            return False
        if first == seq and last > seq and interior[owner]:
            if last in active:
                return False
            active[last] = interior[owner]
        previous = seq

    # The final concrete event must be some summary's exact last occurrence.
    return previous is not None and previous + 1 == n and not active


def summarize(history: tuple[int, ...]) -> tuple[tuple[int, int, int], ...]:
    positions: dict[int, list[int]] = {}
    for seq, value in enumerate(history):
        positions.setdefault(value, []).append(seq)
    return tuple(
        sorted((seqs[0], seqs[-1], len(seqs)) for seqs in positions.values())
    )


def exhaustive_genuine_histories() -> tuple[int, int]:
    histories = 0
    unique_summaries: set[tuple[int, tuple[tuple[int, int, int], ...]]] = set()
    for n in range(0, 8):
        if n == 0:
            candidates = [()]
        else:
            candidates = itertools.product(range(4), repeat=n)
        for history in candidates:
            histories += 1
            summaries = summarize(tuple(history))
            unique_summaries.add((n, summaries))
            if not sweep(n, summaries):
                raise AssertionError(("genuine history rejected", history, summaries))
            if not exact_oracle(n, summaries):
                raise AssertionError(("oracle rejected genuine history", history, summaries))
    return histories, len(unique_summaries)


def random_candidate(rng: random.Random) -> tuple[int, tuple[tuple[int, int, int], ...]] | None:
    n = rng.randint(4, 12)
    max_summaries = min(4, n // 2)
    count = rng.randint(1, max_summaries)
    endpoints = rng.sample(range(n), 2 * count)
    rng.shuffle(endpoints)
    intervals = [tuple(sorted(endpoints[2 * i : 2 * i + 2])) for i in range(count)]
    capacities = [last - first - 1 for first, last in intervals]
    extra = n - 2 * count
    if extra < 0 or extra > sum(capacities):
        return None
    additions = [0] * count
    while extra:
        available = [i for i, cap in enumerate(capacities) if additions[i] < cap]
        if not available:
            return None
        index = rng.choice(available)
        additions[index] += 1
        extra -= 1
    summaries = tuple(
        sorted(
            (first, last, 2 + additions[i])
            for i, (first, last) in enumerate(intervals)
        )
    )
    return n, summaries


def randomized_falsification(trials: int = 20_000) -> tuple[int, int, int]:
    rng = random.Random(SEED)
    compared = 0
    feasible = 0
    impossible = 0
    while compared < trials:
        candidate = random_candidate(rng)
        if candidate is None:
            continue
        n, summaries = candidate
        oracle = exact_oracle(n, summaries)
        candidate_result = sweep(n, summaries)
        if oracle != candidate_result:
            raise AssertionError(("sweep/oracle disagreement", n, summaries, oracle, candidate_result))
        compared += 1
        feasible += int(oracle)
        impossible += int(not oracle)
    return compared, feasible, impossible


def large_sparse_probe(summary_count: int = 100_000, block: int = 10) -> tuple[int, int]:
    n = summary_count * block
    summaries = tuple(
        (index * block, index * block + block - 1, block)
        for index in range(summary_count)
    )
    if not sweep(n, summaries):
        raise AssertionError("large valid summary set rejected")
    return n, len(summaries)


def main() -> None:
    impossible = ((0, 2, 3), (1, 3, 2), (4, 6, 2))
    concrete = ((0, 3, 2), (1, 2, 2), (4, 6, 3))
    if exact_oracle(7, impossible) or sweep(7, impossible):
        raise AssertionError("published impossible counterexample was accepted")
    if not exact_oracle(7, concrete) or not sweep(7, concrete):
        raise AssertionError("concrete A,B,B,A,C,C,C control was rejected")

    histories, unique = exhaustive_genuine_histories()
    trials, feasible, rejected = randomized_falsification()
    large_events, large_summaries = large_sparse_probe()

    report = {
        "seed": SEED,
        "fixed_impossible_rejected": True,
        "fixed_concrete_accepted": True,
        "exhaustive_histories": histories,
        "unique_genuine_summary_sets": unique,
        "random_oracle_comparisons": trials,
        "random_feasible": feasible,
        "random_impossible": rejected,
        "large_probe_events": large_events,
        "large_probe_summaries": large_summaries,
        "algorithm": "fixed endpoints + earliest-deadline interior quota sweep",
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["semantic_sha256"] = hashlib.sha256(canonical).hexdigest()
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
