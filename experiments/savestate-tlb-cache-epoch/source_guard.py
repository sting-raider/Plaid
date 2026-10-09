#!/usr/bin/env python3
"""Guard the exact pinned ares serialization semantics used by this experiment."""
from pathlib import Path
import hashlib
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ARES, text=True).strip() == PIN
subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ARES, check=True)

cpu_path = ARES / "ares/n64/cpu/serialization.cpp"
system_path = ARES / "ares/n64/system/serialization.cpp"
cpu = cpu_path.read_text()
system = system_path.read_text()

cpu_needles = [
    "for(auto& line : icache.lines) {",
    "s(line.tagKey);",
    "s(line.index);",
    "s(line.words);",
    "for(auto& e : tlb.entry) {",
    "s(e.physicalAddress);",
    "s(e.virtualAddress);",
    "s(e.addressSpaceID);",
    "s(scc.tlb.virtualAddress);",
    "s(scc.tlb.addressSpaceID);",
]
for needle in cpu_needles:
    assert needle in cpu, needle

system_needles = [
    "if(synchronize) power(/* reset = */ false);",
    "serialize(s, synchronize);",
    "s(rdram);",
    "s(cpu);",
]
for needle in system_needles:
    assert needle in system, needle

# Deserialization is field installation through the bidirectional serializer;
# it must not replay guest mapping writes or completed I-cache fills here.
assert "TLBWI(" not in cpu
assert "TLBWR(" not in cpu
assert ".fill(" not in cpu
assert system.index("s(rdram);") < system.index("s(cpu);")

print("ares_pin=" + PIN)
print("cpu_serialization_sha256=" + hashlib.sha256(cpu_path.read_bytes()).hexdigest())
print("system_serialization_sha256=" + hashlib.sha256(system_path.read_bytes()).hexdigest())
print("PASS: synchronized restore directly serializes I-cache, installed TLB entries, and EntryHi/ASID state without replaying TLBWI/TLBWR/fill operations")
