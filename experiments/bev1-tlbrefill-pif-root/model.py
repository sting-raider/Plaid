#!/usr/bin/env python3
"""Adversarial composition model for BEV=1 32-bit TLB-refill PIF provenance."""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass

VECTOR_VA = 0xFFFFFFFFBFC00200
VECTOR_PHYS = 0x1FC00200
VECTOR_OFFSET = 0x200
HANDLER = 0x24020007
FIRMWARE_A = "pif:synthetic:A"
FIRMWARE_B = "pif:synthetic:B"


@dataclass(frozen=True)
class BackingRead:
    ordinal: int
    offset: int
    word: int
    fetch_id: int | None
    firmware_id: str


@dataclass(frozen=True)
class Fetch:
    ordinal: int
    fetch_id: int
    vaddr: int
    physical: int
    returned: int
    backing_ordinal: int | None
    firmware_id: str


def strict_origin(fetch: Fetch, reads: list[BackingRead]):
    if fetch.vaddr != VECTOR_VA or fetch.physical != VECTOR_PHYS:
        return None
    if fetch.backing_ordinal is None:
        return None
    matches = [r for r in reads if r.ordinal == fetch.backing_ordinal]
    if len(matches) != 1:
        return None
    r = matches[0]
    if r.fetch_id != fetch.fetch_id:
        return None
    if r.firmware_id != fetch.firmware_id:
        return None
    if r.offset != VECTOR_OFFSET or r.word != fetch.returned:
        return None
    return ("pif_rom", r.firmware_id, r.ordinal, r.offset)


def latest_equal_origin(fetch: Fetch, reads: list[BackingRead]):
    # Deliberately unsound comparator: ignores active fetch and firmware identity.
    candidates = [r for r in reads if r.word == fetch.returned]
    if not candidates:
        return None
    r = max(candidates, key=lambda x: x.ordinal)
    return ("pif_rom", r.firmware_id, r.ordinal, r.offset)


def address_only_origin(fetch: Fetch):
    # Deliberately unsound comparator: derives PIF offset from vector address.
    return ("pif_rom", None, None, fetch.physical & 0x7FF)


def history(name: str, reads: list[BackingRead], fetch: Fetch, expected):
    strict = strict_origin(fetch, reads)
    latest = latest_equal_origin(fetch, reads)
    address = address_only_origin(fetch)
    assert strict == expected, (name, strict, expected)
    return {
        "name": name,
        "strict": strict,
        "latest_equal": latest,
        "address_only": address,
    }


def rejected_forgery(fetch: Fetch, reads: list[BackingRead], mutate) -> bool:
    f = copy.deepcopy(fetch)
    rs = copy.deepcopy(reads)
    f, rs = mutate(f, rs)
    return strict_origin(f, rs) is None


