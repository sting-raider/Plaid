#!/usr/bin/env python3
"""Fail if the exact pinned source contracts used by this experiment drift."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / ".refs"
PINS = {
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
    "n64-systemtest": "196f5421173220eb2f63a7a99c64795dc0ea0698",
}

CHECKS = {
    "ares": {
        "ares/n64/rsp/interpreter-ipu.cpp": [
            "status.halted = 1;",
            "status.broken = 1;",
            "if(status.interruptOnBreak) mi.raise(MI::IRQ::SP);",
        ],
        "ares/n64/rsp/io.cpp": [
            "if(data.bit( 3) && !data.bit( 4)) mi.lower(MI::IRQ::SP);",
            "if(data.bit( 4) && !data.bit( 3)) mi.raise(MI::IRQ::SP);",
            "if(data.bit( 7) && !data.bit( 8)) status.interruptOnBreak = 0;",
            "if(data.bit( 8) && !data.bit( 7)) status.interruptOnBreak = 1;",
        ],
        "ares/n64/mi/mi.cpp": [
            "line |= irq.sp.line & irq.sp.mask;",
            "line |= irq.pi.line & irq.pi.mask;",
            "cpu.setInterruptPending(CPU::Interrupt::RCP, line);",
        ],
        "ares/n64/mi/io.cpp": [
            "if(data.bit( 0)) irq.sp.mask = 0;",
            "if(data.bit( 1)) irq.sp.mask = 1;",
            "poll();",
        ],
        "ares/n64/cpu/cpu.cpp": [
            "scc.cause.interruptPending & scc.status.interruptMask",
            "scc.status.interruptEnable && !scc.status.exceptionLevel && !scc.status.errorLevel",
            "exception.interrupt();",
        ],
    },
    "gopher64": {
        "src/device/rsp_interface.rs": [
            "if device.rsp.regs[SP_STATUS_REG] & SP_STATUS_INTR_BREAK != 0 {",
            "device::mi::set_rcp_interrupt(device, device::mi::MI_INTR_SP)",
            "if (w & SP_CLR_INTR) != 0 && (w & SP_SET_INTR) == 0 {",
            "if (w & SP_SET_INTR) != 0 && (w & SP_CLR_INTR) == 0 {",
        ],
        "src/device/mi.rs": [
            "device.mi.regs[MI_INTR_REG] & device.mi.regs[MI_INTR_MASK_REG]",
            "device.cpu.cop0.regs[device::cop0::COP0_CAUSE_REG] &= !device::cop0::COP0_CAUSE_IP2;",
            "pub fn set_rcp_interrupt(device: &mut device::Device, interrupt: u32)",
        ],
    },
    "n64-systemtest": {
        "src/tests/rsp/registers.rs": [
            "RSP::set_interrupt();",
            "soft_assert_eq(mi::is_sp_interrupt(), true",
            "SP_STATUS_SET_SET_INTERRUPT | crate::rsp::rsp::SP_STATUS_SET_CLEAR_INTERRUPT",
            "If both Interrupt set and clear are set, nothing should change",
        ],
    },
}


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> None:
    report: dict[str, object] = {"pins": {}, "files": {}}
    for name, expected in PINS.items():
        repo = REFS / name
        actual = git_head(repo)
        if actual != expected:
            raise SystemExit(f"{name}: expected {expected}, got {actual}")
        report["pins"][name] = actual
        for relative, needles in CHECKS[name].items():
            path = repo / relative
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            missing = [needle for needle in needles if needle not in text]
            if missing:
                raise SystemExit(f"{name}/{relative}: missing guarded source: {missing!r}")
            report["files"][f"{name}/{relative}"] = hashlib.sha256(raw).hexdigest()

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report_sha = hashlib.sha256(canonical).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"source_guard_sha256={report_sha}")


if __name__ == "__main__":
    main()
