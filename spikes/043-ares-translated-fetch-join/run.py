"""Build pinned ares and validate translated/degraded RDRAM -> uncached CPU fetch joins."""
from pathlib import Path
import copy
import hashlib
import json
import os
import subprocess
import types

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "target/ares-translated-fetch-join-spike"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
HERE = Path(__file__).resolve().parent

ORI_T1 = 0x34091234
ORI_T2 = 0x340A5678
ORI_T3 = 0x340B1357


def load_patched_builder():
    """Add the completed translated-read callback to a copy of the shared builder."""
    path = ROOT / "spikes/003-ares-oracle/run.py"
    source = path.read_text()
    anchor = '                ram = "// Project-owned successful identity-mapped ordinary RAM callbacks.'
    assert source.count(anchor) == 1
    insert_at = source.index(
        "                destination.parent.mkdir(parents=True,exist_ok=True)",
        source.index(anchor),
    )
    injection = r'''                plaidTranslatedOld = """        u32 chipIndex = mapped() / 2_MiB;
        u64 value = Memory::Writable::read<Size>(mapped());
        return degrade(mapped(), value, chipIndex);"""
                plaidTranslatedNew = """        u32 chipIndex = mapped() / 2_MiB;
        u32 plaidMapped = mapped();
        auto& plaidChip = self.chips[chipIndex];
        u64 value = Memory::Writable::read<Size>(plaidMapped);
        u32 plaidCci = plaidChip.cci;
        u32 plaidCcLow = plaidChip.ccLow;
        u32 plaidCcHigh = plaidChip.ccHigh;
        u64 plaidDelivered = degrade(plaidMapped, value, chipIndex);
        if(plaidRdramTranslatedObserver) plaidRdramTranslatedObserver(address, plaidMapped, Size, (u32)device, chipIndex, value, plaidDelivered, plaidCci, plaidCcLow, plaidCcHigh);
        return plaidDelivered;"""
                assert ram.count(plaidTranslatedOld) == 1
                ram = ram.replace(plaidTranslatedOld, plaidTranslatedNew)
                ram = "// Project-owned completed translated ordinary RAM read callback.\\nusing PlaidRdramTranslatedObserver = void (*)(u32, u32, u32, u32, u32, u64, u64, u32, u32, u32);\\ninline PlaidRdramTranslatedObserver plaidRdramTranslatedObserver = nullptr;\\n" + ram
'''
    patched = source[:insert_at] + injection + source[insert_at:]
    module = types.ModuleType("plaid_translated_fetch_builder")
    module.__file__ = str(path)
    exec(compile(patched, str(path), "exec"), module.__dict__)
    return module, source, patched


def source_guard(ref):
    ram = (ref / "ares/n64/rdram/rdram.hpp").read_text()
    memory = (ref / "ares/n64/cpu/memory.cpp").read_text()
    scalar = """        u32 chipIndex = mapped() / 2_MiB;
        u64 value = Memory::Writable::read<Size>(mapped());
        return degrade(mapped(), value, chipIndex);"""
    fetch = """auto CPU::fetch(PhysAccess access) -> maybe<u32> {
  step(1 * 2);
  if(!access) return nothing;
  u32 paddr = access.paddr;
  if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);
  if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);
  return busRead<Word>(paddr);
}"""
    assert ram.count(scalar) == 1
    assert memory.count(fetch) == 1
    assert ram.count("u32 word = self.hidden.nibble(mapped & ~3);") == 1
    impl = (ref / "ares/n64/rdram/rdram.cpp").read_text()
    assert impl.count("auto RDRAM::Writable::translate(u32 address) -> maybe<u32>") == 1
    assert impl.count("return n * 2_MiB + (address & 0x1f'ffff);") == 1
    assert impl.count("if(chip.cci >= chip.ccHigh) return value;") == 1
    assert impl.count("if(chip.cci <= chip.ccLow) return 0;") == 1


def renumber(events):
    out = copy.deepcopy(events)
    for i, event in enumerate(out, 1):
        event["ordinal"] = i
    return out


