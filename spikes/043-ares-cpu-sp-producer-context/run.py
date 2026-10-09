#!/usr/bin/env python3
"""Build exact pinned ares and verify decoded CPU producer -> SP Word sink contexts."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = ROOT / ".refs/ares"
OUTPUT = ROOT / "target/ares-cpu-sp-producer-context"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"

build_spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
build_mod = importlib.util.module_from_spec(build_spec); build_spec.loader.exec_module(build_mod)
verify_spec = importlib.util.spec_from_file_location("producer_verify", HERE / "verify.py")
verify_mod = importlib.util.module_from_spec(verify_spec); verify_spec.loader.exec_module(verify_mod)


def guard_sources() -> dict[str, str]:
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip() == ARES_REV
    paths = {
        "cpu": REF / "ares/n64/cpu/cpu.cpp",
        "ipu": REF / "ares/n64/cpu/interpreter-ipu.cpp",
        "fpu": REF / "ares/n64/cpu/interpreter-fpu.cpp",
        "rcp": REF / "ares/n64/memory/io.hpp",
        "rsp_io": REF / "ares/n64/rsp/io.cpp",
    }
    text = {k: p.read_text(encoding="utf-8") for k, p in paths.items()}
    assert "instructionPrologue(ipu.pc, *data);\n  decoderEXECUTE(*data);\n  instructionEpilogue<0>();" in text["cpu"]
    assert "auto CPU::SW(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Word>(rs.u64 + imm, rt.u32);\n}" in text["ipu"]
    assert "auto CPU::SB(cr64& rt, cr64& rs, s16 imm) -> void {\n  write<Byte>(rs.u64 + imm, rt.u32);\n}" in text["ipu"]
    assert "auto CPU::SWC1(u8 ft, cr64& rs, s16 imm) -> void {" in text["fpu"]
    assert "write<Word>(rs.u64 + imm, FT(u32));" in text["fpu"]
    assert "case 1: return ((T*)this)->writeWord(address, data << 16, thread);" in text["rcp"]
    assert "if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);" in text["rsp_io"]
    return {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}


def invoke(exe: Path, mode: str) -> tuple[str, dict]:
    raw = subprocess.check_output([str(exe), mode], text=True, timeout=30)
    return raw, json.loads(raw)


def main() -> None:
    hashes = guard_sources()
    exe = build_mod.build(
        HERE / "driver.cpp", OUTPUT,
        raw_fetch_access=True,
        physical_fetch_access=True,
        sp_backing_access=True,
    )
    disabled_raw, disabled = invoke(exe, "disabled")
    enabled_raw, enabled = invoke(exe, "enabled")
    repeat_raw, repeat = invoke(exe, "enabled")
    assert disabled["events"] == []
    assert enabled_raw == repeat_raw, "enabled traces are not byte-identical"
    assert disabled["facts"] == enabled["facts"] == repeat["facts"]
    assert disabled["outcomes"] == enabled["outcomes"] == repeat["outcomes"]
    summary = verify_mod.verify(enabled)

    body = {
        "ares_revision": ARES_REV,
        "disabled_facts": disabled["facts"],
        "enabled": enabled,
        "summary": summary,
        "source_sha256": hashes,
    }
    encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    trace_digest = hashlib.sha256(enabled_raw.encode()).hexdigest()
    print("PASS: decoded CPU SW/SB/SWC1 contexts join actual SP Word sinks")
    print("events=7 attributed=6 out_of_context=1 fault_without_sink=1")
    print("trace_sha256=" + trace_digest)
    print("results_sha256=" + digest)
    for key in sorted(hashes): print(f"source_{key}_sha256={hashes[key]}")


if __name__ == "__main__":
    main()
