"""Verify a streamed access sidecar against the complete existing boot capture."""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-boot-history-spike"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
ROM_SHA = "629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a"
FW_SHA = "fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd"
FIELDS = {
    "scalar":{"write","address","aligned_address","bytes","device","value"},
    "burst":{"write","address","bytes","device","words"},
    "fill":{"slot","physical","index","words"},
    "cache_operation":{"operation","vaddr","physical","before_tag","after_tag","before_words","after_words"},
    "fetch_begin":{"vaddr","translated","bus","cached","value"},
    "fetch_end":{"vaddr","translated","bus","cached","value"},
    "fetch":{"fetch_context","fetch_seq","word","physical","cached"},
}
PROFILE = {"firmware_sha256":FW_SHA,"firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102",
           "rdram_size":8388608,"deterministic_entropy":True,"pif_processor":"reference_hle","pif_checksum_enforced":True}


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records(path):
    def unique(pairs):
        result = {}
        for key,value in pairs:
            assert key not in result
            result[key] = value
        return result
    with path.open("rb") as file:
        for raw in file:
            assert raw.endswith(b"\n") and len(raw) <= 1024*1024
            yield json.loads(raw,object_pairs_hook=unique)


def verify(history_path,fetch_path,budget):
    fetch_records = records(fetch_path)
    fetch_header = next(fetch_records)
    assert fetch_header == {"record":"header","format":"plaid-ares-fetch-research-v5","revision":REV,
        "rom_sha256":ROM_SHA,"budget":budget,"initial_state":"cpu_power_pif_entry",
        "mapped_cartridge_size":2742280,"source_policy":"delegated_rom_halves_before_prologue",
        "boot_inputs":PROFILE,"cache_policy":"selected_icache_line_at_prologue"}
    expected_header = {"record":"header","format":"plaid-ares-access-history-v0","revision":REV,
        "rom_sha256":ROM_SHA,"budget":budget,"mapped_cartridge_size":fetch_header["mapped_cartridge_size"],
        "firmware_sha256":FW_SHA,"policy":"identity_ram_successful_access_and_fetch_boundaries",
        "lifecycle_policy":"single_run_no_host_restore","paired_fetch_format":"plaid-ares-fetch-research-v5"}
    rows = records(history_path)
    assert next(rows) == expected_header
    ordinal = fetches = scalar_witnesses = matched_fills = unknown_fills = 0
    active = pending = None
    counts = Counter()
    scalar_devices = Counter()
    outside_data_reads = 0
    ended = False
    for row in rows:
        assert not ended
        kind = row["record"]
        if kind == "end":
            assert active is None and pending is None
            assert row == {"record":"end","record_count":ordinal,"fetch_count":fetches,"reason":"instruction_call_budget"}
            ended = True
            continue
        assert kind in FIELDS
        assert pending is None or kind == "fetch"
        assert set(row) == {"record","ordinal","context","pc"} | FIELDS[kind]
        ordinal += 1
        assert type(row["ordinal"]) is int and row["ordinal"] == ordinal
        assert type(row["context"]) is int and type(row["pc"]) is int and 0 <= row["pc"] < 1<<64
        counts[kind] += 1
        if kind == "fetch_begin":
            assert active is None and pending is None and row["context"] == ordinal
            assert row["value"] == 0 and type(row["cached"]) is bool
            active = {"begin":row,"eligible_count":0,"eligible":None,"last_burst":None,"fills":0,"matched_fill":None}
        else:
            assert row["context"] == (active["begin"]["context"] if active else 0)
        if kind == "scalar":
            assert row["bytes"] in (1,2,4,8) and type(row["write"]) is bool
            assert 0 <= row["address"] < 8388608
            assert row["aligned_address"] == row["address"] & ~(row["bytes"]-1)
            assert type(row["value"]) is int and 0 <= row["value"] < 1<<64
            scalar_devices[(row["device"],row["write"],row["bytes"])] += 1
            if active and not row["write"] and row["bytes"] == 4 and row["device"] == 3:
                active["eligible_count"] += 1
                active["eligible"] = row
            elif not active and not row["write"] and row["device"] == 3:
                outside_data_reads += 1
        elif kind == "burst":
            assert row["bytes"] in (16,32) and row["address"] % row["bytes"] == 0
            assert type(row["write"]) is bool and 0 <= row["address"] < 8388608
            assert len(row["words"]) == row["bytes"]//4
            assert all(type(word) is int and 0 <= word < 1<<32 for word in row["words"])
            if active: active["last_burst"] = row
        elif kind == "fill":
            assert 0 <= row["slot"] < 512 and row["index"] == (row["slot"]<<5)&0xfe0
            assert row["index"] == row["physical"]&0xfe0 and len(row["words"]) == 8
            assert all(type(word) is int and 0 <= word < 1<<32 for word in row["words"])
            burst = active["last_burst"] if active else None
            if active: active["fills"] += 1
            if burst and burst["ordinal"]+1 == ordinal and not burst["write"] and burst["device"] == 1 and burst["bytes"] == 32 and burst["address"] == (row["physical"]&~0xfff)|row["index"] and burst["words"] == row["words"]:
                active["matched_fill"] = row
        elif kind == "cache_operation":
            assert row["operation"] in (0,8,16,20,24)
            assert len(row["before_words"]) == len(row["after_words"]) == 8
        elif kind == "fetch_end":
            assert active is not None
            begin = active["begin"]
            for field in ("context","pc","vaddr","translated","bus","cached"):
                assert row[field] == begin[field]
            if not row["cached"] and active["eligible_count"] == 1:
                read = active["eligible"]
                if read["address"] == row["bus"] and read["value"] == row["value"]:
                    scalar_witnesses += 1
            pending = {"end":row,"active":active}
            active = None
        elif kind == "fetch":
            assert active is None and pending is not None
            end = pending["end"]
            assert row["fetch_context"] == end["context"] and row["fetch_seq"] == fetches
            assert (row["pc"],row["physical"],row["cached"],row["word"]) == (
                end["pc"],end["bus"],end["cached"],end["value"])
            original = next(fetch_records)
            assert original["record"] == "fetch" and original["seq"] == fetches
            for key in ("pc","physical","cached","word"): assert original[key] == row[key]
            fill = pending["active"]["matched_fill"]
            line = original.get("cache_line")
            if row["cached"] and pending["active"]["fills"] == 1 and fill and line:
                if fill["physical"] == row["physical"] and fill["slot"] == (row["pc"]>>5)&0x1ff and all(fill[field] == line[field] for field in ("slot","index","words")):
                    matched_fills += 1
            fetches += 1
            pending = None
    assert ended and active is None and pending is None
    assert next(fetch_records) == {"record":"end","fetch_count":fetches,"reason":"instruction_call_budget"}
    assert next(fetch_records,None) is None
    return {"records":ordinal,"fetches":fetches,"counts":dict(sorted(counts.items())),
            "scalar_fetch_witnesses":scalar_witnesses,"outside_uncached_cpu_reads":outside_data_reads,
            "matched_context_ram_fills":matched_fills,"unknown_context_fills":counts["fill"]-matched_fills,
            "scalar_access_classes":[{"device":device,"write":write,"bytes":size,"count":count}
                for (device,write,size),count in sorted(scalar_devices.items())]}


