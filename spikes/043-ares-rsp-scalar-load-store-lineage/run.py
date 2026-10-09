"""Build pinned ares and validate bounded RSP scalar load -> GPR -> store lineage."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess

from verify import reject_forgeries, verify

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-rsp-scalar-load-store-lineage"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def function_block(source: str, name: str) -> str:
    marker = f"pub fn {name}("
    start = source.index(marker)
    stop = source.find("\npub fn ", start + len(marker))
    return source[start:] if stop < 0 else source[start:stop]


def source_audit() -> dict:
    ares = ROOT / ".refs/ares"
    gopher = ROOT / ".refs/gopher64"
    assert git_head(ares) == ARES_REV
    assert git_head(gopher) == GOPHER_REV
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ares, check=True)
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=gopher, check=True)

    ipu_path = ares / "ares/n64/rsp/interpreter-ipu.cpp"
    header_path = ares / "ares/n64/rsp/rsp.hpp"
    rsp_path = ares / "ares/n64/rsp/rsp.cpp"
    ipu = ipu_path.read_text(encoding="utf-8")
    header = header_path.read_text(encoding="utf-8")
    rsp = rsp_path.read_text(encoding="utf-8")

    guards = [
        "rt.u32 = s8(dmem.read<Byte>(rs.u32 + imm));",
        "rt.u32 = u8(dmem.read<Byte>(rs.u32 + imm));",
        "rt.u32 = s16(dmem.readUnaligned<Half>(rs.u32 + imm));",
        "rt.u32 = u16(dmem.readUnaligned<Half>(rs.u32 + imm));",
        "rt.u32 = dmem.readUnaligned<Word>(rs.u32 + imm);",
        "dmem.write<Byte>(rs.u32 + imm, rt.u32);",
        "dmem.writeUnaligned<Half>(rs.u32 + imm, rt.u32);",
        "dmem.writeUnaligned<Word>(rs.u32 + imm, rt.u32);",
        "rt.u32 = rs.u32 | imm;",
        "rd.u32 = s32(rs.u32 + rt.u32);",
    ]
    for guard in guards:
        assert ipu.count(guard) >= 1, guard
    assert "u16 upper = read<Byte>(address + 0);" in header
    assert "u16 lower = read<Byte>(address + 1);" in header
    assert "u32 upper = readUnaligned<Half>(address + 0);" in header
    assert "u32 lower = readUnaligned<Half>(address + 2);" in header
    assert "data[address & maskByte]" in header
    assert "instructionPrologue(instruction);" in rsp and "interpreterEXECUTE();" in rsp

    gopher_path = gopher / "src/device/rsp_su_instructions.rs"
    gopher_source = gopher_path.read_text(encoding="utf-8")
    gopher_blocks = {name: function_block(gopher_source, name) for name in
                     ("lb", "lbu", "lh", "lhu", "lw", "lwu", "sb", "sh", "sw", "ori", "addu")}
    for name in ("lb", "lbu", "lh", "lhu", "lw", "lwu", "sb", "sh", "sw"):
        assert "device.rsp.mem" in gopher_blocks[name], name
        assert "0xFFF" in gopher_blocks[name], name
    assert "device.rsp.cpu.gpr[rt(opcode) as usize]" in gopher_blocks["ori"]
    # Gopher64 is a source-level corroboration only. We do not promote matching implementation
    # structure into a hardware invariant or claim it was behaviorally executed here.

    return {
        "ares_revision": ARES_REV,
        "ares_interpreter_ipu_sha256": hashlib.sha256(ipu_path.read_bytes()).hexdigest(),
        "ares_rsp_hpp_sha256": hashlib.sha256(header_path.read_bytes()).hexdigest(),
        "ares_rsp_cpp_sha256": hashlib.sha256(rsp_path.read_bytes()).hexdigest(),
        "ares_scalar_load_store_guards": len(guards),
        "gopher64_revision": GOPHER_REV,
        "gopher64_rsp_su_sha256": hashlib.sha256(gopher_path.read_bytes()).hexdigest(),
        "gopher64_source_functions_checked": sorted(gopher_blocks),
        "gopher64_behaviorally_executed": False,
    }


def generate_drivers() -> tuple[Path, Path]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source = (HERE / "driver.cpp").read_text(encoding="utf-8")
    baseline = OUTPUT / "baseline.cpp"
    sensor = OUTPUT / "sensor.cpp"
    baseline.write_text("#define PLAID_SENSOR 0\n" + source, encoding="utf-8", newline="\n")
    sensor.write_text("#define PLAID_SENSOR 1\n" + source, encoding="utf-8", newline="\n")
    return baseline, sensor


def execute(exe: Path, *, disabled: bool = False) -> dict:
    env = dict(os.environ)
    if disabled:
        env["PLAID_RSP_DISABLE"] = "1"
    else:
        env.pop("PLAID_RSP_DISABLE", None)
    raw = subprocess.check_output([str(exe)], text=True, env=env, timeout=45)
    rows = [json.loads(line) for line in raw.splitlines() if line.startswith("{")]
    assert len(rows) == 2, raw
    return {"machine": rows[0], "history": rows[1]}


def main() -> None:
    if os.name == "nt":
        path = subprocess.check_output(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", Path(__file__).resolve().as_posix()],
            text=True,
        ).strip()
        subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "python3", path], check=True)
        return

    audit = source_audit()
    builder = load_module("plaid_ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    baseline_source, sensor_source = generate_drivers()
    extras = (HERE / "driver.cpp", HERE / "verify.py", Path(__file__))
    baseline_exe = builder.build(
        baseline_source,
        OUTPUT / "baseline-build",
        extra_sources=extras,
        rsp_dmem_access=False,
    )
    sensor_exe = builder.build(
        sensor_source,
        OUTPUT / "sensor-build",
        extra_sources=extras,
        rsp_dmem_access=True,
    )

    runs = {
        "baseline": execute(baseline_exe),
        "disabled": execute(sensor_exe, disabled=True),
        "instrumented": execute(sensor_exe),
        "repeat": execute(sensor_exe),
    }

    baseline_machine = runs["baseline"]["machine"]
    assert all(run["machine"] == baseline_machine for run in runs.values())
    assert runs["baseline"]["history"]["events"] == []
    assert runs["disabled"]["history"]["events"] == []
    assert runs["instrumented"] == runs["repeat"]

    summary = verify(runs["instrumented"]["history"], baseline_machine)
    summary.update(
        source_audit=audit,
        observer_neutral_machine_projection=True,
        disabled_neutral_machine_projection=True,
        repeat_deterministic=True,
        forgeries_rejected=reject_forgeries(runs["instrumented"]["history"], baseline_machine),
    )
    assert summary["forgeries_rejected"] == 8

    result_path = OUTPUT / "results.json"
    result_path.write_text(
        json.dumps({"summary": summary, "runs": runs}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    result_hash = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(json.dumps({k: v for k, v in summary.items() if k != "edges"}, sort_keys=True))
    print("EDGE_SUMMARY=" + json.dumps(summary["edges"], sort_keys=True))
    print(f"RESULT_SHA256={result_hash}")
    print("PASS exact-pin RSP scalar load/GPR/store generation replay and adversarial cuts")


if __name__ == "__main__":
    main()
