"""Retain executed PageMask/cache-remap facts without synthetic ancestry promotion."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import verify

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/ares-pagemask-cache-remap-primary'
SOURCE_BLOBS={
    'ares/n64/cpu/cpu.hpp':'b51000d99e1e8818ad04a8c747a8170b0e98fae8',
    'ares/n64/cpu/tlb.cpp':'3bec71ea1039b7fc5a5b2816ecc2b2ed534872dc',
    'ares/n64/cpu/memory.cpp':'f362ef67ab41ccf57330bbedd6f614e07a61dd17',
    'ares/n64/cpu/interpreter-scc.cpp':'c3d119bf4931c4616ae297a4c18b561490207e11',
    'ares/n64/cpu/interpreter-ipu.cpp':'938ccbd0af1f127439d9859c1fd6be2bbd5222a3',
    'ares/n64/rdram/rdram.hpp':'c718ec2e9b2a78610353562cbc81dd973b278ee2'}


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',
            Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True)
        return
    subprocess.run([sys.executable,str(HERE/'test_verify.py')],check=True)
    spec=importlib.util.spec_from_file_location('pagemask_builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    for name,blob in SOURCE_BLOBS.items():
        assert subprocess.check_output(['git','rev-parse',builder.REV+':'+name],
            cwd=builder.REF,text=True).strip()==blob
    # No reference callbacks or decoder/cache patches are requested.
    executable=builder.build(HERE/'driver.cpp',OUTPUT,extra_sources=(HERE/'driver.cpp',))
    raw=subprocess.check_output([str(executable)],text=True,timeout=45)
    repeat=subprocess.check_output([str(executable)],text=True,timeout=45)
    assert raw==repeat
    facts=json.loads(raw)
    summary=verify(facts)
    canonical=json.dumps(facts,sort_keys=True,separators=(',',':')).encode()
    assert hashlib.sha256(canonical).hexdigest()=='4227e340a3000607b70cde96339a379737ea46167a7cf10573fe7aba093050fd'
    path=OUTPUT/'results.json'
    path.write_text(json.dumps(dict(schema_version=0,revision=builder.REV,source_blobs=SOURCE_BLOBS,
        facts=facts,repeat_equal=True,summary=summary),indent=2,sort_keys=True)+'\n',
        encoding='utf-8',newline='\n')
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('EVIDENCE_SHA256='+hashlib.sha256(canonical).hexdigest(),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS unmodified pinned PageMask/cache remap; mapping/fill ancestry remains unmeasured',flush=True)


if __name__=='__main__':
    main()
