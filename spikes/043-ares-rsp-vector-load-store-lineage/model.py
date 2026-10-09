#!/usr/bin/env python3
"""Exact pinned-ares lane model for bounded RSP vector load->store lineage."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import random


@dataclass(frozen=True)
class Byte:
    value: int
    origin: str


class Machine:
    def __init__(self, fill: int = 0xCC, vector_fill=None):
        self.dmem = [Byte(fill, f"initial-dmem@{i:03x}") for i in range(4096)]
        if vector_fill is None:
            vector_fill = [(0xE0 + i) & 0xFF for i in range(16)]
        self.v = [Byte(vector_fill[i], f"initial-v2@{i}") for i in range(16)]
        self.reads = []
        self.writes = []

    def put(self, start, values, generation):
        for i, value in enumerate(values):
            a = (start + i) & 0xFFF
            self.dmem[a] = Byte(value & 0xFF, f"{generation}@{a:03x}")

    def lqv(self, address, e, generation):
        start = e
        end = min(16 + e - (address & 15), 16)
        for offset in range(start, end):
            a = address & 0xFFF
            b = self.dmem[a]
            self.v[offset & 15] = Byte(b.value, f"{generation}:{b.origin}")
            self.reads.append((generation, a, offset & 15, b.value, b.origin))
            address += 1

    def lrv(self, address, e, generation):
        start = 16 - ((address & 15) - e)
        address &= ~15
        for offset in range(start, 16):
            a = address & 0xFFF
            b = self.dmem[a]
            self.v[offset & 15] = Byte(b.value, f"{generation}:{b.origin}")
            self.reads.append((generation, a, offset & 15, b.value, b.origin))
            address += 1

    def mtc2(self, value, e, generation):
        self.v[e] = Byte((value >> 8) & 0xFF, f"{generation}:gpr")
        if e != 15:
            self.v[e + 1] = Byte(value & 0xFF, f"{generation}:gpr")

    def sqv(self, address, e, generation):
        start = e
        end = start + (16 - (address & 15))
        for offset in range(start, end):
            a = address & 0xFFF
            lane = offset & 15
            b = self.v[lane]
            self.dmem[a] = Byte(b.value, f"{generation}:{b.origin}")
            self.writes.append((generation, a, lane, b.value, b.origin))
            address += 1

    def srv(self, address, e, generation):
        start = e
        end = start + (address & 15)
        base = 16 - (address & 15)
        address &= ~15
        for offset in range(start, end):
            a = address & 0xFFF
            lane = (offset + base) & 15
            b = self.v[lane]
            self.dmem[a] = Byte(b.value, f"{generation}:{b.origin}")
            self.writes.append((generation, a, lane, b.value, b.origin))
            address += 1

    def values(self, start, size):
        return [self.dmem[(start + i) & 0xFFF].value for i in range(size)]

    def origins(self, start, size):
        return [self.dmem[(start + i) & 0xFFF].origin for i in range(size)]

    def vector_values(self):
        return [b.value for b in self.v]

    def vector_origins(self):
        return [b.origin for b in self.v]


def scenarios():
    out = {}

    m = Machine(vector_fill=[0xE0 + i for i in range(16)])
    src = [0x10 + i for i in range(16)]
    m.put(0x200, src, "src-a")
    m.put(0x300, [0x55] * 16, "dst-before")
    m.lqv(0x200, 0, "load-a")
    m.sqv(0x300, 0, "store-a")
    out["aligned_lqv_sqv"] = {
        "vector": m.vector_values(),
        "destination": m.values(0x300, 16),
        "origins": m.origins(0x300, 16),
    }
    assert out["aligned_lqv_sqv"]["destination"] == src
    assert all("load-a:src-a@" in x for x in out["aligned_lqv_sqv"]["origins"])

    init = [0xA0 + i for i in range(16)]
    m = Machine(vector_fill=init)
    src = [0x30 + i for i in range(11)]
    m.put(0x205, src, "partial-src")
    m.put(0x310, [0x55] * 16, "dst-before")
    m.lqv(0x205, 3, "partial-load")
    m.sqv(0x310, 0, "partial-store")
    expected = init[:]
    expected[3:14] = src
    out["partial_lqv_sqv"] = {
        "vector": m.vector_values(),
        "destination": m.values(0x310, 16),
        "origins": m.origins(0x310, 16),
    }
    assert out["partial_lqv_sqv"]["destination"] == expected
    assert all("initial-v2@" in x for x in out["partial_lqv_sqv"]["origins"][:3])
    assert all("partial-load:partial-src@" in x for x in out["partial_lqv_sqv"]["origins"][3:14])
    assert all("initial-v2@" in x for x in out["partial_lqv_sqv"]["origins"][14:])

    m = Machine(vector_fill=[0xF0 + i for i in range(16)])
    same = [0x70 + i for i in range(16)]
    m.put(0x400, same, "equal-a")
    m.put(0x500, same, "equal-b")
    m.put(0x520, [0x55] * 16, "dst-before")
    m.lqv(0x400, 0, "load-equal-a")
    m.lqv(0x500, 0, "load-equal-b")
    m.sqv(0x520, 0, "store-equal")
    out["equal_decoy_latest_load"] = {
        "vector": m.vector_values(),
        "destination": m.values(0x520, 16),
        "origins": m.origins(0x520, 16),
    }
    assert out["equal_decoy_latest_load"]["destination"] == same
    assert all("load-equal-b:equal-b@" in x for x in out["equal_decoy_latest_load"]["origins"])
    naive = [f"value-match:equal-a@{0x400+i:03x}" for i in range(16)]
    assert naive != out["equal_decoy_latest_load"]["origins"]

    m = Machine(vector_fill=[0xB0 + i for i in range(16)])
    src = [0x90 + i for i in range(11)]
    m.put(0x600, src, "lrv-src")
    m.put(0x700, [0x55] * 16, "dst-before")
    m.lrv(0x60B, 0, "lrv-load")
    m.srv(0x70B, 0, "srv-store")
    out["lrv_srv_effective_span"] = {
        "vector": m.vector_values(),
        "destination": m.values(0x700, 16),
        "origins": m.origins(0x700, 16),
        "read_addresses": [a for _, a, _, _, _ in m.reads],
        "write_addresses": [a for _, a, _, _, _ in m.writes],
    }
    assert out["lrv_srv_effective_span"]["destination"][:11] == src
    assert out["lrv_srv_effective_span"]["destination"][11:] == [0x55] * 5
    assert out["lrv_srv_effective_span"]["read_addresses"] == list(range(0x600, 0x60B))
    assert out["lrv_srv_effective_span"]["write_addresses"] == list(range(0x700, 0x70B))

    m = Machine(fill=0x44, vector_fill=[0x44] * 16)
    m.put(0x805, [0x44] * 11, "same-a")
    m.put(0x900, [0x44] * 11, "same-b")
    m.put(0xA00, [0x44] * 16, "same-dst-before")
    m.lqv(0x805, 3, "same-load-a")
    m.lrv(0x90B, 0, "same-load-b")
    m.sqv(0xA00, 0, "same-store")
    out["mixed_same_value_no_diff"] = {
        "vector": m.vector_values(),
        "destination": m.values(0xA00, 16),
        "origins": m.origins(0xA00, 16),
    }
    assert out["mixed_same_value_no_diff"]["destination"] == [0x44] * 16
    origins = out["mixed_same_value_no_diff"]["origins"]
    assert all("initial-v2@" in x for x in origins[:3])
    assert all("same-load-a:same-a@" in x for x in origins[3:5])
    assert all("same-load-b:same-b@" in x for x in origins[5:])
    assert len(set(out["mixed_same_value_no_diff"]["destination"])) == 1

    m = Machine(vector_fill=[0xD0 + i for i in range(16)])
    src = [0x20 + i for i in range(16)]
    m.put(0xB00, src, "clobber-src")
    m.put(0xC00, [0x55] * 16, "dst-before")
    m.lqv(0xB00, 0, "clobber-load")
    m.mtc2(0xCAFE, 6, "mtc2-r4")
    m.sqv(0xC00, 0, "clobber-store")
    expected = src[:]
    expected[6:8] = [0xCA, 0xFE]
    out["mtc2_clobber"] = {
        "vector": m.vector_values(),
        "destination": m.values(0xC00, 16),
        "origins": m.origins(0xC00, 16),
    }
    assert out["mtc2_clobber"]["destination"] == expected
    assert "mtc2-r4:gpr" in out["mtc2_clobber"]["origins"][6]
    assert "mtc2-r4:gpr" in out["mtc2_clobber"]["origins"][7]
    return out


def fuzz():
    rng = random.Random(0x504C414944)
    trials = 4096
    ambiguous = 0
    partial_mixed = 0
    for _ in range(trials):
        value = rng.randrange(256)
        e = rng.randrange(0, 8)
        low = rng.randrange(0, 16)
        address_a = 0x100 + low
        address_b = 0x200 + low
        m = Machine(fill=value, vector_fill=[value] * 16)
        m.put(address_a, [value] * 32, "a")
        m.put(address_b, [value] * 32, "b")
        m.lqv(address_a, e, "ga")
        before = m.vector_origins()
        m.lqv(address_b, e, "gb")
        after = m.vector_origins()
        if before != after and m.vector_values() == [value] * 16:
            ambiguous += 1
        if any(x.startswith("initial-v2") for x in after) and any(x.startswith("gb:") for x in after):
            partial_mixed += 1
    assert ambiguous == trials
    assert partial_mixed > 0
    return {"trials": trials, "value_only_ambiguous": ambiguous, "partial_mixed": partial_mixed}


def main():
    cases = scenarios()
    result = {
        "cases": cases,
        "fuzz": fuzz(),
        "conclusions": {
            "vector_register_requires_lane_origins": True,
            "same_value_load_generation_is_not_content_diff": True,
            "lrv_srv_effective_addresses_are_aligned_span_not_nominal_base": True,
            "mtc2_cuts_only_written_lanes": True,
        },
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    result["sha256"] = hashlib.sha256(canonical).hexdigest()
    print(json.dumps(result, sort_keys=True))
    print("PASS")


if __name__ == "__main__":
    main()
