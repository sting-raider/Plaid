#!/usr/bin/env python3
"""Adversarial composition model for pointer-table target identity.

This model deliberately keeps four facts separate:
  * immutable table bytes / numeric guest target,
  * translation/backing generation,
  * resident I-cache generation,
  * executable bytes/content identity.

It tests whether a stable numeric table target can be promoted to one CodeAddress
(image,generation) without an independent executable-lifetime witness.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Optional

TARGET = 0x80001000
TABLE_WORD = TARGET.to_bytes(4, "big")
TABLE_SHA = sha256(TABLE_WORD).hexdigest()


@dataclass(frozen=True)
class CodeGen:
    name: str
    backing: str
    mapping_gen: int
    payload: int


@dataclass(frozen=True)
class Dispatch:
    name: str
    pointer: int
    table_sha256: str
    current_backing: CodeGen
    resident: Optional[CodeGen]
    fetch_witness: bool
    expected: Optional[str]


def resolve_sound(d: Dispatch) -> Optional[str]:
    """Only an actual fetch/residency witness establishes executable identity."""
    if d.pointer != TARGET or d.table_sha256 != TABLE_SHA:
        return None
    if not d.fetch_witness or d.resident is None:
        return None
    return d.resident.name


def resolve_latest_backing(d: Dispatch) -> str:
    """Tempting but unsound shortcut: same pointer => current backing generation."""
    return d.current_backing.name


def resolve_payload_equivalence(d: Dispatch, known: list[CodeGen]) -> Optional[str]:
    """Another unsound shortcut: equal instruction bytes => same executable identity."""
    matches = [g.name for g in known if g.payload == d.current_backing.payload]
    return matches[0] if matches else None


def verify_unique_generation(dispatches: list[Dispatch], claimed: str) -> bool:
    """A unique target generation certificate must match every witnessed dispatch."""
    for d in dispatches:
        got = resolve_sound(d)
        if got is None or got != claimed:
            return False
    return True


def main() -> None:
    g0 = CodeGen("G0", "phys:001000", 0, 0x24020001)
    g1 = CodeGen("G1", "phys:001000", 0, 0x24020002)
    # Fresh backing generation, byte-identical to G1 on purpose.
    g2 = CodeGen("G2", "phys:001000", 0, 0x24020002)
    # Same numeric virtual pointer under a different mapping context/backing.
    g3 = CodeGen("G3", "phys:201000", 1, 0x24020003)
    known = [g0, g1, g2, g3]

    dispatches = [
        Dispatch("initial_g0", TARGET, TABLE_SHA, g0, g0, True, "G0"),
        # Backing replacement does not evict stale resident executable bytes.
        Dispatch("stale_after_g1_backing", TARGET, TABLE_SHA, g1, g0, True, "G0"),
        # After an explicit refill, the same table pointer executes G1.
        Dispatch("refilled_g1", TARGET, TABLE_SHA, g1, g1, True, "G1"),
        # Same-value G2 backing replacement is distinct; resident G1 survives.
        Dispatch("equal_payload_g2_stale_g1", TARGET, TABLE_SHA, g2, g1, True, "G1"),
        # Missing residency/fetch evidence cannot be repaired by current backing equality.
        Dispatch("missing_fetch_witness", TARGET, TABLE_SHA, g2, None, False, None),
        # Mapping context changes while pointer bytes remain identical.
        Dispatch("mapping_switch_g3", TARGET, TABLE_SHA, g3, g3, True, "G3"),
        # Restore can resurrect an older resident generation.
        Dispatch("restore_old_g0", TARGET, TABLE_SHA, g1, g0, True, "G0"),
    ]

    rows = []
    naive_failures = 0
    sound_open = 0
    for d in dispatches:
        sound = resolve_sound(d)
        latest = resolve_latest_backing(d)
        payload = resolve_payload_equivalence(d, known)
        if sound is None:
            sound_open += 1
        if d.expected is not None and latest != d.expected:
            naive_failures += 1
        if sound != d.expected:
            raise AssertionError(f"sound resolver mismatch for {d.name}: {sound} != {d.expected}")
        rows.append(
            {
                "case": d.name,
                "pointer": f"0x{d.pointer:08x}",
                "table_sha256": d.table_sha256,
                "current_backing": d.current_backing.name,
                "resident": None if d.resident is None else d.resident.name,
                "sound": sound,
                "latest_backing_shortcut": latest,
                "payload_shortcut": payload,
                "expected": d.expected,
            }
        )

    # Table bytes never changed, but witnessed executable identities are not unique.
    assert {d.table_sha256 for d in dispatches} == {TABLE_SHA}
    witnessed = {resolve_sound(d) for d in dispatches if resolve_sound(d) is not None}
    assert witnessed == {"G0", "G1", "G3"}
    assert not verify_unique_generation([d for d in dispatches if d.fetch_witness], "G0")
    assert not verify_unique_generation([d for d in dispatches if d.fetch_witness], "G1")
    assert not verify_unique_generation([d for d in dispatches if d.fetch_witness], "G3")

    # Equal payload is a deliberate decoy: G1 and G2 are distinct causal generations.
    assert g1.payload == g2.payload and g1.name != g2.name
    assert resolve_sound(dispatches[3]) == "G1"
    assert dispatches[3].current_backing.name == "G2"

    # Forged histories/certificates that omit target-lifetime evidence fail closed.
    forgeries = {
        "claim_source_generation_for_all_targets": verify_unique_generation(
            [d for d in dispatches if d.fetch_witness], "G0"
        ),
        "claim_current_backing_for_stale_dispatch": (
            resolve_latest_backing(dispatches[1]) == dispatches[1].expected
        ),
        "claim_equal_payload_means_new_generation_visible": (
            dispatches[3].current_backing.payload == dispatches[3].resident.payload
            and resolve_sound(dispatches[3]) == dispatches[3].current_backing.name
        ),
        "claim_missing_fetch_from_backing": resolve_sound(dispatches[4]) is not None,
        "claim_mapping_generation_irrelevant": (
            dispatches[5].current_backing.mapping_gen == g0.mapping_gen
        ),
        "claim_restore_is_monotonic_latest": (
            resolve_sound(dispatches[6]) == dispatches[6].current_backing.name
        ),
    }
    assert all(v is False for v in forgeries.values()), forgeries

    report = {
        "schema": 1,
        "table_sha256": TABLE_SHA,
        "numeric_target": f"0x{TARGET:08x}",
        "table_mutations": 0,
        "witnessed_executable_generations": sorted(witnessed),
        "naive_latest_backing_failures": naive_failures,
        "sound_open_cases": sound_open,
        "equal_payload_distinct_generations": [g1.name, g2.name],
        "forgeries_rejected": sorted(forgeries),
        "dispatches": rows,
        "result": "VALIDATED: immutable numeric target set does not prove executable image/generation/lifetime",
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(encoded).hexdigest()
    print(json.dumps(report, indent=2, sort_keys=True))
    print(f"REPORT_SHA256={digest}")
    print("PASS pointer target generation/lifetime adversarial composition")


if __name__ == "__main__":
    main()
