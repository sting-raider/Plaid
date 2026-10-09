#!/usr/bin/env python3
"""Deterministic adversarial replay for PI copy/completion vs I-cache provenance.

The model composes independently observed primitive boundaries. It never infers a
writer from equal values, and completion events do not mutate backing or resident
cache state.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

OLD = 0x34080000
FIRST = 0x34081111
SECOND = 0x34083333
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Word:
    value: int
    generation: str
    root: str


@dataclass
class Resident:
    word: Word
    generation: str
    trusted: bool


class ReplayError(RuntimeError):
    pass


class Recorder:
    def __init__(self) -> None:
        self.seq = 0
        self.events: list[dict[str, Any]] = []
        self.backing = Word(OLD, "backing:init", "init")
        self.resident: Resident | None = None

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.seq += 1
        e = {"seq": self.seq, "kind": kind, **fields}
        self.events.append(e)
        return e

    def pi_copy(self, transfer: int, value: int, queue_token: int | None) -> None:
        root = f"pi:{transfer}"
        generation = f"backing:pi:{transfer}"
        self.emit(
            "pi_copy",
            transfer=transfer,
            value=value,
            queue_token=queue_token,
            backing_generation=generation,
            root=root,
        )
        self.backing = Word(value, generation, root)

    def completion(self, transfer: int, queue_token: int) -> None:
        self.emit("pi_completion", transfer=transfer, queue_token=queue_token)

    def cpu_write(self, writer: int, value: int) -> None:
        generation = f"backing:cpu:{writer}"
        root = f"cpu:{writer}"
        self.emit("cpu_write", writer=writer, value=value, backing_generation=generation, root=root)
        self.backing = Word(value, generation, root)

    def invalidate(self) -> None:
        self.emit("invalidate")
        self.resident = None

    def fill(self) -> None:
        generation = f"resident:fill:{self.seq + 1}"
        self.emit(
            "fill",
            value=self.backing.value,
            backing_generation=self.backing.generation,
            backing_root=self.backing.root,
            resident_generation=generation,
        )
        self.resident = Resident(copy.deepcopy(self.backing), generation, True)

    def fetch(self) -> None:
        if self.resident is None:
            raise RuntimeError("fixture fetch without resident line")
        self.emit(
            "fetch",
            value=self.resident.word.value,
            resident_generation=self.resident.generation,
            claimed_root=self.resident.word.root if self.resident.trusted else UNKNOWN,
            trusted=self.resident.trusted,
        )

    def restore_same_tuple_without_witness(self) -> None:
        if self.resident is None:
            raise RuntimeError("restore requires resident tuple")
        saved = copy.deepcopy(self.resident)
        generation = f"resident:restore:{self.seq + 1}"
        self.emit("restore_same_tuple", value=saved.word.value, resident_generation=generation)
        self.resident = Resident(saved.word, generation, False)


def canonical_trace() -> list[dict[str, Any]]:
    r = Recorder()
    r.fill()              # old backing -> resident old
    r.fetch()
    r.pi_copy(1, FIRST, 101)
    r.completion(1, 101)  # lifecycle event only
    r.fetch()             # completed DMA, stale resident still old
    r.invalidate()
    r.fill()
    r.fetch()             # now rooted in PI transfer 1

    r.pi_copy(2, SECOND, None)  # queue insertion failed, byte effect exists
    r.fetch()             # stale PI-1 resident
    r.invalidate()
    r.fill()
    r.fetch()             # queue-less PI-2 writer becomes resident/executable

    r.pi_copy(3, SECOND, None)  # same value, distinct writer generation
    r.fetch()             # still PI-2 resident despite equal current backing
    r.invalidate()
    r.fill()
    r.fetch()             # switches to PI-3 generation

    r.cpu_write(1, SECOND)      # equal payload, non-PI writer
    r.fetch()             # still PI-3 resident
    r.restore_same_tuple_without_witness()
    r.fetch()             # identical tuple after restore is UNKNOWN
    return r.events


class StrictVerifier:
    def __init__(self) -> None:
        self.backing = Word(OLD, "backing:init", "init")
        self.resident: Resident | None = None
        self.last_seq = 0
        self.queue_tokens: dict[int, int] = {}
        self.completed: set[int] = set()
        self.fetch_roots: dict[int, str] = {}

    def fail(self, e: dict[str, Any], message: str) -> None:
        raise ReplayError(f"seq {e.get('seq')} {e.get('kind')}: {message}")

    def replay(self, events: list[dict[str, Any]]) -> dict[int, str]:
        for e in events:
            seq = e.get("seq")
            if not isinstance(seq, int) or seq <= self.last_seq:
                self.fail(e, "non-monotonic or duplicate sequence")
            self.last_seq = seq
            kind = e["kind"]
            if kind == "pi_copy":
                transfer = e["transfer"]
                generation = f"backing:pi:{transfer}"
                root = f"pi:{transfer}"
                if e["backing_generation"] != generation or e["root"] != root:
                    self.fail(e, "PI backing generation/root mismatch")
                token = e["queue_token"]
                if token is not None:
                    if token in self.queue_tokens.values():
                        self.fail(e, "queue token reused")
                    self.queue_tokens[transfer] = token
                self.backing = Word(e["value"], generation, root)
            elif kind == "pi_completion":
                transfer, token = e["transfer"], e["queue_token"]
                if self.queue_tokens.get(transfer) != token:
                    self.fail(e, "completion lacks exact successful queue token")
                if transfer in self.completed:
                    self.fail(e, "duplicate completion")
                self.completed.add(transfer)
                # Deliberately no backing/resident mutation here.
            elif kind == "cpu_write":
                generation = f"backing:cpu:{e['writer']}"
                root = f"cpu:{e['writer']}"
                if e["backing_generation"] != generation or e["root"] != root:
                    self.fail(e, "CPU backing generation/root mismatch")
                self.backing = Word(e["value"], generation, root)
            elif kind == "invalidate":
                self.resident = None
            elif kind == "fill":
                if e["value"] != self.backing.value:
                    self.fail(e, "fill payload disagrees with current backing")
                if e["backing_generation"] != self.backing.generation:
                    self.fail(e, "fill backing generation mismatch")
                if e["backing_root"] != self.backing.root:
                    self.fail(e, "fill backing root mismatch")
                expected_generation = f"resident:fill:{seq}"
                if e["resident_generation"] != expected_generation:
                    self.fail(e, "fill resident generation mismatch")
                self.resident = Resident(copy.deepcopy(self.backing), expected_generation, True)
            elif kind == "fetch":
                if self.resident is None:
                    self.fail(e, "cached fetch lacks resident line")
                expected_root = self.resident.word.root if self.resident.trusted else UNKNOWN
                if e["value"] != self.resident.word.value:
                    self.fail(e, "fetch payload mismatch")
                if e["resident_generation"] != self.resident.generation:
                    self.fail(e, "fetch resident generation mismatch")
                if e["trusted"] != self.resident.trusted:
                    self.fail(e, "fetch trust mismatch")
                if e["claimed_root"] != expected_root:
                    self.fail(e, "fetch provenance mismatch")
                self.fetch_roots[seq] = expected_root
            elif kind == "restore_same_tuple":
                if self.resident is None or e["value"] != self.resident.word.value:
                    self.fail(e, "restore tuple mismatch")
                expected_generation = f"resident:restore:{seq}"
                if e["resident_generation"] != expected_generation:
                    self.fail(e, "restore generation mismatch")
                self.resident = Resident(copy.deepcopy(self.resident.word), expected_generation, False)
            else:
                self.fail(e, "unknown event kind")
        return self.fetch_roots


def find(events: list[dict[str, Any]], seq: int) -> dict[str, Any]:
    return next(e for e in events if e["seq"] == seq)


def rejected(events: list[dict[str, Any]]) -> str:
    try:
        StrictVerifier().replay(events)
    except ReplayError as exc:
        return str(exc)
    raise AssertionError("forged history accepted")


def adversaries(canonical: list[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}

    # Completion is not a cache transition. Claiming PI-1 on the stale fetch fails.
    forged = copy.deepcopy(canonical)
    find(forged, 5)["claimed_root"] = "pi:1"
    out["completion_promotes_stale_resident"] = rejected(forged)

    # Current backing is PI-2, but stale resident still belongs to PI-1.
    forged = copy.deepcopy(canonical)
    find(forged, 10)["claimed_root"] = "pi:2"
    out["current_backing_promotes_stale_resident"] = rejected(forged)

    # Same-value PI-3 copy must not rewrite the resident PI-2 generation.
    forged = copy.deepcopy(canonical)
    find(forged, 15)["claimed_root"] = "pi:3"
    out["equal_payload_latest_writer_substitution"] = rejected(forged)

    # A fill may not claim a PI writer whose concrete copy event was deleted.
    forged = [copy.deepcopy(e) for e in canonical if e["seq"] != 9]
    out["deleted_queue_less_copy"] = rejected(forged)

    # Equal payload is not sufficient to swap backing generations at fill.
    forged = copy.deepcopy(canonical)
    fill = find(forged, 12)
    fill["backing_generation"] = "backing:pi:1"
    fill["backing_root"] = "pi:1"
    out["wrong_equal_fill_generation"] = rejected(forged)

    # Completion must still have exact queue identity, even though it is not byte provenance.
    forged = copy.deepcopy(canonical)
    find(forged, 4)["queue_token"] = 999
    out["forged_completion_token"] = rejected(forged)

    # Restore equality cannot resurrect the old resident lineage.
    forged = copy.deepcopy(canonical)
    find(forged, 22)["claimed_root"] = "pi:3"
    find(forged, 22)["trusted"] = True
    out["restore_tuple_reuses_old_lineage"] = rejected(forged)

    return out


def policy_disagreements(events: list[dict[str, Any]], roots: dict[int, str]) -> dict[str, Any]:
    # Model two deliberately naive policies for falsification accounting.
    current_backing = Word(OLD, "backing:init", "init")
    latest_completed_root = "init"
    completed: set[int] = set()
    completion_required_unknown: list[int] = []
    current_backing_wrong: list[int] = []
    completion_visibility_wrong: list[int] = []
    for e in events:
        kind = e["kind"]
        if kind == "pi_copy":
            current_backing = Word(e["value"], e["backing_generation"], e["root"])
        elif kind == "cpu_write":
            current_backing = Word(e["value"], e["backing_generation"], e["root"])
        elif kind == "pi_completion":
            completed.add(e["transfer"])
            latest_completed_root = f"pi:{e['transfer']}"
        elif kind == "fetch":
            truth = roots[e["seq"]]
            if truth != UNKNOWN and current_backing.root != truth:
                current_backing_wrong.append(e["seq"])
            if truth != UNKNOWN and latest_completed_root != truth:
                completion_visibility_wrong.append(e["seq"])
            if truth.startswith("pi:") and int(truth.split(":")[1]) not in completed:
                completion_required_unknown.append(e["seq"])
    return {
        "current_backing_wrong_fetches": current_backing_wrong,
        "completion_visibility_wrong_fetches": completion_visibility_wrong,
        "valid_pi_fetches_without_completion": completion_required_unknown,
    }


def main() -> None:
    trace = canonical_trace()
    roots = StrictVerifier().replay(trace)
    rejected_cases = adversaries(trace)
    disagreements = policy_disagreements(trace, roots)
    assert disagreements["valid_pi_fetches_without_completion"]
    report = {
        "events": len(trace),
        "fetch_roots": {str(k): v for k, v in roots.items()},
        "completed_transfers": [1],
        "queue_less_transfers": [2, 3],
        "policy_disagreements": disagreements,
        "rejected_forged_histories": rejected_cases,
        "trace_sha256": hashlib.sha256(
            json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["report_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
