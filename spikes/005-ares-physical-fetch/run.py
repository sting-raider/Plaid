"""Validate actual physical metadata without claiming byte-source/lifetime proof."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-physical-fetch-spike"
ROM = ROOT / "target/systemtest-spike/n64-systemtest.z64"
ROM_SHA = "629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a"
BUDGET = 5000000
V0_DIGEST = "2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c"


def equal_files(first, second):
    with first.open("rb") as left, second.open("rb") as right:
        while chunk := left.read(1024*1024): assert chunk == right.read(len(chunk))
        assert not right.read(1)


def worker():
    data = ROM.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ROM_SHA
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"), OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True,
        extra_sources=(ROOT / "spikes/004-ares-fetch/driver.cpp",))
    fixture = subprocess.check_output([str(exe),"fixture"],text=True,timeout=10)
    assert fixture == subprocess.check_output([str(exe),"fixture"],text=True,timeout=10)
    expected = [
        (0xffffffff80000000,0x24100001,0,True),
        (0xffffffff80000000,0x24100001,0,True),
        (0xffffffffa0000000,0x24100002,0,False),
        (0xffffffff80000000,0x24100002,0,True),
        (0x4000,0x24100003,0x2000,False),
        (0x4000,0x24100004,0x3000,False),
        (0x4000,0x24100005,0x3004,False),
    ]
    assert [tuple(json.loads(row)[key] for key in ("pc","word","physical","cached"))
        for row in fixture.splitlines()] == expected
    (OUTPUT / "fixture.ndjson").write_text(fixture)
    states = {}
    for mode in ("plain","traced","repeat"):
        subprocess.run([str(exe),"plain" if mode == "plain" else "traced",str(ROM),
            str(OUTPUT / f"{mode}.ndjson"),str(OUTPUT / f"{mode}.json"),
            str(OUTPUT / f"{mode}.messages"),str(BUDGET)],check=True,timeout=180)
        states[mode] = json.loads((OUTPUT / f"{mode}.json").read_text())
    assert states["plain"] == states["traced"] == states["repeat"]
    assert states["traced"] == json.loads((ROOT / "target/ares-fetch-spike/traced.json").read_text())
    equal_files(OUTPUT / "traced.ndjson", OUTPUT / "repeat.ndjson")
    equal_files(OUTPUT / "plain.messages", OUTPUT / "traced.messages")
    equal_files(OUTPUT / "traced.messages", OUTPUT / "repeat.messages")
    projection = hashlib.sha256()
    digest = hashlib.sha256()
    count = 0
    samples = set()
    cached = uncached = 0
    ended = False
    with (OUTPUT / "traced.ndjson").open("rb") as trace:
        for raw in trace:
            digest.update(raw)
            event = json.loads(raw)
            if event["record"] == "header":
                assert count == 0
                assert event["format"] == "plaid-ares-fetch-research-v1"
                assert event["revision"] == builder.REV and event["rom_sha256"] == ROM_SHA
                assert event.pop("mapped_cartridge_size") == len(data) & ~7
                event["format"] = "plaid-ares-fetch-research-v0"
            elif event["record"] == "fetch":
                assert event["seq"] == count
                physical, cache = event.pop("physical"), event.pop("cached")
                assert 0 <= physical <= 0xffffffff and physical % 4 == 0 and type(cache) is bool
                samples.add((event["pc"],physical,cache))
                cached += cache
                uncached += not cache
                count += 1
            elif event["record"] == "end":
                assert event == {"record":"end","fetch_count":count,"reason":"instruction_call_budget"}
                assert not trace.read(1)
                ended = True
            else: raise AssertionError(event)
            projection.update((json.dumps(event,separators=(",",":"))+"\n").encode())
    assert ended and count == 4999998 and projection.hexdigest() == V0_DIGEST
    assert cached and uncached
    results = {"fetches":count,"unique_virtual_physical_cache_tuples":len(samples),
        "cached_fetches":cached,"uncached_fetches":uncached,"mapped_cartridge_size":len(data)&~7,
        "trace_bytes":(OUTPUT / "traced.ndjson").stat().st_size,"trace_sha256":digest.hexdigest(),
        "v0_projection_sha256":projection.hexdigest(),"observer_state_unchanged":True,
        "guest_completion_claimed":False}
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
