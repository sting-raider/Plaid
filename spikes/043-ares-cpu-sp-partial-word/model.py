#!/usr/bin/env python3
"""Source-derived model for pinned-ares SWL/SWR -> RSP IMEM sink effects."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
DATA = 0x11223344
BYTE, HALF, WORD = 1, 2, 4

@dataclass(frozen=True)
class Op:
    size: int
    vaddr: int
    value: int
    aligned_error: bool = True


def ares_ops(instr: str, endian: str, vaddr: int, data: int) -> list[Op]:
    """Exact control-flow transcription of pinned CPU::SWL/CPU::SWR."""
    off = vaddr & 3
    base = vaddr & ~3
    data &= 0xffffffff
    out: list[Op] = []
    def emit(size: int, addr: int, value: int, aligned_error: bool = True) -> None:
        out.append(Op(size, addr, value & 0xffffffff, aligned_error))

    if instr == "SWL":
        if endian == "little":
            if off == 0: emit(BYTE, base | 0, data >> 24)
            elif off == 1: emit(HALF, base | 0, data >> 16)
            elif off == 2:
                emit(BYTE, base | 2, data >> 24)
                emit(HALF, base | 0, data >> 8)
            else: emit(WORD, base | 0, data)
        elif endian == "big":
            if off == 0: emit(WORD, vaddr, data)
            elif off == 1:
                emit(BYTE, vaddr, data >> 24)
                emit(HALF, vaddr + 1, data >> 8)
            elif off == 2: emit(HALF, vaddr, data >> 16)
            else: emit(BYTE, vaddr, data >> 24)
        else: raise ValueError(endian)
    elif instr == "SWR":
        if endian == "little":
            if off == 0: emit(WORD, base | 0, data)
            elif off == 1:
                emit(HALF, base | 2, data >> 8)
                emit(BYTE, base | 1, data)
            elif off == 2: emit(HALF, base | 2, data)
            else: emit(BYTE, base | 3, data)
        elif endian == "big":
            if off == 0: emit(BYTE, vaddr, data, False)
            elif off == 1: emit(HALF, vaddr, data, False)
            elif off == 2:
                emit(BYTE, vaddr, data, False)
                emit(HALF, vaddr - 2, data >> 8, False)
            else: emit(WORD, vaddr, data, False)
        else: raise ValueError(endian)
    else: raise ValueError(instr)
    return out


def reverse_endian_paddr(size: int, paddr: int) -> int:
    return paddr ^ {BYTE: 7, HALF: 6, WORD: 4}[size]


def rcp_word(size: int, paddr: int, data: int) -> tuple[int, int]:
    """Pinned Memory::RCP::write -> writeWord effect for Byte/Half/Word."""
    if size == BYTE:
        value = (data << {0: 24, 1: 16, 2: 8, 3: 0}[paddr & 3]) & 0xffffffff
    elif size == HALF:
        value = (data << (16 if (paddr & 2) == 0 else 0)) & 0xffffffff
    elif size == WORD:
        value = data & 0xffffffff
    else:
        raise ValueError(size)
    return paddr & ~3, value


def execute(initial: bytes, instr: str, endian: str, offset: int, data: int = DATA) -> tuple[bytes, list[dict]]:
    if len(initial) != 16: raise ValueError("need 16-byte IMEM window")
    phys_base = 0x04001000
    mem = bytearray(initial)
    events: list[dict] = []
    for index, op in enumerate(ares_ops(instr, endian, phys_base + offset, data)):
        paddr = reverse_endian_paddr(op.size, op.vaddr) if endian == "little" else op.vaddr
        word, value = rcp_word(op.size, paddr, op.value)
        local = (word - phys_base) & 0xfff
        if not 0 <= local <= 12:
            raise AssertionError((instr, endian, offset, hex(word), local))
        mem[local:local + 4] = value.to_bytes(4, "big")
        events.append({
            "index": index,
            "size": op.size,
            "vdelta": op.vaddr - phys_base,
            "pdelta": paddr - phys_base,
            "source_value": op.value,
            "sink_word_delta": local,
            "sink_value": value,
        })
    return bytes(mem), events


def execute_pair(initial: bytes, endian: str, offset: int, data: int = DATA) -> tuple[bytes, list[dict]]:
    phys_base = 0x04001000
    mem = bytes(initial)
    all_events: list[dict] = []
    sequence = (("SWL", offset), ("SWR", offset + 3)) if endian == "big" else (("SWR", offset), ("SWL", offset + 3))
    for seq, (instr, off) in enumerate(sequence):
        # execute against current bytes while preserving absolute-offset semantics
        # by replaying the one instruction directly over the current window.
        mem2 = bytearray(mem)
        for index, op in enumerate(ares_ops(instr, endian, phys_base + off, data)):
            paddr = reverse_endian_paddr(op.size, op.vaddr) if endian == "little" else op.vaddr
            word, value = rcp_word(op.size, paddr, op.value)
            local = (word - phys_base) & 0xfff
            if not 0 <= local <= 12: raise AssertionError((endian, offset, instr, hex(word), local))
            mem2[local:local+4] = value.to_bytes(4, "big")
            all_events.append({"sequence": seq, "instr": instr, "index": index, "size": op.size, "sink_word_delta": local, "sink_value": value})
        mem = bytes(mem2)
    return mem, all_events


def main() -> None:
    initial = bytes(range(0xa0, 0xb0))
    rows = []
    overwrite_cases = 0
    for endian in ("big", "little"):
        for instr in ("SWL", "SWR"):
            for offset in range(8):
                after, events = execute(initial, instr, endian, offset)
                if len(events) == 2:
                    assert events[0]["sink_word_delta"] == events[1]["sink_word_delta"]
                    assert events[0]["sink_value"] != events[1]["sink_value"]
                    word = events[1]["sink_word_delta"]
                    assert after[word:word+4] == events[1]["sink_value"].to_bytes(4, "big")
                    overwrite_cases += 1
                rows.append({"kind":"single","endian":endian,"instr":instr,"offset":offset,"after":after.hex(),"events":events})

    pair_nonstandard = 0
    for endian in ("big", "little"):
        for offset in range(4):
            after, events = execute_pair(initial, endian, offset)
            # Ordinary RDRAM pair semantics would modify exactly four guest bytes.
            # SP-memory widening should not leave that ordinary partial-store image.
            if after != initial:
                pair_nonstandard += 1
            rows.append({"kind":"pair","endian":endian,"offset":offset,"after":after.hex(),"events":events})

    assert overwrite_cases == 8  # four offset classes repeated across two aligned words
    assert pair_nonstandard == 8
    payload = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print("PASS: source-derived SWL/SWR -> SP full-word sink model")
    print(f"two_subwrite_full_overwrite_cases={overwrite_cases}")
    print(f"pair_cases={pair_nonstandard}/8")
    print("model_sha256=" + hashlib.sha256(payload).hexdigest())

if __name__ == "__main__": main()
