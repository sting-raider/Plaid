#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/tlbr-icache-lifetime"
BASE = ROOT / "spikes/003-ares-oracle/run.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_oracle_builder", BASE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker() -> None:
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    subprocess.run(["python3", str(HERE / "model.py")], check=True)
    builder = load_builder()
    exe = builder.build(HERE / "driver.cpp", OUTPUT)
    first = subprocess.check_output([str(exe)], text=True, timeout=30)
    second = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first == second
    state = json.loads(first)

    assert state["idx_switch"] == 0
    assert state["idx_global"] == 256
    assert state["first_a"] == {"value": 0x1111, "paddr": 0x1000}
    assert state["global_b"] == {"value": 0x7777, "paddr": 0x7000}
    assert state["global_a"] == {"value": 0x7777, "paddr": 0x7000}
    assert state["fault"] == {"exception": 2, "badvaddr": 0x4000}
    assert state["stale_reactivated_a"] == {"value": 0x1111, "paddr": 0x1000}
    assert state["equal_c"] == {"value": 0x1111, "paddr": 0x5000}
    assert state["fresh_a"] == {"value": 0x4444, "paddr": 0x1000}
    assert state["tlbp_context_unchanged"] is True
    assert state["same_value_tlbr_unchanged"] is True
    assert state["out_of_range_tlbr_unchanged"] is True
    assert state["installed_entries_unchanged"] is True
    assert state["inactive_backing_word"] == 0x34094444
    assert (state["initial_tag"] & ~1) == 0x1000
    assert (state["equal_tag"] & ~1) == 0x5000

    misses = state["misses"]
    assert misses["first_a"] == misses["start"] + 1
    assert misses["fault_after"] == misses["fault_before"]
    assert misses["reactivate_after"] == misses["reactivate_before"]
    assert misses["equal_after"] == misses["equal_before"] + 1
    assert misses["fresh_after"] == misses["fresh_before"] + 1

    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    stdout_digest = hashlib.sha256(first.encode()).hexdigest()
    print("RESULT_SHA256=" + digest)
    print("REPEAT_STDOUT_SHA256=" + stdout_digest)
    print("RESULT=" + json.dumps(state, sort_keys=True, separators=(",", ":")))
    print("PASS: real guest TLBR reactivates stale resident executable bytes without installed-entry or I-cache mutation; equal-payload different-PA fetch replaces the resident generation")


def main() -> None:
    if os.name == "nt":
        script = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
