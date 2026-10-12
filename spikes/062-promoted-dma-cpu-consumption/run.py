"""New lifecycle sensor against authenticated unchanged v4 reference controls."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
from verify import inspect

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/promoted-dma-cpu-consumption-primary'
PRIOR=ROOT/'target/rsp-dmem-dma-cpu-fetch-primary'
BASELINE_DIGESTS={
    'results.json':'a9c6ef980c5cd11a0c1ba0ed9ae7a706e2c9ebf486293cad35c4bb847f9cb710',
    'baseline/oracle':'6f0a45544ec0b4b022a9b40c1a8f864ae10477454034f8a62d69aedb96e36307',
    'baseline/build.json':'8d35d6212e0227e79a4cc657de92b95bb93147664b0ad6e60db61f6a3972556f',
    'source.json':'0e6d95cb879272bbf123981d6c8fe91753ddcf8fe456abefdbe450c09714fc9b',
}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--verify-existing',action='store_true');args=parser.parse_args()
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        command=['wsl','-d','Ubuntu','--exec','python3',path]
        if args.verify_existing:command.append('--verify-existing')
        subprocess.run(command,check=True);return
    OUTPUT.mkdir(parents=True,exist_ok=True)
    for relative,digest in BASELINE_DIGESTS.items():assert hashlib.sha256((PRIOR/relative).read_bytes()).hexdigest()==digest,relative
    retained=json.loads((PRIOR/'results.json').read_bytes())['runs']['baseline']
    spec=importlib.util.spec_from_file_location('guard',ROOT/'spikes/061-rsp-dmem-dma-cpu-fetch/source_guard.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard);audit=guard.check()
    path=OUTPUT/'results.json'
    if args.verify_existing:
        previous=json.loads(path.read_bytes());assert previous['revision']==audit['revision'];runs=previous['runs']
    else:
        spec=importlib.util.spec_from_file_location('builder',ROOT/'spikes/003-ares-oracle/run.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        extras=(HERE/'driver.cpp',ROOT/'spikes/047-ares-rsp-cpu-imem-compose/driver.cpp',ROOT/'spikes/047-ares-rsp-cpu-imem-compose/observer.hpp',
            ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp')
        print('Reusing authenticated unchanged reference; building required new lifecycle sensor',flush=True)
        sensor=builder.build(HERE/'driver.cpp',OUTPUT/'sensor',extra_sources=extras,
            raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True,rsp_dmem_access=True,
            cpu_instruction_access=True,rsp_word_read_access=True,rdram_scalar_access=True,
            fetch_boundary_access=True,rsp_dma_lifecycle_access=True)
        runs={}
        for name,exe,mode in (('baseline',PRIOR/'baseline/oracle','plain'),('disabled',sensor,'plain'),('instrumented',sensor,'traced'),('repeat',sensor,'traced')):
            runs[name]=json.loads(subprocess.check_output([str(exe),mode],text=True,timeout=30))
        path.write_text(json.dumps(dict(revision=builder.REV,runs=runs),indent=2,sort_keys=True)+'\n',encoding='utf-8')
    assert runs['baseline']==retained,'reused baseline differs from authenticated controls'
    for run in runs.values():
        assert len(run['checkpoints'])==19
        for field in ('checkpoints','steps','state','initial_dmem','initial_imem','final_dmem','final_imem','initial_ram','final_ram'):
            assert run[field]==retained[field],field
    assert runs['instrumented']==runs['repeat']
    assert runs['baseline']['events']==runs['disabled']['events']==[]
    source,definitions=inspect(runs['instrumented'])
    data=(json.dumps(source,sort_keys=True,separators=(',',':'))+'\n').encode();(OUTPUT/'source.json').write_bytes(data)
    receipt=dict(source_sha256=hashlib.sha256(data).hexdigest(),records=len(source['events']),definitions=definitions,
        source_audit=audit,baseline_digests=BASELINE_DIGESTS,controlled_checkpoints=19,
        baseline_disabled_repeat_equal=True,mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
    (OUTPUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('PASS exact promoted source/control/independent census:',len(source['events']),'events;',len(definitions),'definitions',flush=True)
    print('SOURCE_SHA256='+receipt['source_sha256'],flush=True)

if __name__=='__main__':main()
