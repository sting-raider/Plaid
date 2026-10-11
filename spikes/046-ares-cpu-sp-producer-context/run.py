"""Pinned original/disabled/enabled/repeated actual CPU-to-SP producer checks."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import verify, reject_forgeries

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/ares-cpu-sp-producer-primary'


def main():
    if os.name == 'nt':
        path = subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',
            Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True)
        return
    subprocess.run([sys.executable,str(HERE/'test_verify.py')],check=True)
    spec = importlib.util.spec_from_file_location('sp_producer_builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    extras = (HERE/'driver.cpp',ROOT/'spikes/044-ares-cpu-copy-dataflow/prepare.py',
        ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp')
    baseline = builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=extras)
    sensor = builder.build(HERE/'driver.cpp',OUTPUT/'sensor',extra_sources=extras,
        raw_fetch_access=True,physical_fetch_access=True,sp_backing_access=True,cpu_instruction_access=True)
    runs = {}
    for name, executable, mode in (('baseline',baseline,'plain'),('disabled',sensor,'plain'),
            ('instrumented',sensor,'traced'),('repeat',sensor,'traced')):
        runs[name] = json.loads(subprocess.check_output([str(executable),mode],text=True,timeout=30))
    for run in runs.values():
        assert len(run['checkpoints']) == 8
        assert all(run[field] == runs['baseline'][field] for field in ('checkpoints','initial_imem','final_imem'))
    assert runs['instrumented'] == runs['repeat']
    assert runs['baseline']['events'] == runs['disabled']['events'] == []
    summary = verify(runs['instrumented'])
    summary['forgeries_rejected'] = reject_forgeries(runs['instrumented'])
    output = OUTPUT/'results.json'
    output.write_text(json.dumps(dict(schema_version=0,revision=builder.REV,summary=summary,runs=runs),
        indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(output.read_bytes()).hexdigest(),flush=True)
    print('PASS actual CPU decoder/GPR/FPR to SP Word effects and independent checkpoints',flush=True)


if __name__ == '__main__':
    main()
