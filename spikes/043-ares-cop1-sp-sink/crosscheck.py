#!/usr/bin/env python3
"""Exact-pin source cross-check for ares vs Gopher64 COP1 stores into SP memory."""
from pathlib import Path
import hashlib, json, re

ROOT=Path(__file__).resolve().parents[2]
ARES=ROOT/'.refs/ares'
GOPHER=ROOT/'.refs/gopher64'
ARES_REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'
GOPHER_REV='e96debac941a26ba4961e5145056c0821d3a56f7'


def git_head(path):
    import subprocess
    return subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()


def between(text,start,end):
    a=text.index(start); b=text.index(end,a+len(start)); return text[a:b]


def main():
    assert git_head(ARES)==ARES_REV
    assert git_head(GOPHER)==GOPHER_REV

    ares_fpu=(ARES/'ares/n64/cpu/interpreter-fpu.cpp').read_text()
    ares_io=(ARES/'ares/n64/memory/io.hpp').read_text()
    ares_rsp=(ARES/'ares/n64/rsp/io.cpp').read_text()
    assert 'write<Dual>(rs.u64 + imm, FT(u64));' in ares_fpu
    ares_dual=between(ares_io,'    if constexpr(Size == Dual) {\n      ((T*)this)->writeWord(address, data >> 32, thread);','    }\n  }\n};')
    assert ares_dual.count('writeWord(')==1 and 'address + 4' not in ares_dual
    assert 'imem.write<Word>(address, data)' in ares_rsp and 'dmem.write<Word>(address, data)' in ares_rsp

    g_cop1=(GOPHER/'src/device/cop1.rs').read_text()
    g_mem=(GOPHER/'src/device/memory.rs').read_text()
    g_rsp=(GOPHER/'src/device/rsp_interface.rs').read_text()
    sdc1=between(g_cop1,'pub fn sdc1(','fn mfc1(')
    assert sdc1.count('device::memory::data_write(')==2
    assert 'phys_address + 4' in sdc1
    assert 'const MM_RSP_MEM: usize = 0x04000000;' in g_mem
    assert 'device.memory.memory_map_write[i] = device::rsp_interface::write_mem;' in g_mem
    write_mem=between(g_rsp,'pub fn write_mem(','fn do_dma(')
    assert 'device.rsp.mem[masked_address..masked_address + 4].copy_from_slice' in write_mem

    evidence={
      'ares_revision':ARES_REV,
      'ares_rcp_dual_writeword_calls':1,
      'ares_rcp_dual_second_word':False,
      'gopher_revision':GOPHER_REV,
      'gopher_sdc1_data_write_calls':2,
      'gopher_sdc1_second_address':True,
      'gopher_sp_map_to_rsp_write_mem':True,
      'gopher_rsp_sink_width_bytes':4,
    }
    encoded=(json.dumps(evidence,sort_keys=True,separators=(',',':'))+'\n').encode()
    print('PASS: exact-pin source disagreement is structurally guarded')
    print('crosscheck_sha256='+hashlib.sha256(encoded).hexdigest())
    print(encoded.decode().strip())

if __name__=='__main__': main()
