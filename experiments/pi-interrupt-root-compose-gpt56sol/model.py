#!/usr/bin/env python3
"""Adversarial PI -> MI -> CPU interrupt-root composition model.

This is a bounded evidence model, not an N64 hardware implementation.  The state
transitions mirror only the exact pinned ares source seams guarded by
source_guard.py: accepted PI DMA has an immediate byte effect after the queue
insert attempt; only a surviving queued event can call dmaFinished(); dmaFinished
raises the raw MI PI line; MI mask changes repoll that raw line into CPU RCP
pending; CPU interrupt entry additionally requires Status.IM/IE and !EXL/!ERL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import hashlib
import json
import random

ARES = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
SEEDS = 64
OPS_PER_SEED = 5000


@dataclass
class Request:
    rid: int
    copy_gen: int
    queued: bool
    payload: int


@dataclass
class State:
    op: int = 0
    next_rid: int = 1
    busy: bool = False
    active: Optional[Request] = None
    queued: Optional[Request] = None

    # PI/MI interrupt state.  Keep raw producer identity separate from CPU pending.
    raw_pi: bool = False
    raw_source_rid: Optional[int] = None
    raw_gen: Optional[int] = None
    mi_mask: bool = False
    mask_gen: int = 0
    cause_rcp: bool = False
    cause_gen: int = 0
    cause_source_rid: Optional[int] = None

    # CPU gate state from the independently validated interrupt-root contract.
    ie: bool = True
    im_rcp: bool = True
    exl: bool = False
    erl: bool = False
    bev: bool = False
    status_gen: int = 0

    copies: list[tuple[int, int, int]] = field(default_factory=list)
    completions: list[tuple[int, int]] = field(default_factory=list)
    roots: list[tuple[int, int, int, int, int, int]] = field(default_factory=list)

    def tick(self) -> int:
        self.op += 1
        return self.op

    def poll(self, gen: int) -> None:
        # This is the single-source PI-only projection of ares MI::poll().
        self.cause_rcp = self.raw_pi and self.mi_mask
        self.cause_gen = gen
        self.cause_source_rid = self.raw_source_rid if self.cause_rcp else None

    def request(self, inserted: bool, payload: int = 0) -> Optional[int]:
        gen = self.tick()
        if self.busy:
            return None
        req = Request(self.next_rid, gen, inserted, payload)
        self.next_rid += 1
        self.busy = True
        self.active = req
        # Exact ares ordering: the byte copy occurs after queueInsert even when
        # queueInsert silently failed.  Payload is deliberately not identity.
        self.copies.append((gen, req.rid, payload))
        if inserted:
            self.queued = req
        return req.rid

    def cancel(self) -> int:
        # PI_STATUS reset: cancel queued DMA/busy state.  It is not IRQ ack.
        gen = self.tick()
        self.busy = False
        self.active = None
        self.queued = None
        return gen

    def complete(self) -> bool:
        gen = self.tick()
        if self.queued is None:
            return False
        req = self.queued
        self.queued = None
        self.active = None
        self.busy = False
        self.raw_pi = True
        self.raw_source_rid = req.rid
        self.raw_gen = gen
        self.completions.append((gen, req.rid))
        self.poll(gen)
        return True

    def clear_interrupt(self) -> int:
        gen = self.tick()
        self.raw_pi = False
        self.raw_source_rid = None
        self.raw_gen = None
        self.poll(gen)
        return gen

    def set_mask(self, value: bool) -> int:
        # Even a same-value command is retained as an operation generation.
        gen = self.tick()
        self.mi_mask = value
        self.mask_gen = gen
        self.poll(gen)
        return gen

    def set_status(
        self,
        *,
        ie: Optional[bool] = None,
        im: Optional[bool] = None,
        exl: Optional[bool] = None,
        erl: Optional[bool] = None,
        bev: Optional[bool] = None,
    ) -> int:
        gen = self.tick()
        if ie is not None:
            self.ie = ie
        if im is not None:
            self.im_rcp = im
        if exl is not None:
            self.exl = exl
        if erl is not None:
            self.erl = erl
        if bev is not None:
            self.bev = bev
        self.status_gen = gen
        return gen

    def boundary(self):
        gen = self.tick()
        if self.cause_rcp and self.im_rcp and self.ie and not self.exl and not self.erl:
            root = 0xFFFFFFFFBFC00380 if self.bev else 0xFFFFFFFF80000180
            assert self.cause_source_rid is not None
            assert any(rid == self.cause_source_rid for _, rid in self.completions)
            assert self.raw_gen is not None
            rec = (
                gen,
                self.cause_source_rid,
                self.raw_gen,
                self.cause_gen,
                self.status_gen,
                root,
            )
            self.roots.append(rec)
            self.exl = True
            return rec
        return None


def deterministic_cases() -> dict[str, object]:
    cases: dict[str, object] = {}

    # Copy with rejected queue insertion cannot later complete or raise PI.
    s = State()
    s.set_mask(True)
    assert s.request(False, 0x11) == 1
    assert not s.complete()
    assert s.boundary() is None
    cases["queue_fail_copy_no_irq"] = {"copies": len(s.copies), "roots": len(s.roots)}

    # Cancel removes the queued completion but does not undo the already-done copy.
    s = State()
    s.set_mask(True)
    assert s.request(True, 0x22) == 1
    s.cancel()
    assert not s.complete()
    assert s.boundary() is None
    cases["cancel_before_completion"] = {"copies": len(s.copies), "roots": len(s.roots)}

    # Completion with MI PI masked records raw pending only.  A later mask write
    # exposes the old completion to CPU RCP pending and then to the root gate.
    s = State()
    assert s.request(True, 0x33) == 1
    assert s.complete()
    assert s.raw_pi and not s.cause_rcp
    assert s.boundary() is None
    mask_gen = s.set_mask(True)
    root = s.boundary()
    assert root is not None and root[1] == 1 and root[3] == mask_gen
    cases["masked_completion_then_unmask"] = {"source_request": root[1], "mask_gen": mask_gen}

    # CPU IE is a separate gate after MI has already asserted Cause.IP2/RCP.
    s = State(ie=False)
    s.set_mask(True)
    assert s.request(True, 0x44) == 1
    assert s.complete() and s.cause_rcp
    assert s.boundary() is None
    s.set_status(ie=True)
    root = s.boundary()
    assert root is not None and root[1] == 1
    cases["late_cpu_enable"] = {"source_request": root[1]}

    # Ack/lower before the CPU boundary removes eligibility.
    s = State()
    s.set_mask(True)
    assert s.request(True, 0x55) == 1
    assert s.complete()
    s.clear_interrupt()
    assert s.boundary() is None
    cases["clear_before_boundary"] = {"roots": 0}

    # Equal bytes and "latest PI copy" are not interrupt provenance.  Request 2
    # performs the same payload copy but has no queue event; the root still comes
    # from request 1's retained completion generation.
    s = State()
    s.set_mask(True)
    assert s.request(True, 0x66) == 1
    assert s.complete()
    assert s.request(False, 0x66) == 2
    root = s.boundary()
    assert root is not None and root[1] == 1
    assert s.copies[-1][1] == 2
    cases["equal_payload_latest_copy_decoy"] = {
        "root_source_request": root[1],
        "latest_copy_request": s.copies[-1][1],
    }

    # A same-value MI mask-set command repolls the still-pending raw PI line.  It
    # is a new operation generation but must not steal the raw producer identity.
    s = State()
    s.set_mask(True)
    assert s.request(True, 0x77) == 1
    assert s.complete()
    old_raw_gen = s.raw_gen
    repoll_gen = s.set_mask(True)
    root = s.boundary()
    assert root is not None and root[1] == 1 and root[2] == old_raw_gen and root[3] == repoll_gen
    cases["same_value_mask_repoll"] = {"raw_gen": old_raw_gen, "repoll_gen": repoll_gen}

    return cases


def fuzz() -> dict[str, int]:
    stats = {
        "histories": 0,
        "operations": 0,
        "queue_failed_copies": 0,
        "histories_with_copy_without_completion": 0,
        "roots_whose_source_is_not_latest_copy": 0,
        "same_value_mask_operations": 0,
    }

    for seed in range(SEEDS):
        rng = random.Random(seed)
        s = State()
        for _ in range(OPS_PER_SEED):
            stats["operations"] += 1
            action = rng.randrange(8)
            if action == 0:
                rid = s.request(rng.random() < 0.75, rng.randrange(4))
                if rid is not None and s.active is not None and not s.active.queued:
                    stats["queue_failed_copies"] += 1
            elif action == 1:
                s.complete()
            elif action == 2:
                s.cancel()
            elif action == 3:
                s.clear_interrupt()
            elif action == 4:
                s.set_mask(bool(rng.getrandbits(1)))
            elif action == 5:
                s.set_status(
                    ie=bool(rng.getrandbits(1)),
                    im=bool(rng.getrandbits(1)),
                    exl=bool(rng.getrandbits(1)),
                    erl=bool(rng.getrandbits(1)),
                    bev=bool(rng.getrandbits(1)),
                )
            elif action == 6:
                root = s.boundary()
                if root is not None and s.copies and s.copies[-1][1] != root[1]:
                    stats["roots_whose_source_is_not_latest_copy"] += 1
            else:
                # Force the equal-value operation adversary.
                s.set_mask(s.mi_mask)
                stats["same_value_mask_operations"] += 1

            assert s.cause_rcp == (s.raw_pi and s.mi_mask)
            if s.cause_rcp:
                assert s.cause_source_rid is not None
                assert s.raw_source_rid == s.cause_source_rid
            for root in s.roots:
                assert any(rid == root[1] for _, rid in s.completions)

        if len(s.copies) > len(s.completions):
            stats["histories_with_copy_without_completion"] += 1
        stats["histories"] += 1

    # These are falsification requirements, not just telemetry.
    assert stats["queue_failed_copies"] > 0
    assert stats["histories_with_copy_without_completion"] > 0
    assert stats["roots_whose_source_is_not_latest_copy"] > 0
    assert stats["same_value_mask_operations"] > 0
    return stats


def main() -> None:
    doc = {
        "ares_pin": ARES,
        "deterministic": deterministic_cases(),
        "fuzz": fuzz(),
        "invariant": (
            "PI copy/request identity is distinct from queued-completion identity; "
            "root provenance is completion -> raw PI line -> MI poll/mask -> CPU gate -> root"
        ),
    }
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
    print(json.dumps(doc, sort_keys=True, indent=2))
    print("RESULT_SHA256=" + hashlib.sha256(canonical).hexdigest())
    print("PASS: copy, completion, MI pending/mask, CPU gate and root generations remain causally distinct")


if __name__ == "__main__":
    main()
