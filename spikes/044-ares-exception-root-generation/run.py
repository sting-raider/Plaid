#!/usr/bin/env python3
"""Build exact pinned ares and execute the exception-root generation fixture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REF = ROOT / ".refs/ares"
OUT = ROOT / "target/ares-exception-root-generation"
REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
SOURCE_BLOBS = {
    "ares/n64/cpu/cpu.hpp": "b51000d99e1e8818ad04a8c747a8170b0e98fae8",
    "ares/n64/cpu/exceptions.cpp": "870e7d420f38fbda862cb4c7cb88481155b19251",
    "ares/n64/cpu/dcache.cpp": "4de28e0ad9566d31f47210a997c22fa994785d26",
    "ares/n64/cpu/memory.cpp": "f362ef67ab41ccf57330bbedd6f614e07a61dd17",
    "ares/n64/cpu/interpreter-ipu.cpp": "938ccbd0af1f127439d9859c1fd6be2bbd5222a3",
    "ares/n64/rdram/rdram.hpp": "c718ec2e9b2a78610353562cbc81dd973b278ee2",
}


def source_guard() -> None:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REF, text=True).strip()
    assert revision == REV, (revision, REV)
    subprocess.run(["git", "-c", "core.autocrlf=true", "diff", "--quiet", "HEAD"], cwd=REF, check=True)
    for path, expected in SOURCE_BLOBS.items():
        actual = subprocess.check_output(["git", "hash-object", path], cwd=REF, text=True).strip()
        assert actual == expected, (path, actual, expected)


def build():
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load ares builder")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build(HERE / "driver.cpp", OUT)


def main() -> None:
    source_guard()
    exe = build()
    first = subprocess.check_output([str(exe)], text=True, timeout=30)
    second = subprocess.check_output([str(exe)], text=True, timeout=30)
    assert first == second, (first, second)
    facts = json.loads(first)
    vector = 0xFFFFFFFF80000180
    assert facts["vector_va"] == vector
    assert facts["stale_root_pc"] == vector
    assert facts["refilled_root_pc"] == vector
    assert facts["warm_handler"] == 1
    assert facts["stale_handler"] == 1
    assert facts["refilled_handler"] == 2
    assert facts["backing_word"] == 0x24020002
    assert facts["stale_resident_word"] == 0x24020001
    assert facts["refilled_resident_word"] == 0x24020002
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print("EVIDENCE_SHA256=" + digest)
    print("EVIDENCE_JSON=" + canonical)
    print("PASS: exception transfer reaches the same vector address while stale I-cache selects the old handler generation until invalidate/refill")


if __name__ == "__main__":
    main()
