#!/usr/bin/env python3
"""Replay executable IMEM writer generations through completed reverse SP DMA."""
from __future__ import annotations

import copy
import hashlib

K_IMEM_SINK = 1
K_DMA_WRITE = 2
K_OTHER_RDRAM_WRITE = 3


def initial_byte(offset: int) -> int:
    return (offset * 29 + 7) & 0xFF


def payload(value: int, size: int) -> bytes:
    return value.to_bytes(size, "big")


def initial_cells():
    return [
        {"value": initial_byte(i), "origin": "initial", "phase": 0, "writer_seq": 0}
        for i in range(4096)
    ]


def replay(history: dict, state: dict, enforce_contract: bool = True) -> dict:
    events = history["events"] if "events" in history else history
    assert events, "instrumented history is empty"
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1)), "non-contiguous chronology"

    imem = initial_cells()
    resident = {}
    exports = {}
    same_value = []
    dma_sources = []
    imem_sinks = dma_writes = other_writes = 0

    for event in events:
        kind = event["kind"]
        if kind == K_IMEM_SINK:
            assert event["region"] == 1 and event["bytes"] == 4 and event["cpu"] is True
            assert event["offset"] & 3 == 0
            data = payload(event["value"], 4)
            before = bytes(imem[(event["offset"] + i) & 0xFFF]["value"] for i in range(4))
            if before == data:
                same_value.append(event["seq"])
            for i, byte in enumerate(data):
                imem[(event["offset"] + i) & 0xFFF] = {
                    "value": byte,
                    "origin": "cpu_imem",
                    "phase": event["phase"],
                    "writer_seq": event["seq"],
                }
            imem_sinks += 1
            continue

        if kind == K_DMA_WRITE:
            assert event["bytes"] == 8
            assert event["dma_region"] == 1 and event["region"] == 1
            assert event["dram"] == event["dma_dram"]
            expected_source = event["dma_pbus"] & 0xFF8
            assert event["source"] == expected_source != 0xFFFF_FFFF
            cells = [copy.deepcopy(imem[(expected_source + i) & 0xFFF]) for i in range(8)]
            data = bytes(cell["value"] for cell in cells)
            # Payload is only an integrity check after descriptor-selected source
            # identity. Equal bytes elsewhere in IMEM cannot select provenance.
            assert data == payload(event["value"], 8)
            for i, cell in enumerate(cells):
                exported = {
                    **cell,
                    "export_seq": event["seq"],
                    "source": (expected_source + i) & 0xFFF,
                    "source_region": 1,
                    "rdram_origin": "sp_dma",
                }
                resident[event["dram"] + i] = copy.deepcopy(exported)
                exports[event["dram"] + i] = copy.deepcopy(exported)
            dma_sources.append((event["dram"], expected_source, event["dma_region"], event["dma_count"], event["dma_skip"]))
            dma_writes += 1
            continue

        if kind == K_OTHER_RDRAM_WRITE:
            assert event["bytes"] in (1, 2, 4, 8)
            data = payload(event["value"], event["bytes"])
            for i, byte in enumerate(data):
                address = event["dram"] + i
                assert (0x1000 <= address < 0x1018) or (0x2000 <= address < 0x2010)
                resident[address] = {
                    "value": byte,
                    "origin": "other_rdram",
                    "phase": event["phase"],
                    "writer_seq": event["seq"],
                    "rdram_origin": "other",
                }
            other_writes += 1
            continue

        raise AssertionError(f"unknown event kind {kind}")

    expected_initial = bytes(initial_byte(i) for i in range(4096))
    assert hashlib.sha256(expected_initial).hexdigest() == state["initial_imem_sha256"]
    expected_final = bytes(cell["value"] for cell in imem)
    assert hashlib.sha256(expected_final).hexdigest() == state["imem_sha256"]

    expected_destinations = [0x1000, 0x1010, 0x2000, 0x2008]
    expected_sources = [0x040, 0x048, 0xFF8, 0x000]
    assert [d for d, _, _, _, _ in dma_sources] == expected_destinations
    assert [s for _, s, _, _, _ in dma_sources] == expected_sources
    assert all(region == 1 for _, _, region, _, _ in dma_sources)

    def current_byte(address: int) -> int:
        return resident.get(address, {"value": 0})["value"]

    def word(address: int) -> int:
        return int.from_bytes(bytes(current_byte(address + i) for i in range(4)), "big")

    assert state["multi"] == [word(x) for x in (0x1000, 0x1004, 0x1010, 0x1014)]
    assert state["wrap"] == [word(x) for x in (0x2000, 0x2004, 0x2008, 0x200C)]

    scoped = bytearray(40)
    for address, cell in resident.items():
        if 0x1000 <= address < 0x1018:
            scoped[address - 0x1000] = cell["value"]
        elif 0x2000 <= address < 0x2010:
            scoped[24 + address - 0x2000] = cell["value"]
        else:
            raise AssertionError(f"unexpected tracked destination 0x{address:x}")
    assert hashlib.sha256(scoped).hexdigest() == state["egress_sha256"]
    assert state["rdram_bytes"] in (4 * 1024 * 1024, 8 * 1024 * 1024)

    first_dma = next(e for e in events if e["kind"] == K_DMA_WRITE and e["dram"] == 0x1000)
    first_payload = payload(first_dma["value"], 8)
    decoy_payload = bytes(imem[(0x080 + i) & 0xFFF]["value"] for i in range(8))
    equal_payload_decoy = first_payload == decoy_payload

    if enforce_contract:
        phase1 = [e for e in events if e["kind"] == K_IMEM_SINK and e["phase"] == 1]
        assert len(phase1) == 1 and phase1[0]["seq"] in same_value, "same-value executable rewrite lost"
        assert equal_payload_decoy, "fixture failed to create equal-payload decoy"
        assert all(exports[a]["phase"] == 1 for a in range(0x1000, 0x1004))
        assert all(exports[a]["phase"] == 2 for a in range(0x1004, 0x1008))
        assert all(exports[a]["phase"] == 2 for a in range(0x1010, 0x1018))
        assert all(exports[a]["phase"] == 4 for a in range(0x2000, 0x2010))
        assert all(exports[a]["source_region"] == 1 for a in exports)
        assert [exports[a]["source"] for a in range(0x2008, 0x2010)] == list(range(0x000, 0x008))
        assert state["dmem_wrap"] != state["wrap"][2:4], "bank-edge discriminator accidentally equal"
        assert 0x1008 not in exports and 0x100F not in exports
        # Decoy writers exist and are newer than the true first source, but the
        # descriptor still selects 0x040 rather than equal-valued 0x080.
        decoys = [e for e in events if e["kind"] == K_IMEM_SINK and e["phase"] == 3]
        assert len(decoys) == 2 and all(e["seq"] < first_dma["seq"] for e in decoys)
        assert first_dma["source"] == 0x040

    return {
        "events": len(events),
        "imem_word_sinks": imem_sinks,
        "dma_dual_writes": dma_writes,
        "other_rdram_writes": other_writes,
        "same_value_sink_seqs": same_value,
        "equal_payload_decoy": equal_payload_decoy,
        "dma_sources": [
            {"dram": d, "imem": s, "region": r, "count": c, "skip": k}
            for d, s, r, c, k in dma_sources
        ],
        "exported_cpu_imem_bytes": sum(cell["origin"] == "cpu_imem" for cell in exports.values()),
        "exported_initial_bytes": sum(cell["origin"] == "initial" for cell in exports.values()),
        "scoped_egress_sha256": state["egress_sha256"],
        "bank_wrap_second_source": {"region": 1, "offset": 0x000},
    }


