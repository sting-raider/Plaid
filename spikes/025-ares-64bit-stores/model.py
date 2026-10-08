#!/usr/bin/env python3
"""Independent model for the pinned ares VR4300 SD/SDL/SDR decomposition."""
from __future__ import annotations
import hashlib
import json

DATA = 0x1122334455667788
SIZES = {"Byte": 1, "Half": 2, "Word": 4, "Dual": 8}

# (size, offset within aligned 8-byte window, right shift)
SDL = {
    "little": {
        0: [("Byte",0,56)],
        1: [("Half",0,48)],
        2: [("Byte",2,56),("Half",0,40)],
        3: [("Word",0,32)],
        4: [("Byte",4,56),("Word",0,24)],
        5: [("Half",4,48),("Word",0,16)],
        6: [("Byte",6,56),("Half",4,40),("Word",0,8)],
        7: [("Dual",0,0)],
    },
    "big": {
        0: [("Dual",0,0)],
        1: [("Byte",1,56),("Half",2,40),("Word",4,8)],
        2: [("Half",2,48),("Word",4,16)],
        3: [("Byte",3,56),("Word",4,24)],
        4: [("Word",4,32)],
        5: [("Byte",5,56),("Half",6,40)],
        6: [("Half",6,48)],
        7: [("Byte",7,56)],
    },
}
SDR = {
    "little": {
        0: [("Dual",0,0)],
        1: [("Word",4,24),("Half",2,8),("Byte",1,0)],
        2: [("Word",4,16),("Half",2,0)],
        3: [("Word",4,8),("Byte",3,0)],
        4: [("Word",4,0)],
        5: [("Half",6,8),("Byte",5,0)],
        6: [("Half",6,0)],
        7: [("Byte",7,0)],
    },
    "big": {
        0: [("Byte",0,0)],
        1: [("Half",0,0)],
        2: [("Half",0,8),("Byte",2,0)],
        3: [("Word",0,0)],
        4: [("Word",0,8),("Byte",4,0)],
        5: [("Word",0,16),("Half",4,0)],
        6: [("Word",0,24),("Half",4,8),("Byte",6,0)],
        7: [("Dual",0,0)],
    },
}

def subwrites(op: str, endian: str, offset: int):
    if op == "SD":
        return [("Dual",0,0)] if offset == 0 else []
    return (SDL if op == "SDL" else SDR)[endian][offset]

def apply(mem: bytearray, base: int, writes, endian: str, data: int = DATA):
    for kind, off, shift in writes:
        size = SIZES[kind]
        value = (data >> shift) & ((1 << (size * 8)) - 1)
        mem[base+off:base+off+size] = value.to_bytes(size, endian)

def changed_mask(op: str, endian: str, offset: int):
    before = bytearray(range(0x90, 0xA0))
    after = bytearray(before)
    apply(after, 0, subwrites(op,endian,offset), endian)
    return [i for i,(a,b) in enumerate(zip(before,after)) if a != b]

def test_pairs():
    for endian in ("big","little"):
        for target in range(1,8):
            mem = bytearray([0xCC] * 24)
            if endian == "big":
                left_addr, right_addr = target, target + 7
            else:
                left_addr, right_addr = target + 7, target
            lbase, loff = left_addr & ~7, left_addr & 7
            rbase, roff = right_addr & ~7, right_addr & 7
            apply(mem, lbase, SDL[endian][loff], endian)
            apply(mem, rbase, SDR[endian][roff], endian)
            expected = DATA.to_bytes(8,endian)
            got = bytes(mem[target:target+8])
            assert got == expected, (endian,target,got.hex(),expected.hex())
            assert mem[target-1] == 0xCC and mem[target+8] == 0xCC

def test_widths():
    for endian in ("big","little"):
        for op in ("SDL","SDR"):
            for offset in range(8):
                writes = subwrites(op,endian,offset)
                byte_count = sum(SIZES[k] for k,_,_ in writes)
                lanes=[]
                for k,off,_ in writes: lanes += list(range(off,off+SIZES[k]))
                assert len(lanes)==len(set(lanes))==byte_count
                assert 1 <= byte_count <= 8
    assert subwrites("SD","big",0) == [("Dual",0,0)]
    assert subwrites("SD","little",1) == []

def main():
    test_widths(); test_pairs()
    result={}
    for endian in ("big","little"):
        result[endian]={}
        for op in ("SD","SDL","SDR"):
            result[endian][op]={str(o):{"writes":subwrites(op,endian,o),"changed":changed_mask(op,endian,o)} for o in range(8)}
    payload=json.dumps(result,sort_keys=True,separators=(",",":")).encode()
    print("PASS: decomposition widths/lane uniqueness and unaligned SDL+SDR pairs")
    print("sha256",hashlib.sha256(payload).hexdigest())
    print(json.dumps(result,sort_keys=True,indent=2))
if __name__ == "__main__": main()
