"""Execute pinned ares TLB-mapped uncached fetch provenance experiment."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-tlb-uncached-fetch-spike"
BASE_RUNNER = ROOT / "spikes/025-ares-rdram-uncached-fetch/run.py"


def load_base_runner():
    spec = importlib.util.spec_from_file_location("rdram_fetch_base", BASE_RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.OUTPUT = OUTPUT
    return module


def pair_fetches(payload):
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


def phase(pairs, number):
    return [p for p in pairs if p["phase"] == number]


def adversarial_verifier(payload):
    pairs = pair_fetches(payload)
    # Physical/value equality cannot substitute for virtual/mapping context.
    p1, p2, p3 = phase(pairs, 1)[0], phase(pairs, 2)[0], phase(pairs, 3)[0]
    assert p1["bus_paddr"] == p2["bus_paddr"] and p1["value"] == p2["value"]
    assert p1["vaddr"] != p2["vaddr"]
    assert p1["vaddr"] == p3["vaddr"] and p1["value"] == p3["value"]
    assert p1["bus_paddr"] != p3["bus_paddr"]

    forged = copy.deepcopy(payload)
    # Move the phase-6 equal-valued data read into the second fetch interval.
    # Two eligible reads must make the witness unknown.
    fetch6 = [e for e in forged["fetch_events"] if e["phase"] == 6]
    scalar6 = [e for e in forged["scalar_events"] if e["phase"] == 6]
    assert len(fetch6) == 4 and len(scalar6) == 3
    decoy = next(e for e in scalar6 if e["address"] == 0x00b000)
    second_begin = fetch6[2]
    old_decoy, old_begin = decoy["ordinal"], second_begin["ordinal"]
    assert old_begin == old_decoy + 1, (old_decoy, old_begin)
    decoy["ordinal"], second_begin["ordinal"] = old_begin, old_decoy
    assert phase(pair_fetches(forged), 6)[1]["witness_ordinal"] is None

    cached = copy.deepcopy(payload)
    original = phase(pair_fetches(cached), 1)[0]
    begin_end = [e for e in cached["fetch_events"] if e["phase"] == 1]
    begin_end[0]["cache"] = begin_end[1]["cache"] = True
    assert phase(pair_fetches(cached), 1)[0]["witness_ordinal"] is None
    assert original["witness_ordinal"] is not None


def run():
    subprocess.run(["python3", str(HERE / "source_guard.py")], check=True)
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
    assert [facts[k] for k in ("primary", "alias", "remap")] == [0x1234] * 3
    assert facts["cached"] == 0x5678
    assert facts["little"] == 0x9abc
    assert facts["decoy"] == 0
    assert facts["global"] == 0x2468
    for key in ("asid_exception", "invalid_exception", "missing_exception"):
        assert facts[key] == 2, (key, facts[key])
    assert facts["asid_badvaddr"] == 0x20000
    assert facts["invalid_badvaddr"] == 0x24000
    assert facts["missing_badvaddr"] == 0x28000

    pairs = pair_fetches(traced)
    adversarial_verifier(traced)
    expected = {
        1: (0x4000, 0x001000, 0x001000, False, 0x34091234),
        2: (0x8000, 0x001000, 0x001000, False, 0x34091234),
        3: (0x4000, 0x003000, 0x003000, False, 0x34091234),
        4: (0xc000, 0x005000, 0x005000, True,  0x340a5678),
        5: (0x10000, 0x007000, 0x007004, False, 0x340b9abc),
        7: (0x1c000, 0x00d000, 0x00d000, False, 0x340c2468),
    }
    for ph, fields in expected.items():
        selected = phase(pairs, ph)
        assert len(selected) == 1, (ph, selected)
        p = selected[0]
        actual = (p["vaddr"], p["translated_paddr"], p["bus_paddr"], p["cache"], p["value"])
        assert actual == fields, (ph, actual, fields)
        if ph == 4:
            assert p["witness_ordinal"] is None
        else:
            assert p["witness_ordinal"] is not None

    p6 = phase(pairs, 6)
    assert len(p6) == 2 and all(p["witness_ordinal"] is not None for p in p6), p6
    assert [(p["vaddr"], p["bus_paddr"], p["value"]) for p in p6] == [
        (0x14000, 0x009000, 0x8e080000), (0x14004, 0x009004, 0x00000000)]
    scalar6 = [e for e in traced["scalar_events"] if e["phase"] == 6]
    assert [(e["address"], e["value"]) for e in scalar6] == [
        (0x009000, 0x8e080000), (0x00b000, 0), (0x009004, 0)]
    second_begin = next(e for e in traced["fetch_events"]
                        if e["phase"] == 6 and e["begin"] and e["vaddr"] == 0x14004)
    assert scalar6[1]["ordinal"] < second_begin["ordinal"]

    # Failed translations never reach CPU::fetch. Other devices are irrelevant;
    # specifically no uncached-CPU scalar event may masquerade as the fetch.
    for ph in (8, 9, 10):
        assert not phase(pairs, ph)
        assert not [e for e in traced["scalar_events"] if e["phase"] == ph and e["uncached_cpu"]]

    evidence = {
        "fetch_pairs": pairs,
        "scalar_events": traced["scalar_events"],
        "facts": facts,
        "state": traced["state"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "results.json"
    result_path.write_text(json.dumps({"baseline": baseline, "plain": plain, "traced": traced, "evidence": evidence},
                                      indent=2, sort_keys=True) + "\n")
    print("EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    print("RESULT_SHA256=" + hashlib.sha256(result_path.read_bytes()).hexdigest())
    print("PASS: TLB CCA=2 fetches join exact identity-RDRAM reads; aliases/remaps stay distinct; cacheable/failure paths fail closed")


def main():
    if os.name == "nt":
        script = subprocess.check_output(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()], text=True).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", script], check=True)
    else:
        run()


if __name__ == "__main__":
    main()
