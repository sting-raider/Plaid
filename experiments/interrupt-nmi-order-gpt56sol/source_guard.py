#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'target/interrupt-nmi-order-gpt56sol'
PINS={'ares':'9408cb43d4948fc3ea6e152a307a34348df3fe04','gopher64':'e96debac941a26ba4961e5145056c0821d3a56f7','mupen64plus-core':'ba95bab92a76744753bfe61470823a4937850ab0'}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 for name,rev in PINS.items():
  p=ROOT/'.refs'/name; assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=p,text=True).strip()==rev; subprocess.run(['git','diff','--quiet','HEAD'],cwd=p,check=True)
 a=ROOT/'.refs/ares/ares/n64/cpu'; cpu=(a/'cpu.cpp').read_text(); exc=(a/'exceptions.cpp').read_text()
 irq=cpu.index('if(auto interrupts = scc.cause.interruptPending & scc.status.interruptMask)'); nmi=cpu.index('if (scc.nmiPending)'); fetch=cpu.index('auto access = devirtualize<Read, Word>(ipu.pc)'); assert irq<nmi<fetch
 assert 'exception.interrupt();\n      return true;' in cpu and 'exception.nmi();\n    return true;' in cpu
 assert 'self.scc.status.exceptionLevel = 1;' in exc and 'self.scc.status.errorLevel = 1;' in exc and "self.pipeline.setPc(0xffff'ffff'bfc0'0000);" in exc
 g=ROOT/'.refs/gopher64/src/device/exceptions.rs'; gt=g.read_text(); assert 'pub fn check_pending_interrupts' in gt and 'pub fn reset_event' in gt and 'COP0_STATUS_EXL' in gt and 'COP0_STATUS_ERL' in gt
 md=ROOT/'.refs/mupen64plus-core/src/device/device.c'; mt=md.read_text(); assert 'schedule HW2 interrupt now and an NMI after 1/2 seconds' in mt and 'add_interrupt_event(&dev->r4300.cp0, HW2_INT, 0);' in mt and 'add_interrupt_event(&dev->r4300.cp0, NMI_INT, 50000000);' in mt
 mi=ROOT/'.refs/mupen64plus-core/src/device/r4300/interrupt.c'; mit=mi.read_text(); assert 'void nmi_int_handler(void* opaque)' in mit and 'void raise_maskable_interrupt' in mit
 payload={'pins':PINS,'ares_order':['eligible_maskable_interrupt','nmi_pending','instruction_fetch'],'independent_reference_note':'Gopher64 uses separate interrupt checking/reset_event; Mupen schedules HW2 and NMI as queue events 50,000,000 Count units apart, so neither exact pin independently validates ares simultaneous-level priority.','sha256':{'ares_cpu':sha(a/'cpu.cpp'),'ares_exceptions':sha(a/'exceptions.cpp'),'gopher_exceptions':sha(g),'mupen_device':sha(md),'mupen_interrupt':sha(mi)}}
 OUT.mkdir(parents=True,exist_ok=True); p=OUT/'source_guard.json'; p.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
