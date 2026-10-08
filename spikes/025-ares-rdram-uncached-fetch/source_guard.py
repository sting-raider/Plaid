#!/usr/bin/env python3
"""Assert the exact pinned ares source shape required by the uncached-fetch witness proposal."""
from pathlib import Path
import argparse
import subprocess

PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

REQUIRED = {
    "ares/n64/cpu/memory.cpp": [
        "return bus.read<Size>(address, *this, RBusDevice::VR4300_UNCACHED);",
        "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);\n  return busRead<Word>(paddr);",
        "if(access.cache) return dcache.read<Size>(access.vaddr, paddr);\n  return busRead<Size>(paddr);",
    ],
    "ares/n64/memory/bus.hpp": [
        "if(address <= 0x03ff'ffff) return mi.readRdram<Size>(address, device, thread);",
    ],
    "ares/n64/mi/bus.hpp": [
        "if(unlikely(io.ebusTestMode) && device == RBusDevice::VR4300_UNCACHED)\n      return rdram.ram.ebusRead<Size>(address);\n    return rdram.ram.read<Size>(address, device);",
    ],
    "ares/n64/rdram/rdram.hpp": [
        "if(unlikely(!self.mapIdentity)) {",
        "if(address >= size) return 0;",
        "return Memory::Writable::read<Size>(address);",
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ares", type=Path)
    args = ap.parse_args()
    root = args.ares.resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    assert head == PIN, (head, PIN)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=root, check=True)
    for rel, snippets in REQUIRED.items():
        text = (root / rel).read_text()
        if rel == "ares/n64/rdram/rdram.hpp":
            # Mapping/bounds checks also occur in other access methods. Guard
            # the ordinary read body instead of demanding file-wide uniqueness.
            begin = "    auto read(u32 address, RBusDevice device) -> u64 {"
            end = "    auto ebusRead(u32 address) -> u64 {"
            assert text.count(begin) == text.count(end) == 1
            text = text[text.index(begin):text.index(end)]
        for snippet in snippets:
            assert text.count(snippet) == 1, (rel, snippet, text.count(snippet))
    print(f"PASS: exact uncached-fetch/RDRAM source contract present at {PIN}")

if __name__ == "__main__":
    main()
