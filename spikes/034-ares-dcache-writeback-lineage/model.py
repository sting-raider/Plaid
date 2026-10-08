#!/usr/bin/env python3
"""Deterministic fail-closed model for versioned D-cache -> RDRAM writeback lineage."""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib, json, random

LINE_BYTES = 16

@dataclass
class Line:
    generation: int = 0
    resident: bool = False
    tag: int = 0
    payload: list[int] = field(default_factory=lambda: [0] * LINE_BYTES)
    origins: list[str] = field(default_factory=lambda: ["unknown"] * LINE_BYTES)
    dirty: set[int] = field(default_factory=set)

@dataclass
class Pending:
    slot: int
    generation: int
    address: int
    payload: tuple[int, ...]
    origins: tuple[str, ...]

class Verifier:
    def __init__(self):
        self.lines: dict[int, Line] = {}
        self.pending: Pending | None = None
        self.backing: dict[int, str] = {}
        self.certificates: list[dict] = []
        self.unknown_writes = 0
        self.next_generation = 1

    def line(self, slot: int) -> Line:
        return self.lines.setdefault(slot, Line())

    def fill(self, slot: int, address: int, payload: bytes, event: str):
        assert len(payload) == LINE_BYTES and address % LINE_BYTES == 0
        if self.pending is not None:
            self.pending = None
        line = self.line(slot)
        line.generation = self.next_generation; self.next_generation += 1
        line.resident = True
        line.tag = address & ~0xfff
        line.payload[:] = payload
        line.origins[:] = [f"fill:{event}:{address+i:#x}" for i in range(LINE_BYTES)]
        line.dirty.clear()

    def store(self, slot: int, paddr: int, data: bytes, event: str):
        line = self.line(slot)
        assert line.resident
        base = line.tag | ((paddr & 0xff0))
        assert base <= paddr and paddr + len(data) <= base + LINE_BYTES
        off = paddr - base
        for i, b in enumerate(data):
            line.payload[off+i] = b
            line.origins[off+i] = f"store:{event}:{i}"
            line.dirty.add(off+i)

    def wb_begin(self, slot: int, address: int):
        line = self.line(slot)
        assert self.pending is None
        if not line.resident or not line.dirty:
            return
        expected = line.tag | (address & 0xff0)
        if expected != address:
            return
        self.pending = Pending(slot, line.generation, address,
                               tuple(line.payload), tuple(line.origins))

    def backing_write(self, address: int, payload: bytes):
        if (self.pending is None or self.pending.address != address or
            self.pending.payload != tuple(payload)):
            self.unknown_writes += 1
            return False
        p = self.pending
        line = self.line(p.slot)
        if not line.resident or line.generation != p.generation:
            self.pending = None
            self.unknown_writes += 1
            return False
        for i, origin in enumerate(p.origins):
            self.backing[address+i] = origin
        self.certificates.append({
            "slot": p.slot, "generation": p.generation, "address": address,
            "origins": list(p.origins),
        })
        return True

    def wb_end(self, slot: int):
        if self.pending is not None and self.pending.slot == slot:
            self.pending = None

    def invalidate(self, slot: int):
        line = self.line(slot)
        line.resident = False
        line.generation = self.next_generation; self.next_generation += 1
        line.dirty.clear()
        if self.pending is not None and self.pending.slot == slot:
            self.pending = None


def line_payload(first_word: int, tail=(0x10203040,0x50607080,0x90a0b0c0)) -> bytes:
    words = (first_word,) + tuple(tail)
    return b"".join(x.to_bytes(4, "big") for x in words)


