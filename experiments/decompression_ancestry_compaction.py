#!/usr/bin/env python3
"""Lossless compaction experiment for decompression provenance receipts.

Composes the validated byte-granular dictionary/LZ receipt with a compact
operation/DAG receipt. Compact nodes bind a cryptographic digest of the full
causal expansion, not merely output values. Verification independently replays
operation semantics and streams the causal expansion; no value equality is used
as provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, replace
import argparse
import hashlib
import json
import os
import random
import resource
import subprocess
import sys
import time
from typing import Iterable

SEED = 0x504C41494443


@dataclass(frozen=True)
class Cell:
    value: int
    token: str


@dataclass(frozen=True)
class Op:
    kind: str
    a: int
    b: int = 0

    @staticmethod
    def literal(offset: int) -> "Op":
        return Op("literal", offset, 0)

    @staticmethod
    def backref(distance: int, length: int) -> "Op":
        return Op("backref", distance, length)


@dataclass(frozen=True)
class ByteWrite:
    seq: int
    address: int
    value: int
    source_address: int
    source_token: str
    write_token: str


@dataclass(frozen=True)
class ByteReceipt:
    transform_id: str
    source_base: int
    source_size: int
    output_base: int
    input_value_sha256: str
    ops_sha256: str
    output_value_sha256: str
    writes: tuple[ByteWrite, ...]


@dataclass(frozen=True)
class CompactNode:
    op_index: int
    seq_start: int
    length: int
    dst_start: int
    kind: str
    arg_a: int
    arg_b: int
    causal_sha256: str


@dataclass(frozen=True)
class CompactReceipt:
    transform_id: str
    source_base: int
    source_size: int
    output_base: int
    input_value_sha256: str
    ops_sha256: str
    output_value_sha256: str
    nodes: tuple[CompactNode, ...]


def hbytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jbytes(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def ops_sha(ops: tuple[Op, ...]) -> str:
    return hbytes(jbytes([[o.kind, o.a, o.b] for o in ops]))


def values_sha(values: Iterable[int]) -> str:
    return hbytes(bytes(values))


def initial_memory(values: bytes, base: int, epoch: int) -> dict[int, Cell]:
    return {base + i: Cell(v, f"I:{epoch}:{base+i:08x}") for i, v in enumerate(values)}


def clone_memory(mem: dict[int, Cell]) -> dict[int, Cell]:
    return dict(mem)


def source_values(mem: dict[int, Cell], base: int, size: int) -> bytes:
    return bytes(mem[base + i].value for i in range(size))


def write_canonical(w: ByteWrite) -> bytes:
    return jbytes([
        w.seq, w.address, w.value, w.source_address, w.source_token, w.write_token
    ]) + b"\n"


def execute_byte(
    memory: dict[int, Cell], source_base: int, source_size: int, output_base: int,
    ops: tuple[Op, ...], transform_id: str,
) -> tuple[dict[int, Cell], ByteReceipt]:
    mem = clone_memory(memory)
    initial = source_values(mem, source_base, source_size)
    writes: list[ByteWrite] = []

    def emit(src_addr: int) -> None:
        if src_addr not in mem:
            raise ValueError("read from uninitialized address")
        src = mem[src_addr]
        seq = len(writes)
        dst = output_base + seq
        token = f"O:{transform_id}:{seq}"
        w = ByteWrite(seq, dst, src.value, src_addr, src.token, token)
        writes.append(w)
        mem[dst] = Cell(src.value, token)

    for op in ops:
        if op.kind == "literal":
            if not 0 <= op.a < source_size:
                raise ValueError("literal outside source")
            emit(source_base + op.a)
        elif op.kind == "backref":
            if op.a <= 0 or op.b <= 0:
                raise ValueError("invalid backref")
            for _ in range(op.b):
                seq = len(writes)
                src_index = seq - op.a
                if src_index < 0:
                    raise ValueError("backref before output")
                emit(output_base + src_index)
        else:
            raise ValueError("unknown op")

    output = bytes(w.value for w in writes)
    return mem, ByteReceipt(
        transform_id, source_base, source_size, output_base,
        values_sha(initial), ops_sha(ops), values_sha(output), tuple(writes)
    )


def compact_from_byte(ops: tuple[Op, ...], byte: ByteReceipt) -> CompactReceipt:
    """Canonical one-node-per-transform-op compaction.

    Important: an overlapping backref is NOT split at writer-generation boundaries.
    Its sequential semantic rule is sufficient to regenerate those boundaries.
    Each node digest commits to the exact byte-level causal expansion.
    """
    nodes: list[CompactNode] = []
    cursor = 0
    for i, op in enumerate(ops):
        length = 1 if op.kind == "literal" else op.b
        chunk = byte.writes[cursor:cursor + length]
        if len(chunk) != length:
            raise ValueError("byte receipt does not cover operation")
        digest = hashlib.sha256()
        for w in chunk:
            digest.update(write_canonical(w))
        nodes.append(CompactNode(
            op_index=i,
            seq_start=cursor,
            length=length,
            dst_start=byte.output_base + cursor,
            kind=op.kind,
            arg_a=op.a,
            arg_b=op.b,
            causal_sha256=digest.hexdigest(),
        ))
        cursor += length
    if cursor != len(byte.writes):
        raise ValueError("unconsumed byte writes")
    return CompactReceipt(
        byte.transform_id, byte.source_base, byte.source_size, byte.output_base,
        byte.input_value_sha256, byte.ops_sha256, byte.output_value_sha256,
        tuple(nodes),
    )


def stream_verify_and_expand(
    memory: dict[int, Cell], ops: tuple[Op, ...], receipt: CompactReceipt,
    collect: bool = True,
) -> tuple[bool, tuple[ByteWrite, ...]]:
    """Independent compact verifier.

    It does not trust node digests or output values. It replays every operation
    from supplied generation-bearing memory, creates fresh writer generations,
    and recomputes each node causal digest in order. Expansion can be streamed;
    collecting writes is used only by equivalence tests.
    """
    if receipt.ops_sha256 != ops_sha(ops):
        return False, ()
    try:
        init = source_values(memory, receipt.source_base, receipt.source_size)
    except KeyError:
        return False, ()
    if receipt.input_value_sha256 != values_sha(init):
        return False, ()
    if len(receipt.nodes) != len(ops):
        return False, ()

    mem = clone_memory(memory)
    writes: list[ByteWrite] = []
    output_hash = hashlib.sha256()
    seq = 0

    for i, (op, node) in enumerate(zip(ops, receipt.nodes)):
        expected_len = 1 if op.kind == "literal" else op.b
        if (
            node.op_index != i or node.seq_start != seq or node.length != expected_len
            or node.dst_start != receipt.output_base + seq or node.kind != op.kind
            or node.arg_a != op.a or node.arg_b != op.b
        ):
            return False, ()
        digest = hashlib.sha256()
        for _ in range(expected_len):
            if op.kind == "literal":
                src_addr = receipt.source_base + op.a
            elif op.kind == "backref":
                src_index = seq - op.a
                if op.a <= 0 or op.b <= 0 or src_index < 0:
                    return False, ()
                src_addr = receipt.output_base + src_index
            else:
                return False, ()
            src = mem.get(src_addr)
            if src is None:
                return False, ()
            dst = receipt.output_base + seq
            token = f"O:{receipt.transform_id}:{seq}"
            w = ByteWrite(seq, dst, src.value, src_addr, src.token, token)
            digest.update(write_canonical(w))
            output_hash.update(bytes([src.value]))
            mem[dst] = Cell(src.value, token)
            if collect:
                writes.append(w)
            seq += 1
        if digest.hexdigest() != node.causal_sha256:
            return False, ()

    if output_hash.hexdigest() != receipt.output_value_sha256:
        return False, ()
    return True, tuple(writes)


def naive_value_verify(
    memory: dict[int, Cell], ops: tuple[Op, ...], receipt: CompactReceipt
) -> bool:
    """Intentionally weak comparator: checks operation shape and final values only."""
    if receipt.ops_sha256 != ops_sha(ops) or len(receipt.nodes) != len(ops):
        return False
    for i, (op, node) in enumerate(zip(ops, receipt.nodes)):
        length = 1 if op.kind == "literal" else op.b
        if (node.op_index, node.seq_start, node.length, node.kind, node.arg_a, node.arg_b) != (
            i, sum(1 if x.kind == "literal" else x.b for x in ops[:i]), length,
            op.kind, op.a, op.b,
        ):
            return False
    try:
        _, replay = execute_byte(memory, receipt.source_base, receipt.source_size,
                                 receipt.output_base, ops, receipt.transform_id)
    except ValueError:
        return False
    return replay.output_value_sha256 == receipt.output_value_sha256


def random_ops(rng: random.Random, source_size: int, target_len: int) -> tuple[Op, ...]:
    ops: list[Op] = []
    produced = 0
    while produced < target_len:
        remaining = target_len - produced
        if produced == 0 or rng.random() < 0.28:
            ops.append(Op.literal(rng.randrange(source_size)))
            produced += 1
        else:
            distance = rng.randint(1, produced)
            max_len = min(64, remaining)
            length = rng.randint(1, max_len)
            if max_len > 1 and rng.random() < 0.55:
                distance = rng.randint(1, min(produced, 8))
                low = min(max_len, distance + 1)
                if low <= max_len:
                    length = rng.randint(low, max_len)
            ops.append(Op.backref(distance, length))
            produced += length
    return tuple(ops)


def mutate_node(r: CompactReceipt, idx: int, **kw: object) -> CompactReceipt:
    nodes = list(r.nodes)
    nodes[idx] = replace(nodes[idx], **kw)
    return replace(r, nodes=tuple(nodes))


def positive_equivalence(rng: random.Random, cases: int) -> dict[str, int]:
    total_writes = total_nodes = overlaps = inplace = unsplit_overlap_nodes = 0
    for case in range(cases):
        source_size = rng.randint(4, 48)
        values = bytes(rng.randrange(8) for _ in range(source_size))
        source_base = 0x1000
        output_base = source_base + rng.randint(1, source_size - 1) if case % 9 == 0 else 0x4000
        inplace += int(output_base != 0x4000)
        ops = random_ops(rng, source_size, rng.randint(16, 256))
        overlap_ops = [o for o in ops if o.kind == "backref" and o.b > o.a]
        overlaps += int(bool(overlap_ops))
        unsplit_overlap_nodes += len(overlap_ops)
        mem = initial_memory(values, source_base, case + 1)
        _, byte = execute_byte(mem, source_base, source_size, output_base, ops, f"P{case}")
        compact = compact_from_byte(ops, byte)
        ok, expanded = stream_verify_and_expand(mem, ops, compact, collect=True)
        if not ok or expanded != byte.writes:
            raise AssertionError(f"compact equivalence failure case {case}")
        total_writes += len(byte.writes)
        total_nodes += len(compact.nodes)
    return {
        "programs": cases,
        "byte_writes": total_writes,
        "compact_nodes": total_nodes,
        "programs_with_overlapping_backrefs": overlaps,
        "inplace_programs": inplace,
        "unsplit_overlapping_backref_nodes": unsplit_overlap_nodes,
    }


def adversarial_forgery(rng: random.Random, cases: int) -> dict[str, dict[str, int]]:
    axes = {
        name: {"cases": 0, "strict_rejects": 0, "naive_accepts": 0}
        for name in [
            "source_generation_swap", "causal_digest_erasure", "backref_parent_substitution",
            "node_widening", "node_deletion", "node_reordering", "transform_generation_reuse",
            "same_value_redecode_digest_reuse", "future_parent_digest_forgery",
        ]
    }

    def record(name: str, mem: dict[int, Cell], ops: tuple[Op, ...], forged: CompactReceipt) -> None:
        axes[name]["cases"] += 1
        axes[name]["strict_rejects"] += int(not stream_verify_and_expand(mem, ops, forged, collect=False)[0])
        axes[name]["naive_accepts"] += int(naive_value_verify(mem, ops, forged))

    for case in range(cases):
        value = rng.randrange(4)
        source_base, output_base = 0x1000, 0x4000
        values = bytes([value, value, value ^ 1, value])
        ops = (Op.literal(0), Op.backref(1, 8), Op.literal(1), Op.backref(2, 6))
        mem_a = initial_memory(values, source_base, 100000 + case * 2)
        mem_b = initial_memory(values, source_base, 100001 + case * 2)
        _, byte = execute_byte(mem_a, source_base, len(values), output_base, ops, f"A{case}")
        good = compact_from_byte(ops, byte)

        record("source_generation_swap", mem_b, ops, good)
        record("causal_digest_erasure", mem_a, ops, mutate_node(good, 1, causal_sha256="0" * 64))
        record("backref_parent_substitution", mem_a, ops,
               mutate_node(good, 3, causal_sha256=good.nodes[1].causal_sha256))
        record("node_widening", mem_a, ops, mutate_node(good, 1, length=good.nodes[1].length + 1))
        record("node_deletion", mem_a, ops, replace(good, nodes=good.nodes[:-1]))
        swapped = list(good.nodes)
        swapped[1], swapped[2] = swapped[2], swapped[1]
        record("node_reordering", mem_a, ops, replace(good, nodes=tuple(swapped)))
        record("transform_generation_reuse", mem_a, ops, replace(good, transform_id=f"OLD{case}"))

        mem_after, byte1 = execute_byte(mem_a, source_base, len(values), output_base, ops, f"R1-{case}")
        _, byte2 = execute_byte(mem_after, source_base, len(values), output_base, ops, f"R2-{case}")
        c1 = compact_from_byte(ops, byte1)
        c2 = compact_from_byte(ops, byte2)
        forged = replace(c2, nodes=tuple(replace(n2, causal_sha256=n1.causal_sha256)
                                         for n1, n2 in zip(c1.nodes, c2.nodes)))
        record("same_value_redecode_digest_reuse", mem_after, ops, forged)

        bogus = hashlib.sha256((good.nodes[1].causal_sha256 + "future").encode()).hexdigest()
        record("future_parent_digest_forgery", mem_a, ops, mutate_node(good, 1, causal_sha256=bogus))

    return axes


def encoded_size(obj: object) -> int:
    if hasattr(obj, "__dataclass_fields__"):
        return len(jbytes(asdict(obj)))
    raise TypeError


def benchmark_one(mode: str, n: int) -> dict[str, object]:
    source_base, output_base = 0x1000, 0x4000
    if mode == "compressible":
        values = b"A"
        ops = (Op.literal(0), Op.backref(1, n - 1)) if n > 1 else (Op.literal(0),)
    elif mode == "alternating":
        values = bytes([0, 1])
        ops = tuple(Op.literal(i & 1) for i in range(n))
    else:
        raise ValueError(mode)
    mem = initial_memory(values, source_base, 1)
    t0 = time.perf_counter()
    _, byte = execute_byte(mem, source_base, len(values), output_base, ops, f"B-{mode}-{n}")
    t1 = time.perf_counter()
    compact = compact_from_byte(ops, byte)
    t2 = time.perf_counter()
    ok, _ = stream_verify_and_expand(mem, ops, compact, collect=False)
    t3 = time.perf_counter()
    if not ok:
        raise AssertionError("benchmark compact verification failed")
    byte_size = encoded_size(byte)
    compact_size = encoded_size(compact)
    return {
        "mode": mode, "writes": len(byte.writes), "nodes": len(compact.nodes),
        "byte_json_bytes": byte_size, "compact_json_bytes": compact_size,
        "ratio_compact_over_byte": round(compact_size / byte_size, 6),
        "execute_ms": round((t1 - t0) * 1000, 3),
        "compact_ms": round((t2 - t1) * 1000, 3),
        "verify_stream_ms": round((t3 - t2) * 1000, 3),
        "peak_rss_kb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def run_benchmarks() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    script = os.path.abspath(__file__)
    for mode, sizes in [("compressible", [1000, 10000, 100000]), ("alternating", [1000, 5000, 10000])]:
        for n in sizes:
            cp = subprocess.run([sys.executable, script, "--measure", mode, str(n)],
                                check=True, capture_output=True, text=True)
            rows.append(json.loads(cp.stdout))
    return rows


def worst_case_proof(n: int = 4096) -> dict[str, int]:
    values = bytes([0, 1])
    mem = initial_memory(values, 0x1000, 9)
    ops = tuple(Op.literal(i & 1) for i in range(n))
    _, byte = execute_byte(mem, 0x1000, len(values), 0x4000, ops, "WORST")
    compact = compact_from_byte(ops, byte)
    ok, expanded = stream_verify_and_expand(mem, ops, compact)
    if not ok or expanded != byte.writes or len(compact.nodes) != len(byte.writes):
        raise AssertionError("worst-case explicitness violated")
    return {"writes": len(byte.writes), "nodes": len(compact.nodes)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", nargs=2, metavar=("MODE", "N"))
    ap.add_argument("--positive", type=int, default=5000)
    ap.add_argument("--forgeries", type=int, default=2000)
    args = ap.parse_args()
    if args.measure:
        print(json.dumps(benchmark_one(args.measure[0], int(args.measure[1])), sort_keys=True))
        return

    rng = random.Random(SEED)
    positive = positive_equivalence(rng, args.positive)
    forgeries = adversarial_forgery(rng, args.forgeries)
    for axis, row in forgeries.items():
        if row["strict_rejects"] != row["cases"]:
            raise AssertionError(f"strict verifier accepted forgery axis {axis}: {row}")
    ancestry_axes = [
        "source_generation_swap", "causal_digest_erasure", "backref_parent_substitution",
        "transform_generation_reuse", "same_value_redecode_digest_reuse", "future_parent_digest_forgery",
    ]
    for axis in ancestry_axes:
        if forgeries[axis]["naive_accepts"] != forgeries[axis]["cases"]:
            raise AssertionError(f"naive control unexpectedly rejected {axis}")

    worst = worst_case_proof()
    benches = run_benchmarks()
    semantic = {"seed": SEED, "positive": positive, "forgeries": forgeries, "worst_case": worst}
    semantic_sha = hbytes(jbytes(semantic))
    report = {"semantic": semantic, "benchmarks": benches}
    print(json.dumps(report, sort_keys=True, indent=2))
    print(f"SEMANTIC_SHA256={semantic_sha}")
    print("PASS: compact operation/DAG receipts expand exactly to byte-granular ancestry; unsplit sequential backrefs preserve self-feeding generations; strict replay rejects every forged compact receipt")


if __name__ == "__main__":
    main()
