#!/usr/bin/env python3
"""Adversarial model for the minimum mode-sensitive exception-root witness.

This is deliberately not a VR4300 emulator. It checks the proof-composition rule
that a root observation is meaningful only when bound to the exact Status/KSU/X
state generation that classified the faulting virtual address.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatusState:
    generation: int
    ksu: str
    ux: bool
    sx: bool
    kx: bool
    exl: bool = False
    erl: bool = False
    bev: bool = False

    @property
    def effective_mode(self) -> str:
        return "kernel" if self.exl or self.erl else self.ksu

    @property
    def bits(self) -> int:
        mode = self.effective_mode
        extended = {"kernel": self.kx, "supervisor": self.sx, "user": self.ux}[mode]
        return 64 if extended else 32


@dataclass(frozen=True)
class FetchFact:
    va: int
    status_generation: int | None
    outcome: str


@dataclass(frozen=True)
class RootFact:
    status_generation: int | None
    root: int


def base(bev: bool) -> int:
    return 0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000


def expected_root(status: StatusState, outcome: str) -> int | None:
    if outcome == "execute":
        return None
    if outcome == "address_error":
        return base(status.bev) + 0x180
    if outcome == "tlb_miss":
        if status.exl:
            return base(status.bev) + 0x180
        return base(status.bev) + (0x80 if status.bits == 64 else 0)
    raise ValueError(outcome)


def verify(status: StatusState, fetch: FetchFact, root: RootFact | None) -> bool:
    # Value equality is not chronology. Every fact must bind the exact generation.
    if fetch.status_generation is None or fetch.status_generation != status.generation:
        return False
    expected = expected_root(status, fetch.outcome)
    if expected is None:
        return root is None
    if root is None or root.status_generation is None:
        return False
    return root.status_generation == status.generation and root.root == expected


def self_test() -> None:
    # Positive 32-bit user mapped miss.
    u32_g7 = StatusState(7, "user", False, False, False)
    assert verify(
        u32_g7,
        FetchFact(0x4000, 7, "tlb_miss"),
        RootFact(7, 0xFFFFFFFF80000000),
    )

    # Same Status value written again is a distinct generation. A certificate
    # from generation 7 cannot explain generation 8 merely because all bits match.
    u32_g8 = StatusState(8, "user", False, False, False)
    assert not verify(
        u32_g8,
        FetchFact(0x4000, 8, "tlb_miss"),
        RootFact(7, 0xFFFFFFFF80000000),
    )

    # Same numeric root in supervisor and user 32-bit contexts does not merge the
    # causal contexts. A root fact from one generation cannot discharge the other.
    s32_g9 = StatusState(9, "supervisor", False, False, False)
    assert not verify(
        s32_g9,
        FetchFact(0x4000, 9, "tlb_miss"),
        RootFact(8, 0xFFFFFFFF80000000),
    )

    # UX changes the true-miss vector even with identical KSU and VA.
    u64_g10 = StatusState(10, "user", True, False, False)
    assert verify(
        u64_g10,
        FetchFact(0x100004000, 10, "tlb_miss"),
        RootFact(10, 0xFFFFFFFF80000080),
    )
    assert not verify(
        u64_g10,
        FetchFact(0x100004000, 10, "tlb_miss"),
        RootFact(10, 0xFFFFFFFF80000000),
    )

    # An address-error root must not be forged into an XTLB root just because the
    # context is 64-bit. Segment legality precedes TLB-miss classification.
    assert verify(
        u64_g10,
        FetchFact(0x4000000000004000, 10, "address_error"),
        RootFact(10, 0xFFFFFFFF80000180),
    )
    assert not verify(
        u64_g10,
        FetchFact(0x4000000000004000, 10, "address_error"),
        RootFact(10, 0xFFFFFFFF80000080),
    )

    # Missing generation is UNKNOWN/OPEN, never silently generation zero.
    assert not verify(
        u32_g7,
        FetchFact(0x4000, None, "tlb_miss"),
        RootFact(None, 0xFFFFFFFF80000000),
    )

    # EXL makes the effective execution mode kernel and forces nested true misses
    # to the general vector, even if the stored KSU/UX bits look user/64-bit.
    nested = StatusState(11, "user", True, False, False, exl=True)
    assert nested.effective_mode == "kernel" and nested.bits == 32
    assert verify(
        nested,
        FetchFact(0x4000, 11, "tlb_miss"),
        RootFact(11, 0xFFFFFFFF80000180),
    )


if __name__ == "__main__":
    self_test()
    print("PASS: mode/root witness rejects same-value generations, mode-less joins, and forged roots")
