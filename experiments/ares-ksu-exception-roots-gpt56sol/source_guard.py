#!/usr/bin/env python3
"""Guard the exact reference sources used by this experiment."""
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"

EXPECTED_BLOBS = {
    ARES / "ares/n64/cpu/context.cpp": "770cfd76a5f45d0a886c352e2c42ed0bb850ecee",
    ARES / "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    ARES / "ares/n64/cpu/exceptions.cpp": "870e7d420f38fbda862cb4c7cb88481155b19251",
    GOPHER / "src/device/memory.rs": "7355a5976228687fdd2d5568f897d6ff5649b7a3",
    GOPHER / "src/device/cop0.rs": "75e48a396b37c1f50d03363a7417e5530cce7923",
    GOPHER / "src/device/exceptions.rs": "629750763f1029347a381fc3f87f1a007e5e25cc",
}


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> int:
    assert git(ARES, "rev-parse", "HEAD") == ARES_REV
    assert git(GOPHER, "rev-parse", "HEAD") == GOPHER_REV
    for path, expected in EXPECTED_BLOBS.items():
        repo = ARES if str(path).startswith(str(ARES)) else GOPHER
        rel = path.relative_to(repo)
        actual = git(repo, "hash-object", str(rel))
        assert actual == expected, (rel, actual, expected)

    memory = (ARES / "ares/n64/cpu/memory.cpp").read_text()
    context = (ARES / "ares/n64/cpu/context.cpp").read_text()
    exc = (ARES / "ares/n64/cpu/exceptions.cpp").read_text()
    gmem = (GOPHER / "src/device/memory.rs").read_text()
    gexc = (GOPHER / "src/device/exceptions.rs").read_text()

    # Guard the semantic seams rather than relying on line numbers.
    assert "if (vaddr >= 0xffff'ffff'8000'0000ull && vaddr <= 0xffff'ffff'83ef'ffffull)" in memory
    assert memory.index("0xffff'ffff'83ef'ffffull") < memory.index("switch(segment(vaddr))")
    assert "case Mode::Supervisor:" in context and "segment[4] = Segment::Unused;" in context
    assert "case Mode::User:" in context and "bits = self.scc.status.userExtendedAddressing ? 64 : 32;" in context
    assert "if(self.context.bits == 64) vectorOffset = 0x0080;" in exc

    # Gopher64 at this exact pin translates KSEG by address bits and otherwise
    # enters TLB lookup without consulting KSU/UX/SX/KX, and its TLB refill code
    # assigns only 0 or the default 0x180. Do not use unrelated 0x80 literals in
    # the file as a proxy for XTLB support.
    assert "pub fn translate_address" in gmem
    assert "return device::tlb::get_physical_address(device, address, access_type);" in gmem
    tlb_fn = gexc[gexc.index("pub fn tlb_miss_exception"):gexc.index("pub fn reset_event")]
    assert "let mut vector_offset = 0x180;" in tlb_fn
    assert "vector_offset = 0;" in tlb_fn
    assert "vector_offset = 0x80" not in tlb_fn and "vector_offset = 0x080" not in tlb_fn

    print("PASS: exact pinned ares/Gopher64 source identities and semantic seams match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
