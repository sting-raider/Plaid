#!/usr/bin/env python3
"""Fail closed if the pinned ares/Gopher64 interrupt contracts drift."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def main() -> int:
    if revision(ARES) != ARES_REV:
        raise SystemExit("ares pin mismatch")
    if revision(GOPHER) != GOPHER_REV:
        raise SystemExit("gopher64 pin mismatch")

    cpu = (ARES / "ares/n64/cpu/cpu.cpp").read_text()
    exc = (ARES / "ares/n64/cpu/exceptions.cpp").read_text()
    gopher = (GOPHER / "src/device/exceptions.rs").read_text()

    require(cpu, "scc.cause.interruptPending & scc.status.interruptMask", "ares pending/mask intersection")
    require(cpu, "scc.status.interruptEnable && !scc.status.exceptionLevel && !scc.status.errorLevel", "ares IE/EXL/ERL gate")
    require(cpu, "exception.interrupt();", "ares instruction-boundary entry")
    require(exc, "auto CPU::Exception::interrupt()", "ares interrupt wrapper")
    require(exc, "trigger( 0);", "ares interrupt exception code")
    require(exc, "u16 vectorOffset = 0x0180;", "ares general vector")
    require(exc, "0xbfc0'0200", "ares BEV bootstrap base")
    require(exc, "0x8000'0000", "ares normal vector base")

    require(gopher, "COP0_STATUS_IE\n            | device::cop0::COP0_STATUS_EXL\n            | device::cop0::COP0_STATUS_ERL", "gopher IE/EXL/ERL gate")
    require(gopher, "COP0_CAUSE_IP_MASK", "gopher pending/mask intersection")
    require(gopher, "interrupt_exception(device);", "gopher interrupt entry")
    require(gopher, "exception_general(device, 0x180);", "gopher general vector")
    require(gopher, "0x80000000 + vector_offset", "gopher normal vector base")
    require(gopher, "0xBFC00200 + vector_offset", "gopher BEV vector base")

    print("PASS: exact pinned ares and Gopher64 maskable-interrupt gate/root source contracts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
