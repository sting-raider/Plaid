#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == PIN
subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)

scc_path = ARES / "ares/n64/cpu/interpreter-scc.cpp"
tlb_path = ARES / "ares/n64/cpu/tlb.cpp"
scc = scc_path.read_text()
tlb = tlb_path.read_text()
for needle in [
    "auto CPU::MTC0(cr64& rt, u8 rd) -> void {",
    "setControlRegister(rd, rt.u64);",
    "case 10:  //entryhi",
    "scc.tlb.addressSpaceID            = data.bit( 0, 7);",
    "scc.tlb.virtualAddress.bit(13,39) = data.bit(13,39);",
    "scc.tlb.region                    = data.bit(62,63);",
    "devirtualizeCache = {};\n  tlb.entry[scc.index.tlbEntry] = scc.tlb;",
]:
    assert needle in scc, needle
for needle in [
    "if(!entry.globals && entry.addressSpaceID != self.scc.tlb.addressSpaceID) return nothing;",
    "if((vaddr & entry.addressMaskHi) != entry.virtualAddress) return nothing;",
    "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
    "return PhysAccess{true, entry.cacheAlgorithm[lo] != 2, physicalAddress, vaddr};",
]:
    assert needle in tlb, needle

entryhi_case = scc[scc.index("case 10:  //entryhi"):scc.index("case 11:  //compare")]
assert "devirtualizeCache" not in entryhi_case

print("ares_pin=" + PIN)
print("interpreter_scc_sha256=" + hashlib.sha256(scc_path.read_bytes()).hexdigest())
print("tlb_sha256=" + hashlib.sha256(tlb_path.read_bytes()).hexdigest())
print("PASS: exact pinned ares MTC0 EntryHi mutates live ASID staging; TLB match consumes that ASID")
