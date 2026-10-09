#!/usr/bin/env python3
"""Independent adversarial model for PageMask -> physical tag -> I-cache resident provenance."""
from __future__ import annotations
from dataclasses import dataclass, replace
import hashlib
import json
import random

MASK16 = 0b11 << 13
MASK64 = 0b1111 << 13


def geometry(page_mask: int) -> tuple[int, int, int]:
    page_mask &= 0b101010101010 << 13
    page_mask |= page_mask >> 1
    mask_hi = ~(page_mask | 0x1FFF) & ((1 << 40) - 1)
    mask_lo = (page_mask | 0x1FFF) >> 1
    select = mask_lo + 1
    return mask_hi, mask_lo, select


def translate(va: int, page_mask: int, p0: int, p1: int) -> tuple[int, int]:
    _, mask_lo, select = geometry(page_mask)
    half = 1 if va & select else 0
    return half, (p1 if half else p0) + (va & mask_lo)


def fixed4k(va: int, p0: int, p1: int) -> tuple[int, int]:
    half = 1 if va & 0x1000 else 0
    return half, (p1 if half else p0) + (va & 0xFFF)


def slot(va: int) -> int:
    return (va >> 5) & 0x1FF


def tag(paddr: int) -> int:
    return (paddr & ~0xFFF) | 1


@dataclass(frozen=True)
class Mapping:
    op_gen: int
    page_mask: int
    p0: int
    p1: int
    asid: int = 7


@dataclass(frozen=True)
class Resident:
    resident_gen: int
    slot: int
    tag: int
    paddr: int
    word: int
    backing_gen: int
    fill_mapping_gen: int
    fill_context_gen: int


@dataclass(frozen=True)
class FetchWitness:
    mapping_gen: int
    context_gen: int
    paddr: int
    slot: int
    tag: int
    resident_gen: int
    backing_gen: int
    word: int
    hit: bool


class Machine:
    def __init__(self) -> None:
        self.mapping: Mapping | None = None
        self.context_gen = 0
        self.asid = 7
        self.memory: dict[int, tuple[int, int]] = {}
        self.resident: dict[int, Resident] = {}
        self.next_map = 0
        self.next_backing = 0
        self.next_resident = 0

    def map(self, page_mask: int, p0: int, p1: int, asid: int = 7) -> Mapping:
        self.next_map += 1
        self.mapping = Mapping(self.next_map, page_mask, p0, p1, asid)
        return self.mapping

    def context(self, asid: int) -> int:
        self.context_gen += 1
        self.asid = asid
        return self.context_gen

    def write(self, paddr: int, word: int) -> int:
        self.next_backing += 1
        self.memory[paddr] = (word, self.next_backing)
        return self.next_backing

    def fetch(self, va: int) -> FetchWitness | None:
        assert self.mapping is not None
        if self.asid != self.mapping.asid:
            return None
        _, paddr = translate(va, self.mapping.page_mask, self.mapping.p0, self.mapping.p1)
        s = slot(va)
        t = tag(paddr)
        old = self.resident.get(s)
        if old is not None and old.tag == t:
            return FetchWitness(self.mapping.op_gen, self.context_gen, paddr, s, t,
                                old.resident_gen, old.backing_gen, old.word, True)
        word, backing_gen = self.memory[paddr]
        self.next_resident += 1
        resident = Resident(self.next_resident, s, t, paddr, word, backing_gen,
                            self.mapping.op_gen, self.context_gen)
        self.resident[s] = resident
        return FetchWitness(self.mapping.op_gen, self.context_gen, paddr, s, t,
                            resident.resident_gen, backing_gen, word, False)


def verify(va: int, mapping: Mapping, context_gen: int, asid: int,
           resident: Resident | None, witness: FetchWitness) -> bool:
    if asid != mapping.asid or witness.mapping_gen != mapping.op_gen or witness.context_gen != context_gen:
        return False
    _, paddr = translate(va, mapping.page_mask, mapping.p0, mapping.p1)
    if witness.paddr != paddr or witness.slot != slot(va) or witness.tag != tag(paddr):
        return False
    if resident is None or resident.slot != witness.slot or resident.tag != witness.tag:
        return not witness.hit
    if not witness.hit:
        return False
    return (witness.resident_gen == resident.resident_gen
            and witness.backing_gen == resident.backing_gen
            and witness.word == resident.word
            and resident.paddr == paddr)


