"""Observe completed guest tag/invalidation operations without extra accesses."""
from pathlib import Path
import importlib.util
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-operations-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    driver = Path(__file__).with_name("driver.cpp")
    exe = builder.build(driver,OUTPUT,raw_fetch_access=True,physical_fetch_access=True,
        cache_fill_access=True,cache_operation_access=True,extra_sources=(
            driver.with_name("observer.hpp"),ROOT/"spikes/013-ares-cache-tag/driver.cpp",
            ROOT/"spikes/012-ares-cache-fill/observer.hpp"))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"] and not plain["fills"] and not plain["cache_operations"]
    assert plain["state"] == traced["state"] == repeat["state"]
    projection = dict(traced); projection.pop("cache_operations")
    assert hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(",",":")).encode()).hexdigest() == "4ffd0952041adf8b8b79bfb5f941594531a4e061db7cb862e6d1a846e0407ebe"
    expected = [0]*32; expected[8] = -2147483648; expected[16] = 9
    state = traced["state"]
    assert state["regs"] == expected and state["pc"] == 0xffffffff80000004
    assert state["hi"] == state["lo"] == state["exception"] == state["epc"] == 0
    assert state["count"] == 103 and state["cache_hits"] == state["cache_misses"] == 2
    assert state["status"] == 877723392 and state["configuration"] == 1879499872
    assert state["ram_sha256"] == "acadcf93aed6b50df4253efb0a898bef4aa107253e68c3a2038a75315a65db82"
    assert state["icache_sha256"] == "f1fae837b5c53982dab46e78c4aa73ed3b082f54c63b8bf26b2578c12c5d315e"
    operations = traced["cache_operations"]
    assert len(operations) == 3 and len(traced["fills"]) == 2 and len(traced["events"]) == 7
    assert [(e["operation"],e["before_tag"],e["after_tag"],e["fill_count"]) for e in operations] == [
        (8,1,0x4001,1),(0,0x4001,0x4000,1),(8,0x4001,1,2)]
    assert [e["pc"] for e in operations] == [0xffffffffa0002000,0xffffffffa0002004,0xffffffffa0002008]
    assert [e["physical"] for e in operations] == [0x4000,0x4000,0]
    assert all(e["slot"] == 0 and e["before_words"] == e["after_words"] for e in operations)
    assert [e["before_words"][0] for e in operations] == [0x24100001,0x24100001,0x24100009]
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print("PASS: three completed guest CACHE operations, exact tag/data transitions and unchanged repeated checkpoint goldens")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
