#!/usr/bin/env python3
"""Fail closed if exact pinned SI/MI/CPU composition contracts drift."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"

ARES_BLOBS = {
    "ares/n64/si/dma.cpp": "c2690ab2b0d4adaaec233871be98bea04b63d92b",
    "ares/n64/si/io.cpp": "9fd94bb082cb8cf4a70313a62df23b903ad1d7a5",
    "ares/n64/mi/mi.cpp": "5c2421cc7d9cc9c62b6d9445c978bb1c1d58a4c9",
    "ares/n64/cpu/cpu.cpp": "41964d49c8983ae9a97b25625174cd4c4316c4a8",
    "ares/n64/cpu/exceptions.cpp": "870e7d420f38fbda862cb4c7cb88481155b19251",
}
GOPHER_BLOBS = {
    "src/device/si.rs": "35460182400db0bd2cf28299e5bc5f7a69dd118d",
    "src/device/mi.rs": "ae3cfdb3e706a50b0ecbe02754cf0380cfaab94a",
}


def revision(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def blob(repo: Path, path: str) -> str:
    return subprocess.check_output(["git", "rev-parse", f"HEAD:{path}"], cwd=repo, text=True).strip()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def check_blobs(repo: Path, expected: dict[str, str], label: str) -> None:
    for path, want in expected.items():
        got = blob(repo, path)
        if got != want:
            raise SystemExit(f"{label} blob drift {path}: {got} != {want}")


def main() -> int:
    if revision(ARES) != ARES_REV:
        raise SystemExit("ares pin mismatch")
    if revision(GOPHER) != GOPHER_REV:
        raise SystemExit("gopher64 pin mismatch")
    check_blobs(ARES, ARES_BLOBS, "ares")
    check_blobs(GOPHER, GOPHER_BLOBS, "gopher64")

    si_dma = (ARES / "ares/n64/si/dma.cpp").read_text()
    si_io = (ARES / "ares/n64/si/io.cpp").read_text()
    mi = (ARES / "ares/n64/mi/mi.cpp").read_text()
    cpu = (ARES / "ares/n64/cpu/cpu.cpp").read_text()
    exc = (ARES / "ares/n64/cpu/exceptions.cpp").read_text()
    g_si = (GOPHER / "src/device/si.rs").read_text()
    g_mi = (GOPHER / "src/device/mi.rs").read_text()

    require(si_dma, "pif.dmaRead(io.readAddress, io.dramAddress);", "ares real SI read transfer")
    require(si_dma, "pif.dmaWrite(io.writeAddress, io.dramAddress);", "ares real SI write transfer")
    require(si_dma, "io.dmaBusy = 0;", "ares SI completion clears busy")
    require(si_dma, "io.interrupt = 1;", "ares SI completion latches interrupt")
    require(si_dma, "mi.raise(MI::IRQ::SI);", "ares SI completion raises MI source")
    require(si_io, "cpu.queueInsert(Queue::SI_DMA_Read", "ares SI read request queues completion")
    require(si_io, "cpu.queueInsert(Queue::SI_DMA_Write", "ares SI write request queues completion")
    require(si_io, "io.interrupt = 0;", "ares SI status acknowledgement clears latch")
    require(si_io, "mi.lower(MI::IRQ::SI);", "ares SI acknowledgement lowers MI source")
    require(si_io, "auto SI::writeFinished()", "ares separate direct PIF write completion producer")
    require(mi, "line |= irq.si.line & irq.si.mask;", "ares MI SI mask gate")
    require(mi, "cpu.setInterruptPending(CPU::Interrupt::RCP, line);", "ares MI to CPU RCP pending")
    require(cpu, "scc.cause.interruptPending & scc.status.interruptMask", "ares CPU pending/mask gate")
    require(cpu, "scc.status.interruptEnable && !scc.status.exceptionLevel && !scc.status.errorLevel", "ares CPU IE/EXL/ERL gate")
    require(exc, "u16 vectorOffset = 0x0180;", "ares general exception vector")

    require(g_si, "EVENT_TYPE_SI", "gopher SI scheduled completion")
    require(g_si, "SI_STATUS_DMA_BUSY", "gopher SI busy lifecycle")
    require(g_si, "SI_STATUS_INTERRUPT", "gopher SI interrupt latch")
    require(g_si, "set_rcp_interrupt(device, device::mi::MI_INTR_SI)", "gopher SI completion raises MI")
    require(g_si, "clear_rcp_interrupt(device, device::mi::MI_INTR_SI)", "gopher SI acknowledgement lowers MI")
    require(g_mi, "MI_INTR_SI", "gopher MI SI source")
    require(g_mi, "COP0_CAUSE_IP2", "gopher MI to CPU IP2")

    print("PASS: exact pinned ares/Gopher64 SI completion, acknowledgement, MI gate and CPU-root source contracts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
