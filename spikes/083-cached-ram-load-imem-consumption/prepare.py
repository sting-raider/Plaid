"""Shadow the exact existing D-cache fill/read/invalidate callbacks only."""
from pathlib import Path
import hashlib
import subprocess


def generate(reference, output):
    revision='9408cb43d4948fc3ea6e152a307a34348df3fe04'
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=reference,text=True).strip()==revision
    source=reference/'ares/n64/cpu/dcache.cpp'
    raw=subprocess.check_output(['git','show',f'{revision}:ares/n64/cpu/dcache.cpp'],cwd=reference)
    assert source.read_text()==raw.decode(), 'unclean pinned D-cache source'
    code=source.read_text()
    fill='  setValid(cpu.busReadBurst<DCache>(tag | index, words));'
    assert code.count(fill)==1
    code=code.replace(fill,'  bool plaidFilled = cpu.busReadBurst<DCache>(tag | index, words);\n  setValid(plaidFilled);\n  if(plaidFilled && plaidOperandDcacheObserver) plaidOperandDcacheObserver(1, this, tag | index);')
    read='  return line.read<Size>(paddr);'
    begin=code.index('auto CPU::DataCache::read(u64 vaddr, u32 paddr) -> u64 {')
    end=code.index('template<u32 Size>\nauto CPU::DataCache::readDebug',begin)
    block=code[begin:end];assert block.count(read)==1
    block=block.replace(read,'  u64 data = line.read<Size>(paddr);\n  if(plaidOperandDcacheReadObserver) plaidOperandDcacheReadObserver(vaddr, paddr, Size, data, &line);\n  return data;')
    code=code[:begin]+block+code[end:]
    destination=output/'cpu_operand_dcache.cpp';destination.write_text(code)
    cpu=output/'cpu.cpp';text=cpu.read_text()
    include=f'#include "{source}"';assert text.count(include)==1
    cpu.write_text(text.replace(include,f'#include "{destination}"'))
    header=output/'include/n64/cpu/cpu.hpp';text=header.read_text()
    marker='  //dcache.cpp\n  struct DataCache {';assert text.count(marker)==1
    prefix,cache=text.split(marker,1)
    setvalid='''      auto setValid(bool on) -> void {
        if(on) tagKey |= 1u;
        else tagKey &= ~1u;
      }'''
    assert cache.count(setvalid)==1
    cache=cache.replace(setvalid,'''      auto setValid(bool on) -> void {
        bool plaidWasValid = valid();
        if(on) tagKey |= 1u;
        else tagKey &= ~1u;
        if(!on && plaidWasValid && plaidOperandDcacheObserver)
          plaidOperandDcacheObserver(5, this, (tagKey & ~0x0000'0fffu) | index);
      }''')
    callbacks='''// Project-owned passive callbacks; CPU object layout is unchanged.
using PlaidOperandDcacheObserver = void (*)(u32, const void*, u32);
inline PlaidOperandDcacheObserver plaidOperandDcacheObserver = nullptr;
using PlaidOperandDcacheReadObserver = void (*)(u64, u32, u32, u64, const void*);
inline PlaidOperandDcacheReadObserver plaidOperandDcacheReadObserver = nullptr;
'''
    header.write_text(callbacks+prefix+marker+cache)
    (output/'dcache-source.json').write_text('{"sha256":"'+hashlib.sha256(raw).hexdigest()+'"}\n')
