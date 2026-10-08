#!/usr/bin/env python3
"""Build and execute the real pinned ares PI/queue/CPU fixture with external queue identities."""
from pathlib import Path
import hashlib, importlib.util, json, subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REF=ROOT/'.refs/ares'
OUT=ROOT/'target/ares-pi-queue-dispatch/actual'
REV='9408cb43d4948fc3ea6e152a307a34348df3fe04'

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def build():
    builder=load('ares_builder',ROOT/'spikes/003-ares-oracle/run.py')
    prepare=load('queue_prepare',ROOT/'spikes/032-ares-queue-identity/prepare.py')
    # The capability fixture inherits both `nall::queue` and the N64 global
    # `ares::Nintendo64::queue` via using-directives in the common driver.
    # Generate a compile-only shadow *beside* the source fixture so its relative
    # includes remain exact, then delete it after both binaries are built.
    source=(HERE/'driver.cpp').read_text()
    marker='#endif\n\nstruct Fact {'
    assert source.count(marker)==1
    source=source.replace(marker,'#endif\n\n#define queue ares::Nintendo64::queue\n\nstruct Fact {')
    OUT.mkdir(parents=True,exist_ok=True)
    generated=HERE/'_driver.generated.cpp'; generated.write_text(source)
    baseline_source=OUT/'baseline.generated.cpp'
    baseline_source.write_text(f'#define PLAID_PI_QUEUE_SENSOR 0\n#include "{generated}"\n')
    try:
        baseline=builder.build(baseline_source,OUT/'baseline',extra_sources=(generated,))
        observed_dir=OUT/'observed'
        prepare.generate(REF,observed_dir/'include/nall/priority-queue.hpp')
        observed=builder.build(generated,observed_dir,
            raw_fetch_access=True,physical_fetch_access=True,pi_dma_access=True,
            extra_sources=(HERE/'observer.hpp',ROOT/'spikes/032-ares-queue-identity/prepare.py'))
        return baseline,observed
    finally:
        generated.unlink(missing_ok=True)

def phase(data,n): return next(x for x in data['facts'] if x['phase']==n)
def queue_phase(data,n): return [x for x in data['queue_trace'] if x['phase']==n]
def pi_phase(data,n): return [x for x in data['pi_trace'] if x['phase']==n]

