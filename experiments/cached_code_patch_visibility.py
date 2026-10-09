#!/usr/bin/env python3
"""Finite adversarial reducer for cached CPU code-patch fetch visibility.
Project-owned model only; it does not emulate the CPU.
"""
import copy, hashlib, json

PLAID = "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256"
ARES = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
BLOBS = {
    "ares/n64/cpu/cpu.hpp": "b51000d99e1e8818ad04a8c747a8170b0e98fae8",
    "ares/n64/cpu/dcache.cpp": "4de28e0ad9566d31f47210a997c22fa994785d26",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/cpu/interpreter-ipu.cpp": "938ccbd0af1f127439d9859c1fd6be2bbd5222a3",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2",
}
BASE = 0x2000
OLD = bytes.fromhex("111122223333444455556666777788889999aaaabbbbccccddddeeeeffff0000")
NEW = bytes.fromhex("a1b2c3d4")


def need(x, why):
    if not x: raise AssertionError(why)


def origin(kind, rev, event): return (kind, rev, event)


class M:
    def __init__(self):
        self.n=0; self.ev=[]; self.back=bytearray(OLD); self.bg=0
        self.bo=[origin("initial",0,0) for _ in OLD]
        self.i=None; self.d=None
    def emit(self,k,**d):
        self.n+=1; self.ev.append({"n":self.n,"k":k,"d":d}); return self.n
    def fill_i(self):
        r=self.emit("ir",base=BASE,payload=self.back.hex(),bg=self.bg)
        gen=0 if self.i is None else self.i["gen"]+1
        self.i={"data":bytearray(self.back),"o":list(self.bo),"gen":gen,"valid":True}
        self.emit("ifill",base=BASE,read=r,gen=gen,payload=self.i["data"].hex())
    def fill_d(self):
        r=self.emit("dr",base=BASE,payload=self.back.hex(),bg=self.bg)
        gen=0 if self.d is None else self.d["gen"]+1
        self.d={"data":bytearray(self.back),"o":list(self.bo),"gen":gen,"rev":0,"dirty":False,"valid":True}
        self.emit("dfill",base=BASE,read=r,gen=gen,payload=self.d["data"].hex())
    def store(self,off,payload,label):
        if self.d is None or not self.d["valid"]: self.fill_d()
        e=self.emit("store",base=BASE,off=off,width=len(payload),payload=payload.hex(),label=label,gen=self.d["gen"],prior=self.d["rev"])
        self.d["rev"]+=1; o=origin(label,self.d["rev"],e)
        self.d["data"][off:off+len(payload)]=payload; self.d["o"][off:off+len(payload)]=[o]*len(payload); self.d["dirty"]=True
        return e
    def wb(self):
        need(self.d and self.d["dirty"],"writeback without dirty D-cache")
        e=self.emit("wb",base=BASE,width=len(self.d["data"]),payload=self.d["data"].hex(),gen=self.d["gen"],rev=self.d["rev"])
        self.back[:]=self.d["data"]; self.bo=list(self.d["o"]); self.bg+=1; self.d["dirty"]=False
        self.emit("bg",gen=self.bg,wb=e); return e
    def inv_i(self):
        need(self.i is not None,"invalidate without I-cache"); self.i["valid"]=False
        self.emit("iinv",base=BASE,gen=self.i["gen"])
    def fetch(self,off=0):
        if self.i is None or not self.i["valid"]: self.fill_i()
        v=bytes(self.i["data"][off:off+4]); oo=self.i["o"][off:off+4]
        e=self.emit("fetch",base=BASE,off=off,value=v.hex(),gen=self.i["gen"],oe=[x[2] for x in oo],ok=[x[0] for x in oo])
        return e,v,oo


