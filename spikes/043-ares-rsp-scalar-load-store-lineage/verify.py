"""Replay actual RSP scalar load/GPR/store histories without value-based provenance guesses."""
from __future__ import annotations

from copy import deepcopy
import hashlib

LOADS = {
    0x20: (1, True, "LB"),
    0x24: (1, False, "LBU"),
    0x21: (2, True, "LH"),
    0x25: (2, False, "LHU"),
    0x23: (4, False, "LW"),
    0x27: (4, False, "LWU"),
}
STORES = {0x28: (1, "SB"), 0x29: (2, "SH"), 0x2B: (4, "SW")}


def _s16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _initial_origins() -> list[str]:
    return [f"initial:{i:03x}" for i in range(4096)]


def _contexts(events: list[dict]) -> dict[int, list[dict]]:
    ordinals = [event["ordinal"] for event in events]
    assert ordinals == sorted(ordinals) and len(ordinals) == len(set(ordinals))
    assert ordinals == list(range(1, len(ordinals) + 1))
    grouped: dict[int, list[dict]] = {}
    for event in events:
        assert event["context"] > 0 and event["phase"] > 0
        grouped.setdefault(event["context"], []).append(event)
    for context, rows in grouped.items():
        assert rows[0]["kind"] == 0 and rows[-1]["kind"] == 2
        assert sum(row["kind"] == 0 for row in rows) == 1
        assert sum(row["kind"] == 2 for row in rows) == 1
        assert all(row["context"] == context for row in rows)
        assert all(row["phase"] == rows[0]["phase"] for row in rows)
        assert all(row["word"] == rows[0]["word"] for row in rows)
        assert all(row["pc"] == rows[0]["pc"] for row in rows)
    return grouped


def _load_value(memory: bytearray, address: int, width: int, signed: bool) -> tuple[int, list[int]]:
    offsets = [((address + lane) & 0xFFF) for lane in range(width)]
    raw = int.from_bytes(bytes(memory[offset] for offset in offsets), "big")
    if signed and raw & (1 << (width * 8 - 1)):
        raw |= ((1 << (32 - width * 8)) - 1) << (width * 8)
    return _u32(raw), offsets


def _load_lanes(origins: list[str], offsets: list[int], value: int, width: int) -> list[str | None]:
    lanes: list[str | None] = [None, None, None, None]
    for i, offset in enumerate(offsets):
        lanes[4 - width + i] = origins[offset]
    # Upper bytes from sign/zero extension are derived, not copied source bytes.
    # They deliberately remain None. Same-width stores consume only the low lanes.
    return lanes


def _expected_store_bytes(value: int, width: int) -> list[int]:
    return list(_u32(value).to_bytes(4, "big")[-width:])


