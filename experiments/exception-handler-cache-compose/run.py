#!/usr/bin/env python3
"""Build and execute the exact-pinned exception/I-cache composition fixture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "target/exception-handler-cache-compose"
ARES_REV = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
VECTOR = 0xFFFFFFFF80000180
VECTOR_PA = 0x180
HANDLER_A = 0x24100011
HANDLER_B = 0x24100022


def builder_module():
    path = ROOT / "spikes/003-ares-oracle/run.py"
    spec = importlib.util.spec_from_file_location("plaid_ares_oracle", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def phase_projection(result: dict) -> dict:
    return {"phases": result["phases"], "final": result["final"]}


def check(result: dict) -> None:
    phases = result["phases"]
    assert [p["name"] for p in phases] == [
        "cold_a",
        "stale_after_changed_write",
        "refill_b",
        "stale_after_same_value_write",
        "refill_same_value_b",
    ]
    assert [p["s0"] for p in phases] == [0x11, 0x11, 0x22, 0x22, 0x22]
    assert [p["backing"] for p in phases] == [HANDLER_A, HANDLER_B, HANDLER_B, HANDLER_B, HANDLER_B]
    assert [p["resident"] for p in phases] == [HANDLER_A, HANDLER_A, HANDLER_B, HANDLER_B, HANDLER_B]
    assert [p["misses"] for p in phases] == [1, 1, 2, 2, 3]
    assert [p["hits"] for p in phases] == [0, 1, 1, 2, 2]
    assert all(p["valid"] for p in phases)
    assert all(p["tag"] == 1 for p in phases), phases
    assert all(p["pc"] == VECTOR + 4 for p in phases)

    if result["mode"] == "plain":
        assert result["handler_fetches"] == []
        assert result["fills"] == []
        assert result["writes"] == []
        return

    fetches = result["handler_fetches"]
    fills = result["fills"]
    writes = result["writes"]
    assert len(fetches) == 5, fetches
    assert [f["pc"] for f in fetches] == [VECTOR] * 5
    assert [f["physical"] for f in fetches] == [VECTOR_PA] * 5
    assert all(f["cached"] for f in fetches)
    assert [f["word"] for f in fetches] == [HANDLER_A, HANDLER_A, HANDLER_B, HANDLER_B, HANDLER_B]
    assert [f["resident"] for f in fetches] == [HANDLER_A, HANDLER_A, HANDLER_B, HANDLER_B, HANDLER_B]
    assert [f["fill_count"] for f in fetches] == [1, 1, 2, 2, 3]

    assert len(fills) == 3, fills
    assert [f["id"] for f in fills] == [1, 2, 3]
    assert [f["physical"] for f in fills] == [VECTOR_PA] * 3
    assert [f["index"] for f in fills] == [VECTOR_PA] * 3
    assert [f["word0"] for f in fills] == [HANDLER_A, HANDLER_B, HANDLER_B]

    # Both changed-value and same-value mutations are real completed RDRAM writes.
    assert len(writes) == 2, writes
    assert [w["address"] for w in writes] == [VECTOR_PA, VECTOR_PA]
    assert [w["value"] for w in writes] == [HANDLER_B, HANDLER_B]
    assert all(w["size"] == 4 for w in writes), writes


def main() -> int:
    ref = ROOT / ".refs/ares"
    if not ref.exists():
        raise SystemExit("missing .refs/ares")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ref, text=True).strip()
    if actual != ARES_REV:
        raise SystemExit(f"ares pin mismatch: {actual} != {ARES_REV}")

    builder = builder_module()
    exe = builder.build(
        HERE / "driver.cpp",
        OUT,
        raw_fetch_access=True,
        physical_fetch_access=True,
        cache_fill_access=True,
        rdram_scalar_access=True,
    )

    raw_plain = subprocess.check_output([str(exe), "plain"], text=True, timeout=30)
    raw_traced = subprocess.check_output([str(exe), "traced"], text=True, timeout=30)
    raw_repeat = subprocess.check_output([str(exe), "traced"], text=True, timeout=30)
    assert raw_traced == raw_repeat, "traced run is not byte-identical on repeat"

    plain = json.loads(raw_plain)
    traced = json.loads(raw_traced)
    repeat = json.loads(raw_repeat)
    check(plain)
    check(traced)
    check(repeat)
    assert phase_projection(plain) == phase_projection(traced) == phase_projection(repeat), (
        phase_projection(plain), phase_projection(traced)
    )

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": 1,
        "ares_revision": ARES_REV,
        "plain": plain,
        "traced": traced,
    }
    result_path = OUT / "results.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    print(
        "PASS"
        f" RESULT_SHA256={digest}"
        " handler_fetches=5 fills=3 writes=2"
        " stale_changed=1 stale_same_value=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
