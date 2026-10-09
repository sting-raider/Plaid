#!/usr/bin/env python3
"""Build and execute the exact-pinned ares restore-epoch composition fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-savestate-tlb-cache-epoch"


def worker():
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    subprocess.run(["python3", str(HERE / "model.py")], check=True, stdout=subprocess.DEVNULL)
    spec = importlib.util.spec_from_file_location("builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    baseline = builder.build(HERE / "baseline.cpp", OUTPUT / "baseline",
        extra_sources=(HERE / "fixture.cpp",))
    traced = builder.build(HERE / "driver.cpp", OUTPUT / "traced",
        raw_fetch_access=True, physical_fetch_access=True, cache_fill_access=True,
        extra_sources=(HERE / "fixture.cpp", ROOT / "spikes/012-ares-cache-fill/observer.hpp"))

    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    disabled_raw = subprocess.check_output([str(traced), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(traced), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    base, disabled, result = map(json.loads, (baseline_raw, disabled_raw, traced_raw))
    assert base["state"] == disabled["state"] == result["state"]
    assert base["external_generations"] == disabled["external_generations"] == result["external_generations"]
    assert disabled["fill_count"] == disabled["naive_post_restore_fill"] == 0
    assert result["fill_count"] == 3
    assert result["naive_post_restore_fill"] == 3
    assert result["external_generations"] == {"mapping": 3, "context": 3, "restore_epoch": 2}
    state = result["state"]
    assert state["asid"] == 0x11 and state["tlb_pa0"] == 0x1000
    assert state["cache_word0"] == 0x34091111 and state["t1"] == 0x1111
    assert state["exception"] == 0 and state["distinct_rollback"] and state["equal_state_restore"]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_blob = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (OUTPUT / "results.json").write_bytes(result_blob)
    (OUTPUT / "baseline.json").write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
    print("results_sha256=" + hashlib.sha256(result_blob).hexdigest())
    print("PASS: one synchronized restore rolls back TLB+EntryHi/I-cache state without replaying external generations; exact equal-state histories still require a snapshot-qualified restore epoch")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
