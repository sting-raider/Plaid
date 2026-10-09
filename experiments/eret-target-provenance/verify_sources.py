#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PINS = {
    "plaid": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "gopher64": "e96debac941a26ba4961e5145056c0821d3a56f7",
    "mupen64plus-core": "ba95bab92a76744753bfe61470823a4937850ab0",
    "n64-systemtest": "196f5421173220eb2f63a7a99c64795dc0ea0698",
}


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing source guard {label}: {needle!r}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plaid", type=Path, required=True)
    ap.add_argument("--ares", type=Path, required=True)
    ap.add_argument("--gopher64", type=Path, required=True)
    ap.add_argument("--mupen", type=Path, required=True)
    ap.add_argument("--systemtest", type=Path, required=True)
    args = ap.parse_args()
    roots = {
        "plaid": args.plaid,
        "ares": args.ares,
        "gopher64": args.gopher64,
        "mupen64plus-core": args.mupen,
        "n64-systemtest": args.systemtest,
    }
    heads = {name: git_head(root) for name, root in roots.items()}
    for name, expected in PINS.items():
        if heads[name] != expected:
            raise AssertionError(f"{name} head {heads[name]} != pinned {expected}")

    ares = read(args.ares / "ares/n64/cpu/interpreter-scc.cpp")
    require(ares, "case 14:  //exception program counter\n    scc.epc = data;", "ares EPC writable")
    require(ares, "case 30:  //error exception program counter\n    scc.epcError = data;", "ares ErrorEPC writable")
    require(ares, "pipeline.setPc(scc.epcError);", "ares ERL ERET source")
    require(ares, "pipeline.setPc(scc.epc);", "ares EXL ERET source")

    gopher = read(args.gopher64 / "src/device/cop0.rs")
    require(gopher, "u64::MAX, // EPC", "gopher EPC write mask")
    require(gopher, "u64::MAX, // ErrorPC", "gopher ErrorEPC write mask")
    require(gopher, "device.cpu.pc = device.cpu.cop0.regs[COP0_ERROREPC_REG];", "gopher ERL ERET source")
    require(gopher, "device.cpu.pc = device.cpu.cop0.regs[COP0_EPC_REG];", "gopher EXL ERET source")

    mupen = read(args.mupen / "src/device/r4300/mips_instructions.def")
    require(mupen, "case CP0_EPC_REG:\n        cp0_regs[CP0_EPC_REG] = rrt32;", "mupen EPC writable")
    require(mupen, "case CP0_ERROREPC_REG:\n        cp0_regs[CP0_ERROREPC_REG] = rrt32;", "mupen ErrorEPC writable")
    require(mupen, "generic_jump_to(r4300, cp0_regs[CP0_EPC_REG]);", "mupen EPC ERET source")
    require(mupen, "cp0_regs[CP0_STATUS_REG] & CP0_STATUS_ERL", "mupen ERL selector")
    require(mupen, 'DebugMessage(M64MSG_ERROR, "error in ERET");', "mupen ERL stop disagreement")

    systemtest = read(args.systemtest / "src/tests/privilege/mod.rs")
    require(systemtest, '"mtc0 {entry}, $14",', "systemtest programs EPC")
    require(systemtest, '"eret",', "systemtest executes ERET")
    require(systemtest, "entry = in(reg) entry as u32", "systemtest variable target")

    plaid = read(args.plaid / "crates/plaid-core/src/discovery.rs")
    require(plaid, 'matches!(i.opcode_name(), "syscall" | "break" | "eret")', "Plaid fail-closed ERET")

    checked = {
        "schema": "plaid.eret-target-source-guards.v1",
        "pins": heads,
        "guards": {
            "ares": 4,
            "gopher64": 4,
            "mupen64plus-core": 5,
            "n64-systemtest": 3,
            "plaid": 1,
        },
        "result": "PASS",
    }
    canonical = json.dumps(checked, sort_keys=True, separators=(",", ":")).encode()
    checked["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    print(json.dumps(checked, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
