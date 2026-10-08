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
    parser.add_argument("--physical",action="store_true",help="Recheck the v1 physical observer capture")
    physical = parser.parse_args().physical
    output = ROOT / "target/ares-physical-fetch-spike" if physical else OUTPUT
    raw = output / "traced.ndjson"
    map_path = output / "map.json"
    cargo = os.environ.get("CARGO") or shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo.exe")
    subprocess.run([cargo,"build","-p","plaid"],cwd=ROOT,check=True)
    exe = ROOT / ("target/debug/plaid.exe" if os.name == "nt" else "target/debug/plaid")
    started = time.perf_counter()
    process = subprocess.Popen([str(exe),"import-fetch",str(ROM),str(raw),str(map_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    stdout, stderr = process.communicate(timeout=180)
    elapsed = time.perf_counter() - started
    assert process.returncode == 0, stderr
    peak = peak_working_set(process)
    print(stdout.strip())
    subprocess.run([str(exe),"verify-fetch",str(ROM),str(raw),str(map_path)],check=True,timeout=180)
    data = json.loads(map_path.read_text())
    assert len(data["fetch_captures"]) == 1
    assert sum(f["occurrences"] for f in data["fetch_observations"]) == 4999998
    capture = next(iter(data["fetch_captures"].values()))
    if physical:
        sensor = json.loads((output / "results.json").read_text())
        assert capture["trace_sha256"] == sensor["trace_sha256"]
        assert capture["trace_sha256"] == "c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1"
        assert capture["mapped_cartridge_size"] == 2742280
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
        "raw_fetches":4999998,"summary_facts":len(data["fetch_observations"]),"import_seconds":elapsed,
        "peak_working_set_bytes":peak}
    (output / "import-metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
    print(json.dumps(metrics,indent=2))


if __name__ == "__main__": main()
