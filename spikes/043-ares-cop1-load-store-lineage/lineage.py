#!/usr/bin/env python3
"""Independent byte-lineage model for VR4300 COP1 load/store register selection."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Cell:
    value: int
    origin: str


def be_bytes(value: int, width: int) -> list[int]:
    return list(value.to_bytes(width, "big"))


def be_value(values: list[int]) -> int:
    return int.from_bytes(bytes(values), "big")


class FprLineage:
    """Track semantic bytes in the 32 physical 64-bit FPR storage cells.

    Slot 0 is the raw-u64 MSB and slot 7 the LSB. Therefore high-32 is slots
    0..3 and low-32 is slots 4..7. This models the pinned ares fgr_t views; it
    does not infer ancestry from equal payload values.
    """

    def __init__(self, raw: list[int]):
        assert len(raw) == 32
        self.cells: list[list[Cell]] = []
        for reg, value in enumerate(raw):
            self.cells.append(
                [Cell(byte, f"init:f{reg}:b{i}") for i, byte in enumerate(be_bytes(value, 8))]
            )

    @staticmethod
    def selection(op: str, fr: int, ft: int) -> tuple[int, list[int]]:
        assert op in {"LWC1", "LDC1", "SWC1", "SDC1", "MTC1", "DMTC1"}
        width = 4 if op in {"LWC1", "SWC1", "MTC1"} else 8
        if width == 8:
            return (ft if fr else ft & ~1), list(range(8))
        if fr:
            return ft, list(range(4, 8))
        return ft & ~1, list(range(0, 4) if ft & 1 else range(4, 8))

    def write(self, op: str, fr: int, ft: int, payload: list[int], origin_prefix: str) -> None:
        reg, slots = self.selection(op, fr, ft)
        assert len(payload) == len(slots)
        for index, (slot, byte) in enumerate(zip(slots, payload)):
            self.cells[reg][slot] = Cell(byte, f"{origin_prefix}:b{index}")

    def read(self, op: str, fr: int, ft: int) -> tuple[list[int], list[str]]:
        reg, slots = self.selection(op, fr, ft)
        cells = [self.cells[reg][slot] for slot in slots]
        return [cell.value for cell in cells], [cell.origin for cell in cells]

    def raw_u64(self, reg: int) -> int:
        return be_value([cell.value for cell in self.cells[reg]])


def initial_fprs(word: int) -> list[int]:
    raw = [0x7000000000000000 + i for i in range(32)]
    # Deliberate equal-valued decoys. A load of `word` can leave numeric state
    # unchanged while still creating a new generation; cross-FR selection can
    # later read an equal value from a different, untouched physical lane.
    raw[0] = (word << 32) | 0x55667788
    raw[1] = (0x99AABBCC << 32) | word
    return raw


def selftest() -> tuple[int, str]:
    import hashlib
    import json

    word = 0x10213243
    dual = 0x1021324354657687
    initial = initial_fprs(word)
    receipts = []
    cases = 0
    for load_op in ("LWC1", "LDC1"):
        for load_fr in (0, 1):
            for load_ft in (0, 1):
                for store_op in ("SWC1", "SDC1"):
                    for store_fr in (0, 1):
                        for store_ft in (0, 1):
                            model = FprLineage(initial)
                            width = 4 if load_op == "LWC1" else 8
                            value = word if width == 4 else dual
                            model.write(load_op, load_fr, load_ft, be_bytes(value, width), "load:1")
                            payload, origins = model.read(store_op, store_fr, store_ft)
                            receipts.append(
                                (
                                    load_op,
                                    load_fr,
                                    load_ft,
                                    store_op,
                                    store_fr,
                                    store_ft,
                                    be_value(payload),
                                    origins,
                                    model.raw_u64(0),
                                    model.raw_u64(1),
                                )
                            )
                            cases += 1

    model = FprLineage(initial)
    model.write("LWC1", 0, 1, be_bytes(word, 4), "load:decoy")
    payload, origins = model.read("SWC1", 1, 1)
    assert be_value(payload) == word
    assert all(not origin.startswith("load:decoy") for origin in origins)
    receipts.append(("equal-decoy-fr0-to-fr1", be_value(payload), origins))

    model = FprLineage(initial)
    model.write("LWC1", 1, 1, be_bytes(word, 4), "load:decoy2")
    payload, origins = model.read("SWC1", 0, 1)
    assert be_value(payload) == word
    assert all(not origin.startswith("load:decoy2") for origin in origins)
    receipts.append(("equal-decoy-fr1-to-fr0", be_value(payload), origins))

    model = FprLineage(initial)
    model.write("LWC1", 0, 1, be_bytes(word, 4), "load:overwrite")
    model.write("MTC1", 0, 1, be_bytes(word, 4), "mtc1:overwrite")
    payload, origins = model.read("SWC1", 0, 1)
    assert be_value(payload) == word
    assert all(origin.startswith("mtc1:overwrite") for origin in origins)
    receipts.append(("equal-overwrite", be_value(payload), origins))

    encoded = json.dumps(receipts, sort_keys=True, separators=(",", ":")).encode()
    return cases + 3, hashlib.sha256(encoded).hexdigest()


if __name__ == "__main__":
    count, digest = selftest()
    print(f"PASS: {count} COP1 lineage-model cases")
    print("model_sha256=" + digest)