def main() -> None:
    cases = []

    real = BackingRead(20, VECTOR_OFFSET, HANDLER, 2, FIRMWARE_A)
    root = Fetch(21, 2, VECTOR_VA, VECTOR_PHYS, HANDLER, 20, FIRMWARE_A)
    cases.append(
        history(
            "causal_refill_root",
            [real],
            root,
            ("pif_rom", FIRMWARE_A, 20, VECTOR_OFFSET),
        )
    )

    # Same returned instruction, but SI latch supplied it. A prior real PIF read is a decoy.
    prior_equal = BackingRead(10, VECTOR_OFFSET + 8, HANDLER, None, FIRMWARE_A)
    latch = Fetch(21, 2, VECTOR_VA, VECTOR_PHYS, HANDLER, None, FIRMWARE_A)
    cases.append(history("busy_latch_equal_payload", [prior_equal], latch, None))
    assert cases[-1]["latest_equal"] is not None
    assert cases[-1]["address_only"] is not None

    # A mirrored non-fetch access hits the same masked source offset first.
    mirror_prior = BackingRead(11, VECTOR_OFFSET, HANDLER, None, FIRMWARE_A)
    cases.append(
        history(
            "prior_mirror_same_offset",
            [mirror_prior, real],
            root,
            ("pif_rom", FIRMWARE_A, 20, VECTOR_OFFSET),
        )
    )

    # Lockout returns zero at the same vector address. Numeric address cannot invent firmware origin.
    locked = Fetch(21, 2, VECTOR_VA, VECTOR_PHYS, 0, None, FIRMWARE_A)
    cases.append(history("rom_lockout", [], locked, None))
    assert cases[-1]["address_only"] is not None

    # A same-valued read inside another fetch context is not this refill root's source.
    wrong_context = BackingRead(19, VECTOR_OFFSET, HANDLER, 99, FIRMWARE_A)
    root_wrong_context = Fetch(21, 2, VECTOR_VA, VECTOR_PHYS, HANDLER, 19, FIRMWARE_A)
    cases.append(history("wrong_fetch_context", [wrong_context], root_wrong_context, None))

    # Equal payload at another PIF offset must not substitute.
    wrong_offset = BackingRead(20, VECTOR_OFFSET + 8, HANDLER, 2, FIRMWARE_A)
    root_wrong_offset = Fetch(21, 2, VECTOR_VA, VECTOR_PHYS, HANDLER, 20, FIRMWARE_A)
    cases.append(history("equal_payload_wrong_offset", [wrong_offset], root_wrong_offset, None))

    # Equal bytes under another declared firmware identity remain different provenance.
    wrong_firmware = BackingRead(20, VECTOR_OFFSET, HANDLER, 2, FIRMWARE_B)
    cases.append(history("equal_payload_wrong_firmware_generation", [wrong_firmware], root, None))
    assert cases[-1]["latest_equal"] is not None

    # The architectural vector fixes this physical address. A forged mirror cannot reuse the witness.
    mirrored_root = Fetch(21, 2, VECTOR_VA, 0x1FC00A00, HANDLER, 20, FIRMWARE_A)
    cases.append(history("forged_physical_mirror", [real], mirrored_root, None))

    # The completed general exception-vector receipt does not prove this refill fetch.
    general_vector = Fetch(21, 2, 0xFFFFFFFFBFC00380, 0x1FC00380, HANDLER, 20, FIRMWARE_A)
    cases.append(history("general_vector_receipt_not_refill_receipt", [real], general_vector, None))

    forgeries = {
        "delete_backing": lambda f, rs: (f, []),
        "wrong_fetch_id": lambda f, rs: (
            f,
            [BackingRead(rs[0].ordinal, rs[0].offset, rs[0].word, 77, rs[0].firmware_id)],
        ),
        "wrong_offset": lambda f, rs: (
            f,
            [BackingRead(rs[0].ordinal, VECTOR_OFFSET + 8, rs[0].word, rs[0].fetch_id, rs[0].firmware_id)],
        ),
        "wrong_word": lambda f, rs: (
            f,
            [BackingRead(rs[0].ordinal, rs[0].offset, rs[0].word ^ 1, rs[0].fetch_id, rs[0].firmware_id)],
        ),
        "wrong_firmware": lambda f, rs: (
            f,
            [BackingRead(rs[0].ordinal, rs[0].offset, rs[0].word, rs[0].fetch_id, FIRMWARE_B)],
        ),
        "wrong_physical": lambda f, rs: (
            Fetch(f.ordinal, f.fetch_id, f.vaddr, f.physical + 0x800, f.returned, f.backing_ordinal, f.firmware_id),
            rs,
        ),
        "wrong_vector": lambda f, rs: (
            Fetch(f.ordinal, f.fetch_id, f.vaddr + 0x180, f.physical, f.returned, f.backing_ordinal, f.firmware_id),
            rs,
        ),
        "duplicate_ordinal": lambda f, rs: (
            f,
            rs + [BackingRead(rs[0].ordinal, rs[0].offset, rs[0].word, rs[0].fetch_id, rs[0].firmware_id)],
        ),
    }
    rejected = []
    for name, mut in forgeries.items():
        assert rejected_forgery(root, [real], mut), name
        rejected.append(name)

    report = {
        "cases": cases,
        "forged_histories_rejected": rejected,
        "naive_false_positive_cases": [
            c["name"]
            for c in cases
            if c["strict"] is None
            and (c["latest_equal"] is not None or c["address_only"] is not None)
        ],
        "vector_va": VECTOR_VA,
        "vector_physical": VECTOR_PHYS,
        "vector_offset": VECTOR_OFFSET,
        "firmware_identity_bound": True,
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print(canonical)
    print("RESULT_SHA256=" + digest)
    print(
        "PASS: BEV1 32-bit refill-root provenance requires the exact in-context "
        "PIF backing event plus firmware identity; address/value/mirror equality is insufficient"
    )


if __name__ == "__main__":
    main()
