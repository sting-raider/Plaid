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
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
DRIVER = Path(__file__).with_name("driver.cpp")
OUTPUT = ROOT / "target/ares-rsp-self-store-spike"
VECTOR_STORES = {"SBV","SDV","SFV","SHV","SLV","SPV","SQV","SRV","SSV","STV","SUV","SWV"}


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
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=ARES,text=True).strip() == ARES_REV
    assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=GOPHER,text=True).strip() == GOPHER_REV
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=ARES,check=True)
    subprocess.run(["git","-c","core.autocrlf=true","diff","--quiet","HEAD"],cwd=GOPHER,check=True)

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

    assert "} dmem{*this};\n  Memory::Writable imem;" in rsp_hpp
    assert "dmem.allocate(4_KiB);\n  imem.allocate(4_KiB);" in rsp_cpp
    assert "u32 instruction = imem.read<Word>(ipu.pc);" in rsp_cpp
    assert "data[address & maskByte]" in rsp_hpp
    assert "write<Byte>(address + 0" in rsp_hpp and "write<Byte>(address + 1" in rsp_hpp
    assert "u32 mask = bit::round(size) - 1;" in writable and "maskByte = mask & ~0;" in writable

    # Independent pinned Gopher64 stores use only the lower 4 KiB of an 8 KiB
    # RSP memory image. Its SP interface explicitly treats bit 0x1000 as IMEM.
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

    return {
        "ares_scalar_stores": sorted(scalar),
        "ares_vector_stores": sorted(VECTOR_STORES),
        "ares_dmem_bytes": 4096,
        "ares_imem_bytes": 4096,
        "gopher_rsp_mem_bytes": 8192,
        "gopher_store_mask": "0x0fff",
        "gopher_imem_selector": "0x1000",
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
    assert observed["probe_count"] == 17
    expected = {
        "SB@0x1000","SH@0x0fff","SW@0x0ffe",
        *VECTOR_STORES,
        "decoded_SH@0x0fff","decoded_SW@0x1000",
    }
    assert {p["name"] for p in observed["probes"]} == expected
    assert all(p["changed_dmem"] > 0 for p in observed["probes"])

    result = {
        "ares_revision": ARES_REV,
        "gopher64_revision": GOPHER_REV,
        "driver_sha256": hashlib.sha256(DRIVER.read_bytes()).hexdigest(),
        "source_audit": audit,
        "execution": observed,
        "repeat_deterministic": raw1 == raw2,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    print("PASS: all pinned ares RSP scalar/vector store families changed DMEM only; boundary/wrap and decoded stores left IMEM byte-identical; pinned Gopher64 independently masks stores to DMEM")


if __name__ == "__main__":
    main()
