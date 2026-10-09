#!/usr/bin/env python3
"""Replay actual DMEM writer generations through completed SP write-DMA effects."""
from __future__ import annotations

import copy
import hashlib

K_INSN_BEGIN = 0
K_RSP_SINK = 1
K_INSN_END = 2
K_CPU_SINK = 3
K_FOREIGN_SINK = 4
K_DMA_WRITE = 5


def initial_byte(offset: int) -> int:
    return (offset * 37 + 11) & 0xFF


def payload(value: int, size: int) -> bytes:
    return value.to_bytes(size, "big")


def initial_cells():
    return [
        {"value": initial_byte(i), "origin": "initial", "phase": 0, "context": 0, "writer_seq": 0}
        for i in range(4096)
    ]


def replay(history: dict, state: dict, enforce_contract: bool = True) -> dict:
    events = history["events"] if "events" in history else history
    assert events, "instrumented history is empty"
    assert [event["seq"] for event in events] == list(range(1, len(events) + 1)), "non-contiguous chronology"

    dmem = initial_cells()
    dram = {}
    active = None
    contexts = {}
    rsp_sink_count = cpu_sink_count = dma_write_count = 0
    same_value = []
    dma_sources = []

    for event in events:
        kind = event["kind"]
        if kind == K_INSN_BEGIN:
            assert active is None
            assert event["context"] == event["seq"] and event["context"] != 0
            active = event["context"]
            contexts[active] = (event["phase"], event["pc"], event["word"])
            continue
        if kind == K_INSN_END:
            assert active == event["context"] and active in contexts
            phase, pc, word = contexts[active]
            assert (event["phase"], event["pc"], event["word"]) == (phase, pc, word)
            active = None
            continue
        if kind == K_FOREIGN_SINK:
            raise AssertionError("unclassified out-of-instruction DMEM mutation")
        if kind in (K_RSP_SINK, K_CPU_SINK):
            if kind == K_RSP_SINK:
                assert active == event["context"] and active in contexts
                assert event["phase"] == contexts[active][0]
                origin = "rsp"
                rsp_sink_count += 1
            else:
                assert active is None and event["context"] == 0
                origin = "cpu"
                cpu_sink_count += 1
            assert event["bytes"] in (1, 2, 4, 8)
            data = payload(event["value"], event["bytes"])
            before = bytes(dmem[(event["offset"] + i) & 0xFFF]["value"] for i in range(event["bytes"]))
            if before == data:
                same_value.append(event["seq"])
            for i, byte in enumerate(data):
                dmem[(event["offset"] + i) & 0xFFF] = {
                    "value": byte,
                    "origin": origin,
                    "phase": event["phase"],
                    "context": event["context"],
                    "writer_seq": event["seq"],
                }
            continue
        if kind == K_DMA_WRITE:
            assert active is None
            assert event["bytes"] == 4
            delta = event["dram"] - event["dma_dram"]
            assert delta in (0, 4), "RDRAM effect not tied to current 8-byte fragment"
            expected_source = (event["dma_pbus"] + delta) & 0xFFF
            assert event["source"] == expected_source != 0xFFFF_FFFF
            source_cells = [copy.deepcopy(dmem[(expected_source + i) & 0xFFF]) for i in range(4)]
            source_payload = bytes(cell["value"] for cell in source_cells)
            # Integrity only: source identity above is descriptor-derived before
            # the payload is compared, so equal values cannot select an origin.
            assert source_payload == payload(event["value"], 4)
            for i, cell in enumerate(source_cells):
                dram[event["dram"] + i] = {
                    **cell,
                    "export_seq": event["seq"],
                    "source": (expected_source + i) & 0xFFF,
                }
            dma_sources.append((event["dram"], expected_source, event["dma_count"], event["dma_skip"]))
            dma_write_count += 1
            continue
        raise AssertionError(f"unknown event kind {kind}")

    assert active is None
    expected_dmem = bytes(cell["value"] for cell in dmem)
    assert hashlib.sha256(bytes(initial_byte(i) for i in range(4096))).hexdigest() == state["initial_dmem_sha256"]
    assert hashlib.sha256(expected_dmem).hexdigest() == state["dmem_sha256"]

    expected_destinations = [0x1000, 0x1004, 0x1010, 0x1014, 0x2000, 0x2004, 0x2008, 0x200C]
    got_destinations = [event["dram"] for event in events if event["kind"] == K_DMA_WRITE]
    assert got_destinations == expected_destinations
    expected_sources = [0x040, 0x044, 0x048, 0x04C, 0xFF8, 0xFFC, 0x000, 0x004]
    assert [source for _, source, _, _ in dma_sources] == expected_sources

    def word(address: int) -> int:
        return int.from_bytes(bytes(dram[address + i]["value"] for i in range(4)), "big")

    assert state["multi"] == [word(x) for x in (0x1000, 0x1004, 0x1010, 0x1014)]
    assert state["wrap"] == [word(x) for x in (0x2000, 0x2004, 0x2008, 0x200C)]

    # Reconstruct exactly the fixture-owned destination windows, including the
    # multi-row skip hole. Full RDRAM is retained as a neutrality checkpoint but
    # this bounded lineage trace does not pretend to explain unrelated traffic.
    scoped = bytearray(40)
    for address, cell in dram.items():
        if 0x1000 <= address < 0x1018:
            scoped[address - 0x1000] = cell["value"]
        elif 0x2000 <= address < 0x2010:
            scoped[24 + address - 0x2000] = cell["value"]
        else:
            raise AssertionError(f"unexpected DMA destination 0x{address:x}")
    assert hashlib.sha256(scoped).hexdigest() == state["egress_sha256"]
    assert state["rdram_bytes"] in (4 * 1024 * 1024, 8 * 1024 * 1024)

    if enforce_contract:
        phase1 = [event for event in events if event["kind"] == K_RSP_SINK and event["phase"] == 1]
        assert phase1 and any(event["seq"] in same_value for event in phase1), "same-value RSP store was not retained"
        assert dram[0x1000]["origin"] == "rsp" and dram[0x1000]["phase"] == 1
        assert all(dram[address]["origin"] == "initial" for address in (0x1001, 0x1002, 0x1003))
        assert all(dram[address]["origin"] == "rsp" and dram[address]["phase"] == 2 for address in range(0x1004, 0x1008))
        assert all(dram[address]["origin"] == "rsp" and dram[address]["phase"] == 3 for address in range(0x1010, 0x1014))
        assert all(dram[address]["origin"] == "cpu" and dram[address]["phase"] == 4 for address in range(0x1014, 0x1018))
        assert all(dram[address]["origin"] == "rsp" and dram[address]["phase"] == 5 for address in (0x2006, 0x2007, 0x2008, 0x2009))
        assert 0x1008 not in dram and 0x100C not in dram

    return {
        "events": len(events),
        "rsp_sinks": rsp_sink_count,
        "cpu_sinks": cpu_sink_count,
        "dma_word_writes": dma_write_count,
        "same_value_sink_seqs": same_value,
        "dma_sources": [{"dram": d, "dmem": s, "count": c, "skip": k} for d, s, c, k in dma_sources],
        "exported_rsp_bytes": sum(cell["origin"] == "rsp" for cell in dram.values()),
        "exported_cpu_bytes": sum(cell["origin"] == "cpu" for cell in dram.values()),
        "exported_initial_bytes": sum(cell["origin"] == "initial" for cell in dram.values()),
        "rdram_backing_bytes": state["rdram_bytes"],
        "scoped_egress_sha256": state["egress_sha256"],
    }


