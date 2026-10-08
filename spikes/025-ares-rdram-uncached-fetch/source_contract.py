#!/usr/bin/env python3
"""Fail-closed model for joining an uncached VR4300 instruction fetch to a successful
identity-mapped ordinary RDRAM word read.

This does NOT claim to execute ares. It encodes a bounded observer contract derived
from pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 and deliberately attacks naive
value/device/address joins.
"""
from dataclasses import dataclass
from typing import Optional
import hashlib
import json

PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
VR4300_UNCACHED = "VR4300_UNCACHED"
WORD = 4

@dataclass(frozen=True)
class FetchContext:
    ident: int
    vaddr: int
    paddr: int

@dataclass(frozen=True)
class BackingRead:
    seq: int
    context_id: int
    address: int
    value: int
    device: str
    size: int

@dataclass(frozen=True)
class Witness:
    context_id: int
    vaddr: int
    paddr: int
    word: int
    read_seq: int

class Observer:
    def __init__(self):
        self.seq = 0
        self.next_context = 1
        self.active: Optional[FetchContext] = None
        self.candidate: Optional[BackingRead] = None
        self.ambiguous = False

    def begin_fetch(self, vaddr: int, paddr: int, cached: bool) -> Optional[int]:
        # Cached fetches use I-cache fills/hits, never this ordinary-read contract.
        if cached:
            assert self.active is None
            self.candidate = None
            self.ambiguous = False
            return None
        assert self.active is None
        ident = self.next_context
        self.next_context += 1
        self.active = FetchContext(ident, vaddr, paddr)
        self.candidate = None
        self.ambiguous = False
        return ident

    def identity_rdram_read(self, address: int, value: int, *, device=VR4300_UNCACHED,
                            size=WORD, map_identity=True, in_bounds=True,
                            via_ebus=False) -> None:
        self.seq += 1
        # Hook location is after mapIdentity/bounds checks and after the actual read.
        # Remapped/degraded, EBus and failed/out-of-bounds paths must not emit.
        if not (map_identity and in_bounds and not via_ebus):
            return
        if self.active is None or device != VR4300_UNCACHED or size != WORD:
            return
        event = BackingRead(self.seq, self.active.ident, address, value & 0xffffffff,
                            device, size)
        if self.candidate is not None:
            self.ambiguous = True
        self.candidate = event

    def end_fetch(self, word: int) -> Optional[Witness]:
        ctx = self.active
        if ctx is None:
            return None
        self.active = None
        candidate = self.candidate
        ambiguous = self.ambiguous
        self.candidate = None
        self.ambiguous = False
        if candidate is None or ambiguous:
            return None
        if candidate.context_id != ctx.ident:
            return None
        if candidate.address != ctx.paddr or candidate.value != (word & 0xffffffff):
            return None
        return Witness(ctx.ident, ctx.vaddr, ctx.paddr, word & 0xffffffff, candidate.seq)


def naive_join(reads, *, paddr, word):
    """Deliberately unsound competitor: latest uncached read with equal address/value."""
    for event in reversed(reads):
        if (event["device"] == VR4300_UNCACHED and event["address"] == paddr
                and event["value"] == word):
            return event
    return None


def run_cases():
    results = []

    # 1: exact identity-mapped uncached fetch witnesses the actual word read.
    o = Observer(); cid = o.begin_fetch(0xffffffffa0004000, 0x4000, False)
    o.identity_rdram_read(0x4000, 0x24100009)
    w = o.end_fetch(0x24100009)
    assert w and w.context_id == cid and w.paddr == 0x4000 and w.word == 0x24100009
    results.append("identity_uncached_fetch")

    # 2: same RBusDevice/address/value on an ordinary data read is not enough.
    data_read = {"device":VR4300_UNCACHED,"address":0x4000,"value":0x24100009}
    assert naive_join([data_read], paddr=0x4000, word=0x24100009) is data_read
    o = Observer(); o.identity_rdram_read(0x4000, 0x24100009)  # no fetch context
    o.begin_fetch(0xffffffff80004000, 0x4000, True)           # cached fetch
    assert o.end_fetch(0x24100009) is None
    results.append("data_read_decoy_rejected")

    # 3: cached fetches cannot consume an ordinary single-word witness.
    o = Observer(); assert o.begin_fetch(0xffffffff80004000, 0x4000, True) is None
    o.identity_rdram_read(0x4000, 0x24100009)
    assert o.end_fetch(0x24100009) is None
    results.append("cached_fetch_rejected")

    # 4-6: paths that bypass successful identity RDRAM read stay unknown.
    for name, kwargs in [
        ("remapped_rejected", {"map_identity":False}),
        ("ebus_rejected", {"via_ebus":True}),
        ("out_of_bounds_rejected", {"in_bounds":False}),
    ]:
        o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4000, False)
        o.identity_rdram_read(0x4000, 0x24100009, **kwargs)
        assert o.end_fetch(0x24100009) is None
        results.append(name)

    # 7-8: equal bytes at the wrong address, or mutated return value, cannot join.
    o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4000, False)
    o.identity_rdram_read(0x5000, 0x24100009)
    assert o.end_fetch(0x24100009) is None
    results.append("wrong_address_rejected")

    o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4000, False)
    o.identity_rdram_read(0x4000, 0x24100009)
    assert o.end_fetch(0x24100008) is None
    results.append("value_mismatch_rejected")

    # 9: two backing reads under one fetch context are unexpected; fail closed.
    o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4000, False)
    o.identity_rdram_read(0x4000, 0x24100009)
    o.identity_rdram_read(0x4000, 0x24100009)
    assert o.end_fetch(0x24100009) is None
    results.append("multiple_reads_ambiguous")

    # 10: failed/no backing read never inherits a stale prior candidate.
    o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4000, False)
    o.identity_rdram_read(0x4000, 0x24100009)
    assert o.end_fetch(0x24100009)
    o.begin_fetch(0xffffffffa0004004, 0x4004, False)
    assert o.end_fetch(0x00000000) is None
    results.append("stale_candidate_not_reused")

    # 11: transformed physical address is the contract key. This captures the
    # little-endian CPU::fetch XOR-4 behavior without pretending vaddr alone suffices.
    o = Observer(); o.begin_fetch(0xffffffffa0004000, 0x4004, False)
    o.identity_rdram_read(0x4004, 0x11223344)
    w = o.end_fetch(0x11223344)
    assert w and w.paddr == 0x4004
    results.append("post_endian_physical_key")

    payload = {"pin": PIN, "cases": results, "count": len(results)}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload

if __name__ == "__main__":
    out = run_cases()
    print(json.dumps(out, indent=2, sort_keys=True))
