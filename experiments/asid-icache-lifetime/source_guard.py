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


def check(path: Path, needles: list[str]) -> tuple[str, str]:
    text = path.read_text()
    for needle in needles:
        assert needle in text, (path, needle)
    return text, hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    guard_repo(ARES, ARES_REV)
    guard_repo(GOPHER, GOPHER_REV)

    scc, scc_sha = check(ARES / "ares/n64/cpu/interpreter-scc.cpp", [
        "auto CPU::MTC0(cr64& rt, u8 rd) -> void {",
        "setControlRegister(rd, rt.u64);",
        "case 10:  //entryhi",
        "scc.tlb.addressSpaceID            = data.bit( 0, 7);",
        "scc.tlb.virtualAddress.bit(13,39) = data.bit(13,39);",
        "scc.tlb.region                    = data.bit(62,63);",
    ])
    entryhi = scc[scc.index("case 10:  //entryhi"):scc.index("case 11:  //compare")]
    assert "tlb.entry[" not in entryhi
    assert "icache" not in entryhi

    _, tlb_sha = check(ARES / "ares/n64/cpu/tlb.cpp", [
        "if(!entry.globals && entry.addressSpaceID != self.scc.tlb.addressSpaceID) return nothing;",
        "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
        "return PhysAccess{true, entry.cacheAlgorithm[lo] != 2, physicalAddress, vaddr};",
    ])
    _, cpu_sha = check(ARES / "ares/n64/cpu/cpu.hpp", [
        "auto line(u64 vaddr) -> Line& { return lines[vaddr >> 5 & 0x1ff]; }",
        "const u32 t = paddr & ~0x0000'0fffu;",
        "return valid() && (tagKey & ~1u) == t;",
        "cpu.busReadBurst<ICache>(tag | index, words);",
    ])
    _, gopher_sha = check(GOPHER / "src/device/cache.rs", [
        "let line_index = ((phys_address >> 5) & 0x1FF) as usize;",
        "(device.memory.icache[line_index].tag & 0x1ffffffc) == (phys_address & !0xFFF) as u32",
    ])

    print("ARES_REV=" + ARES_REV)
    print("ARES_INTERPRETER_SCC_SHA256=" + scc_sha)
    print("ARES_TLB_SHA256=" + tlb_sha)
    print("ARES_CPU_HPP_SHA256=" + cpu_sha)
    print("GOPHER_REV=" + GOPHER_REV)
    print("GOPHER_CACHE_RS_SHA256=" + gopher_sha)
    print("PASS: EntryHi ASID matching and I-cache resident lifetime are distinct guarded source contracts")


if __name__ == "__main__":
    main()
