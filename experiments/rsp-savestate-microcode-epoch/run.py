#!/usr/bin/env python3
"""Build/run exact-pinned ares RSP savestate microcode-epoch fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-rsp-savestate-microcode-epoch"


def worker():
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    model_raw = subprocess.check_output(["python3", str(HERE / "model.py")], text=True)
    model_hash = next(line.split("=", 1)[1] for line in model_raw.splitlines() if line.startswith("MODEL_SHA256="))

    spec = importlib.util.spec_from_file_location("builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    exe = builder.build(HERE / "fixture.cpp", OUTPUT / "fixture")

    first = subprocess.check_output([str(exe)], text=True, timeout=30)
    second = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first == second
    result = json.loads(first)
    assert result["external_generations"] == {"install": 3, "writer": 4, "restore_epoch": 2}
    assert result["naive"] == {"latest_matching_install": 3, "latest_matching_writer": 4}
    state = result["state"]
    assert state["s0_install_generation"] == 1
    assert state["imem_word0"] == 0x24010001
    assert state["imem_word1"] == 0x24020002
    assert state["post_restore_fetch"] == 0x24010001
    assert state["distinct_rollback"]
    assert state["equal_state_before_second_restore"]
    assert state["equal_state_restore"]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    canonical = {
        "model_sha256": model_hash,
        "fixture": result,
    }
    blob = (json.dumps(canonical, sort_keys=True, separators=(",", ":")) + "\n").encode()
    (OUTPUT / "results.json").write_bytes(blob)
    (OUTPUT / "fixture.stdout").write_text(first)
    print("FIXTURE_STDOUT_SHA256=" + hashlib.sha256(first.encode()).hexdigest())
    print("RESULT_SHA256=" + hashlib.sha256(blob).hexdigest())
    print("PASS: synchronized restore resurrected S0 RSP IMEM/execution state without replaying external install/writer generations; equal-value latest-generation joins are false")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
