#!/usr/bin/env python3
"""Build exact pinned ares and execute simultaneous IRQ/NMI ordering cases."""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
OUT=ROOT/'target/interrupt-nmi-order-gpt56sol'; ARES='9408cb43d4948fc3ea6e152a307a34348df3fe04'
START=0xFFFFFFFFA0000000; NMI_ROOT=0xFFFFFFFFBFC00000; EPC_SENT=0x123456789ABCDEF0; ERR_SENT=0x5555666677778888

def irq_root(bev): return (0xFFFFFFFFBFC00200 if bev else 0xFFFFFFFF80000000)+0x180

def oracle():
 p=ROOT/'spikes/003-ares-oracle/run.py'; s=importlib.util.spec_from_file_location('oracle',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def scenarios():
 return [
 ('collision_persist_bev0',0,1,0,0,4,4,1,0,0),('collision_persist_bev1',1,1,0,0,4,4,1,0,0),
 ('collision_clear_nmi_bev0',0,1,0,0,4,4,1,1,0),('collision_clear_ip_bev0',0,1,0,0,4,4,1,0,1),
 ('irq_only_bev0',0,1,0,0,4,4,0,0,0),('masked_plus_nmi',0,1,0,0,4,8,1,0,0),
 ('ie0_plus_nmi',0,0,0,0,4,4,1,0,0),('exl1_plus_nmi',0,1,1,0,4,4,1,0,0),
 ('erl1_plus_nmi',0,1,0,1,4,4,1,0,0),('no_events',0,1,0,0,0,0,0,0,0)]

def projection(x): return {k:v for k,v in x.items() if k not in ('mode','fetches_first','fetches_second')}

def check(c,x,traced):
 name,bev,ie,exl,erl,ip,im,nmi,clear_nmi,clear_ip=c
 assert x['name']==name
 eligible=bool(ip&im) and bool(ie) and not exl and not erl
 if eligible:
  r=irq_root(bev); assert x['first_pc']==r and x['first_epc']==START and x['first_exl']==1 and x['first_s0']==0 and x['first_s1']==0
  assert x['fetches_first']==0
  if nmi and not clear_nmi:
   assert x['second_pc']==NMI_ROOT and x['second_errorepc']==r and x['second_erl']==1 and x['second_bev']==1 and x['second_s1']==0
   assert x['fetches_second']==0
  else:
   assert bev==0
   assert x['second_pc']==r+4 and x['second_s1']==0x5678 and x['second_erl']==0
   assert x['fetches_second']==(1 if traced else 0)
 elif nmi:
  assert x['first_pc']==NMI_ROOT and x['first_errorepc']==START and x['first_epc']==EPC_SENT and x['first_erl']==1 and x['first_bev']==1
  assert x['fetches_first']==0
  assert x['second_pc']==NMI_ROOT and x['second_errorepc']==NMI_ROOT and x['fetches_second']==0
 else:
  assert name=='no_events'
  assert x['first_pc']==START+4 and x['first_s0']==0x1234 and x['second_pc']==START+8
  assert (x['fetches_first'],x['fetches_second'])==((1,1) if traced else (0,0))

def invoke(exe,mode,c):
 args=[str(exe),mode,c[0],*map(str,c[1:5]),hex(c[5]),hex(c[6]),*map(str,c[7:])]
 a=subprocess.check_output(args,text=True,timeout=20); b=subprocess.check_output(args,text=True,timeout=20); assert a==b,(c,mode,a,b); return json.loads(a)

def main():
 ref=ROOT/'.refs/ares'; rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ref,text=True).strip(); assert rev==ARES
 subprocess.run(['git','diff','--quiet','HEAD'],cwd=ref,check=True)
 cpu=(ref/'ares/n64/cpu/cpu.cpp').read_text(); exc=(ref/'ares/n64/cpu/exceptions.cpp').read_text()
 assert cpu.index('if(auto interrupts = scc.cause.interruptPending & scc.status.interruptMask)') < cpu.index('if (scc.nmiPending)') < cpu.index('auto access = devirtualize<Read, Word>(ipu.pc)')
 assert 'self.scc.status.exceptionLevel = 1;' in exc and 'self.scc.status.errorLevel = 1;' in exc
 o=oracle(); base=o.build(HERE/'baseline.cpp',OUT/'baseline'); sensed=o.build(HERE/'driver.cpp',OUT/'sensed',raw_fetch_access=True,physical_fetch_access=True,fetch_boundary_access=True)
 rows=[]
 for c in scenarios():
  b=invoke(base,'plain',c); p=invoke(sensed,'plain',c); t=invoke(sensed,'traced',c)
  assert projection(b)==projection(p)==projection(t),(c,b,p,t)
  check(c,b,False); check(c,p,False); check(c,t,True)
  rows.append({'scenario':c[0],'baseline':b,'sensor_disabled':p,'sensor_enabled':t})
 payload={'plaid_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'ares_revision':ARES,'cases':len(rows),'rows':rows,'source_sha256':{'cpu.cpp':sha(ref/'ares/n64/cpu/cpu.cpp'),'exceptions.cpp':sha(ref/'ares/n64/cpu/exceptions.cpp')}}
 OUT.mkdir(parents=True,exist_ok=True); dest=OUT/'results.json'; dest.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print('RESULT_SHA256',sha(dest)); print(f'PASS: {len(rows)} scenarios repeated; observer-neutral machine state; collision IRQ->NMI has zero handler fetches')
 return 0
if __name__=='__main__': sys.exit(main())
