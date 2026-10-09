#!/usr/bin/env python3
"""Guard the exact pinned-ares RSP savestate serialization contract."""
from pathlib import Path
import hashlib
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / ".refs/ares"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

with (ROOT / "refs.lock.toml").open("rb") as f:
    refs = tomllib.load(f)
ares_ref = next(repo for repo in refs["repo"] if repo["name"] == "ares")
assert ares_ref["rev"] == PIN
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == PIN

rsp_path = REF / "ares/n64/rsp/serialization.cpp"
sys_path = REF / "ares/n64/system/serialization.cpp"
rsp = rsp_path.read_text()
system = sys_path.read_text()

required_rsp = [
    "s(dmem);",
    "s(imem);",
    "s(pipeline.address);",
    "s(pipeline.instruction);",
    "s(dma.pending);",
    "s(dma.current);",
    "s(dma.busy.read);",
    "s(dma.busy.write);",
    "s(dma.full.read);",
    "s(dma.full.write);",
    "s(dma.clock);",
    "for(auto& r : ipu.r) s(r.u32);",
    "s(ipu.pc);",
    "s(branch.pc);",
    "s(branch.nextpc);",
    "s(branch.state);",
    "s(branch.nstate);",
    "s(originPc);",
    "s(originCpu);",
]
for needle in required_rsp:
    assert rsp.count(needle) == 1, needle
assert "dmaTransferStart" not in rsp
assert "dmaTransferStep" not in rsp
assert "imem.write" not in rsp

required_system = [
    "if(synchronize) power(/* reset = */ false);",
    "serialize(s, synchronize);",
    "s(rdram);",
    "s(cpu);",
    "s(rsp);",
]
for needle in required_system:
    assert system.count(needle) >= 1, needle
assert system.index("s(rdram);") < system.index("s(cpu);") < system.index("s(rsp);")

print("ARES_PIN=" + PIN)
print("RSP_SERIALIZATION_SHA256=" + hashlib.sha256(rsp_path.read_bytes()).hexdigest())
print("SYSTEM_SERIALIZATION_SHA256=" + hashlib.sha256(sys_path.read_bytes()).hexdigest())
print("PASS: synchronized restore directly serializes RSP IMEM/execution/DMA state; no SP-DMA replay appears in RSP serialization")
