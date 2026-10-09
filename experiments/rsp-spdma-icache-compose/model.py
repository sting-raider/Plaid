#!/usr/bin/env python3
"""Adversarial composition model for RSP -> reverse SP DMA -> RDRAM -> I-cache provenance.

This is a proof-composition model over previously validated primitive boundaries.
It does not emulate the N64 and does not infer provenance from equal values.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

UNKNOWN = "UNKNOWN"
LINE_BASE = 0x6000
LINE_SIZE = 32


@dataclass(frozen=True)
class ByteState:
    value: int
    storage_generation: str
    root: str


@dataclass
class CacheLine:
    base: int
    resident_generation: str
    bytes: list[ByteState]
    trusted: bool


class ReplayError(RuntimeError):
    pass


def initial_dmem() -> list[ByteState]:
    return [
        ByteState(0, f"dmem:init:{i}", f"dmem_initial:{i}")
        for i in range(LINE_SIZE)
    ]


def initial_rdram() -> dict[int, ByteState]:
    return {
        LINE_BASE + i: ByteState(
            0, f"rdram:init:{i}", f"rdram_initial:{LINE_BASE + i:08x}"
        )
        for i in range(LINE_SIZE)
    }


class Recorder:
    """Creates a self-describing event history from explicit storage effects."""

    def __init__(self) -> None:
        self.dmem = initial_dmem()
        self.rdram = initial_rdram()
        self.line: CacheLine | None = None
        self.events: list[dict[str, Any]] = []
        self.seq = 0

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.seq += 1
        event = {"seq": self.seq, "kind": kind, **fields}
        self.events.append(event)
        return event

    def rsp_store_word(self, context: int, offset: int, word: int) -> None:
        values = list(word.to_bytes(4, "big"))
        self.emit(
            "rsp_store_word", context=context, offset=offset, values=values
        )
        for lane, value in enumerate(values):
            generation = f"rsp:{context}:{offset + lane}"
            self.dmem[offset + lane] = ByteState(value, generation, generation)

    def sp_dma_word(self, source: int, destination: int) -> None:
        source_bytes = self.dmem[source : source + 4]
        event = self.emit(
            "sp_dma_word",
            source=source,
            destination=destination,
            values=[byte.value for byte in source_bytes],
            source_generations=[
                byte.storage_generation for byte in source_bytes
            ],
            source_roots=[byte.root for byte in source_bytes],
        )
        for lane, byte in enumerate(source_bytes):
            address = destination + lane
            self.rdram[address] = ByteState(
                byte.value,
                f"dma:{event['seq']}:{address:08x}",
                byte.root,
            )

    def cpu_rdram_write_word(self, destination: int, word: int) -> None:
        values = list(word.to_bytes(4, "big"))
        event = self.emit(
            "cpu_rdram_write_word",
            destination=destination,
            values=values,
        )
        for lane, value in enumerate(values):
            address = destination + lane
            generation = f"cpu:{event['seq']}:{address:08x}"
            self.rdram[address] = ByteState(value, generation, generation)

    def invalidate(self) -> None:
        self.emit("icache_invalidate", base=LINE_BASE)
        if self.line is not None and self.line.base == LINE_BASE:
            self.line = None

    def fill(self) -> None:
        backing = [self.rdram[LINE_BASE + lane] for lane in range(LINE_SIZE)]
        event = self.emit(
            "icache_fill",
            base=LINE_BASE,
            values=[byte.value for byte in backing],
            backing_generations=[
                byte.storage_generation for byte in backing
            ],
            backing_roots=[byte.root for byte in backing],
        )
        self.line = CacheLine(
            LINE_BASE,
            f"fill:{event['seq']}",
            copy.deepcopy(backing),
            True,
        )

    def fetch(self) -> None:
        if self.line is None:
            raise RuntimeError("fixture attempted a cached fetch without a line")
        word = self.line.bytes[:4]
        roots = [
            byte.root if self.line.trusted else UNKNOWN for byte in word
        ]
        self.emit(
            "cached_fetch",
            paddr=LINE_BASE,
            resident_generation=self.line.resident_generation,
            values=[byte.value for byte in word],
            expected_roots=roots,
            trusted=self.line.trusted,
        )

    def restore_same_tuple_without_witness(self) -> None:
        if self.line is None:
            raise RuntimeError("fixture restore requires a resident line")
        saved = copy.deepcopy(self.line)
        event = self.emit(
            "restore_line_without_fill_witness",
            base=saved.base,
            tag_base=saved.base,
            values=[byte.value for byte in saved.bytes],
        )
        # Equal tag/data after a restore does not establish that the old fill
        # caused this residency. Keep the bytes but deliberately lose lineage.
        self.line = CacheLine(
            saved.base,
            f"restore:{event['seq']}",
            saved.bytes,
            False,
        )


def build_trace() -> list[dict[str, Any]]:
    recorder = Recorder()

    # Phase A: first RSP producer reaches a cache miss/fill and then a hit.
    recorder.rsp_store_word(1, 0, 0x34081234)
    recorder.sp_dma_word(0, LINE_BASE)
    recorder.sp_dma_word(4, LINE_BASE + 4)
    recorder.fill()
    recorder.fetch()

    # Phase B: equal RSP writer + equal reverse DMA change backing generation.
    # The still-resident line must retain the older fill's lineage.
    recorder.rsp_store_word(2, 0, 0x34081234)
    recorder.sp_dma_word(0, LINE_BASE)
    recorder.fetch()

    # Invalidation/refill must switch to the new backing generation.
    recorder.invalidate()
    recorder.fill()
    recorder.fetch()

    # Phase C: an equal CPU/RDRAM overwrite after the fill must not
    # retroactively rewrite resident provenance. Refill must see the CPU writer.
    recorder.cpu_rdram_write_word(LINE_BASE, 0x34081234)
    recorder.fetch()
    recorder.invalidate()
    recorder.fill()
    recorder.fetch()

    # Phase D: an equal backing overwrite before fill must win. The old
    # RSP/DMA chain cannot survive merely because the bytes match.
    recorder.invalidate()
    recorder.rsp_store_word(3, 0, 0x34081234)
    recorder.sp_dma_word(0, LINE_BASE)
    recorder.cpu_rdram_write_word(LINE_BASE, 0x34081234)
    recorder.fill()
    recorder.fetch()

    # Phase E: restore an identical cache tuple without a witnessed fill.
    # Tuple equality cannot resurrect historical fill provenance.
    recorder.restore_same_tuple_without_witness()
    recorder.fetch()

    return recorder.events


class StrictVerifier:
    """Replays causal generations; value equality never supplies identity."""

    def __init__(self) -> None:
        self.dmem = initial_dmem()
        self.rdram = initial_rdram()
        self.line: CacheLine | None = None
        self.last_seq = 0
        self.seen_seq: set[int] = set()
        self.fetch_results: dict[int, list[str]] = {}

    def fail(self, event: dict[str, Any], detail: str) -> None:
        raise ReplayError(
            f"seq {event.get('seq')} {event.get('kind')}: {detail}"
        )

    def replay(self, events: list[dict[str, Any]]) -> dict[int, list[str]]:
        for event in events:
            seq = event["seq"]
            if seq in self.seen_seq:
                self.fail(event, "duplicate ordinal")
            if seq <= self.last_seq:
                self.fail(event, "non-monotonic ordinal")
            self.seen_seq.add(seq)
            self.last_seq = seq

            kind = event["kind"]
            if kind == "rsp_store_word":
                self._rsp_store(event)
            elif kind == "sp_dma_word":
                self._sp_dma(event)
            elif kind == "cpu_rdram_write_word":
                self._cpu_write(event)
            elif kind == "icache_invalidate":
                self._invalidate(event)
            elif kind == "icache_fill":
                self._fill(event)
            elif kind == "cached_fetch":
                self._fetch(event)
            elif kind == "restore_line_without_fill_witness":
                self._restore(event)
            else:
                self.fail(event, "unknown event kind")

        return self.fetch_results

    def _rsp_store(self, event: dict[str, Any]) -> None:
        values = event["values"]
        offset = event["offset"]
        context = event["context"]
        if len(values) != 4 or offset < 0 or offset + 4 > len(self.dmem):
            self.fail(event, "invalid RSP store span")
        for lane, value in enumerate(values):
            if not 0 <= value <= 0xFF:
                self.fail(event, "invalid RSP byte")
            generation = f"rsp:{context}:{offset + lane}"
            self.dmem[offset + lane] = ByteState(
                value, generation, generation
            )

    def _sp_dma(self, event: dict[str, Any]) -> None:
        source = event["source"]
        destination = event["destination"]
        if source < 0 or source + 4 > len(self.dmem):
            self.fail(event, "invalid SP DMA source")
        if any(
            destination + lane not in self.rdram for lane in range(4)
        ):
            self.fail(event, "SP DMA destination outside modeled RDRAM")

        current = self.dmem[source : source + 4]
        if event["values"] != [byte.value for byte in current]:
            self.fail(event, "SP DMA payload does not match current DMEM")
        if event["source_generations"] != [
            byte.storage_generation for byte in current
        ]:
            self.fail(event, "SP DMA source generation mismatch")
        if event["source_roots"] != [byte.root for byte in current]:
            self.fail(event, "SP DMA source root mismatch")

        for lane, byte in enumerate(current):
            address = destination + lane
            self.rdram[address] = ByteState(
                byte.value,
                f"dma:{event['seq']}:{address:08x}",
                byte.root,
            )

    def _cpu_write(self, event: dict[str, Any]) -> None:
        destination = event["destination"]
        values = event["values"]
        if len(values) != 4 or any(
            destination + lane not in self.rdram for lane in range(4)
        ):
            self.fail(event, "invalid CPU RDRAM write")
        for lane, value in enumerate(values):
            address = destination + lane
            generation = f"cpu:{event['seq']}:{address:08x}"
            self.rdram[address] = ByteState(
                value, generation, generation
            )

    def _invalidate(self, event: dict[str, Any]) -> None:
        if event["base"] != LINE_BASE:
            self.fail(event, "unexpected invalidation base")
        if self.line is not None and self.line.base == LINE_BASE:
            self.line = None

    def _fill(self, event: dict[str, Any]) -> None:
        base = event["base"]
        if base != LINE_BASE or base & (LINE_SIZE - 1):
            self.fail(event, "unexpected or unaligned fill")
        current = [
            self.rdram[base + lane] for lane in range(LINE_SIZE)
        ]
        if event["values"] != [byte.value for byte in current]:
            self.fail(event, "fill payload mismatch")
        if event["backing_generations"] != [
            byte.storage_generation for byte in current
        ]:
            self.fail(event, "fill backing generation mismatch")
        if event["backing_roots"] != [byte.root for byte in current]:
            self.fail(event, "fill backing root mismatch")

        self.line = CacheLine(
            base,
            f"fill:{event['seq']}",
            copy.deepcopy(current),
            True,
        )

    def _fetch(self, event: dict[str, Any]) -> None:
        paddr = event["paddr"]
        if paddr != LINE_BASE or self.line is None:
            self.fail(event, "cached fetch has no modeled resident hit")
        word = self.line.bytes[:4]
        roots = [
            byte.root if self.line.trusted else UNKNOWN for byte in word
        ]
        if event["resident_generation"] != self.line.resident_generation:
            self.fail(event, "resident generation mismatch")
        if event["trusted"] != self.line.trusted:
            self.fail(event, "resident trust mismatch")
        if event["values"] != [byte.value for byte in word]:
            self.fail(event, "cached fetch payload mismatch")
        if event["expected_roots"] != roots:
            self.fail(event, "cached fetch provenance mismatch")
        self.fetch_results[event["seq"]] = roots

    def _restore(self, event: dict[str, Any]) -> None:
        if self.line is None or event["base"] != self.line.base:
            self.fail(event, "restore fixture has no source resident tuple")
        if event["tag_base"] != self.line.base:
            self.fail(event, "restored tag mismatch")
        if event["values"] != [byte.value for byte in self.line.bytes]:
            self.fail(event, "restored payload mismatch")
        self.line = CacheLine(
            self.line.base,
            f"restore:{event['seq']}",
            copy.deepcopy(self.line.bytes),
            False,
        )


def event(events: list[dict[str, Any]], seq: int) -> dict[str, Any]:
    return next(item for item in events if item["seq"] == seq)


def strict_rejects(events: list[dict[str, Any]]) -> str:
    try:
        StrictVerifier().replay(events)
    except ReplayError as exc:
        return str(exc)
    raise AssertionError("forged history was accepted")


def adversaries(canonical: list[dict[str, Any]]) -> dict[str, str]:
    rejected: dict[str, str] = {}

    forged = copy.deepcopy(canonical)
    dma = event(forged, 7)
    dma["source_generations"] = [
        f"rsp:1:{lane}" for lane in range(4)
    ]
    dma["source_roots"] = [f"rsp:1:{lane}" for lane in range(4)]
    rejected["equal_payload_wrong_rsp_generation"] = strict_rejects(forged)

    forged = copy.deepcopy(canonical)
    old_fill = event(canonical, 4)
    new_fill = event(forged, 10)
    new_fill["backing_generations"][:4] = old_fill[
        "backing_generations"
    ][:4]
    new_fill["backing_roots"][:4] = old_fill["backing_roots"][:4]
    rejected["equal_payload_wrong_fill_generation"] = strict_rejects(forged)

    forged = [
        copy.deepcopy(item)
        for item in canonical
        if item["seq"] != 7
    ]
    rejected["deleted_equal_dma_sink"] = strict_rejects(forged)

    forged = copy.deepcopy(canonical)
    # Turn the pre-refill invalidation at seq 9 into an equal CPU overwrite.
    # The fill still claims the now-obsolete RSP/DMA storage generations.
    victim = event(forged, 9)
    victim.clear()
    victim.update(
        {
            "seq": 9,
            "kind": "cpu_rdram_write_word",
            "destination": LINE_BASE,
            "values": [0x34, 0x08, 0x12, 0x34],
        }
    )
    rejected["equal_overwrite_before_fill"] = strict_rejects(forged)

    forged = copy.deepcopy(canonical)
    event(forged, 10)["base"] = LINE_BASE + LINE_SIZE
    rejected["wrong_fill_address"] = strict_rejects(forged)

    forged = copy.deepcopy(canonical)
    event(forged, 8)["resident_generation"] = "fill:10"
    rejected["forged_resident_generation"] = strict_rejects(forged)

    forged = copy.deepcopy(canonical)
    forged.insert(8, copy.deepcopy(event(canonical, 8)))
    rejected["duplicate_ordinal"] = strict_rejects(forged)

    return rejected


def naive_current_backing(
    events: list[dict[str, Any]]
) -> dict[int, list[str]]:
    """Intentionally wrong: attributes every hit to current RDRAM."""
    dmem = initial_dmem()
    rdram = initial_rdram()
    out: dict[int, list[str]] = {}
    for item in events:
        kind = item["kind"]
        seq = item["seq"]
        if kind == "rsp_store_word":
            for lane, value in enumerate(item["values"]):
                generation = f"rsp:{item['context']}:{item['offset'] + lane}"
                dmem[item["offset"] + lane] = ByteState(
                    value, generation, generation
                )
        elif kind == "sp_dma_word":
            for lane in range(4):
                address = item["destination"] + lane
                source = dmem[item["source"] + lane]
                rdram[address] = ByteState(
                    source.value, f"dma:{seq}:{address:08x}", source.root
                )
        elif kind == "cpu_rdram_write_word":
            for lane, value in enumerate(item["values"]):
                address = item["destination"] + lane
                generation = f"cpu:{seq}:{address:08x}"
                rdram[address] = ByteState(value, generation, generation)
        elif kind == "cached_fetch":
            out[seq] = [
                rdram[item["paddr"] + lane].root for lane in range(4)
            ]
    return out


def naive_latest_tuple_restore(
    events: list[dict[str, Any]]
) -> list[str] | None:
    """Intentionally wrong: resurrects a matching historical fill after restore."""
    fills: list[dict[str, Any]] = []
    restore: dict[str, Any] | None = None
    for item in events:
        if item["kind"] == "icache_fill":
            fills.append(item)
        elif item["kind"] == "restore_line_without_fill_witness":
            restore = item
    if restore is None:
        return None
    matches = [
        fill for fill in fills
        if fill["base"] == restore["base"]
        and fill["values"] == restore["values"]
    ]
    if not matches:
        return None
    return matches[-1]["backing_roots"][:4]


def root_family(roots: list[str]) -> str:
    if all(root.startswith("rsp:") for root in roots):
        contexts = {root.split(":")[1] for root in roots}
        return "rsp:" + ",".join(sorted(contexts))
    if all(root.startswith("cpu:") for root in roots):
        seqs = {root.split(":")[1] for root in roots}
        return "cpu:" + ",".join(sorted(seqs))
    if all(root == UNKNOWN for root in roots):
        return UNKNOWN
    return "mixed"


def main() -> None:
    canonical = build_trace()
    strict = StrictVerifier().replay(canonical)
    rejected = adversaries(canonical)

    naive_backing = naive_current_backing(canonical)
    current_backing_mismatches = [
        seq for seq, roots in strict.items()
        if naive_backing.get(seq) != roots
    ]

    restore_seq = max(strict)
    latest_tuple_guess = naive_latest_tuple_restore(canonical)
    tuple_restore_mismatch = latest_tuple_guess != strict[restore_seq]

    report = {
        "schema": "rsp-spdma-icache-compose/v0",
        "canonical_event_count": len(canonical),
        "fetch_roots": {
            str(seq): {
                "family": root_family(roots),
                "roots": roots,
            }
            for seq, roots in strict.items()
        },
        "stale_hit_after_equal_rsp_dma": {
            "fetch_seq": 8,
            "strict_family": root_family(strict[8]),
            "current_backing_family": root_family(naive_backing[8]),
        },
        "stale_hit_after_equal_cpu_overwrite": {
            "fetch_seq": 13,
            "strict_family": root_family(strict[13]),
            "current_backing_family": root_family(naive_backing[13]),
        },
        "refill_switches_generation": {
            "before_refill_fetch": root_family(strict[8]),
            "after_refill_fetch": root_family(strict[11]),
        },
        "pre_fill_equal_overwrite_wins": root_family(strict[22]),
        "restore_without_fill_witness": {
            "strict": root_family(strict[restore_seq]),
            "latest_equal_tuple_guess": (
                root_family(latest_tuple_guess)
                if latest_tuple_guess is not None
                else None
            ),
            "naive_mismatch": tuple_restore_mismatch,
        },
        "naive_current_backing_mismatch_fetches": current_backing_mismatches,
        "forged_histories_rejected": sorted(rejected),
        "forgery_reasons": rejected,
    }

    canonical_bytes = json.dumps(
        canonical, sort_keys=True, separators=(",", ":")
    ).encode()
    report["canonical_trace_sha256"] = hashlib.sha256(
        canonical_bytes
    ).hexdigest()

    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["report_payload_sha256"] = hashlib.sha256(encoded).hexdigest()

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
