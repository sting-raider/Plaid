"""Layout-neutral callback at the actual selected-slot TLBWI boundary."""
from pathlib import Path


def generate(ref,out):
    ref,out=Path(ref),Path(out)
    hp=out/'include/n64/cpu/cpu.hpp';header=hp.read_text()
    assert 'plaidTlbWriteObserver' not in header
    hp.write_text('using PlaidTlbWriteObserver = void (*)(u32);\ninline PlaidTlbWriteObserver plaidTlbWriteObserver = nullptr;\n'+header,newline='\n')
    original=ref/'ares/n64/cpu/interpreter-scc.cpp'
    code=original.read_text()
    marker='  tlb.entry[scc.index.tlbEntry].synchronize();\n  debugger.tlbWrite(scc.index.tlbEntry);'
    assert code.count(marker)==1
    code=code.replace(marker,'  tlb.entry[scc.index.tlbEntry].synchronize();\n  if(plaidTlbWriteObserver) plaidTlbWriteObserver(scc.index.tlbEntry);\n  debugger.tlbWrite(scc.index.tlbEntry);')
    shadow=out/'interpreter-scc.cpp';shadow.write_text(code,newline='\n')
    cp=out/'cpu.cpp';cpu=cp.read_text();marker=f'#include "{original}"'
    assert cpu.count(marker)==1
    cp.write_text(cpu.replace(marker,f'#include "{shadow}"'),newline='\n')
