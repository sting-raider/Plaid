#!/usr/bin/env python3
"""Fail-closed source guard for the PI-copy/queue/cache composition seam."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
REQUIRED = {
    "nall/nall/priority-queue.hpp": [
        "if(size >= Size) return false;",
        "if(auto event = remove()) callback(*event);",
    ],
    "ares/n64/n64.hpp": [
        "struct Queue : priority_queue<u32[512]>",
    ],
    "ares/n64/cpu/cpu.cpp": [
        "if(!queue.insert(event, clocks)) return;",
        "case Queue::PI_DMA_Write:  return pi.dmaFinished();",
    ],
    "ares/n64/pi/io.cpp": [
        "io.dmaBusy = 1;\n    io.originPc = cpu.ipu.pc;\n    cpu.queueInsert(Queue::PI_DMA_Write, dmaDuration(false));\n    dmaWrite();",
        "if(data.bit(1)) {\n      io.interrupt = 0;",
    ],
    "ares/n64/pi/dma.cpp": [
        "auto PI::dmaWrite() -> void {",
        "rdram.ram.write<Byte>(io.dramAddress++, mem[i], RBusDevice::PI_DMA);",
        "rdram.ram.write<Byte>(io.dramAddress++, mem[i+0], RBusDevice::PI_DMA);",
        "rdram.ram.write<Byte>(io.dramAddress++, mem[i+1], RBusDevice::PI_DMA);",
        "auto PI::dmaFinished() -> void {\n  io.dmaBusy = 0;\n  io.interrupt = 1;",
    ],
    "ares/n64/cpu/cpu.hpp": [
        "auto fetch(u64 vaddr, u32 paddr, CPU& cpu) -> u32 {",
        "if(!line.hit(paddr)) {",
        "line.fill(paddr, cpu);",
        "return line.read(paddr);",
        "cpu.busReadBurst<ICache>(tag | index, words);",
    ],
    "ares/n64/cpu/memory.cpp": [
        "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);",
    ],
    "ares/n64/memory/bus.hpp": [
        "if constexpr(Size == ICache) device = RBusDevice::VR4300_ICACHE;",
        "if(address <= 0x03ff'ffff) return mi.readRdramBurst<Size>(address, data, device, thread), true;",
    ],
    "ares/n64/mi/bus.hpp": [
        "rdram.ram.readBurst<Size>(address, data, device);",
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ares", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "-C", str(args.ares), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise SystemExit(f"wrong ares revision: {head}")
    subprocess.run(["git", "-C", str(args.ares), "diff", "--quiet", "HEAD"], check=True)
    hashes = {}
    contracts = 0
    for relative, needles in REQUIRED.items():
        path = args.ares / relative
        data = path.read_bytes()
        text = data.decode("utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise SystemExit(f"{relative}: missing source contract(s): {missing}")
        contracts += len(needles)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    print(json.dumps({
        "ares_revision": PIN,
        "contracts": contracts,
        "guarded_files_sha256": hashes,
        "result": "PASS",
    }, sort_keys=True))


if __name__ == "__main__":
    main()
