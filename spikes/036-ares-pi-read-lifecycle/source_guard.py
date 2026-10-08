#!/usr/bin/env python3
"""Fail closed if the pinned ares PI-read/queue contracts drift."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def require(path: str, snippets: list[str]) -> None:
    text = (REF / path).read_text()
    for snippet in snippets:
        assert text.count(snippet) == 1, (path, snippet, text.count(snippet))


def main() -> None:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    require("ares/n64/pi/io.cpp", [
        "cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true));\n    dmaRead();",
        "queue.remove(Queue::PI_DMA_Read);\n      queue.remove(Queue::PI_DMA_Write);",
    ])
    require("ares/n64/pi/dma.cpp", [
        "u16 data = rdram.ram.read<Half>(io.dramAddress + address, RBusDevice::PI_DMA);\n    busWriteHalf(data);",
        "auto PI::dmaFinished() -> void {\n  io.dmaBusy = 0;\n  io.interrupt = 1;\n  mi.raise(MI::IRQ::PI);",
    ])
    require("ares/n64/pi/bus.hpp", [
        "if(!io.ioBusy) io.busLatch = u32(data) << 16 | data;\n  if(busDevice >= 0) devices[busDevice].device->piWriteHalf(data, busTiming);",
    ])
    require("ares/n64/cpu/cpu.cpp", [
        "case Queue::PI_DMA_Read:   return pi.dmaFinished();",
        "case Queue::PI_DMA_Write:  return pi.dmaFinished();",
    ])
    require("ares/n64/n64.hpp", [
        "PI_DMA_Read,\n      PI_DMA_Write,",
    ])
    require("nall/nall/priority-queue.hpp", [
        "if(size >= capacity) return false;",
        "if(entry.valid) callback(entry.event);",
    ])
    print("PASS: exact pinned ares PI_DMA_Read ordering, backing-read, PBUS-latch, dispatch and queue contracts match")


if __name__ == "__main__":
    main()
