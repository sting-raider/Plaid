#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, subprocess, sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUT=ROOT/'target/ares-pi-queue-dispatch'
REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'

def run(cmd): return subprocess.check_output(cmd,text=True,cwd=ROOT)

def main():
    guard=run([sys.executable,str(HERE/'source_guard.py'),str(REF)])
    model1=run([sys.executable,str(HERE/'model.py')])
    model2=run([sys.executable,str(HERE/'model.py')])
    assert model1==model2
    report=json.loads(model1)
    assert report['sha256']=='ebab07300e683fa8d555f0fc4228fe3627b04bd261778373594be76cb3be0b27'
    assert report['scenarios']['forgeries_rejected']==5
    assert report['scenarios']['full_queue_reject']['copies'][0]['scheduled'] is False
    assert report['scenarios']['serialize_loses_identity']['certified']==[]
    OUT.mkdir(parents=True,exist_ok=True)
    receipt=dict(revision=REV,
      source_guard_sha256=hashlib.sha256(guard.encode()).hexdigest(),
      model_stdout_sha256=hashlib.sha256(model1.encode()).hexdigest(),
      model_report_sha256=report['sha256'],
      fuzz=report['fuzz'],
      exact_reference_execution=False,
      actual_queue_execution_inherited_from='spikes/032-ares-queue-identity',
      full_cpu_pi_execution=False,
      result='PARTIAL')
    path=OUT/'results.json'; path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(guard,end='')
    print('MODEL_REPORT_SHA256='+report['sha256'])
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest())
    print('PASS: request/insertion/dispatch/completion contract rejects cancellation, capacity failure, restore-loss and forged joins')

if __name__=='__main__': main()