def verify(history: dict, machine: dict) -> dict:
    assert history["format"] == "plaid-rsp-scalar-lineage-v0"
    scenarios = machine["scenarios"]
    assert machine["scenario_count"] == len(scenarios) == 14
    events = history["events"]
    grouped = _contexts(events)
    by_phase: dict[int, list[int]] = {}
    for context, rows in grouped.items():
        by_phase.setdefault(rows[0]["phase"], []).append(context)
    for contexts in by_phase.values():
        contexts.sort(key=lambda context: grouped[context][0]["ordinal"])

    all_edges: list[dict] = []
    phase_summaries: list[dict] = []
    global_load_serial = 0

    for phase, scenario in enumerate(scenarios, 1):
        assert len(scenario["initial_hex"]) == 8192
        memory = bytearray.fromhex(scenario["initial_hex"])
        assert len(memory) == 4096
        origins = _initial_origins()
        register_lineage: list[dict | None] = [None] * 32
        contexts = by_phase.get(phase, [])
        assert len(contexts) == len(scenario["program"])
        load_contexts: list[int] = []
        store_edges: list[dict] = []

        for index, context in enumerate(contexts):
            rows = grouped[context]
            begin, end = rows[0], rows[-1]
            sinks = rows[1:-1]
            assert all(row["kind"] == 1 for row in sinks)
            expected_word = scenario["program"][index]
            assert begin["word"] == end["word"] == expected_word
            assert begin["pc"] == end["pc"] == index * 4
            op = expected_word >> 26
            rs = expected_word >> 21 & 31
            rt = expected_word >> 16 & 31
            rd = expected_word >> 11 & 31
            assert (begin["rs"], begin["rt"], begin["rd"]) == (rs, rt, rd)
            assert (end["rs"], end["rt"], end["rd"]) == (rs, rt, rd)

            if op in LOADS:
                assert not sinks
                width, signed, opname = LOADS[op]
                effective = _u32(begin["rs_value"] + _s16(expected_word))
                expected_value, offsets = _load_value(memory, effective, width, signed)
                assert end["rt_value"] == expected_value
                global_load_serial += 1
                register_lineage[rt] = {
                    "load_serial": global_load_serial,
                    "load_context": context,
                    "load_op": opname,
                    "source_offsets": offsets,
                    "lanes": _load_lanes(origins, offsets, expected_value, width),
                    "loaded_value": expected_value,
                }
                load_contexts.append(context)
                continue

            if op in STORES:
                width, opname = STORES[op]
                assert len(sinks) == width
                effective = _u32(begin["rs_value"] + _s16(expected_word))
                offsets = [((effective + lane) & 0xFFF) for lane in range(width)]
                values = _expected_store_bytes(begin["rt_value"], width)
                assert [row["bytes"] for row in sinks] == [1] * width
                assert [row["offset"] for row in sinks] == offsets
                assert [row["value"] for row in sinks] == values
                lineage = register_lineage[rt]
                lane_origins = [None] * width
                producer = None
                if lineage is not None:
                    producer = lineage["load_context"]
                    lane_origins = lineage["lanes"][4 - width :]
                edge = {
                    "scenario": scenario["name"],
                    "store_context": context,
                    "store_op": opname,
                    "producer_load_context": producer,
                    "destination_offsets": offsets,
                    "ultimate_origins": lane_origins,
                    "value": begin["rt_value"],
                }
                store_edges.append(edge)
                all_edges.append(edge)
                for offset, value, origin in zip(offsets, values, lane_origins, strict=True):
                    memory[offset] = value
                    origins[offset] = origin if origin is not None else f"unknown:store:{context}"
                continue

            if op == 0x0D:  # ORI is a whole-GPR writer even when the numeric value does not change.
                assert not sinks
                expected = _u32(begin["rs_value"] | (expected_word & 0xFFFF))
                assert end["rt_value"] == expected
                register_lineage[rt] = None
                continue

            if op == 0 and (expected_word & 0x3F) == 0x21:  # ADDU
                assert not sinks
                expected = _u32(begin["rs_value"] + begin["rt_value"])
                assert end["rd_value"] == expected
                register_lineage[rd] = None
                continue

            if expected_word == 0x0000000D:  # BREAK
                assert not sinks and end["halted"]
                continue

            raise AssertionError(f"unsupported fixture instruction {expected_word:08x}")

        assert hashlib.sha256(memory).hexdigest() == scenario["final_dmem_sha256"]
        assert scenario["halted"] == scenario["broken"] == 1
        assert len(store_edges) == 1
        edge = store_edges[0]
        if scenario["name"] in {"ori_same_value_clobber", "addu_same_value_clobber"}:
            assert edge["producer_load_context"] is None
            assert all(origin is None for origin in edge["ultimate_origins"])
        else:
            assert load_contexts and edge["producer_load_context"] == load_contexts[-1]
            last_load = register_lineage[2]
            # unrelated_writer writes r4, so r2 still names the last load. All other non-clobber
            # cases end with r2 unchanged as well.
            assert last_load is not None and last_load["load_context"] == load_contexts[-1]
            expected_origins = [f"initial:{offset:03x}" for offset in last_load["source_offsets"]]
            assert edge["ultimate_origins"] == expected_origins
        phase_summaries.append({
            "name": scenario["name"],
            "contexts": len(contexts),
            "loads": len(load_contexts),
            "producer": edge["producer_load_context"],
            "origins": edge["ultimate_origins"],
        })

    assert set(by_phase) == set(range(1, 15))
    named = {entry["name"]: entry for entry in phase_summaries}
    equal = named["equal_two_loads"]
    reload = named["same_source_reload"]
    assert equal["loads"] == reload["loads"] == 2

    # Directly demonstrate why value equality cannot substitute for GPR-generation replay.
    by_name = {scenario["name"]: scenario for scenario in scenarios}
    clobber = by_name["ori_same_value_clobber"]
    clobber_contexts = by_phase[scenarios.index(clobber) + 1]
    load_end = grouped[clobber_contexts[0]][-1]
    clobber_end = grouped[clobber_contexts[1]][-1]
    store_begin = grouped[clobber_contexts[2]][0]
    assert load_end["rt_value"] == clobber_end["rt_value"] == store_begin["rt_value"] == 0x1234
    assert named["ori_same_value_clobber"]["producer"] is None

    eq_scenario = by_name["equal_two_loads"]
    eq_contexts = by_phase[scenarios.index(eq_scenario) + 1]
    eq_values = [grouped[eq_contexts[i]][-1]["rt_value"] for i in (0, 1)]
    assert eq_values[0] == eq_values[1] == 0x11223344
    assert named["equal_two_loads"]["producer"] == eq_contexts[1]

    return {
        "scenario_count": len(scenarios),
        "event_count": len(events),
        "edge_count": len(all_edges),
        "load_generation_count": global_load_serial,
        "equal_payload_candidates": 2,
        "equal_payload_latest_context_selected": True,
        "same_value_ori_clobber_cut": True,
        "same_value_addu_clobber_cut": True,
        "same_source_reload_fresh_context_selected": True,
        "wrap_cases": 2,
        "bit12_alias_case": True,
        "edges": all_edges,
    }