def pair_fetches(events):
    assert [e["ordinal"] for e in events] == list(range(1, len(events) + 1))
    fetches = [e for e in events if e["kind"] == 0]
    assert len(fetches) % 2 == 0
    pairs = []
    for i in range(0, len(fetches), 2):
        begin, end = fetches[i], fetches[i + 1]
        assert begin["begin"] and not end["begin"]
        assert begin["ordinal"] < end["ordinal"]
        for key in ("phase", "pc", "vaddr", "translated_paddr", "bus_paddr", "cache"):
            assert begin[key] == end[key], (begin, end)
        between = [
            e for e in events
            if begin["ordinal"] < e["ordinal"] < end["ordinal"] and e["kind"] == 1
        ]
        eligible = [
            e for e in between
            if e["phase"] == begin["phase"]
            and e["bytes"] == 4
            and e["uncached_cpu"]
            and e["request"] == begin["bus_paddr"]
            and e["delivered"] == end["value"]
        ]
        witness = eligible[0] if (not begin["cache"] and len(eligible) == 1) else None
        pairs.append({
            "phase": begin["phase"],
            "vaddr": begin["vaddr"],
            "translated_paddr": begin["translated_paddr"],
            "bus_paddr": begin["bus_paddr"],
            "cache": begin["cache"],
            "value": end["value"],
            "between_translated_ordinals": [e["ordinal"] for e in between],
            "witness": None if witness is None else {
                "ordinal": witness["ordinal"],
                "request": witness["request"],
                "mapped": witness["mapped"],
                "chip": witness["chip"],
                "raw": witness["raw"],
                "delivered": witness["delivered"],
                "cci": witness["cci"],
                "cc_low": witness["cc_low"],
                "cc_high": witness["cc_high"],
                "transformed": witness["raw"] != witness["delivered"],
            },
        })
    return pairs


def adversarial_checks(events, pairs):
    phase2_fetch = pairs[1]
    value_only = [
        e for e in events
        if e["kind"] == 1 and e["delivered"] == phase2_fetch["value"]
    ]
    assert len(value_only) >= 3
    assert phase2_fetch["witness"] is not None

    forged = copy.deepcopy(events)
    end_index = next(
        i for i, e in enumerate(forged)
        if e["kind"] == 0 and e["phase"] == 2 and not e["begin"]
    )
    begin_ord = next(
        e["ordinal"] for e in forged
        if e["kind"] == 0 and e["phase"] == 2 and e["begin"]
    )
    inner = next(
        e for e in forged
        if e["kind"] == 1 and e["phase"] == 2 and e["ordinal"] > begin_ord
    )
    forged.insert(end_index, copy.deepcopy(inner))
    forged = renumber(forged)
    assert pair_fetches(forged)[1]["witness"] is None

    forged = copy.deepcopy(events)
    event = next(e for e in forged if e["kind"] == 1 and e["phase"] == 1)
    event["request"] ^= 4
    assert pair_fetches(forged)[0]["witness"] is None

    forged = copy.deepcopy(events)
    event = next(e for e in forged if e["kind"] == 1 and e["phase"] == 3)
    event["delivered"] = event["raw"]
    assert pair_fetches(forged)[2]["witness"] is None

    forged = [
        e for e in copy.deepcopy(events)
        if not (e["kind"] == 1 and e["phase"] == 3)
    ]
    forged = renumber(forged)
    assert pair_fetches(forged)[2]["witness"] is None

    forged = copy.deepcopy(events)
    end_index = next(
        i for i, e in enumerate(forged)
        if e["kind"] == 0 and e["phase"] == 1 and not e["begin"]
    )
    decoy = copy.deepcopy(next(e for e in forged if e["kind"] == 1 and e["phase"] == 1))
    decoy["request"] += 0x100
    decoy["mapped"] += 0x100
    decoy["raw"] ^= 0x11111111
    decoy["delivered"] = decoy["raw"]
    forged.insert(end_index, decoy)
    forged = renumber(forged)
    assert pair_fetches(forged)[0]["witness"] is not None

    return {
        "value_only_candidate_count_phase2": len(value_only),
        "ambiguous_matching_read_fails_closed": True,
        "wrong_request_fails_closed": True,
        "raw_delivered_substitution_fails_closed": True,
        "missing_translated_read_fails_closed": True,
        "unrelated_in_context_read_does_not_steal": True,
    }