def fixed_cases():
    report = {}
    A, B, SLOT = 0x1000, 0x3000, 0x100
    original = line_payload(0x11111111)
    mutated_word = 0xA1B2C3D4
    mutated = mutated_word.to_bytes(4,"big") + original[4:]

    v = Verifier(); v.fill(SLOT,A,original,"a-fill"); v.store(SLOT,A,mutated[:4],"a-store")
    v.wb_begin(SLOT,A); ok = v.backing_write(A,mutated); v.wb_end(SLOT)
    assert ok and all(v.backing[A+i].startswith("store:a-store") for i in range(4))
    assert all(v.backing[A+i].startswith("fill:a-fill") for i in range(4,16))
    report["explicit_writeback"] = {"certificates":len(v.certificates),"unknown":v.unknown_writes}

    v = Verifier(); v.fill(SLOT,A,original,"e-fill"); v.store(SLOT,A,mutated[:4],"e-store")
    v.wb_begin(SLOT,A); ok = v.backing_write(A,mutated); v.wb_end(SLOT); v.fill(SLOT,B,original,"e-replace")
    assert ok and len(v.certificates)==1 and v.line(SLOT).tag == 0x3000
    report["dirty_eviction"] = {"certificates":1,"new_generation":v.line(SLOT).generation}

    v = Verifier(); v.fill(SLOT,A,original,"c-a"); v.fill(SLOT,B,original,"c-b")
    assert not v.certificates and v.unknown_writes==0
    report["clean_replacement"] = {"certificates":0}

    v = Verifier(); v.fill(SLOT,A,original,"i-fill"); v.store(SLOT,A,mutated[:4],"i-store"); v.invalidate(SLOT)
    forged = v.backing_write(A,mutated)
    assert not forged and not v.certificates and v.unknown_writes==1
    report["invalidate_drop"] = {"forged_equal_write_certified":forged,"unknown":1}

    v = Verifier(); v.fill(SLOT,A,original,"t-a"); v.store(SLOT,A,mutated[:4],"t-store"); v.fill(SLOT,B,mutated,"t-b")
    v.wb_begin(SLOT,A); forged = v.backing_write(A,mutated); v.wb_end(SLOT)
    assert not forged
    report["same_payload_wrong_generation"] = {"certified":forged,"unknown":v.unknown_writes}
    return report


def fuzz(seed=0xDCA6E, histories=3000, steps=120):
    rng = random.Random(seed)
    A, B, SLOT = 0x1000, 0x3000, 0x100
    payloads = [line_payload(x) for x in (0x11111111,0x22222222,0xA1B2C3D4)]
    forged_rejected = certs = 0
    for h in range(histories):
        v = Verifier()
        for s in range(steps):
            op = rng.randrange(7)
            line = v.line(SLOT)
            if op == 0:
                addr = A if rng.randrange(2)==0 else B
                v.fill(SLOT, addr, rng.choice(payloads), f"f{h}-{s}")
            elif op == 1 and line.resident:
                base = line.tag | (A & 0xff0)
                if line.tag == (B & ~0xfff): base = B
                off = rng.choice((0,4,8,12))
                v.store(SLOT, base+off, rng.getrandbits(32).to_bytes(4,"big"), f"s{h}-{s}")
            elif op == 2 and line.resident and v.pending is None:
                addr = A if line.tag == (A & ~0xfff) else B
                v.wb_begin(SLOT, addr)
            elif op == 3:
                if v.pending is not None and rng.randrange(4):
                    p=v.pending; ok=v.backing_write(p.address,bytes(p.payload)); certs += int(ok)
                else:
                    ok=v.backing_write(rng.choice((A,B)), rng.choice(payloads)); forged_rejected += int(not ok)
            elif op == 4:
                v.wb_end(SLOT)
            elif op == 5:
                v.invalidate(SLOT)
            else:
                # Clean replacement only when line is clean; otherwise skip to avoid modeling an omitted writeback.
                if line.resident and not line.dirty:
                    addr = B if line.tag==(A&~0xfff) else A
                    v.fill(SLOT,addr,rng.choice(payloads),f"r{h}-{s}")
    return {"seed":seed,"histories":histories,"steps":steps,"certificates":certs,"forged_rejected":forged_rejected}


def main():
    report={"fixed":fixed_cases(),"fuzz":fuzz()}
    canonical=json.dumps(report,sort_keys=True,separators=(",",":"))
    print(json.dumps(report,indent=2,sort_keys=True))
    print("REPORT_SHA256="+hashlib.sha256(canonical.encode()).hexdigest())

if __name__ == "__main__": main()
