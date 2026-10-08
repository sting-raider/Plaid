"""Reproduce actual PI request/CPU queue dispatch with independent checkpoints."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUTPUT=ROOT/"target/ares-pi-queue-dispatch-context"


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


def worker():
    builder=module("plaid_builder",ROOT/"spikes/003-ares-oracle/run.py")
    baseline=builder.build(HERE/"baseline.cpp",OUTPUT/"baseline",raw_fetch_access=True,physical_fetch_access=True,
                           extra_sources=(HERE/"driver.cpp",))
    observed=builder.build(HERE/"driver.cpp",OUTPUT/"observed",raw_fetch_access=True,physical_fetch_access=True,
                           pi_dma_access=True,queue_access=True,rdram_scalar_access=True,
                           extra_sources=(HERE/"observer.hpp",ROOT/"spikes/032-ares-queue-identity/observer.hpp"))
    def run(exe,mode):
        return subprocess.check_output([str(exe),mode],text=True,timeout=30)
    base=json.loads(run(baseline,"plain")); disabled=json.loads(run(observed,"plain"))
    raw=run(observed,"traced"); assert raw==run(observed,"traced")
    traced=json.loads(raw)
    state={k:v for k,v in traced.items() if k!="events"}
    assert state=={k:v for k,v in base.items() if k!="events"}
    assert state=={k:v for k,v in disabled.items() if k!="events"}
    assert base["events"]==disabled["events"]==[]
    (OUTPUT/"traced.json").write_text(raw)
    (OUTPUT/"state.json").write_text(json.dumps(state,indent=2)+"\n")
    print("PASS: actual PI I/O and CPU synchronize baseline/disabled/repeated reported checkpoints agree",flush=True)
    checker=module("plaid_pi_queue_checker",HERE/"verify.py")
    result=checker.verify(traced["events"])
    checker.counterexamples(traced["events"])
    receipt=dict(revision=builder.REV,raw_records=len(traced["events"]),result=result,state=state,
                 reported_baseline_disabled_repeat_equal=True,guest_mmio_executed=False,hardware_timing_claimed=False)
    path=OUTPUT/"results.json"; path.write_text(json.dumps(receipt,indent=2)+"\n")
    print("RESULT_SHA256="+hashlib.sha256(path.read_bytes()).hexdigest())
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    if os.name=="nt":
        path=subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",path],check=True)
    else: worker()
