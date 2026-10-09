#!/usr/bin/env python3
"""Build exact pinned ares and validate VR4300 SC -> CPU-visible SP storage effects."""
from __future__ import annotations
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
OUTPUT = ROOT / "target/ares-cpu-sc-sp-sink"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"

build_spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
build_mod = importlib.util.module_from_spec(build_spec); build_spec.loader.exec_module(build_mod)
verify_spec = importlib.util.spec_from_file_location("sc_sp_verify", HERE / "verify.py")
verify_mod = importlib.util.module_from_spec(verify_spec); verify_spec.loader.exec_module(verify_mod)


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def source_guard() -> dict[str, str]:
    assert git_head(ARES) == ARES_REV
    paths = {
        "ares_ipu": ARES / "ares/n64/cpu/interpreter-ipu.cpp",
        "ares_rcp": ARES / "ares/n64/memory/io.hpp",
        "ares_rsp_io": ARES / "ares/n64/rsp/io.cpp",
    }
    texts = {k: p.read_text(encoding="utf-8") for k, p in paths.items()}
    assert "auto CPU::LL(r64& rt, cr64& rs, s16 imm) -> void {" in texts["ares_ipu"]
    assert "scc.ll = access.paddr >> 4;\n      scc.llbit = 1;" in texts["ares_ipu"]
    assert "auto CPU::SC(r64& rt, cr64& rs, s16 imm) -> void {\n  if(scc.llbit) {\n    rt.u64 = write<Word>(rs.u64 + imm, rt.u32);\n  } else {\n    rt.u64 = 0;\n  }\n}" in texts["ares_ipu"]
    assert "if constexpr(Size == Word) {\n      ((T*)this)->writeWord(address, data, thread);\n    }" in texts["ares_rcp"]
    assert "if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);\n    else                 return dmem.write<Word>(address, data);" in texts["ares_rsp_io"]

    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    if GOPHER.exists():
        assert git_head(GOPHER) == GOPHER_REV
        gp = GOPHER / "src/device/cpu_instructions.rs"
        gt = gp.read_text(encoding="utf-8")
        start = gt.index("pub fn sc(device: &mut device::Device, opcode: u32) {")
        end = gt.index("pub fn scd(device: &mut device::Device, opcode: u32) {", start)
        sc = gt[start:end]
        assert "if device.cpu.llbit {" in sc
        assert "AccessType::Write" in sc
        assert "data_write" in sc
        hashes["gopher_cpu_instructions"] = hashlib.sha256(gp.read_bytes()).hexdigest()
    return hashes


def invoke(exe: Path) -> tuple[str, dict]:
    raw = subprocess.check_output([str(exe), "enabled"], text=True, timeout=30)
    return raw, json.loads(raw)


def main() -> None:
    hashes = source_guard()
    baseline = build_mod.build(HERE / "baseline.cpp", OUTPUT / "baseline")
    instrumented = build_mod.build(
        HERE / "driver.cpp", OUTPUT / "instrumented",
        raw_fetch_access=True,
        physical_fetch_access=True,
        sp_backing_access=True,
    )

    baseline_raw, baseline_doc = invoke(baseline)
    enabled_raw, enabled_doc = invoke(instrumented)
    repeat_raw, repeat_doc = invoke(instrumented)

    assert baseline_doc["events"] == []
    assert enabled_raw == repeat_raw, "instrumented traces are not byte-identical"
    assert baseline_doc["facts"] == enabled_doc["facts"] == repeat_doc["facts"]
    assert baseline_doc["decoy_ok"] == enabled_doc["decoy_ok"] == repeat_doc["decoy_ok"] is True

    summary = verify_mod.verify(enabled_doc)
    forged = verify_mod.forged_rejections(enabled_doc)
    assert len(forged) == 5

    body = {
        "ares_revision": ARES_REV,
        "gopher_revision": GOPHER_REV if GOPHER.exists() else None,
        "baseline_facts": baseline_doc["facts"],
        "enabled": enabled_doc,
        "summary": summary,
        "forged_histories_rejected": forged,
        "source_sha256": hashes,
    }
    encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    print(json.dumps({**summary, "forged_histories_rejected": forged, "neutrality": True, "repeat_deterministic": True}, sort_keys=True))
    print("TRACE_SHA256=" + hashlib.sha256(enabled_raw.encode()).hexdigest())
    print("RESULT_SHA256=" + hashlib.sha256(encoded).hexdigest())
    for key in sorted(hashes): print(f"SOURCE_{key.upper()}_SHA256={hashes[key]}")
    print("PASS: successful SC reaches one measured SP Word sink; failed/faulting SC does not, and same-value success remains a writer generation")


if __name__ == "__main__":
    main()
