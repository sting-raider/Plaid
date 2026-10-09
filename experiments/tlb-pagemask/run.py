#!/usr/bin/env python3
"""Build and execute the exact-pin large-PageMask TLB provenance experiment."""
from __future__ import annotations

from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-tlb-pagemask"
BASE_RUNNER = ROOT / "spikes/025-ares-rdram-uncached-fetch/run.py"
MODEL = HERE / "source_model.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_base_runner():
    module = load_module(BASE_RUNNER, "rdram_fetch_base")
    module.HERE = HERE
    module.OUTPUT = OUTPUT
    return module


def pair_fetches(payload: dict) -> list[dict]:
    scalars = payload["scalar_events"]
    fetches = payload["fetch_events"]
    ordered = sorted(e["ordinal"] for e in [*scalars, *fetches])
    assert ordered == list(range(1, len(ordered) + 1)), ordered
    assert len(fetches) % 2 == 0
    pairs = []
    for i in range(0, len(fetches), 2):
        begin, end = fetches[i], fetches[i + 1]
        assert begin["begin"] and not end["begin"]
        for key in ("phase", "pc", "vaddr", "translated_paddr", "bus_paddr", "cache"):
            assert begin[key] == end[key], (begin, end)
        assert begin["ordinal"] < end["ordinal"]
        eligible = [e for e in scalars
                    if begin["ordinal"] < e["ordinal"] < end["ordinal"]
                    and not e["write"] and e["bytes"] == 4 and e["uncached_cpu"]]
        witness = None
        if not begin["cache"] and len(eligible) == 1:
            candidate = eligible[0]
            if candidate["address"] == begin["bus_paddr"] and candidate["value"] == end["value"]:
                witness = candidate["ordinal"]
        pairs.append({
            "phase": begin["phase"],
            "vaddr": begin["vaddr"],
            "translated_paddr": begin["translated_paddr"],
            "bus_paddr": begin["bus_paddr"],
            "cache": begin["cache"],
            "value": end["value"],
            "witness_ordinal": witness,
            "between_scalars": [e["ordinal"] for e in scalars
                                if begin["ordinal"] < e["ordinal"] < end["ordinal"]],
        })
    return pairs


def by_phase(pairs: list[dict], phase: int) -> list[dict]:
    return [p for p in pairs if p["phase"] == phase]


def adversarial_checks(payload: dict, model) -> list[dict]:
    pairs = pair_fetches(payload)
    mapping_inputs = {
        1: (0, 0x00004000, 0x001000, 0x002000),
        2: (0b11 << 13, 0x00021000, 0x010000, 0x020000),
        3: (0b11 << 13, 0x0002C000, 0x030000, 0x040000),
        4: (0b1111 << 13, 0x00045000, 0x050000, 0x070000),
        5: (0b1111 << 13, 0x00070000, 0x080000, 0x0A0000),
        6: (0b11 << 13, 0x00084000, 0x0C0000, 0x0D0000),
    }
    rows = []
    for phase, (mask, vaddr, p0, p1) in mapping_inputs.items():
        selected = by_phase(pairs, phase)
        assert len(selected) == 1, (phase, selected)
        pair = selected[0]
        actual_lo, model_paddr = model.translate(vaddr, mask, p0, p1)
        naive_lo, naive_paddr = model.fixed_4k_guess(vaddr, p0, p1)
        assert model_paddr == pair["translated_paddr"] == pair["bus_paddr"], (phase, pair, model_paddr)
        assert pair["witness_ordinal"] is not None
        if phase == 1:
            assert (actual_lo, model_paddr) == (naive_lo, naive_paddr)
        else:
            assert (actual_lo, model_paddr) != (naive_lo, naive_paddr), phase
            forged = copy.deepcopy(payload)
            for event in forged["fetch_events"]:
                if event["phase"] == phase:
                    event["translated_paddr"] = naive_paddr
                    event["bus_paddr"] = naive_paddr
            assert by_phase(pair_fetches(forged), phase)[0]["witness_ordinal"] is None
        rows.append({
            "phase": phase,
            "mask": mask,
            "vaddr": vaddr,
            "actual_lo": actual_lo,
            "actual_paddr": model_paddr,
            "fixed4k_lo": naive_lo,
            "fixed4k_paddr": naive_paddr,
            "value": pair["value"],
            "witness_ordinal": pair["witness_ordinal"],
        })

    # Large-page ASID mismatch and invalid selected-half paths must stop before fetch.
    for phase in (7, 8):
        assert not by_phase(pairs, phase)
        assert not [e for e in payload["scalar_events"] if e["phase"] == phase and e["uncached_cpu"]]
    return rows


def run() -> None:
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
    subprocess.run(["python3", str(MODEL)], check=True)
    model = load_module(MODEL, "tlb_pagemask_model")

    base = load_base_runner()
    baseline_exe = base.build_baseline()
    instrumented_exe = base.build_instrumented()
    baseline_raw = subprocess.check_output([str(baseline_exe), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(instrumented_exe), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(instrumented_exe), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw

    baseline, plain, traced = map(json.loads, (baseline_raw, plain_raw, traced_raw))
    assert not baseline["scalar_events"] and not baseline["fetch_events"]
    assert not plain["scalar_events"] and not plain["fetch_events"]
    assert baseline["facts"] == plain["facts"] == traced["facts"]
    assert baseline["state"] == plain["state"] == traced["state"]

    facts = traced["facts"]
    assert [facts[k] for k in ("v4k", "v16_even", "v16_odd", "v64_even", "v64_odd", "vglobal")] == [
        0x1111, 0x2222, 0x3333, 0x4444, 0x5555, 0x6666]
    assert facts["select4k"] == 0x1000
    assert facts["select16k"] == 0x4000
    assert facts["select64k"] == 0x10000
    assert facts["mask16k"] == (0b11 << 13)
    assert facts["mask64k"] == (0b1111 << 13)
    assert facts["asid_exception"] == 2 and facts["asid_badvaddr"] == 0x00089000
    assert facts["invalid_exception"] == 2 and facts["invalid_badvaddr"] == 0x00091000

    pairs = pair_fetches(traced)
    expected = {
        1: (0x00004000, 0x001000, 0x34091111),
        2: (0x00021000, 0x011000, 0x340A2222),
        3: (0x0002C000, 0x040000, 0x340B3333),
        4: (0x00045000, 0x055000, 0x340C4444),
        5: (0x00070000, 0x0A0000, 0x340D5555),
        6: (0x00084000, 0x0D0000, 0x340E6666),
    }
    for phase, fields in expected.items():
        selected = by_phase(pairs, phase)
        assert len(selected) == 1, (phase, selected)
        pair = selected[0]
        assert (pair["vaddr"], pair["translated_paddr"], pair["value"]) == fields
        assert pair["bus_paddr"] == pair["translated_paddr"]
        assert not pair["cache"] and pair["witness_ordinal"] is not None
        between = [e for e in traced["scalar_events"] if e["ordinal"] in pair["between_scalars"]]
        assert len(between) == 1 and between[0]["address"] == pair["translated_paddr"]

    adversarial = adversarial_checks(traced, model)
    evidence = {
        "fetch_pairs": pairs,
        "adversarial_geometry": adversarial,
        "facts": facts,
        "state": traced["state"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps({
        "baseline": baseline,
        "plain": plain,
        "traced": traced,
        "evidence": evidence,
    }, indent=2, sort_keys=True) + "\n")
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + hashlib.sha256(result_path.read_bytes()).hexdigest())
    print("PASS: large PageMask fetches use mask-derived half/offset geometry; fixed-4KiB reconstruction fails closed")


def main() -> None:
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
