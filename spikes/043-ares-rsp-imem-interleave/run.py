#!/usr/bin/env python3
"""Build and execute the exact pinned-ares IMEM DMA/direct-write interleave fixture."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARES = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-rsp-imem-interleave"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)

    guard_raw = subprocess.check_output([os.sys.executable, str(HERE / "source_guard.py"), str(ARES)], text=True)
    guard = json.loads(guard_raw)

    model_raw = subprocess.check_output([os.sys.executable, str(HERE / "model.py")], text=True)
    model_lines = [line for line in model_raw.splitlines() if line.strip()]
    assert model_lines[-1] == "PASS"
    model = json.loads(model_lines[0])
    assert model["fixed_misclassified_bytes"] == {
        "after_completed_row": 4,
        "before_later_row": 0,
        "same_value": 4,
        "wrap": 4,
    }
    assert model["fuzz"]["naive_bad_histories"] == 2207
    assert model["fuzz"]["same_value_cpu_writes"] == 2809

    builder = load_builder()
    exe = builder.build(HERE / "driver.cpp", OUT / "build")
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=45)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=45)
    assert raw1 == raw2, "reference fixture was not deterministic"
    observed = json.loads(raw1)

    a = observed["after_completed_row"]
    assert a["mid"] == [0xAAAAAAAA, 0x22222222]
    assert a["final"] == [0xAAAAAAAA, 0x22222222, 0x33333333, 0x44444444]

    b = observed["before_later_row"]
    assert b == {"mid": 0xBBBBBBBB, "final": 0x33333333}

    c = observed["same_value"]
    assert c["before"] == c["after"] == c["final"] == 0x11111111
    assert c["write_invoked"] is True

    d = observed["wrap"]
    assert d["mid"] == [0xCCCCCCCC, 0xDDDDDDDD]
    assert d["final"] == [0xCCCCCCCC, 0x66666666, 0x77777777, 0x88888888]
    assert observed["non_overlap"] == 0xEEEEEEEE

    result = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "ares_revision": REV,
        "driver_sha256": hashlib.sha256((HERE / "driver.cpp").read_bytes()).hexdigest(),
        "reference_stdout_sha256": hashlib.sha256(raw1.encode()).hexdigest(),
        "repeat_deterministic": raw1 == raw2,
        "source_guard": guard,
        "model": model,
        "reference": observed,
        "conclusions": {
            "cpu_write_between_count_rows_is_observable": True,
            "write_to_completed_row_survives_dma_completion": True,
            "write_to_future_row_is_superseded_by_later_dma_row": True,
            "same_value_direct_write_is_invisible_to_content_diff": True,
            "wrap_preserves_the_same_ordering_rule": True,
            "transfer_identity_alone_is_not_resident_microcode_generation": True,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    result_path = OUT / "results.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("RESULT_SHA256=" + hashlib.sha256(result_path.read_bytes()).hexdigest())
    print("REFERENCE_STDOUT_SHA256=" + result["reference_stdout_sha256"])
    print("MODEL_SHA256=" + model["sha256"])
    print("PASS: exact pinned ares permits CPU IMEM mutation between count rows; per-byte latest-writer revisions are required")


def main():
    if os.name == "nt":
        script = subprocess.check_output([
            "wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()
        ], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
