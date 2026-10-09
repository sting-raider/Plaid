"""Actual scoped RSP DMEM sinks, independent baseline/disabled/repeat states."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
from verify import verify,reject_forgeries

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/ares-rsp-dmem-history-spike'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def generate():
    old=ROOT/'spikes/026-ares-rsp-self-stores/driver.cpp'
    source=old.read_text(encoding='utf-8').replace('#include "../003-ares-oracle/driver.cpp"',f'#include "{ROOT/"spikes/003-ares-oracle/driver.cpp"}"')
    marker='#include <vector>'
    assert source.count(marker)==1
    source=source.replace(marker,marker+f'\n#include "{HERE/"observer.hpp"}"')
    marker='  if(cpu.recompiler.enabled || rsp.recompiler.enabled) return 4;'
    assert source.count(marker)==1
    source=source.replace(marker,marker+'''
  #if PLAID_RSP_DMEM_SENSOR
  if(!std::getenv("PLAID_RSP_DISABLE")) {
    plaidRspInstructionObserver=rsp_instruction_event;
    plaidRspDmemObserver=rsp_dmem_event;
  }
  #endif''')
    source=source.replace('  string dmemHash;','  string dmemHash;\n  string machineHash;\n  u32 initialWord;\n  string initialHash;')
    marker='    resetMem();'
    assert source.count(marker)==1
    source=source.replace(marker,'''    ++rspPhase;
    resetMem();
    // Equal out-of-instruction sink: must never acquire an RSP producer context.
    u32 initialValue=(u32(rsp.dmem.data[0])<<24)|(u32(rsp.dmem.data[1])<<16)|(u32(rsp.dmem.data[2])<<8)|rsp.dmem.data[3];
    rsp.dmem.write<Word>(0x1000,initialValue);''')
    source=source.replace('if(scalar) rsp.ipu.r[2].u32 = 0xa1b2c3d4;',
        'if(scalar) rsp.ipu.r[2].u32 = name=="SB-equal" ? u8(initialValue) : 0xa1b2c3d4;')
    source=source.replace('changed, digest(rsp.dmem.data, 4096)}','changed, digest(rsp.dmem.data, 4096),rsp_machine_digest(),initialValue,digest(dmemBefore.data(),4096)}')
    marker='  string finalImem = digest(rsp.imem.data, 4096);'
    source=source.replace(marker,'''  runDecoded("SB-equal",0xa0220000,0x1003,true,[&] {},false);

'''+marker)
    source=source.replace('r.base, r.changedDmem, r.dmemHash.data());',
        'r.base, r.changedDmem, r.dmemHash.data());\n    std::printf(",\\\"machine_sha256\\\":\\\"%s\\\",\\\"initial_word\\\":%u,\\\"initial_sha256\\\":\\\"%s\\\"}",r.machineHash.data(),r.initialWord,r.initialHash.data());')
    source=source.replace('dmem_sha256\\\":\\\"%s\\\"}",','dmem_sha256\\\":\\\"%s\\\"",')
    source=source.replace('  ares::Nintendo64::system.unload();','  rsp_print_events();\n  ares::Nintendo64::system.unload();')
    source=source.replace('results.size() == 29','results.size() == 30')
    OUTPUT.mkdir(parents=True,exist_ok=True)
    paths=[]
    for enabled in (0,1):
        p=OUTPUT/('sensor.cpp' if enabled else 'baseline.cpp')
        p.write_text(f'#define PLAID_RSP_DMEM_SENSOR {enabled}\n'+source,encoding='utf-8',newline='\n');paths.append(p)
    return paths,old


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True);return
    old=load('rsp_old_audit',ROOT/'spikes/026-ares-rsp-self-stores/run.py');audit=old.source_audit()
    builder=old.load_builder();files,original=generate();extras=(original,HERE/'observer.hpp',Path(__file__))
    baseline=builder.build(files[0],OUTPUT/'baseline',extra_sources=extras)
    sensor=builder.build(files[1],OUTPUT/'sensor',rsp_dmem_access=True,extra_sources=extras)
    results={}
    for key,exe in (('baseline',baseline),('disabled',sensor),('instrumented',sensor),('repeat',sensor)):
        env=dict(os.environ)
        if key=='disabled':env['PLAID_RSP_DISABLE']='1'
        else:env.pop('PLAID_RSP_DISABLE',None)
        raw=subprocess.check_output([str(exe)],text=True,env=env,timeout=30)
        rows=[json.loads(line) for line in raw.splitlines() if line.startswith('{')]
        assert len(rows)==2
        results[key]=dict(machine=rows[0],history=rows[1])
    assert all(r['machine']==results['baseline']['machine'] for r in results.values())
    assert results['instrumented']==results['repeat']
    assert results['baseline']['history']['events']==results['disabled']['history']['events']==[]
    assert results['baseline']['history']['foreign_writes']==results['disabled']['history']['foreign_writes']==0
    prior=ROOT/'target/ares-rsp-self-store-spike-29/results.json'
    assert hashlib.sha256(prior.read_bytes()).hexdigest()=='d04a2728422bd184bdcde85469b145384a12f0f9ef8ab7fb98f240f805b10055'
    previous=json.loads(prior.read_text(encoding='utf-8'))['execution']['probes']
    for before,after in zip(previous,results['baseline']['machine']['probes'][:29],strict=True):
        assert before=={k:after[k] for k in before}
    summary=verify(results['instrumented']['history'],results['instrumented']['machine'])
    summary.update(audit=audit,independent_checkpoint_equal=True,forgeries_rejected=reject_forgeries(results["instrumented"]["history"],results["instrumented"]["machine"]))
    path=OUTPUT/'results.json';path.write_text(json.dumps(dict(summary=summary,runs=results),indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS actual RSP DMEM replay and independent baseline/disabled/repeated checkpoints',flush=True)


if __name__=='__main__':main()
