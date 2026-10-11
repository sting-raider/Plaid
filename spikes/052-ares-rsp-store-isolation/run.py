"""Unmodified interpreter probes; source comparisons are not hardware execution."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from audit import source_audit
from verify import verify, reject_forgeries

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT/'target/ares-rsp-store-isolation-primary'
SOURCE_BLOBS = {
    'ares': {
        'ares/n64/rsp/interpreter-ipu.cpp': '9a3d93cba5177c225f2aa65df3af322a0145f35f',
        'ares/n64/rsp/interpreter-vpu.cpp': 'b30d62f63efee6c2287e48637d079eadcba95565',
        'ares/n64/rsp/rsp.hpp': '3f05ea5e7b266245c2091dac8a7aad7680f1361d',
        'ares/n64/rsp/rsp.cpp': 'b743688847a63796a3582caffaaba014b5da66c4',
        'ares/n64/memory/msb/writable.hpp': 'a5e1ad2cebe78c465ec46964ce405ba5c9e81a90',
    },
    'gopher64': {
        'src/device/rsp_su_instructions.rs': '4afc4c9886bf85759e12f61769acbe84a7e33898',
        'src/device/rsp_interface.rs': '1d62a69c618328dc1735e3c92c400359c7458c52',
    },
    'n64-systemtest': {
        'src/tests/rsp/op_sw.rs': '95e4aa015e941c2950feed3bf25ba17ff42756f1',
        'src/tests/rsp/op_vector_stores.rs': 'a8693502bbf54ac328a7b03ef90b47614eeaabcd',
        'src/rsp/rsp_assembler.rs': '45beb36f989baaf20a1e13bd30114368d53797d8',
    },
}


def main():
    if os.name == 'nt':
        script = subprocess.check_output(['wsl', '-d', 'Ubuntu', '--exec', 'wslpath',
            '-a', Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(['wsl', '-d', 'Ubuntu', '--exec', 'python3', script], check=True)
        return
    subprocess.run([sys.executable, str(HERE/'test_verify.py')], check=True)
    audit = source_audit()
    for repo, files in SOURCE_BLOBS.items():
        for name, blob in files.items():
            assert subprocess.check_output(['git', 'rev-parse', 'HEAD:'+name],
                cwd=ROOT/'.refs'/repo, text=True).strip() == blob
    spec = importlib.util.spec_from_file_location('rsp_isolation_builder', ROOT/'spikes/003-ares-oracle/run.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(HERE/'driver.cpp', OUTPUT/'build')
    raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    repeat = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert raw == repeat
    data = json.loads(raw)
    summary = verify(data)
    rejected = reject_forgeries(data)
    path = OUTPUT/'results.json'
    path.write_text(json.dumps(dict(schema_version=0, revision=builder.REV,
        source_blobs=SOURCE_BLOBS, source_audit=audit, repeat_equal=True,
        driver_imem_snapshot_checks_passed=True, raw=data, summary=summary,
        rejected_measured_forgeries=rejected), indent=2, sort_keys=True)+'\n',
        encoding='utf8', newline='\n')
    print(json.dumps(summary, sort_keys=True), flush=True)
    print('TRACE_SHA256='+hashlib.sha256(raw.encode()).hexdigest(), flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(), flush=True)
    print('PASS 29 unmodified decoded RSP store probes preserve their full IMEM snapshots', flush=True)


if __name__ == '__main__':
    main()
