#!/usr/bin/env python3
"""Build exact pinned ares and validate conditional-store storage effects."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUTPUT=ROOT/'target/ares-llsc-store-effects'
spec=importlib.util.spec_from_file_location('ares_builder',ROOT/'spikes/003-ares-oracle/run.py')
builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

def invoke(exe,mode):
    raw=subprocess.check_output([str(exe),mode],text=True,timeout=40)
    return raw,json.loads(raw)

def payload(width):
    value=0x11223344 if width==4 else 0x1122334455667788
    return list(value.to_bytes(width,'big'))

def events_for(doc,case_id):
    scalar=[e for e in doc['scalar_events'] if e['case']==case_id]
    burst=[e for e in doc['burst_events'] if e['case']==case_id]
    return scalar,burst

def verify_case(doc,f):
    scalar,burst=events_for(doc,f['id'])
    expected=payload(f['width'])
    writes=[e for e in scalar+burst if e['write']]
    if f['failed']:
        assert f['rt']==0 and f['exception']==0,f
        assert f['initial']==f['before_writeback']==f['after'] and f['dirty_before']==f['dirty_after']==0,f
        assert not scalar and not burst,f
        return
    if f['fault']:
        assert f['rt']==0 and f['exception']==5 and f['badva']==0xffffffffa0002001,f
        assert f['initial']==f['before_writeback']==f['after'] and f['dirty_before']==f['dirty_after']==0,f
        assert len(scalar)==1 and not scalar[0]['write'] and scalar[0]['stage']==1,f
        assert not writes and not burst,f
        return
    assert f['rt']==1 and f['exception']==0,f
    if not f['cached']:
        assert f['dirty_before']==f['dirty_after']==0 and not f['resident'],f
        assert f['before_writeback']==expected and f['after']==expected,f
        assert [(e['stage'],e['write'],e['bytes']) for e in scalar]==[(1,False,f['width']),(1,True,f['width'])],(f,scalar)
        assert not burst,f
        if f['same']:
            assert f['initial']==f['after'],f
            assert scalar[-1]['write'],f
        else:
            assert f['initial']!=f['after'],f
    else:
        assert not scalar,f
        assert f['before_writeback']==f['initial'],f
        assert f['resident']==expected,f
        assert f['dirty_before']!=0 and f['dirty_after']==0,f
        assert f['after']==expected,f
        assert len(burst)==2,(f,burst)
        assert burst[0]['stage']==1 and not burst[0]['write'] and burst[0]['bytes']==16,(f,burst)
        assert burst[1]['stage']==2 and burst[1]['write'] and burst[1]['bytes']==16,(f,burst)
        assert burst[0]['ordinal'] < burst[1]['ordinal'],(f,burst)
        if f['same']:
            assert f['initial']==f['after'],f
            assert burst[-1]['write'],f
        else:
            assert f['initial']!=f['after'],f

def adversaries(doc):
    base=json.loads(json.dumps(doc))
    checks=[]
    def rejects(mutator):
        forged=json.loads(json.dumps(base)); mutator(forged)
        try:
            for f in forged['facts']: verify_case(forged,f)
        except AssertionError:
            return True
        return False
    checks.append(rejects(lambda d:d['scalar_events'].__setitem__(slice(None),[e for e in d['scalar_events'] if not (e['case']==4 and e['write'])])))
    checks.append(rejects(lambda d:d['burst_events'].__setitem__(slice(None),[e for e in d['burst_events'] if not (e['case']==6 and e['write'])])))
    checks.append(rejects(lambda d:d['scalar_events'].append({'case':1,'stage':1,'ordinal':999999,'write':True,'address':8192,'bytes':4,'device':0,'value':0})))
    checks.append(rejects(lambda d:next(e for e in d['burst_events'] if e['case']==5 and e['write']).__setitem__('stage',1)))
    checks.append(rejects(lambda d:next(f for f in d['facts'] if f['name']=='sc_cached_same').__setitem__('dirty_before',0)))
    assert all(checks),checks
    return len(checks)

def main():
    # The shared reference builder requires raw/effective fetch sensing whenever
    # RDRAM burst callbacks are present. Those fetch observers stay null in this
    # fixture; enabling the build capability does not add a guest access.
    instrumented=builder.build(HERE/'driver.cpp',OUTPUT/'instrumented',extra_sources=(HERE/'observer.hpp',),raw_fetch_access=True,physical_fetch_access=True,rdram_burst_access=True,rdram_scalar_access=True)
    baseline=builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=(HERE/'driver.cpp',HERE/'observer.hpp'))
    baseline_raw,base=invoke(baseline,'plain')
    plain_raw,plain=invoke(instrumented,'plain')
    traced_raw,traced=invoke(instrumented,'traced')
    repeat_raw,repeat=invoke(instrumented,'traced')
    assert traced_raw==repeat_raw
    assert not base['scalar_events'] and not base['burst_events']
    assert not plain['scalar_events'] and not plain['burst_events']
    assert base['facts']==plain['facts']==traced['facts']==repeat['facts']
    assert len(traced['facts'])==12
    for f in traced['facts']: verify_case(traced,f)
    forged=adversaries(traced)
    encoded=(json.dumps({'baseline':base,'plain':plain,'traced':traced},sort_keys=True,separators=(',',':'))+'\n').encode()
    OUTPUT.mkdir(parents=True,exist_ok=True); (OUTPUT/'results.json').write_bytes(encoded)
    print('PASS: 12 decoded SC/SCD cases preserve baseline/plain/traced state and classify sink effects')
    print('forgeries_rejected='+str(forged))
    print('results_sha256='+hashlib.sha256(encoded).hexdigest())

if __name__=='__main__':
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else: main()
