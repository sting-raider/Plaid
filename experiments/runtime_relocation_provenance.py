#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass, replace
from pathlib import Path

N64RECOMP_REV = "ffb39cdad1da5de07eaaa48bd1db4a89a7986771"
SOURCE_BLOBS = {
    "RecompModTool/main.cpp": "0768f16bf58ce09824cfe6ddec9eb5fcf9251ed7",
    "include/recomp.h": "73f3e73d7fc6cd6ccf37637f579fc389b554d8c3",
}
SEED = 0x504C41494452454C
FUZZ_CASES = 100_000
FORMULA_CASES = 250_000


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify_source_root(root: Path) -> dict[str, str]:
    observed: dict[str, str] = {}
    for rel, expected in SOURCE_BLOBS.items():
        actual = git_blob_sha1((root / rel).read_bytes())
        if actual != expected:
            raise AssertionError(f"source guard failed for {rel}: {actual} != {expected}")
        observed[rel] = actual
    return observed


def s16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def reloc_hi16_modtool(target: int) -> int:
    target &= 0xFFFFFFFF
    return ((target - s16(target)) >> 16) & 0xFFFF


def reloc_hi16_macro(target: int) -> int:
    target &= 0xFFFFFFFF
    return ((target >> 16) + ((target >> 15) & 1)) & 0xFFFF


def apply_reloc(kind: str, pre_word: int, target: int) -> int:
    pre_word &= 0xFFFFFFFF
    target &= 0xFFFFFFFF
    if kind == "R_MIPS_HI16":
        imm = reloc_hi16_modtool(target)
    elif kind == "R_MIPS_LO16":
        imm = target & 0xFFFF
    else:
        raise ValueError(kind)
    return (pre_word & 0xFFFF0000) | imm


@dataclass(frozen=True)
class StorageGeneration:
    generation: str
    load_generation: str
    word: int


@dataclass(frozen=True)
class RelocationEvent:
    event_id: str
    seq: int
    site: int
    kind: str
    target: int
    input_generation: str
    input_load_generation: str
    pre_word: int
    write_id: str
    output_generation: str


@dataclass(frozen=True)
class WriteEvent:
    write_id: str
    seq: int
    site: int
    pre_generation: str
    post_generation: str
    pre_word: int
    post_word: int


@dataclass(frozen=True)
class Receipt:
    relocation: RelocationEvent
    write: WriteEvent


def make_receipt(*, event_id: str, seq: int, site: int, kind: str, target: int, source: StorageGeneration) -> Receipt:
    post = apply_reloc(kind, source.word, target)
    out_gen = f"{source.generation}/{event_id}:post"
    write_id = f"{event_id}:write"
    return Receipt(
        RelocationEvent(
            event_id=event_id,
            seq=seq,
            site=site,
            kind=kind,
            target=target & 0xFFFFFFFF,
            input_generation=source.generation,
            input_load_generation=source.load_generation,
            pre_word=source.word & 0xFFFFFFFF,
            write_id=write_id,
            output_generation=out_gen,
        ),
        WriteEvent(
            write_id=write_id,
            seq=seq + 1,
            site=site,
            pre_generation=source.generation,
            post_generation=out_gen,
            pre_word=source.word & 0xFFFFFFFF,
            post_word=post,
        ),
    )


def strict_receipt(receipt: Receipt, source: StorageGeneration) -> bool:
    r, w = receipt.relocation, receipt.write
    if r.kind not in {"R_MIPS_HI16", "R_MIPS_LO16"} or r.seq >= w.seq:
        return False
    if r.site != w.site or r.write_id != w.write_id:
        return False
    if r.input_generation != source.generation or r.input_load_generation != source.load_generation:
        return False
    if r.pre_word != (source.word & 0xFFFFFFFF):
        return False
    if w.pre_generation != source.generation or w.pre_word != (source.word & 0xFFFFFFFF):
        return False
    if w.post_generation != r.output_generation or w.post_generation == w.pre_generation:
        return False
    return w.post_word == apply_reloc(r.kind, source.word, r.target)


def naive_receipt(receipt: Receipt) -> tuple[int, str, int, int]:
    r, w = receipt.relocation, receipt.write
    return (r.site, r.kind, r.target, w.post_word)


def strict_pair(hi: Receipt, lo: Receipt, hi_source: StorageGeneration, lo_source: StorageGeneration) -> bool:
    return (
        strict_receipt(hi, hi_source)
        and strict_receipt(lo, lo_source)
        and hi.relocation.kind == "R_MIPS_HI16"
        and lo.relocation.kind == "R_MIPS_LO16"
        and hi.relocation.target == lo.relocation.target
        and hi.relocation.input_load_generation == lo.relocation.input_load_generation
        and hi.relocation.seq < lo.relocation.seq
    )


