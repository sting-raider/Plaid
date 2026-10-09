#!/usr/bin/env python3
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-mtc0-entryhi-asid"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def worker():
    guard_raw = subprocess.check_output(["python3", str(HERE / "source_guard.py")], text=True)
    model_raw = subprocess.check_output(["python3", str(HERE / "model.py")], text=True)
    model = json.loads(model_raw)
    builder = load_builder()
    assert builder.REV == PIN, (builder.REV, PIN)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exe = builder.build(HERE / "driver.cpp", OUTPUT / "build")
    first_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    second_raw = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first_raw == second_raw
    facts = json.loads(first_raw)

    assert facts["a"] == {"value": 0x1111, "paddr": 0x1000}
    assert facts["b"] == {"value": 0x2222, "paddr": 0x3000}
    assert facts["equal1"] == {"value": 0x1111, "paddr": 0x5000}
    assert facts["equal2"] == facts["equal1"]
    assert facts["global_b"] == facts["global_a"] == {"value": 0x7777, "paddr": 0x7000}
    assert facts["miss"] == {"exception": 2, "badvaddr": 0x4000}
    assert facts["same_value_entryhi_unchanged"] is True
    assert facts["installed_entries_unchanged"] is True
    assert facts["mtc0_writes"] == 7
    assert model["naive_entry_only_wrong_backing"] > 0
    assert model["same_value_writes_invisible_to_state_diff"] > 0
    assert model["equal_payload_different_backing_context_switches"] > 0

    evidence = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "ares_pin": PIN,
        "facts": facts,
        "model": model,
        "source_guard_stdout": guard_raw.strip().splitlines(),
        "repeat_stdout_sha256": hashlib.sha256(first_raw.encode()).hexdigest(),
        "interpretation": {
            "mtc0_entryhi_can_change_backing_without_entry_mutation": True,
            "equal_payload_does_not_identify_backing": True,
            "global_mapping_is_asid_insensitive": True,
            "same_value_entryhi_write_is_invisible_to_state_diff": True,
            "entry_generation_only_model_is_insufficient": True,
        },
    }
    out = OUTPUT / "results.json"
    out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + digest)
    print("PASS: MTC0 EntryHi ASID switches executable backing with installed TLB entries unchanged")


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
