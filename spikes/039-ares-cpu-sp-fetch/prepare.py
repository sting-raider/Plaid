"""Original callback shadows around existing SP word effects and DMA stores."""
from pathlib import Path
import re


def generate(ref, out):
    ref, out = Path(ref), Path(out)
    header = (ref/'ares/n64/rsp/rsp.hpp').read_text(encoding='utf-8')
    declarations = '''// Original research callbacks; no reference object fields.
using PlaidSpWordObserver = void (*)(bool,u32,u32,u32,u32,bool);
using PlaidSpDmaStoreObserver = void (*)(u32,u32,u32,u32,u64);
inline PlaidSpWordObserver plaidSpWordObserver = nullptr;
inline PlaidSpDmaStoreObserver plaidSpDmaStoreObserver = nullptr;
'''
    destination = out/'include/n64/rsp/rsp.hpp'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(declarations+header,encoding='utf-8',newline='\n')
    io = (ref/'ares/n64/rsp/io.cpp').read_text(encoding='utf-8')
    before = '''    if(address & 0x1000) return imem.read<Word>(address);
    else                 return dmem.read<Word>(address);'''
    after = '''    u32 plaidValue = address & 0x1000 ? imem.read<Word>(address) : dmem.read<Word>(address);
    if(plaidSpWordObserver) plaidSpWordObserver(false,address,(address>>12)&1,address&0xffc,plaidValue,&thread==&cpu);
    return plaidValue;'''
    assert io.count(before)==1;io=io.replace(before,after)
    before = '''    if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);
    else                 return dmem.write<Word>(address, data);'''
    after = '''    if(address & 0x1000) { recompiler.invalidate(address & 0xfff); imem.write<Word>(address,data); }
    else dmem.write<Word>(address,data);
    if(plaidSpWordObserver) plaidSpWordObserver(true,address,(address>>12)&1,address&0xffc,data,&thread==&cpu);
    return;'''
    assert io.count(before)==1;io=io.replace(before,after)
    io_path=out/'rsp_io.cpp';io_path.write_text(io,encoding='utf-8',newline='\n')
    dma=(ref/'ares/n64/rsp/dma.cpp').read_text(encoding='utf-8')
    for marker,extra in [
        ('        imem.write<Dual>(dma.current.pbusAddress, data);',
         '        if(plaidSpDmaStoreObserver) plaidSpDmaStoreObserver(dma.current.dramAddress,1,dma.current.pbusAddress&0xff8,8,data);'),
        ('        dmem.write<Word>(dma.current.pbusAddress + 0, dataLo);',
         '        if(plaidSpDmaStoreObserver) plaidSpDmaStoreObserver(dma.current.dramAddress,0,dma.current.pbusAddress&0xffc,4,dataLo);'),
        ('        dmem.write<Word>(dma.current.pbusAddress + 4, dataHi);',
         '        if(plaidSpDmaStoreObserver) plaidSpDmaStoreObserver(dma.current.dramAddress+4,0,(dma.current.pbusAddress+4)&0xffc,4,dataHi);')]:
        assert dma.count(marker)==1;dma=dma.replace(marker,marker+'\n'+extra)
    dma_path=out/'rsp_dma.cpp';dma_path.write_text(dma,encoding='utf-8',newline='\n')
    rsp=(ref/'ares/n64/rsp/rsp.cpp').read_text(encoding='utf-8')
    replacements={'io.cpp':io_path,'dma.cpp':dma_path}
    rsp=re.sub(r'#include "([^"]+)"',lambda m:f'#include "{replacements.get(m[1],ref/"ares/n64/rsp"/m[1])}"',rsp)
    rsp_path=out/'rsp.cpp';rsp_path.write_text(rsp,encoding='utf-8',newline='\n')
    unity=(out/'n64.cpp').read_text(encoding='utf-8')
    marker='#include <n64/rsp/rsp.cpp>'
    unity=unity.replace(f'#include "{rsp_path}"',marker)
    assert unity.count(marker)==1
    (out/'n64.cpp').write_text(unity.replace(marker,f'#include "{rsp_path}"'),encoding='utf-8',newline='\n')
