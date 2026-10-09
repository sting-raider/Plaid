#!/usr/bin/env python3
"""Build and execute the exact pinned-ares TLBWR mapping-generation matrix."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-tlbwr-mapping-generation"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def worker():
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    model_raw = subprocess.check_output(["python3", str(HERE / "model.py")], text=True)
    model = json.loads(model_raw)

    builder = load_builder()
    assert builder.REV == PIN, (builder.REV, PIN)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exe = builder.build(HERE / "driver.cpp", OUTPUT / "build")

    first_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    second_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first_raw == second_raw, (first_raw, second_raw)
    facts = json.loads(first_raw)

    assert facts["first_changed_slot"] == 31
    assert facts["same_value_changed_count"] == 0
    assert facts["index_after_first"] == 7
    assert facts["index_after_range"] == 5
    assert facts["slot7_equals_slot31"] is True
    assert facts["first_cache_cleared"] is True
    assert facts["same_cache_cleared"] is True
    assert len(facts["range"]) == 32
    assert all(slot in (30, 31) for slot in facts["range"])

    evidence = {
        "ares_pin": PIN,
        "facts": facts,
        "model": model,
        "repeat_stdout_sha256": hashlib.sha256(first_raw.encode()).hexdigest(),
        "interpretation": {
            "snapshot_diff_recovers_changed_wired31_slot": True,
            "snapshot_diff_misses_same_value_wired31_generation": True,
            "cp0_index_is_not_tlbwr_replacement_identity": True,
            "equal_payload_can_name_multiple_slots": True,
            "actual_selected_slot_boundary_required_for_complete_history": True,
        },
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + digest)
    print("PASS: exact TLBWR slot selection obeys Wired; same-value generation is invisible to snapshot diff")


def main():
    if os.name == "nt":
        script = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", str(Path(__file__).resolve())],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
