"""Recheck the ignored complete homebrew capture; record one-host import cost."""
from pathlib import Path
import ctypes
import json
import os
import shutil
import subprocess
import time
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "target/ares-fetch-spike"
ROM = ROOT / "target/systemtest-spike/n64-systemtest.z64"


def peak_working_set(process):
    if os.name != "nt": return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb",wintypes.DWORD),("faults",wintypes.DWORD)] + [
            (name,ctypes.c_size_t) for name in ("peak","working","peak_paged","paged",
                "peak_nonpaged","nonpaged","pagefile","peak_pagefile")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    get_info = ctypes.WinDLL("psapi",use_last_error=True).GetProcessMemoryInfo
    get_info.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    if not get_info(process._handle,ctypes.byref(counters),counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.peak


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--physical",action="store_true",help="Recheck the v1 physical observer capture")
    modes.add_argument("--source",action="store_true",help="Recheck the v2 ROM-source observer capture")
    modes.add_argument("--boot",action="store_true",help="Recheck the v4 explicit boot-profile capture")
    modes.add_argument("--cache",action="store_true",help="Recheck the v5 selected-cache boot capture")
    parser.add_argument("--budget",type=int,choices=(1000000,10000000),default=1000000,help="Boot capture prefix")
    args = parser.parse_args()
    timeout = 300 if args.cache else 180
    physical, source = args.physical, args.source
    boot = args.boot or args.cache
    output = ROOT / "target/ares-rom-fetch-spike" if source else ROOT / "target/ares-physical-fetch-spike" if physical else OUTPUT
    if boot: output = ROOT / ("target/ares-cache-fetch-spike" if args.cache else "target/ares-boot-profile-spike") / str(args.budget)
    elif args.budget != 1000000: parser.error("--budget requires --boot or --cache")
    sensor = json.loads((output / "results.json").read_text()) if boot else None
    expected_count = sensor["fetches"] if boot else 4999998
    raw = output / "traced.ndjson"
    map_path = output / "map.json"
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    subprocess.run([cargo,"build","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT / ("target/debug/plaid.exe" if os.name == "nt" else "target/debug/plaid")
    started = time.perf_counter()
    inputs = [str(ROM),str(raw)]
    if boot: inputs.insert(1,str(ROOT / ".refs/ares/ares/System/Nintendo 64/pif.ntsc.rom"))
    process = subprocess.Popen([str(exe),"import-boot-fetch" if boot else "import-fetch",*inputs,str(map_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stdout, stderr = process.communicate(timeout=timeout)
    elapsed = time.perf_counter() - started
    assert process.returncode == 0, stderr
    peak = peak_working_set(process)
    print(stdout.strip())
    subprocess.run([str(exe),"verify-boot-fetch" if boot else "verify-fetch",*inputs,str(map_path)],check=True,timeout=timeout)
    data = json.loads(map_path.read_text())
    assert len(data["fetch_captures"]) == 1
    assert sum(f["occurrences"] for f in data["fetch_observations"]) == expected_count
    capture = next(iter(data["fetch_captures"].values()))
    if boot:
        assert sensor["budget"] == args.budget
        assert expected_count == (1000000 if args.budget == 1000000 else 9999998)
        assert capture["trace_sha256"] == sensor["trace_sha256"]
        assert capture["initial_state"] == "cpu_power_pif_entry"
        assert capture["boot_inputs"] == {"firmware_sha256":sensor["firmware_sha256"],
            "firmware_size":1984,"region":"ntsc","cic":"CIC-NUS-6102","rdram_size":8388608,
            "deterministic_entropy":True,"pif_processor":"reference_hle","pif_checksum_enforced":True}
        known = [f for f in data["fetch_observations"] if f["source"]["kind"] == "cartridge_rom"]
        assert sum(f["occurrences"] for f in known) == sensor["rom_source_fetches"]
        assert all(f["source"]["kind"] in ("cartridge_rom","unknown") for f in data["fetch_observations"])
        if args.cache:
            assert capture["cache_policy"] == sensor["cache_policy"] == "selected_icache_line_at_prologue"
            cached = [f for f in data["fetch_observations"] if "cache_line" in f]
            assert all(f["access"]["cached"] == ("cache_line" in f) for f in data["fetch_observations"])
            assert sum(f["occurrences"] for f in cached) == sensor["cached_fetches"]
            snapshots = {(f["cache_line"]["slot"],f["cache_line"]["tag_key"],f["cache_line"]["index"],
                tuple(f["cache_line"]["words"])) for f in cached}
            assert len(snapshots) == sensor["unique_resident_snapshots"]
            if args.budget == 1000000:
                assert len(data["fetch_observations"]) == 1155
                assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "07f650865d122d13059c6f862e68303aa82527173d87f08b37e2d0e90108156f"
            else:
                assert len(data["fetch_observations"]) == 54279 and len(known) == 65
                assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "7c6740e204721cd7a4b3a02c494453525eca6fa3e8043b2c1d19a270e8867c11"
        elif args.budget == 1000000:
            assert capture["trace_sha256"] == "38a0781c763a110ca419af65bf9f1a19ed96cd9282e01b2545486d9d865bd937"
            assert len(data["fetch_observations"]) == 1155 and not known
            assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "f88a70b8c444b44326e5e9fd79a2b64b8aa983bbc3669495f7a9c0458ea7fcad"
        else:
            assert capture["trace_sha256"] == "d46c9c99245c65cb2b671b182da0a247006b077026000ac2b29d5df786644027"
            assert len(data["fetch_observations"]) == 54279 and len(known) == 65
            assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "78199fd10ebadd1affb9d96060c1e2da960cd56bfc415f8ef7c29f924f26161c"
    elif source:
        sensor = json.loads((output / "results.json").read_text())
        assert capture["trace_sha256"] == sensor["trace_sha256"]
        assert capture["trace_sha256"] == "40d8d029cd66fb5ecfcdc3d77bdbc570dd13ce62684d47e7704cbe375008d204"
        assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "a3a2e4f0249974f6119a3a496ab518744259c38dbce32a182adee3bae3248786"
        assert capture["source_policy"] == "delegated_rom_halves_before_prologue"
        assert capture["mapped_cartridge_size"] == 2742280
        assert len(data["fetch_observations"]) == 53037
        known = [f for f in data["fetch_observations"] if f["source"]["kind"] == "cartridge_rom"]
        assert len(known) == sensor["unique_rom_source_offsets"] == 65
        assert sum(f["occurrences"] for f in known) == sensor["rom_source_fetches"] == 1852
        assert all(not f["access"]["cached"] and f["access"]["physical"] == 0x10000000 + f["source"]["offset"] for f in known)
        assert sum(f["occurrences"] for f in data["fetch_observations"] if f["source"]["kind"] == "unknown") == sensor["unknown_source_fetches"]
    elif physical:
        sensor = json.loads((output / "results.json").read_text())
        assert capture["trace_sha256"] == sensor["trace_sha256"]
        assert capture["trace_sha256"] == "c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1"
        assert capture["mapped_cartridge_size"] == 2742280
        assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "04057ba54310f4e4adc7d879f32aa976a9679c1f1d9d7aa629155978f3f92dc7"
        assert len(data["fetch_observations"]) == sensor["unique_virtual_physical_cache_tuples"]
        assert all("access" in f for f in data["fetch_observations"])
        for cached, name in ((True,"cached_fetches"),(False,"uncached_fetches")):
            assert sum(f["occurrences"] for f in data["fetch_observations"] if f["access"]["cached"] == cached) == sensor[name]
    else:
        assert len(data["fetch_observations"]) == 53037
        assert capture["trace_sha256"] == "2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c"
        assert hashlib.sha256(map_path.read_bytes()).hexdigest() == "c32b48621f4a86314a9e229241eb8e0cc3417fc5a611609ae60506386587f6d3"
    assert not data["regions"] and not data["blocks"] and not data["loads"] and not data["entries"]
    merged = output / "self-merged.json"
    subprocess.run([str(exe),"merge",str(map_path),str(map_path),str(merged)],check=True)
    assert map_path.read_bytes() == merged.read_bytes()
    report = json.loads(subprocess.check_output([str(exe),"solve",str(ROM),str(map_path)],text=True))
    assert report["status"] == "open" and not report["native_complete"]
    assert any(b["kind"] == "fetch_execution_identity_unknown" for b in report["blockers"])
    (output / "solve.json").write_text(json.dumps(report,indent=2)+"\n")
    metrics = {"profile":"Rust debug, single host/run; no throughput/scalability claim",
        "host_os":os.name,"raw_bytes":raw.stat().st_size,"map_bytes":map_path.stat().st_size,
        "raw_fetches":expected_count,"summary_facts":len(data["fetch_observations"]),"import_seconds":elapsed,
        "peak_working_set_bytes":peak}
    (output / "import-metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    print(json.dumps(metrics,indent=2))


if __name__ == "__main__": main()
