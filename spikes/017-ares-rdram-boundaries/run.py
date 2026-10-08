"""Ensure remapped/degraded/failed accesses cannot become identity witnesses."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-rdram-boundaries-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    driver = Path(__file__).with_name("driver.cpp")
    baseline = builder.build(driver.with_name("baseline.cpp"),OUTPUT/"baseline",
        raw_fetch_access=True,physical_fetch_access=True,extra_sources=(driver,))
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    exe = builder.build(driver,OUTPUT/"sensor",raw_fetch_access=True,physical_fetch_access=True,
        rdram_burst_access=True,extra_sources=(ROOT/"spikes/016-ares-rdram-bursts/observer.hpp",))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["rdram_bursts"]
    assert original["results"] == plain["results"] == traced["results"] == repeat["results"]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    results = traced["results"]
    assert len(results) == 9 and results[0] == [0x11223300+i for i in range(8)]
    assert results[1] == [0xaabbcc00+i for i in range(8)] and results[2] == [0xffffffff]*8
    assert results[3] == results[5] == results[6] == results[7] == [0]*8
    assert all(0 <= word <= 0xffffffff for word in results[4])
    assert any(word not in (0,0xffffffff) for word in results[4])
    assert results[4] == [3554205747,1686149089,1393422709,3374901345,2282948992,163274021,3619125818,2641673048]
    assert results[8] == [0x55667700+i for i in range(4)]
    events = traced["rdram_bursts"]
    assert [(e["write"],e["address"],e["bytes"],e["icache_requestor"]) for e in events] == [
        (False,0,32,True),(True,0,32,True),(False,0,16,False)]
    assert events[0]["words"] == results[0] and events[1]["words"] == [0x55667700+i for i in range(8)]
    assert events[2]["words"] == results[8]
    assert traced["state"]["count"] == 0 and traced["state"]["ri_error"] == 1
    state = traced["state"]
    expected = [0]*32; expected[29] = -1543495696
    assert state["regs"] == expected and state["hi"] == state["lo"] == 0
    assert state["pc"] == 0xffffffffbfc00000
    assert state["ram_sha256"] == "b34ba68aca7b98053ef23b552d335c428b1fb33b19972b1bfb2e4cbeaf0d515c"
    assert state["hidden_sha256"] == "68510b252b438d53c7be9eb09f1d519e8d0f3193d0f0a1d942852d282070cf6e"
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print(json.dumps(traced,indent=2))
    print("PASS: remapped/degraded/missing/inactive/out-of-bounds accesses remain outside identity policy; actual 16/32-byte witnesses and complete RAM/hidden/CPU checkpoints agree")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
