"""Disprove effective fetch page as resident-byte origin across CACHE retags."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-tag-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    driver = Path(__file__).with_name("driver.cpp")
    baseline = builder.build(driver.with_name("baseline.cpp"),OUTPUT/"baseline",
        raw_fetch_access=True,physical_fetch_access=True,extra_sources=(driver,))
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    exe = builder.build(driver,OUTPUT/"sensor",raw_fetch_access=True,physical_fetch_access=True,
        cache_fill_access=True,extra_sources=(ROOT/"spikes/012-ares-cache-fill/observer.hpp",))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"] and not plain["fills"]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert original["post_tags"] == plain["post_tags"] == traced["post_tags"]
    assert traced["post_tags"] == [1,0x4001,0x4001,0x4000,0x4001,1,1]
    assert traced["post_fill_counts"] == [1,1,1,1,2,2,2]
    events,fills = traced["events"],traced["fills"]
    assert len(events) == 7 and len(fills) == 2
    assert [e["word"] for e in events] == [0x24100001,0xbd080000,0x24100001,0xbd000000,0x24100009,0xbd080000,0x24100009]
    assert [e.get("last_fill_event") for e in events] == [1,None,1,None,2,None,2]
    assert [e.get("fill_matches_tag") for e in events] == [True,None,False,None,True,None,False]
    assert [f["burst_address"] for f in fills] == [0,0x4000]
    assert traced["state"]["cache_hits"] == 2 and traced["state"]["cache_misses"] == 2
    expected = [0]*32; expected[8] = -2147483648; expected[16] = 9
    assert traced["state"]["regs"] == expected and traced["state"]["pc"] == 0xffffffff80000004
    assert traced["state"]["exception"] == 0 and traced["state"]["hi"] == traced["state"]["lo"] == 0
    assert traced["state"]["count"] == 103 and traced["state"]["epc"] == 0
    assert traced["state"]["status"] == 877723392 and traced["state"]["configuration"] == 1879499872
    assert traced["state"]["ram_sha256"] == "acadcf93aed6b50df4253efb0a898bef4aa107253e68c3a2038a75315a65db82"
    assert traced["state"]["icache_sha256"] == "f1fae837b5c53982dab46e78c4aa73ed3b082f54c63b8bf26b2578c12c5d315e"
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print(json.dumps(traced,indent=2))
    print("PASS: guest CACHE retags twice without refilling; baseline/plain/traced/repeated checkpoints agree")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
