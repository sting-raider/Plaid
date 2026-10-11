"""Reproduce unmodified guest TLBR/context/resident behavior at the exact pin."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from source_guard import main as source_guard
from verify import verify, reject_forgeries

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/ares-tlbr-cache-lifetime-primary'
SOURCE_BLOBS = {
    'ares/n64/cpu/interpreter.cpp': 'f8f95f5ccdd9e3b9c0bd48c03d80b74e9c5a83a9',
    'ares/n64/cpu/interpreter-scc.cpp': 'c3d119bf4931c4616ae297a4c18b561490207e11',
    'ares/n64/cpu/tlb.cpp': '3bec71ea1039b7fc5a5b2816ecc2b2ed534872dc',
    'ares/n64/cpu/cpu.hpp': 'b51000d99e1e8818ad04a8c747a8170b0e98fae8',
    'ares/n64/cpu/memory.cpp': 'f362ef67ab41ccf57330bbedd6f614e07a61dd17',
}
GOPHER_CACHE_BLOB = 'abeadc57a8292cf34c5fda702bd359043269021e'


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath',
            '-a', Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True)
        return
    subprocess.run([sys.executable, str(HERE/'test_verify.py')], check=True)
    source_guard()
    spec = importlib.util.spec_from_file_location('tlbr_builder', ROOT/'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    for name, blob in SOURCE_BLOBS.items():
        assert subprocess.check_output(['git', 'rev-parse', builder.REV+':'+name],
            cwd=builder.REF, text=True).strip() == blob
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD:src/device/cache.rs'],
        cwd=ROOT/'.refs/gopher64', text=True).strip() == GOPHER_CACHE_BLOB
    external = {
        'mupen64plus-core': ('ba95bab92a76744753bfe61470823a4937850ab0', 'src/device/r4300/tlb.c', 'b7a29e8da6f89c42b825ee33fed4af762ed6fd83'),
        'n64-systemtest': ('196f5421173220eb2f63a7a99c64795dc0ea0698', 'src/tests/tlb/mod.rs', '34bbe10575b3dfe29d9efbafafd3c49254495293'),
    }
    for reference, (rev, name, blob) in external.items():
        assert subprocess.check_output(['git', 'rev-parse', rev+':'+name],
            cwd=ROOT/'.refs'/reference, text=True).strip() == blob
    exe = builder.build(HERE/'driver.cpp', OUTPUT/'build')
    raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    repeat = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert raw == repeat
    data = json.loads(raw)
    summary = verify(data)
    rejected = reject_forgeries(data)
    path = OUTPUT/'results.json'
    path.write_text(json.dumps(dict(schema_version=0, revision=builder.REV,
        source_blobs=SOURCE_BLOBS, gopher_cache_blob=GOPHER_CACHE_BLOB, external_source_objects=external,
        repeat_equal=True, raw=data, summary=summary,
        rejected_measured_forgeries=rejected), indent=2, sort_keys=True)+'\n',
        encoding='utf8', newline='\n')
    print(json.dumps(summary, sort_keys=True), flush=True)
    print('TRACE_SHA256='+hashlib.sha256(raw.encode()).hexdigest(), flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    print('PASS finite guest TLBR context/cache reactivation; lifetime certificate remains open', flush=True)


if __name__ == '__main__':
    main()
