#!/usr/bin/env python3
"""Guard the exact pinned reference-side Watch contracts and omissions."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REFS = {
    "ares": (ROOT / ".refs/ares", "9408cb43d4948fc3ea6e152a307a34348df3fe04"),
    "gopher64": (ROOT / ".refs/gopher64", "e96debac941a26ba4961e5145056c0821d3a56f7"),
    "mupen64plus-core": (ROOT / ".refs/mupen64plus-core", "ba95bab92a76744753bfe61470823a4937850ab0"),
    "n64-systemtest": (ROOT / ".refs/n64-systemtest", "196f5421173220eb2f63a7a99c64795dc0ea0698"),
}


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"missing pinned source contract {label}: {fragment!r}")


def forbid(text: str, fragment: str, label: str) -> None:
    if fragment.lower() in text.lower():
        raise SystemExit(f"unexpected pinned source contract {label}: {fragment!r}")


def grep(path: Path, needle: str) -> str:
    proc = subprocess.run(["git", "grep", "-n", "-i", needle], cwd=path, text=True, stdout=subprocess.PIPE)
    if proc.returncode not in (0, 1):
        raise SystemExit(f"git grep failed in {path}: {proc.returncode}")
    return proc.stdout


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    for name, (path, expected) in REFS.items():
        if revision(path) != expected:
            raise SystemExit(f"{name} pin mismatch")

    ares = REFS["ares"][0]
    ares_cpu = (ares / "ares/n64/cpu/cpu.hpp").read_text()
    ares_scc_path = ares / "ares/n64/cpu/interpreter-scc.cpp"
    ares_scc = ares_scc_path.read_text()
    ares_exc_path = ares / "ares/n64/cpu/exceptions.cpp"
    ares_exc = ares_exc_path.read_text()
    ares_ser_path = ares / "ares/n64/cpu/serialization.cpp"
    ares_ser = ares_ser_path.read_text()

    require(ares_cpu, "struct WatchLo", "ares WatchLo storage")
    require(ares_cpu, "n1  trapOnWrite", "ares WatchLo W bit")
    require(ares_cpu, "n1  trapOnRead", "ares WatchLo R bit")
    require(ares_scc, "case 18:  //watchlo", "ares WatchLo CP0 case")
    require(ares_scc, "scc.watchLo.trapOnWrite               = data.bit(0);", "ares guest MTC0 W write")
    require(ares_scc, "scc.watchLo.trapOnRead                = data.bit(1);", "ares guest MTC0 R write")
    require(ares_scc, "scc.watchLo.physicalAddress.bit(3,31) = data.bit(3,31);", "ares guest MTC0 address write")
    require(ares_ser, "s(scc.watchLo.trapOnWrite);", "ares WatchLo serialization")
    require(ares_ser, "s(scc.watchLo.trapOnRead);", "ares WatchLo serialization")
    forbid(ares_exc, "watch", "ares exception implementation must remain absent at this pin")
    forbid(ares_exc, "trigger(23", "ares Watch ExcCode trigger must remain absent at this pin")

    # Lower-case watchLo should be confined to storage, CP0 access, and save-state
    # code. A memory/load-store trigger would add another path and invalidate the
    # executable disagreement hypothesis.
    ares_watchlo = grep(ares, "watchLo")
    allowed = {
        "ares/n64/cpu/cpu.hpp",
        "ares/n64/cpu/interpreter-scc.cpp",
        "ares/n64/cpu/serialization.cpp",
    }
    seen = {line.split(":", 1)[0] for line in ares_watchlo.splitlines() if line.strip()}
    if not seen or not seen.issubset(allowed):
        raise SystemExit(f"unexpected ares watchLo use sites: {sorted(seen)}")

    gopher = REFS["gopher64"][0]
    gopher_cp0_path = gopher / "src/device/cop0.rs"
    gopher_cp0 = gopher_cp0_path.read_text()
    require(gopher_cp0, "//const COP0_WATCHLO_REG: usize = 18;", "Gopher WatchLo named constant disabled")
    require(gopher_cp0, "//const COP0_WATCHHI_REG: usize = 19;", "Gopher WatchHi named constant disabled")
    require(gopher_cp0, "const COP0_WATCHLO_REG_MASK", "Gopher generic write mask")
    forbid(grep(gopher, "EXCCODE_WATCH"), "EXCCODE_WATCH", "Gopher Watch exception code")
    forbid(grep(gopher, "watch_exception"), "watch_exception", "Gopher Watch exception handler")

    mupen = REFS["mupen64plus-core"][0]
    mupen_cp0_path = mupen / "src/device/r4300/cp0.h"
    mupen_mips_path = mupen / "src/device/r4300/mips_instructions.def"
    mupen_cp0 = mupen_cp0_path.read_text()
    mupen_mips = mupen_mips_path.read_text()
    require(mupen_cp0, "CP0_WATCHLO_REG", "Mupen WatchLo register id")
    require(mupen_cp0, "CP0_WATCHHI_REG", "Mupen WatchHi register id")
    require(mupen_mips, "case CP0_WATCHLO_REG:", "Mupen MTC0 WatchLo case")
    require(mupen_mips, "cp0_regs[CP0_WATCHLO_REG] = rrt32;", "Mupen MTC0 WatchLo storage")
    forbid(grep(mupen, "EXCEPTION_WATCH"), "EXCEPTION_WATCH", "Mupen Watch exception handler")
    forbid(grep(mupen, "watch_exception"), "watch_exception", "Mupen Watch exception handler")

    systemtest = REFS["n64-systemtest"][0]
    systemtest_cp0_path = systemtest / "src/cop0.rs"
    systemtest_cp0 = systemtest_cp0_path.read_text()
    require(systemtest_cp0, "WatchLo = 0x12", "systemtest WatchLo register id")
    require(systemtest_cp0, "WatchHi = 0x13", "systemtest WatchHi register id")
    system_watch = grep(systemtest, "WatchLo")
    system_paths = sorted({line.split(":", 1)[0] for line in system_watch.splitlines() if line.strip()})
    if system_paths != ["src/cop0.rs"]:
        raise SystemExit(f"new/changed n64-systemtest WatchLo coverage requires review: {system_paths}")

    report = {
        "pins": {name: rev for name, (_path, rev) in REFS.items()},
        "sha256": {
            "ares_cpu_hpp": digest(ares / "ares/n64/cpu/cpu.hpp"),
            "ares_interpreter_scc": digest(ares_scc_path),
            "ares_exceptions": digest(ares_exc_path),
            "ares_serialization": digest(ares_ser_path),
            "gopher_cop0": digest(gopher_cp0_path),
            "mupen_cp0_h": digest(mupen_cp0_path),
            "mupen_mips_instructions": digest(mupen_mips_path),
            "systemtest_cop0": digest(systemtest_cp0_path),
        },
        "ares_watchlo_paths": sorted(seen),
        "systemtest_watchlo_paths": system_paths,
        "conclusion": "pinned references expose/store Watch state but no executable Watch trigger/test was found; hardware/manual evidence must remain authoritative for the root obligation",
    }
    out = ROOT / "target/ares-watch-exception-roots/source_guard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("PASS: exact pinned Watch source contracts and omissions guarded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
