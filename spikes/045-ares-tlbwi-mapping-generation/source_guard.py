#!/usr/bin/env python3
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
assert head == PIN, (head, PIN)
subprocess.run(["git", "diff", "--quiet"], cwd=REF, check=True)
subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=REF, check=True)

scc = (REF / "ares/n64/cpu/interpreter-scc.cpp").read_text()
decoder = (REF / "ares/n64/cpu/interpreter.cpp").read_text()

required = [
    "auto CPU::TLBWI() -> void {",
    "if(!context.kernelMode()) {",
    "if(!scc.status.enable.coprocessor0) return exception.coprocessor0();",
    "if(scc.index.tlbEntry >= TLB::Entries) return;",
    "devirtualizeCache = {};",
    "tlb.entry[scc.index.tlbEntry] = scc.tlb;",
    "tlb.entry[scc.index.tlbEntry].synchronize();",
    "debugger.tlbWrite(scc.index.tlbEntry);",
]
for needle in required:
    assert needle in scc, needle
assert "op(0x02, TLBWI);" in decoder

body = scc[scc.index("auto CPU::TLBWI() -> void {"):]
body = body[:body.index("\n}") + 2]
ordered = [
    "if(scc.index.tlbEntry >= TLB::Entries) return;",
    "devirtualizeCache = {};",
    "tlb.entry[scc.index.tlbEntry] = scc.tlb;",
    "tlb.entry[scc.index.tlbEntry].synchronize();",
    "debugger.tlbWrite(scc.index.tlbEntry);",
]
pos = -1
for needle in ordered:
    nxt = body.index(needle)
    assert nxt > pos, (needle, body)
    pos = nxt

print(f"PASS exact ares pin {PIN}: TLBWI index/write/synchronize/debugger ordering guarded")
