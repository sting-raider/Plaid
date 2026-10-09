#!/usr/bin/env python3
"""Build exact pinned ares and verify COP1 store effects in SP DMEM/IMEM."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'target/ares-cop1-sp-sink'

bspec=importlib.util.spec_from_file_location('ares_build',ROOT/'spikes/003-ares-oracle/run.py')
build=importlib.util.module_from_spec(bspec); bspec.loader.exec_module(build)
mspec=importlib.util.spec_from_file_location('cop1_model',ROOT/'spikes/035-ares-cop1-stores/model.py')
model=importlib.util.module_from_spec(mspec); mspec.loader.exec_module(model)


def source_guards():
    ref=ROOT/'.refs/ares'
    io=(ref/'ares/n64/memory/io.hpp').read_text()
    dual='''    if constexpr(Size == Dual) {\n      ((T*)this)->writeWord(address, data >> 32, thread);\n    }'''
    assert io.count(dual)==1
    fpu=(ref/'ares/n64/cpu/interpreter-fpu.cpp').read_text()
    assert 'write<Word>(rs.u64 + imm, FT(u32));' in fpu
    assert 'write<Dual>(rs.u64 + imm, FT(u64));' in fpu
    rsp=(ref/'ares/n64/rsp/io.cpp').read_text()
    assert 'if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);' in rsp
    assert 'else                 return dmem.write<Word>(address, data);' in rsp


def invoke(exe,op,bank,fr,ft,mode,offset,observer):
    args=[str(exe),op,bank,str(fr),str(ft),mode,str(offset),observer]
    a=subprocess.check_output(args,text=True,timeout=20)
    b=subprocess.check_output(args,text=True,timeout=20)
    assert a==b,(op,bank,fr,ft,mode,offset,observer)
    return json.loads(a)


def neutral_pair(exe,op,bank,fr,ft,mode,offset):
    on=invoke(exe,op,bank,fr,ft,mode,offset,'on')
    off=invoke(exe,op,bank,fr,ft,mode,offset,'off')
    a={k:v for k,v in on.items() if k not in ('observer','sinks')}
    b={k:v for k,v in off.items() if k not in ('observer','sinks')}
    assert a==b,(on,off)
    assert off['sinks']==[],off
    return on,off


def expected_word(op,fr,ft):
    if op=='SWC1': return model.select_u32(fr,ft)
    return (model.select_u64(fr,ft)>>32)&0xffffffff


def patched_words(before,offset,value):
    out=list(before)
    out[offset//4]=value
    return out


def main():
    source_guards()
    exe=build.build(HERE/'driver.cpp',OUT,raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True)
    results=[]
    for op in ('SWC1','SDC1'):
      for bank in ('dmem','imem'):
       for fr in (0,1):
        for ft in range(4):
         for offset in (0,8):
          s,disabled=neutral_pair(exe,op,bank,fr,ft,'ok',offset); results += [s,disabled]
          value=expected_word(op,fr,ft)
          assert (s['exception'],s['coprocessor_error'])==(0,0),s
          assert s['after_other_words']==s['before_other_words'],s
          assert s['after_target_words']==patched_words(s['before_target_words'],offset,value),s
          assert s['sinks']==[{'address':(0x04001000 if bank=='imem' else 0x04000000)+offset,
                               'bank':1 if bank=='imem' else 0,'offset':offset,
                               'value':value,'cpu':True}],s
          # Raw bytes are retained as observations, not used to infer guest order.
          # The actual sink must affect only its concrete four-byte storage group.
          assert s['after_target_bytes'][:offset]==s['before_target_bytes'][:offset],s
          assert s['after_target_bytes'][offset+4:]==s['before_target_bytes'][offset+4:],s

         for mode,expected in (('cu1off',(11,1)),('misalign',(5,0))):
          s,disabled=neutral_pair(exe,op,bank,fr,ft,mode,0); results += [s,disabled]
          assert (s['exception'],s['coprocessor_error'])==expected,s
          assert s['after_target_words']==s['before_target_words'],s
          assert s['after_other_words']==s['before_other_words'],s
          assert s['sinks']==[],s

    # Explicitly pin the surprising SDC1 device effect. The nominal 64-bit source
    # produces only the high source word at this ares RCP sink; the next Word is
    # unchanged. This is an implementation result, not a hardware invariant.
    probe=next(x for x in results if x['observer']=='on' and x['op']=='SDC1' and x['bank']=='dmem' and x['fr']==1 and x['ft']==1 and x['mode']=='ok' and x['offset']==0)
    assert probe['sinks'][0]['value']==0x99aabbcc
    assert probe['after_target_words'][0]==0x99aabbcc
    assert probe['after_target_words'][1]==probe['before_target_words'][1]

    encoded=(json.dumps(results,sort_keys=True,separators=(',',':'))+'\n').encode()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'results.json').write_bytes(encoded)
    digest=hashlib.sha256(encoded).hexdigest()
    print(f'PASS: {len(results)} enabled/disabled exact-pin COP1-to-SP observations; every process repeated')
    print('results_sha256='+digest)

if __name__=='__main__': main()
