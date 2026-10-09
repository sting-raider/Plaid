#!/usr/bin/env python3
"""Build exact pinned ares and execute the PI DMA/I-cache composition fixture."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "target/pi-dma-icache-compose"
PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
OLD = 0x34080000
FIRST = 0x34081111
SECOND = 0x34083333
TARGET = 0x4000


def build():
    subprocess.run(["python3", str(HERE / "source_guard.py"), "--ares", str(ROOT / ".refs/ares")], check=True)
    spec = importlib.util.spec_from_file_location("ares_builder", ROOT / "spikes/003-ares-oracle/run.py")
    builder = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(builder)
    baseline = builder.build(
        HERE / "baseline.cpp",
        OUT / "baseline",
        extra_sources=(HERE / "driver.cpp",),
    )
    sensor = builder.build(
        HERE / "driver.cpp",
        OUT / "sensor",
        raw_fetch_access=True,
        physical_fetch_access=True,
        cache_fill_access=True,
        rdram_burst_access=True,
        rdram_scalar_access=True,
        fetch_boundary_access=True,
        pi_dma_access=True,
    )
    return baseline, sensor


def reconstruct_word(writes):
    first = sorted(writes, key=lambda e: e["address"])[:4]
    assert [e["address"] for e in first] == list(range(TARGET, TARGET + 4))
    return int.from_bytes(bytes(e["value"] for e in first), "big")


def verify(data):
    cps = {c["stage"]: c for c in data["checkpoints"]}
    assert sorted(cps) == [1, 2, 3, 4, 6, 8, 9, 11]
    assert cps[1]["t0"] == 0 and cps[1]["backing"] == OLD and cps[1]["resident"] == OLD
    assert cps[2]["backing"] == FIRST and cps[2]["resident"] == OLD and cps[2]["busy"] == 1 and cps[2]["interrupt"] == 0
    assert cps[3]["backing"] == FIRST and cps[3]["resident"] == OLD and cps[3]["busy"] == 0 and cps[3]["interrupt"] == 1
    assert cps[4]["t0"] == 0 and cps[4]["resident"] == OLD and cps[4]["backing"] == FIRST
    assert cps[6]["t0"] == 0x1111 and cps[6]["resident"] == FIRST and cps[6]["backing"] == FIRST
    assert cps[8]["backing"] == SECOND and cps[8]["resident"] == FIRST and cps[8]["busy"] == 1 and cps[8]["interrupt"] == 0
    assert cps[9]["t0"] == 0x1111 and cps[9]["resident"] == FIRST and cps[9]["backing"] == SECOND
    assert cps[11]["t0"] == 0x3333 and cps[11]["resident"] == SECOND and cps[11]["backing"] == SECOND
    assert all(c["resident_hit"] == 1 for c in cps.values())

    events = data["events"]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    begins = [e for e in events if e["kind"] == "pi_copy_begin"]
    returns = [e for e in events if e["kind"] == "pi_copy_return"]
    completions = [e for e in events if e["kind"] == "pi_completion"]
    assert [e["transfer"] for e in begins] == [1, 2]
    assert [e["transfer"] for e in returns] == [1, 2]
    assert [e["transfer"] for e in completions] == [1]
    assert completions[0]["stage"] == 3

    writes1 = [e for e in events if e["kind"] == "pi_rdram_write" and e["transfer"] == 1]
    writes2 = [e for e in events if e["kind"] == "pi_rdram_write" and e["transfer"] == 2]
    assert len(writes1) == len(writes2) == 32
    assert reconstruct_word(writes1) == FIRST
    assert reconstruct_word(writes2) == SECOND
    assert all(e["bytes"] == 1 and e["device"] == 5 for e in writes1 + writes2)

    source1 = [e for e in events if e["kind"] == "pi_source_half" and e["transfer"] == 1]
    source2 = [e for e in events if e["kind"] == "pi_source_half" and e["transfer"] == 2]
    assert len(source1) == len(source2) == 16
    assert source1[0]["offset"] == 0x1000 and source2[0]["offset"] == 0x3000
    assert source1[0]["value"] == FIRST >> 16 and source2[0]["value"] == SECOND >> 16

    fills = [e for e in events if e["kind"] == "icache_fill"]
    bursts = [e for e in events if e["kind"] == "icache_backing_read"]
    assert [e["stage"] for e in fills] == [1, 6, 11]
    assert [e["stage"] for e in bursts] == [1, 6, 11]
    assert [e["words"][0] for e in fills] == [OLD, FIRST, SECOND]
    assert [e["words"][0] for e in bursts] == [OLD, FIRST, SECOND]
    for burst, fill in zip(bursts, fills):
        assert burst["seq"] < fill["seq"] and burst["words"] == fill["words"]

    fetches = [e for e in events if e["kind"] == "fetch_end"]
    assert [(e["stage"], e["value"]) for e in fetches] == [
        (1, OLD), (4, OLD), (6, FIRST), (9, FIRST), (11, SECOND)
    ]
    assert not [e for e in fills if e["stage"] in (4, 9)]

    # The two decisive directional counterexamples.
    completion_seq = completions[0]["seq"]
    stale_after_completion = next(e for e in fetches if e["stage"] == 4)
    assert completion_seq < stale_after_completion["seq"] and stale_after_completion["value"] == OLD
    second_return = next(e for e in returns if e["transfer"] == 2)
    queue_less_fill = next(e for e in fills if e["stage"] == 11)
    queue_less_fetch = next(e for e in fetches if e["stage"] == 11)
    assert second_return["seq"] < queue_less_fill["seq"] < queue_less_fetch["seq"]
    assert not [e for e in completions if e["transfer"] == 2]
    assert queue_less_fetch["value"] == SECOND

    assert data["state"]["exception"] == 0
    assert data["state"]["t0"] == 0x3333
    assert data["state"]["backing"] == SECOND
    assert data["state"]["busy"] == 1 and data["state"]["interrupt"] == 0
    return {
        "events": len(events),
        "pi_writes": [len(writes1), len(writes2)],
        "source_halves": [len(source1), len(source2)],
        "fills": [(e["stage"], e["words"][0]) for e in fills],
        "fetches": [(e["stage"], e["value"]) for e in fetches],
        "completion_transfers": [e["transfer"] for e in completions],
        "queue_less_transfer": 2,
    }


def main():
    baseline, sensor = build()
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_raw = subprocess.check_output([str(baseline), "plain"], text=True, timeout=30)
    plain_raw = subprocess.check_output([str(sensor), "plain"], text=True, timeout=30)
    traced_raw = subprocess.check_output([str(sensor), "traced"], text=True, timeout=30)
    repeat_raw = subprocess.check_output([str(sensor), "traced"], text=True, timeout=30)
    assert traced_raw == repeat_raw
    baseline_data, plain_data, traced = map(json.loads, (baseline_raw, plain_raw, traced_raw))
    assert baseline_data["events"] == plain_data["events"] == []
    assert baseline_data["checkpoints"] == plain_data["checkpoints"] == traced["checkpoints"]
    assert baseline_data["state"] == plain_data["state"] == traced["state"]
    summary = verify(traced)
    report = {
        "ares_revision": PIN,
        "baseline_equal": True,
        "repeat_equal": True,
        "summary": summary,
        "raw": traced,
    }
    path = OUT / "results.json"
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("RESULT_SHA256=" + hashlib.sha256(path.read_bytes()).hexdigest())
    print("TRACE_SHA256=" + hashlib.sha256(traced_raw.encode()).hexdigest())
    print(json.dumps(summary, sort_keys=True))
    print("PASS: PI completion is neither necessary nor sufficient for cached executable visibility")


if __name__ == "__main__":
    main()
