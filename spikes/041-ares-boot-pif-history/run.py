"""Capture PIF bank effects and preserve all already verified prior sources."""
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
OUTPUT=ROOT/'target/ares-boot-pif-history-spike'
PRIOR_REPORTS={10000:'a9694b37a287e5f6ce0ec92c32ac94149e651b055ef7248b41b17b9b02d3229e',
    610000:'14a6fa5d1a0a99d8b0a17790f3a06380da1a9faf896163b152b1d41a1d9bb44b'}


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as file:
        while chunk:=file.read(1024*1024):sha.update(chunk)
    return sha.hexdigest()


def capture(budget):
    boot=load('pif_boot',ROOT/'spikes/008-ares-pif-boot/run.py')
    history=load('pif_boot_profile',ROOT/'spikes/027-ares-boot-history/run.py')
    observers=(HERE/'observer.hpp',ROOT/'spikes/040-ares-boot-sp-history/observer.hpp',
        ROOT/'spikes/037-ares-boot-pi-queue-history/observer.hpp',ROOT/'spikes/030-ares-boot-pi-history/observer.hpp',
        ROOT/'spikes/027-ares-boot-history/observer.hpp',ROOT/'spikes/032-ares-queue-identity/observer.hpp',
        ROOT/'spikes/011-ares-cache-fetch/driver.cpp')
    return boot.worker(budget,driver=HERE/'driver.cpp',output_root=OUTPUT,boot_inputs=history.PROFILE,
        cache_policy='selected_icache_line_at_prologue',build_options=dict(cache_fill_access=True,
            cache_operation_access=True,rdram_burst_access=True,rdram_scalar_access=True,
            fetch_boundary_access=True,pi_dma_access=True,queue_access=True,sp_backing_access=True,pif_backing_access=True),
        observer_sources=observers,run_timeout=600)


def verify(budget):
    boot=load('pif_boot_verify',ROOT/'spikes/008-ares-pif-boot/run.py')
    history=load('pif_history_rows',ROOT/'spikes/027-ares-boot-history/run.py')
    current=OUTPUT/str(budget);prior=ROOT/'target/ares-boot-sp-history-spike'/str(budget)
    prior_path=prior/'rust-sp-history-report.json'
    # Fixed fixture receipts already passed full Python/Rust source reconstruction.
    # Reuse only those exact reports after comparing every old source byte below.
    assert digest(prior_path)==PRIOR_REPORTS[budget]
    prior_report=json.loads(prior_path.read_text(encoding='utf-8'))
    states=[json.loads((d/f'{mode}.json').read_text(encoding='utf-8'))
        for d in (prior,current) for mode in ('plain','traced','repeat')]
    assert all(s==states[0] for s in states)
    for suffix in ('ndjson','messages','ndjson.history.ndjson'):
        boot.equal_files(current/f'traced.{suffix}',current/f'repeat.{suffix}')
    for suffix in ('ndjson','messages'):boot.equal_files(current/f'traced.{suffix}',prior/f'traced.{suffix}')
    assert not (current/'plain.ndjson.history.ndjson').exists()
    raw=current/'traced.ndjson.history.ndjson';projection=current/'v3-projection.ndjson'
    with projection.open('wb') as file:report=inspect(history.records(raw),boot.FIRMWARE.read_bytes(),file)
    boot.equal_files(projection,prior/'traced.ndjson.history.ndjson')
    assert digest(projection)==prior_report['history_sha256']
    assert digest(current/'traced.ndjson')==prior_report['projection']['projection']['projection']['fetch_sha256']
    report.update(history_sha256=digest(raw),v3_projection_sha256=digest(projection),
        paired_fetch_sha256=digest(current/'traced.ndjson'),projection=prior_report,checkpoint_unchanged=True)
    path=current/'pif-history-results.json'
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('samples','projection','write_attempts')},sort_keys=True),flush=True)
    print('REPORT_SHA256='+digest(path),flush=True)
    print('PASS actual PIF reads/write attempts and exact complete previously verified v3/v2/v1/v0/v5 sources',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--budget',type=int,default=10000)
    parser.add_argument('--verify-existing',action='store_true');args=parser.parse_args()
    assert args.budget in PRIOR_REPORTS
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path,*sys.argv[1:]],check=True)
    else:
        if not args.verify_existing:capture(args.budget)
        verify(args.budget)


if __name__=='__main__':main()