def verify(data):
    f1,f2,f3,f4,f5=(phase(data,n) for n in range(1,6))
    # Real PI write copies are visible before the scheduled completion handler.
    assert (f1['busy_request'],f1['interrupt_request'],f1['byte0'])==(1,0,0xa0)
    assert (f1['busy_end'],f1['interrupt_end'])==(0,1)
    assert (f2['busy_request'],f2['interrupt_request'],f2['byte0'])==(1,0,0xc0)
    assert (f2['busy_end'],f2['interrupt_end'])==(0,0)
    assert f3['aux']==512 and (f3['busy_request'],f3['interrupt_request'],f3['byte0'])==(1,0,0xe0)
    assert (f3['busy_end'],f3['interrupt_end'])==(1,0)
    assert (f4['busy_end'],f4['interrupt_end'],f4['aux'])==(0,1,2)
    assert (f5['busy_request'],f5['interrupt_request'])==(1,0) and (f5['busy_end'],f5['interrupt_end'])==(0,1)

    requests=data['requests']; normal=requests['normal']; cancel=requests['cancel']; reject=requests['reject']; restore=requests['restore']
    assert all((normal,cancel,reject,restore)) and len({normal,cancel,reject,restore})==4

    # 1: exact request token survives actual heap removal and reaches actual dmaFinished.
    q1=queue_phase(data,1); p1=pi_phase(data,1)
    normal_inserts=[x for x in q1 if x['kind']==4 and x['request']==normal and x['event']==1]
    assert len(normal_inserts)==1 and normal_inserts[0]['token']
    token1=normal_inserts[0]['token']
    removals=[x for x in q1 if x['kind']==5 and x['valid'] and x['token']==token1]
    completions=[x for x in p1 if x['kind']==8]
    assert len(removals)==1 and len(completions)==1
    assert (completions[0]['request'],completions[0]['token'])==(normal,token1)
    assert normal_inserts[0]['o'] < removals[0]['o'] < completions[0]['o']

    # 2: guest PI_STATUS cancellation invalidates the request token; no completion callback.
    q2=queue_phase(data,2); p2=pi_phase(data,2)
    token2=next(x['token'] for x in q2 if x['kind']==4 and x['request']==cancel and x['event']==1)
    assert any(x['kind']==8 and x['event']==1 and x['token']==token2 for x in q2)
    assert any(x['kind']==5 and not x['valid'] and x['token']==token2 for x in q2)
    assert not [x for x in p2 if x['kind']==8]

    # 3: actual full queue rejects CPU::queueInsert while PI still performs dmaWrite now.
    q3=queue_phase(data,3); p3=pi_phase(data,3)
    assert len([x for x in q3 if x['kind']==2 and x['event']==1])==1
    assert not [x for x in q3 if x['kind']==4 and x['request']==reject and x['event']==1]
    assert any(x['kind']==1 and x['request']==reject for x in p3)  # dmaWrite entered
    assert not [x for x in p3 if x['kind']==8]

    # 4: same event value and equal deadline produce two distinct unowned identities.
    q4=queue_phase(data,4); p4=pi_phase(data,4)
    inserts4=[x for x in q4 if x['kind']==4 and x['event']==1]
    assert len(inserts4)==2 and inserts4[0]['clock']==inserts4[1]['clock'] and inserts4[0]['token']!=inserts4[1]['token']
    assert all(x['request']==0 for x in inserts4)
    comps4=[x for x in p4 if x['kind']==8]
    assert len(comps4)==2 and {x['token'] for x in comps4}=={x['token'] for x in inserts4} and all(x['request']==0 for x in comps4)

    # 5: queue serialization/restore keeps the real event but our external identity is erased.
    q5=queue_phase(data,5); p5=pi_phase(data,5)
    token5=next(x['token'] for x in q5 if x['kind']==4 and x['request']==restore and x['event']==1)
    assert token5 and len([x for x in q5 if x['kind']==9])==2
    comps5=[x for x in p5 if x['kind']==8]
    assert len(comps5)==1 and (comps5[0]['token'],comps5[0]['request'])==(0,0)

    return dict(normal_request=normal,normal_token=token1,canceled_token=token2,
                rejected_request=reject,duplicate_tokens=[x['token'] for x in inserts4],
                pre_restore_token=token5,queue_records=len(data['queue_trace']),pi_records=len(data['pi_trace']))

def main():
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REF,text=True).strip()==REV
    subprocess.run(['git','-c','core.autocrlf=true','diff','--quiet','HEAD'],cwd=REF,check=True)
    baseline,observed=build()
    def call(exe,mode): return subprocess.check_output([str(exe),mode],text=True,timeout=60)
    baseline_raw=call(baseline,'plain')
    disabled_raw=call(observed,'plain')
    traced_raw=call(observed,'traced'); repeat_raw=call(observed,'traced')
    assert traced_raw==repeat_raw
    base,disabled,traced=map(json.loads,(baseline_raw,disabled_raw,traced_raw))
    assert base['queue_trace']==base['pi_trace']==[] and disabled['queue_trace']==disabled['pi_trace']==[]
    assert base['facts']==disabled['facts']==traced['facts']
    assert base['state']==disabled['state']==traced['state']
    result=verify(traced)
    receipt=dict(revision=REV,result=result,
      baseline_disabled_enabled_state_equal=True,repeat_trace_byte_identical=True,
      actual_pi_iowrite_executed=True,actual_pi_dmawrite_executed=True,
      actual_queue_container_executed=True,actual_cpu_synchronize_executed=True,
      dispatch_to_dmafinished_join_observed=True,hardware_timing_claimed=False,
      dispatch_is_byte_transfer_completion=False,serialization_identity_certified=False,
      traced_sha256=hashlib.sha256(traced_raw.encode()).hexdigest())
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'traced.json').write_text(traced_raw)
    path=OUT/'results.json'; path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print('ACTUAL_TRACE_SHA256='+receipt['traced_sha256'])
    print('ACTUAL_RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest())
    print(json.dumps(receipt,sort_keys=True))
    print('PASS: actual pinned PI request token survives to CPU-driven dmaFinished; cancellation/rejection/duplicates/restore fail closed')

if __name__=='__main__': main()
