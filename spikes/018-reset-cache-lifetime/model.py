#!/usr/bin/env python3
"""Deterministic state-transition model for pinned ares N64 reset/cache research.

This deliberately models only the fields needed by spike 018. The modeled
operations are direct transcriptions of ares 9408cb43d4948fc3ea6e152a307a34348df3fe04:
- CPU::InstructionCache::power/fill/fetch from ares/n64/cpu/cpu.hpp
- CPU::Exception::nmi from ares/n64/cpu/exceptions.cpp
- CPU::ERET from ares/n64/cpu/interpreter-scc.cpp
- RDRAM::power(reset) lifetime behavior from ares/n64/rdram/rdram.cpp
- CPU/RDRAM save-state fields from their serialization.cpp files

It is not a replacement emulator and makes no N64-wide hardware claim.
"""

from dataclasses import dataclass, field
import copy
import hashlib
import struct

PAGE_MASK = 0xFFFFF000
INDEX_MASK = 0x0FE0


@dataclass
class Line:
    tag_key: int = 0
    index: int = 0
    words: list[int] = field(default_factory=lambda: [0] * 8)

    def valid(self) -> bool:
        return bool(self.tag_key & 1)

    def hit(self, paddr: int) -> bool:
        return self.valid() and (self.tag_key & ~1) == (paddr & PAGE_MASK)

    def read(self, paddr: int) -> int:
        return self.words[(paddr >> 2) & 7]


class ICache:
    def __init__(self) -> None:
        self.lines = [Line(index=(i << 5) & INDEX_MASK) for i in range(512)]

    def line(self, vaddr: int) -> Line:
        return self.lines[(vaddr >> 5) & 0x1FF]

    def power(self, reset: bool) -> None:
        # Pinned ares ignores reset here and always clears resident state.
        del reset
        for i, line in enumerate(self.lines):
            line.tag_key = 0
            line.index = (i << 5) & INDEX_MASK
            line.words[:] = [0] * 8

    def fill(self, vaddr: int, paddr: int, ram: dict[int, int]) -> None:
        line = self.line(vaddr)
        tag = paddr & PAGE_MASK
        line.tag_key = tag | 1
        start = tag | line.index
        line.words[:] = [ram.get(start + 4 * i, 0) for i in range(8)]

    def fetch(self, vaddr: int, paddr: int, ram: dict[int, int]) -> tuple[int, bool]:
        line = self.line(vaddr)
        filled = False
        if not line.hit(paddr):
            self.fill(vaddr, paddr, ram)
            filled = True
        return line.read(paddr), filled

    def digest(self) -> str:
        h = hashlib.sha256()
        for line in self.lines:
            h.update(struct.pack(">IH", line.tag_key & 0xFFFFFFFF, line.index & 0xFFFF))
            for word in line.words:
                h.update(struct.pack(">I", word & 0xFFFFFFFF))
        return h.hexdigest()


@dataclass
class CPUState:
    pc: int
    epc_error: int = 0
    error_level: bool = False
    vector_location: bool = False
    tlb_shutdown: bool = False
    soft_reset: bool = False


def ram_digest(ram: dict[int, int]) -> str:
    h = hashlib.sha256()
    for address, value in sorted(ram.items()):
        h.update(struct.pack(">II", address & 0xFFFFFFFF, value & 0xFFFFFFFF))
    return h.hexdigest()


def nmi(cpu: CPUState) -> None:
    cpu.vector_location = True
    cpu.tlb_shutdown = False
    cpu.soft_reset = False
    cpu.error_level = True
    cpu.epc_error = cpu.pc
    cpu.pc = 0xFFFF_FFFF_BFC0_0000


def eret(cpu: CPUState) -> None:
    if cpu.error_level:
        cpu.pc = cpu.epc_error
        cpu.error_level = False


def cpu_power(cpu: CPUState, icache: ICache, reset: bool) -> None:
    icache.power(reset)
    cpu.pc = 0xFFFF_FFFF_BFC0_0000
    cpu.epc_error = 0
    cpu.error_level = False
    cpu.vector_location = False
    cpu.tlb_shutdown = False
    cpu.soft_reset = False


def rdram_power(ram: dict[int, int], reset: bool) -> None:
    # Pinned ares executes ram.fill() only when reset == false. Exact entropy
    # bytes are irrelevant here; the tested reset=true path must preserve RAM.
    if not reset:
        ram.clear()


def report(name: str, value: int, filled: bool | None, icache: ICache, ram: dict[int, int]) -> None:
    print(
        f"{name} value_or_pc=0x{value:016x} fill={filled} "
        f"icache_sha256={icache.digest()} ram_sha256={ram_digest(ram)}"
    )


def main() -> None:
    vaddr = 0xFFFF_FFFF_8000_1000
    paddr = 0x0000_1000
    ram = {paddr + 4 * i: 0x1111_0000 + i for i in range(8)}
    cpu = CPUState(pc=vaddr)
    icache = ICache()

    word, filled = icache.fetch(vaddr, paddr, ram)
    assert word == 0x1111_0000 and filled
    report("initial_fill_fetch", word, filled, icache, ram)

    # Backing changes, but resident I-cache bytes remain stale.
    ram[paddr] = 0x2222_0000
    word, filled = icache.fetch(vaddr, paddr, ram)
    assert word == 0x1111_0000 and not filled
    report("stale_before_nmi", word, filled, icache, ram)

    # NMI changes control state only. It does not touch the cache or RDRAM.
    pre_nmi_cache = icache.digest()
    pre_nmi_ram = ram_digest(ram)
    nmi(cpu)
    assert icache.digest() == pre_nmi_cache
    assert ram_digest(ram) == pre_nmi_ram
    report("after_nmi", cpu.pc, None, icache, ram)

    # ERET from ERL returns to ErrorEPC; the stale resident word is reused.
    eret(cpu)
    word, filled = icache.fetch(vaddr, paddr, ram)
    assert cpu.pc == vaddr
    assert word == 0x1111_0000 and not filled
    report("eret_refetch", word, filled, icache, ram)

    # Save-state snapshot contains the stale line plus newer RDRAM bytes.
    snapshot = (copy.deepcopy(cpu), copy.deepcopy(icache), copy.deepcopy(ram))

    # System reset=true calls RDRAM::power(true) and CPU::power(true): backing
    # RAM survives, while CPU::InstructionCache::power clears every line.
    pre_reset_ram = ram_digest(ram)
    rdram_power(ram, True)
    cpu_power(cpu, icache, True)
    assert ram_digest(ram) == pre_reset_ram
    assert not icache.line(vaddr).valid()
    word, filled = icache.fetch(vaddr, paddr, ram)
    assert word == 0x2222_0000 and filled
    report("reset_refill", word, filled, icache, ram)

    # Advance to a newer backing state. The current cache remains stale at 0x2222.
    ram[paddr] = 0x3333_0000
    word, filled = icache.fetch(vaddr, paddr, ram)
    assert word == 0x2222_0000 and not filled
    report("newer_timeline_stale", word, filled, icache, ram)

    # Unserialize overwrites RDRAM and CPU cache fields with the saved snapshot.
    # Model that field restoration directly: an older resident line reappears
    # without a new fill in the resumed chronology.
    cpu, icache, ram = copy.deepcopy(snapshot)
    word, filled = icache.fetch(vaddr, paddr, ram)
    assert word == 0x1111_0000 and not filled
    assert ram[paddr] == 0x2222_0000
    report("restored_snapshot_fetch", word, filled, icache, ram)

    print("PASS reset/cache lifetime adversarial model")


if __name__ == "__main__":
    main()
