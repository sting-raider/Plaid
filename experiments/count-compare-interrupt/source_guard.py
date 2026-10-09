#!/usr/bin/env python3
"""Fail closed if exact pinned Count/Compare producer contracts drift."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "target/count-compare-interrupt"
REFS = {
    "ares": (ROOT / ".refs/ares", "9408cb43d4948fc3ea6e152a307a34348df3fe04"),
    "gopher64": (ROOT / ".refs/gopher64", "e96debac941a26ba4961e5145056c0821d3a56f7"),
    "mupen64plus-core": (ROOT / ".refs/mupen64plus-core", "ba95bab92a76744753bfe61470823a4937850ab0"),
    "n64-systemtest": (ROOT / ".refs/n64-systemtest", "196f5421173220eb2f63a7a99c64795dc0ea0698"),
}


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def main() -> int:
    for name, (path, expected) in REFS.items():
        got = revision(path)
        if got != expected:
            raise SystemExit(f"{name} pin mismatch: {got} != {expected}")

    ares_cpu_path = REFS["ares"][0] / "ares/n64/cpu/cpu.cpp"
    ares_scc_path = REFS["ares"][0] / "ares/n64/cpu/interpreter-scc.cpp"
    gopher_cp0_path = REFS["gopher64"][0] / "src/device/cop0.rs"
    gopher_events_path = REFS["gopher64"][0] / "src/device/events.rs"
    mupen_mips_path = REFS["mupen64plus-core"][0] / "src/device/r4300/mips_instructions.def"
    mupen_irq_path = REFS["mupen64plus-core"][0] / "src/device/r4300/interrupt.c"
    systemtest_cp0_path = REFS["n64-systemtest"][0] / "src/cop0.rs"

    ares_cpu = ares_cpu_path.read_text()
    ares_scc = ares_scc_path.read_text()
    gopher_cp0 = gopher_cp0_path.read_text()
    gopher_events = gopher_events_path.read_text()
    mupen_mips = mupen_mips_path.read_text()
    mupen_irq = mupen_irq_path.read_text()
    systemtest_cp0 = systemtest_cp0_path.read_text()

    # ares: Count/Compare are an implicit modular comparator, not a queue event.
    require(ares_cpu, "u64 remaining = (u64)(scc.compare - scc.count) & CountMask;", "ares modular remaining")
    require(ares_cpu, "if(remaining && clocks >= remaining) setInterruptPending(Interrupt::Timer, 1);", "ares timer latch")
    require(ares_scc, "scc.count = data.bit(0,31) << 1;", "ares Count write")
    require(ares_scc, "scc.compare = data.bit(0,31) << 1;", "ares Compare write")
    require(ares_scc, "setInterruptPending(Interrupt::Timer, 0);", "ares Compare acknowledgement")

    # Gopher64: Compare is an explicit scheduled event. Count writes translate all
    # enabled events, including Compare, preserving the old relative deadline.
    require(gopher_cp0, "device::events::translate_events(device, device.cpu.cop0.regs[COP0_COUNT_REG], data);", "gopher Count event translation")
    require(gopher_cp0, "device.cpu.cop0.regs[COP0_CAUSE_REG] &= !COP0_CAUSE_IP7;", "gopher Compare acknowledgement")
    require(gopher_cp0, "device.cpu.cop0.regs[device::cop0::COP0_CAUSE_REG] |= device::cop0::COP0_CAUSE_IP7;", "gopher Compare assertion")
    require(gopher_events, "i.count = i.count - old_count + new_count;", "gopher all-event translation")

    # Mupen also translates event time on Count writes, but it explicitly removes
    # and recreates COMPARE_INT at the Compare register, so its Compare deadline
    # follows the new Count rather than preserving Gopher's prior relative delta.
    require(mupen_mips, "translate_event_queue(&r4300->cp0, rrt32);", "Mupen Count queue translation")
    require(mupen_mips, "cp0_regs[CP0_CAUSE_REG] &= ~CP0_CAUSE_IP7;", "Mupen Compare acknowledgement")
    require(mupen_irq, "remove_event(&cp0->q, COMPARE_INT);", "Mupen Compare removal during queue translation")
    require(mupen_irq, "add_interrupt_event_count(cp0, COMPARE_INT, cp0_regs[CP0_COMPARE_REG]);", "Mupen Compare recreation")
    require(mupen_irq, "raise_maskable_interrupt(r4300, CP0_CAUSE_IP7);", "Mupen Compare assertion")

    # The pinned system-test tree names the architectural Cause.IP7 bit, but a
    # dedicated Count/Compare timing test is not claimed by this worker.
    require(systemtest_cp0, "interrupt_compare : bool", "n64-systemtest Cause.IP7 naming")

    files = [
        ares_cpu_path, ares_scc_path, gopher_cp0_path, gopher_events_path,
        mupen_mips_path, mupen_irq_path, systemtest_cp0_path,
    ]
    payload = {
        "schema": "plaid-count-compare-source-guard/v0",
        "revisions": {name: expected for name, (_path, expected) in REFS.items()},
        "files": {str(path.relative_to(ROOT)): sha256(path) for path in files},
        "reference_disagreement": {
            "count_write": "ares and Mupen derive a new Compare deadline from the rewritten Count; Gopher64 translates the existing Compare event and preserves its prior relative deadline",
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "source_guard.json"
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    print(f"SOURCE_GUARD_SHA256 {sha256(target)}")
    print("PASS: exact pinned ares/Gopher64/Mupen64Plus/n64-systemtest Count/Compare contracts present; disagreement preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
