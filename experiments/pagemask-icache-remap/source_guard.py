#!/usr/bin/env python3
"""Guard exact reference contracts composed by the large-PageMask cache experiment."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"


def guard_repo(path: Path, rev: str) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    assert head == rev, (path, head, rev)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=path, check=True)


def require(path: Path, snippets: list[str]) -> str:
    text = path.read_text()
    for snippet in snippets:
        assert snippet in text, (path, snippet)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    guard_repo(ARES, ARES_REV)
    guard_repo(GOPHER, GOPHER_REV)
    guard_repo(SYSTEMTEST, SYSTEMTEST_REV)

    tlb_sha = require(ARES / "ares/n64/cpu/tlb.cpp", [
        "bool lo = vaddr & entry.addressSelect;",
        "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
        "pageMask = pageMask & (0b101010101010 << 13);",
        "pageMask |= pageMask >> 1;",
        "addressMaskLo = (pageMask | 0x1fff) >> 1;",
        "addressSelect = addressMaskLo + 1;",
    ])
    memory_sha = require(ARES / "ares/n64/cpu/memory.cpp", [
        "case Context::Segment::Mapped:",
        "if constexpr(Dir == Read)  if(auto access = tlb.load (vaddr, !raiseExceptions)) return access;",
        "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);",
    ])
    cache_sha = require(ARES / "ares/n64/cpu/cpu.hpp", [
        "auto line(u64 vaddr) -> Line& { return lines[vaddr >> 5 & 0x1ff]; }",
        "const u32 t = paddr & ~0x0000'0fffu;",
        "cpu.busReadBurst<ICache>(tag | index, words);",
        "u32  tagKey;    // valid bit (bit 0) + tag",
    ])
    gopher_sha = require(GOPHER / "src/device/cache.rs", [
        "let line_index = ((phys_address >> 5) & 0x1FF) as usize;",
        "(device.memory.icache[line_index].tag & 0x1ffffffc) == (phys_address & !0xFFF) as u32",
    ])
    systemtest_sha = require(SYSTEMTEST / "src/tests/tlb/mod.rs", [
        "(0b0000000011 << 13, 0b0000000011 << 13),  // 16k",
        "(0b0000001111 << 13, 0b0000001111 << 13),  // 64k",
    ])

    refs = (ROOT / "refs.lock.toml").read_text()
    for rev in (ARES_REV, GOPHER_REV, SYSTEMTEST_REV):
        assert rev in refs

    print(f"ARES_TLB_SHA256={tlb_sha}")
    print(f"ARES_MEMORY_SHA256={memory_sha}")
    print(f"ARES_CACHE_SHA256={cache_sha}")
    print(f"GOPHER_CACHE_SHA256={gopher_sha}")
    print(f"SYSTEMTEST_TLB_SHA256={systemtest_sha}")
    print("PASS: exact PageMask translation and cache-index/tag contracts guarded; emulator cache-index disagreement preserved")


if __name__ == "__main__":
    main()