def replay(events):
    back=bytearray(OLD); bo=[origin("initial",0,0) for _ in OLD]; bg=0; i=d=None
    last=None; ir=dr=None; last_wb=None; fetch_o={}
    for want,e in enumerate(events,1):
        need(e["n"]==want,"noncontiguous ordinal"); k=e["k"]; x=e["d"]
        if k=="ir":
            need(x["base"]==BASE and bytes.fromhex(x["payload"])==bytes(back) and x["bg"]==bg,"bad I-cache read"); ir=(e["n"],bytearray(back),list(bo))
        elif k=="ifill":
            need(last=="ir" and ir and x["read"]==ir[0] and bytes.fromhex(x["payload"])==bytes(ir[1]),"bad I-cache fill")
            gen=0 if i is None else i["gen"]+1; need(x["gen"]==gen,"bad I-cache generation"); i={"data":ir[1],"o":ir[2],"gen":gen,"valid":True}
        elif k=="dr":
            need(x["base"]==BASE and bytes.fromhex(x["payload"])==bytes(back) and x["bg"]==bg,"bad D-cache read"); dr=(e["n"],bytearray(back),list(bo))
        elif k=="dfill":
            need(last=="dr" and dr and x["read"]==dr[0] and bytes.fromhex(x["payload"])==bytes(dr[1]),"bad D-cache fill")
            gen=0 if d is None else d["gen"]+1; need(x["gen"]==gen,"bad D-cache generation"); d={"data":dr[1],"o":dr[2],"gen":gen,"rev":0,"dirty":False,"valid":True}
        elif k=="store":
            need(d and d["valid"] and x["base"]==BASE and x["gen"]==d["gen"] and x["prior"]==d["rev"],"bad cached store identity")
            p=bytes.fromhex(x["payload"]); need(x["width"]==len(p) and 0<=x["off"]<=len(d["data"])-len(p),"bad cached store span")
            d["rev"]+=1; o=origin(x["label"],d["rev"],e["n"]); d["data"][x["off"]:x["off"]+len(p)]=p; d["o"][x["off"]:x["off"]+len(p)]=[o]*len(p); d["dirty"]=True
        elif k=="wb":
            need(d and d["valid"] and d["dirty"] and x["base"]==BASE and x["width"]==len(d["data"]),"bad writeback state")
            need(x["gen"]==d["gen"] and x["rev"]==d["rev"] and bytes.fromhex(x["payload"])==bytes(d["data"]),"bad writeback identity/payload")
            back[:]=d["data"]; bo=list(d["o"]); bg+=1; d["dirty"]=False; last_wb=e["n"]
        elif k=="bg": need(last=="wb" and x["gen"]==bg and x["wb"]==last_wb,"bad backing generation")
        elif k=="iinv": need(i and x["base"]==BASE and x["gen"]==i["gen"],"bad I-cache invalidate"); i["valid"]=False
        elif k=="fetch":
            need(i and i["valid"] and x["base"]==BASE and x["gen"]==i["gen"],"bad cached fetch identity")
            v=bytes(i["data"][x["off"]:x["off"]+4]); oo=i["o"][x["off"]:x["off"]+4]
            need(bytes.fromhex(x["value"])==v and x["oe"]==[z[2] for z in oo] and x["ok"]==[z[0] for z in oo],"bad cached fetch payload/origin")
            fetch_o[e["n"]]=list(oo)
        else: raise AssertionError("unknown event "+k)
        last=k
    return bytes(back),bg,fetch_o


def visible(events,fetch,patch):
    p=next(e for e in events if e["n"]==patch); f=next(e for e in events if e["n"]==fetch)
    if p["k"]!="store" or f["k"]!="fetch": return False
    wb=[e for e in events if patch<e["n"]<fetch and e["k"]=="wb" and e["d"]["gen"]==p["d"]["gen"] and e["d"]["rev"]>=p["d"]["prior"]+1]
    if not wb: return False
    fills=[e for e in events if wb[-1]["n"]<e["n"]<fetch and e["k"]=="ifill"]
    return bool(fills and f["d"]["gen"]==fills[-1]["d"]["gen"] and patch in f["d"]["oe"])


