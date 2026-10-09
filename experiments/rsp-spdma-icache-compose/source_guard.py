#!/usr/bin/env python3
"""Fail-closed source guard for the exact pinned ares composition seam."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

REQUIRED = {
    "ares/n64/rsp/dma.cpp": [
        "if(dma.busy.write) {",
        "u32 dataLo = dmem.read<Word>(dma.current.pbusAddress + 0);",
        "u32 dataHi = dmem.read<Word>(dma.current.pbusAddress + 4);",
        "rdram.ram.write<Word>(dma.current.dramAddress + 0, dataLo, RBusDevice::SP_DMA);",
        "rdram.ram.write<Word>(dma.current.dramAddress + 4, dataHi, RBusDevice::SP_DMA);",
    ],
    "ares/n64/cpu/cpu.hpp": [
        "auto fetch(u64 vaddr, u32 paddr, CPU& cpu) -> u32 {",
        "if(!line.hit(paddr)) {",
        "line.fill(paddr, cpu);",
        "return line.read(paddr);",
        "auto fill(u32 paddr, CPU& cpu) -> void {",
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


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ares", type=Path, required=True)
    args = parser.parse_args()

    if git_head(args.ares) != PIN:
        raise SystemExit(f"wrong ares revision: expected {PIN}")

    hashes = {}
    for relative, needles in REQUIRED.items():
        path = args.ares / relative
        data = path.read_bytes()
        text = data.decode("utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            raise SystemExit(
                f"{relative}: pinned source contract changed/missing: {missing}"
            )
        hashes[relative] = hashlib.sha256(data).hexdigest()

    print(
        json.dumps(
            {
                "ares_revision": PIN,
                "guarded_files_sha256": hashes,
                "result": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