def worker():
    builder, original_builder, patched_builder = load_patched_builder()
    assert builder.REV == PIN
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=builder.REF, text=True).strip() == PIN
    source_guard(builder.REF)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    driver = HERE / "driver.cpp"
    observer = HERE / "observer.hpp"

    baseline = builder.build(
        HERE / "baseline.cpp", OUTPUT / "baseline",
        raw_fetch_access=True, physical_fetch_access=True,
        extra_sources=(driver, observer),
    )
    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    baseline_payload = json.loads(baseline_raw)

    sensor = builder.build(
        driver, OUTPUT / "sensor",
        raw_fetch_access=True, physical_fetch_access=True,
        rdram_scalar_access=True, fetch_boundary_access=True,
        extra_sources=(observer,),
    )
    raws = [
        subprocess.check_output([str(sensor), mode], text=True, timeout=30)
        for mode in ("plain", "traced", "traced")
    ]
    plain, traced, repeat = [json.loads(raw) for raw in raws]

    assert raws[1] == raws[2]
    assert baseline_payload["facts"] == plain["facts"] == traced["facts"] == repeat["facts"]
    assert baseline_payload["state"] == plain["state"] == traced["state"] == repeat["state"]
    assert baseline_payload["events"] == plain["events"] == []
    assert len(traced["events"]) == 17

    facts = traced["facts"]
    assert facts["t1"] == 0x1234
    assert facts["t2"] == 0
    assert facts["t3"] == 0x1357
    assert facts["decoy"] == ORI_T1
    assert facts["ri_error"] == 1

    pairs = pair_fetches(traced["events"])
    assert [p["phase"] for p in pairs] == [1, 2, 3, 4, 5, 6]

    p1, p2, p3, p4, p5, p6 = pairs
    for p in (p1, p2):
        w = p["witness"]
        assert w is not None
        assert (p["translated_paddr"], p["bus_paddr"]) == (0, 0)
        assert (w["request"], w["mapped"], w["chip"], w["raw"], w["delivered"], w["cci"]) == (
            0, 0x200000, 1, ORI_T1, ORI_T1, 63
        )
        assert not w["transformed"]

    phase2_reads = [e for e in traced["events"] if e["kind"] == 1 and e["phase"] == 2]
    assert len(phase2_reads) == 2
    assert len(p2["between_translated_ordinals"]) == 1

    w3 = p3["witness"]
    assert w3 is not None
    assert (w3["request"], w3["mapped"], w3["chip"], w3["raw"], w3["delivered"]) == (
        0, 0x200000, 1, ORI_T2, 0
    )
    assert (w3["cci"], w3["cc_low"], w3["cc_high"]) == (8, 8, 16)
    assert w3["transformed"]
    assert p3["value"] == 0

    assert p4["witness"] is None
    assert p4["between_translated_ordinals"] == []
    assert p5["witness"] is None
    assert p5["between_translated_ordinals"] == []

    w6 = p6["witness"]
    assert w6 is not None
    assert (p6["translated_paddr"], p6["bus_paddr"]) == (0, 4)
    assert (w6["request"], w6["mapped"], w6["chip"], w6["raw"], w6["delivered"], w6["cci"]) == (
        4, 0x200004, 1, ORI_T3, ORI_T3, 63
    )
    assert not w6["transformed"]

    adversarial = adversarial_checks(traced["events"], pairs)

    report = {
        "pin": PIN,
        "event_count": len(traced["events"]),
        "fetch_count": len(pairs),
        "translated_read_count": sum(e["kind"] == 1 for e in traced["events"]),
        "pairs": pairs,
        "adversarial": adversarial,
        "state": traced["state"],
        "facts": facts,
    }
    result_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (OUTPUT / "results.json").write_text(result_text)
    manifest = {
        "pin": PIN,
        "original_builder_sha256": hashlib.sha256(original_builder.encode()).hexdigest(),
        "patched_builder_sha256": hashlib.sha256(patched_builder.encode()).hexdigest(),
        "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
        "observer_sha256": hashlib.sha256(observer.read_bytes()).hexdigest(),
        "trace_sha256": hashlib.sha256(raws[1].encode()).hexdigest(),
        "results_sha256": hashlib.sha256(result_text.encode()).hexdigest(),
        "event_count": len(traced["events"]),
        "fetch_count": len(pairs),
        "translated_read_count": report["translated_read_count"],
    }
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (OUTPUT / "manifest.json").write_text(manifest_text)

    print(manifest_text, end="")
    print(result_text, end="")
    print(
        "PASS: translated raw backing and post-CCI delivered instruction are joined "
        "inside explicit CPU fetch contexts; degraded delivery stays distinct, and "
        "missing/EBUS/ambiguous/value-only alternatives fail closed"
    )


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
