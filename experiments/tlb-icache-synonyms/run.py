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
    assert state["away_back"] == 0x2222
    assert state["away_back_tag_preserved"] is True
    assert state["equal_remap"] == 0x2222
    assert state["different_remap"] == 0x3333
    assert state["tlbwi_preserved_resident_valid"] is True

    misses = state["misses"]
    assert misses["after_a"] == misses["start"] + 1
    assert misses["after_c"] == misses["after_a"]              # same ares slot/tag hit
    assert misses["after_b"] == misses["after_c"] + 1         # virtual-color miss
    assert misses["after_a_refill"] == misses["after_b"] + 1
    assert misses["after_b_refill"] == misses["after_a_refill"] + 1
    assert misses["after_away_back"] == misses["after_b_refill"]  # TLBWI away/back did not kill resident line
    assert misses["after_equal_remap"] == misses["after_away_back"] + 1
    assert misses["after_different_remap"] == misses["after_equal_remap"] + 1

    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    print("RESULT_SHA256=" + digest)
    print("RESULT=" + json.dumps(state, sort_keys=True, separators=(",", ":")))
    print("PASS: exact pinned ares admits divergent cacheable TLB synonym residents; TLB remap alone is not a resident lifetime boundary; physical-tag fetch remaps refill")


def main() -> None:
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
