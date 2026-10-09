#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/tlb-icache-synonyms"
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
    assert state["idx_a"] == 0 and state["idx_b"] == 128 and state["idx_c"] == 0
    assert state["first"] == [0x1111, 0x1111, 0x1111]
    assert state["stale"] == [0x1111, 0x1111]
    assert state["divergent_words"] == [0x34092222, 0x34091111]
    assert state["fresh"] == [0x2222, 0x2222]
    assert state["equal_remap"] == 0x2222
    assert state["different_remap"] == 0x3333
    assert state["tlbwi_preserved_resident_valid"] is True
    # Initial A miss, same-index C hit, different-index B miss; then one-color
    # refill, other-color refill, equal-payload remap refill, different remap refill.
    misses = state["misses"]
    assert misses[1] == misses[0] + 1
    assert misses[2] == misses[1]
    assert misses[3] == misses[2] + 1
    assert misses[4] == misses[3] + 1
    assert misses[5] == misses[4] + 2  # B refill + equal-payload remap
    assert misses[6] == misses[5] + 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    print("RESULT_SHA256=" + digest)
    print("RESULT=" + json.dumps(state, sort_keys=True, separators=(",", ":")))
    print("PASS: exact pinned ares admits divergent cacheable TLB synonym residents; physical-tag remaps refill")


def main() -> None:
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
