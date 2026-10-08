#!/usr/bin/env python3
"""Deterministic source-derived SWL/SWR mutation experiment for Plaid.

Models the exact partial-store decomposition in pinned ares:
  9408cb43d4948fc3ea6e152a307a34348df3fe04
and cross-checks reverse-endian backing bytes against pinned n64-systemtest:
  196f5421173220eb2f63a7a99c64795dc0ea0698

This is not an emulator. It is a small executable model of the bounded
instruction/memory-write logic under study.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import random
from typing import Dict, Iterable, List, Optional, Tuple

ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
VALUE = 0x11223344
ORACLE_VALUE = 0x50607080
FILL = 0xAA

BYTE, HALF, WORD = 1, 2, 4
SIZE_NAME = {BYTE: "B", HALF: "H", WORD: "W"}


@dataclass(frozen=True)
class Op:
    size: int
    vaddr: int
    value: int
    aligned_error: bool = True


def ares_ops(instr: str, endian: str, vaddr: int, data: int) -> List[Op]:
    """Exact control-flow transcription of pinned ares CPU::SWL/CPU::SWR."""
    off = vaddr & 3
    base = vaddr & ~3
    data &= 0xFFFF_FFFF
    ops: List[Op] = []

    def emit(size: int, addr: int, value: int, aligned_error: bool = True) -> None:
        ops.append(Op(size, addr, value, aligned_error))

    if instr == "SWL":
        if endian == "little":
            if off == 0:
                emit(BYTE, base | 0, data >> 24)
            elif off == 1:
                emit(HALF, base | 0, data >> 16)
            elif off == 2:
                emit(BYTE, base | 2, data >> 24)
                emit(HALF, base | 0, data >> 8)
            else:
                emit(WORD, base | 0, data)
        elif endian == "big":
            if off == 0:
                emit(WORD, vaddr + 0, data)
            elif off == 1:
                emit(BYTE, vaddr + 0, data >> 24)
                emit(HALF, vaddr + 1, data >> 8)
            elif off == 2:
                emit(HALF, vaddr + 0, data >> 16)
            else:
                emit(BYTE, vaddr + 0, data >> 24)
        else:
            raise ValueError(endian)
    elif instr == "SWR":
        if endian == "little":
            if off == 0:
                emit(WORD, base | 0, data)
            elif off == 1:
                emit(HALF, base | 2, data >> 8)
                emit(BYTE, base | 1, data)
            elif off == 2:
                emit(HALF, base | 2, data)
            else:
                emit(BYTE, base | 3, data)
        elif endian == "big":
            # Pinned ares explicitly disables alignment checking here.
            if off == 0:
                emit(BYTE, vaddr + 0, data, False)
            elif off == 1:
                emit(HALF, vaddr + 0, data, False)
            elif off == 2:
                emit(BYTE, vaddr + 0, data, False)
                emit(HALF, vaddr - 2, data >> 8, False)
            else:
                emit(WORD, vaddr + 0, data, False)
        else:
            raise ValueError(endian)
    else:
        raise ValueError(instr)
    return ops


def reverse_endian_paddr(size: int, paddr: int) -> int:
    # Pinned ares CPU::reverseEndianPaddr<Size>.
    return paddr ^ {BYTE: 7, HALF: 6, WORD: 4}[size]


def op_paddr(op: Op, endian: str) -> int:
    paddr = op.vaddr  # identity physical mapping for this bounded fixture
    return reverse_endian_paddr(op.size, paddr) if endian == "little" else paddr


def actual_lane_span(paddr: int, size: int) -> Tuple[int, ...]:
    """Lanes actually changed by ares DCache/MSB writable helpers.

    Half/Word helpers index an aligned storage slot even when the caller
    intentionally suppresses address-alignment exceptions.
    """
    start = paddr & ~(size - 1)
    return tuple(range(start, start + size))


def write_backing(memory: Dict[int, int], op: Op, endian: str) -> Tuple[int, Tuple[int, ...]]:
    paddr = op_paddr(op, endian)
    lanes = actual_lane_span(paddr, op.size)
    mask = (1 << (op.size * 8)) - 1
    raw = (op.value & mask).to_bytes(op.size, "big")
    for address, value in zip(lanes, raw):
        memory[address] = value
    return paddr, lanes


def execute(
    instr: str,
    endian: str,
    vaddr: int,
    data: int,
    memory: Dict[int, int],
    fail_index: Optional[int] = None,
) -> Tuple[bool, List[dict]]:
    events: List[dict] = []
    for index, op in enumerate(ares_ops(instr, endian, vaddr, data)):
        # Each ares sub-write is `if(!write<...>(...)) return;`.
        if fail_index == index:
            events.append({"index": index, "ok": False, "op": op})
            return False, events
        paddr, lanes = write_backing(memory, op, endian)
        events.append(
            {
                "index": index,
                "ok": True,
                "op": op,
                "paddr": paddr,
                "lanes": lanes,
            }
        )
    return True, events


def virtual_byte(memory: Dict[int, int], endian: str, vaddr: int, fill: int = FILL) -> int:
    paddr = vaddr if endian == "big" else (vaddr ^ 7)
    return memory.get(paddr, fill)


def virtual_changed(memory: Dict[int, int], endian: str, addresses: Iterable[int]) -> List[int]:
    return [a for a in addresses if virtual_byte(memory, endian, a) != FILL]


def fresh_memory(lo: int, hi: int) -> Dict[int, int]:
    return {a: FILL for a in range(lo, hi)}


def expected_single_lanes(endian: str, instr: str, off: int) -> List[int]:
    if endian == "big":
        if instr == "SWL":
            return list(range(off, 4))
        return list(range(0, off + 1))
    if instr == "SWL":
        return list(range(0, off + 1))
    return list(range(off, 4))


def dirty_mask(paddr: int, size: int) -> int:
    # Exact pinned ares DataCache::Line::write expression, truncated to u16.
    return (((1 << size) - 1) << (paddr & 0xF)) & 0xFFFF


def mask_lanes(mask: int) -> Tuple[int, ...]:
    return tuple(i for i in range(16) if mask & (1 << i))


def cache_dirty_mismatches() -> List[dict]:
    out: List[dict] = []
    for endian in ("big", "little"):
        for instr in ("SWL", "SWR"):
            for word_base in (0, 4, 8, 12):
                vbase = 0x1000 + word_base
                for off in range(4):
                    for op_index, op in enumerate(ares_ops(instr, endian, vbase + off, VALUE)):
                        paddr = op_paddr(op, endian)
                        actual = tuple(a & 0xF for a in actual_lane_span(paddr, op.size))
                        recorded = mask_lanes(dirty_mask(paddr, op.size))
                        if actual != recorded:
                            out.append(
                                {
                                    "endian": endian,
                                    "instr": instr,
                                    "word_base_in_line": word_base,
                                    "offset": off,
                                    "op_index": op_index,
                                    "size": SIZE_NAME[op.size],
                                    "paddr_low": paddr & 0xF,
                                    "actual": actual,
                                    "dirty": recorded,
                                }
                            )
    return out


def check_single_lane_matrix() -> List[dict]:
    base = 0x1000
    rows: List[dict] = []
    for endian in ("big", "little"):
        for instr in ("SWL", "SWR"):
            for off in range(4):
                mem = fresh_memory(base - 16, base + 32)
                ok, events = execute(instr, endian, base + off, VALUE, mem)
                assert ok
                changed = [a - base for a in virtual_changed(mem, endian, range(base, base + 4))]
                expected = expected_single_lanes(endian, instr, off)
                assert changed == expected, (endian, instr, off, changed, expected)
                rows.append(
                    {
                        "endian": endian,
                        "instr": instr,
                        "offset": off,
                        "virtual_lanes": changed,
                        "ops": [
                            {
                                "size": SIZE_NAME[e["op"].size],
                                "vdelta": e["op"].vaddr - base,
                                "value_low": e["op"].value & ((1 << (8 * e["op"].size)) - 1),
                                "aligned_error": e["op"].aligned_error,
                            }
                            for e in events
                        ],
                    }
                )
    return rows


def check_unaligned_pairs(rounds: int = 4096) -> int:
    """Prove paired SWL/SWR can materialize arbitrary unaligned words."""
    rng = random.Random(0x504C414944)  # "PLAID"
    base = 0x2000

    def run_one(endian: str, addr: int, value: int) -> None:
        mem = fresh_memory(base - 32, base + 64)
        if endian == "big":
            seq = (("SWL", addr), ("SWR", addr + 3))
            expected = value.to_bytes(4, "big")
        else:
            seq = (("SWR", addr), ("SWL", addr + 3))
            expected = value.to_bytes(4, "little")
        for instr, vaddr in seq:
            ok, _ = execute(instr, endian, vaddr, value, mem)
            assert ok
        got = bytes(virtual_byte(mem, endian, addr + i) for i in range(4))
        assert got == expected, (endian, addr & 3, hex(value), got.hex(), expected.hex())
        changed = virtual_changed(mem, endian, range(addr - 4, addr + 8))
        assert all(addr <= a < addr + 4 for a in changed), (endian, addr & 3, changed)
        for outside in list(range(addr - 4, addr)) + list(range(addr + 4, addr + 8)):
            assert virtual_byte(mem, endian, outside) == FILL
        if value == VALUE:
            assert changed == list(range(addr, addr + 4)), (endian, addr & 3, changed)

    for endian in ("big", "little"):
        for off in range(4):
            run_one(endian, base + off, VALUE)
    for _ in range(rounds):
        endian = rng.choice(("big", "little"))
        off = rng.randrange(4)
        value = rng.getrandbits(32)
        run_one(endian, base + off, value)
    return 8 + rounds


def backing_u64(memory: Dict[int, int], base: int) -> int:
    return int.from_bytes(bytes(memory[a] for a in range(base, base + 8)), "big")


def check_systemtest_reverse_endian_oracle() -> List[dict]:
    """Cross-check the exact pinned n64-systemtest SWL/SWR RE vectors.

    n64-systemtest uses value 0x50607080, backing initialized to 0xaa,
    and records the first physical u64 after each offset.
    """
    expected = {
        "SWL": (
            0xAAAA_AAAA_AAAA_AA50,
            0xAAAA_AAAA_AAAA_5060,
            0xAAAA_AAAA_AA50_6070,
            0xAAAA_AAAA_5060_7080,
        ),
        "SWR": (
            0xAAAA_AAAA_5060_7080,
            0xAAAA_AAAA_6070_80AA,
            0xAAAA_AAAA_7080_AAAA,
            0xAAAA_AAAA_80AA_AAAA,
        ),
    }
    base = 0x3000
    rows = []
    for instr in ("SWL", "SWR"):
        for off in range(4):
            mem = fresh_memory(base, base + 32)
            ok, _ = execute(instr, "little", base + off, ORACLE_VALUE, mem)
            assert ok
            got = backing_u64(mem, base)
            want = expected[instr][off]
            assert got == want, (instr, off, hex(got), hex(want))
            rows.append({"instr": instr, "offset": off, "backing_u64": f"{got:016x}"})
    return rows


def check_cache_vs_uncached() -> int:
    """Clean-resident-line fixture: cached store defers backing mutation."""
    base = 0x4000
    cases = 0
    for endian in ("big", "little"):
        for instr in ("SWL", "SWR"):
            for off in range(4):
                backing = fresh_memory(base - 16, base + 32)
                cache = dict(backing)  # clean resident line after fill
                original = dict(backing)

                ok, _ = execute(instr, endian, base + off, VALUE, cache)
                assert ok
                assert backing == original  # cached path has not written backing

                direct = dict(original)
                ok, _ = execute(instr, endian, base + off, VALUE, direct)
                assert ok

                # A writeback of the resident cache line makes backing agree
                # with the direct path for this clean single-line fixture.
                line_base = base & ~0xF
                for a in range(line_base, line_base + 16):
                    backing[a] = cache[a]
                assert backing == direct
                cases += 1
    return cases


def check_failures() -> List[dict]:
    """Exercise the explicit `if(!write) return` control flow.

    `fail_index=0` models translation/access rejection before any mutation.
    For two-subwrite cases, `fail_index=1` is an adversarial sink failure that
    proves there is no rollback in the instruction wrapper. Real normal RDRAM
    subwrites within one word normally share the same translation fate, so the
    second case is a control-flow property, not evidence of a common hardware
    event.
    """
    base = 0x5000
    rows = []
    for endian in ("big", "little"):
        for instr in ("SWL", "SWR"):
            for off in range(4):
                ops = ares_ops(instr, endian, base + off, VALUE)

                mem0 = fresh_memory(base - 16, base + 32)
                before0 = dict(mem0)
                ok0, _ = execute(instr, endian, base + off, VALUE, mem0, fail_index=0)
                assert not ok0 and mem0 == before0

                if len(ops) > 1:
                    mem1 = fresh_memory(base - 16, base + 32)
                    before1 = dict(mem1)
                    ok1, _ = execute(instr, endian, base + off, VALUE, mem1, fail_index=1)
                    assert not ok1 and mem1 != before1
                    rows.append(
                        {
                            "endian": endian,
                            "instr": instr,
                            "offset": off,
                            "prefix_mutated": True,
                            "first_op_size": SIZE_NAME[ops[0].size],
                        }
                    )
    return rows


def main() -> None:
    lane_rows = check_single_lane_matrix()
    pair_cases = check_unaligned_pairs()
    oracle_rows = check_systemtest_reverse_endian_oracle()
    cache_cases = check_cache_vs_uncached()
    failure_rows = check_failures()
    mismatches = cache_dirty_mismatches()

    mismatch_shape = {
        (m["endian"], m["instr"], m["offset"], m["size"])
        for m in mismatches
    }
    assert mismatch_shape == {
        ("big", "SWR", 1, "H"),
        ("big", "SWR", 3, "W"),
    }
    assert len(mismatches) == 8

    canonical = {
        "ares_rev": ARES_REV,
        "systemtest_rev": SYSTEMTEST_REV,
        "lane_rows": lane_rows,
        "pair_cases": pair_cases,
        "oracle_rows": oracle_rows,
        "cache_cases": cache_cases,
        "failure_rows": failure_rows,
        "dirty_mismatches": mismatches,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    print("PASS ares SWL/SWR partial-store executable-mutation model")
    print(f"  lane matrix:       {len(lane_rows)} / {len(lane_rows)}")
    print(f"  unaligned pairs:   {pair_cases} / {pair_cases}")
    print(f"  RE oracle vectors: {len(oracle_rows)} / {len(oracle_rows)}")
    print(f"  cache/direct:      {cache_cases} / {cache_cases}")
    print(f"  prefix-fail cases: {len(failure_rows)}")
    print(f"  dirty mismatches:  {len(mismatches)}")
    for m in mismatches:
        print(
            "    "
            f"{m['endian']} {m['instr']} word+{m['word_base_in_line']} "
            f"off={m['offset']} {m['size']} paddr_low={m['paddr_low']}: "
            f"actual={list(m['actual'])} dirty={list(m['dirty'])}"
        )
    print(f"  result_sha256:     {digest}")


if __name__ == "__main__":
    main()
