#!/usr/bin/env python3
"""Build exact pinned ares and validate VR4300 SCD -> CPU-visible SP storage effects."""
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
SYSTEMTEST = ROOT / ".refs/n64-systemtest"
OUTPUT = ROOT / "target/ares-cpu-scd-sp-sink"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"

build_spec = importlib.util.spec_from_file_location("ares_oracle_build", ROOT / "spikes/003-ares-oracle/run.py")
build_mod = importlib.util.module_from_spec(build_spec); build_spec.loader.exec_module(build_mod)
verify_spec = importlib.util.spec_from_file_location("scd_sp_verify", HERE / "verify.py")
verify_mod = importlib.util.module_from_spec(verify_spec); verify_spec.loader.exec_module(verify_mod)


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    tail = text[start:]
    next_fn = tail.find("\npub fn ", 1)
    return tail if next_fn < 0 else tail[:next_fn]


def source_guard() -> tuple[dict[str, str], dict[str, int | bool]]:
    assert git_head(ARES) == ARES_REV
    paths = {
        "ares_ipu": ARES / "ares/n64/cpu/interpreter-ipu.cpp",
        "ares_memory": ARES / "ares/n64/cpu/memory.cpp",
        "ares_rcp": ARES / "ares/n64/memory/io.hpp",
        "ares_rsp_io": ARES / "ares/n64/rsp/io.cpp",
    }
    texts = {k: p.read_text(encoding="utf-8") for k, p in paths.items()}
    assert "auto CPU::LLD(r64& rt, cr64& rs, s16 imm) -> void {" in texts["ares_ipu"]
    assert "scc.ll = access.paddr >> 4;\n      scc.llbit = 1;" in texts["ares_ipu"]
    assert "auto CPU::SCD(r64& rt, cr64& rs, s16 imm) -> void {\n  if(!context.kernelMode() && context.bits == 32) return exception.reservedInstruction();\n  if(scc.llbit) {\n    rt.u64 = write<Dual>(rs.u64 + imm, rt.u64);\n  } else {\n    rt.u64 = 0;\n  }\n}" in texts["ares_ipu"]
    assert "if (raiseAlignedError && vaddrAlignedError<Size>(vaddr, Dir == Write))" in texts["ares_memory"]
    assert "if constexpr(Size == Dual) {\n      ((T*)this)->writeWord(address, data >> 32, thread);\n    }" in texts["ares_rcp"]
    assert "if(address & 0x1000) return recompiler.invalidate(address & 0xfff), imem.write<Word>(address, data);\n    else                 return dmem.write<Word>(address, data);" in texts["ares_rsp_io"]

    hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()}
    comparison: dict[str, int | bool] = {
        "ares_rcp_dual_word_writes": 1,
        "gopher_scd_data_writes": 0,
        "gopher_scd_clears_llbit": False,
        "systemtest_sp_sd_upper_word_only": False,
        "systemtest_scd_rdram_full64": False,
        "systemtest_direct_scd_sp_oracle": False,
    }
    if GOPHER.exists():
        assert git_head(GOPHER) == GOPHER_REV
        gp = GOPHER / "src/device/cpu_instructions.rs"
        gt = gp.read_text(encoding="utf-8")
        scd = function_body(gt, "pub fn scd(device: &mut device::Device, opcode: u32) {")
        assert "if device.cpu.llbit {" in scd
        assert "device.cpu.llbit = false;" in scd
        assert scd.count("device::memory::data_write(") == 2, scd
        assert "phys_address + 4" in scd
        comparison["gopher_scd_data_writes"] = scd.count("device::memory::data_write(")
        comparison["gopher_scd_clears_llbit"] = True
        hashes["gopher_cpu_instructions"] = hashlib.sha256(gp.read_bytes()).hexdigest()
    if SYSTEMTEST.exists():
        assert git_head(SYSTEMTEST) == SYSTEMTEST_REV
        sp_path = SYSTEMTEST / "src/tests/sp_memory/mod.rs"
        llsc_path = SYSTEMTEST / "src/tests/arithmetic/ll_sc.rs"
        sp = sp_path.read_text(encoding="utf-8")
        llsc = llsc_path.read_text(encoding="utf-8")
        assert "SD is broken: It only writes the upper 32 bit of the value, touching only 4 bytes" in sp
        assert "impl Test for SCD" in llsc
        assert "soft_assert_eq(scd_status, 1, \"SCD success flag\")" in llsc
        assert "soft_assert_eq(memory, 0x1020_3040_5060_7080, \"Memory after SCD\")" in llsc
        # The hardware-facing pin independently covers normal-memory SCD and SP SD,
        # but contains no direct SCD-to-SPMEM case. Keep that absence explicit.
        assert "SCD" not in sp and "scd" not in sp
        comparison["systemtest_sp_sd_upper_word_only"] = True
        comparison["systemtest_scd_rdram_full64"] = True
        hashes["systemtest_sp_memory"] = hashlib.sha256(sp_path.read_bytes()).hexdigest()
        hashes["systemtest_ll_sc"] = hashlib.sha256(llsc_path.read_bytes()).hexdigest()
    return hashes, comparison


