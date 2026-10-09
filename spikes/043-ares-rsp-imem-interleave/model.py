#!/usr/bin/env python3
"""Adversarial model for SP-DMA row grouping versus per-byte IMEM writers."""
import hashlib
import json
import random

SIZE = 4096


def fresh():
    return {"value": bytearray(SIZE), "origin": ["initial"] * SIZE, "revision": [0] * SIZE}


def write(state, addr, data, origin):
    for i, byte in enumerate(data):
        at = (addr + i) & 0xFFF
        state["value"][at] = byte
        state["origin"][at] = origin
        state["revision"][at] += 1


def dma_row(state, transfer, row, addr, data):
    write(state, addr, data, f"dma:{transfer}:row:{row}")


def cpu_word(state, ident, addr, value):
    write(state, addr, value.to_bytes(4, "big"), f"cpu:{ident}")


def naive_retag(state, transfer, rows):
    """Deliberately unsound completion rule: DMA retakes every span it ever touched."""
    for row, addr, data in rows:
        for i in range(len(data)):
            state["origin"][(addr + i) & 0xFFF] = f"dma:{transfer}:row:{row}"


def clone(state):
    return {"value": bytearray(state["value"]), "origin": list(state["origin"]), "revision": list(state["revision"])}


def fixed_cases():
    d0 = bytes.fromhex("1111111122222222")
    d1 = bytes.fromhex("3333333344444444")

    s = fresh(); rows = []
    rows.append((0, 0x200, d0)); dma_row(s, "T", 0, 0x200, d0)
    cpu_word(s, "after", 0x200, 0xAAAAAAAA)
    rows.append((1, 0x208, d1)); dma_row(s, "T", 1, 0x208, d1)
    n = clone(s); naive_retag(n, "T", rows)
    assert s["origin"][0x200:0x204] == ["cpu:after"] * 4
    after_completed_row = sum(a != b for a, b in zip(s["origin"], n["origin"]))

    s = fresh(); rows = []
    rows.append((0, 0x200, d0)); dma_row(s, "T", 0, 0x200, d0)
    cpu_word(s, "future", 0x208, 0xBBBBBBBB)
    rows.append((1, 0x208, d1)); dma_row(s, "T", 1, 0x208, d1)
    n = clone(s); naive_retag(n, "T", rows)
    assert s["origin"][0x208:0x20C] == ["dma:T:row:1"] * 4
    before_later_row = sum(a != b for a, b in zip(s["origin"], n["origin"]))

    s = fresh(); rows = []
    rows.append((0, 0x200, d0)); dma_row(s, "T", 0, 0x200, d0)
    old = int.from_bytes(s["value"][0x200:0x204], "big")
    rev = s["revision"][0x200]
    cpu_word(s, "same", 0x200, old)
    assert int.from_bytes(s["value"][0x200:0x204], "big") == old
    assert s["revision"][0x200] == rev + 1
    rows.append((1, 0x208, d1)); dma_row(s, "T", 1, 0x208, d1)
    n = clone(s); naive_retag(n, "T", rows)
    same_value = sum(a != b for a, b in zip(s["origin"], n["origin"]))

    s = fresh(); rows = []
    w0 = bytes.fromhex("5555555566666666")
    w1 = bytes.fromhex("7777777788888888")
    rows.append((0, 0xFF8, w0)); dma_row(s, "W", 0, 0xFF8, w0)
    cpu_word(s, "survive", 0xFF8, 0xCCCCCCCC)
    cpu_word(s, "die", 0x000, 0xDDDDDDDD)
    rows.append((1, 0x000, w1)); dma_row(s, "W", 1, 0x000, w1)
    n = clone(s); naive_retag(n, "W", rows)
    assert s["origin"][0xFF8:0xFFC] == ["cpu:survive"] * 4
    assert s["origin"][0:4] == ["dma:W:row:1"] * 4
    wrap = sum(a != b for a, b in zip(s["origin"], n["origin"]))

    return {
        "after_completed_row": after_completed_row,
        "before_later_row": before_later_row,
        "same_value": same_value,
        "wrap": wrap,
    }


def fuzz(seed=0x504C414944, histories=5000):
    rng = random.Random(seed)
    naive_bad = 0
    same_value = 0
    surviving_cpu_bytes = 0
    for h in range(histories):
        s = fresh()
        rows = []
        transfer = f"F{h}"
        count = rng.randint(2, 4)
        base = rng.randrange(0, 512) * 8
        if h % 7 == 0:
            base = 0xFF8
        for row in range(count):
            addr = (base + row * 8) & 0xFFF
            data = bytes(rng.getrandbits(8) for _ in range(8))
            rows.append((row, addr, data))
            dma_row(s, transfer, row, addr, data)
            if row != count - 1 and rng.random() < 0.8:
                kind = rng.choice(["completed", "future", "unrelated"])
                if kind == "completed":
                    target = (base + rng.randint(0, row) * 8) & 0xFFF
                elif kind == "future":
                    target = (base + rng.randint(row + 1, count - 1) * 8) & 0xFFF
                else:
                    target = (base + 0x200 + rng.randrange(0, 8) * 4) & 0xFFF
                target &= ~3
                old = int.from_bytes(bytes(s["value"][(target + i) & 0xFFF] for i in range(4)), "big")
                if rng.random() < 0.35:
                    value = old
                    same_value += 1
                else:
                    value = rng.getrandbits(32)
                cpu_word(s, f"{h}:{row}", target, value)
        n = clone(s)
        naive_retag(n, transfer, rows)
        mismatches = sum(a != b for a, b in zip(s["origin"], n["origin"]))
        if mismatches:
            naive_bad += 1
            surviving_cpu_bytes += mismatches
    return {
        "histories": histories,
        "naive_bad_histories": naive_bad,
        "same_value_cpu_writes": same_value,
        "surviving_cpu_bytes_misclassified": surviving_cpu_bytes,
    }


def main():
    fixed = fixed_cases()
    randomized = fuzz()
    result = {"fixed_misclassified_bytes": fixed, "fuzz": randomized}
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["sha256"] = hashlib.sha256(payload).hexdigest()
    assert fixed == {"after_completed_row": 4, "before_later_row": 0, "same_value": 4, "wrap": 4}
    assert randomized["naive_bad_histories"] > 0
    assert randomized["same_value_cpu_writes"] > 0
    print(json.dumps(result, sort_keys=True))
    print("PASS")


if __name__ == "__main__":
    main()
