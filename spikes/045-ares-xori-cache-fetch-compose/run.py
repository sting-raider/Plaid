#!/usr/bin/env python3
"""Build exact pinned ares and execute CPU-transform -> cache -> fetch composition."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OUT = ROOT / "target/ares-xori-cache-fetch-compose"
SOURCE_BLOBS = {
    "ares/n64/cpu/cpu.hpp": "b51000d99e1e8818ad04a8c747a8170b0e98fae8",
    "ares/n64/cpu/dcache.cpp": "4de28e0ad9566d31f47210a997c22fa994785d26",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/cpu/interpreter-ipu.cpp": "938ccbd0af1f127439d9859c1fd6be2bbd5222a3",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2",
}
OLD = 0x24020001
NEW = 0x24020002
SOURCE = NEW ^ 0x00FF


def source_guard():
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == REV
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    for path, expected in SOURCE_BLOBS.items():
        actual = subprocess.check_output(["git", "hash-object", path], cwd=REF, text=True).strip()
        assert actual == expected, (path, actual, expected)

    decoder = (REF / "ares/n64/cpu/interpreter.cpp").read_text(encoding="utf-8")
    ipu = (REF / "ares/n64/cpu/interpreter-ipu.cpp").read_text(encoding="utf-8")
    assert "op(0x0e, XORI, RT, RS, IMMu16);" in decoder
    assert "op(0x23, LW, RT, RS, IMMi16);" in decoder
    assert "op(0x2b, SW, RT, RS, IMMi16);" in decoder
    assert "auto CPU::XORI(r64& rt, cr64& rs, u16 imm) -> void {\n  rt.u64 = rs.u64 ^ imm;\n}" in ipu
    assert "case 0x19: {  //dcache hit write back" in ipu
    assert "case 0x10: {  //icache hit invalidate" in ipu
    assert "line.writeBack();" in ipu and "line.setValid(false);" in ipu


def build():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert builder.REV == REV
    return builder.build(HERE / "driver.cpp", OUT, extra_sources=(HERE / "run.py", HERE / "model.py"))


def verify(facts):
    assert facts["normal_after_store"] == 1
    assert facts["normal_after_writeback"] == 1
    assert facts["normal_final"] == 2
    assert facts["normal_source"] == SOURCE
    assert facts["normal_transform"] == NEW
    assert facts["normal_backing"] == NEW
    assert facts["normal_icache"] == NEW

    # Same-valued foreign backing store cannot be distinguished by bits, but the
    # executable reference proves the chronology can contain that extra writer.
    assert facts["foreign_after_store"] == 1
    assert facts["foreign_after_writeback"] == 1
    assert facts["foreign_final"] == 2
    assert facts["foreign_backing"] == NEW
    assert facts["foreign_icache"] == NEW

    # Refill before writeback captures the old backing generation and remains
    # stale even after backing later changes to the transformed bits.
    assert facts["prefill_after_store"] == 1
    assert facts["prefill_after_writeback"] == 1
    assert facts["prefill_final"] == 1
    assert facts["prefill_backing"] == NEW
    assert facts["prefill_icache"] == OLD

    # XORI zero changes no bits, but the separate replay requires a new causal
    # transform generation between load and cached store.
    assert facts["identity_source"] == NEW
    assert facts["identity_transform"] == NEW
    assert facts["identity_final"] == 2
    assert facts["identity_backing"] == NEW
    assert facts["exception"] == 0


def main():
    source_guard()
    exe = build()
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=45)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=45)
    assert raw1 == raw2, "exact fixture output changed across repeat"
    facts = json.loads(raw1)
    verify(facts)
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evidence.json").write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print("EVIDENCE_SHA256=" + digest)
    print("EVIDENCE_JSON=" + canonical)
    print("PASS: exact CPU XORI transform reaches executable fetch only through the measured cache chronology; stale and same-value-writer adversaries stay distinguishable")


if __name__ == "__main__":
    main()
