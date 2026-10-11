#!/usr/bin/env python3
"""Fail closed if exact pinned VI/MI/CPU composition contracts drift."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"

ARES_BLOBS = {
    "ares/n64/vi/vi.cpp": "698d02f9dc274e6414079de7a09b80393555e0b2",
    "ares/n64/vi/io.cpp": "d541f2861fba00247e5a77f522585f70215f7199",
    "ares/n64/vi/vi.hpp": "043e9f2c74719ad8f6efa61f2db603dad4b0f983",
    "ares/n64/mi/mi.cpp": "5c2421cc7d9cc9c62b6d9445c978bb1c1d58a4c9",
    "ares/n64/cpu/cpu.cpp": "41964d49c8983ae9a97b25625174cd4c4316c4a8",
    "ares/n64/cpu/exceptions.cpp": "870e7d420f38fbda862cb4c7cb88481155b19251",
}


def revision(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def blob(repo: Path, path: str) -> str:
    return subprocess.check_output(["git", "rev-parse", f"HEAD:{path}"], cwd=repo, text=True).strip()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def main() -> int:
    if revision(ARES) != ARES_REV:
        raise SystemExit("ares pin mismatch")
    if revision(GOPHER) != GOPHER_REV:
        raise SystemExit("gopher64 pin mismatch")
    for path, want in ARES_BLOBS.items():
        got = blob(ARES, path)
        if got != want:
            raise SystemExit(f"ares blob drift {path}: {got} != {want}")

    vi = (ARES / "ares/n64/vi/vi.cpp").read_text()
    vi_io = (ARES / "ares/n64/vi/io.cpp").read_text()
    vi_h = (ARES / "ares/n64/vi/vi.hpp").read_text()
    mi = (ARES / "ares/n64/mi/mi.cpp").read_text()
    cpu = (ARES / "ares/n64/cpu/cpu.cpp").read_text()
    exc = (ARES / "ares/n64/cpu/exceptions.cpp").read_text()
    g_vi = (GOPHER / "src/device/vi.rs").read_text()
    g_mi = (GOPHER / "src/device/mi.rs").read_text()

    require(vi_h, "auto active() -> bool { return io.colorDepth != 0; }", "ares VI active gate")
    require(vi, "++io.vcounter;", "ares VI scanline progression")
    require(vi, "if(io.vcounter == io.coincidence >> 1)", "ares VI coincidence comparison")
    require(vi, "mi.raise(MI::IRQ::VI);", "ares VI coincidence raises MI VI")
    require(vi_io, "io.coincidence = data.bit(0,9);", "ares VI_INTR programming")
    require(vi_io, "mi.lower(MI::IRQ::VI);", "ares VI_CURRENT acknowledgement")
    require(mi, "line |= irq.vi.line & irq.vi.mask;", "ares MI VI mask gate")
    require(mi, "cpu.setInterruptPending(CPU::Interrupt::RCP, line);", "ares MI to CPU RCP pending")
    require(cpu, "scc.cause.interruptPending & scc.status.interruptMask", "ares CPU pending/mask gate")
    require(cpu, "scc.status.interruptEnable && !scc.status.exceptionLevel && !scc.status.errorLevel", "ares CPU IE/EXL/ERL gate")
    require(exc, "u16 vectorOffset = 0x0180;", "ares general exception vector")

    require(g_vi, "EVENT_TYPE_VI", "gopher scheduled VI event")
    require(g_vi, "device::mi::set_rcp_interrupt(device, device::mi::MI_INTR_VI);", "gopher VI event raises MI")
    require(g_vi, "VI_CURRENT_REG => device::mi::clear_rcp_interrupt(device, device::mi::MI_INTR_VI)", "gopher VI current acknowledgement")
    require(g_mi, "MI_INTR_VI", "gopher MI VI source")
    require(g_mi, "COP0_CAUSE_IP2", "gopher MI to CPU IP2")

    print("PASS: exact pinned ares/Gopher64 VI trigger, acknowledgement, MI gate and CPU-root contracts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
