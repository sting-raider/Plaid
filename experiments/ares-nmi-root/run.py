#!/usr/bin/env python3
"""Build exact pinned ares and exercise the external-NMI entry path."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "target/ares-nmi-root"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
GOPHER_REV = "e96debac941a26ba4961e5145056c0821d3a56f7"
SYSTEMTEST_REV = "196f5421173220eb2f63a7a99c64795dc0ea0698"
ROOT_PC = 0xFFFFFFFFBFC00000
ENTRY_PC = 0xFFFFFFFFA0000104
EPC_SENTINEL = 0x1111222233334444


def oracle_helper():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_guards(ref: Path) -> dict[str, str]:
    paths = {
        "exceptions": ref / "ares/n64/cpu/exceptions.cpp",
        "cpu": ref / "ares/n64/cpu/cpu.cpp",
        "header": ref / "ares/n64/cpu/cpu.hpp",
        "pif_hle": ref / "ares/n64/pif/hle.cpp",
    }
    text = {name: path.read_text() for name, path in paths.items()}
    assert "self.scc.status.softReset = 0;" in text["exceptions"]
    assert "self.scc.status.errorLevel = 1;" in text["exceptions"]
    assert "self.scc.epcError = self.ipu.pc;" in text["exceptions"]
    assert "self.pipeline.setPc(0xffff'ffff'bfc0'0000);" in text["exceptions"]
    assert "if (scc.nmiPending)" in text["cpu"]
    assert "exception.nmi();" in text["cpu"]
    # No clearing assignment exists in the CPU instruction/NMI implementation itself.
    assert "scc.nmiPending = 0" not in text["cpu"]
    assert "n1 nmiPending;" in text["header"]
    assert "cpu.scc.nmiPending = 1;" in text["pif_hle"]
    return {name: sha256(path) for name, path in paths.items()}


def cases():
    # Full state cross-product for a single pending NMI. BEV/EXL/ERL/SR are all
    # adversarial inputs because a normal exception entry depends on some of them.
    for bev in (0, 1):
        for exl in (0, 1):
            for erl in (0, 1):
                for sr in (0, 1):
                    for delay in (0, 1):
                        yield (bev, exl, erl, sr, delay, 1)
    # Persistent-pending adversary: ares' CPU path does not consume the latch.
    yield (0, 0, 0, 1, 0, 2)
    yield (1, 1, 1, 0, 1, 2)


def check(case, state):
    bev, exl, erl, sr, delay, repeat = case
    assert [state[k] for k in ("bev_in", "exl_in", "erl_in", "sr_in", "delay_in", "repeat")] == list(case)
    assert state["first_pc"] == ROOT_PC
    assert state["first_errorepc"] == ENTRY_PC
    assert state["first_pending"] == 1
    assert state["pc"] == ROOT_PC
    assert state["errorepc"] == (ENTRY_PC if repeat == 1 else ROOT_PC)
    assert state["epc"] == EPC_SENTINEL
    assert state["bev"] == 1
    assert state["exl"] == exl  # NMI does not rewrite EXL in this pin.
    assert state["erl"] == 1
    assert state["sr"] == 0     # Exact ares behavior; independent refs disagree.
    assert state["ts"] == 0
    assert state["pending"] == 1
    assert state["pipeline_delay"] == 0


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares; fetch the exact pin first")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if revision != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {revision} != {ARES_REV}")
    subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ref, check=True)

    hashes = source_guards(ref)
    oracle = oracle_helper()
    exe = oracle.build(HERE / "driver.cpp", OUTPUT)

    rows = []
    for case in cases():
        args = [str(exe), *map(str, case)]
        first = subprocess.check_output(args, text=True, timeout=15)
        second = subprocess.check_output(args, text=True, timeout=15)
        assert first == second, (case, first, second)
        state = json.loads(first)
        check(case, state)
        rows.append(state)
        print(json.dumps(state, sort_keys=True, separators=(",", ":")))

    body = {
        "plaid_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "ares_revision": ARES_REV,
        "gopher64_source_revision": GOPHER_REV,
        "n64_systemtest_source_revision": SYSTEMTEST_REV,
        "source_sha256": hashes,
        "case_count": len(rows),
        "results": rows,
        "observations": {
            "fixed_root": ROOT_PC,
            "pending_consumed_by_cpu_path": False,
            "ares_soft_reset_after_nmi": 0,
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = OUTPUT / "results.json"
    result.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    print(f"RESULT_SHA256 {sha256(result)}")
    print(f"PASS: {len(rows)} exact-pin NMI cases repeated byte-identically and matched the guarded ares transition")
    return 0


if __name__ == "__main__":
    sys.exit(main())
