"""Build exact pinned ares and disprove RSP-store -> IMEM aliasing."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ARES = ROOT / ".refs/ares"
GOPHER = ROOT / ".refs/gopher64"
N64TEST = ROOT / ".refs/n64-systemtest"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
N64TEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
DRIVER = Path(__file__).with_name("driver.cpp")
OUTPUT = ROOT / "target/ares-rsp-self-store-spike"
VECTOR_STORES = {"SBV","SDV","SFV","SHV","SLV","SPV","SQV","SRV","SSV","STV","SUV","SWV"}
VECTOR_BASE_1000_STORES = VECTOR_STORES - {"STV"}


def load_builder():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def function_body(source: str, marker: str) -> str:
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{": depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError(marker)


def source_audit():
    pins = ((ARES, ARES_REV), (GOPHER, GOPHER_REV), (N64TEST, N64TEST_REV))
    for checkout, revision in pins:
        assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=checkout,text=True).strip() == revision
        subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=checkout,check=True)

    ipu = (ARES / "ares/n64/rsp/interpreter-ipu.cpp").read_text()
    vpu = (ARES / "ares/n64/rsp/interpreter-vpu.cpp").read_text()
    rsp_hpp = (ARES / "ares/n64/rsp/rsp.hpp").read_text()
    rsp_cpp = (ARES / "ares/n64/rsp/rsp.cpp").read_text()
    writable = (ARES / "ares/n64/memory/msb/writable.hpp").read_text()

    scalar = {
        "SB": "dmem.write<Byte>(rs.u32 + imm, rt.u32);",
        "SH": "dmem.writeUnaligned<Half>(rs.u32 + imm, rt.u32);",
        "SW": "dmem.writeUnaligned<Word>(rs.u32 + imm, rt.u32);",
    }
    for name, sink in scalar.items():
        body = function_body(ipu, f"auto RSP::{name}(")
        assert sink in body and "imem" not in body, (name, body)

    discovered = set(re.findall(r"auto RSP::(S(?:BV|DV|FV|HV|LV|PV|QV|RV|SV|TV|UV|WV))\(", vpu))
    assert discovered == VECTOR_STORES, (sorted(discovered), sorted(VECTOR_STORES))
    for name in sorted(VECTOR_STORES):
        body = function_body(vpu, f"auto RSP::{name}(")
        assert "dmem.write<Byte>" in body and "imem" not in body, (name, body)
    srv = function_body(vpu, "auto RSP::SRV(")
    assert "auto end = start + (address & 15);" in srv
    assert "address &= ~15;" in srv

    assert "} dmem{*this};\n  Memory::Writable imem;" in rsp_hpp
    assert "dmem.allocate(4_KiB);\n  imem.allocate(4_KiB);" in rsp_cpp
    assert "u32 instruction = imem.read<Word>(ipu.pc);" in rsp_cpp
    assert "data[address & maskByte]" in rsp_hpp
    assert "write<Byte>(address + 0" in rsp_hpp and "write<Byte>(address + 1" in rsp_hpp
    assert "u32 mask = bit::round(size) - 1;" in writable and "maskByte = mask & ~0;" in writable

    # Independent pinned Gopher64: one 8 KiB SP image, but every RSP-originated
    # store masks to the lower 4 KiB. The SP interface separately identifies
    # bit 0x1000 as IMEM for CPU/DMA writes.
    su = (GOPHER / "src/device/rsp_su_instructions.rs").read_text()
    interface = (GOPHER / "src/device/rsp_interface.rs").read_text()
    assert "pub mem: [u8; 0x2000]" in interface
    assert "if masked_address & 0x1000 != 0" in interface and "// imem being updated" in interface
    for name in ("sb","sh","sw"):
        body = function_body(su, f"pub fn {name}(")
        assert "device.rsp.mem" in body and "0xFFF" in body, (name, body)
    for name in sorted(n.lower() for n in VECTOR_STORES):
        body = function_body(su, f"pub fn {name}(")
        assert "device.rsp.mem" in body and "0xFFF" in body, (name, body)

    # Pinned n64-systemtest is a hardware-oriented corpus. Its scalar SW test
    # explicitly expects 0xffe to wrap to 0x000 in DMEM. Its shared vector
    # helper compares addresses after &0xfff; 11/12 store-family tests use a
    # literal 0x1000 adversarial base. STV uses a separate exhaustive-ish
    # offset/register matrix, so do not pretend its source has the same shape.
    sw_test = (N64TEST / "src/tests/rsp/op_sw.rs").read_text()
    vector_test = (N64TEST / "src/tests/rsp/op_vector_stores.rs").read_text()
    assembler = (N64TEST / "src/rsp/rsp_assembler.rs").read_text()
    assert "When writing to 0xFFF, 0xFFE or 0xFFD, there is wrap-around to 0x0" in sw_test
    assert "assembler.write_sw(GPR::S2, GPR::R0, 0x7FFE);" in sw_test
    assert "wrapped around to start of DMEM" in sw_test
    assert "let address = (base_offset + i * 0x10 - 0x10) & 0xFFF;" in vector_test
    for name in sorted(VECTOR_STORES):
        marker = f"pub struct {name} {{}}"
        assert marker in vector_test
        start = vector_test.index(marker)
        next_struct = vector_test.find("pub struct ", start + len(marker))
        stop = len(vector_test) if next_struct < 0 else next_struct
        block = vector_test[start:stop]
        if name in VECTOR_BASE_1000_STORES:
            assert "0x1000" in block, (name, block[:500])
        else:
            assert "assembler.write_stv" in block and "TEST_OFFSETS" in block, block[:500]
    assert "SWC2 = 58" in assembler
    assert "B = 0, S = 1, L = 2, D = 3, Q = 4, R = 5, P = 6, U = 7, H = 8, F = 9, W = 10, T = 11" in assembler
    wc2 = function_body(assembler, "fn write_wc2(")
    for field in ("((imm7 as u32) & 0b111_1111)", "((element as u32) << 7)", "((wc2op as u32) << 11)", "((vt as u32) << 16)", "((base as u32) << 21)", "((op as u32) << 26)"):
        assert field in wc2, field

    return {
        "ares_scalar_stores": sorted(scalar),
        "ares_vector_stores": sorted(VECTOR_STORES),
        "ares_dmem_bytes": 4096,
        "ares_imem_bytes": 4096,
        "ares_srv_aligned_zero_length": True,
        "gopher_rsp_mem_bytes": 8192,
        "gopher_store_mask": "0x0fff",
        "gopher_imem_selector": "0x1000",
        "n64_systemtest_scalar_wrap_expectation": "SW@0xffe -> DMEM 0xffe,0xfff,0x000,0x001",
        "n64_systemtest_vector_base_1000_families": sorted(VECTOR_BASE_1000_STORES),
        "n64_systemtest_stv_shape": "separate TEST_OFFSETS/register/element matrix",
    }


def main():
    audit = source_audit()
    if OUTPUT.exists(): shutil.rmtree(OUTPUT)
    builder = load_builder()
    exe = builder.build(DRIVER, OUTPUT / "build")
    raw1 = subprocess.check_output([str(exe)], text=True, timeout=30)
    raw2 = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert raw1 == raw2
    observed = json.loads(raw1)
    assert observed["probe_count"] == 29
    expected = {"SB", "SH", "SW-wrap", "SW-bit12", "SRV@0x100f"}
    for name in VECTOR_STORES:
        expected.add(name + "@0x1000")
        expected.add(name + "@0x0fff")
    assert {p["name"] for p in observed["probes"]} == expected
    by_name = {p["name"]: p for p in observed["probes"]}
    assert by_name["SRV@0x1000"]["changed_dmem"] == 0
    assert by_name["SRV@0x100f"]["changed_dmem"] > 0
    assert all(p["changed_dmem"] > 0 for p in observed["probes"] if p["name"] != "SRV@0x1000")

    result = {
        "ares_revision": ARES_REV,
        "gopher64_revision": GOPHER_REV,
        "n64_systemtest_revision": N64TEST_REV,
        "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        "source_audit": audit,
        "execution": observed,
        "repeat_deterministic": raw1 == raw2,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    print("PASS: decoded pinned-ares RSP scalar/vector stores never mutate IMEM; all nonzero-length adversaries mutate DMEM only, aligned SRV is correctly zero-length, and Gopher64/n64-systemtest independently corroborate the DMEM-only address domain")


if __name__ == "__main__":
    main()
