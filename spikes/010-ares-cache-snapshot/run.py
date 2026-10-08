"""Sense resident instruction-cache bytes without inferring their load lineage."""
from pathlib import Path
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-cache-snapshot-spike"


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True)
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2] and not plain["events"]
    assert plain["state"] == traced["state"] == repeat["state"]
    events = traced["events"]; assert len(events) == 12
    assert [event["word"] for event in events] == [0x24100000+n for n in (1,1,2,2,3,2,4,5,6,7,7,8)]
    assert [event["physical"] for event in events] == [0,0,0,0,0x4000,0,0x2000,0x3000,0x3004,0x1024,0x1024,0x5024]
    for event in events:
        if not event["cached"]:
            assert "cache_slot" not in event and "cache_line" not in event
            continue
        line = event["cache_line"]
        assert event["cache_slot"] == (event["pc"]>>5)&0x1ff
        assert line["index"] == (event["cache_slot"]<<5)&0xfe0
        assert line["tag_key"] == (event["physical"]&~0xfff)|1
        assert len(line["words"]) == 8 and line["words"][(event["physical"]>>2)&7] == event["word"]
    assert [event["cached"] for event in events] == [True,True,False,True,True,True,True,True,True,True,True,True]
    assert events[0]["cache_line"] == events[1]["cache_line"]
    assert events[3]["cache_line"] == events[5]["cache_line"] # Same bytes after eviction prove no lifetime.
    assert events[7]["cache_line"] == events[8]["cache_line"] # Reverse endian selects the second word.
    assert events[8]["word"] != events[8]["cache_line"]["words"][(events[8]["pc"]>>2)&7]
    assert events[9]["cache_line"] == events[10]["cache_line"]
    assert [events[i]["cache_slot"] for i in (9,10,11)] == [129,1,129]
    assert traced["state"]["cache_hits"] == 2 and traced["state"]["cache_misses"] == 9
    assert traced["state"]["count"] == 444
    assert traced["state"]["regs"] == [0]*16+[8]+[0]*15
    assert traced["state"]["pc"] == 0xffffffff80005028
    assert traced["state"]["ram_sha256"] == "fdaa4712ad0c382090e5e8db1065b8c4632c1d0fcea6c888ae656b454fc766e1"
    assert traced["state"]["icache_sha256"] == "9073f41420302efa4f6ec1880d421f17ebd37dd8f16e7280ea5408540c97c3ef"
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print(json.dumps(traced,indent=2))


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
