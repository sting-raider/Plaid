"""Guard the exact pinned ares source contracts used by the TLB fetch spike."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"


def require(path, snippets):
    text = (REF / path).read_text()
    for snippet in snippets:
        assert snippet in text, (path, snippet)


def main():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    require("ares/n64/cpu/tlb.cpp", [
        "if(!entry.globals && entry.addressSpaceID != self.scc.tlb.addressSpaceID) return nothing;",
        "if(!entry.valid[lo]) {",
        "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
        "return PhysAccess{true, entry.cacheAlgorithm[lo] != 2, physicalAddress, vaddr};",
    ])
    require("ares/n64/cpu/memory.cpp", [
        "case Context::Segment::Mapped:",
        "if constexpr(Dir == Read)  if(auto access = tlb.load (vaddr, !raiseExceptions)) return access;",
        "if(access.cache) return icache.fetch(access.vaddr, paddr, cpu);",
        "return busRead<Word>(paddr);",
        "if(context.littleEndian()) paddr = reverseEndianPaddr<Word>(paddr);",
    ])
    require("ares/n64/cpu/interpreter-scc.cpp", [
        "tlb.entry[scc.index.tlbEntry] = scc.tlb;",
        "tlb.entry[scc.index.tlbEntry].synchronize();",
    ])
    require("ares/n64/rdram/rdram.hpp", [
        "return Memory::Writable::read<Size>(address);",
    ])
    print("PASS source guard: exact pinned TLB/CPU/RDRAM contracts present")


if __name__ == "__main__":
    main()
