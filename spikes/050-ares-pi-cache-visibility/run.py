"""Reproduce selected PI copy/cache facts without general ancestry promotion."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from verify import verify
from adversaries import check

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/'target/ares-pi-cache-visibility-primary'
SOURCE_BLOBS={
    "ares/n64/cpu/cpu.cpp": "41964d49c8983ae9a97b25625174cd4c4316c4a8",
    "ares/n64/cpu/cpu.hpp": "b51000d99e1e8818ad04a8c747a8170b0e98fae8",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/memory/bus.hpp": "367308207719c1048daa1bbf7ffca635ca0c97d5",
    "ares/n64/mi/bus.hpp": "2d61fa47b6ae568390df421036df4ffefd23b4e5",
    "ares/n64/n64.hpp": "33a2a973d6026a8a014231f79a8ab9b98998b703",
    "ares/n64/pi/dma.cpp": "f2bd415495c6d84da779026b61fbe4c9f6ef7c88",
    "ares/n64/pi/io.cpp": "2a41a8240e96ea3517bfb1fa67748829a900fb84",
    "nall/nall/priority-queue.hpp": "17eb754bccdfd075f8dac206d7c0aafd28d01e37",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2"
}


def main():
    if os.name=='nt':
        path=subprocess.check_output(['wsl','-d','Ubuntu','--exec','wslpath','-a',
            Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(['wsl','-d','Ubuntu','--exec','python3',path],check=True)
        return
    subprocess.run([sys.executable,str(HERE/'test_verify.py')],check=True)
    spec=importlib.util.spec_from_file_location('pi_cache_builder',ROOT/'spikes/003-ares-oracle/run.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    for name,blob in SOURCE_BLOBS.items():
        assert subprocess.check_output(['git','rev-parse',builder.REV+':'+name],
            cwd=builder.REF,text=True).strip()==blob
    baseline=builder.build(HERE/'baseline.cpp',OUTPUT/'baseline',extra_sources=(HERE/'driver.cpp',))
    sensor=builder.build(HERE/'driver.cpp',OUTPUT/'sensor',raw_fetch_access=True,
        physical_fetch_access=True,cache_fill_access=True,rdram_burst_access=True,
        rdram_scalar_access=True,fetch_boundary_access=True,pi_dma_access=True,
        extra_sources=(HERE/'driver.cpp',))
    baseline_raw=subprocess.check_output([str(baseline),'plain'],text=True,timeout=45)
    plain_raw=subprocess.check_output([str(sensor),'plain'],text=True,timeout=45)
    raw=subprocess.check_output([str(sensor),'traced'],text=True,timeout=45)
    repeat=subprocess.check_output([str(sensor),'traced'],text=True,timeout=45)
    assert raw==repeat
    original,disabled,data=map(json.loads,(baseline_raw,plain_raw,raw))
    assert original['events']==disabled['events']==[]
    for key in ('checkpoints','state'):
        assert original[key]==disabled[key]==data[key]
    summary=verify(data)
    rejected=check(data)
    path=OUTPUT/'results.json'
    path.write_text(json.dumps(dict(schema_version=0,revision=builder.REV,source_blobs=SOURCE_BLOBS,
        reported_checkpoint_equality=True,repeat_equal=True,raw=data,summary=summary,
        rejected_measured_forgeries=rejected),
        indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(summary,sort_keys=True),flush=True)
    print('TRACE_SHA256='+hashlib.sha256(raw.encode()).hexdigest(),flush=True)
    print('RESULT_SHA256='+hashlib.sha256(path.read_bytes()).hexdigest(),flush=True)
    print('PASS finite PI copy/cache visibility with selected checkpoint equality',flush=True)


if __name__=='__main__': main()
