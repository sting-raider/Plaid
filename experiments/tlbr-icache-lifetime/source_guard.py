#!/usr/bin/env python3
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
MUPEN = ROOT / ".refs/mupen64plus-core"
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
ARES_PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_PIN = "e96debac941a26ba4961e5145056c0821d3a56f7"
MUPEN_PIN = "ba95bab92a76744753bfe61470823a4937850ab0"
SYSTEMTEST_PIN = "196f5421173220eb2f63a7a99c64795dc0ea0698"


def assert_clean_pin(path: Path, pin: str) -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    assert head == pin, (path, head, pin)
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=path, check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=path, check=True)


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    tail = text[start:]
    end = tail.index("\n}\n") + 3
    return tail[:end]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for path, pin in [
    (ARES, ARES_PIN),
    (GOPHER, GOPHER_PIN),
    (MUPEN, MUPEN_PIN),
    (SYSTEMTEST, SYSTEMTEST_PIN),
]:
    assert_clean_pin(path, pin)

scc_path = ARES / "ares/n64/cpu/interpreter-scc.cpp"
decoder_path = ARES / "ares/n64/cpu/interpreter.cpp"
tlb_path = ARES / "ares/n64/cpu/tlb.cpp"
cpu_path = ARES / "ares/n64/cpu/cpu.hpp"
scc = scc_path.read_text()
decoder = decoder_path.read_text()
tlb_cpp = tlb_path.read_text()
cpu_hpp = cpu_path.read_text()

for needle in [
    "auto CPU::TLBR() -> void {",
    "if(scc.index.tlbEntry >= TLB::Entries) return;",
    "scc.tlb = tlb.entry[scc.index.tlbEntry];",
    "auto CPU::TLBP() -> void {",
    "scc.index.probeFailure = 1;",
    "scc.index.probeFailure = 0;",
]:
    assert needle in scc, needle
assert "op(0x01, TLBR);" in decoder
assert "op(0x08, TLBP);" in decoder

read_body = function_body(scc, "auto CPU::TLBR() -> void {")
probe_body = function_body(scc, "auto CPU::TLBP() -> void {")
for forbidden in [
    "devirtualizeCache = {}",
    "tlb.entry[scc.index.tlbEntry] = scc.tlb",
    "tlb.entry[index] = scc.tlb",
    "debugger.tlbWrite(",
    "tlbCache = {}",
    "icache",
]:
    assert forbidden not in read_body, (forbidden, read_body)
for forbidden in ["scc.tlb =", "icache", "devirtualizeCache = {}", "tlbCache = {}"]:
    assert forbidden not in probe_body, (forbidden, probe_body)

asid_guard = "if(!entry.globals && entry.addressSpaceID != self.scc.tlb.addressSpaceID) return nothing;"
assert tlb_cpp.count(asid_guard) == 2, tlb_cpp.count(asid_guard)
for needle in [
    "physicalAddress = entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo);",
    "return PhysAccess{true, entry.cacheAlgorithm[lo] != 2, physicalAddress, vaddr};",
]:
    assert needle in tlb_cpp, needle
for needle in [
    "auto line(u64 vaddr) -> Line& { return lines[vaddr >> 5 & 0x1ff]; }",
    "const u32 t = paddr & ~0x0000'0fffu;",
    "return valid() && (tagKey & ~1u) == t;",
    "cpu.busReadBurst<ICache>(tag | index, words);",
]:
    assert needle in cpu_hpp, needle

# Preserve the known reference disagreement: pinned Gopher64 indexes I-cache by
# physical address, unlike the exact ares implementation exercised here.
gopher_cache_path = GOPHER / "src/device/cache.rs"
gopher_cache = gopher_cache_path.read_text()
for needle in [
    "let line_index = ((phys_address >> 5) & 0x1FF) as usize;",
    "(device.memory.icache[line_index].tag & 0x1ffffffc) == (phys_address & !0xFFF) as u32",
]:
    assert needle in gopher_cache, needle

# Preserve the separate translation-model disagreement already found by the
# TLBR worker. Mupen's inspected legacy fast LUT has no active-ASID predicate.
mupen_tlb_path = MUPEN / "src/device/r4300/tlb.c"
mupen_tlb = mupen_tlb_path.read_text()
translate = function_body(mupen_tlb, "uint32_t virtual_to_physical_address(struct r4300_core* r4300, uint32_t address, int w)")
assert "tlb->LUT_r[addr]" in translate
assert "tlb->LUT_w[addr]" in translate
assert "asid" not in translate.lower(), translate

# Hardware-oriented system-test source explicitly expects ASID-dependent use.
systemtest_path = SYSTEMTEST / "src/tests/tlb/mod.rs"
systemtest = systemtest_path.read_text()
for needle in [
    "pub struct TLBUseTestReadMatchViaASID {}",
    "unsafe { cop0::set_entry_hi(1); }",
    "// Set a different ASID to make sure it doesn't match",
]:
    assert needle in systemtest, needle

print("ARES_REV=" + ARES_PIN)
print("ARES_SCC_SHA256=" + sha(scc_path))
print("ARES_TLB_SHA256=" + sha(tlb_path))
print("ARES_CPU_HPP_SHA256=" + sha(cpu_path))
print("GOPHER_REV=" + GOPHER_PIN)
print("GOPHER_CACHE_SHA256=" + sha(gopher_cache_path))
print("MUPEN_REV=" + MUPEN_PIN)
print("MUPEN_TLB_SHA256=" + sha(mupen_tlb_path))
print("SYSTEMTEST_REV=" + SYSTEMTEST_PIN)
print("SYSTEMTEST_TLB_SHA256=" + sha(systemtest_path))
print("PASS: TLBR writes staged EntryHi context without installed-entry/cache invalidation; ares cache residency is separately physical-tagged and reference disagreements remain explicit")
