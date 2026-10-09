#!/usr/bin/env python3
"""Exact-pin source guard for the ERL/ErrorEPC ERET disagreement."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path

PINS = {
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
    "mupen": "ba95bab92a76744753bfe61470823a4937850ab0",
    "systemtest": "196f5421173220eb2f63a7a99c64795dc0ea0698",
}

def sha(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rev(path: Path): return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()

def require(text: str, needle: str, label: str):
    if text.count(needle) != 1:
        raise AssertionError(f"{label}: expected exactly one anchor, got {text.count(needle)}: {needle!r}")

def main():
    ap = argparse.ArgumentParser()
    for name in PINS: ap.add_argument(f"--{name}", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ns = ap.parse_args()
    roots = {name: getattr(ns, name) for name in PINS}
    for name, pin in PINS.items():
        got = rev(roots[name])
        if got != pin: raise SystemExit(f"{name} pin mismatch: {got} != {pin}")
        subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=roots[name], check=True)

    ares = roots["ares"] / "ares/n64/cpu/interpreter-scc.cpp"
    at = ares.read_text()
    require(at, "case 30:  //error exception program counter\n    scc.epcError = data;", "ares ErrorEPC write")
    require(at, "if(scc.status.errorLevel) {\n    pipeline.setPc(scc.epcError);\n    scc.status.errorLevel = 0;", "ares ERET ERL")

    gopher = roots["gopher64"] / "src/device/cop0.rs"
    gt = gopher.read_text()
    require(gt, "u64::MAX, // ErrorPC", "gopher ErrorEPC full write mask")
    require(gt, "if device.cpu.cop0.regs[COP0_STATUS_REG] & COP0_STATUS_ERL != 0 {\n        device.cpu.pc = device.cpu.cop0.regs[COP0_ERROREPC_REG];\n        device.cpu.cop0.regs[COP0_STATUS_REG] &= !COP0_STATUS_ERL", "gopher ERET ERL")

    mupen = roots["mupen"] / "src/device/r4300/mips_instructions.def"
    mt = mupen.read_text()
    require(mt, "case CP0_ERROREPC_REG:\n        cp0_regs[CP0_ERROREPC_REG] = rrt32;", "mupen ErrorEPC write")
    require(mt, "if (cp0_regs[CP0_STATUS_REG] & CP0_STATUS_ERL)\n    {\n        DebugMessage(M64MSG_ERROR, \"error in ERET\");\n        *r4300_stop(r4300)=1;", "mupen disputed ERET ERL")

    st = roots["systemtest"] / "src/tests/cop0/mod.rs"
    stt = st.read_text()
    marker = "pub struct ErrorEPCNoMasking {}"
    require(stt, marker, "systemtest ErrorEPC test")
    start = stt.index(marker)
    next_struct = stt.find("\npub struct ", start + len(marker))
    if next_struct < 0:
        raise AssertionError("systemtest ErrorEPC block terminator not found")
    error_block = stt[start:next_struct]
    require(error_block, "unsafe { cop0::set_errorepc(value); }", "systemtest ErrorEPC write")
    require(error_block, "let expected = value;", "systemtest exact readback expectation")
    require(error_block, "let readback = cop0::errorepc();", "systemtest ErrorEPC readback")

    result = {
        "pins": PINS,
        "sha256": {
            "ares_interpreter_scc": sha(ares),
            "gopher_cop0": sha(gopher),
            "mupen_instructions": sha(mupen),
            "systemtest_cop0_tests": sha(st),
        },
        "facts": {
            "ares": "ERL selects ErrorEPC and guest writes ErrorEPC",
            "gopher64": "ERL selects ErrorEPC and ErrorEPC has full 64-bit write mask",
            "mupen": "guest writes ErrorEPC but pure interpreter stops on ERL ERET",
            "n64_systemtest": "hardware-facing ErrorEPCNoMasking expects written 64-bit values to read back exactly",
        },
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if ns.out:
        ns.out.parent.mkdir(parents=True, exist_ok=True)
        ns.out.write_text(payload)
    return 0

if __name__ == "__main__": raise SystemExit(main())