def scenario() -> dict:
    va = 0x21000
    m = Machine()
    m.write(0x011000, 0x34091111)
    m.write(0x020000, 0x34091111)  # equal-value fixed-4K decoy
    map1 = m.map(MASK16, 0x010000, 0x020000)
    f1 = m.fetch(va); assert f1 and not f1.hit and f1.paddr == 0x011000
    resident1 = m.resident[slot(va)]

    # Same-value TLB write is a distinct operation generation but not a cache lifetime end.
    map2 = m.map(MASK16, 0x010000, 0x020000)
    assert map2.op_gen != map1.op_gen and m.resident[slot(va)] == resident1
    m.write(0x011000, 0x34092222)
    stale = m.fetch(va); assert stale and stale.hit and stale.word == 0x34091111

    # Equal payload at a new physical tag requires a new resident generation.
    m.write(0x031000, 0x34091111)
    m.write(0x040000, 0x34091111)
    map3 = m.map(MASK16, 0x030000, 0x040000)
    equal = m.fetch(va); assert equal and not equal.hit and equal.paddr == 0x031000
    assert equal.resident_gen != stale.resident_gen and equal.word == stale.word

    # Return to original mapping, refill fresh, mutate backing, then leave/return without fetch.
    map4 = m.map(MASK16, 0x010000, 0x020000)
    fresh = m.fetch(va); assert fresh and not fresh.hit and fresh.word == 0x34092222
    resident_fresh = m.resident[slot(va)]
    m.write(0x011000, 0x34094444)
    m.map(MASK16, 0x030000, 0x040000)  # away, no fetch
    map6 = m.map(MASK16, 0x010000, 0x020000)  # back, no fetch
    away_back = m.fetch(va); assert away_back and away_back.hit and away_back.word == 0x34092222
    assert m.resident[slot(va)] == resident_fresh

    # Context unreachability likewise does not mutate the resident.
    m.context(0x22)
    assert m.fetch(va) is None
    resident_after_fail = m.resident[slot(va)]
    ctx_back = m.context(7)
    after_context = m.fetch(va); assert after_context and after_context.hit
    assert m.resident[slot(va)] == resident_after_fail

    # Same VA, changed PageMask geometry: exact 64K PA differs from fixed-4K decoy.
    m.write(0x051000, 0x34092222)
    m.write(0x070000, 0x34092222)
    map7 = m.map(MASK64, 0x050000, 0x070000)
    geometry_fetch = m.fetch(va); assert geometry_fetch and not geometry_fetch.hit
    assert geometry_fetch.paddr == 0x051000

    fixed_half, fixed_pa = fixed4k(va, 0x050000, 0x070000)
    exact_half, exact_pa = translate(va, MASK64, 0x050000, 0x070000)
    assert (fixed_half, fixed_pa) != (exact_half, exact_pa)

    # Verify the accepted hit and then attack each independent identity dimension.
    resident = resident_after_fail
    accepted = after_context
    assert verify(va, map6, ctx_back, 7, resident, accepted)
    forgeries = {
        "fixed4k_paddr": replace(accepted, paddr=0x020000, tag=tag(0x020000)),
        "current_backing": replace(accepted, backing_gen=m.memory[0x011000][1], word=m.memory[0x011000][0]),
        "wrong_mapping_generation": replace(accepted, mapping_gen=map6.op_gen - 1),
        "wrong_context_generation": replace(accepted, context_gen=ctx_back - 1),
        "equal_payload_new_resident": replace(accepted, resident_gen=equal.resident_gen),
        "wrong_physical_tag": replace(accepted, tag=tag(0x031000)),
    }
    rejected = sorted(name for name, forged in forgeries.items()
                      if not verify(va, map6, ctx_back, 7, resident, forged))
    assert rejected == sorted(forgeries)

    return {
        "first": f1.__dict__,
        "stale_after_backing_write": stale.__dict__,
        "equal_payload_remap": equal.__dict__,
        "away_back": away_back.__dict__,
        "after_context_return": after_context.__dict__,
        "geometry_remap": geometry_fetch.__dict__,
        "same_value_mapping_generations": [map1.op_gen, map2.op_gen],
        "fixed64_guess": {"half": fixed_half, "paddr": fixed_pa},
        "exact64": {"half": exact_half, "paddr": exact_pa},
        "rejected_forgeries": rejected,
    }


def fuzz() -> dict:
    rng = random.Random(0x504C414944CACE)
    cases = 50_000
    fixed_wrong = 0
    tag_wrong = 0
    bit12_half_wrong = 0
    for _ in range(cases):
        mask = rng.choice([MASK16, MASK64])
        _, mask_lo, select = geometry(mask)
        pair_size = select * 2
        vbase = rng.randrange(0, 0x200000 // pair_size) * pair_size
        va = vbase + rng.randrange(0, pair_size // 4) * 4
        page_size = select
        p0 = rng.randrange(1, 32) * page_size
        p1 = rng.randrange(33, 64) * page_size
        eh, ep = translate(va, mask, p0, p1)
        fh, fp = fixed4k(va, p0, p1)
        if (eh, ep) != (fh, fp):
            fixed_wrong += 1
        if eh != fh:
            bit12_half_wrong += 1
        if tag(ep) != tag(fp):
            tag_wrong += 1
        # The translated low page offset must agree with virtual cache-index bits
        # used by pinned ares for legal large-page mappings.
        assert (ep & 0xFE0) == (va & 0xFE0)
        assert ep >= (p1 if eh else p0)
        assert (ep - (p1 if eh else p0)) <= mask_lo
    assert fixed_wrong > cases // 2 and tag_wrong > cases // 2 and bit12_half_wrong > 0
    return {"cases": cases, "fixed4k_wrong": fixed_wrong,
            "physical_tag_wrong": tag_wrong, "bit12_half_wrong": bit12_half_wrong}


def main() -> None:
    result = {"scenario": scenario(), "fuzz": fuzz()}
    compact = json.dumps(result, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(compact.encode()).hexdigest()
    print("MODEL_SHA256=" + digest)
    print(compact)
    print("PASS: mapping geometry, operation/context generation, translated PA and resident generation remain independently necessary")


if __name__ == "__main__":
    main()
