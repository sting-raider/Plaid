#!/usr/bin/env python3
"""Build exact pinned ares and execute BEV=1 32-bit TLB-refill/PIF composition."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUT = ROOT / "target/bev1-tlbrefill-pif-root"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
MODES = ("normal", "equal_offset_decoy", "mirror_decoy", "busy_latch", "lockout")
VECTOR_VA = 0xFFFFFFFFBFC00200
VECTOR_PHYS = 0x1FC00200
VECTOR_OFFSET = 0x200
TRIGGER_VA = 0xFFFFFFFFA0004000
MISSING_VA = 0x4000
HANDLER = 0x24020007


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_guard() -> None:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    assert revision == PIN, (revision, PIN)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    refs = (ROOT / "refs.lock.toml").read_text()
    assert f'rev = "{PIN}"' in refs

    exception = (REF / "ares/n64/cpu/exceptions.cpp").read_text()
    assert exception.count("(s32)0xbfc0'0200") == 1
    assert exception.count("if(self.context.bits == 32) vectorOffset = 0x0000;") == 1
    assert exception.count("if(self.context.bits == 64) vectorOffset = 0x0080;") == 1
    assert exception.count("auto CPU::Exception::tlbLoadMiss()") == 1
    assert exception.count("trigger( 2, 0, 1)") == 1
    assert exception.count("self.pipeline.setPc(vectorBase + vectorOffset);") == 1

    pif_io = (REF / "ares/n64/pif/io.cpp").read_text()
    assert pif_io.count("return rom.read<Word>(address);") == 1
    memory = (REF / "ares/n64/cpu/memory.cpp").read_text()
    assert memory.count("return busRead<Word>(paddr);") >= 1


def run_one(exe: Path, mode: str):
    for attempt in range(2):
        raw = subprocess.check_output([str(exe), mode], text=True, timeout=30)
        lines = [line for line in raw.splitlines() if line.startswith("{")]
        if lines:
            return json.loads(lines[-1])
        assert attempt == 0, (mode, "successful process produced no JSON twice")
    raise AssertionError("unreachable")


def root_event(result):
    events = [e for e in result["fetches"] if e["vaddr"] == VECTOR_VA]
    assert len(events) == 1, events
    return events[0]


def verify(results: dict) -> None:
    base = results["baseline"]
    inst = results["instrumented"]
    repeat = results["repeat"]
    for mode in MODES:
        assert inst[mode] == repeat[mode], mode
        assert inst[mode]["machine"] == base[mode]["machine"], mode
        machine = inst[mode]["machine"]
        assert machine["root_pc"] == VECTOR_VA, (mode, machine)
        assert machine["exception"] == 2, (mode, machine)
        assert machine["badva"] == MISSING_VA, (mode, machine)
        assert machine["epc"] == TRIGGER_VA, (mode, machine)
        assert machine["bev"] == 1 and machine["exl"] == 1, (mode, machine)
        assert machine["context_bits"] == 32, (mode, machine)

    for mode in ("normal", "equal_offset_decoy", "mirror_decoy"):
        event = root_event(inst[mode])
        assert event["ended"] and not event["cached"]
        assert event["physical"] == VECTOR_PHYS
        assert event["returned"] == HANDLER
        assert event["witness"] == {"kind": "pif_rom", "offset": VECTOR_OFFSET, "word": HANDLER}
        assert inst[mode]["machine"]["v0"] == 7

    normal = inst["normal"]
    assert normal["backing_reads"] == 1 and normal["unattributed_backing_reads"] == 0

    equal = inst["equal_offset_decoy"]
    assert equal["backing_reads"] == 2 and equal["unattributed_backing_reads"] == 1
    assert equal["machine"]["decoy"] == HANDLER
    assert root_event(equal)["witness"]["offset"] == VECTOR_OFFSET

    mirror = inst["mirror_decoy"]
    assert mirror["backing_reads"] == 2 and mirror["unattributed_backing_reads"] == 1
    assert mirror["machine"]["decoy"] == HANDLER
    assert root_event(mirror)["witness"]["offset"] == VECTOR_OFFSET

    busy = inst["busy_latch"]
    busy_event = root_event(busy)
    assert busy_event["physical"] == VECTOR_PHYS and busy_event["returned"] == HANDLER
    assert busy_event["witness"] is None
    assert busy["backing_reads"] == 0 and busy["unattributed_backing_reads"] == 0
    assert busy["machine"]["v0"] == 7

    locked = inst["lockout"]
    locked_event = root_event(locked)
    assert locked_event["physical"] == VECTOR_PHYS and locked_event["returned"] == 0
    assert locked_event["witness"] is None
    assert locked["backing_reads"] == 0 and locked["unattributed_backing_reads"] == 0
    assert locked["machine"]["v0"] == 0


def main() -> None:
    source_guard()
    base_builder = import_module(ROOT / "spikes/003-ares-oracle/run.py", "plaid_bev1_refill_base_builder")
    pif_probe = import_module(ROOT / "experiments/pif-rom-backing/run_ares.py", "plaid_bev1_refill_pif_probe")
    assert base_builder.REV == PIN and pif_probe.PIN == PIN
    OUT.mkdir(parents=True, exist_ok=True)
    driver = HERE / "driver.cpp"
    baseline = base_builder.build(driver, OUT / "baseline")
    probe_builder = pif_probe.patched_builder(OUT / "generated")
    instrumented = probe_builder.build(
        driver,
        OUT / "instrumented",
        raw_fetch_access=True,
        physical_fetch_access=True,
        pif_rom_access=True,
    )

    results = {"ares_revision": PIN, "baseline": {}, "instrumented": {}, "repeat": {}}
    for mode in MODES:
        results["baseline"][mode] = run_one(baseline, mode)
        results["instrumented"][mode] = run_one(instrumented, mode)
        results["repeat"][mode] = run_one(instrumented, mode)
    verify(results)
    out = OUT / "results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    canonical = json.dumps(results["instrumented"], sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print("EVIDENCE_SHA256=" + digest)
    print("RESULTS_PATH=" + str(out))
    print("PASS: real 32-bit BEV1 TLB refill entry reaches PIF vector; only the same active successful PIF-ROM read confers root byte provenance")


if __name__ == "__main__":
    main()