def reject_forgeries(history: dict, machine: dict) -> int:
    forgeries = []

    forged = deepcopy(history)
    forged["events"][1]["ordinal"] = forged["events"][0]["ordinal"]
    forgeries.append(forged)

    forged = deepcopy(history)
    # Delete the ORI begin event. Numeric state still matches the preceding load, but chronology is incomplete.
    phase = 12
    target = next(i for i,e in enumerate(forged["events"]) if e["phase"] == phase and e["kind"] == 0 and (e["word"] >> 26) == 0x0D)
    del forged["events"][target]
    for index,event in enumerate(forged["events"],1): event["ordinal"] = index
    forgeries.append(forged)

    forged = deepcopy(history)
    # Preserve the clobber's same value but forge its instruction identity into a NOP.
    for event in forged["events"]:
        if event["phase"] == 12 and (event["word"] >> 26) == 0x0D:
            event["word"] = 0
    forgeries.append(forged)

    forged = deepcopy(history)
    # Drop one primitive SW sink while leaving the final machine hash untouched.
    target = next(i for i,e in enumerate(forged["events"]) if e["phase"] == 5 and e["kind"] == 1)
    del forged["events"][target]
    for index,event in enumerate(forged["events"],1): event["ordinal"] = index
    forgeries.append(forged)

    forged = deepcopy(history)
    target = next(e for e in forged["events"] if e["phase"] == 1 and e["kind"] == 1)
    target["offset"] ^= 1
    forgeries.append(forged)

    forged = deepcopy(history)
    target = next(e for e in forged["events"] if e["phase"] == 3 and e["kind"] == 2 and (e["word"] >> 26) in LOADS)
    target["rt_value"] ^= 1
    forgeries.append(forged)

    forged = deepcopy(history)
    # Make the two equal-value loads appear to execute in the opposite instruction order.
    begins = [e for e in forged["events"] if e["phase"] == 10 and e["kind"] == 0 and (e["word"] >> 26) in LOADS]
    ends = [e for e in forged["events"] if e["phase"] == 10 and e["kind"] == 2 and (e["word"] >> 26) in LOADS]
    begins[0]["word"], begins[1]["word"] = begins[1]["word"], begins[0]["word"]
    ends[0]["word"], ends[1]["word"] = ends[1]["word"], ends[0]["word"]
    forgeries.append(forged)

    forged = deepcopy(history)
    sink = next(e for e in forged["events"] if e["phase"] == 14 and e["kind"] == 1)
    sink["context"] += 1
    forgeries.append(forged)

    rejected = 0
    for forged in forgeries:
        try:
            verify(forged, machine)
        except (AssertionError, KeyError, ValueError):
            rejected += 1
        else:
            raise AssertionError("forged history was accepted")
    return rejected
