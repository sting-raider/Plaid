#!/usr/bin/env python3
"""Build and execute the exact-pinned ares ADD.S exception matrix."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "target" / "ares-fpu-nan-exceptions"
ARES_PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
MUPEN_PIN = "ba95bab92a76744753bfe61470823a4937850ab0"
GOPHER_PIN = "e96debac941a26ba4961e5145056c0821d3a56f7"
SENTINEL = 0xA5A5A5A5DEADBEEF

CASES = [
    "finite",
    "mips_snan_masked",
    "mips_snan_enabled",
    "mips_qnan",
    "subnormal",
]

EXPECTED = {
    "finite": {
        "dest_after": 0x0000000040400000,
        "fcsr": 0x00000000,
        "exception": 0,
    },
    # Legacy-MIPS sNaN encoding: fraction bit 22 = 1. With Invalid disabled,
    # ares records cause+sticky flag, completes the add, canonicalizes NaN,
    # and writes the destination.
    "mips_snan_masked": {
        "dest_after": 0x000000007FBFFFFF,
        "fcsr": 0x00010040,
        "exception": 0,
    },
    # The same raw operand with Invalid enabled raises FPE before destination
    # writeback. The enable and cause bits remain visible; sticky flag is clear.
    "mips_snan_enabled": {
        "dest_after": SENTINEL,
        "fcsr": 0x00010800,
        "exception": 15,
    },
    # Legacy-MIPS qNaN encoding: fraction bit 22 = 0. Pinned ares classifies
    # this as Unimplemented Operation and always raises FPE.
    "mips_qnan": {
        "dest_after": SENTINEL,
        "fcsr": 0x00020000,
        "exception": 15,
    },
    "subnormal": {
        "dest_after": SENTINEL,
        "fcsr": 0x00020000,
        "exception": 15,
    },
}


def git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def require_pin(path: Path, expected: str, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"missing {label} checkout at {path}")
    actual = git_head(path)
    if actual != expected:
        raise SystemExit(f"{label} pin mismatch: expected {expected}, got {actual}")


def source_guards() -> dict[str, str]:
    ares = ROOT / ".refs" / "ares"
    require_pin(ares, ARES_PIN, "ares")
    text = (ares / "ares/n64/cpu/interpreter-fpu.cpp").read_text()

    markers = [
        "auto snan(f32 f) -> bool",
        "return f32repr(f).bit(22);",
        "if((cl1 == FP_NAN && !snan(f1)) || (cl2 == FP_NAN && !snan(f2)))",
        "if(cl1 == FP_SUBNORMAL || cl2 == FP_SUBNORMAL)",
        "if((cl1 == FP_NAN && snan(f1)) || (cl2 == FP_NAN && snan(f2)))",
        "auto CPU::FADD_S(u8 fd, u8 fs, u8 ft) -> void",
        "FD(f32) = ffd;",
    ]
    for marker in markers:
        if marker not in text:
            raise AssertionError(f"ares source guard missing: {marker}")

    qnan_i = text.index(markers[2])
    subnormal_i = text.index(markers[3], qnan_i)
    snan_i = text.index(markers[4], subnormal_i)
    if not qnan_i < subnormal_i < snan_i:
        raise AssertionError("ares input classification order changed")

    # Independent references are deliberately guards for disagreement, not
    # promoted to oracles. Their pinned source currently lacks the ares split.
    mupen = ROOT / ".refs" / "mupen64plus-core"
    if mupen.exists():
        require_pin(mupen, MUPEN_PIN, "Mupen64Plus")
        mtext = (mupen / "src/device/r4300/fpu.h").read_text()
        for marker in (
            "case FP_SUBNORMAL: // TODO",
            "case FP_NAN:",
            "(*fcr31) |= FCR31_CAUSE_INVALIDOP_BIT;",
            "return 0; // TODO: exceptions",
        ):
            if marker not in mtext:
                raise AssertionError(f"Mupen source guard missing: {marker}")

    gopher = ROOT / ".refs" / "gopher64"
    if gopher.exists():
        require_pin(gopher, GOPHER_PIN, "Gopher64")
        gtext = (gopher / "src/device/fpu_instructions.rs").read_text()
        start = gtext.index("pub fn add_s(")
        end = gtext.index("pub fn sub_s(", start)
        add_s = gtext[start:end]
        if "fs + ft" not in add_s or "fcr31" in add_s:
            raise AssertionError("Gopher64 ADD.S source guard changed")

    return {
        "ares": ARES_PIN,
        "mupen64plus": MUPEN_PIN if mupen.exists() else "not-checked-out",
        "gopher64": GOPHER_PIN if gopher.exists() else "not-checked-out",
    }


def load_builder():
    path = ROOT / "spikes" / "003-ares-oracle" / "run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle_build", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build


def run_case(exe: Path, case: str) -> dict:
    raw = subprocess.check_output([str(exe), case], text=True).strip()
    row = json.loads(raw)
    if row["case"] != case:
        raise AssertionError((case, row))
    if row["opcode"] != 0x46041180:
        raise AssertionError(f"unexpected opcode: {row['opcode']:#x}")
    if row["dest_before"] != SENTINEL:
        raise AssertionError(f"sentinel was not installed for {case}")
    for key, value in EXPECTED[case].items():
        if row[key] != value:
            raise AssertionError(
                f"{case}: {key} expected {value:#x}, got {row[key]:#x}; row={row}"
            )
    if row["exception"] == 15 and row["epc"] != 0xFFFFFFFFA0000000:
        raise AssertionError(f"{case}: FPE EPC mismatch: {row['epc']:#x}")
    return row


def main() -> int:
    pins = source_guards()
    build = load_builder()
    OUT.mkdir(parents=True, exist_ok=True)
    exe = Path(build(HERE / "driver.cpp", OUT))

    first = [run_case(exe, case) for case in CASES]
    second = [run_case(exe, case) for case in CASES]
    if first != second:
        raise AssertionError("repeat run changed exact observation matrix")

    payload = {
        "plaid_base": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "pins": pins,
        "cases": first,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    payload["sha256"] = digest
    out_file = OUT / "results.json"
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"RESULT_SHA256={digest}")
    print(f"RESULT_FILE={out_file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
