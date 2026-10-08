#!/usr/bin/env python3
"""Bounded adversarial model for pointer-table immutability under N64 aliases.

This is not an N64 emulator. It encodes the address-identity property exercised by
Plaid's pointer-table closure question: distinct guest virtual addresses can resolve
to the same physical bytes, and unresolved translation must fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    IMMUTABLE = "IMMUTABLE"
    MUTATED = "MUTATED"
    OPEN = "OPEN"


@dataclass(frozen=True)
class Span:
    start: int
    size: int

    @property
    def end(self) -> int:
        return self.start + self.size

    def overlaps(self, other: "Span") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class TlbMap:
    virtual_page: int
    physical_page: int
    size: int = 0x1000
    writable: bool = True


@dataclass(frozen=True)
class Mutation:
    name: str
    vaddr: Optional[int]
    size: int
    succeeded: bool = True
    resolved_paddr: Optional[int] = None
    translation_known: bool = True
    can_reach_backing: bool = True


TABLE_VIRTUAL = Span(0xA0000100, 12)  # KSEG1 snapshot view.
TABLE_PHYSICAL = Span(0x00000100, 12)


def direct_translate(vaddr: int) -> Optional[int]:
    """Model the pinned ares 32-bit KSEG0/KSEG1 physical-address mask."""
    if 0x80000000 <= vaddr <= 0xBFFFFFFF:
        return vaddr & 0x1FFFFFFF
    return None


def translate(vaddr: int, tlb: tuple[TlbMap, ...] = ()) -> Optional[int]:
    direct = direct_translate(vaddr)
    if direct is not None:
        return direct
    for entry in tlb:
        if entry.virtual_page <= vaddr < entry.virtual_page + entry.size:
            if not entry.writable:
                return None
            return entry.physical_page + (vaddr - entry.virtual_page)
    return None


def virtual_range_verdict(table: Span, mutations: tuple[Mutation, ...]) -> Verdict:
    """Deliberately weak candidate: reject only writes whose guest ranges overlap."""
    for m in mutations:
        if not m.succeeded or not m.can_reach_backing or m.vaddr is None:
            continue
        if Span(m.vaddr, m.size).overlaps(table):
            return Verdict.MUTATED
    return Verdict.IMMUTABLE


def physical_backing_verdict(table: Span, mutations: tuple[Mutation, ...]) -> Verdict:
    """Minimum fail-closed obligation: reason about backing identity, not vaddr spelling."""
    for m in mutations:
        if not m.succeeded or not m.can_reach_backing:
            continue
        if not m.translation_known:
            return Verdict.OPEN
        if m.resolved_paddr is None:
            return Verdict.OPEN
        if Span(m.resolved_paddr, m.size).overlaps(table):
            return Verdict.MUTATED
    return Verdict.IMMUTABLE


def mutate_word(memory: bytearray, paddr: int, value: int) -> None:
    memory[paddr : paddr + 4] = value.to_bytes(4, "big")


def table_words(memory: bytearray) -> tuple[int, ...]:
    return tuple(
        int.from_bytes(memory[p : p + 4], "big")
        for p in range(TABLE_PHYSICAL.start, TABLE_PHYSICAL.end, 4)
    )


def event(name: str, vaddr: int, *, tlb: tuple[TlbMap, ...] = (), **kw) -> Mutation:
    return Mutation(name=name, vaddr=vaddr, size=4, resolved_paddr=translate(vaddr, tlb), **kw)


def run() -> None:
    memory = bytearray(0x1000)
    initial = (0x80000040, 0x80000050, 0x80000060)
    for i, word in enumerate(initial):
        mutate_word(memory, TABLE_PHYSICAL.start + i * 4, word)
    assert table_words(memory) == initial

    scenarios: list[tuple[str, tuple[Mutation, ...], Verdict, Verdict]] = []

    # Control: the exact snapshotted virtual range is caught even by the weak proof.
    same_virtual = event("same-virtual-store", 0xA0000104)
    scenarios.append(("same_virtual", (same_virtual,), Verdict.MUTATED, Verdict.MUTATED))

    # Adversarial KSEG alias: cached KSEG0 and direct KSEG1 resolve to the same paddr.
    kseg0_alias = event("kseg0-cached-alias-store", 0x80000104)
    assert kseg0_alias.resolved_paddr == 0x104
    scenarios.append(("kseg0_alias", (kseg0_alias,), Verdict.IMMUTABLE, Verdict.MUTATED))

    # Adversarial TLB alias: unrelated virtual page is writable onto the same paddr.
    tlb = (TlbMap(virtual_page=0x00400000, physical_page=0x00000000),)
    tlb_alias = event("tlb-alias-store", 0x00400108, tlb=tlb)
    assert tlb_alias.resolved_paddr == 0x108
    scenarios.append(("tlb_alias", (tlb_alias,), Verdict.IMMUTABLE, Verdict.MUTATED))

    # Cached stores can defer the backing mutation until writeback. The store itself
    # still invalidates an immutability claim unless cache lifecycle proves it dies.
    dirty_alias = event("cached-dirty-store", 0x80000100)
    deferred_writeback = Mutation(
        name="later-dcache-writeback",
        vaddr=None,
        size=4,
        resolved_paddr=0x100,
    )
    scenarios.append(
        ("deferred_writeback", (dirty_alias, deferred_writeback), Verdict.IMMUTABLE, Verdict.MUTATED)
    )

    # Even a physically immutable backing snapshot is insufficient for a cacheable
    # table load if an older D-cache line is already resident. The pinned ares
    # D-cache returns resident words on a hit and only fills from backing on a miss.
    backing_snapshot_word = 0x80000070
    resident_dcache_word = 0x80000050
    assert backing_snapshot_word != resident_dcache_word
    assert physical_backing_verdict(TABLE_PHYSICAL, ()) == Verdict.IMMUTABLE
    print(
        "stale_dcache_source  physical=IMMUTABLE snapshot_match="
        + str(backing_snapshot_word == resident_dcache_word)
    )

    # Non-overlap control must not turn the stronger checker into "reject everything".
    elsewhere = event("nonoverlap-store", 0x80000200)
    scenarios.append(("nonoverlap", (elsewhere,), Verdict.IMMUTABLE, Verdict.IMMUTABLE))

    # A write whose translation/mapping history is unavailable cannot certify immutable.
    unresolved = Mutation(
        name="unresolved-mapped-store",
        vaddr=0x00600000,
        size=4,
        resolved_paddr=None,
        translation_known=False,
    )
    scenarios.append(("unresolved_mapping", (unresolved,), Verdict.IMMUTABLE, Verdict.OPEN))

    # Failed writes do not mutate backing.
    failed = Mutation(
        name="failed-tlb-modification",
        vaddr=0x00400104,
        size=4,
        succeeded=False,
        resolved_paddr=None,
    )
    scenarios.append(("failed_write", (failed,), Verdict.IMMUTABLE, Verdict.IMMUTABLE))

    for name, mutations, want_v, want_p in scenarios:
        got_v = virtual_range_verdict(TABLE_VIRTUAL, mutations)
        got_p = physical_backing_verdict(TABLE_PHYSICAL, mutations)
        assert got_v == want_v, (name, got_v, want_v)
        assert got_p == want_p, (name, got_p, want_p)
        print(f"{name:20s} virtual={got_v.value:9s} physical={got_p.value}")

    # Concrete byte counterexample: mutate the KSEG1-snapshotted table through KSEG0.
    before = table_words(memory)
    mutate_word(memory, kseg0_alias.resolved_paddr, 0x80000070)
    after = table_words(memory)
    assert before == initial
    assert after == (0x80000040, 0x80000070, 0x80000060)
    assert before != after
    print("table_before          " + ",".join(f"{x:08x}" for x in before))
    print("table_after_kseg0     " + ",".join(f"{x:08x}" for x in after))
    print("RESULT PARTIAL: virtual-only is unsound; physical mutation exclusion is necessary but cacheable table loads also need D-cache lineage")


if __name__ == "__main__":
    run()
