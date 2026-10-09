#!/usr/bin/env python3
from pathlib import Path
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
    subprocess.run(["git", "diff", "--quiet"], cwd=path, check=True)
    subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=path, check=True)


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    tail = text[start:]
    end = tail.index("\n}\n") + 3
    return tail[:end]


for path, pin in [
    (ARES, ARES_PIN), (GOPHER, GOPHER_PIN), (MUPEN, MUPEN_PIN), (SYSTEMTEST, SYSTEMTEST_PIN)
]:
    assert_clean_pin(path, pin)

# ares: TLBP/TLBR do not replace mapping entries, but TLBR copies an entry into
# staged SCC state, and mapped loads/stores consult that staged EntryHi ASID.
scc = (ARES / "ares/n64/cpu/interpreter-scc.cpp").read_text()
decoder = (ARES / "ares/n64/cpu/interpreter.cpp").read_text()
tlb_cpp = (ARES / "ares/n64/cpu/tlb.cpp").read_text()
cpu_hpp = (ARES / "ares/n64/cpu/cpu.hpp").read_text()
for needle in [
    "auto CPU::TLBP() -> void {",
    "scc.index.tlbEntry = 0;  //technically undefined",
    "scc.index.probeFailure = 1;",
    "scc.index.tlbEntry = index;",
    "scc.index.probeFailure = 0;",
    "auto CPU::TLBR() -> void {",
    "if(scc.index.tlbEntry >= TLB::Entries) return;",
    "scc.tlb = tlb.entry[scc.index.tlbEntry];",
]:
    assert needle in scc, needle
assert "op(0x01, TLBR);" in decoder
assert "op(0x08, TLBP);" in decoder
assert "struct TlbCache" in cpu_hpp
asid_guard = "if(!entry.globals && entry.addressSpaceID != self.scc.tlb.addressSpaceID) return nothing;"
assert tlb_cpp.count(asid_guard) == 2, tlb_cpp.count(asid_guard)

probe = function_body(scc, "auto CPU::TLBP() -> void {")
read = function_body(scc, "auto CPU::TLBR() -> void {")
for body in (probe, read):
    for forbidden in [
        "devirtualizeCache = {}",
        "tlb.entry[index] = scc.tlb",
        "tlb.entry[scc.index.tlbEntry] = scc.tlb",
        ".synchronize();",
        "debugger.tlbWrite(",
        "tlbCache = {}",
    ]:
        assert forbidden not in body, (forbidden, body)

# Gopher64 independently keeps TLB read/probe separate from write/map paths.
gopher = (GOPHER / "src/device/tlb.rs").read_text()
for needle in [
    "pub fn read(device: &mut device::Device, index: u64) {",
    "if index > 31 {",
    "device.cpu.cop0.regs[device::cop0::COP0_PAGEMASK_REG] =",
    "pub fn probe(device: &mut device::Device) {",
    "device.cpu.cop0.regs[device::cop0::COP0_INDEX_REG] = 0x80000000; // set probe failure",
    "device.cpu.cop0.regs[device::cop0::COP0_INDEX_REG] = pos as u64;",
]:
    assert needle in gopher, needle
for body in [
    function_body(gopher, "pub fn read(device: &mut device::Device, index: u64) {"),
    function_body(gopher, "pub fn probe(device: &mut device::Device) {")
]:
    for forbidden in ["tlb_unmap(", "tlb_map(", "tlb_entries[index as usize] ="]:
        assert forbidden not in body, (forbidden, body)

# Mupen's pinned legacy fast LUT translation has no active-ASID predicate. This
# is a real reference-model divergence and prevents treating emulator consensus
# as hardware truth for the TLBR->ASID consequence.
mupen_tlb = (MUPEN / "src/device/r4300/tlb.c").read_text()
mupen_translate = function_body(mupen_tlb, "uint32_t virtual_to_physical_address(struct r4300_core* r4300, uint32_t address, int w)")
assert "tlb->LUT_r[addr]" in mupen_translate
assert "tlb->LUT_w[addr]" in mupen_translate
assert "asid" not in mupen_translate.lower(), mupen_translate

# The pinned hardware-oriented n64-systemtest source explicitly has an ASID
# usage test and sets a matching EntryHi ASID before using a non-global entry.
systemtest = (SYSTEMTEST / "src/tests/tlb/mod.rs").read_text()
for needle in [
    "pub struct TLBUseTestReadMatchViaASID {}",
    'fn name(&self) -> &str { "TLB: Use and test reading, match via ASID" }',
    "// Set a matching ASID - this will make the CPU ignore the global bit",
    "unsafe { cop0::set_entry_hi(1); }",
    "// Set a different ASID to make sure it doesn't match",
]:
    assert needle in systemtest, needle

print(
    "PASS exact pins: ares TLBR copies EntryHi and ares translation consults its ASID; "
    "TLBP/TLBR have no TLB-entry write/cache invalidation path; pinned Mupen LUT lacks "
    "active-ASID filtering while pinned n64-systemtest explicitly tests ASID-dependent use"
)
