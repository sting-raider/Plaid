"""Observe actual cache fills, including identical payloads after eviction."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-fill-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True,cache_fill_access=True,
        extra_sources=(Path(__file__).with_name("observer.hpp"),ROOT/"spikes/010-ares-cache-snapshot/driver.cpp"))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"] and not plain["fills"]
    assert plain["state"] == traced["state"] == repeat["state"]
    # Existing unmodified-core checkpoint goldens, independent of fill callback.
    state = traced["state"]
    assert state["count"] == 444 and state["cache_misses"] == 9 and state["cache_hits"] == 2
    assert state["ram_sha256"] == "fdaa4712ad0c382090e5e8db1065b8c4632c1d0fcea6c888ae656b454fc766e1"
    assert state["icache_sha256"] == "9073f41420302efa4f6ec1880d421f17ebd37dd8f16e7280ea5408540c97c3ef"
    assert state["regs"] == [0]*16+[8]+[0]*15 and state["pc"] == 0xffffffff80005028
    events,fills = traced["events"],traced["fills"]
    assert len(events) == 12 and len(fills) == 9
    assert [e.get("fill_id") for e in events] == [1,1,None,2,3,4,5,6,6,7,8,9]
    assert [f["id"] for f in fills] == list(range(1,10))
    for event in events:
        if not event["cached"]: continue
        fill = fills[event["fill_id"]-1]
        assert fill["slot"] == event["cache_slot"]
        assert fill["words"] == event["cache_line"]["words"]
        assert fill["physical"]&~0xfff == event["physical"]&~0xfff
        assert fill["burst_address"] == (event["physical"]&~0xfff)|event["cache_line"]["index"]
    assert fills[1]["words"] == fills[3]["words"] and fills[1]["id"] != fills[3]["id"]
    assert fills[6]["words"] == fills[7]["words"] and fills[6]["slot"] != fills[7]["slot"]
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print("PASS: nine actual fills, hit reuse, equal-payload refills and bank aliases; repeated complete checkpoints unchanged")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
