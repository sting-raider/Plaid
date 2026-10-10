#!/usr/bin/env python3
"""Adversarial model for deletion-resistant, merge-composable evidence manifests.

Research-only. This is not a production ProgramMap schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import copy
import hashlib
import json
import random
import time

DOMAIN_LEAF = "plaid-primitive-event-leaf/v0"
DOMAIN_MANIFEST = "plaid-evidence-session-manifest/v0"


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


@dataclass(frozen=True)
class PrimitiveEvent:
    session: str
    source_digest: str
    seq: int
    kind: str
    semantics: tuple[tuple[str, Any], ...]

    @staticmethod
    def make(
        session: str, source_digest: str, seq: int, kind: str, **semantics: Any
    ) -> "PrimitiveEvent":
        return PrimitiveEvent(
            session=session,
            source_digest=source_digest,
            seq=seq,
            kind=kind,
            semantics=tuple(sorted(semantics.items())),
        )

    def leaf(self) -> dict[str, Any]:
        return {
            "domain": DOMAIN_LEAF,
            "session": self.session,
            "source_digest": self.source_digest,
            "seq": self.seq,
            "kind": self.kind,
            "semantics": dict(self.semantics),
        }


@dataclass(frozen=True)
class SessionManifest:
    session: str
    source_digest: str
    event_count: int
    primitive_root: str

    def record(self) -> dict[str, Any]:
        return {
            "domain": DOMAIN_MANIFEST,
            "session": self.session,
            "source_digest": self.source_digest,
            "event_count": self.event_count,
            "primitive_root": self.primitive_root,
        }


@dataclass
class EvidenceMap:
    events: list[PrimitiveEvent]
    # Derived facts/provenance are intentionally outside the primitive commitment.
    derived_facts: list[dict[str, Any]]
    provenance: dict[str, list[str]]
    # This local copy is editable with the map and is therefore not a trust root.
    local_manifests: dict[str, SessionManifest]


def session_events(events: list[PrimitiveEvent], session: str) -> list[PrimitiveEvent]:
    return [event for event in events if event.session == session]


def build_manifest(events: list[PrimitiveEvent], session: str) -> SessionManifest:
    selected = session_events(events, session)
    if not selected:
        raise ValueError("cannot build manifest for absent session")
    digests = {event.source_digest for event in selected}
    if len(digests) != 1:
        raise ValueError("session has conflicting source digests")
    source_digest = next(iter(digests))
    by_seq: dict[int, PrimitiveEvent] = {}
    for event in selected:
        if event.seq in by_seq and by_seq[event.seq] != event:
            raise ValueError("one event identity has incompatible semantics")
        by_seq[event.seq] = event
    # Exact duplicate rows normalize to one event identity. Sequence belongs to
    # the leaf, so physical row ordering is irrelevant but chronology is not.
    leaves = [by_seq[seq].leaf() for seq in sorted(by_seq)]
    return SessionManifest(
        session=session,
        source_digest=source_digest,
        event_count=len(leaves),
        primitive_root=sha256({"domain": DOMAIN_MANIFEST, "leaves": leaves}),
    )


def build_all_local(events: list[PrimitiveEvent]) -> dict[str, SessionManifest]:
    return {
        session: build_manifest(events, session)
        for session in sorted({event.session for event in events})
    }


def verify_local_recomputed(model: EvidenceMap) -> bool:
    """Naive anti-pattern: trust manifests regenerated from the edited map."""
    try:
        return model.local_manifests == build_all_local(model.events)
    except ValueError:
        return False


def verify_expected(
    model: EvidenceMap, expected: dict[str, SessionManifest]
) -> bool:
    """Strict contract: external/source-bound expected session set + roots."""
    try:
        actual = build_all_local(model.events)
    except ValueError:
        return False
    if set(actual) != set(expected):
        return False
    for session, manifest in expected.items():
        if actual.get(session) != manifest:
            return False
        # A present-but-rewritten in-map manifest cannot override expectation.
        if model.local_manifests.get(session) != manifest:
            return False
    return True


def merge_maps(left: EvidenceMap, right: EvidenceMap) -> EvidenceMap:
    events = sorted(
        set(left.events) | set(right.events),
        key=lambda event: (
            event.session,
            event.seq,
            event.kind,
            event.semantics,
            event.source_digest,
        ),
    )
    derived = sorted(
        {
            canonical(fact).decode(): fact
            for fact in left.derived_facts + right.derived_facts
        }.values(),
        key=canonical,
    )
    provenance: dict[str, list[str]] = {}
    for source in (left.provenance, right.provenance):
        for key, refs in source.items():
            provenance.setdefault(key, [])
            provenance[key] = sorted(set(provenance[key]) | set(refs))
    local = dict(left.local_manifests)
    for session, manifest in right.local_manifests.items():
        if session in local and local[session] != manifest:
            # Do not choose a winner for a contradictory local commitment.
            local.pop(session, None)
        else:
            local[session] = manifest
    return EvidenceMap(events, derived, provenance, local)


def source_digest(label: str, event_specs: list[dict[str, Any]]) -> str:
    return sha256({"source": label, "events": event_specs})


def make_session(
    label: str, specs: list[dict[str, Any]]
) -> tuple[list[PrimitiveEvent], SessionManifest]:
    digest = source_digest(label, specs)
    session = "trace:" + digest
    events = [
        PrimitiveEvent.make(session, digest, seq, spec["kind"], **spec["semantics"])
        for seq, spec in enumerate(specs)
    ]
    return events, build_manifest(events, session)


def base_fixture() -> tuple[
    EvidenceMap, dict[str, SessionManifest], str, str
]:
    specs_a = [
        {
            "kind": "rom_dma",
            "semantics": {"rom_offset": 64, "physical": 0, "size": 8},
        },
        {
            "kind": "cpu_word_store",
            "semantics": {
                "site": 0x80001000,
                "destination": 0x80002000,
                "value": 0x11223344,
                "generation": 0,
            },
        },
        # Equal-value fresh event, distinct causal identity.
        {
            "kind": "cpu_word_store",
            "semantics": {
                "site": 0x80001004,
                "destination": 0x80002004,
                "value": 0x11223344,
                "generation": 0,
            },
        },
        {
            "kind": "indirect_transfer",
            "semantics": {
                "site": 0x80003000,
                "target": 0x80004000,
                "generation": 0,
            },
        },
    ]
    specs_b = [
        {
            "kind": "entry_verification",
            "semantics": {"entry": 0x80005000, "mask": 0, "generation": 0},
        },
        {
            "kind": "rom_dma",
            "semantics": {"rom_offset": 128, "physical": 0x1000, "size": 16},
        },
    ]
    events_a, manifest_a = make_session("trace-A", specs_a)
    events_b, manifest_b = make_session("trace-B", specs_b)
    model = EvidenceMap(
        events=events_a + events_b,
        derived_facts=[{"kind": "region", "image": "img", "generation": 0}],
        provenance={"region:img:0": [f"{events_a[0].session}:0"]},
        local_manifests={
            manifest_a.session: manifest_a,
            manifest_b.session: manifest_b,
        },
    )
    return (
        model,
        {manifest_a.session: manifest_a, manifest_b.session: manifest_b},
        manifest_a.session,
        manifest_b.session,
    )


def clone(model: EvidenceMap) -> EvidenceMap:
    return copy.deepcopy(model)


def rewrite_local(model: EvidenceMap) -> None:
    model.local_manifests = build_all_local(model.events)


def matrix() -> dict[str, bool]:
    base, expected, session_a, session_b = base_fixture()
    result: dict[str, bool] = {}
    result["baseline_strict_pass"] = verify_expected(base, expected)

    edited = clone(base)
    edited.events = [event for event in edited.events if event.session != session_a]
    edited.local_manifests.pop(session_a, None)
    result["whole_session_delete_naive_passes"] = verify_local_recomputed(edited)
    result["whole_session_delete_strict_rejects"] = not verify_expected(edited, expected)

    edited = clone(base)
    victim = next(
        event for event in edited.events if event.session == session_a and event.seq == 1
    )
    edited.events.remove(victim)
    rewrite_local(edited)
    result["single_delete_naive_passes"] = verify_local_recomputed(edited)
    result["single_delete_strict_rejects"] = not verify_expected(edited, expected)

    edited = clone(base)
    old = next(
        event for event in edited.events if event.session == session_a and event.seq == 1
    )
    edited.events.remove(old)
    edited.events.append(
        PrimitiveEvent.make(
            session_a, old.source_digest, 99, old.kind, **dict(old.semantics)
        )
    )
    rewrite_local(edited)
    result["same_value_fresh_event_strict_rejects"] = not verify_expected(
        edited, expected
    )

    edited = clone(base)
    old = next(
        event for event in edited.events if event.session == session_a and event.seq == 0
    )
    edited.events.remove(old)
    digest_b = next(
        event.source_digest for event in edited.events if event.session == session_b
    )
    edited.events.append(
        PrimitiveEvent.make(session_b, digest_b, 2, old.kind, **dict(old.semantics))
    )
    rewrite_local(edited)
    result["cross_session_transplant_strict_rejects"] = not verify_expected(
        edited, expected
    )

    edited = clone(base)
    old = next(
        event for event in edited.events if event.session == session_a and event.seq == 0
    )
    edited.events.append(
        PrimitiveEvent.make(
            session_a,
            old.source_digest,
            old.seq,
            old.kind,
            rom_offset=64,
            physical=0xDEAD,
            size=8,
        )
    )
    result["duplicate_identity_conflict_rejects"] = not verify_expected(edited, expected)

    edited = clone(base)
    edited.events.reverse()
    result["reorder_strict_passes"] = verify_expected(edited, expected)

    edited = clone(base)
    edited.derived_facts.append({"kind": "block", "pc": 0x80000000})
    edited.provenance.setdefault("region:img:0", []).extend(["static:a", "static:b"])
    result["derived_and_provenance_expansion_passes"] = verify_expected(
        edited, expected
    )

    edited = clone(base)
    edited.derived_facts.clear()
    edited.provenance.clear()
    result["derived_deletion_does_not_change_primitive_commitment"] = verify_expected(
        edited, expected
    )

    events_a = [event for event in base.events if event.session == session_a]
    events_b = [event for event in base.events if event.session == session_b]
    left = EvidenceMap(events_a, [{"kind": "a"}], {"x": ["a"]}, {session_a: expected[session_a]})
    right = EvidenceMap(events_b, [{"kind": "b"}], {"x": ["b"]}, {session_b: expected[session_b]})
    merged_ab = merge_maps(left, right)
    merged_ba = merge_maps(right, left)
    result["merge_ab_strict_passes"] = verify_expected(merged_ab, expected)
    result["merge_ba_strict_passes"] = verify_expected(merged_ba, expected)

    def projection(model: EvidenceMap) -> bytes:
        return canonical(
            {
                "events": [event.leaf() for event in model.events],
                "derived": model.derived_facts,
                "provenance": model.provenance,
                "manifests": {
                    key: value.record()
                    for key, value in sorted(model.local_manifests.items())
                },
            }
        )

    result["merge_order_canonical"] = projection(merged_ab) == projection(merged_ba)

    edited = clone(base)
    edited.events = [
        event
        for event in edited.events
        if not (event.session == session_b and event.seq == 1)
    ]
    rewrite_local(edited)
    result["forged_after_edit_local_passes"] = verify_local_recomputed(edited)
    result["forged_after_edit_strict_rejects"] = not verify_expected(edited, expected)
    return result


def random_specs(rng: random.Random, count: int) -> list[dict[str, Any]]:
    kinds = ["rom_dma", "cpu_word_store", "indirect_transfer", "entry_verification"]
    values = [0, 0x11223344, 0x11223344, 0xDEADBEEF]
    specs = []
    for index in range(count):
        kind = rng.choice(kinds)
        if kind == "rom_dma":
            semantics = {
                "rom_offset": rng.randrange(0, 512, 4),
                "physical": rng.randrange(0, 4096, 4),
                "size": rng.choice([4, 8, 16, 32]),
            }
        elif kind == "cpu_word_store":
            semantics = {
                "site": 0x80000000 + 4 * index,
                "destination": 0x80010000 + 4 * rng.randrange(32),
                "value": rng.choice(values),
                "generation": rng.randrange(4),
            }
        elif kind == "indirect_transfer":
            semantics = {
                "site": 0x80020000 + 4 * index,
                "target": 0x80030000 + 4 * rng.randrange(32),
                "generation": rng.randrange(4),
            }
        else:
            semantics = {
                "entry": 0x80040000 + 4 * rng.randrange(32),
                "mask": rng.choice([0, 0, 1, 3]),
                "generation": rng.randrange(4),
            }
        specs.append({"kind": kind, "semantics": semantics})
    return specs


def fuzz(seed: int = 0x504C414944, cases: int = 4000) -> dict[str, int]:
    rng = random.Random(seed)
    counts = {
        "cases": cases,
        "naive_partial_deletion_false_accepts": 0,
        "strict_partial_deletion_rejects": 0,
        "naive_whole_session_deletion_false_accepts": 0,
        "strict_whole_session_deletion_rejects": 0,
        "strict_same_value_replacement_rejects": 0,
        "strict_cross_session_transplant_rejects": 0,
        "strict_reorder_accepts": 0,
        "strict_derived_expansion_accepts": 0,
        "strict_merge_both_orders_accept": 0,
    }
    for case in range(cases):
        sessions = []
        for session_index in range(rng.randint(2, 4)):
            specs = random_specs(rng, rng.randint(2, 12))
            sessions.append(make_session(f"fuzz-{case}-{session_index}", specs))
        events = [event for group, _ in sessions for event in group]
        expected = {manifest.session: manifest for _, manifest in sessions}
        base = EvidenceMap(
            events,
            [{"kind": "derived", "case": case}],
            {"d": [f"p:{case}"]},
            dict(expected),
        )
        assert verify_expected(base, expected)

        edited = clone(base)
        edited.events.remove(rng.choice(edited.events))
        rewrite_local(edited)
        counts["naive_partial_deletion_false_accepts"] += int(
            verify_local_recomputed(edited)
        )
        counts["strict_partial_deletion_rejects"] += int(
            not verify_expected(edited, expected)
        )

        victim_session = rng.choice(list(expected))
        edited = clone(base)
        edited.events = [
            event for event in edited.events if event.session != victim_session
        ]
        rewrite_local(edited)
        counts["naive_whole_session_deletion_false_accepts"] += int(
            verify_local_recomputed(edited)
        )
        counts["strict_whole_session_deletion_rejects"] += int(
            not verify_expected(edited, expected)
        )

        edited = clone(base)
        victim = rng.choice(edited.events)
        edited.events.remove(victim)
        new_seq = max(
            event.seq for event in edited.events if event.session == victim.session
        ) + 1000
        edited.events.append(
            PrimitiveEvent.make(
                victim.session,
                victim.source_digest,
                new_seq,
                victim.kind,
                **dict(victim.semantics),
            )
        )
        rewrite_local(edited)
        counts["strict_same_value_replacement_rejects"] += int(
            not verify_expected(edited, expected)
        )

        edited = clone(base)
        victim = rng.choice(edited.events)
        other_session = rng.choice(
            [session for session in expected if session != victim.session]
        )
        edited.events.remove(victim)
        other_seqs = [event.seq for event in edited.events if event.session == other_session]
        edited.events.append(
            PrimitiveEvent.make(
                other_session,
                expected[other_session].source_digest,
                max(other_seqs) + 1000,
                victim.kind,
                **dict(victim.semantics),
            )
        )
        rewrite_local(edited)
        counts["strict_cross_session_transplant_rejects"] += int(
            not verify_expected(edited, expected)
        )

        edited = clone(base)
        rng.shuffle(edited.events)
        counts["strict_reorder_accepts"] += int(verify_expected(edited, expected))

        edited = clone(base)
        edited.derived_facts.append({"kind": "new-derived", "nonce": case})
        edited.provenance.setdefault("d", []).append(f"more:{case}")
        counts["strict_derived_expansion_accepts"] += int(
            verify_expected(edited, expected)
        )

        maps = [
            EvidenceMap(
                group,
                [{"kind": "s", "id": index}],
                {str(index): [manifest.session]},
                {manifest.session: manifest},
            )
            for index, (group, manifest) in enumerate(sessions)
        ]
        merged_left = maps[0]
        for other in maps[1:]:
            merged_left = merge_maps(merged_left, other)
        merged_right = maps[-1]
        for other in reversed(maps[:-1]):
            merged_right = merge_maps(merged_right, other)
        counts["strict_merge_both_orders_accept"] += int(
            verify_expected(merged_left, expected)
            and verify_expected(merged_right, expected)
        )
    return counts


def benchmark(
    seed: int = 0x4D414E4946455354, sessions: int = 40, per_session: int = 1000
) -> dict[str, Any]:
    rng = random.Random(seed)
    all_events: list[PrimitiveEvent] = []
    expected: dict[str, SessionManifest] = {}
    started = time.perf_counter()
    for session_index in range(sessions):
        specs = random_specs(rng, per_session)
        group, manifest = make_session(f"bench-{session_index}", specs)
        all_events.extend(group)
        expected[manifest.session] = manifest
    build_ms = (time.perf_counter() - started) * 1000
    model = EvidenceMap(all_events, [], {}, dict(expected))
    started = time.perf_counter()
    verified = verify_expected(model, expected)
    verify_ms = (time.perf_counter() - started) * 1000
    manifest_bytes = len(
        canonical({key: value.record() for key, value in expected.items()})
    )
    event_bytes = len(canonical([event.leaf() for event in all_events]))
    return {
        "sessions": sessions,
        "events": len(all_events),
        "build_ms": round(build_ms, 3),
        "verify_ms": round(verify_ms, 3),
        "verified": verified,
        "manifest_bytes": manifest_bytes,
        "event_leaf_bytes": event_bytes,
        "manifest_to_leaf_ratio": round(manifest_bytes / event_bytes, 6),
    }


def main() -> None:
    checks = matrix()
    assert all(checks.values()), checks
    fuzz_result = fuzz()
    for key, value in fuzz_result.items():
        if key != "cases":
            assert value == fuzz_result["cases"], (
                key,
                value,
                fuzz_result["cases"],
            )
    bench = benchmark()
    assert bench["verified"]
    result = {
        "schema": "plaid-evidence-manifest-experiment/v0",
        "matrix": checks,
        "fuzz": fuzz_result,
        "benchmark": bench,
    }
    result["semantic_sha256"] = sha256(
        {
            "schema": result["schema"],
            "matrix": checks,
            "fuzz": fuzz_result,
            # Timing varies by host and is deliberately excluded.
            "benchmark": {
                key: value
                for key, value in bench.items()
                if key not in ("build_ms", "verify_ms")
            },
        }
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
