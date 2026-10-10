#!/usr/bin/env python3
"""Adversarial exception-root provenance model.

Backing storage generations and resident I-cache generations are intentionally
separate. The bad verifier under test attributes one selected root fetch to the
latest equal-valued backing generation and ignores resident ancestry.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "target/exception-handler-cache-compose/model-report.json"


@dataclass
class State:
    backing_gen: int = 0
    backing_value: int = 0
    next_fill: int = 0
    resident_fill: int | None = None
    resident_parent: int | None = None
    resident_value: int | None = None
    valid: bool = False


def apply(s: State, e: dict) -> None:
    kind = e["kind"]
    if kind == "write":
        s.backing_gen += 1
        if e.get("generation") != s.backing_gen:
            raise ValueError("write generation")
        s.backing_value = e["value"]
    elif kind == "invalidate":
        s.valid = False
    elif kind == "fill":
        s.next_fill += 1
        if e.get("fill") != s.next_fill:
            raise ValueError("fill generation")
        if e.get("parent") != s.backing_gen or e.get("value") != s.backing_value:
            raise ValueError("fill parent/payload")
        s.resident_fill = s.next_fill
        s.resident_parent = s.backing_gen
        s.resident_value = s.backing_value
        s.valid = True
    elif kind == "fetch":
        if not s.valid or s.resident_fill is None:
            raise ValueError("fetch without resident")
        if e.get("fill") != s.resident_fill or e.get("parent") != s.resident_parent:
            raise ValueError("fetch ancestry")
        if e.get("value") != s.resident_value:
            raise ValueError("fetch payload")
    else:
        raise ValueError("unknown event")


def strict(events: list[dict]) -> bool:
    s = State()
    try:
        for e in events:
            apply(s, e)
    except (KeyError, TypeError, ValueError):
        return False
    return True


def naive_last_fetch_accepts(events: list[dict]) -> bool:
    """Unsoundly judge only the selected final fetch from current backing bits."""
    generation = 0
    value = 0
    last = None
    for e in events:
        if e.get("kind") == "write":
            generation += 1
            value = e["value"]
        elif e.get("kind") == "fetch":
            last = e
    return bool(
        last
        and last.get("value") == value
        and last.get("claimed_latest_parent", generation) == generation
    )


def write(events: list[dict], s: State, value: int) -> None:
    e = {"kind": "write", "generation": s.backing_gen + 1, "value": value}
    events.append(e)
    apply(s, e)


def invalidate(events: list[dict], s: State) -> None:
    e = {"kind": "invalidate"}
    events.append(e)
    apply(s, e)


def fill(events: list[dict], s: State) -> None:
    e = {"kind": "fill", "fill": s.next_fill + 1, "parent": s.backing_gen, "value": s.backing_value}
    events.append(e)
    apply(s, e)


def fetch(events: list[dict], s: State) -> dict:
    if not s.valid:
        fill(events, s)
    e = {
        "kind": "fetch",
        "fill": s.resident_fill,
        "parent": s.resident_parent,
        "value": s.resident_value,
        "latest_backing_generation": s.backing_gen,
        "latest_backing_value": s.backing_value,
    }
    events.append(e)
    apply(s, e)
    return e


def fixed() -> dict:
    # Same-value write after fill: bits match latest backing, ancestry does not.
    events: list[dict] = []
    s = State()
    write(events, s, 0x24100022)
    first = fetch(events, s)
    write(events, s, 0x24100022)
    stale = fetch(events, s)
    assert first["parent"] == stale["parent"] == 1
    assert stale["latest_backing_generation"] == 2
    forged = copy.deepcopy(events)
    forged[-1]["parent"] = 2
    forged[-1]["claimed_latest_parent"] = 2
    assert strict(events) and not strict(forged) and naive_last_fetch_accepts(forged)

    # Changed backing: current bytes cannot even predict the resident instruction.
    changed: list[dict] = []
    t = State()
    write(changed, t, 0x24100011)
    fetch(changed, t)
    write(changed, t, 0x24100022)
    changed_fetch = fetch(changed, t)
    assert changed_fetch["value"] != changed_fetch["latest_backing_value"]
    assert strict(changed) and not naive_last_fetch_accepts(changed)

    # Layout after the first fetch is write, fill, fetch. Delete or reorder the
    # fill, or invalidate before reusing that fetch receipt, and strict replay fails.
    missing_fill = [copy.deepcopy(events[0]), copy.deepcopy(events[2])]
    assert not strict(missing_fill)
    invalidated = copy.deepcopy(events[:3]) + [{"kind": "invalidate"}, copy.deepcopy(events[2])]
    assert not strict(invalidated)
    reordered = [copy.deepcopy(events[0]), copy.deepcopy(events[2]), copy.deepcopy(events[1])]
    assert not strict(reordered)

    # Equal-payload fills are distinct resident generations.
    decoy: list[dict] = []
    d = State()
    write(decoy, d, 7)
    a = fetch(decoy, d)
    invalidate(decoy, d)
    b = fetch(decoy, d)
    assert a["value"] == b["value"] and a["fill"] != b["fill"]
    forged_decoy = copy.deepcopy(decoy)
    forged_decoy[-1]["fill"] = a["fill"]
    assert not strict(forged_decoy)

    return {
        "same_value_latest_backing_false_attribution": True,
        "changed_value_current_backing_prediction_fails": True,
        "missing_fill_rejected": True,
        "invalidated_resident_rejected": True,
        "reordered_fill_rejected": True,
        "equal_payload_fill_decoy_rejected": True,
    }


def fuzz(seed: int = 0x504C414944, histories: int = 20_000, actions: int = 32) -> dict:
    rng = random.Random(seed)
    same_value_false = changed_stale = fetches = fills = writes = 0
    for _ in range(histories):
        events: list[dict] = []
        s = State()
        write(events, s, rng.randrange(4)); writes += 1
        fetch(events, s); fetches += 1; fills += 1
        for _ in range(actions):
            choice = rng.randrange(100)
            if choice < 46:
                write(events, s, rng.randrange(4)); writes += 1
            elif choice < 62:
                invalidate(events, s)
            else:
                before = s.next_fill
                item = fetch(events, s)
                fetches += 1; fills += s.next_fill - before
                if item["parent"] != item["latest_backing_generation"]:
                    if item["value"] == item["latest_backing_value"]:
                        same_value_false += 1
                        forged = copy.deepcopy(events)
                        forged[-1]["parent"] = item["latest_backing_generation"]
                        forged[-1]["claimed_latest_parent"] = item["latest_backing_generation"]
                        if strict(forged) or not naive_last_fetch_accepts(forged):
                            raise AssertionError("latest-backing forgery test failed")
                    else:
                        changed_stale += 1
        if not strict(events):
            raise AssertionError("valid generated history rejected")
    return {
        "seed": seed,
        "histories": histories,
        "actions_per_history": actions,
        "writes": writes,
        "fills": fills,
        "fetches": fetches,
        "same_value_latest_backing_false_attributions": same_value_false,
        "changed_value_stale_fetches": changed_stale,
    }


def main() -> int:
    report = {"schema": 1, "fixed": fixed(), "fuzz": fuzz()}
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    report["sha256"] = digest
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        "PASS MODEL_SHA256=" + digest
        + f" same_value_false_attributions={report['fuzz']['same_value_latest_backing_false_attributions']}"
        + f" changed_stale={report['fuzz']['changed_value_stale_fetches']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
