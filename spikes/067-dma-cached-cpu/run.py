"""Small pinned-reference prefix with original-clock RSP definition ancestry."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import inspect

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/dma-cached-cpu-primary'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    if os.name=='nt':
        path = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        command = ['wsl','-d','Ubuntu','--exec','python3',path]
        if args.verify_existing: command.append('--verify-existing')
        subprocess.run(command,check=True)
        return
    path = OUTPUT/'results.json'
    spec = importlib.util.spec_from_file_location('source_guard',ROOT/'spikes/061-rsp-dmem-dma-cpu-fetch/source_guard.py')
    guard = importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    audit = guard.check()
    cache_header = subprocess.check_output(['git','show',f"{audit['revision']}:ares/n64/cpu/cpu.hpp"],cwd=guard.REF)
    cache_digest = hashlib.sha256(cache_header).hexdigest()
    assert cache_digest=='6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27'
    audit['sha256']['ares/n64/cpu/cpu.hpp']=cache_digest
    if args.verify_existing:
        retained = json.loads(path.read_bytes())
        assert retained['revision']==audit['revision']
        runs = retained['runs']
    else:
        spec = importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        extras = (HERE/'driver.cpp',ROOT/'spikes/047-ares-rsp-cpu-imem-compose/driver.cpp',
            ROOT/'spikes/047-ares-rsp-cpu-imem-compose/observer.hpp',
            ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp')
        baseline = OUTPUT/'baseline/oracle'
        manifest = OUTPUT/'baseline/build.json'
        annotation = '''    phase(27);
    #if PLAID_RSP_CPU_IMEM_SENSOR
    compose_push("cpu_reentry",composeEvents.size()+1,0xffffffff80006030ull,0,0,0,0,0,0,true);
    #endif
    cpuStep(27,12,false);'''
        original = (ROOT/'spikes/047-ares-rsp-cpu-imem-compose/driver.cpp').read_text().replace(annotation,'    cpuStep(27,12,false);').encode()
        reuse = baseline.exists() and manifest.exists() and hashlib.sha256(baseline.read_bytes()).hexdigest()=='1ff5822d74c4c84f744c5b4e542ba8aad77c1c615009284cf8a32d5e802d7eb2' and hashlib.sha256(manifest.read_bytes()).hexdigest()=='ca3d30ea92041889a7f14d70b600c3344c6af3417c142b558ae4ffdf5c9ba883'
        if reuse:
            inputs=json.loads(manifest.read_bytes())
            assert hashlib.sha256(original).hexdigest()==inputs['extra_sources']['spikes/047-ares-rsp-cpu-imem-compose/driver.cpp']
            for source_path,digest in inputs['extra_sources'].items():
                if source_path!='spikes/047-ares-rsp-cpu-imem-compose/driver.cpp':assert hashlib.sha256((ROOT/source_path).read_bytes()).hexdigest()==digest
            print('Reusing authenticated unchanged guest baseline; only missing sensor root annotation changed',flush=True)
        else:
            print('Building required small prefix baseline',flush=True)
            baseline = builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=extras)
        print('Building required shared-clock sensor',flush=True)
        sensor = builder.build(HERE/'driver.cpp',OUTPUT/'sensor',extra_sources=extras,
            raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True,cache_fill_access=True,rdram_burst_access=True,
            rsp_dmem_access=True,cpu_instruction_access=True,rsp_word_read_access=True,
            rdram_scalar_access=True,fetch_boundary_access=True,rsp_dma_lifecycle_access=True,rsp_dma_pending_access=True)
        runs = {}
        for name,executable,mode in (('baseline',baseline,'plain'),('disabled',sensor,'plain'),
                ('instrumented',sensor,'traced'),('repeat',sensor,'traced')):
            runs[name] = json.loads(subprocess.check_output([str(executable),mode],text=True,timeout=30))
        path.write_text(json.dumps(dict(revision=builder.REV,runs=runs),indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for run in runs.values():
        assert len(run['checkpoints'])==31
        for field in ('checkpoints','steps','state','initial_dmem','initial_imem','final_dmem','final_imem','initial_ram','final_ram','initial_pending'):
            assert run[field]==runs['baseline'][field],field
    assert runs['instrumented']==runs['repeat']
    assert runs['baseline']['events']==runs['disabled']['events']==[]
    source,definitions = inspect(runs['instrumented'])
    data = (json.dumps(source,sort_keys=True,separators=(',',':'))+'\n').encode()
    (OUTPUT/'source.json').write_bytes(data)
    receipt = dict(source_sha256=hashlib.sha256(data).hexdigest(),records=len(source['events']),
        source_audit=audit,
        definitions=definitions,reference_revision='9408cb43d4948fc3ea6e152a307a34348df3fe04',
        controlled_checkpoints=31,baseline_disabled_repeat_equal=True,
        source_ancestry_certified=False,mutation_coverage_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS exact source/control/independent census:',len(source['events']),'events;',len(definitions),'definitions',flush=True)
    print('SOURCE_SHA256='+receipt['source_sha256'],flush=True)


if __name__=='__main__': main()
