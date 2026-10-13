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
OUTPUT = ROOT/'target/cpu-xori-ram-cached-primary'


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
    name='ares/n64/cpu/interpreter-ipu.cpp'
    code=subprocess.check_output(['git','show',f"{audit['revision']}:{name}"],cwd=guard.REF)
    assert hashlib.sha256(code).hexdigest()=='495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152'
    assert b'if(line.hit(access.paddr)) line.setValid(false);' in code
    assert b'auto CPU::XORI(r64& rt, cr64& rs, u16 imm) -> void {\n  rt.u64 = rs.u64 ^ imm;\n}' in code
    audit['sha256'][name]=hashlib.sha256(code).hexdigest()
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
        print('Building required combined CPU XORI/cache baseline',flush=True)
        baseline = builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=extras)
        print('Building required shared-clock sensor',flush=True)
        sensor = builder.build(HERE/'driver.cpp',OUTPUT/'sensor',extra_sources=extras,
            raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True,cache_fill_access=True,cache_operation_access=True,rdram_burst_access=True,
            rsp_dmem_access=True,cpu_instruction_access=True,rsp_word_read_access=True,
            rdram_scalar_access=True,fetch_boundary_access=True,rsp_dma_lifecycle_access=True,rsp_dma_pending_access=True)
        runs = {}
        for name,executable,mode in (('baseline',baseline,'plain'),('disabled',sensor,'plain'),
                ('instrumented',sensor,'traced'),('repeat',sensor,'traced')):
            runs[name] = json.loads(subprocess.check_output([str(executable),mode],text=True,timeout=30))
        path.write_text(json.dumps(dict(revision=builder.REV,runs=runs),indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for run in runs.values():
        assert len(run['checkpoints'])==45
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
        controlled_checkpoints=45,baseline_disabled_repeat_equal=True,
        source_ancestry_certified=False,mutation_coverage_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS exact source/control/independent census:',len(source['events']),'events;',len(definitions),'definitions',flush=True)
    print('SOURCE_SHA256='+receipt['source_sha256'],flush=True)


if __name__=='__main__': main()
