"""Validate actual ROM source witnesses against the complete physical capture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-rom-fetch-spike"
ROM = ROOT / "target/systemtest-spike/n64-systemtest.z64"
BUDGET = 5000000


def equal_files(left, right):
    with left.open("rb") as first, right.open("rb") as second:
        while chunk := first.read(1024*1024): assert chunk == second.read(len(chunk))
        assert not second.read(1)


def worker():
    data = ROM.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a"
    spec = importlib.util.spec_from_file_location("builder",ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT,
        raw_fetch_access=True,physical_fetch_access=True,
        extra_sources=(ROOT / "spikes/006-ares-rom-source/driver.cpp",ROOT / "spikes/004-ares-fetch/driver.cpp"))
    states = {}
    for mode in ("plain","traced","repeat"):
        subprocess.run([str(exe),"plain" if mode == "plain" else "traced",str(ROM),
            str(OUTPUT / f"{mode}.ndjson"),str(OUTPUT / f"{mode}.json"),
            str(OUTPUT / f"{mode}.messages"),str(BUDGET)],check=True,timeout=180)
        states[mode] = json.loads((OUTPUT / f"{mode}.json").read_text())
    assert states["plain"] == states["traced"] == states["repeat"]
    checkpoint = hashlib.sha256(json.dumps(states["traced"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
    assert checkpoint == "bff38e8306eebacaeb10e105b2e8a5fe791a44b9e2ba13f1f682301ce3ff96bd"
    equal_files(OUTPUT / "traced.ndjson",OUTPUT / "repeat.ndjson")
    equal_files(OUTPUT / "plain.messages",OUTPUT / "traced.messages")
    equal_files(OUTPUT / "traced.messages",OUTPUT / "repeat.messages")
    assert hashlib.sha256((OUTPUT / "traced.messages").read_bytes()).hexdigest() == "01eb219108ac35e2a3d28315f1a2b3ba8b58fa9fd9acf83d58a466bfb48415ea"
    projection = hashlib.sha256(); digest = hashlib.sha256()
    count = witnesses = unknown = 0
    offsets = set(); ended = False
    with (OUTPUT / "traced.ndjson").open("rb") as trace:
        for raw in trace:
            digest.update(raw); event = json.loads(raw)
            if event["record"] == "header":
                assert count == 0 and event["format"] == "plaid-ares-fetch-research-v2"
                assert event.pop("source_policy") == "delegated_rom_halves_before_prologue"
                event["format"] = "plaid-ares-fetch-research-v1"
            elif event["record"] == "fetch":
                assert event["seq"] == count
                source = event.pop("source")
                if source["kind"] == "cartridge_rom":
                    assert set(source) == {"kind","offset"}
                    offset = source["offset"]
                    assert not event["cached"] and event["physical"] == 0x10000000 + offset
                    assert offset % 4 == 0 and 0 <= offset and offset + 4 <= len(data)&~7
                    assert event["word"] == int.from_bytes(data[offset:offset+4],"big")
                    offsets.add(offset); witnesses += 1
                else:
                    assert source == {"kind":"unknown"}; unknown += 1
                count += 1
            elif event["record"] == "end":
                assert event == {"record":"end","fetch_count":count,"reason":"instruction_call_budget"}
                assert not trace.read(1); ended = True
            else: raise AssertionError(event)
            projection.update((json.dumps(event,separators=(",",":"))+"\n").encode())
    assert ended and count == 4999998
    assert projection.hexdigest() == "c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1"
    assert witnesses == 1852 and len(offsets) == 65 and witnesses + unknown == count
    assert digest.hexdigest() == "40d8d029cd66fb5ecfcdc3d77bdbc570dd13ce62684d47e7704cbe375008d204"
    results = {"fetches":count,"rom_source_fetches":witnesses,"unknown_source_fetches":unknown,
        "unique_rom_source_offsets":len(offsets),"trace_bytes":(OUTPUT / "traced.ndjson").stat().st_size,
        "trace_sha256":digest.hexdigest(),"v1_projection_sha256":projection.hexdigest(),
        "observer_state_unchanged":True,"guest_completion_claimed":False}
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
