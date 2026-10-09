#!/usr/bin/env python3
"""Benchmark strict PI-queue history inspection on record-count and identity-count axes.

This creates syntactically and semantically accepted v2 histories from the existing
CLI fixture. Stress records are appended only after the fixture's final completed
scope and before its footer, so legacy fetch/PI causal relationships are unchanged.
No captured corpus or copyrighted input is committed.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def load_fixture():
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    path = scripts / "test_pi_queue_history.py"
    spec = importlib.util.spec_from_file_location("queue_fixture", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.fixture()


def json_line(value):
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def write_static(directory: Path):
    source, firmware, rows, fetches = load_fixture()
    rom = directory / "toy.z64"
    fw = directory / "firmware.bin"
    trace = directory / "fetch.ndjson"
    rom.write_bytes(source)
    fw.write_bytes(firmware)
    with trace.open("wb") as out:
        for row in fetches:
            out.write(json_line(row))
    return rows, rom, fw, trace


def write_history(path: Path, base_rows, axis: str, count: int):
    assert axis in ("neutral", "identity")
    assert base_rows[-1]["record"] == "end"
    base_count = len(base_rows) - 2
    sha = hashlib.sha256()
    total_bytes = 0
    with path.open("wb") as out:
        def emit(row):
            nonlocal total_bytes
            data = json_line(row)
            out.write(data)
            sha.update(data)
            total_bytes += len(data)
        for row in base_rows[:-1]:
            emit(row)
        # Neutral rows are actual legacy scalar records, so they traverse the full
        # v2 -> v1 -> v0 nested projection/inspection path. Successful RDRAM writes
        # outside a fetch context add only counts/hash evidence, not retained causal
        # identities. Identity rows instead stay at v2 and grow the retained token
        # BTreeMap. The existing fixture starts with exactly three inserted tokens.
        for i in range(count):
            ordinal = base_count + i + 1
            if axis == "neutral":
                row = dict(record="scalar", ordinal=ordinal, context=0, pc=0,
                           write=True, address=0, aligned_address=0,
                           bytes=4, device=3, value=0)
            else:
                row = dict(record="queue", ordinal=ordinal, context=0, pc=0,
                           kind=4, slot=0, other=0, event=2, clock=10,
                           valid=True, token=4+i, request=0, active_request=0)
            emit(row)
        footer = dict(base_rows[-1])
        footer["record_count"] = base_count + count
        emit(footer)
    return {
        "axis": axis,
        "stress_records": count,
        "records": base_count + count,
        "bytes": total_bytes,
        "sha256": sha.hexdigest(),
    }


def elapsed_seconds(value: str):
    total = 0.0
    for part in (float(x) for x in value.split(":")):
        total = total * 60 + part
    return total


def parse_time(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    def one(pattern):
        match = re.search(pattern, text, re.M)
        if not match:
            raise RuntimeError(f"missing time field {pattern!r}: {text}")
        return match.group(1)
    elapsed = one(r"^\s*Elapsed \(wall clock\) time.*:\s*(\S+)\s*$")
    return {
        "wall_seconds": elapsed_seconds(elapsed),
        "user_seconds": float(one(r"^\s*User time \(seconds\):\s*(\S+)\s*$")),
        "system_seconds": float(one(r"^\s*System time \(seconds\):\s*(\S+)\s*$")),
        "max_rss_kb": int(one(r"^\s*Maximum resident set size \(kbytes\):\s*(\d+)\s*$")),
        "minor_faults": int(one(r"^\s*Minor \(reclaiming a frame\) page faults:\s*(\d+)\s*$")),
        "major_faults": int(one(r"^\s*Major \(requiring I/O\) page faults:\s*(\d+)\s*$")),
    }


def timed(command, label: Path):
    subprocess.run(["/usr/bin/time", "-v", "-o", str(label), *map(str, command)],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    return parse_time(label)


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--neutral", default="10000,100000,500000,1000000")
    parser.add_argument("--identity", default="10000,50000,100000,250000")
    parser.add_argument("--output", type=Path, default=ROOT / "target/history-scalability/results.json")
    parser.add_argument("--exe", type=Path, default=ROOT / "target/release/plaid")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.exe.exists():
        raise SystemExit(f"missing release executable: {args.exe}")

    with tempfile.TemporaryDirectory(prefix="history-scale-", dir=ROOT / "target") as tmp:
        directory = Path(tmp)
        base_rows, rom, fw, trace = write_static(directory)
        cases = []
        for axis, text in (("neutral", args.neutral), ("identity", args.identity)):
            for count in [int(x) for x in text.split(",") if x]:
                history = directory / f"{axis}-{count}.ndjson"
                meta = write_history(history, base_rows, axis, count)
                output1 = directory / f"{axis}-{count}-report-1.json"
                output2 = directory / f"{axis}-{count}-report-2.json"
                inspect = [args.exe, "inspect-pi-queue-boot-history", rom, fw, trace, history, output1]
                first = timed(inspect, directory / f"{axis}-{count}-inspect1.time")
                inspect[-1] = output2
                repeat = timed(inspect, directory / f"{axis}-{count}-inspect2.time")
                if output1.read_bytes() != output2.read_bytes():
                    raise RuntimeError(f"nondeterministic report for {axis}/{count}")
                verify = [args.exe, "verify-pi-queue-boot-history", rom, fw, trace, history, output1]
                verification = timed(verify, directory / f"{axis}-{count}-verify.time")
                report = json.loads(output1.read_text(encoding="utf-8"))
                if report["history_sha256"] != meta["sha256"]:
                    raise RuntimeError(f"history digest mismatch for {axis}/{count}")
                expected_insertions = 3 + (count if axis == "identity" else 0)
                if report["successful_insertions"] != expected_insertions:
                    raise RuntimeError((axis, count, report["successful_insertions"], expected_insertions))
                if axis == "neutral" and report["projection"]["projection"]["event_counts"]["scalar"] < count:
                    raise RuntimeError(f"nested legacy projection did not consume neutral rows: {count}")
                meta.update(
                    report_sha256=sha256(output1),
                    report_bytes=output1.stat().st_size,
                    successful_insertions=report["successful_insertions"],
                    inspect_first=first,
                    inspect_repeat=repeat,
                    verify=verification,
                )
                cases.append(meta)
                print(json.dumps(meta, sort_keys=True), flush=True)
                history.unlink()
                output1.unlink()
                output2.unlink()

    result = {
        "schema": "plaid-history-scalability-v0",
        "main_commit": "ae41bdba82993ec8e77f47e5f9d3bb9af06f9256",
        "consumer_source_sha256": hashlib.sha256((ROOT/"crates/plaid-core/src/pi_queue_history.rs").read_bytes()).hexdigest(),
        "fixture_source_sha256": hashlib.sha256((ROOT/"scripts/test_pi_queue_history.py").read_bytes()).hexdigest(),
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("RESULT_SHA256=" + sha256(args.output), flush=True)


if __name__ == "__main__":
    main()
