#!/usr/bin/env python3
"""Executable adversarial model for reset-button HW2 -> NMI producer chronology.

This deliberately models only the source-backed queue/latch properties needed by
Plaid's provenance proof. It does not claim the emulator delays are hardware truth.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from pathlib import Path

HW2 = "HW2"
NMI = "NMI"
MUPEN_NMI_DELAY = 50_000_000
GOPHER_NMI_DELAY = 93_750_000  # symbolic clock_rate used by the model; exact value is not the invariant.


@dataclass(frozen=True)
class Event:
    kind: str
    count: int
    token: int
    request: int | None
    epoch: int


class MupenQueue:
    """Relevant semantics from pinned add_interrupt_event/remove/load queue code."""

    def __init__(self, count: int = 0, epoch: int = 0) -> None:
        self.count = count
        self.epoch = epoch
        self.next_token = 1
        self.events: list[Event] = []

    def add(self, kind: str, delay: int, request: int | None) -> Event:
        event = Event(kind, self.count + delay, self.next_token, request, self.epoch)
        self.next_token += 1
        # The pinned queue keeps all duplicates. Equal-count insertion is stable
        # behind existing equal-count rows for the non-wraparound histories here.
        pos = 0
        while pos < len(self.events) and self.events[pos].count <= event.count:
            pos += 1
        self.events.insert(pos, event)
        return event

    def soft_reset(self, request: int) -> tuple[Event, Event]:
        return self.add(HW2, 0, request), self.add(NMI, MUPEN_NMI_DELAY, request)

    def dispatch(self) -> Event:
        if not self.events:
            raise AssertionError("dispatch on empty queue")
        event = self.events.pop(0)  # pinned dispatcher removes before calling handler
        self.count = event.count
        return event

    def serialize(self) -> list[tuple[str, int]]:
        # Pinned save_eventqueue_infos persists only type/count, not insertion/request identity.
        return [(event.kind, event.count) for event in self.events]

    @classmethod
    def restore(cls, rows: list[tuple[str, int]], count: int, epoch: int) -> "MupenQueue":
        q = cls(count=count, epoch=epoch)
        for kind, when in rows:
            # load_eventqueue_infos re-adds only type/count. Request ancestry is therefore unknown.
            event = Event(kind, when, q.next_token, None, epoch)
            q.next_token += 1
            pos = 0
            while pos < len(q.events) and q.events[pos].count <= when:
                pos += 1
            q.events.insert(pos, event)
        return q


class GopherReset:
    """Relevant semantics from pinned UI reset callback + fixed event slot array."""

    def __init__(self, count: int = 0) -> None:
        self.count = count
        self.ip4 = False
        self.nmi: Event | None = None
        self.next_token = 1

    def soft_reset(self, request: int) -> Event:
        # The callback asserts the HW2/IP4 level directly, then create_event overwrites EVENT_TYPE_NMI.
        self.ip4 = True
        event = Event(NMI, self.count + GOPHER_NMI_DELAY, self.next_token, request, 0)
        self.next_token += 1
        self.nmi = event
        return event

    def trigger_nmi(self) -> Event:
        if self.nmi is None:
            raise AssertionError("no NMI event")
        event = self.nmi
        self.nmi = None  # pinned trigger_event disables the slot before handler
        self.count = event.count
        self.ip4 = False  # reset_event clears IP4
        return event


@dataclass(frozen=True)
class Witness:
    event_token: int
    request: int
    kind: str
    epoch: int


def verify_delivery(event: Event, witness: Witness, consumed: set[tuple[int, int]]) -> bool:
    """Minimal fail-closed causal verifier used only by this experiment."""
    identity = (event.epoch, event.token)
    if identity in consumed:
        return False
    if event.request is None:
        return False
    if (
        witness.event_token != event.token
        or witness.request != event.request
        or witness.kind != event.kind
        or witness.epoch != event.epoch
    ):
        return False
    consumed.add(identity)
    return True


def fixed_cases() -> dict[str, object]:
    # Two reset requests at the same Count produce four distinct Mupen queue nodes,
    # despite identical HW2 and NMI type/count pairs.
    mq = MupenQueue(count=100)
    first = mq.soft_reset(1)
    second = mq.soft_reset(2)
    rows = [(e.kind, e.count, e.token, e.request) for e in mq.events]
    assert [r[:2] for r in rows] == [
        (HW2, 100), (HW2, 100), (NMI, 50_000_100), (NMI, 50_000_100)
    ]
    assert len({r[2] for r in rows}) == 4

    consumed: set[tuple[int, int]] = set()
    e1 = mq.dispatch()
    assert verify_delivery(e1, Witness(e1.token, 1, HW2, 0), consumed)
    assert not verify_delivery(e1, Witness(e1.token, 1, HW2, 0), consumed)  # replay
    e2 = mq.dispatch()
    assert not verify_delivery(e2, Witness(e2.token, 1, HW2, 0), consumed)  # same value, wrong request
    assert verify_delivery(e2, Witness(e2.token, 2, HW2, 0), consumed)

    # Save/restore preserves queue type/count rows but not producer ancestry.
    saved = mq.serialize()
    restored = MupenQueue.restore(saved, count=mq.count, epoch=1)
    assert [(e.kind, e.count) for e in restored.events] == saved
    assert all(e.request is None for e in restored.events)
    restored_nmi = restored.dispatch()
    forged = Witness(restored_nmi.token, 1, NMI, 1)
    assert not verify_delivery(restored_nmi, forged, set())

    # Gopher's fixed NMI slot coalesces/overwrites an earlier pending request.
    g = GopherReset(count=100)
    nmi1 = g.soft_reset(1)
    assert g.ip4
    nmi2 = g.soft_reset(2)
    assert g.nmi == nmi2 and g.nmi != nmi1
    delivered = g.trigger_nmi()
    assert delivered.request == 2
    assert not g.ip4

    return {
        "mupen_same_count_rows": rows,
        "mupen_distinct_nodes": 4,
        "mupen_restore_rows": saved,
        "mupen_restore_request_ancestry": "unknown",
        "gopher_first_pending_token": nmi1.token,
        "gopher_replacement_token": nmi2.token,
        "gopher_delivered_request": delivered.request,
        "fixed_forgery_rejections": 3,
    }


def fuzz(seed: int = 0x4857324E, trials: int = 10_000) -> dict[str, int]:
    rng = random.Random(seed)
    mupen_ambiguous_value_keys = 0
    mupen_restore_unknown_rows = 0
    gopher_coalesced_requests = 0
    total_reset_requests = 0

    for _ in range(trials):
        count = rng.randrange(0, 64)
        resets = rng.randrange(1, 6)
        total_reset_requests += resets

        mq = MupenQueue(count=count)
        for request in range(1, resets + 1):
            mq.soft_reset(request)
        buckets: dict[tuple[str, int], int] = {}
        for event in mq.events:
            key = (event.kind, event.count)
            buckets[key] = buckets.get(key, 0) + 1
        mupen_ambiguous_value_keys += sum(1 for n in buckets.values() if n > 1)

        # Randomly checkpoint with pending rows. Any external producer identity not serialized
        # by the emulator must be invalidated or explicitly persisted by the observer.
        if rng.randrange(2) == 0:
            restored = MupenQueue.restore(mq.serialize(), count=count, epoch=1)
            mupen_restore_unknown_rows += sum(e.request is None for e in restored.events)

        g = GopherReset(count=count)
        for request in range(1, resets + 1):
            g.soft_reset(request)
        if resets > 1:
            gopher_coalesced_requests += resets - 1
        assert g.nmi is not None and g.nmi.request == resets

    assert mupen_ambiguous_value_keys > 0
    assert mupen_restore_unknown_rows > 0
    assert gopher_coalesced_requests > 0
    return {
        "seed": seed,
        "trials": trials,
        "total_reset_requests": total_reset_requests,
        "mupen_ambiguous_type_count_keys": mupen_ambiguous_value_keys,
        "mupen_restored_rows_without_request_ancestry": mupen_restore_unknown_rows,
        "gopher_coalesced_or_overwritten_reset_requests": gopher_coalesced_requests,
    }


def main() -> None:
    result = {
        "classification": "PARTIAL",
        "fixed": fixed_cases(),
        "fuzz": fuzz(),
        "invariants": [
            "Mupen duplicate type/count queue rows are distinct operations; value equality is not event identity.",
            "Mupen savestate queue rows preserve type/count but not external producer ancestry.",
            "Gopher repeated reset requests can overwrite/coalesce one pending NMI slot.",
            "Both pinned dispatch paths consume/disable the selected event before invoking its handler.",
            "No cross-reference 1:1 reset-request-to-NMI-generation rule is justified.",
        ],
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    out = Path("target/reset-hw2-nmi-producer")
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(canonical)
    print(f"RESULT_SHA256={digest}")


if __name__ == "__main__":
    main()
