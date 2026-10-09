#!/usr/bin/env python3
"""Deterministic replay model for RSP-DMEM producer -> CPU LW/SW -> SP-IMEM."""
from __future__ import annotations
from dataclasses import dataclass
import copy, hashlib, json, random

@dataclass(frozen=True)
class Origin:
    kind: str
    generation: int
    detail: str

@dataclass
class RegGen:
    value: int
    origins: tuple[Origin, Origin, Origin, Origin] | None
    cause: str

class Replay:
    def __init__(self):
        self.ordinal = 0
        self.dmem = [0x34, 0x08, 0x00, 0xaa, 0xaa, 0xee, 0x77, 0x22]
        self.dorig = [Origin("initial", 0, f"dmem:{i}") for i in range(8)]
        self.imem = [0] * 32
        self.iorig = [Origin("initial", 0, f"imem:{i}") for i in range(32)]
        self.reg: dict[int, RegGen] = {}
        self.certs = []

    def _gen(self, kind, detail):
        self.ordinal += 1
        return Origin(kind, self.ordinal, detail)

    @staticmethod
    def bytes32(v): return tuple((v >> s) & 0xff for s in (24, 16, 8, 0))
    @staticmethod
    def word(bs): return (bs[0]<<24)|(bs[1]<<16)|(bs[2]<<8)|bs[3]

    def dmem_write(self, off, width, value, kind, detail):
        bs = tuple((value >> (8*(width-1-i))) & 0xff for i in range(width))
        for i,b in enumerate(bs):
            p=(off+i)&0xfff
            if p < len(self.dmem):
                self.dmem[p]=b; self.dorig[p]=self._gen(kind, f"{detail}:byte{i}")

    def cpu_lw(self, rt, off, phase):
        bs=tuple(self.dmem[off:off+4]); origins=tuple(self.dorig[off:off+4])
        self.reg[rt]=RegGen(self.word(bs), origins, f"lw@{phase}")

    def cpu_clobber(self, rt, value, phase):
        self.reg[rt]=RegGen(value, None, f"clobber@{phase}")

    def cpu_sw_imem(self, rt, off, phase):
        g=self.reg[rt]; bs=self.bytes32(g.value)
        for i,b in enumerate(bs):
            self.imem[off+i]=b
            self.iorig[off+i]=self._gen("cpu_imem_sink", f"phase{phase}:byte{i}")
        if g.origins is not None:
            self.certs.append({"phase":phase,"offset":off,"value":g.value,
                               "ancestry":[o.__dict__ for o in g.origins],
                               "reg_cause":g.cause})

def canonical_scenario():
    r=Replay()
    for i,b in enumerate((0x11,0x22,0x33,0x44)):
        r.dmem_write(i,1,b,"rsp_sw",f"rsp-sw-1-off{i}")
    r.cpu_lw(8,0,2); r.cpu_sw_imem(8,0,3)
    pure1=copy.deepcopy(r.certs[-1])
    for i,b in enumerate((0x11,0x22,0x33,0x44)):
        r.dmem_write(i,1,b,"rsp_sw",f"rsp-sw-2-off{i}")
    r.cpu_lw(8,0,5); r.cpu_sw_imem(8,4,6)
    pure2=copy.deepcopy(r.certs[-1])
    assert pure1["value"] == pure2["value"] == 0x11223344
    assert [x["generation"] for x in pure1["ancestry"]] != [x["generation"] for x in pure2["ancestry"]]
    r.dmem_write(0,4,0xaabbccdd,"cpu_sp_write","cpu-word")
    r.dmem_write(1,1,0xee,"unknown","foreign-byte")
    r.dmem_write(2,1,0x77,"rsp_vector","sbv-byte2")
    r.dmem_write(3,1,0x22,"rsp_scalar","sb-byte3")
    assert r.word(r.dmem[:4]) == 0xaaee7722
    r.cpu_lw(8,0,11)
    r.dmem[4:8]=r.dmem[:4]
    r.dorig[4:8]=[Origin("initial-decoy",0,f"dmem:{i}") for i in range(4,8)]
    r.cpu_lw(9,4,12)
    r.cpu_sw_imem(8,8,13)
    mixed=copy.deepcopy(r.certs[-1])
    assert [x["kind"] for x in mixed["ancestry"]] == ["cpu_sp_write","unknown","rsp_vector","rsp_scalar"]
    r.cpu_clobber(8,0xaaee7722,14)
    before=len(r.certs); r.cpu_sw_imem(8,12,15); assert len(r.certs)==before
    return {"pure_first":pure1,"pure_same_value_second":pure2,"mixed":mixed,
            "uncertified_same_value_clobber":{"value":0xaaee7722,"offset":12}}

def naive_whole_word(source_words, copied_value):
    matches=[s for s in source_words if s["value"]==copied_value]
    return matches[-1]["label"] if matches else None

def adversarial():
    canonical_scenario()
    sources=[{"label":"mixed-true","value":0xaaee7722},{"label":"equal-decoy","value":0xaaee7722}]
    assert naive_whole_word(sources,0xaaee7722)=="equal-decoy"
    rng=random.Random(0x504c414944);bad=0;trials=5000
    for t in range(trials):
        value=rng.getrandbits(32); bytes_=[(value>>s)&0xff for s in (24,16,8,0)]
        origins=[]
        for i,b in enumerate(bytes_): origins.append((rng.choice(["A","A","B","UNKNOWN"]),t*4+i,b))
        if len({o[0] for o in origins})>1:
            bad+=1
            assert naive_whole_word([{"label":"old-A","value":value}],value)=="old-A"
    assert bad > 4000
    return {"trials":trials,"mixed_histories":bad,"value_only_false_single_source":bad}

def main():
    out={"result":"VALIDATED_MODEL","scenario":canonical_scenario(),"adversarial":adversarial()}
    raw=(json.dumps(out,sort_keys=True,separators=(",",":"))+"\n").encode()
    print(json.dumps(out,indent=2,sort_keys=True))
    print("MODEL_SHA256="+hashlib.sha256(raw).hexdigest())

if __name__ == '__main__': main()
