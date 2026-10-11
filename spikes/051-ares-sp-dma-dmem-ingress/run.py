"""Reproduce the bounded successful RDRAM-to-DMEM source/sink lane fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from prepare import build_traced
from verify import verify
from adversaries import check

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / 'target/ares-sp-dma-dmem-ingress-primary'
SOURCE_BLOBS = {
    'ares/n64/rdram/rdram.hpp': 'c718ec2e9b2a78610353562cbc81dd973b278ee2',
    'ares/n64/rsp/dma.cpp': 'd49cbd601b68244eff6f088e68da2380c200aad9',
    'ares/n64/rsp/io.cpp': '19bf54735fdfcf622374b1533c6c6e966b5ea51a',
    'ares/n64/rsp/rsp.cpp': 'b743688847a63796a3582caffaaba014b5da66c4',
    'ares/n64/rsp/rsp.hpp': '3f05ea5e7b266245c2091dac8a7aad7680f1361d',
}


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath',
            '-a', Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True)
        return
    subprocess.run([sys.executable, str(HERE/'test_verify.py')], check=True)
    spec = importlib.util.spec_from_file_location('ingress_builder', ROOT/'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    for name, blob in SOURCE_BLOBS.items():
        assert subprocess.check_output(['git', 'rev-parse', builder.REV+':'+name],
            cwd=builder.REF, text=True).strip() == blob
    baseline = builder.build(HERE/'driver.cpp', OUTPUT/'baseline')
    sensor = build_traced(builder, HERE/'driver.cpp', OUTPUT)
    original_raw = subprocess.check_output([str(baseline), 'plain'], text=True, timeout=30)
    disabled_raw = subprocess.check_output([str(sensor), 'plain'], text=True, timeout=30)
    raw = subprocess.check_output([str(sensor), 'traced'], text=True, timeout=30)
    repeat = subprocess.check_output([str(sensor), 'traced'], text=True, timeout=30)
    assert raw == repeat
    original, disabled, data = map(json.loads, (original_raw, disabled_raw, raw))
    assert original['events'] == disabled['events'] == []
    assert original['state'] == disabled['state'] == data['state']
    summary = verify(data)
    rejected = check(data)
    path = OUTPUT/'results.json'
    path.write_text(json.dumps(dict(schema_version=0, revision=builder.REV,
        source_blobs=SOURCE_BLOBS, reported_state_equality=True, repeat_equal=True,
        raw=data, summary=summary, rejected_measured_forgeries=rejected),
        indent=2, sort_keys=True)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(summary, sort_keys=True), flush=True)
    print('TRACE_SHA256='+hashlib.sha256(raw.encode()).hexdigest(), flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    print('PASS finite DMEM ingress lanes; successful read identity is not ultimate ancestry', flush=True)


if __name__ == '__main__':
    main()
