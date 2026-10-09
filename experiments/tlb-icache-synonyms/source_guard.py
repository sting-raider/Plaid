#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def guard_repo(path: Path, rev: str) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    assert head == rev, (path, head, rev)
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=path, check=True)


def check(path: Path, needles: list[str]) -> str:
    text = path.read_text()
    for needle in needles:
        assert text.count(needle) == 1, (path, needle, text.count(needle))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    guard_repo(ARES, ARES_REV)
    guard_repo(GOPHER, GOPHER_REV)
    ares_sha = check(ARES / "ares/n64/cpu/cpu.hpp", [
        "auto line(u64 vaddr) -> Line& { return lines[vaddr >> 5 & 0x1ff]; }",
        "const u32 t = paddr & ~0x0000'0fffu;",
        "cpu.busReadBurst<ICache>(tag | index, words);",
        "u32  tagKey;    // valid bit (bit 0) + tag",
    ])
    gopher_sha = check(GOPHER / "src/device/cache.rs", [
        "let line_index = ((phys_address >> 5) & 0x1FF) as usize;",
        "(device.memory.icache[line_index].tag & 0x1ffffffc) == (phys_address & !0xFFF) as u32",
        "i.index = (pos << 5) as u16 & 0xFE0",
    ])
    print(f"ARES_REV={ARES_REV}")
    print(f"ARES_CPU_HPP_SHA256={ares_sha}")
    print(f"GOPHER_REV={GOPHER_REV}")
    print(f"GOPHER_CACHE_RS_SHA256={gopher_sha}")
    print("PASS: exact pinned I-cache index/tag source contracts guarded")


if __name__ == "__main__":
    main()
