#!/usr/bin/env python3
"""Build and execute the exact pinned-ares TLBWI mapping-generation matrix."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-tlbwi-mapping-generation"
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
    assert model["same_value_writes"] == model["snapshot_false_negatives"]
    assert model["forgeries_rejected"] == 4

    builder = load_builder()
    assert builder.REV == PIN, (builder.REV, PIN)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exe = builder.build(HERE / "driver.cpp", OUTPUT / "build")

    first_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    second_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first_raw == second_raw, (first_raw, second_raw)
    facts = json.loads(first_raw)

    assert facts["first_changed_slot"] == 5
    assert facts["same_value_changed_count"] == 0
    assert facts["slot5_equals_slot7"] is True
    assert facts["first_cache_cleared"] is True
    assert facts["same_cache_cleared"] is True
    assert facts["oob_changed_count"] == 0
    assert facts["oob_cache_preserved"] is True
    assert facts["privilege_exception"] == 11
    assert facts["privilege_changed_count"] == 0

    evidence = {
        "ares_pin": PIN,
        "facts": facts,
        "model": model,
        "repeat_stdout_sha256": hashlib.sha256(first_raw.encode()).hexdigest(),
        "interpretation": {
            "legal_tlbwi_uses_cp0_index_slot": True,
            "same_value_tlbwi_is_invisible_to_snapshot_diff": True,
            "equal_payload_different_slot_is_ambiguous_without_index_boundary": True,
            "out_of_range_index_has_no_write_generation": True,
            "cu0_disabled_user_attempt_has_no_write_generation": True,
            "actual_selected_slot_write_boundary_required_for_complete_history": True,
        },
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + digest)
    print("PASS: exact TLBWI uses Index; same-value legal writes require an explicit mapping generation")


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
