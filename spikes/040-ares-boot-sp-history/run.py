"""Observe SP backing in boot and preserve complete prior capture byte for byte."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import inspect

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/ares-boot-sp-history-spike'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as file:
        while chunk:=file.read(1024*1024):sha.update(chunk)
    return sha.hexdigest()


def capture(budget):
    boot=load('sp_boot',ROOT/'spikes/008-ares-pif-boot/run.py')
    history=load('sp_history_profile',ROOT/'spikes/027-ares-boot-history/run.py')
    observers=(HERE/'observer.hpp',ROOT/'spikes/037-ares-boot-pi-queue-history/observer.hpp',
        ROOT/'spikes/030-ares-boot-pi-history/observer.hpp',ROOT/'spikes/027-ares-boot-history/observer.hpp',
        ROOT/'spikes/032-ares-queue-identity/observer.hpp',ROOT/'spikes/011-ares-cache-fetch/driver.cpp')
    return boot.worker(budget,driver=HERE/'driver.cpp',output_root=OUTPUT,
        boot_inputs=history.PROFILE,cache_policy='selected_icache_line_at_prologue',
        build_options=dict(cache_fill_access=True,cache_operation_access=True,rdram_burst_access=True,
            rdram_scalar_access=True,fetch_boundary_access=True,pi_dma_access=True,queue_access=True,sp_backing_access=True),
        observer_sources=observers,run_timeout=600)


def verify(budget):
    boot=load('sp_boot_verify',ROOT/'spikes/008-ares-pif-boot/run.py')
    history=load('sp_history_verify',ROOT/'spikes/027-ares-boot-history/run.py')
    queue=load('sp_queue_verify',ROOT/'spikes/037-ares-boot-pi-queue-history/verify.py')
    pi=load('sp_pi_verify',ROOT/'spikes/030-ares-boot-pi-history/verify.py')
    current=OUTPUT/str(budget)
    baseline=ROOT/'target/ares-boot-pi-queue-history-spike/queue'/str(budget)
    states=[json.loads((current/f'{mode}.json').read_text(encoding='utf-8')) for mode in ('plain','traced','repeat')]
    prior_states=[json.loads((baseline/f'{mode}.json').read_text(encoding='utf-8')) for mode in ('plain','traced','repeat')]
    assert all(s==states[0] for s in states+prior_states)
    for suffix in ('ndjson','messages','ndjson.history.ndjson'):
        boot.equal_files(current/f'traced.{suffix}',current/f'repeat.{suffix}')
    for suffix in ('ndjson','messages'):
        boot.equal_files(current/f'traced.{suffix}',baseline/f'traced.{suffix}')
    assert not (current/'plain.ndjson.history.ndjson').exists()
    raw=current/'traced.ndjson.history.ndjson';v2=current/'v2-projection.ndjson'
    with v2.open('wb') as file:report=inspect(history.records(raw),file)
    boot.equal_files(v2,baseline/'traced.ndjson.history.ndjson')
    print('PASS complete v2/v5 bytes and independent baseline/disabled/repeated machine checkpoints',flush=True)
    v1=current/'v1-projection.ndjson'
    with v1.open('wb') as file:report['queue']=queue.inspect(history.records(v2),file)
    v0=current/'v0-projection.ndjson'
    with v0.open('wb') as file:report['pi_effects']=pi.inspect(history.records(v1),boot.ROM.read_bytes(),file)
    report['prior']=history.verify(v0,current/'traced.ndjson',budget)
    report.update(history_sha256=digest(raw),v2_projection_sha256=digest(v2),
        paired_fetch_sha256=digest(current/'traced.ndjson'),checkpoint_unchanged=True)
    path=current/'sp-history-results.json'
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    summary={k:v for k,v in report.items() if k not in ('samples','queue','pi_effects','prior','dma_store_receipts')}
    summary.update(dma_stores=len(report['dma_store_receipts']),bound_dma_receipts=sum(r['read_ordinal'] is not None for r in report['dma_store_receipts']))
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('REPORT_SHA256='+digest(path),flush=True)
    print('PASS finite actual SP backing reads/stores with complete strict v2/v1/v0/v5 sources',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--budget',type=int,default=10000)
    parser.add_argument('--verify-existing',action='store_true');args=parser.parse_args()
    assert 0<args.budget<=1000000
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path,*sys.argv[1:]],check=True)
    else:
        if not args.verify_existing:capture(args.budget)
        verify(args.budget)


if __name__=='__main__':main()
