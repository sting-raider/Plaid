#!/usr/bin/env python3
"""Build exact pinned ares and execute an ERL/ErrorEPC ERET matrix."""
from __future__ import annotations
import hashlib, importlib.util, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/eret-errorepc-hardware"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
TARGET_ERROR = 0xFFFFFFFFA0000100
TARGET_EPC = 0xFFFFFFFFA0000200
DECOY_ERROR = 0xFFFFFFFFA0000180


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard_ares(ref: Path) -> dict[str, str]:
    path = ref / "ares/n64/cpu/interpreter-scc.cpp"
    text = path.read_text()
    anchors = [
        "case 30:  //error exception program counter\n    scc.epcError = data;",
        "if(scc.status.errorLevel) {\n    pipeline.setPc(scc.epcError);\n    scc.status.errorLevel = 0;",
        "pipeline.setPc(scc.epc);\n    scc.status.exceptionLevel = 0;",
        "scc.llbit = 0;",
    ]
    for anchor in anchors:
        assert text.count(anchor) == 1, anchor
    return {"interpreter_scc": sha256(path)}


def cases():
    return [
        ("erl_guest_new", 1, 1, 1, DECOY_ERROR, TARGET_ERROR, TARGET_EPC, TARGET_ERROR, 0x1111),
        ("erl_guest_same", 1, 0, 1, TARGET_ERROR, TARGET_ERROR, TARGET_EPC, TARGET_ERROR, 0x1111),
        ("erl_capture_control", 1, 1, 0, TARGET_ERROR, DECOY_ERROR, TARGET_EPC, TARGET_ERROR, 0x1111),
        ("erl_exl0_guest", 1, 0, 1, DECOY_ERROR, TARGET_ERROR, TARGET_EPC, TARGET_ERROR, 0x1111),
        ("erl0_epc_control", 0, 1, 1, DECOY_ERROR, TARGET_ERROR, TARGET_EPC, TARGET_EPC, 0x2222),
        ("erl0_exl0_control", 0, 0, 1, DECOY_ERROR, TARGET_ERROR, TARGET_EPC, TARGET_EPC, 0x2222),
    ]


def check(case, state):
    name, erl, exl, guest, initial_error, write_value, epc, expected_pc, marker = case
    assert state["name"] == name
    assert state["erl_in"] == erl and state["exl_in"] == exl and state["guest_write"] == guest
    assert state["initial_errorepc"] == initial_error
    assert state["write_value"] == write_value and state["epc"] == epc
    assert state["errorepc_after"] == (write_value if guest else initial_error)
    assert state["pc_after_eret"] == expected_pc
    assert state["erl_after"] == 0
    assert state["exl_after"] == (exl if erl else 0)
    assert state["s1_after_target"] == marker
    assert state["pc_final"] == expected_pc + 4
    assert state["target_error_constant"] == TARGET_ERROR
    assert state["target_epc_constant"] == TARGET_EPC


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares")
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if rev != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {rev}")
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ref, check=True)
    hashes = guard_ares(ref)
    exe = oracle_helper().build(HERE / "driver.cpp", OUTPUT)
    rows = []
    for case in cases():
        args = [str(exe), case[0], str(case[1]), str(case[2]), str(case[3]), hex(case[4]), hex(case[5]), hex(case[6])]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case[0], first, second)
        row = json.loads(first)
        check(case, row)
        rows.append(row)
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))
    report = {
        "plaid_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ares_revision": ARES_REV,
        "source_sha256": hashes,
        "case_count": len(rows),
        "results": rows,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / "results.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("RESULT_SHA256", sha256(path))
    print(f"PASS: {len(rows)} exact-pin ERET cases repeated byte-identically")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
