"""Original PIF-ROM reads/no-effect write attempts in generated shadows."""
from pathlib import Path
import re


def generate(ref,out):
    ref,out=Path(ref),Path(out)
    header=(ref/'ares/n64/pif/pif.hpp').read_text(encoding='utf-8')
    declarations='''// Original PIF ROM read and delegated read-only write-attempt callback.
using PlaidPifWordObserver = void (*)(bool,u32,u32);
inline PlaidPifWordObserver plaidPifWordObserver = nullptr;
'''
    destination=out/'include/n64/pif/pif.hpp';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(declarations+header,encoding='utf-8',newline='\n')
    assert 'Memory::Readable rom;' in header
    for endian in ('lsb','msb'):
        readable=(ref/f'ares/n64/memory/{endian}/readable.hpp').read_text(encoding='utf-8')
        assert 'auto write(u32 address, u64 value) -> void {\n  }' in readable
    io=(ref/'ares/n64/pif/io.cpp').read_text(encoding='utf-8')
    before='    return rom.read<Word>(address);'
    after='''    u32 plaidValue=rom.read<Word>(address);
    if(plaidPifWordObserver) plaidPifWordObserver(false,address&0x7fc,plaidValue);
    return plaidValue;'''
    assert io.count(before)==1;io=io.replace(before,after)
    before='    return rom.write<Word>(address, data);'
    after='''    rom.write<Word>(address,data);
    if(plaidPifWordObserver) plaidPifWordObserver(true,address&0x7fc,data);
    return;'''
    assert io.count(before)==1;io=io.replace(before,after)
    io_path=out/'pif_io.cpp';io_path.write_text(io,encoding='utf-8',newline='\n')
    pif=(ref/'ares/n64/pif/pif.cpp').read_text(encoding='utf-8')
    pif=re.sub(r'#include "([^"]+)"',lambda m:f'#include "{io_path if m[1]=="io.cpp" else ref/"ares/n64/pif"/m[1]}"',pif)
    pif_path=out/'pif.cpp';pif_path.write_text(pif,encoding='utf-8',newline='\n')
    unity=(out/'n64.cpp').read_text(encoding='utf-8');marker='#include <n64/pif/pif.cpp>'
    unity=unity.replace(f'#include "{pif_path}"',marker);assert unity.count(marker)==1
    (out/'n64.cpp').write_text(unity.replace(marker,f'#include "{pif_path}"'),encoding='utf-8',newline='\n')
