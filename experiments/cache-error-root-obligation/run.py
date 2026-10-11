#!/usr/bin/env python3
"""Execute exact-pinned ares CacheErr guest behavior and guard independent source evidence."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/cache-error-root-obligation"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
EPC_SENTINEL = 0x123456789ABCDEF0
ERROR_EPC_SENTINEL = 0x0FEDCBA987654321


def rev(path: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_guard() -> dict:
    ares = ROOT / ".refs/ares"
    systemtest = ROOT / ".refs/n64-systemtest"
    gopher = ROOT / ".refs/gopher64"
    assert rev(ares) == ARES_REV
    assert rev(systemtest) == SYSTEMTEST_REV
    assert rev(gopher) == GOPHER_REV

    exceptions = ares / "ares/n64/cpu/exceptions.cpp"
    scc = ares / "ares/n64/cpu/interpreter-scc.cpp"
    systemtest_cop0 = systemtest / "src/tests/cop0/mod.rs"
    gopher_cop0 = gopher / "src/device/cop0.rs"
    et = exceptions.read_text()
    st = scc.read_text()
    nt = systemtest_cop0.read_text()
    gt = gopher_cop0.read_text()

    assert "auto CPU::Exception::nmi()" in et
    assert "cacheError" not in et and "CacheError" not in et
    assert "case 27:  //cache error (unused)" in st
    assert "scc.cacheError.unused = 0" in st
    assert 'soft_assert_eq(readback, 0, "CacheError (27) was written as 0xFFFFFFFF")' in nt
    assert "//const COP0_CACHEERR_REG: usize = 27;" in gt

    return {
        "ares_exceptions_sha256": sha(exceptions),
        "ares_interpreter_scc_sha256": sha(scc),
        "n64_systemtest_cop0_tests_sha256": sha(systemtest_cop0),
        "gopher64_cop0_sha256": sha(gopher_cop0),
    }


def check_state(state: dict) -> None:
    assert state["cacheerr"] == 0, state
    assert state["readback"] == 0, state
    assert state["exl"] == 0 and state["erl"] == 0, state
    assert state["cause"] == 13, state
    assert state["epc"] == EPC_SENTINEL, state
    assert state["error_epc"] == ERROR_EPC_SENTINEL, state
    forbidden = {
        0xFFFFFFFF80000000, 0xFFFFFFFF80000080, 0xFFFFFFFF80000100, 0xFFFFFFFF80000180,
        0xFFFFFFFFA0000100, 0xFFFFFFFFBFC00000, 0xFFFFFFFFBFC00300, 0xFFFFFFFFBFC00380,
    }
    assert state["pc"] not in forbidden, state


def main() -> int:
    guards = source_guard()
    oracle = load_oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)
    states = []
    for bev in (0, 1):
        args = [str(exe), str(bev)]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (first, second)
        state = json.loads(first)
        check_state(state)
        states.append(state)
        print(json.dumps(state, sort_keys=True, separators=(",", ":")))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "ares_revision": ARES_REV,
        "n64_systemtest_revision": SYSTEMTEST_REV,
        "gopher64_revision": GOPHER_REV,
        "source_guards": guards,
        "states": states,
    }
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("results_sha256=" + sha(result))
    print("PASS: exact pinned ares guest MTC0/MFC0 CacheErr remains zero and enters no exception root; independent pinned source guards match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