def _resequence(events: list[dict]) -> list[dict]:
    for seq, event in enumerate(events, 1):
        event["seq"] = seq
    return events


def reject_forgeries(history: dict, state: dict) -> int:
    original = history["events"] if "events" in history else history
    cases = []
    same = next(i for i, e in enumerate(original) if e["kind"] == K_IMEM_SINK and e["phase"] == 1)
    changed = next(i for i, e in enumerate(original) if e["kind"] == K_IMEM_SINK and e["phase"] == 2)
    first_dma = next(i for i, e in enumerate(original) if e["kind"] == K_DMA_WRITE and e["dram"] == 0x1000)
    wrap_second = next(i for i, e in enumerate(original) if e["kind"] == K_DMA_WRITE and e["dram"] == 0x2008)

    forged = copy.deepcopy(original); forged.pop(same); cases.append(_resequence(forged))
    # Equal-valued decoy forgery: payload still matches, source/descriptor do not.
    forged = copy.deepcopy(original); forged[first_dma]["source"] = 0x080; forged[first_dma]["dma_pbus"] = 0x080; cases.append(forged)
    forged = copy.deepcopy(original); forged[first_dma]["dma_region"] = 0; forged[first_dma]["region"] = 0; cases.append(forged)
    forged = copy.deepcopy(original); forged[wrap_second]["dma_region"] = 0; forged[wrap_second]["region"] = 0; cases.append(forged)
    forged = copy.deepcopy(original); forged[wrap_second]["source"] = 0xFF8; cases.append(forged)
    forged = copy.deepcopy(original); forged.pop(changed); cases.append(_resequence(forged))
    forged = copy.deepcopy(original); forged[first_dma]["dram"] = 0x1008; cases.append(forged)
    forged = copy.deepcopy(original); forged[first_dma]["value"] ^= 1; cases.append(forged)
    forged = copy.deepcopy(original); forged[0]["seq"] = 2; cases.append(forged)

    rejected = 0
    for events in cases:
        try:
            replay({"events": events}, state, enforce_contract=True)
        except (AssertionError, KeyError, ValueError):
            rejected += 1
    assert rejected == len(cases), (rejected, len(cases))
    return rejected
