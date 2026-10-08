"""Observe natural CPU power entry with explicit existing firmware input."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-pif-boot-spike"
ROM = ROOT / "target/systemtest-spike/n64-systemtest.z64"
FIRMWARE = ROOT / ".refs/ares/ares/System/Nintendo 64/pif.ntsc.rom"
FIRMWARE_SHA = "fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd"


def equal_files(left, right):
    with left.open("rb") as first, right.open("rb") as second:
        while chunk := first.read(1024*1024): assert chunk == second.read(len(chunk))
        assert not second.read(1)


def worker(budget):
    data, firmware = ROM.read_bytes(), FIRMWARE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == "629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a"
    assert len(firmware) == 1984 and hashlib.sha256(firmware).hexdigest() == FIRMWARE_SHA
    spec = importlib.util.spec_from_file_location("builder",ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"),OUTPUT / "build",
        raw_fetch_access=True,physical_fetch_access=True,
        extra_sources=(ROOT / "spikes/006-ares-rom-source/driver.cpp",ROOT / "spikes/004-ares-fetch/driver.cpp"))
    output = OUTPUT / str(budget); output.mkdir(exist_ok=True)
    (output / "results.json").unlink(missing_ok=True)
    states = {}
    for mode in ("plain","traced","repeat"):
        (output / f"{mode}.json").unlink(missing_ok=True)
        subprocess.run([str(exe),"plain" if mode == "plain" else "traced",str(ROM),
            str(output / f"{mode}.ndjson"),str(output / f"{mode}.json"),
            str(output / f"{mode}.messages"),str(budget),str(FIRMWARE)],check=True,
            timeout=max(180,60*((budget+999999)//1000000)))
        states[mode] = json.loads((output / f"{mode}.json").read_text())
    assert states["plain"] == states["traced"] == states["repeat"]
    equal_files(output / "traced.ndjson",output / "repeat.ndjson")
    equal_files(output / "plain.messages",output / "traced.messages")
    equal_files(output / "traced.messages",output / "repeat.messages")
    digest = hashlib.sha256(); count = witnesses = 0
    physical_domains = {"pif":set(),"sp":set(),"ram":set(),"cartridge":set(),"other":set()}
    first = None; ended = False
    with (output / "traced.ndjson").open("rb") as trace:
        for raw in trace:
            digest.update(raw); event = json.loads(raw)
            if event["record"] == "header":
                assert event["format"] == "plaid-ares-fetch-research-v3"
                assert event["revision"] == builder.REV and event["firmware_sha256"] == FIRMWARE_SHA
                assert event["initial_state"] == "cpu_power_pif_entry"
                assert event["pif_processor"] == "reference_hle" and event["pif_checksum_enforced"] is True
                assert event["budget"] == budget and event["mapped_cartridge_size"] == len(data)&~7
            elif event["record"] == "fetch":
                assert event["seq"] == count
                if first is None: first = event
                pa = event["physical"]
                domain = "pif" if 0x1fc00000 <= pa < 0x1fc007c0 else "sp" if 0x04000000 <= pa < 0x04002000 else "ram" if pa < 0x800000 else "cartridge" if 0x10000000 <= pa < 0x1fc00000 else "other"
                physical_domains[domain].add(pa)
                source = event["source"]
                if source["kind"] == "cartridge_rom":
                    offset = source["offset"]
                    assert not event["cached"] and pa == 0x10000000 + offset
                    assert offset % 4 == 0 and 0 <= offset and offset+4 <= len(data)&~7
                    assert event["word"] == int.from_bytes(data[offset:offset+4],"big")
                    witnesses += 1
                else: assert source == {"kind":"unknown"}
                count += 1
            elif event["record"] == "end":
                assert event == {"record":"end","fetch_count":count,"reason":"instruction_call_budget"}
                assert not trace.read(1); ended = True
            else: raise AssertionError(event)
    assert ended and count <= budget and first is not None
    assert (first["pc"],first["physical"],first["word"]) == (0xffffffffbfc00000,0x1fc00000,int.from_bytes(firmware[:4],"big"))
    assert states["traced"]["pif_checksum_enforced"] is True
    if budget == 1000000:
        assert count == budget and witnesses == 0
        assert digest.hexdigest() == "fbdf4da4fbae6bec9712404b7f14df790fe1fb3aca1a9b1239e207248bffe021"
        assert states["traced"]["configuration"] == 0x7006e463
        assert states["traced"]["pif_state"] == 4
        assert states["traced"]["pi"]["dma_busy"] == 1
        assert states["traced"]["pi"]["bsd1"] == [64,18,7,3]
    messages = (output / "traced.messages").read_text(errors="replace")
    results = {"budget":budget,"fetches":count,"rom_source_fetches":witnesses,
        "unique_physical_addresses":{key:len(value) for key,value in physical_domains.items()},
        "first_fetch":first,"final_state":states["traced"],"firmware_sha256":FIRMWARE_SHA,
        "trace_bytes":(output / "traced.ndjson").stat().st_size,"trace_sha256":digest.hexdigest(),
        "messages_sha256":hashlib.sha256((output / "traced.messages").read_bytes()).hexdigest(),
        "guest_failure_lines":[line for line in messages.splitlines() if "failed:" in line],
        "observer_state_unchanged":True,"guest_completion_claimed":False}
    (output / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--budget",type=int,default=1000000)
    budget = parser.parse_args().budget
    assert 0 < budget <= 10000000
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script,*sys.argv[1:]],check=True)
    else: worker(budget)


if __name__ == "__main__": main()
