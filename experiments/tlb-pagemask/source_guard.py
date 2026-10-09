#!/usr/bin/env python3
"""Guard exact pinned ares and n64-systemtest PageMask contracts."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def require(root: Path, path: str, snippets: list[str]) -> None:
    text = (root / path).read_text()
    for snippet in snippets:
        assert snippet in text, (path, snippet)


def main() -> None:
    assert revision(ARES) == ARES_REV
    assert revision(SYSTEMTEST) == SYSTEMTEST_REV
    for checkout in (ARES, SYSTEMTEST):
        subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=checkout, check=True)

    require(ARES, "ares/n64/cpu/tlb.cpp", [
        "bool lo = vaddr & entry.addressSelect;",
        "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
        "pageMask = pageMask & (0b101010101010 << 13);",
        "pageMask |= pageMask >> 1;",
        "addressMaskHi = ~(n40)(pageMask | 0x1fff);",
        "addressMaskLo = (pageMask | 0x1fff) >> 1;",
        "addressSelect = addressMaskLo + 1;",
    ])
    require(ARES, "ares/n64/cpu/memory.cpp", [
        "case Context::Segment::Mapped:",
        "if constexpr(Dir == Read)  if(auto access = tlb.load (vaddr, !raiseExceptions)) return access;",
        "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);",
        "return busRead<Word>(paddr);",
    ])
    require(SYSTEMTEST, "src/tests/tlb/mod.rs", [
        "(0b0000000011 << 13, 0b0000000011 << 13),  // 16k",
        "(0b0000001111 << 13, 0b0000001111 << 13),  // 64k",
        "(0b00000000111 << 13, 0b00000000011 << 13),",
        "(0b00000000010 << 13, 0b00000000011 << 13),",
    ])
    print("PASS source guard: exact pinned ares PageMask geometry and n64-systemtest mask cases present")


if __name__ == "__main__":
    main()
