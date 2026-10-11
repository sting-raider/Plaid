"""Reconcile the existing finite XORI experiment with shared strict sensing."""
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
OUTPUT = ROOT/'target/ares-cpu-xori-transform-primary'


def main():
    if os.name == 'nt':
        path = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath', '-a',
            Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', path], check=True)
        return
    subprocess.run([sys.executable, str(HERE/'test_verify.py')], check=True)
    spec = importlib.util.spec_from_file_location('transform_builder', ROOT/'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    reference = ROOT/'.refs/ares'
    assert 'op(0x0e, XORI, RT, RS, IMMu16);' in (reference/'ares/n64/cpu/interpreter.cpp').read_text()
    assert 'auto CPU::XORI(r64& rt, cr64& rs, u16 imm) -> void {\n  rt.u64 = rs.u64 ^ imm;\n}' in (reference/'ares/n64/cpu/interpreter-ipu.cpp').read_text()
    extras = (HERE/'driver.cpp', ROOT/'spikes/044-ares-cpu-copy-dataflow/observer.hpp',
        ROOT/'spikes/044-ares-cpu-copy-dataflow/prepare.py', ROOT/'spikes/042-ares-rsp-dmem-history/observer.hpp')
    baseline = builder.build(HERE/'baseline.cpp', OUTPUT/'baseline', extra_sources=extras)
    sensor = builder.build(HERE/'driver.cpp', OUTPUT/'sensor', extra_sources=extras,
        raw_fetch_access=True, physical_fetch_access=True, rdram_scalar_access=True, cpu_instruction_access=True)
    runs = {}
    for name, executable, mode in (('baseline', baseline, 'plain'), ('disabled', sensor, 'plain'),
            ('instrumented', sensor, 'traced'), ('repeat', sensor, 'traced')):
        runs[name] = json.loads(subprocess.check_output([str(executable), mode], text=True, timeout=30))
    for run in runs.values():
        assert len(run['checkpoints']) == 20
        assert all(run[field] == runs['baseline'][field] for field in ('checkpoints', 'facts', 'state'))
    assert runs['instrumented'] == runs['repeat']
    assert all(not runs[name][field] for name in ('baseline', 'disabled')
        for field in ('instruction_events', 'scalar_events'))
    summary = verify(runs['instrumented'])
    summary['forgeries_rejected'] = reject_forgeries(runs['instrumented'])
    output = OUTPUT/'results.json'
    output.write_text(json.dumps(dict(schema_version=0, revision=builder.REV, summary=summary, runs=runs),
        indent=2, sort_keys=True)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(summary, sort_keys=True), flush=True)
    print('RESULT_SHA256='+hashlib.sha256(output.read_bytes()).hexdigest(), flush=True)
    print('PASS bounded XORI transformation, explicit zero transform and independent checkpoints', flush=True)


if __name__ == '__main__':
    main()
