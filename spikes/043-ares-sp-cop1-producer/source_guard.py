#!/usr/bin/env python3
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'.refs/ares'
PIN='9408cb43d4948fc3ea6e152a307a34348df3fe04'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==PIN
fpu=(REF/'ares/n64/cpu/interpreter-fpu.cpp').read_text()
bus=(REF/'ares/n64/memory/bus.hpp').read_text()
io=(REF/'ares/n64/rsp/io.cpp').read_text()
markers=[
('SWC1 CU1 gate','auto CPU::SWC1(u8 ft, cr64& rs, s16 imm) -> void {\n  if(!scc.status.enable.coprocessor1) return exception.coprocessor1();\n  write<Word>(rs.u64 + imm, FT(u32));\n}',fpu),
('FR0 odd lane','} else if(index & 1) {\n    return fpu.r[index & ~1].s32h;',fpu),
('SP bus route',"if(address <= 0x0407'ffff) return rsp.write<Size>(address, data, thread);",bus),
('SP banked word sink','if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);\n    else                 return dmem.write<Word>(address, data);',io),
]
for name,marker,text in markers:
    assert text.count(marker)==1,(name,text.count(marker))
print('PASS exact pinned ares SWC1/FR/SP sink source guards')
