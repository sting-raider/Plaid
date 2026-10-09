#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/pagemask-icache-remap"
BASE = ROOT / "spikes/003-ares-oracle/run.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_oracle_builder", BASE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def worker() -> None:
    guard = subprocess.check_output(["python3", str(HERE / "source_guard.py")], text=True)
    model = subprocess.check_output(["python3", str(HERE / "model.py")], text=True)
    model_sha = next(line.split("=", 1)[1] for line in model.splitlines() if line.startswith("MODEL_SHA256="))

    builder = load_builder()
    exe = builder.build(HERE / "driver.cpp", OUTPUT)
    first = subprocess.check_output([str(exe)], text=True, timeout=30)
    second = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first == second, "combined exact-reference fixture must be deterministic"
    state = json.loads(first)

    assert state["select16"] == 0x4000
    assert state["select64"] == 0x10000
    assert state["first"] == 0x1111
    assert state["stale"] == 0x1111
    assert state["equal_remap"] == 0x1111
    assert state["stale_new"] == 0x1111
    assert state["fresh_original"] == 0x2222
    assert state["away_back"] == 0x2222
    assert state["asid_exception"] == 2
    assert state["asid_return"] == 0x2222
    assert state["geometry_remap"] == 0x2222
    assert state["odd"] == 0x5555
    assert state["resident_preservation"] == {
        "same_value_tlbwi": True,
        "away_back": True,
        "asid_fail": True,
    }
    assert state["tags"] == {
        "first": 0x11001,
        "equal": 0x31001,
        "original_again": 0x11001,
        "geometry": 0x51001,
        "odd": 0xA0001,
    }

    misses = state["misses"]
    assert misses["first"] == misses["start"] + 1
    assert misses["stale"] == misses["first"]
    assert misses["equal"] == misses["stale"] + 1
    assert misses["fresh_original"] == misses["equal"] + 1
    assert misses["away_back"] == misses["fresh_original"]
    assert misses["asid_fail"] == misses["away_back"]
    assert misses["asid_return"] == misses["asid_fail"]
    assert misses["geometry"] == misses["asid_return"] + 1
    assert misses["odd"] == misses["geometry"] + 1

    receipt = {
        "fixture": state,
        "model_sha256": model_sha,
        "source_guard_sha256": hashlib.sha256(guard.encode()).hexdigest(),
        "fixture_stdout_sha256": hashlib.sha256(first.encode()).hexdigest(),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    print(guard, end="")
    print(model, end="")
    print("FIXTURE_STDOUT_SHA256=" + receipt["fixture_stdout_sha256"])
    print("RESULT_SHA256=" + digest)
    print("RESULT=" + json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    print("PASS: large-PageMask mapping geometry composes with physical-tag resident generations; remap/context unreachability alone does not retire cached executable bytes")


def main() -> None:
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
