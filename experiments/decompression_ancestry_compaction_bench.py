#!/usr/bin/env python3
"""Direct-build/RSS benchmark for compact decompression ancestry receipts.

This is intentionally separate from the semantic fuzzer so receipt construction
can be measured without first materializing the byte-granular history. It imports
the experiment's data model and independent verifier.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import decompression_ancestry_compaction as model

SEED = 0x504C414944434F4D


def direct_compact(
    memory: dict[int, model.Cell],
    source_base: int,
    source_size: int,
    output_base: int,
    ops: tuple[model.Op, ...],
    transform_id: str,
) -> tuple[dict[int, model.Cell], model.CompactReceipt]:
    """Build one compact node per recognized transform op, never retaining writes."""
    mem = model.clone_memory(memory)
    initial = model.source_values(mem, source_base, source_size)
    nodes: list[model.CompactNode] = []
    output_hash = hashlib.sha256()
    seq = 0

    for op_index, op in enumerate(ops):
        length = 1 if op.kind == "literal" else op.b
        if op.kind == "literal" and not 0 <= op.a < source_size:
            raise ValueError("literal outside source")
        if op.kind == "backref" and (op.a <= 0 or op.b <= 0):
            raise ValueError("invalid backreference")

        seq_start = seq
        causal_hash = hashlib.sha256()
        for _ in range(length):
            if op.kind == "literal":
                source_address = source_base + op.a
            elif op.kind == "backref":
                source_index = seq - op.a
                if source_index < 0:
                    raise ValueError("backreference before output start")
                source_address = output_base + source_index
            else:
                raise ValueError("unknown operation")

            source = mem.get(source_address)
            if source is None:
                raise ValueError("read from uninitialized address")
            destination = output_base + seq
            write_token = f"O:{transform_id}:{seq}"
            write = model.ByteWrite(
                seq=seq,
                address=destination,
                value=source.value,
                source_address=source_address,
                source_token=source.token,
                write_token=write_token,
            )
            causal_hash.update(model.write_canonical(write))
            output_hash.update(bytes([source.value]))
            mem[destination] = model.Cell(source.value, write_token)
            seq += 1

        nodes.append(
            model.CompactNode(
                op_index=op_index,
                seq_start=seq_start,
                length=length,
                dst_start=output_base + seq_start,
                kind=op.kind,
                arg_a=op.a,
                arg_b=op.b,
                causal_sha256=causal_hash.hexdigest(),
            )
        )

    return mem, model.CompactReceipt(
        transform_id=transform_id,
        source_base=source_base,
        source_size=source_size,
        output_base=output_base,
        input_value_sha256=model.values_sha(initial),
        ops_sha256=model.ops_sha(ops),
        output_value_sha256=output_hash.hexdigest(),
        nodes=tuple(nodes),
    )


def encoded_size(receipt: object) -> int:
    return len(model.jbytes(asdict(receipt)))


def positive_equivalence(cases: int) -> dict[str, int]:
    rng = random.Random(SEED)
    writes = nodes = overlapping_nodes = inplace = 0
    for case in range(cases):
        source_size = rng.randint(4, 48)
        values = bytes(rng.randrange(8) for _ in range(source_size))
        source_base = 0x1000
        output_base = source_base + rng.randint(1, source_size - 1) if case % 9 == 0 else 0x4000
        inplace += int(output_base != 0x4000)
        ops = model.random_ops(rng, source_size, rng.randint(16, 256))
        overlapping_nodes += sum(op.kind == "backref" and op.b > op.a for op in ops)
        memory = model.initial_memory(values, source_base, case + 1)
        _, byte = model.execute_byte(memory, source_base, source_size, output_base, ops, f"D{case}")
        from_byte = model.compact_from_byte(ops, byte)
        _, direct = direct_compact(memory, source_base, source_size, output_base, ops, f"D{case}")
        if direct != from_byte:
            raise AssertionError(f"direct builder diverged from byte compactor in case {case}")
        ok, expanded = model.stream_verify_and_expand(memory, ops, direct, collect=True)
        if not ok or expanded != byte.writes:
            raise AssertionError(f"direct compact receipt failed expansion in case {case}")
        writes += len(byte.writes)
        nodes += len(direct.nodes)
    return {
        "cases": cases,
        "writes": writes,
        "nodes": nodes,
        "unsplit_overlapping_backref_nodes": overlapping_nodes,
        "inplace_cases": inplace,
    }


def workload(mode: str, n: int) -> tuple[bytes, tuple[model.Op, ...]]:
    if mode == "compressible":
        values = b"A"
        ops = (model.Op.literal(0), model.Op.backref(1, n - 1)) if n > 1 else (model.Op.literal(0),)
        return values, ops
    if mode == "alternating":
        values = bytes([0, 1])
        return values, tuple(model.Op.literal(i & 1) for i in range(n))
    raise ValueError(mode)


def worker(build: str, mode: str, n: int) -> dict[str, object]:
    source_base, output_base = 0x1000, 0x4000
    values, ops = workload(mode, n)
    memory = model.initial_memory(values, source_base, 1)
    started = time.perf_counter()
    if build == "byte":
        _, receipt = model.execute_byte(memory, source_base, len(values), output_base, ops, f"B-{mode}-{n}")
        retained_units = len(receipt.writes)
    elif build == "compact":
        _, receipt = direct_compact(memory, source_base, len(values), output_base, ops, f"B-{mode}-{n}")
        retained_units = len(receipt.nodes)
        ok, _ = model.stream_verify_and_expand(memory, ops, receipt, collect=False)
        if not ok:
            raise AssertionError("direct compact verification failed")
    else:
        raise ValueError(build)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "build": build,
        "mode": mode,
        "writes": n,
        "retained_units": retained_units,
        "json_bytes": encoded_size(receipt),
        "elapsed_ms": round(elapsed_ms, 3),
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def benchmarks() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    script = os.path.abspath(__file__)
    for mode, sizes in (("compressible", (1000, 10000, 100000)), ("alternating", (1000, 5000, 10000))):
        for n in sizes:
            pair: dict[str, dict[str, object]] = {}
            for build in ("byte", "compact"):
                completed = subprocess.run(
                    [sys.executable, script, "--worker", build, mode, str(n)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                pair[build] = json.loads(completed.stdout)
            byte = pair["byte"]
            compact = pair["compact"]
            rows.append(
                {
                    "mode": mode,
                    "writes": n,
                    "byte_json_bytes": byte["json_bytes"],
                    "compact_json_bytes": compact["json_bytes"],
                    "compact_nodes": compact["retained_units"],
                    "ratio_compact_over_byte": round(compact["json_bytes"] / byte["json_bytes"], 6),
                    "byte_elapsed_ms": byte["elapsed_ms"],
                    "compact_build_and_verify_ms": compact["elapsed_ms"],
                    "byte_peak_rss_kb": byte["peak_rss_kb"],
                    "compact_peak_rss_kb": compact["peak_rss_kb"],
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", nargs=3, metavar=("BUILD", "MODE", "N"))
    parser.add_argument("--cases", type=int, default=2000)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker[0], args.worker[1], int(args.worker[2])), sort_keys=True))
        return

    equivalence = positive_equivalence(args.cases)
    stable = {"seed": SEED, "equivalence": equivalence}
    stable_sha = hashlib.sha256(model.jbytes(stable)).hexdigest()
    report = {"stable": stable, "benchmarks": benchmarks()}
    print(json.dumps(report, sort_keys=True, indent=2))
    print(f"EQUIVALENCE_SHA256={stable_sha}")
    print("PASS: direct compact construction equals byte-history compaction and expands to the identical causal write sequence without retaining byte-write receipts")


if __name__ == "__main__":
    main()
