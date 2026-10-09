#!/usr/bin/env python3
"""Fail closed unless the exact pinned reference source seams still match."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

PINS = {
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "mupen64plus-core": "ba95bab92a76744753bfe61470823a4937850ab0",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
}

ROOT = Path(os.environ.get("REFS_DIR", ".refs"))


def head(repo: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()


def require(repo: str, rel: str, *needles: str) -> None:
    path = ROOT / repo / rel
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"source guard failed: {repo}/{rel} missing {needle!r}")


def main() -> None:
    for repo, pin in PINS.items():
        actual = head(ROOT / repo)
        if actual != pin:
            raise SystemExit(f"pin mismatch for {repo}: expected {pin}, got {actual}")

    # ares: accepted PI DMA schedules first, then copies synchronously; queue
    # insertion can return silently; queued dispatch alone calls dmaFinished().
    require(
        "ares",
        "ares/n64/pi/io.cpp",
        "cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true));\n    dmaRead();",
        "cpu.queueInsert(Queue::PI_DMA_Write, dmaDuration(false));\n    dmaWrite();",
        "queue.remove(Queue::PI_DMA_Read);",
        "io.interrupt = 0;\n      mi.lower(MI::IRQ::PI);",
    )
    require(
        "ares",
        "ares/n64/cpu/cpu.cpp",
        "if(!queue.insert(event, clocks)) return;",
        "case Queue::PI_DMA_Read:   return pi.dmaFinished();",
        "case Queue::PI_DMA_Write:  return pi.dmaFinished();",
        "scc.cause.interruptPending.bit(bit) = value;",
        "scc.status.interruptEnable && !scc.status.exceptionLevel && !scc.status.errorLevel",
        "exception.interrupt();",
    )
    require(
        "ares",
        "ares/n64/pi/dma.cpp",
        "auto PI::dmaFinished() -> void {",
        "io.interrupt = 1;\n  mi.raise(MI::IRQ::PI);",
    )
    require(
        "ares",
        "ares/n64/mi/mi.cpp",
        "case IRQ::PI: irq.pi.line = 1; break;",
        "case IRQ::PI: irq.pi.line = 0; break;",
        "line |= irq.pi.line & irq.pi.mask;",
        "cpu.setInterruptPending(CPU::Interrupt::RCP, line);",
    )
    require(
        "ares",
        "ares/n64/mi/io.cpp",
        "if(data.bit( 8)) irq.pi.mask = 0;",
        "if(data.bit( 9)) irq.pi.mask = 1;",
        "poll();",
    )
    require(
        "ares",
        "ares/n64/pi/serialization.cpp",
        "s(io.interrupt);",
        "s(io.originPc);",
    )
    require(
        "ares",
        "ares/n64/mi/serialization.cpp",
        "s(irq.pi.line);",
        "s(irq.pi.mask);",
    )

    # Independent source agreement on the coarse causal split.  Do not require
    # queue mechanics to match ares: they are explicitly implementation-specific.
    require(
        "mupen64plus-core",
        "src/device/rcp/pi/pi_controller.c",
        "add_interrupt_event(&pi->mi->r4300->cp0, PI_INT, cycles);",
        "pi->regs[PI_STATUS_REG] |= PI_STATUS_INTERRUPT;",
        "raise_rcp_interrupt(pi->mi, MI_INTR_PI);",
        "clear_rcp_interrupt(pi->mi, MI_INTR_PI);",
    )
    require(
        "mupen64plus-core",
        "src/device/rcp/mi/mi_controller.c",
        "mi->regs[MI_INTR_REG] |= mi_intr;",
        "if (mi->regs[MI_INTR_REG] & mi->regs[MI_INTR_MASK_REG])",
        "r4300_check_interrupt(mi->r4300, CP0_CAUSE_IP2, mi->regs[MI_INTR_REG] & mi->regs[MI_INTR_MASK_REG]);",
    )

    require(
        "gopher64",
        "src/device/pi.rs",
        "device::events::create_event(device, device::events::EVENT_TYPE_PI, cycles);",
        "device.pi.regs[PI_STATUS_REG] |= PI_STATUS_INTERRUPT;",
        "device::mi::set_rcp_interrupt(device, device::mi::MI_INTR_PI)",
        "device::mi::clear_rcp_interrupt(device, device::mi::MI_INTR_PI);",
    )
    require(
        "gopher64",
        "src/device/mi.rs",
        "device.mi.regs[MI_INTR_REG] |= interrupt;",
        "device.mi.regs[MI_INTR_REG] & device.mi.regs[MI_INTR_MASK_REG]",
        "device::exceptions::check_pending_interrupts(device)",
    )
    require(
        "gopher64",
        "src/device/exceptions.rs",
        "device::cop0::COP0_STATUS_IE",
        "device::cop0::COP0_STATUS_EXL",
        "device::cop0::COP0_STATUS_ERL",
        "exception_general(device, 0x180);",
    )

    print("PASS source guards")
    for repo, pin in PINS.items():
        print(f"{repo}={pin}")


if __name__ == "__main__":
    main()
