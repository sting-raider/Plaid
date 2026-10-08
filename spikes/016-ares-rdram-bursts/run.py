"""Check actual successful RAM bursts without deriving copy/image lifetimes."""
from pathlib import Path
import importlib.util
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-rdram-bursts-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True,cache_fill_access=True,
        cache_operation_access=True,rdram_burst_access=True,extra_sources=(
            Path(__file__).with_name("observer.hpp"),ROOT/"spikes/015-ares-cache-outcomes/driver.cpp",
            ROOT/"spikes/014-ares-cache-operations/driver.cpp",ROOT/"spikes/013-ares-cache-tag/driver.cpp",
            ROOT/"spikes/014-ares-cache-operations/observer.hpp",ROOT/"spikes/012-ares-cache-fill/observer.hpp"))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"] and not plain["fills"] and not plain["rdram_bursts"]
    assert plain["state"] == traced["state"] == repeat["state"]
    projection = dict(traced); projection.pop("rdram_bursts")
    assert hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(",",":")).encode()).hexdigest() == "63d27623769528d7147d051c8f8597ff71ffb59ad78bdffc901accdaf9d164b9"
    bursts = traced["rdram_bursts"]
    assert [(e["write"],e["address"]) for e in bursts] == [(False,0),(False,0x4000),(False,0),(False,0x4000),(True,0x4000)]
    assert all(e["bytes"] == 32 and e["icache_requestor"] and len(e["words"]) == 8 for e in bursts)
    assert [e["words"][0] for e in bursts] == [0x24100001,0x24100009,0x24100001,0x24100009,0x24100009]
    assert [e["words"] for e in bursts[:4]] == [e["words"] for e in traced["fills"]]
    state = traced["state"]
    assert state["count"] == 257 and state["cache_writebacks"] == 1
    assert state["ram_sha256"] == "50a18fe00c8412198450b7c3b145685651d375984164e4e87ec60f4c050fa4bd"
    assert state["icache_sha256"] == "c6caf1bddc422cd59faa433446a3d02649b05dd2fba13bc54539e6a3c11f28a6"
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print("PASS: four actual RAM burst reads and one completed write; invalid attempts supply no backing witness; repeated complete checkpoints unchanged")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
