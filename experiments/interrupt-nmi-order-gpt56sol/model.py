#!/usr/bin/env python3
"""Adversarial model comparing pinned ares IRQ/NMI arbitration with VR4300 manual priority."""
from __future__ import annotations
import hashlib, json, random
from dataclasses import dataclass, asdict
from pathlib import Path
START=0xFFFFFFFFA0000000; NMI_ROOT=0xFFFFFFFFBFC00000

def irq_root(bev:int)->int: return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000)+0x180
@dataclass
class State:
 pc:int=START; bev:int=0; ie:int=1; exl:int=0; erl:int=0; ip:int=0; im:int=0; nmi:int=0
 epc:int=0x123456789ABCDEF0; errorepc:int=0x5555666677778888; fetches:int=0

def eligible_irq(s): return bool(s.ip&s.im) and bool(s.ie) and not s.exl and not s.erl

def take_irq(s): s.epc=s.pc; s.exl=1; s.pc=irq_root(s.bev); return 'irq'
def take_nmi(s): s.bev=1; s.erl=1; s.errorepc=s.pc; s.pc=NMI_ROOT; return 'nmi'

def ares_boundary(s):
 if eligible_irq(s): return take_irq(s)
 if s.nmi: return take_nmi(s)
 s.fetches+=1; s.pc+=4; return 'fetch'

def manual_boundary(s,nmi_edge:bool):
 # VR4300 UM Table 6-5: NMI outranks ordinary Interrupt. Section 13.1 says
 # NMI is edge-triggered, so a stable numeric level is not another NMI event.
 if nmi_edge: return take_nmi(s)
 if eligible_irq(s): return take_irq(s)
 s.fetches+=1; s.pc+=4; return 'fetch'

def main():
 a=State(bev=0,ie=1,exl=0,erl=0,ip=4,im=4,nmi=1); h=State(**asdict(a))
 af=ares_boundary(a); hf=manual_boundary(h,True)
 assert af=='irq' and hf=='nmi'
 assert a.pc==irq_root(0) and h.pc==NMI_ROOT
 # Pinned ares rechecks its persistent level on boundary two; the hardware
 # contract does not manufacture a second edge from the same numeric value.
 a2=ares_boundary(a); h2=manual_boundary(h,False)
 assert a2=='nmi' and h2=='fetch'
 assert a.fetches==0 and h.fetches==1

 rng=random.Random(0x4E4D4951); disagreements=0; eligible_collisions=0; same_value_level_rechecks=0
 counts={'ares_irq_first':0,'manual_nmi_first':0,'agree_other':0}
 for _ in range(100_000):
  kw=dict(bev=rng.randrange(2),ie=rng.randrange(2),exl=rng.randrange(2),erl=rng.randrange(2),ip=rng.randrange(256),im=rng.randrange(256),nmi=rng.randrange(2))
  x=State(**kw); y=State(**kw); coll=bool(kw['nmi']) and eligible_irq(x)
  xa=ares_boundary(x); ym=manual_boundary(y,bool(kw['nmi']))
  if coll:
   eligible_collisions+=1; assert xa=='irq' and ym=='nmi'; disagreements+=1; counts['ares_irq_first']+=1; counts['manual_nmi_first']+=1
  else:
   assert xa==ym; counts['agree_other']+=1
  before=(x.ip,x.nmi); ares_boundary(x)
  if before==(x.ip,x.nmi): same_value_level_rechecks+=1
 assert disagreements==eligible_collisions and disagreements>0
 checks={
  'unordered_root_union_cannot_encode_priority': af!=hf,
  'ares_simultaneous_priority_is_not_hardware_contract': af=='irq' and hf=='nmi',
  'persistent_numeric_nmi_level_is_not_new_hardware_edge': a2=='nmi' and h2!='nmi',
  'root_transfer_does_not_imply_fetch': a.fetches==0,
  'irq_epc_and_nmi_errorepc_are_distinct_history_slots': a.epc!=a.errorepc,
  'same_value_levels_are_rechecked_by_ares': same_value_level_rechecks>0,
 }
 assert all(checks.values()),checks
 payload={'manual':'NEC VR4300 User’s Manual U10504EJ7V0UM00 §6.4.3 Table 6-5 and §13.1','fuzz_seed':'0x4e4d4951','fuzz_cases':100000,'eligible_collision_priority_disagreements':disagreements,'counts':counts,'same_value_level_rechecks':same_value_level_rechecks,'checks':sorted(checks),'single_collision':{'ares_first':af,'ares_second':a2,'manual_first':hf,'manual_second_without_new_nmi_edge':h2,'ares_final':asdict(a),'manual_final':asdict(h)}}
 raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode(); payload['payload_sha256']=hashlib.sha256(raw).hexdigest()
 out=Path(__file__).with_name('model-results.json'); out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print(json.dumps(payload,sort_keys=True)); print(f"PASS: {disagreements} / 100000 states expose exact ares-vs-manual simultaneous-priority disagreement")
if __name__=='__main__': main()
