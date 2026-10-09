#!/usr/bin/env python3
"""Guard exact pinned reference source used by the IMEM reverse-DMA experiment."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(text: str, needle: str, label: str, count: int = 1) -> None:
    actual = text.count(needle)
    assert actual == count, f"{label}: expected {count} exact source witness(es), got {actual}"


def check() -> dict:
    assert head(ARES) == ARES_REV
    assert head(GOPHER) == GOPHER_REV

    dma_path = ARES / "ares/n64/rsp/dma.cpp"
    io_path = ARES / "ares/n64/rsp/io.cpp"
    rsp_path = ARES / "ares/n64/rsp/rsp.hpp"
    gopher_path = GOPHER / "src/device/rsp_interface.rs"
    dma = dma_path.read_text(encoding="utf-8")
    io = io_path.read_text(encoding="utf-8")
    rsp = rsp_path.read_text(encoding="utf-8")
    gopher = gopher_path.read_text(encoding="utf-8")

    require(dma, "u64 data = imem.read<Dual>(dma.current.pbusAddress);", "ares IMEM source read")
    require(dma, "rdram.ram.write<Dual>(dma.current.dramAddress, data, RBusDevice::SP_DMA);", "ares completed Dual sink")
    # One increment sits in each transfer direction. The write-DMA branch is
    # guarded above by the unique IMEM read + Dual RDRAM sink pair.
    require(dma, "dma.current.pbusAddress += 8;", "ares source/destination advance", 2)
    require(io, "dma.pending.pbusAddress.bit(3,11) = data.bit( 3,11);", "ares PBUS offset latch")
    require(io, "dma.pending.pbusRegion            = data.bit(12);", "ares PBUS bank latch")
    require(rsp, "n1  pbusRegion;", "ares region field")
    require(rsp, "n12 pbusAddress;", "ares wrapped offset field")

    # Independent source comparison: Gopher64 likewise separates the bank bit
    # from the wrapping 12-bit offset for the duration of one DMA descriptor.
    require(gopher, "let offset = dma.memaddr & 0x1000;", "gopher bank latch")
    require(gopher, "let mut mem_addr = dma.memaddr & 0xff8;", "gopher source offset")
    # The same stable-bank expression appears once in each DMA direction.
    require(gopher, "(offset + (mem_addr & 0xFFF)) as usize", "gopher stable-bank addressing", 2)

    result = {
        "ares_revision": ARES_REV,
        "gopher_revision": GOPHER_REV,
        "sha256": {
            "ares_dma": digest(dma_path),
            "ares_io": digest(io_path),
            "ares_rsp": digest(rsp_path),
            "gopher_rsp_interface": digest(gopher_path),
        },
        "semantic_guard": "bank identity is descriptor state separate from wrapped source offset",
    }
    return result


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
