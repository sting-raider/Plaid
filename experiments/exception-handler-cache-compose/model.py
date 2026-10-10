#!/usr/bin/env python3
"""Adversarial model for exception-root handler byte provenance.

This deliberately separates backing storage generations from resident I-cache fill
identity.  It tests the tempting but unsound rule "vector PC + current backing
bytes identifies the handler that executed".
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
    backing_generation: int = 0
    backing_value: int = 0
    next_fill: int = 0
    resident_fill: int | None = None
    resident_parent: int | None = None
    resident_value: int | None = None
    valid: bool = False


def apply(state: State, event: dict) -> None:
    kind = event["kind"]
    if kind == "write":
        state.backing_generation += 1
        state.backing_value = event["value"]
        if event.get("generation") != state.backing_generation:
            raise ValueError("wrong write generation")
        return
    if kind == "invalidate":
        state.valid = False
        return
    if kind == "fill":
        state.next_fill += 1
        if event.get("fill") != state.next_fill:
            raise ValueError("wrong fill generation")
        if event.get("parent") != state.backing_generation:
            raise ValueError("fill parent is not current backing generation")
        if event.get("value") != state.backing_value:
            raise ValueError("fill payload differs from backing")
        state.resident_fill = state.next_fill
        state.resident_parent = state.backing_generation
        state.resident_value = state.backing_value
        state.valid = True
        return
    if kind == "fetch":
        if not state.valid or state.resident_fill is None:
            raise ValueError("fetch without valid resident line")
        if event.get("fill") != state.resident_fill:
            raise ValueError("fetch references wrong resident fill")
        if event.get("parent") != state.resident_parent:
            raise ValueError("fetch references wrong backing parent")
        if event.get("value") != state.resident_value:
            raise ValueError("fetch payload differs from resident line")
        return
    raise ValueError(f"unknown event {kind}")


def strict_verify(events: list[dict]) -> bool:
    state = State()
    try:
        for event in events:
            apply(state, event)
    except (KeyError, TypeError, ValueError):
        return False
    return True


def value_only_latest_backing_verify(events: list[dict]) -> bool:
    """A deliberately unsound verifier that ignores fill/parent identity."""
    generation = 0
    value = 0
    for event in events:
        kind = event.get("kind")
        if kind == "write":
            generation += 1
            value = event["value"]
        elif kind == "fetch":
            if event.get("value") != value:
                return False
            # This is the bug under attack: matching current bits are promoted to
            # current-backing provenance regardless of resident cache ancestry.
            if event.get("claimed_latest_parent", generation) != generation:
                return False
    return True


def write(events: list[dict], state: State, value: int) -> None:
    events.append({"kind": "write", "generation": state.backing_generation + 1, "value": value})
    apply(state, events[-1])


def invalidate(events: list[dict], state: State) -> None:
    events.append({"kind": "invalidate"})
    apply(state, events[-1])


def fill(events: list[dict], state: State) -> None:
    events.append({
        "kind": "fill",
        "fill": state.next_fill + 1,
        "parent": state.backing_generation,
        "value": state.backing_value,
    })
    apply(state, events[-1])


def fetch(events: list[dict], state: State) -> dict:
    if not state.valid:
        fill(events, state)
    event = {
        "kind": "fetch",
        "fill": state.resident_fill,
        "parent": state.resident_parent,
        "value": state.resident_value,
        "latest_backing_generation": state.backing_generation,
        "latest_backing_value": state.backing_value,
    }
    events.append(event)
    apply(state, event)
    return event


def fixed_adversaries() -> dict:
    # Same-value storage generation: every visible bit is identical but ancestry is not.
    events: list[dict] = []
    state = State()
    write(events, state, 0x24100022)
    first = fetch(events, state)
    write(events, state, 0x24100022)
    stale = fetch(events, state)
    assert first["parent"] == stale["parent"] == 1
    assert stale["latest_backing_generation"] == 2
    assert stale["value"] == stale["latest_backing_value"]
    assert strict_verify(events)

    forged_latest = copy.deepcopy(events)
    forged_latest[-1]["parent"] = 2
    forged_latest[-1]["claimed_latest_parent"] = 2
    assert not strict_verify(forged_latest)
    assert value_only_latest_backing_verify(forged_latest)

    # Changed backing while resident is valid: current RAM does not even predict bits.
    changed: list[dict] = []
    changed_state = State()
    write(changed, changed_state, 0x24100011)
    fetch(changed, changed_state)
    write(changed, changed_state, 0x24100022)
    changed_fetch = fetch(changed, changed_state)
    assert changed_fetch["value"] != changed_fetch["latest_backing_value"]
    assert strict_verify(changed)
    assert not value_only_latest_backing_verify(changed)

    # Explicit invalidation forbids reuse of the old resident generation.
    invalidated = copy.deepcopy(events[:2])
    invalidated.append({"kind": "invalidate"})
    invalidated.append(copy.deepcopy(events[1]))
    assert not strict_verify(invalidated)

    # A fetch cannot invent a resident generation if its fill record was deleted.
    missing_fill = [events[0], copy.deepcopy(events[1])]
    assert not strict_verify(missing_fill)

    # A fill cannot be moved after the fetch it supposedly explains.
    reordered = [events[0], copy.deepcopy(events[1]), copy.deepcopy(events[1])]
    reordered[1]["kind"] = "fetch"
    reordered[2]["kind"] = "fill"
    assert not strict_verify(reordered)

    # Equal-payload decoy fill generation is not interchangeable with the resident one.
    decoy: list[dict] = []
    decoy_state = State()
    write(decoy, decoy_state, 7)
    a = fetch(decoy, decoy_state)
    invalidate(decoy, decoy_state)
    b = fetch(decoy, decoy_state)
    assert a["value"] == b["value"] and a["fill"] != b["fill"]
    forged_decoy = copy.deepcopy(decoy)
    forged_decoy[-1]["fill"] = a["fill"]
    assert not strict_verify(forged_decoy)

    return {
        "same_value_latest_backing_false_attribution": True,
        "changed_value_current_backing_prediction_fails": True,
        "invalidated_resident_forgery_rejected": True,
        "missing_fill_forgery_rejected": True,
        "reordered_fill_forgery_rejected": True,
        "equal_payload_fill_decoy_rejected": True,
    }


def fuzz(seed: int = 0x504C414944, histories: int = 20_000, actions: int = 32) -> dict:
    rng = random.Random(seed)
    same_value_false_attributions = 0
    changed_value_stale_fetches = 0
    fetches = 0
    fills = 0
    writes = 0
    for _ in range(histories):
        events: list[dict] = []
        state = State()
        write(events, state, rng.randrange(4))
        writes += 1
        fetch(events, state)
        fetches += 1
        fills += 1
        for _ in range(actions):
            choice = rng.randrange(100)
            if choice < 46:
                # Small value alphabet intentionally produces equal-payload fresh generations.
                write(events, state, rng.randrange(4))
                writes += 1
            elif choice < 62:
                invalidate(events, state)
            else:
                before_fills = state.next_fill
                item = fetch(events, state)
                fetches += 1
                fills += state.next_fill - before_fills
                if item["parent"] != item["latest_backing_generation"]:
                    if item["value"] == item["latest_backing_value"]:
                        same_value_false_attributions += 1
                        forged = copy.deepcopy(events)
                        forged[-1]["parent"] = item["latest_backing_generation"]
                        forged[-1]["claimed_latest_parent"] = item["latest_backing_generation"]
                        if strict_verify(forged):
                            raise AssertionError("strict verifier accepted forged latest-backing parent")
                        if not value_only_latest_backing_verify(forged):
                            raise AssertionError("value-only verifier failed to demonstrate false acceptance")
                    else:
                        changed_value_stale_fetches += 1
        if not strict_verify(events):
            raise AssertionError("strict verifier rejected generated valid history")
    return {
        "seed": seed,
        "histories": histories,
        "actions_per_history": actions,
        "writes": writes,
        "fills": fills,
        "fetches": fetches,
        "same_value_latest_backing_false_attributions": same_value_false_attributions,
        "changed_value_stale_fetches": changed_value_stale_fetches,
    }


def main() -> int:
    report = {
        "schema": 1,
        "fixed": fixed_adversaries(),
        "fuzz": fuzz(),
    }
    raw = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    report["sha256"] = digest
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"PASS MODEL_SHA256={digest} same_value_false_attributions={report['fuzz']['same_value_latest_backing_false_attributions']} changed_stale={report['fuzz']['changed_value_stale_fetches']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
