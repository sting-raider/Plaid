#!/usr/bin/env python3
"""Fail closed if exact pinned software-interrupt ownership contracts drift."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
MUPEN = ROOT / ".refs/mupen64plus-core"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
MUPEN_REV = "ba95bab92a76744753bfe61470823a4937850ab0"

EXPECTED_BLOBS = {
    ARES / "ares/n64/cpu/interpreter-scc.cpp": "c3d119bf4931c4616ae297a4c18b561490207e11",
    GOPHER / "src/device/cop0.rs": "75e48a396b37c1f50d03363a7417e5530cce7923",
    MUPEN / "src/device/r4300/mips_instructions.def": "c3a4acfb4a003d6f6259af3c22464966b7eff15c",
}


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def main() -> int:
    for path, expected in ((ARES, ARES_REV), (GOPHER, GOPHER_REV), (MUPEN, MUPEN_REV)):
        if revision(path) != expected:
            raise SystemExit(f"pin mismatch: {path}")
    for path, expected in EXPECTED_BLOBS.items():
        actual = blob(path)
        if actual != expected:
            raise SystemExit(f"blob mismatch {path}: {actual} != {expected}")

    ares = (ARES / "ares/n64/cpu/interpreter-scc.cpp").read_text()
    gopher = (GOPHER / "src/device/cop0.rs").read_text()
    mupen = (MUPEN / "src/device/r4300/mips_instructions.def").read_text()

    require(ares, "case 13:  //cause", "ares Cause write case")
    require(ares, "scc.cause.interruptPending.bit(0) = data.bit(8);", "ares software IP0 write")
    require(ares, "scc.cause.interruptPending.bit(1) = data.bit(9);", "ares software IP1 write")
    require(ares, "cpu.interruptPoll();", "ares post-write interrupt poll")

    require(gopher, "const COP0_CAUSE_REG_MASK: u64 = 0b00000000000000000000001100000000;", "gopher Cause write mask 0x300")
    require(gopher, "device::memory::masked_write_64(", "gopher masked CP0 write")
    require(gopher, "device::exceptions::check_pending_interrupts(device);", "gopher post-write interrupt check")

    require(mupen, "case CP0_CAUSE_REG:", "mupen Cause write case")
    require(mupen, "cp0_regs[CP0_CAUSE_REG] &= ~(CP0_CAUSE_IP0 | CP0_CAUSE_IP1);", "mupen software pending replacement")
    require(mupen, "cp0_regs[CP0_CAUSE_REG] |= rrt32 & (CP0_CAUSE_IP0 | CP0_CAUSE_IP1);", "mupen writable software IP mask")

    print("PASS: exact pinned ares/Gopher64/Mupen software-interrupt Cause ownership contracts present")
    for path, expected in EXPECTED_BLOBS.items():
        print(f"BLOB {expected} {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