def naive_pair(hi: Receipt, lo: Receipt) -> bool:
    return (
        hi.relocation.kind == "R_MIPS_HI16"
        and lo.relocation.kind == "R_MIPS_LO16"
        and hi.relocation.target == lo.relocation.target
    )


def run_formula_check(rng: random.Random) -> int:
    for i in range(FORMULA_CASES):
        target = rng.getrandbits(32)
        a = reloc_hi16_modtool(target)
        b = reloc_hi16_macro(target)
        if a != b:
            raise AssertionError((i, hex(target), hex(a), hex(b)))
    return FORMULA_CASES


def adversarial_cases() -> dict[str, bool | str]:
    target = 0x80408000
    site_hi = 0x80001000
    site_lo = 0x80001004
    a = StorageGeneration("overlayA:g1:word", "overlayA:g1", 0x3C081111)
    b = StorageGeneration("overlayA:g2:word", "overlayA:g2", 0x3C082222)
    ra = make_receipt(event_id="rel-a", seq=10, site=site_hi, kind="R_MIPS_HI16", target=target, source=a)
    rb = make_receipt(event_id="rel-b", seq=20, site=site_hi, kind="R_MIPS_HI16", target=target, source=b)
    assert ra.write.post_word == rb.write.post_word
    forged_ra = Receipt(
        replace(ra.relocation, input_generation=b.generation, input_load_generation=b.load_generation, pre_word=b.word),
        ra.write,
    )

    same_pre = StorageGeneration("overlayS:g1:word", "overlayS:g1", ra.write.post_word)
    same1 = make_receipt(event_id="same-1", seq=30, site=site_hi, kind="R_MIPS_HI16", target=target, source=same_pre)
    same_after = StorageGeneration(same1.write.post_generation, same_pre.load_generation, same1.write.post_word)
    same2 = make_receipt(event_id="same-2", seq=40, site=site_hi, kind="R_MIPS_HI16", target=target, source=same_after)
    assert same1.write.pre_word == same1.write.post_word == same2.write.post_word

    hi_src = StorageGeneration("pair:g1:hi", "overlayP:g1", 0x3C080000)
    lo_src_good = StorageGeneration("pair:g1:lo", "overlayP:g1", 0x25080000)
    lo_src_bad = StorageGeneration("pair:g2:lo", "overlayP:g2", 0x25080000)
    hi = make_receipt(event_id="pair-hi", seq=50, site=site_hi, kind="R_MIPS_HI16", target=target, source=hi_src)
    lo_good = make_receipt(event_id="pair-lo-good", seq=60, site=site_lo, kind="R_MIPS_LO16", target=target, source=lo_src_good)
    lo_bad = make_receipt(event_id="pair-lo-bad", seq=60, site=site_lo, kind="R_MIPS_LO16", target=target, source=lo_src_bad)

    missing_write = Receipt(ra.relocation, replace(ra.write, write_id="missing"))
    reordered = Receipt(ra.relocation, replace(ra.write, seq=ra.relocation.seq - 1))
    forged_post_gen = Receipt(ra.relocation, replace(ra.write, post_generation=ra.write.pre_generation))
    equal_payload_decoy = Receipt(replace(rb.relocation, event_id="decoy", write_id=ra.write.write_id), ra.write)

    return {
        "erased_preimage_same_post": ra.write.post_word == rb.write.post_word,
        "strict_rejects_generation_swap": not strict_receipt(forged_ra, a),
        "naive_generation_swap_collides": naive_receipt(forged_ra) == naive_receipt(ra),
        "same_value_relocation_mints_generation": strict_receipt(same1, same_pre) and strict_receipt(same2, same_after) and same1.write.post_generation != same2.write.post_generation,
        "naive_same_value_collapses": naive_receipt(same1) == naive_receipt(same2),
        "strict_pair_accepts_same_load_generation": strict_pair(hi, lo_good, hi_src, lo_src_good),
        "strict_pair_rejects_cross_load_generation": not strict_pair(hi, lo_bad, hi_src, lo_src_bad),
        "naive_pair_accepts_cross_load_generation": naive_pair(hi, lo_bad),
        "strict_rejects_missing_write_identity": not strict_receipt(missing_write, a),
        "strict_rejects_reordered_write": not strict_receipt(reordered, a),
        "strict_rejects_generation_nonadvance": not strict_receipt(forged_post_gen, a),
        "strict_rejects_equal_payload_decoy_event": not strict_receipt(equal_payload_decoy, a),
        "post_word": f"0x{ra.write.post_word:08x}",
    }


