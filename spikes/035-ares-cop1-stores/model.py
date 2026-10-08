#!/usr/bin/env python3
"""Independent model for VR4300 COP1 store payload selection and fault ordering."""
from __future__ import annotations
import hashlib, json, random

R0 = 0x1122334455667788
R1 = 0x99aabbccddeeff00
R2 = 0x0123456789abcdef
R3 = 0xfedcba9876543210
REGS = [R0, R1, R2, R3]


def select_u32(fr: int, ft: int, regs=REGS) -> int:
    if fr:
        return regs[ft] & 0xffffffff
    base = regs[ft & ~1]
    return (base >> (32 if ft & 1 else 0)) & 0xffffffff


def select_u64(fr: int, ft: int, regs=REGS) -> int:
    return regs[ft if fr else (ft & ~1)] & 0xffffffffffffffff


def expected_exception(op: str, cu1: bool, mode: str, offset: int) -> tuple[int,int]:
    if not cu1:
        return 11, 1
    align = 4 if op == 'SWC1' else 8
    if offset % align:
        return 5, 0
    if mode == 'tlbmiss':
        return 3, 0
    return 0, 0


def payload_bytes(op: str, fr: int, ft: int, endian: str) -> bytes:
    n = 4 if op == 'SWC1' else 8
    value = select_u32(fr, ft) if n == 4 else select_u64(fr, ft)
    return value.to_bytes(n, endian)


def main() -> None:
    facts=[]
    for fr in (0,1):
        for ft in range(4):
            facts.append({'fr':fr,'ft':ft,'u32':select_u32(fr,ft),'u64':select_u64(fr,ft)})
    assert select_u32(0,0)==0x55667788
    assert select_u32(0,1)==0x11223344
    assert select_u64(0,0)==R0 and select_u64(0,1)==R0
    assert select_u32(1,1)==0xddeeff00 and select_u64(1,1)==R1
    for op in ('SWC1','SDC1'):
      for fr in (0,1):
       for ft in range(4):
        for endian in ('big','little'):
         p=payload_bytes(op,fr,ft,endian)
         assert len(p)==(4 if op=='SWC1' else 8)
    for op in ('SWC1','SDC1'):
      for mode in ('uncached','cached','tlbmiss'):
       for offset in range(8):
        assert expected_exception(op,False,mode,offset)==(11,1)
    rng=random.Random(0xC0F1)
    for _ in range(100000):
        regs=[rng.getrandbits(64) for _ in range(32)]
        ft=rng.randrange(32); fr=rng.randrange(2)
        if fr:
            assert select_u32(fr,ft,regs)==(regs[ft]&0xffffffff)
            assert select_u64(fr,ft,regs)==regs[ft]
        else:
            base=regs[ft&~1]
            assert select_u32(fr,ft,regs)==((base>>(32 if ft&1 else 0))&0xffffffff)
            assert select_u64(fr,ft,regs)==base
    encoded=(json.dumps(facts,sort_keys=True,separators=(',',':'))+'\n').encode()
    print('PASS: COP1 FR payload-selection model and 100000 adversarial register cases')
    print('model_sha256='+hashlib.sha256(encoded).hexdigest())

if __name__=='__main__': main()