def _resequence(events: list[dict]) -> list[dict]:
    """Keep deletion forgeries nontrivial by repairing only ordinal/context IDs."""
    old_to_new = {}
    for new_seq, event in enumerate(events, 1):
        old_to_new[event["seq"]] = new_seq
    for new_seq, event in enumerate(events, 1):
        event["seq"] = new_seq
        if event["context"]:
            event["context"] = old_to_new.get(event["context"], event["context"])
    return events


def reject_forgeries(history: dict, state: dict) -> int:
    original = history["events"] if "events" in history else history
    cases = []

    same = next(i for i, e in enumerate(original) if e["kind"] == K_RSP_SINK and e["phase"] == 1)
    cpu = next(i for i, e in enumerate(original) if e["kind"] == K_CPU_SINK)
    vector = next(i for i, e in enumerate(original) if e["kind"] == K_RSP_SINK and e["phase"] == 3)
    dma = next(i for i, e in enumerate(original) if e["kind"] == K_DMA_WRITE)
    phase2 = next(i for i, e in enumerate(original) if e["kind"] == K_RSP_SINK and e["phase"] == 2)

    forged = copy.deepcopy(original); forged.pop(same); cases.append(_resequence(forged))
    forged = copy.deepcopy(original); forged[dma]["source"] ^= 4; cases.append(forged)
    forged = copy.deepcopy(original); forged[dma]["dma_pbus"] ^= 8; cases.append(forged)
    forged = copy.deepcopy(original); forged[cpu]["kind"] = K_FOREIGN_SINK; cases.append(forged)
    forged = copy.deepcopy(original); forged.pop(cpu); cases.append(_resequence(forged))
    forged = copy.deepcopy(original); forged[phase2]["context"] += 1; cases.append(forged)
    forged = copy.deepcopy(original); forged[vector]["value"] ^= 1; cases.append(forged)
    forged = copy.deepcopy(original); forged[dma]["dram"] = 0x1008; cases.append(forged)
    forged = copy.deepcopy(original); forged[0]["seq"] = 2; cases.append(forged)

    rejected = 0
    for events in cases:
        try:
            replay({"events": events}, state, enforce_contract=True)
        except (AssertionError, KeyError, ValueError):
            rejected += 1
    assert rejected == len(cases), (rejected, len(cases))
    return rejected
