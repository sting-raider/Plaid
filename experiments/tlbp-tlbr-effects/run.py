#!/usr/bin/env python3
"""Build and execute the exact pinned-ares TLBP/TLBR effects matrix."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-tlbp-tlbr-effects"
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

    expected_true = [
        "probe_cache_unchanged", "probe_devirt_unchanged", "probe_translation_same",
        "miss_failure", "miss_cache_unchanged", "miss_devirt_unchanged", "miss_translation_same",
        "tlbr_staged_matches", "tlbr_cache_unchanged", "tlbr_devirt_unchanged", "tlbr_translation_same",
        "same_value_tlbr_staged_same", "same_value_tlbr_devirt_unchanged",
        "oor_tlbr_staged_same", "oor_tlbr_cache_unchanged", "oor_tlbr_devirt_unchanged", "oor_tlbr_translation_same",
    ]
    for key in expected_true:
        assert facts[key] is True, (key, facts)
    assert facts["probe_slot"] == 9
    assert facts["probe_failure"] is False
    assert facts["miss_index"] == 0
    for key in ["probe_entries_changed", "miss_entries_changed", "tlbr_entries_changed", "same_value_tlbr_entries_changed", "oor_tlbr_entries_changed"]:
        assert facts[key] == 0, (key, facts)

    assert model["correct_mapping_generations"] == 0
    assert model["translation_mismatches"] == 0
    assert model["false_generations_if_cp0_delta_is_mapping"] == model["cp0_changes"]

    evidence = {
        "ares_pin": PIN,
        "facts": facts,
        "model": model,
        "repeat_stdout_sha256": hashlib.sha256(first_raw.encode()).hexdigest(),
        "interpretation": {
            "tlbp_is_mapping_observer_not_mapping_mutator": True,
            "tlbr_is_mapping_observer_not_mapping_mutator": True,
            "cp0_index_and_staging_deltas_are_not_mapping_generations": True,
            "same_value_tlbr_is_not_evidence_of_no_instruction_execution": True,
            "translation_cache_and_devirtualize_cache_survive_scoped_ops": True,
        },
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + digest)
    print("PASS: exact TLBP/TLBR change CP0 observation state without changing translation mappings in the tested scope")


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
