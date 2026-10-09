#!/usr/bin/env python3
"""Adversarial VR4300 Watch-root certificate model.

This is a project-owned reducer, not an emulator. It encodes only the bounded
Watch facts needed by the research note and deliberately keeps reset-unknown
state distinct from an explicitly disabled WatchLo generation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random

WATCH_EXCCODE = 23
NORMAL_BASE = 0xFFFFFFFF80000000
BOOT_BASE = 0xFFFFFFFFBFC00200
GENERAL_OFFSET = 0x180


@dataclass(frozen=True)
class Config:
    generation: int
    known: bool
    watchlo: int | None

    @property
    def read(self) -> bool | None:
        return None if self.watchlo is None else bool(self.watchlo & 2)

    @property
    def write(self) -> bool | None:
        return None if self.watchlo is None else bool(self.watchlo & 1)

    @property
    def block(self) -> int | None:
        return None if self.watchlo is None else self.watchlo & 0xFFFFFFF8


@dataclass(frozen=True)
class State:
    config: Config
    bev: int


def reset(bev: int = 1) -> State:
    # VR4300 User's Manual section 6.4.17 says WatchLo/WatchHi are undefined
    # after reset. Do not silently substitute an emulator's zero-filled state.
    return State(Config(0, False, None), bev)


def mtc0_watchlo(state: State, value: int) -> State:
    # Same-value writes are still distinct register generations/history events.
    return State(Config(state.config.generation + 1, True, value & 0xFFFFFFFB), state.bev)


def set_bev(state: State, bev: int) -> State:
    assert bev in (0, 1)
    return State(state.config, bev)


def vector(bev: int) -> int:
    return (BOOT_BASE if bev else NORMAL_BASE) + GENERAL_OFFSET


def access(state: State, kind: str, paddr: int, *, exl: bool = False,
           higher_priority_exception: bool = False) -> dict:
    if kind == "cache":
        return {"outcome": "normal", "reason": "cache_never_watch", "generation": state.config.generation}
    if kind not in {"load", "store"}:
        raise ValueError(kind)
    if higher_priority_exception:
        return {"outcome": "higher_priority", "generation": state.config.generation}
    if not state.config.known:
        return {"outcome": "unknown", "reason": "reset_watch_state_unknown", "generation": state.config.generation}

    enabled = state.config.read if kind == "load" else state.config.write
    matches = (paddr & 0xFFFFFFF8) == state.config.block
    if not enabled or not matches:
        return {"outcome": "normal", "generation": state.config.generation}
    if exl:
        return {"outcome": "postponed", "generation": state.config.generation}
    return {
        "outcome": "watch",
        "generation": state.config.generation,
        "exc_code": WATCH_EXCCODE,
        "vector": vector(state.bev),
    }


def deterministic_cases() -> list[dict]:
    rows: list[dict] = []
    s = reset()
    rows.append({"name": "reset_unknown_load", **access(s, "load", 0x1000)})
    s = mtc0_watchlo(s, 0x1000)  # explicit R/W clear
    rows.append({"name": "explicit_disable", **access(s, "load", 0x1000)})
    s = mtc0_watchlo(s, 0x1002)
    rows.append({"name": "read_match_lane0_bev1", **access(s, "load", 0x1000)})
    rows.append({"name": "read_match_lane4_bev1", **access(s, "load", 0x1004)})
    rows.append({"name": "read_nonmatch_next_block", **access(s, "load", 0x1008)})
    rows.append({"name": "read_match_exl_postponed", **access(s, "load", 0x1000, exl=True)})
    rows.append({"name": "cache_same_address", **access(s, "cache", 0x1000)})
    rows.append({"name": "higher_priority_preempts", **access(s, "load", 0x1000, higher_priority_exception=True)})
    s = set_bev(s, 0)
    rows.append({"name": "read_match_bev0", **access(s, "load", 0x1000)})
    s = mtc0_watchlo(s, 0x1001)
    rows.append({"name": "write_match", **access(s, "store", 0x1000)})
    rows.append({"name": "write_only_does_not_trap_load", **access(s, "load", 0x1000)})

    # Equal payload, new generation: equality cannot erase the operation.
    before = s.config.generation
    s2 = mtc0_watchlo(s, 0x1001)
    assert s2.config.generation == before + 1 and s2.config.watchlo == s.config.watchlo
    rows.append({"name": "same_value_rewrite_new_generation", **access(s2, "store", 0x1000)})
    return rows


def fuzz(seed: int = 0x57415443, count: int = 100_000) -> dict:
    rng = random.Random(seed)
    outcomes = {k: 0 for k in ("unknown", "normal", "postponed", "watch", "higher_priority")}
    same_value_rewrites = 0
    state = reset()
    last_value: int | None = None
    for _ in range(count):
        op = rng.randrange(7)
        if op <= 1:
            # Deliberately generate repeated WatchLo values often.
            if last_value is not None and rng.randrange(4) == 0:
                value = last_value
                same_value_rewrites += 1
            else:
                value = (rng.randrange(0, 1 << 20) << 3) | rng.randrange(4)
                value &= 0xFFFFFFFF
            old_gen = state.config.generation
            state = mtc0_watchlo(state, value)
            assert state.config.generation == old_gen + 1
            last_value = value & 0xFFFFFFFB
        elif op == 2:
            state = set_bev(state, rng.randrange(2))
        else:
            kind = ("load", "store", "cache")[rng.randrange(3)]
            paddr = rng.randrange(0, 1 << 20) << 2
            row = access(
                state,
                kind,
                paddr,
                exl=bool(rng.randrange(8) == 0),
                higher_priority_exception=bool(rng.randrange(32) == 0),
            )
            outcomes[row["outcome"]] += 1
    return {"seed": seed, "operations": count, "same_value_rewrites": same_value_rewrites, "outcomes": outcomes}


def forged_histories_rejected() -> list[str]:
    rejected: list[str] = []
    # Each tuple is (name, actual history result, forged claimed result).
    tests = []
    unknown = reset()
    tests.append(("reset_unknown_claimed_disabled", access(unknown, "load", 0x1000)["outcome"], "normal"))

    enabled = mtc0_watchlo(reset(), 0x1002)
    tests.append(("matching_read_claimed_normal", access(enabled, "load", 0x1000)["outcome"], "normal"))
    tests.append(("low_lane_alias_claimed_nonmatch", access(enabled, "load", 0x1004)["outcome"], "normal"))
    tests.append(("cache_claimed_watch", access(enabled, "cache", 0x1000)["outcome"], "watch"))
    tests.append(("exl_postpone_claimed_normal", access(enabled, "load", 0x1000, exl=True)["outcome"], "normal"))

    bev0 = set_bev(enabled, 0)
    actual = access(bev0, "load", 0x1000)
    if actual.get("vector") != vector(1):
        rejected.append("wrong_bev_vector")

    same = mtc0_watchlo(enabled, enabled.config.watchlo or 0)
    if same.config.generation != enabled.config.generation:
        rejected.append("same_value_generation_coalesced")

    for name, actual_outcome, forged in tests:
        if actual_outcome != forged:
            rejected.append(name)
    assert len(rejected) == 7, rejected
    return rejected


def main() -> int:
    rows = deterministic_cases()
    expected = {
        "reset_unknown_load": "unknown",
        "explicit_disable": "normal",
        "read_match_lane0_bev1": "watch",
        "read_match_lane4_bev1": "watch",
        "read_nonmatch_next_block": "normal",
        "read_match_exl_postponed": "postponed",
        "cache_same_address": "normal",
        "higher_priority_preempts": "higher_priority",
        "read_match_bev0": "watch",
        "write_match": "watch",
        "write_only_does_not_trap_load": "normal",
        "same_value_rewrite_new_generation": "watch",
    }
    assert {r["name"]: r["outcome"] for r in rows} == expected
    fuzz_report = fuzz()
    rejected = forged_histories_rejected()
    report = {"cases": rows, "fuzz": fuzz_report, "forgeries_rejected": rejected}
    payload = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"MODEL_SHA256 {digest}")
    print(f"PASS: {len(rows)} deterministic cases, {fuzz_report['operations']} randomized operations, {len(rejected)} forged certificates rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
