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
from source_guard import check as source_check

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/rsp-dmem-dma-cpu-fetch-primary'


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
    audit = source_check()
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
            ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp',ROOT/'spikes/058-rsp-defined-imem/verify.py',ROOT/'spikes/059-rsp-word-read-imem/verify.py',ROOT/'spikes/060-rsp-installed-imem-fetch/verify.py')
        print('Building required small prefix baseline',flush=True)
        baseline = builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=extras)
        print('Building required shared-clock sensor',flush=True)
        sensor = builder.build(HERE/'driver.cpp',OUTPUT/'sensor',extra_sources=extras,
            raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True,
            rsp_dmem_access=True,cpu_instruction_access=True,rsp_word_read_access=True,
            rdram_scalar_access=True,fetch_boundary_access=True)
        runs = {}
        for name,executable,mode in (('baseline',baseline,'plain'),('disabled',sensor,'plain'),
                ('instrumented',sensor,'traced'),('repeat',sensor,'traced')):
            runs[name] = json.loads(subprocess.check_output([str(executable),mode],text=True,timeout=30))
        path.write_text(json.dumps(dict(revision=builder.REV,runs=runs),indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for run in runs.values():
        assert len(run['checkpoints'])==19
        for field in ('checkpoints','steps','state','initial_dmem','initial_imem','final_dmem','final_imem','initial_ram','final_ram'):
            assert run[field]==runs['baseline'][field],field
    assert runs['instrumented']==runs['repeat']
    assert runs['baseline']['events']==runs['disabled']['events']==[]
    source,definitions = inspect(runs['instrumented'])
    data = (json.dumps(source,sort_keys=True,separators=(',',':'))+'\n').encode()
    (OUTPUT/'source.json').write_bytes(data)
    receipt = dict(source_sha256=hashlib.sha256(data).hexdigest(),records=len(source['events']),
        source_audit=audit,
        definitions=definitions,reference_revision='9408cb43d4948fc3ea6e152a307a34348df3fe04',
        controlled_checkpoints=19,baseline_disabled_repeat_equal=True,
        source_ancestry_certified=False,mutation_coverage_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS exact source/control/independent census:',len(source['events']),'events;',len(definitions),'definitions',flush=True)
    print('SOURCE_SHA256='+receipt['source_sha256'],flush=True)


if __name__=='__main__': main()
