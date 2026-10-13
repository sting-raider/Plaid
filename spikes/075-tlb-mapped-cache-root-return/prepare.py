"""Layout-neutral callback at the actual selected-slot TLBWI boundary."""
from pathlib import Path


def generate(ref,out,entryhi=False,entrylo=False):
    ref,out=Path(ref),Path(out)
    hp=out/'include/n64/cpu/cpu.hpp';header=hp.read_text()
    assert 'plaidTlbWriteObserver' not in header
    hp.write_text('using PlaidTlbWriteObserver = void (*)(u32);\ninline PlaidTlbWriteObserver plaidTlbWriteObserver = nullptr;\n'+header,newline='\n')
    original=ref/'ares/n64/cpu/interpreter-scc.cpp'
    code=original.read_text()
    marker='  tlb.entry[scc.index.tlbEntry].synchronize();\n  debugger.tlbWrite(scc.index.tlbEntry);'
    assert code.count(marker)==1
    code=code.replace(marker,'  tlb.entry[scc.index.tlbEntry].synchronize();\n  if(plaidTlbWriteObserver) plaidTlbWriteObserver(scc.index.tlbEntry);\n  debugger.tlbWrite(scc.index.tlbEntry);')
    if entryhi:
        hp.write_text('using PlaidEntryHiObserver = void (*)(u64);\ninline PlaidEntryHiObserver plaidEntryHiObserver = nullptr;\n'+hp.read_text(),newline='\n')
        marker='    scc.tlb.region                    = data.bit(62,63);\n    break;'
        assert code.count(marker)==1
        code=code.replace(marker,'    scc.tlb.region                    = data.bit(62,63);\n    if(plaidEntryHiObserver) plaidEntryHiObserver(data);\n    break;')
    if entrylo:
        hp.write_text('using PlaidEntryLoObserver = void (*)(u64);\ninline PlaidEntryLoObserver plaidEntryLoObserver = nullptr;\n'+hp.read_text(),newline='\n')
        marker='    scc.tlb.physicalAddress[0].bit(12,35) = data.bit(6,29);\n    break;'
        assert code.count(marker)==1
        code=code.replace(marker,'    scc.tlb.physicalAddress[0].bit(12,35) = data.bit(6,29);\n    if(plaidEntryLoObserver) plaidEntryLoObserver(data);\n    break;')
    shadow=out/'interpreter-scc.cpp';shadow.write_text(code,newline='\n')
    cp=out/'cpu.cpp';cpu=cp.read_text();marker=f'#include "{original}"'
    assert cpu.count(marker)==1
    cp.write_text(cpu.replace(marker,f'#include "{shadow}"'),newline='\n')