def run_fuzz(rng: random.Random) -> dict[str, int]:
    counters = {
        "generation_swap_false_accepts": 0,
        "strict_generation_swap_rejects": 0,
        "same_value_naive_collapses": 0,
        "strict_same_value_advances": 0,
        "cross_generation_naive_accepts": 0,
        "strict_cross_generation_rejects": 0,
    }
    for i in range(FUZZ_CASES):
        kind = "R_MIPS_HI16" if rng.getrandbits(1) else "R_MIPS_LO16"
        target = rng.getrandbits(32)
        upper = rng.getrandbits(16) << 16
        imm_a, imm_b = rng.getrandbits(16), rng.getrandbits(16)
        if imm_b == imm_a:
            imm_b ^= 1
        src_a = StorageGeneration(f"a:{i}", f"load-a:{i}", upper | imm_a)
        src_b = StorageGeneration(f"b:{i}", f"load-b:{i}", upper | imm_b)
        r_a = make_receipt(event_id=f"r:{i}", seq=10, site=0x80000000 + ((i & 0x1FFF) * 4), kind=kind, target=target, source=src_a)
        r_b = make_receipt(event_id=f"rb:{i}", seq=20, site=r_a.relocation.site, kind=kind, target=target, source=src_b)
        if r_a.write.post_word != r_b.write.post_word:
            raise AssertionError("relocation failed to erase old immediate")
        forged = Receipt(replace(r_a.relocation, input_generation=src_b.generation, input_load_generation=src_b.load_generation, pre_word=src_b.word), r_a.write)
        counters["generation_swap_false_accepts"] += int(naive_receipt(forged) == naive_receipt(r_a))
        counters["strict_generation_swap_rejects"] += int(not strict_receipt(forged, src_a))

        patched = StorageGeneration(f"same:{i}:0", f"load-same:{i}", r_a.write.post_word)
        s1 = make_receipt(event_id=f"s1:{i}", seq=30, site=r_a.relocation.site, kind=kind, target=target, source=patched)
        after = StorageGeneration(s1.write.post_generation, patched.load_generation, s1.write.post_word)
        s2 = make_receipt(event_id=f"s2:{i}", seq=40, site=r_a.relocation.site, kind=kind, target=target, source=after)
        counters["same_value_naive_collapses"] += int(naive_receipt(s1) == naive_receipt(s2))
        counters["strict_same_value_advances"] += int(strict_receipt(s1, patched) and strict_receipt(s2, after) and s1.write.post_generation != s2.write.post_generation)

        hi_source = StorageGeneration(f"h:{i}", f"pair-load:{i}:a", 0x3C080000 | rng.getrandbits(16))
        lo_source = StorageGeneration(f"l:{i}", f"pair-load:{i}:b", 0x25080000 | rng.getrandbits(16))
        hi = make_receipt(event_id=f"hi:{i}", seq=50, site=0x80010000, kind="R_MIPS_HI16", target=target, source=hi_source)
        lo = make_receipt(event_id=f"lo:{i}", seq=60, site=0x80010004, kind="R_MIPS_LO16", target=target, source=lo_source)
        counters["cross_generation_naive_accepts"] += int(naive_pair(hi, lo))
        counters["strict_cross_generation_rejects"] += int(not strict_pair(hi, lo, hi_source, lo_source))

    for name, value in counters.items():
        if value != FUZZ_CASES:
            raise AssertionError(f"{name}: {value} != {FUZZ_CASES}")
    return {"cases": FUZZ_CASES, **counters}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", type=Path)
    args = p.parse_args()
    rng = random.Random(SEED)
    source_blobs = verify_source_root(args.source_root) if args.source_root else SOURCE_BLOBS.copy()
    formula_cases = run_formula_check(rng)
    adversarial = adversarial_cases()
    if not all(v is True for k, v in adversarial.items() if k != "post_word"):
        raise AssertionError(adversarial)
    fuzz = run_fuzz(rng)
    core = {
        "result": "PASS",
        "n64recomp_revision": N64RECOMP_REV,
        "source_blobs": source_blobs,
        "formula_equivalence_cases": formula_cases,
        "adversarial": adversarial,
        "fuzz": fuzz,
        "claim": "site/kind/target/post-bytes are insufficient runtime relocation provenance",
        "required_contract": [
            "input_storage_generation",
            "input_load_or_overlay_generation",
            "preimage_word",
            "relocation_event_identity",
            "relocation_kind_and_target",
            "actual_mutation_event_identity_and_order",
            "postimage_storage_generation",
            "same-generation pairing_for_HI16_LO16_when_pair_semantics_are_claimed",
        ],
        "separate_obligations": ["cache-visible executable lifetime", "complete relocation discovery", "target reachability"],
    }
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print(json.dumps({**core, "sha256": digest}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
