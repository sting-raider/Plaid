"""Check hit/miss/fill/writeback outcomes against a separately built baseline."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-outcomes-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    driver = Path(__file__).with_name("driver.cpp")
    fixture = ROOT/"spikes/013-ares-cache-tag/driver.cpp"
    baseline = builder.build(driver.with_name("baseline.cpp"),OUTPUT/"baseline",
        raw_fetch_access=True,physical_fetch_access=True,extra_sources=(fixture,))
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    exe = builder.build(driver,OUTPUT/"sensor",raw_fetch_access=True,physical_fetch_access=True,
        cache_fill_access=True,cache_operation_access=True,extra_sources=(fixture,
            ROOT/"spikes/014-ares-cache-operations/driver.cpp",ROOT/"spikes/014-ares-cache-operations/observer.hpp",
            ROOT/"spikes/012-ares-cache-fill/observer.hpp"))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"] and not plain["fills"] and not plain["cache_operations"]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert original["post_tags"] == plain["post_tags"] == traced["post_tags"]
    state = traced["state"]
    expected = [0]*32; expected[8] = -2147483648; expected[16] = 9
    assert state["regs"] == expected and state["pc"] == 0xffffffffa0004004
    assert state["hi"] == state["lo"] == state["exception"] == state["epc"] == 0
    assert state["count"] == 257 and state["cache_hits"] == 5 and state["cache_misses"] == 4
    assert state["cache_writebacks"] == 1
    assert state["status"] == 877723392 and state["configuration"] == 1879499872
    assert state["ram_sha256"] == "50a18fe00c8412198450b7c3b145685651d375984164e4e87ec60f4c050fa4bd"
    assert state["icache_sha256"] == "c6caf1bddc422cd59faa433446a3d02649b05dd2fba13bc54539e6a3c11f28a6"
    events,fills,operations = traced["events"],traced["fills"],traced["cache_operations"]
    assert len(events) == 17 and len(fills) == 4 and len(operations) == 8
    assert [(e["operation"],e["before_tag"],e["after_tag"],e["fill_count"]) for e in operations] == [
        (8,1,0x4001,1),(0,0x4001,0x4000,1),(8,0x4001,1,2),
        (16,1,0,2),(16,1,1,3),(20,1,0x4001,4),(24,0x4001,0x4001,4),(24,0x4001,0x4001,4)]
    assert [e["physical"] for e in operations] == [0x4000,0x4000,0,0,0x4000,0x4000,0x4000,0]
    assert operations[5]["before_words"][0] == 0x24100001 and operations[5]["after_words"][0] == 0x24100009
    assert all(e["before_words"] == e["after_words"] for i,e in enumerate(operations) if i != 5)
    assert [f["burst_address"] for f in fills] == [0,0x4000,0,0x4000]
    assert events[-1]["physical"] == 0x4000 and not events[-1]["cached"] and events[-1]["word"] == 0x24100009
    assert traced["post_fill_counts"] == [1,1,1,1,2,2,2,2,3,3,3,4,4,4,4,4,4]
    assert traced["post_tags"] == [1,0x4001,0x4001,0x4000,0x4001,1,1,0,1,1,1,0x4001,0x4001,0x4001,0x4001,0x4001,0x4001]
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print(json.dumps(state,indent=2))
    print("PASS: hit/miss invalidation, explicit fill, hit/miss writeback and actual restored RAM; baseline/repeated complete checkpoints agree")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
