#!/usr/bin/env python3
"""Build exact pinned ares and test decoded SWC1 -> SP sink producer joins."""
from __future__ import annotations
from pathlib import Path
import hashlib, importlib.util, json, subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/'target/ares-sp-cop1-producer'

spec=importlib.util.spec_from_file_location('ares_oracle_build',ROOT/'spikes/003-ares-oracle/run.py')
buildmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(buildmod)
vspec=importlib.util.spec_from_file_location('sp_cop1_verify',HERE/'verify.py')
verify=importlib.util.module_from_spec(vspec);vspec.loader.exec_module(verify)

def invoke(exe, mode, scenario):
    raw=subprocess.check_output([str(exe),mode,scenario],text=True,timeout=30)
    again=subprocess.check_output([str(exe),mode,scenario],text=True,timeout=30)
    assert raw==again,(mode,scenario)
    return json.loads(raw),raw

def architectural(report):
    return {'scenario':report['scenario'],'phases':report['phases'],'state':report['state']}

def check_fault(report, code=None):
    assert report['events']==[],report
    assert len(report['phases'])==1,report
    if code is not None: assert report['phases'][0]['exception']==code,report

def main():
    base=buildmod.build(HERE/'baseline.cpp',OUT/'baseline')
    sensor=buildmod.build(HERE/'sensor.cpp',OUT/'sensor',raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True)
    reports={}
    for scenario in ('matrix','cu1off','misalign','tlbmiss','status'):
        b,_=invoke(base,'disabled',scenario)
        d,_=invoke(sensor,'disabled',scenario)
        e1,raw1=invoke(sensor,'enabled',scenario)
        e2,raw2=invoke(sensor,'enabled',scenario)
        assert architectural(b)==architectural(d)==architectural(e1)==architectural(e2),scenario
        assert raw1==raw2,scenario
        if scenario=='matrix':
            vr=verify.verify(e1)
            assert vr['event_count']==11 and len(vr['cop1_witnesses'])==10
            assert verify.adversarial(e1)==6
        elif scenario=='cu1off': check_fault(e1,11)
        elif scenario=='misalign': check_fault(e1,5)
        elif scenario=='tlbmiss': check_fault(e1,3)
        elif scenario=='status': check_fault(e1,0)
        reports[scenario]=e1
    encoded=(json.dumps(reports,sort_keys=True,separators=(',',':'))+'\n').encode()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'results.json').write_bytes(encoded)
    digest=hashlib.sha256(encoded).hexdigest()
    print('PASS exact pinned ares decoded SWC1 -> SP producer matrix')
    print('matrix_events=11 cop1_witnesses=10 forged_rejected=6')
    print('results_sha256='+digest)
if __name__=='__main__': main()
