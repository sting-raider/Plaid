"""Original actual RSP instruction boundaries and primitive DMEM sink callbacks."""
from pathlib import Path
import re


def generate(ref,out,sp_backing=False,word_reads=False):
    ref,out=Path(ref),Path(out)
    destination=out/'include/n64/rsp/rsp.hpp'
    header=(destination if destination.exists() else ref/'ares/n64/rsp/rsp.hpp').read_text(encoding='utf-8')
    declarations='''// Original observational callbacks; no reference object fields.
using PlaidRspInstructionObserver = void (*)(bool,u32,u32,u32,bool);
using PlaidRspDmemObserver = void (*)(u32,u32,u64);
inline PlaidRspInstructionObserver plaidRspInstructionObserver = nullptr;
inline PlaidRspDmemObserver plaidRspDmemObserver = nullptr;
'''
    if word_reads:
        declarations += '''using PlaidRspWordReadObserver = void (*)(u32,u32);
inline PlaidRspWordReadObserver plaidRspWordReadObserver = nullptr;
'''
    marker='      if constexpr(Size == Dual) *(u64*)&data[address & maskDual] = bswap64(value);'
    assert header.count(marker)==1
    extra='''
      if(plaidRspDmemObserver) {
        u32 plaidOffset=address & (Size==Byte ? maskByte : Size==Half ? maskHalf : Size==Word ? maskWord : maskDual);
        u64 plaidValue=value;
        if constexpr(Size != Dual) plaidValue &= (u64(1) << (Size*8))-1;
        plaidRspDmemObserver(plaidOffset,Size,plaidValue);
      }'''
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(declarations+header.replace(marker,marker+extra),encoding='utf-8',newline='\n')
    source=out/'rsp.cpp'
    # Only the freshly generated SP shadow is a composable input. An earlier
    # failed RSP-only build may leave this helper's own output here.
    rsp=(source if sp_backing else ref/'ares/n64/rsp/rsp.cpp').read_text(encoding='utf-8')
    rsp=re.sub(r'#include "([^"]+)"',lambda m:f'#include "{m[1] if Path(m[1]).is_absolute() else ref/"ares/n64/rsp"/m[1]}"',rsp)
    marker='  pipeline.instruction = instruction;'
    assert rsp.count(marker)==1
    rsp=rsp.replace(marker,marker+'\n  if(plaidRspInstructionObserver) plaidRspInstructionObserver(true,ipu.pc,instruction,ipu.pc,status.halted);')
    marker='  return instructionBranchEpilogue();'
    assert rsp.count(marker)==1
    rsp=rsp.replace(marker,'''  auto plaidResult=instructionBranchEpilogue();
  if(plaidRspInstructionObserver) plaidRspInstructionObserver(false,pipeline.address,pipeline.instruction,ipu.pc,status.halted);
  return plaidResult;''')
    if word_reads:
        ipu=(ref/'ares/n64/rsp/interpreter-ipu.cpp').read_text(encoding='utf-8')
        marker='''auto RSP::LW(r32& rt, cr32& rs, s16 imm) -> void {
  rt.u32 = dmem.readUnaligned<Word>(rs.u32 + imm);
}'''
        assert ipu.count(marker)==1
        ipu=ipu.replace(marker,'''auto RSP::LW(r32& rt, cr32& rs, s16 imm) -> void {
  u32 plaidAddress=rs.u32 + imm;
  auto plaidValue=dmem.readUnaligned<Word>(plaidAddress);
  if(plaidRspWordReadObserver) plaidRspWordReadObserver(plaidAddress,u32(plaidValue));
  rt.u32=plaidValue;
}''')
        patched=out/'rsp-interpreter-ipu.cpp'
        patched.write_text(ipu,encoding='utf-8',newline='\n')
        marker=f'#include "{ref/"ares/n64/rsp/interpreter-ipu.cpp"}"'
        assert rsp.count(marker)==1
        rsp=rsp.replace(marker,f'#include "{patched}"')
    source.write_text(rsp,encoding='utf-8',newline='\n')
    unity=(out/'n64.cpp').read_text(encoding='utf-8')
    marker='#include <n64/rsp/rsp.cpp>'
    unity=unity.replace(f'#include "{source}"',marker);assert unity.count(marker)==1
    (out/'n64.cpp').write_text(unity.replace(marker,f'#include "{source}"'),encoding='utf-8',newline='\n')
