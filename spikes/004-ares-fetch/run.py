"""Bounded raw fetch experiment; its stream is not Plaid discovery trace v0."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-fetch-spike"
ROM = ROOT / "target/systemtest-spike/n64-systemtest.z64"
ROM_SHA = "629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a"
BUDGET = int(os.environ.get("PLAID_FETCH_BUDGET", "5000000"))
assert 0 < BUDGET <= 10000000


def equal_files(first, second):
    with first.open("rb") as left, second.open("rb") as right:
        while chunk := left.read(1024 * 1024):
            assert chunk == right.read(len(chunk)), (first,second)
        assert not right.read(1)


def worker():
    data = ROM.read_bytes()
    assert hashlib.sha256(data).hexdigest() == ROM_SHA
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(Path(__file__).with_name("driver.cpp"), OUTPUT, raw_fetch_access=True)
    states = {}
    for mode in ("plain","traced","repeat"):
        subprocess.run([str(exe),"plain" if mode == "plain" else "traced",str(ROM),
            str(OUTPUT / f"{mode}.ndjson"),str(OUTPUT / f"{mode}.json"),
            str(OUTPUT / f"{mode}.messages"),str(BUDGET)],check=True,timeout=120)
        states[mode] = json.loads((OUTPUT / f"{mode}.json").read_text())
    assert states["plain"] == states["traced"] == states["repeat"], states
    equal_files(OUTPUT / "traced.ndjson", OUTPUT / "repeat.ndjson")
    equal_files(OUTPUT / "plain.messages", OUTPUT / "traced.messages")
    equal_files(OUTPUT / "traced.messages", OUTPUT / "repeat.messages")
    addresses = {"cartridge":set(),"ram":set(),"sp":set(),"other":set()}
    count = 0
    digest = hashlib.sha256()
    with (OUTPUT / "traced.ndjson").open("rb") as trace:
        raw = trace.readline()
        digest.update(raw)
        assert json.loads(raw) == {"record":"header","format":"plaid-ares-fetch-research-v0",
            "revision":builder.REV,"rom_sha256":ROM_SHA,"budget":BUDGET,
            "initial_state":"declared_post_ipl2_sp_entry"}
        for raw in trace:
            digest.update(raw)
            event = json.loads(raw)
            if event["record"] == "end":
                assert event == {"record":"end","fetch_count":count,"reason":"instruction_call_budget"}
                assert not trace.read(1)
                break
            assert set(event) == {"record","seq","pc","word","delay_slot"}
            assert event["record"] == "fetch" and event["seq"] == count and event["pc"] % 4 == 0
            assert 0 <= event["word"] <= 0xffffffff and type(event["delay_slot"]) is bool
            count += 1
            pc = event["pc"]
            if 0xffffffff80000000 <= pc <= 0xffffffffbfffffff:
                physical = pc & 0x1fffffff
                if 0x10000000 <= physical < 0x10000000 + len(data):
                    offset = physical - 0x10000000
                    assert event["word"] == int.from_bytes(data[offset:offset+4],"big"), event
                    addresses["cartridge"].add(pc)
                elif physical < 0x800000: addresses["ram"].add(pc)
                elif 0x4000000 <= physical < 0x4002000: addresses["sp"].add(pc)
                else: addresses["other"].add(pc)
            else: addresses["other"].add(pc)
        else: raise AssertionError("Missing budget-stop footer")
    results = {"rom_sha256":ROM_SHA,"budget":BUDGET,"fetches":count,
        "unique_fetch_addresses":{key:len(value) for key,value in addresses.items()},
        "final_state":states["traced"],"trace_sha256":digest.hexdigest(),
        "guest_completion_claimed":False}
    messages = (OUTPUT / "traced.messages").read_bytes()
    results["upstream_failures"] = [line for line in messages.decode("utf-8").splitlines() if " failed:" in line]
    results["messages_sha256"] = hashlib.sha256(messages).hexdigest()
    if BUDGET == 5000000:
        assert count == 4999998
        assert results["unique_fetch_addresses"] == {"cartridge":65,"ram":52424,"sp":548,"other":0}
        assert digest.hexdigest() == "2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c"
        assert len(results["upstream_failures"]) == 1 and "Initial COP0 Config" in results["upstream_failures"][0]
    (OUTPUT / "results.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script],check=True)
    else: worker()


if __name__ == "__main__": main()
