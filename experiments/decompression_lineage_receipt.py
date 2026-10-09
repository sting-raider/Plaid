#!/usr/bin/env python3
"""Adversarial provenance model for dictionary/LZ-style decompression.

This is deliberately a transform-evidence experiment, not a claim that one
compression format covers N64 software.  The tiny IR has literal reads and
sequential backreferences, which is enough to exercise the causal feature that
matters to Plaid: an output byte may read a byte generated earlier by the same
transform, and source/output storage may overlap.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import argparse
import hashlib
import json
import random
from typing import Iterable


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
class WriteReceipt:
    seq: int
    out_index: int
    address: int
    value: int
    source_address: int
    source_token: str
    write_token: str


@dataclass(frozen=True)
class Receipt:
    transform_id: str
    source_base: int
    source_size: int
    output_base: int
    input_value_sha256: str
    ops_sha256: str
    output_value_sha256: str
    writes: tuple[WriteReceipt, ...]


@dataclass
class RunResult:
    memory: dict[int, Cell]
    receipt: Receipt
    output: bytes


def value_hash(values: Iterable[int]) -> str:
    return hashlib.sha256(bytes(values)).hexdigest()


def ops_hash(ops: Iterable[Op]) -> str:
    payload = [[op.kind, op.a, op.b] for op in ops]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=False, separators=(",", ":")).encode()
    ).hexdigest()


def initial_memory(values: bytes, source_base: int, epoch: int) -> dict[int, Cell]:
    return {
        source_base + i: Cell(value, f"I:{epoch}:{source_base + i:08x}")
        for i, value in enumerate(values)
    }


def clone_memory(memory: dict[int, Cell]) -> dict[int, Cell]:
    return {address: Cell(cell.value, cell.token) for address, cell in memory.items()}


def source_values(memory: dict[int, Cell], source_base: int, source_size: int) -> bytes:
    return bytes(memory[source_base + i].value for i in range(source_size))


def execute(
    memory: dict[int, Cell],
    source_base: int,
    source_size: int,
    output_base: int,
    ops: tuple[Op, ...],
    transform_id: str,
) -> RunResult:
    mem = clone_memory(memory)
    initial_values = source_values(mem, source_base, source_size)
    writes: list[WriteReceipt] = []

    def emit(source_address: int) -> None:
        if source_address not in mem:
            raise ValueError(f"read from uninitialized address 0x{source_address:x}")
        source = mem[source_address]
        seq = len(writes)
        destination = output_base + seq
        write_token = f"O:{transform_id}:{seq}"
        writes.append(
            WriteReceipt(
                seq=seq,
                out_index=seq,
                address=destination,
                value=source.value,
                source_address=source_address,
                source_token=source.token,
                write_token=write_token,
            )
        )
        mem[destination] = Cell(source.value, write_token)

    for op in ops:
        if op.kind == "literal":
            if op.a < 0 or op.a >= source_size:
                raise ValueError("literal offset outside declared source")
            emit(source_base + op.a)
        elif op.kind == "backref":
            if op.a <= 0 or op.b <= 0:
                raise ValueError("invalid backreference")
            for _ in range(op.b):
                out_index = len(writes)
                source_index = out_index - op.a
                if source_index < 0:
                    raise ValueError("backreference before output start")
                # Sequential byte copying is intentional.  If length > distance,
                # later bytes read generations produced earlier by this same op.
                emit(output_base + source_index)
        else:
            raise ValueError(f"unknown op {op.kind}")

    output = bytes(write.value for write in writes)
    receipt = Receipt(
        transform_id=transform_id,
        source_base=source_base,
        source_size=source_size,
        output_base=output_base,
        input_value_sha256=value_hash(initial_values),
        ops_sha256=ops_hash(ops),
        output_value_sha256=value_hash(output),
        writes=tuple(writes),
    )
    return RunResult(mem, receipt, output)


def hash_only_verify(
    memory: dict[int, Cell], ops: tuple[Op, ...], receipt: Receipt
) -> bool:
    """A tempting but provenance-blind verifier.

    It independently replays value semantics and authenticates initial/final byte
    hashes plus the transform program, but it deliberately ignores every source
    and output generation in the receipt.
    """
    if receipt.ops_sha256 != ops_hash(ops):
        return False
    if receipt.input_value_sha256 != value_hash(
        source_values(memory, receipt.source_base, receipt.source_size)
    ):
        return False
    try:
        replay = execute(
            memory,
            receipt.source_base,
            receipt.source_size,
            receipt.output_base,
            ops,
            receipt.transform_id,
        )
    except ValueError:
        return False
    return receipt.output_value_sha256 == value_hash(replay.output)


def value_replay_verify(
    memory: dict[int, Cell], ops: tuple[Op, ...], receipt: Receipt
) -> bool:
    """Stronger value/event-shape check that still ignores causal generations."""
    if not hash_only_verify(memory, ops, receipt):
        return False
    try:
        replay = execute(
            memory,
            receipt.source_base,
            receipt.source_size,
            receipt.output_base,
            ops,
            receipt.transform_id,
        )
    except ValueError:
        return False
    if len(replay.receipt.writes) != len(receipt.writes):
        return False
    for expected, claimed in zip(replay.receipt.writes, receipt.writes):
        if (
            expected.seq != claimed.seq
            or expected.out_index != claimed.out_index
            or expected.address != claimed.address
            or expected.value != claimed.value
        ):
            return False
    return True


def strict_verify(
    memory: dict[int, Cell], ops: tuple[Op, ...], receipt: Receipt
) -> bool:
    """Re-derive ordered source and output generations and require exact receipt."""
    if not hash_only_verify(memory, ops, receipt):
        return False
    try:
        replay = execute(
            memory,
            receipt.source_base,
            receipt.source_size,
            receipt.output_base,
            ops,
            receipt.transform_id,
        )
    except ValueError:
        return False
    return replay.receipt == receipt


def mutate_write(receipt: Receipt, index: int, **kwargs: object) -> Receipt:
    writes = list(receipt.writes)
    writes[index] = replace(writes[index], **kwargs)
    return replace(receipt, writes=tuple(writes))


def random_ops(rng: random.Random, source_size: int, target_len: int) -> tuple[Op, ...]:
    ops: list[Op] = []
    produced = 0
    while produced < target_len:
        remaining = target_len - produced
        if produced == 0 or rng.random() < 0.44:
            ops.append(Op.literal(rng.randrange(source_size)))
            produced += 1
        else:
            distance = rng.randint(1, produced)
            max_len = min(12, remaining)
            length = rng.randint(1, max_len)
            # Regularly force self-feeding overlap instead of accidentally
            # testing only memcpy-like non-overlap copies.
            if remaining >= 2 and rng.random() < 0.35:
                distance = rng.randint(1, min(4, produced))
                length = rng.randint(min(max_len, distance + 1), max_len) if max_len > distance else max_len
                length = max(1, length)
            ops.append(Op.backref(distance, length))
            produced += length
    return tuple(ops)


def positive_fuzz(rng: random.Random, cases: int) -> dict[str, int]:
    writes = 0
    overlapping = 0
    inplace = 0
    for case in range(cases):
        source_size = rng.randint(4, 32)
        values = bytes(rng.randrange(256) for _ in range(source_size))
        source_base = 0x1000
        if case % 7 == 0:
            output_base = source_base + rng.randint(1, source_size - 1)
            inplace += 1
        else:
            output_base = 0x4000
        target_len = rng.randint(8, 80)
        ops = random_ops(rng, source_size, target_len)
        if any(op.kind == "backref" and op.b > op.a for op in ops):
            overlapping += 1
        memory = initial_memory(values, source_base, epoch=case + 1)
        result = execute(memory, source_base, source_size, output_base, ops, f"P{case}")
        if not strict_verify(memory, ops, result.receipt):
            raise AssertionError(f"strict verifier rejected valid case {case}")
        writes += len(result.receipt.writes)
    return {
        "programs": cases,
        "writes": writes,
        "overlapping_backref_programs": overlapping,
        "inplace_programs": inplace,
    }


def record_axis(
    counters: dict[str, dict[str, int]],
    axis: str,
    memory: dict[int, Cell],
    ops: tuple[Op, ...],
    forged: Receipt,
) -> None:
    row = counters.setdefault(
        axis,
        {"cases": 0, "hash_only_accepts": 0, "value_replay_accepts": 0, "strict_rejects": 0},
    )
    row["cases"] += 1
    row["hash_only_accepts"] += int(hash_only_verify(memory, ops, forged))
    row["value_replay_accepts"] += int(value_replay_verify(memory, ops, forged))
    row["strict_rejects"] += int(not strict_verify(memory, ops, forged))


def adversarial_sweep(rng: random.Random, cases: int) -> dict[str, dict[str, int]]:
    counters: dict[str, dict[str, int]] = {}
    source_base = 0x1000
    output_base = 0x4000

    for case in range(cases):
        value = rng.randrange(256)
        epoch_a = 100_000 + case * 2
        epoch_b = epoch_a + 1

        # 1. Byte-identical source storage in a different generation.
        values = bytes([value, value ^ 0x5A, value])
        ops = (Op.literal(0), Op.literal(1), Op.backref(2, 3))
        mem_a = initial_memory(values, source_base, epoch_a)
        mem_b = initial_memory(values, source_base, epoch_b)
        good_a = execute(mem_a, source_base, len(values), output_base, ops, f"G{case}").receipt
        record_axis(counters, "input_storage_generation_swap", mem_b, ops, good_a)

        # 2. Overlapping backreference. With distance=1 each copied byte reads
        # the immediately preceding OUTPUT GENERATION, even though every value is equal.
        mono = bytes([value, value])
        mono_mem = initial_memory(mono, source_base, epoch_a)
        overlap_ops = (Op.literal(0), Op.backref(1, 7))
        overlap = execute(mono_mem, source_base, len(mono), output_base, overlap_ops, f"B{case}").receipt
        forged = mutate_write(
            overlap,
            4,
            source_token=mono_mem[source_base].token,
            source_address=source_base,
        )
        record_axis(counters, "overlapping_backref_flattened_to_literal", mono_mem, overlap_ops, forged)

        # 3. Equal-valued decoy input address steals literal ancestry.
        decoy_ops = (Op.literal(0), Op.literal(2))
        decoy = execute(mem_a, source_base, len(values), output_base, decoy_ops, f"D{case}").receipt
        forged = mutate_write(
            decoy,
            0,
            source_token=mem_a[source_base + 2].token,
            source_address=source_base + 2,
        )
        record_axis(counters, "equal_payload_decoy_input", mem_a, decoy_ops, forged)

        # 4. Same-value in-place clobber. The first output write replaces the
        # future literal source with a NEW generation without changing its bits.
        inplace_values = bytes([value, value, value])
        inplace_mem = initial_memory(inplace_values, source_base, epoch_a)
        inplace_ops = (Op.literal(0), Op.literal(1))
        inplace = execute(
            inplace_mem,
            source_base,
            len(inplace_values),
            source_base + 1,
            inplace_ops,
            f"I{case}",
        ).receipt
        assert inplace.writes[1].source_token == inplace.writes[0].write_token
        forged = mutate_write(
            inplace,
            1,
            source_token=inplace_mem[source_base + 1].token,
            source_address=source_base + 1,
        )
        record_axis(counters, "inplace_equal_value_future_source_clobber", inplace_mem, inplace_ops, forged)

        # 5. A future output token cannot be the source of an earlier write.
        future = mutate_write(
            overlap,
            2,
            source_token=overlap.writes[3].write_token,
            source_address=overlap.writes[3].address,
        )
        record_axis(counters, "future_generation_reordered_as_parent", mono_mem, overlap_ops, future)

        # 6. Deleting the source generation while retaining all values is not neutral.
        missing = mutate_write(overlap, 3, source_token="", source_address=overlap.writes[3].source_address)
        record_axis(counters, "missing_source_generation", mono_mem, overlap_ops, missing)

        # 7. A second equal-output decompression into the same span is a new transform.
        # Value replay cannot distinguish T1 from T2 output generations.
        repeat_ops = (Op.literal(0), Op.literal(1), Op.literal(2))
        run1 = execute(mem_a, source_base, len(values), output_base, repeat_ops, f"R1-{case}")
        run2 = execute(run1.memory, source_base, len(values), output_base, repeat_ops, f"R2-{case}")
        forged_writes = tuple(
            replace(
                new,
                write_token=old.write_token,
            )
            for old, new in zip(run1.receipt.writes, run2.receipt.writes)
        )
        forged_repeat = replace(run2.receipt, writes=forged_writes)
        record_axis(counters, "same_value_redecode_generation_collapse", run1.memory, repeat_ops, forged_repeat)

        # 8. A hash-only rule cannot detect a truncated causal history at all.
        truncated = replace(overlap, writes=overlap.writes[:-1])
        record_axis(counters, "truncated_write_history", mono_mem, overlap_ops, truncated)

    return counters


def check_expected(counters: dict[str, dict[str, int]], cases: int) -> None:
    ancestry_axes = {
        "input_storage_generation_swap",
        "overlapping_backref_flattened_to_literal",
        "equal_payload_decoy_input",
        "inplace_equal_value_future_source_clobber",
        "future_generation_reordered_as_parent",
        "missing_source_generation",
        "same_value_redecode_generation_collapse",
    }
    for axis, row in counters.items():
        if row["cases"] != cases or row["hash_only_accepts"] != cases or row["strict_rejects"] != cases:
            raise AssertionError(f"unexpected strict/hash result for {axis}: {row}")
        expected_value = 0 if axis == "truncated_write_history" else cases
        if row["value_replay_accepts"] != expected_value:
            raise AssertionError(f"unexpected value replay result for {axis}: {row}")
        if axis != "truncated_write_history" and axis not in ancestry_axes:
            raise AssertionError(f"unclassified adversary {axis}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive-cases", type=int, default=20_000)
    parser.add_argument("--adversarial-cases", type=int, default=10_000)
    parser.add_argument("--seed", type=lambda x: int(x, 0), default=0x504C414944)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    positive = positive_fuzz(rng, args.positive_cases)
    adversarial = adversarial_sweep(rng, args.adversarial_cases)
    check_expected(adversarial, args.adversarial_cases)

    report = {
        "schema": 1,
        "seed": args.seed,
        "positive": positive,
        "adversarial": adversarial,
        "contract": {
            "literal_parent": "exact current source-byte storage generation at read time",
            "backref_parent": "exact earlier output-byte generation actually read",
            "write_identity": "fresh output generation for every successful byte write, including equal-value writes",
            "overlap": "source reads are ordered against destination clobbers; initial/final value equality is insufficient",
        },
    }
    payload = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    print(payload)
    print(f"REPORT_SHA256={digest}")
    print(
        "PASS: strict causal replay accepted all valid transforms and rejected every forged ancestry; "
        "hash/value-only rules falsely accepted generation, backreference, decoy, in-place and redecode forgeries"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
