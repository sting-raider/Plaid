#!/usr/bin/env python3
"""Execute the bounded exact-pin RSP vector load->store lineage experiment."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ARES = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-rsp-vector-load-store-lineage"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PLAID_BASE = "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256"


def load_builder():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("ares_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_json(script, *args):
    raw = subprocess.check_output([os.sys.executable, str(script), *map(str, args)], text=True)
    lines = [line for line in raw.splitlines() if line.strip()]
    return raw, json.loads(lines[0])


def worker():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)

    guard_raw, guard = run_json(HERE / "source_guard.py", ARES)
    model_raw, model = run_json(HERE / "model.py")
    assert model_raw.splitlines()[-1] == "PASS"
    assert model["fuzz"]["trials"] == 4096
    assert model["fuzz"]["value_only_ambiguous"] == 4096

    builder = load_builder()
    exe = builder.build(
        HERE / "driver.cpp",
        OUT / "build",
        extra_sources=(HERE / "model.py", HERE / "source_guard.py", Path(__file__)),
    )
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=45)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=45)
    assert raw1 == raw2, "exact-reference fixture was not deterministic"
    observed = json.loads(raw1)
    cases = {row["name"]: row for row in observed["cases"]}
    assert set(cases) == set(model["cases"])

    for name, expected in model["cases"].items():
        assert cases[name]["vector"] == expected["vector"], name
        assert cases[name]["destination"] == expected["destination"], name
        assert cases[name]["rsp_instruction_calls"] > 0, name

    assert cases["equal_decoy_latest_load"]["destination"] == list(range(0x70, 0x80))
    assert cases["mixed_same_value_no_diff"]["destination"] == [0x44] * 16
    assert cases["mixed_same_value_no_diff"]["vector"] == [0x44] * 16
    assert model["cases"]["mixed_same_value_no_diff"]["origins"][3].startswith(
        "same-store:same-load-a:"
    )
    assert model["cases"]["mixed_same_value_no_diff"]["origins"][5].startswith(
        "same-store:same-load-b:"
    )
    assert cases["mtc2_clobber"]["destination"][6:8] == [0xCA, 0xFE]
    assert model["cases"]["mtc2_clobber"]["origins"][6:8] == [
        "clobber-store:mtc2-r4:gpr",
        "clobber-store:mtc2-r4:gpr",
    ]
    assert model["cases"]["lrv_srv_effective_span"]["read_addresses"] == list(range(0x600, 0x60B))
    assert model["cases"]["lrv_srv_effective_span"]["write_addresses"] == list(range(0x700, 0x70B))

    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)
    result = {
        "plaid_base": PLAID_BASE,
        "ares_revision": REV,
        "driver_sha256": hashlib.sha256((HERE / "driver.cpp").read_bytes()).hexdigest(),
        "model_sha256": model["sha256"],
        "source_guard": guard,
        "reference_stdout_sha256": hashlib.sha256(raw1.encode()).hexdigest(),
        "repeat_deterministic": raw1 == raw2,
        "reference_unmodified": True,
        "reference": observed,
        "model": model,
        "conclusions": {
            "bounded_lqv_lrv_to_sqv_srv_values_match_lane_replay": True,
            "whole_vector_single_origin_is_unsound": True,
            "same_value_source_generations_are_not_distinguishable_by_value": True,
            "partial_loads_preserve_unwritten_lane_origins": True,
            "decoded_mtc2_cuts_only_its_written_lanes": True,
            "actual_read_callbacks_observed": False,
        },
        "limitations": [
            "Read addresses are derived from exact guarded interpreter source plus executed instruction inputs; this fixture does not install a completed-read callback.",
            "This validates pinned ares interpreter behavior for LQV/LRV, SQV/SRV and MTC2 only, not all RSP vector memory operations or hardware truth.",
            "The result does not establish whole-ROM reachability, executable lifetime, CPU refetch composition, DMA lineage, or native-complete closure.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "results.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
    print("REFERENCE_STDOUT_SHA256=" + result["reference_stdout_sha256"])
    print("MODEL_SHA256=" + result["model_sha256"])
    print("PASS bounded RSP vector lane lineage: values match exact-pin replay; value-only provenance is unsound")


def main():
    if os.name == "nt":
        script = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        worker()


if __name__ == "__main__":
    main()
