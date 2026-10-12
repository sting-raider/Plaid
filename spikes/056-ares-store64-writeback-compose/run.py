"""Integration source join using the existing actual generic lower callbacks."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/store64-writeback-primary/reference'


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def worker():
    builder=load('existing_dcache_builder',ROOT/'spikes/034-ares-dcache-writeback-lineage/run.py')
    builder.HERE=HERE;builder.OUTPUT=OUTPUT
    original=builder.build_baseline()
    instrumented,inputs=builder.build_instrumented()
    prior_bytes=(ROOT/'target/ares-64bit-store-spike/results.json').read_bytes()
    assert hashlib.sha256(prior_bytes).hexdigest()=='cf8f82bde400e23c0f2225ee55baaf727b7f09b87c2ca2489c2e295aed6c5f1e'
    prior=json.loads(prior_bytes)
    cases=[]

    def invoke(exe,mode,operation,endian,offset):
        return subprocess.check_output([str(exe),mode,operation,endian,str(offset)],timeout=30)

    def semantic(data):
        return {k:v for k,v in data.items() if k not in ('dcache_events','burst_events')}

    for endian in ('big','little'):
        for operation in ('SD','SDL','SDR'):
            for offset in range(8):
                baseline=json.loads(invoke(original,'plain',operation,endian,offset))
                disabled=json.loads(invoke(instrumented,'plain',operation,endian,offset))
                raw=invoke(instrumented,'traced',operation,endian,offset)
                assert raw==invoke(instrumented,'traced',operation,endian,offset)
                traced=json.loads(raw)
                assert semantic(baseline)==semantic(disabled)==semantic(traced)
                old=next(c for c in prior if (c['mode'],c['op'],c['endian'],c['offset'])==('cached',operation,endian,offset))
                assert traced['initial']==old['before_raw'][:16]
                physical=traced['resident_after_first']
                guest=[physical[i^7 if endian=='little' else i] for i in range(16)]
                if not old['exception']:
                    assert guest==old['after_guest'][:16]
                    assert traced['final_backing']==physical
                else:
                    assert traced['resident_after_first']==traced['initial']==traced['final_backing']
                records=sorted(traced['dcache_events']+traced['burst_events'],key=lambda e:e['ordinal'])
                assert [e['ordinal'] for e in records]==list(range(1,len(records)+1))
                writes=[e for e in traced['dcache_events'] if e['kind']=='store']
                exports=[e for e in traced['burst_events'] if e['write'] and e['dcache']]
                assert bool(writes)==bool(exports)==(not old['exception'])
                assert len(exports)==(0 if old['exception'] else 1)
                cases.append(dict(operation=operation,endian=endian,offset=offset,baseline=baseline,disabled=disabled,traced=traced))
    document=dict(reference=builder.REV,source_inputs=inputs,repeat_equal=True,cases=cases)
    raw=json.dumps(document,sort_keys=True,separators=(',',':')).encode()
    (OUTPUT/'results.json').write_bytes(raw)
    print('PASS 48 decoded cached store cases, repeated equal stores, actual ordered subwrites/backing exports and complete baseline/disabled/repeat controls')
    print('RESULT_SHA256='+hashlib.sha256(raw).hexdigest())


if __name__=='__main__':
    if os.name=='nt':
        script=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',script],check=True)
    else:
        worker()
