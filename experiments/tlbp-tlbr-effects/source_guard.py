#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
ARES_PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_PIN = "e96debac941a26ba4961e5145056c0821d3a56f7"


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


assert_clean_pin(ARES, ARES_PIN)
assert_clean_pin(GOPHER, GOPHER_PIN)

scc = (ARES / "ares/n64/cpu/interpreter-scc.cpp").read_text()
decoder = (ARES / "ares/n64/cpu/interpreter.cpp").read_text()
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
assert "scc.index." in probe
assert "scc.tlb = tlb.entry[scc.index.tlbEntry];" in read

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

g_read = function_body(gopher, "pub fn read(device: &mut device::Device, index: u64) {")
g_probe = function_body(gopher, "pub fn probe(device: &mut device::Device) {")
for body in (g_read, g_probe):
    for forbidden in ["tlb_unmap(", "tlb_map(", "tlb_entries[index as usize] ="]:
        assert forbidden not in body, (forbidden, body)

print(
    f"PASS exact pins: ares {ARES_PIN} TLBP/TLBR have no TLB-write/cache-invalidation path; "
    f"Gopher64 {GOPHER_PIN} independently keeps read/probe separate from TLB map/unmap"
)
