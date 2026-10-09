#!/usr/bin/env python3
"""Source-derived model for exact pinned-ares SDL/SDR -> CPU-visible SP sinks."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
DATA = 0x1122334455667788
BYTE, HALF, WORD, DUAL = 1, 2, 4, 8

@dataclass(frozen=True)
class Op:
    size: int
    vaddr: int
    value: int


def ares_ops(instr: str, endian: str, vaddr: int, data: int = DATA) -> list[Op]:
    """Exact control-flow transcription of pinned CPU::SD/SDL/SDR."""
    off = vaddr & 7
    base = vaddr & ~7
    out: list[Op] = []
    def emit(size: int, addr: int, value: int) -> None:
        out.append(Op(size, addr, value & 0xffffffffffffffff))

    if instr == "SD":
        if off: raise ValueError("model SD control is aligned only")
        emit(DUAL, vaddr, data)
    elif instr == "SDL":
        if endian == "little":
            if off == 0: emit(BYTE, base | 0, data >> 56)
            elif off == 1: emit(HALF, base | 0, data >> 48)
            elif off == 2:
                emit(BYTE, base | 2, data >> 56); emit(HALF, base | 0, data >> 40)
            elif off == 3: emit(WORD, base | 0, data >> 32)
            elif off == 4:
                emit(BYTE, base | 4, data >> 56); emit(WORD, base | 0, data >> 24)
            elif off == 5:
                emit(HALF, base | 4, data >> 48); emit(WORD, base | 0, data >> 16)
            elif off == 6:
                emit(BYTE, base | 6, data >> 56); emit(HALF, base | 4, data >> 40); emit(WORD, base | 0, data >> 8)
            else: emit(DUAL, base | 0, data)
        elif endian == "big":
            if off == 0: emit(DUAL, base | 0, data)
            elif off == 1:
                emit(BYTE, base | 1, data >> 56); emit(HALF, base | 2, data >> 40); emit(WORD, base | 4, data >> 8)
            elif off == 2:
                emit(HALF, base | 2, data >> 48); emit(WORD, base | 4, data >> 16)
            elif off == 3:
                emit(BYTE, base | 3, data >> 56); emit(WORD, base | 4, data >> 24)
            elif off == 4: emit(WORD, base | 4, data >> 32)
            elif off == 5:
                emit(BYTE, base | 5, data >> 56); emit(HALF, base | 6, data >> 40)
            elif off == 6: emit(HALF, base | 6, data >> 48)
            else: emit(BYTE, base | 7, data >> 56)
        else: raise ValueError(endian)
    elif instr == "SDR":
        if endian == "little":
            if off == 0: emit(DUAL, base | 0, data)
            elif off == 1:
                emit(WORD, base | 4, data >> 24); emit(HALF, base | 2, data >> 8); emit(BYTE, base | 1, data)
            elif off == 2:
                emit(WORD, base | 4, data >> 16); emit(HALF, base | 2, data)
            elif off == 3:
                emit(WORD, base | 4, data >> 8); emit(BYTE, base | 3, data)
            elif off == 4: emit(WORD, base | 4, data)
            elif off == 5:
                emit(HALF, base | 6, data >> 8); emit(BYTE, base | 5, data)
            elif off == 6: emit(HALF, base | 6, data)
            else: emit(BYTE, base | 7, data)
        elif endian == "big":
            if off == 0: emit(BYTE, base | 0, data)
            elif off == 1: emit(HALF, base | 0, data)
            elif off == 2:
                emit(HALF, base | 0, data >> 8); emit(BYTE, base | 2, data)
            elif off == 3: emit(WORD, base | 0, data)
            elif off == 4:
                emit(WORD, base | 0, data >> 8); emit(BYTE, base | 4, data)
            elif off == 5:
                emit(WORD, base | 0, data >> 16); emit(HALF, base | 4, data)
            elif off == 6:
                emit(WORD, base | 0, data >> 24); emit(HALF, base | 4, data >> 8); emit(BYTE, base | 6, data)
            else: emit(DUAL, base | 0, data)
        else: raise ValueError(endian)
    else:
        raise ValueError(instr)
    return out


def reverse_endian_paddr(size: int, paddr: int) -> int:
    if size == BYTE: return paddr ^ 7
    if size == HALF: return paddr ^ 6
    if size == WORD: return paddr ^ 4
    return paddr  # exact pinned ares leaves Dual paddr unchanged


def rcp_sink(size: int, paddr: int, data: int) -> tuple[int, int]:
    """Exact Memory::RCP write normalization to the concrete writeWord sink."""
    if size == BYTE:
        value = (data & 0xff) << {0: 24, 1: 16, 2: 8, 3: 0}[paddr & 3]
    elif size == HALF:
        value = (data & 0xffff) << (16 if (paddr & 2) == 0 else 0)
    elif size == WORD:
        value = data & 0xffffffff
    elif size == DUAL:
        # Critical exact-reference behavior: one writeWord only, using high 32 bits.
        value = (data >> 32) & 0xffffffff
    else:
        raise ValueError(size)
    return paddr & ~3, value & 0xffffffff


def apply(mem: bytes, instr: str, endian: str, effective_offset: int, *, phys_base: int) -> tuple[bytes, list[dict]]:
    out = bytearray(mem)
    events: list[dict] = []
    for index, op in enumerate(ares_ops(instr, endian, phys_base + effective_offset)):
        paddr = reverse_endian_paddr(op.size, op.vaddr) if endian == "little" else op.vaddr
        word, value = rcp_sink(op.size, paddr, op.value)
        local = (word - phys_base) & 0xfff
        if not 0 <= local <= len(out) - 4:
            raise AssertionError((instr, endian, effective_offset, hex(word), local))
        out[local:local + 4] = value.to_bytes(4, "big")
        events.append({
            "index": index,
            "size": op.size,
            "vdelta": op.vaddr - phys_base,
            "pdelta": paddr - phys_base,
            "sink_word_delta": local,
            "sink_value": value,
        })
    return bytes(out), events


def execute(initial: bytes, instr: str, endian: str, offset: int, *, bank: str) -> tuple[bytes, list[dict]]:
    phys_base = 0x04001000 if bank == "imem" else 0x04000000
    return apply(initial, instr, endian, offset, phys_base=phys_base)


def execute_pair(initial: bytes, endian: str, start: int, *, bank: str) -> tuple[bytes, list[dict]]:
    phys_base = 0x04001000 if bank == "imem" else 0x04000000
    sequence = (("SDL", start), ("SDR", start + 7)) if endian == "big" else (("SDL", start + 7), ("SDR", start))
    mem = bytes(initial)
    all_events: list[dict] = []
    for seq, (instr, offset) in enumerate(sequence):
        mem, events = apply(mem, instr, endian, offset, phys_base=phys_base)
        for event in events:
            event = dict(event); event["sequence"] = seq; event["instr"] = instr
            all_events.append(event)
    return mem, all_events


def changed(initial: bytes, final: bytes) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(initial, final)) if a != b]


def main() -> None:
    initial = bytes(range(0xa0, 0xb8))
    rows = []
    dual_cases = two_word_cases = repeated_sink_cases = 0
    for endian in ("big", "little"):
        for instr in ("SDL", "SDR"):
            for offset in range(8):
                after, events = execute(initial, instr, endian, offset, bank="imem")
                sink_words = [e["sink_word_delta"] for e in events]
                if any(e["size"] == DUAL for e in events):
                    dual_cases += 1
                    assert len(changed(initial, after)) == 4
                if len(set(sink_words)) == 2: two_word_cases += 1
                if len(sink_words) != len(set(sink_words)): repeated_sink_cases += 1
                rows.append({"kind":"single","endian":endian,"instr":instr,"offset":offset,"after":after.hex(),"events":events})
    assert dual_cases == 4
    assert two_word_cases == 12
    assert repeated_sink_cases == 8

    pair_lengths = set()
    for endian in ("big", "little"):
        for start in range(8):
            after, events = execute_pair(initial, endian, start, bank="imem")
            pair_lengths.add(len(changed(initial, after)))
            rows.append({"kind":"pair","endian":endian,"start":start,"after":after.hex(),"events":events})
    assert pair_lengths == {4, 8, 12}, pair_lengths

    for endian in ("big", "little"):
        after, events = execute(initial, "SD", endian, 0, bank="imem")
        assert len(events) == 1 and events[0]["size"] == DUAL
        assert len(changed(initial, after)) == 4
        rows.append({"kind":"sd-control","endian":endian,"after":after.hex(),"events":events})

    payload = (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print("PASS: source-derived SDL/SDR -> SP concrete sink model")
    print(f"dual_single_cases={dual_cases}/32")
    print(f"two_word_single_cases={two_word_cases}/32")
    print(f"repeated_same_sink_single_cases={repeated_sink_cases}/32")
    print("pair_changed_byte_counts=4,8,12")
    print("sd_control_changed_bytes=4")
    print("model_sha256=" + hashlib.sha256(payload).hexdigest())

if __name__ == "__main__":
    main()
