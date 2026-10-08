"""Verify one callback chronology against independent controlled-state goldens."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-ordered-history-spike"
PRIOR = "0eac15edb2d40ecbcd85b5302c12fc25b24f9980a6c83b2d9b6291f3cbeaed8a"


def verify(data):
    assert data["history_policy"] == "controlled_fixture_callbacks_v0"
    expected = [("fixture_write", i) for i in range(1, 9)] + [
        ("rdram_burst",1),("fill",1),("fetch",1),
        ("fetch",2),("cache_operation",1),("fetch",3),
        ("fetch",4),("cache_operation",2),
        ("rdram_burst",2),("fill",2),("fetch",5),
        ("fetch",6),("cache_operation",3),("fetch",7),
        ("fetch",8),("cache_operation",4),
        ("rdram_burst",3),("fill",3),("fetch",9),
        ("fetch",10),("cache_operation",5),("fetch",11),
        ("fetch",12),("rdram_burst",4),("fill",4),("cache_operation",6),
        ("fetch",13),("fixture_write",9),
        ("fetch",14),("rdram_burst",5),("cache_operation",7),
        ("fetch",15),("fetch",16),("cache_operation",8),("fetch",17)]
    history = data["history"]
    assert len(history) == 43
    assert history == [dict(seq=i,kind=kind,index=index) for i,(kind,index) in enumerate(expected,1)]
    payloads = {"fixture_write":data["fixture_writes"],"rdram_burst":data["rdram_bursts"],
                "fill":data["fills"],"fetch":data["events"],"cache_operation":data["cache_operations"]}
    for kind, records in payloads.items():
        # Every retained payload occurs once in the chronology, with a valid index.
        assert [e["index"] for e in history if e["kind"] == kind] == list(range(1,len(records)+1))
    writes = data["fixture_writes"]
    assert [(e["address"],e["word"]) for e in writes] == [
        (0,0x24100001),(0x4000,0x24100009),(0x2000,0xbd080000),
        (0x2004,0xbd000000),(0x2008,0xbd080000),(0x200c,0xbd100000),
        (0x2010,0xbd140000),(0x2014,0xbd180000),(0x4000,0x24100008)]
    assert all(e["actor"] == "fixture" and e["bytes"] == 4 for e in writes)
    bursts, fills, fetches, operations = [payloads[k] for k in ("rdram_burst","fill","fetch","cache_operation")]
    assert len(bursts) == 5 and len(fills) == 4 and len(fetches) == 17 and len(operations) == 8
    for burst, fill in zip(bursts[:4],fills):
        assert not burst["write"] and burst["address"] == fill["burst_address"]
        assert burst["words"] == fill["words"] and burst["bytes"] == 32 and burst["icache_requestor"]
    # Retagged hits retain an earlier fill's words at a different effective page.
    for fetch, fill in ((fetches[2],fills[0]),(fetches[6],fills[1])):
        assert not fetch["fill_matches_tag"] and fetch["word"] == fill["words"][0]
        assert fetch["physical"] != fill["burst_address"]
    assert bursts[4]["write"] and bursts[4]["address"] == writes[-1]["address"] == 0x4000
    assert bursts[4]["words"] == operations[6]["before_words"] == fills[3]["words"]
    assert bursts[4]["words"][0] == fetches[-1]["word"] == 0x24100009 != writes[-1]["word"]
    projection = dict(data)
    for field in ("history_policy","history","fixture_writes"): projection.pop(field)
    assert hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(",",":")).encode()).hexdigest() == PRIOR


def negative_checks(data):
    altered = copy.deepcopy(data)
    # Reorder fill and actual RAM read while preserving each payload and count.
    altered["history"][8],altered["history"][9] = altered["history"][9],altered["history"][8]
    for i,event in enumerate(altered["history"],1): event["seq"] = i
    variants = [altered]
    altered = copy.deepcopy(data); altered["history"].pop(9); variants.append(altered)
    altered = copy.deepcopy(data); altered["history"][8]["index"] = 99; variants.append(altered)
    altered = copy.deepcopy(data); altered["rdram_bursts"][0]["words"][0] ^= 1; variants.append(altered)
    altered = copy.deepcopy(data); altered["fixture_writes"][-1]["actor"] = "cpu"; variants.append(altered)
    for variant in variants:
        try: verify(variant)
        except AssertionError: continue
        raise AssertionError("altered chronology or witness was accepted")


def worker():
    spec = importlib.util.spec_from_file_location("builder",ROOT/"spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    inputs = tuple(ROOT/f"spikes/{p}" for p in (
        "013-ares-cache-tag/driver.cpp","012-ares-cache-fill/observer.hpp",
        "014-ares-cache-operations/observer.hpp","014-ares-cache-operations/driver.cpp",
        "015-ares-cache-outcomes/driver.cpp","016-ares-rdram-bursts/observer.hpp",
        "016-ares-rdram-bursts/driver.cpp"))
    baseline = builder.build(ROOT/"spikes/015-ares-cache-outcomes/baseline.cpp",OUTPUT/"baseline",
        raw_fetch_access=True,physical_fetch_access=True,extra_sources=inputs)
    original = json.loads(subprocess.check_output([str(baseline),"plain"],text=True,timeout=30))
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT/"sensor",
        raw_fetch_access=True,physical_fetch_access=True,cache_fill_access=True,
        cache_operation_access=True,rdram_burst_access=True,
        extra_sources=(*inputs,Path(__file__).with_name("history.hpp")))
    runs = [subprocess.check_output([str(exe),mode],text=True,timeout=30) for mode in ("plain","traced","traced")]
    plain,traced,repeat = [json.loads(raw) for raw in runs]
    assert runs[1] == runs[2]
    assert original["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert not any(plain[k] for k in ("history","fixture_writes","rdram_bursts","fills","events","cache_operations"))
    verify(traced); negative_checks(traced)
    (OUTPUT/"results.json").write_text(json.dumps(traced,indent=2)+"\n")
    print("PASS: 43 ordered witnesses; read/fill/fetch and fetch/writeback/completion order; retagged data history; independent and repeated complete checkpoints unchanged; five forged histories rejected")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
