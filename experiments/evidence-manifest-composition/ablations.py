#!/usr/bin/env python3
"""Ablate which evidence-manifest fields actually prevent laundering."""
from __future__ import annotations

import copy
import json
import random

from model import (
    EvidenceMap,
    PrimitiveEvent,
    base_fixture,
    build_all_local,
    canonical,
    make_session,
    random_specs,
    sha256,
    verify_expected,
    verify_local_recomputed,
)


def verify_external_root_only(
    model: EvidenceMap, expected_roots: dict[str, str]
) -> bool:
    """No raw source: exact externally expected session set + primitive roots."""
    try:
        actual = build_all_local(model.events)
    except ValueError:
        return False
    return set(actual) == set(expected_roots) and all(
        actual[session].primitive_root == root
        for session, root in expected_roots.items()
    )


def verify_source_only(
    model: EvidenceMap, expected_sources: dict[str, str]
) -> bool:
    """Expected source/session presence, but no committed projected semantics."""
    actual_sessions = {event.session for event in model.events}
    if actual_sessions != set(expected_sources):
        return False
    for session, digest in expected_sources.items():
        selected = [event for event in model.events if event.session == session]
        if not selected or any(event.source_digest != digest for event in selected):
            return False
    return True


def verify_source_and_count(
    model: EvidenceMap, expected: dict[str, tuple[str, int]]
) -> bool:
    """Presence/count check, still does not bind each event's semantics."""
    if {event.session for event in model.events} != set(expected):
        return False
    for session, (digest, count) in expected.items():
        selected = [event for event in model.events if event.session == session]
        unique_seq = {event.seq for event in selected}
        if (
            len(unique_seq) != count
            or len(selected) != count
            or any(event.source_digest != digest for event in selected)
        ):
            return False
    return True


def semantic_mutation(event: PrimitiveEvent) -> PrimitiveEvent:
    semantics = dict(event.semantics)
    key = sorted(semantics)[0]
    value = semantics[key]
    semantics[key] = value + 4 if isinstance(value, int) else str(value) + "-forged"
    return PrimitiveEvent.make(
        event.session,
        event.source_digest,
        event.seq,
        event.kind,
        **semantics,
    )


def run_matrix() -> dict[str, bool]:
    base, expected, session_a, _ = base_fixture()
    roots = {session: manifest.primitive_root for session, manifest in expected.items()}
    sources = {session: manifest.source_digest for session, manifest in expected.items()}
    counts = {
        session: (manifest.source_digest, manifest.event_count)
        for session, manifest in expected.items()
    }
    result: dict[str, bool] = {}

    result["baseline_root_only_passes"] = verify_external_root_only(base, roots)
    result["baseline_source_only_passes"] = verify_source_only(base, sources)
    result["baseline_source_count_passes"] = verify_source_and_count(base, counts)

    partial = copy.deepcopy(base)
    partial.events.remove(
        next(event for event in partial.events if event.session == session_a and event.seq == 1)
    )
    partial.local_manifests = build_all_local(partial.events)
    result["partial_delete_source_only_false_accepts"] = verify_source_only(
        partial, sources
    )
    result["partial_delete_source_count_rejects"] = not verify_source_and_count(
        partial, counts
    )
    result["partial_delete_external_root_rejects"] = not verify_external_root_only(
        partial, roots
    )
    result["partial_delete_local_rehash_false_accepts"] = verify_local_recomputed(partial)

    changed = copy.deepcopy(base)
    victim = next(
        event for event in changed.events if event.session == session_a and event.seq == 0
    )
    changed.events.remove(victim)
    changed.events.append(semantic_mutation(victim))
    changed.local_manifests = build_all_local(changed.events)
    result["semantic_change_source_only_false_accepts"] = verify_source_only(
        changed, sources
    )
    result["semantic_change_source_count_false_accepts"] = verify_source_and_count(
        changed, counts
    )
    result["semantic_change_external_root_rejects"] = not verify_external_root_only(
        changed, roots
    )
    result["semantic_change_full_manifest_rejects"] = not verify_expected(changed, expected)

    same_value = copy.deepcopy(base)
    victim = next(
        event for event in same_value.events if event.session == session_a and event.seq == 1
    )
    same_value.events.remove(victim)
    # Keep count constant but move equal payload to a fresh causal identity.
    same_value.events.append(
        PrimitiveEvent.make(
            victim.session,
            victim.source_digest,
            1001,
            victim.kind,
            **dict(victim.semantics),
        )
    )
    same_value.local_manifests = build_all_local(same_value.events)
    result["same_value_source_count_false_accepts"] = verify_source_and_count(
        same_value, counts
    )
    result["same_value_external_root_rejects"] = not verify_external_root_only(
        same_value, roots
    )

    whole = copy.deepcopy(base)
    whole.events = [event for event in whole.events if event.session != session_a]
    whole.local_manifests = build_all_local(whole.events)
    result["whole_session_source_only_rejects"] = not verify_source_only(whole, sources)
    result["whole_session_external_root_rejects"] = not verify_external_root_only(
        whole, roots
    )

    derived = copy.deepcopy(base)
    derived.derived_facts.append({"kind": "new-derived", "pc": 0x80000000})
    derived.provenance.setdefault("x", []).extend(["new:a", "new:b"])
    result["derived_changes_external_root_pass"] = verify_external_root_only(
        derived, roots
    )

    # Rewriting the *external expectation* to match tampering obviously succeeds.
    # This is the trust-boundary proof: the expectation must not be map-controlled.
    attacker_expected = build_all_local(changed.events)
    attacker_roots = {
        session: manifest.primitive_root
        for session, manifest in attacker_expected.items()
    }
    result["attacker_rewritten_expectation_can_launder"] = verify_external_root_only(
        changed, attacker_roots
    )
    return result


def size_probe(seed: int = 0x41424C4154494F4E, sessions: int = 40) -> dict[str, int]:
    rng = random.Random(seed)
    manifests = {}
    for index in range(sessions):
        events, manifest = make_session(
            f"ablation-size-{index}", random_specs(rng, 1000)
        )
        assert events
        manifests[manifest.session] = manifest
    roots = {
        session: manifest.primitive_root
        for session, manifest in manifests.items()
    }
    full = {session: manifest.record() for session, manifest in manifests.items()}
    return {
        "sessions": sessions,
        "external_root_map_bytes": len(canonical(roots)),
        "full_manifest_bytes": len(canonical(full)),
    }


def main() -> None:
    checks = run_matrix()
    assert all(checks.values()), checks
    result = {
        "schema": "plaid-evidence-manifest-ablation/v0",
        "checks": checks,
        "size_probe": size_probe(),
    }
    result["semantic_sha256"] = sha256(result)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