def invoke(exe: Path) -> tuple[str, dict, list[str]]:
    proc = subprocess.run([str(exe), "enabled"], text=True, capture_output=True, timeout=30)
    assert proc.returncode == 0, {"returncode": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    lines = proc.stdout.splitlines()
    json_lines = [line for line in lines if line.lstrip().startswith("{")]
    noise = [line for line in lines if not line.lstrip().startswith("{")]
    assert json_lines, {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}
    return proc.stdout, json.loads(json_lines[-1]), noise


def main() -> None:
    hashes, comparison = source_guard()
    baseline = build_mod.build(HERE / "baseline.cpp", OUTPUT / "baseline")
    instrumented = build_mod.build(
        HERE / "driver.cpp", OUTPUT / "instrumented",
        raw_fetch_access=True,
        physical_fetch_access=True,
        sp_backing_access=True,
    )

    baseline_raw, baseline_doc, baseline_noise = invoke(baseline)
    enabled_raw, enabled_doc, enabled_noise = invoke(instrumented)
    repeat_raw, repeat_doc, repeat_noise = invoke(instrumented)

    assert baseline_doc["events"] == []
    assert enabled_raw == repeat_raw, "instrumented traces are not byte-identical"
    assert enabled_noise == repeat_noise
    assert baseline_doc["facts"] == enabled_doc["facts"] == repeat_doc["facts"]
    assert baseline_doc["decoy_ok"] == enabled_doc["decoy_ok"] == repeat_doc["decoy_ok"] is True

    summary = verify_mod.verify(enabled_doc)
    forged = verify_mod.forged_rejections(enabled_doc)
    assert len(forged) == 6

    body = {
        "ares_revision": ARES_REV,
        "gopher_revision": GOPHER_REV if GOPHER.exists() else None,
        "systemtest_revision": SYSTEMTEST_REV if SYSTEMTEST.exists() else None,
        "baseline_facts": baseline_doc["facts"],
        "enabled": enabled_doc,
        "summary": summary,
        "forged_histories_rejected": forged,
        "reference_comparison": comparison,
        "non_json_stdout": {"baseline": baseline_noise, "enabled": enabled_noise},
        "source_sha256": hashes,
    }
    encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_bytes(encoded)
    print(json.dumps({**summary, "forged_histories_rejected": forged, "neutrality": True, "repeat_deterministic": True, "reference_comparison": comparison, "non_json_stdout_lines": {"baseline": len(baseline_noise), "enabled": len(enabled_noise)}}, sort_keys=True))
    print("TRACE_SHA256=" + hashlib.sha256(enabled_raw.encode()).hexdigest())
    print("RESULT_SHA256=" + hashlib.sha256(encoded).hexdigest())
    for key in sorted(hashes): print(f"SOURCE_{key.upper()}_SHA256={hashes[key]}")
    print("PASS: successful SCD reaches one measured SP Word sink in pinned ares; failed/faulting SCD does not, same-value success remains a writer generation, Gopher64 structurally disagrees, and n64-systemtest provides only adjacent SCD-RDRAM/SP-SD hardware evidence")


if __name__ == "__main__":
    main()
