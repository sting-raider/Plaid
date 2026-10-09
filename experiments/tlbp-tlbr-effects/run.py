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

    assert facts["tlbp_hit_slot"] == 9
    assert facts["tlbp_hit_translation_same"] is True
    assert facts["tlbp_miss_index"] == 0
    assert facts["tlbp_miss_translation_same"] is True
    assert facts["tlbr_enable_before_found"] is False
    assert facts["tlbr_enable_after_found"] is True
    assert facts["tlbr_enable_after_paddr"] == 0x00060000
    assert facts["tlbr_enable_asid_after"] == 0x55
    assert facts["tlbr_disable_before_found"] is True
    assert facts["tlbr_disable_after_found"] is False
    assert facts["tlbr_disable_asid_after"] == 10
    assert facts["all_mapping_entry_changes"] == 0
    assert facts["all_instruction_cache_snapshots_unchanged"] is True
    assert facts["all_devirtualize_sentinels_unchanged"] is True
    assert facts["same_value_tlbr_translation_same"] is True
    assert facts["out_of_range_tlbr_translation_same"] is True

    assert model["mapping_entry_mutations"] == 0
    assert model["tlbp_translation_flips"] == 0
    assert model["tlbr_active_asid_changes"] > 0
    assert model["tlbr_sampled_translation_flips"] > 0
    assert model["false_entry_generations_if_any_cp0_delta_is_entry_write"] == model["cp0_changes"]

    evidence = {
        "ares_pin": PIN,
        "facts": facts,
        "model": model,
        "repeat_stdout_sha256": hashlib.sha256(first_raw.encode()).hexdigest(),
        "interpretation": {
            "original_tlbr_observational_hypothesis_rejected": True,
            "tlbp_index_side_effect_did_not_change_translation_in_tested_cases": True,
            "tlbr_did_not_mutate_tlb_entries_or_translation_caches": True,
            "tlbr_entryhi_asid_can_change_translation_reachability": True,
            "mapping_entry_generation_and_translation_context_generation_must_be_distinct": True,
            "same_value_or_out_of_range_tlbr_need_not_change_translation_context": True,
        },
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + digest)
    print("PASS: TLBR leaves mapping entries/caches intact but EntryHi ASID can change mapped-VA reachability")


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
