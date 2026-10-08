#!/usr/bin/env python3
"""Build exact pinned ares and check SWC1/SDC1 mutation and exception semantics."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUTPUT=ROOT/'target/ares-cop1-store-spike'

spec=importlib.util.spec_from_file_location('ares_oracle_build', ROOT/'spikes/003-ares-oracle/run.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
mspec=importlib.util.spec_from_file_location('cop1_model', HERE/'model.py')
model=importlib.util.module_from_spec(mspec); mspec.loader.exec_module(model)


def invoke(exe,op,mode,fr,ft,endian,offset):
    args=[str(exe),op,mode,str(fr),str(ft),endian,str(offset)]
    raw=subprocess.check_output(args,text=True,timeout=20)
    again=subprocess.check_output(args,text=True,timeout=20)
    assert raw==again,(op,mode,fr,ft,endian,offset)
    return json.loads(raw)


def expected_after(before,op,fr,ft,endian,offset):
    out=bytearray(before)
    payload=model.payload_bytes(op,fr,ft,endian)
    out[offset:offset+len(payload)]=payload
    return list(out)


def main():
    exe=mod.build(HERE/'driver.cpp',OUTPUT)
    results=[]
    for op in ('SWC1','SDC1'):
      for fr in (0,1):
       for ft in range(4):
        for endian in ('big','little'):
          for mode in ('uncached','cached'):
            s=invoke(exe,op,mode,fr,ft,endian,0); results.append(s)
            assert s['exception']==0 and s['coprocessor_error']==0,s
            expected=expected_after(s['before_alias'],op,fr,ft,endian,0)
            if mode=='uncached':
                # The architectural guest-byte view must match the independent
                # payload model. Raw backing is checked separately because the
                # controlled little-endian handler probe applies ares' endian
                # physical-lane transform before the RDRAM write.
                assert s['after_alias']==expected,s
                assert s['after_raw']!=s['before_raw'],s
                if endian=='big': assert s['after_raw']==expected,s
                assert s['dirty']==0,s
            else:
                assert s['after_raw']==s['before_raw'],s
                assert s['after_alias']==s['before_alias'],s
                assert s['after_cached']==expected,s
                assert s['dirty']!=0,s

          s=invoke(exe,op,'tlbmiss',fr,ft,endian,0); results.append(s)
          assert (s['exception'],s['coprocessor_error'])==(3,0),s
          assert s['after_raw']==s['before_raw'] and s['after_alias']==s['before_alias'] and s['dirty']==0,s

          s=invoke(exe,op,'misalign',fr,ft,endian,1); results.append(s)
          assert (s['exception'],s['coprocessor_error'])==(5,0),s
          assert s['after_raw']==s['before_raw'] and s['after_alias']==s['before_alias'] and s['dirty']==0,s

          s=invoke(exe,op,'cu1off',fr,ft,endian,0); results.append(s)
          assert (s['exception'],s['coprocessor_error'])==(11,1),s
          assert s['after_raw']==s['before_raw'] and s['after_alias']==s['before_alias'] and s['dirty']==0,s
          s=invoke(exe,op,'cu1off_misalign',fr,ft,endian,1); results.append(s)
          assert (s['exception'],s['coprocessor_error'])==(11,1),s
          assert s['after_raw']==s['before_raw'] and s['after_alias']==s['before_alias'] and s['dirty']==0,s

    assert model.select_u32(0,1)==0x11223344
    assert model.select_u64(0,1)==0x1122334455667788
    encoded=(json.dumps(results,sort_keys=True,separators=(',',':'))+'\n').encode()
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/'results.json').write_bytes(encoded)
    digest=hashlib.sha256(encoded).hexdigest()
    print(f'PASS: {len(results)} repeated pinned-ares SWC1/SDC1 cases')
    print('results_sha256='+digest)

if __name__=='__main__': main()