def scenarios():
    out={}
    m=M(); m.fill_i(); m.fill_d(); p=m.store(0,NEW,"patch"); f,v,_=m.fetch(); need(v==OLD[:4] and not visible(m.ev,f,p),"store wrongly visible"); out["store_not_visible"]=(m,{"p":p,"f":f})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(0,NEW,"patch"); w=m.wb(); f,v,_=m.fetch(); need(m.back[:4]==NEW and v==OLD[:4] and not visible(m.ev,f,p),"writeback wrongly visible"); out["writeback_still_stale"]=(m,{"p":p,"wb":w,"f":f})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(0,NEW,"patch"); w=m.wb(); m.inv_i(); f,v,o=m.fetch(); need(v==NEW and all(z[2]==p for z in o) and visible(m.ev,f,p),"post-writeback refill not visible"); out["writeback_then_refill_visible"]=(m,{"p":p,"wb":w,"f":f})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(0,NEW,"patch"); m.inv_i(); f0,v0,_=m.fetch(); w=m.wb(); f1,v1,_=m.fetch(); need(v0==OLD[:4] and v1==OLD[:4] and not visible(m.ev,f1,p),"pre-writeback refill incorrectly upgraded"); out["refill_before_writeback_stays_stale"]=(m,{"p":p,"pre":f0,"wb":w,"post":f1})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(1,bytes.fromhex("abcd"),"partial"); m.wb(); fs,vs,_=m.fetch(); m.inv_i(); fn,vn,on=m.fetch(); expect=OLD[:1]+bytes.fromhex("abcd")+OLD[3:4]; need(vs==OLD[:4] and vn==expect and [z[2] for z in on]==[0,p,p,0] and not visible(m.ev,fs,p) and visible(m.ev,fn,p),"partial lineage wrong"); out["partial_patch"]=(m,{"p":p,"stale":fs,"visible":fn})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(0,OLD[:4],"same_value"); m.wb(); fs,vs,os=m.fetch(); m.inv_i(); fn,vn,on=m.fetch(); need(vs==vn==OLD[:4] and [z[2] for z in os]==[0]*4 and [z[2] for z in on]==[p]*4 and not visible(m.ev,fs,p) and visible(m.ev,fn,p),"same-value generation lost"); out["same_value_patch"]=(m,{"p":p,"stale":fs,"visible":fn})
    m=M(); m.fill_i(); m.fill_d(); p=m.store(4,OLD[:4],"equal_decoy"); m.wb(); m.inv_i(); f,v,o=m.fetch(0); need(v==OLD[:4] and [z[2] for z in o]==[0]*4 and not visible(m.ev,f,p),"equal-value decoy stole origin"); out["equal_payload_decoy"]=(m,{"p":p,"f":f})
    return out


def forgeries(good):
    rejected=[]
    def bad(name,ev):
        try: replay(ev)
        except AssertionError: rejected.append(name); return
        raise AssertionError("forgery accepted: "+name)
    m,_=good["writeback_then_refill_visible"]
    e=copy.deepcopy(m.ev); e[-1]["d"]["gen"]-=1; bad("fetch_generation",e)
    e=copy.deepcopy(m.ev); next(x for x in e if x["k"]=="wb")["d"]["rev"]-=1; bad("writeback_revision",e)
    e=copy.deepcopy(m.ev); [x for x in e if x["k"]=="ifill"][-1]["d"]["payload"]=OLD.hex(); bad("fill_payload",e)
    m,_=good["same_value_patch"]; e=copy.deepcopy(m.ev); s=[x for x in e if x["k"]=="fetch"][0]; p=next(x["n"] for x in e if x["k"]=="store"); s["d"]["oe"]=[p]*4; s["d"]["ok"]=["same_value"]*4; bad("same_value_origin",e)
    m,_=good["partial_patch"]; e=copy.deepcopy(m.ev); s=[x for x in e if x["k"]=="fetch"][-1]; p=next(x["n"] for x in e if x["k"]=="store"); s["d"]["oe"]=[p]*4; s["d"]["ok"]=["partial"]*4; bad("partial_fullword_origin",e)
    m,_=good["writeback_then_refill_visible"]; e=copy.deepcopy(m.ev); [x for x in e if x["k"]=="ir"][-1]["d"]["bg"]-=1; bad("stale_backing_generation",e)
    return rejected


def main():
    good=scenarios(); report={"schema":"plaid-cached-code-patch-visibility-v0","plaid":PLAID,"ares":ARES,"source_blobs":BLOBS,"forgeries":forgeries(good),"scenarios":{}}
    for name,(m,meta) in good.items():
        b,g,_=replay(m.ev); need(b==bytes(m.back) and g==m.bg,"replay disagreement")
        report["scenarios"][name]={"meta":meta,"events":m.ev,"backing":m.back.hex(),"bg":m.bg}
    raw=json.dumps(report,sort_keys=True,separators=(",",":")).encode(); h=hashlib.sha256(raw).hexdigest()
    print(json.dumps({"result":"PASS","sha256":h,"forgery_rejections":len(report["forgeries"]),"event_counts":{k:len(v[0].ev) for k,v in good.items()}},sort_keys=True))

if __name__=="__main__": main()