def worker(budget,verify_existing=False):
    boot = load("boot",ROOT/"spikes/008-ares-pif-boot/run.py")
    output = OUTPUT/str(budget)
    output.mkdir(parents=True,exist_ok=True)
    (output/"history-results.json").unlink(missing_ok=True)
    if verify_existing:
        results = json.loads((output/"results.json").read_text())
        states = [json.loads((output/f"{mode}.json").read_text()) for mode in ("plain","traced","repeat")]
        assert states[0] == states[1] == states[2] == results["final_state"]
        boot.equal_files(output/"traced.ndjson",output/"repeat.ndjson")
        boot.equal_files(output/"plain.messages",output/"traced.messages")
        boot.equal_files(output/"traced.messages",output/"repeat.messages")
        assert hashlib.sha256(boot.ROM.read_bytes()).hexdigest() == ROM_SHA
        assert hashlib.sha256(boot.FIRMWARE.read_bytes()).hexdigest() == FW_SHA
        digest = hashlib.sha256()
        with (output/"traced.ndjson").open("rb") as file:
            while chunk := file.read(1024*1024): digest.update(chunk)
        assert digest.hexdigest() == results["trace_sha256"]
    else:
        for mode in ("plain","traced","repeat"):
            (output/f"{mode}.ndjson.history.ndjson").unlink(missing_ok=True)
        results = boot.worker(budget,driver=HERE/"driver.cpp",output_root=OUTPUT,boot_inputs=PROFILE,
            cache_policy="selected_icache_line_at_prologue",
            build_options={"cache_fill_access":True,"cache_operation_access":True,"rdram_burst_access":True,
                           "rdram_scalar_access":True,"fetch_boundary_access":True},
            observer_sources=(HERE/"observer.hpp",ROOT/"spikes/011-ares-cache-fetch/driver.cpp"),run_timeout=600)
    output = OUTPUT/str(budget)
    history = output/"traced.ndjson.history.ndjson"
    repeat = output/"repeat.ndjson.history.ndjson"
    boot.equal_files(history,repeat)
    assert not (output/"plain.ndjson.history.ndjson").exists()
    receipt = verify(history,output/"traced.ndjson",budget)
    if budget == 1000000:
        assert results["trace_sha256"] == "c0dcae4870aaec1b30097d7fd95f2b6214f043e2ac1dea6366b1814655ce4ce9"
        assert results["final_state"] == json.loads((ROOT/"target/ares-cache-fetch-spike/1000000/results.json").read_text())["final_state"]
        assert receipt["fetches"] == 1000000 and receipt["scalar_fetch_witnesses"] == 0
        assert receipt["matched_context_ram_fills"] > 0
    digest = hashlib.sha256()
    with history.open("rb") as file:
        while chunk := file.read(1024*1024): digest.update(chunk)
    receipt.update(history_sha256=digest.hexdigest(),history_bytes=history.stat().st_size,
                   prior_fetch_sha256=results["trace_sha256"],observer_state_unchanged=True,
                   guest_completion_claimed=False,production_identity_promoted=False)
    (output/"history-results.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))
    print("PASS: ordered boot sidecar repeats exactly; complete v5 stream and reported machine checkpoint unchanged")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget",type=int,default=1000000)
    parser.add_argument("--verify-existing",action="store_true",help="recheck retained complete streams/checkpoints without CPU execution")
    options = parser.parse_args()
    budget = options.budget
    assert 0 < budget <= 1000000
    if os.name == "nt":
        script = subprocess.check_output(["wsl","-d","Ubuntu","--exec","wslpath","-a",Path(__file__).resolve().as_posix()],text=True).strip()
        subprocess.run(["wsl","-d","Ubuntu","--exec","python3",script,*sys.argv[1:]],check=True)
    else: worker(budget,options.verify_existing)


if __name__ == "__main__": main()
