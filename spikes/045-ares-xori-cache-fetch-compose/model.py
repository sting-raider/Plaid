#!/usr/bin/env python3
"""Deterministic generation replay for CPU XORI -> cache -> executable fetch composition.

This is not an emulator. It composes source-established contracts and deliberately
rejects payload-only provenance joins.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(__file__).resolve().parents[2] / "target/xori-cache-fetch-compose"
OLD = 0x24020001
NEW = 0x24020002
TARGET = 0x2000
SOURCE = 0x1000
DECOY = 0x1100


def build_scenario(name: str, imm: int, *, foreign: bool = False, prefill_before_writeback: bool = False):
    source_word = NEW ^ imm
    events = []
    next_gen = 1
    backing = {}
    regs = {}
    dcache = {}
    icache = {}

    def mint(kind, tag, **fields):
        nonlocal next_gen
        ev = {"seq": len(events) + 1, "kind": kind, "tag": tag, "gen": next_gen, **fields}
        next_gen += 1
        events.append(ev)
        return ev["gen"]

    def action(kind, tag, **fields):
        events.append({"seq": len(events) + 1, "kind": kind, "tag": tag, **fields})

    backing[TARGET] = mint("seed_backing", "target_old", address=TARGET, value=OLD, origin="old_program")
    backing[SOURCE] = mint("seed_backing", "source_actual", address=SOURCE, value=source_word, origin="source_actual")
    backing[DECOY] = mint("seed_backing", "source_decoy", address=DECOY, value=source_word, origin="source_decoy")

    icache[TARGET] = mint("icache_fill", "initial_fill", address=TARGET, value=OLD, from_gen=backing[TARGET])
    action("fetch", "initial_fetch", address=TARGET, value=OLD, resident_gen=icache[TARGET])

    regs["t1"] = mint("load", "decoy_load", reg="t1", address=DECOY, value=source_word, from_gen=backing[DECOY])
    regs["t0"] = mint("load", "actual_load", reg="t0", address=SOURCE, value=source_word, from_gen=backing[SOURCE])
    regs["t0"] = mint("xori", "transform", reg="t0", imm=imm, value=NEW, from_gen=regs["t0"])
    dcache[TARGET] = mint("dcache_store", "cached_store", address=TARGET, value=NEW, from_gen=regs["t0"])
    action("fetch", "after_cached_store", address=TARGET, value=OLD, resident_gen=icache[TARGET])

    if prefill_before_writeback:
        action("icache_invalidate", "pre_writeback_invalidate", address=TARGET, old_gen=icache[TARGET])
        del icache[TARGET]
        icache[TARGET] = mint("icache_fill", "pre_writeback_fill", address=TARGET, value=OLD, from_gen=backing[TARGET])
        action("fetch", "pre_writeback_refetch", address=TARGET, value=OLD, resident_gen=icache[TARGET])

    backing[TARGET] = mint("dcache_writeback", "writeback", address=TARGET, value=NEW, from_gen=dcache[TARGET])
    action("fetch", "after_writeback", address=TARGET, value=OLD, resident_gen=icache[TARGET])

    if foreign:
        # The bits do not change, but the backing writer generation does.
        backing[TARGET] = mint("uncached_store", "foreign_same_value_store", address=TARGET, value=NEW, origin="foreign")

    if not prefill_before_writeback:
        action("icache_invalidate", "post_writeback_invalidate", address=TARGET, old_gen=icache[TARGET])
        del icache[TARGET]
        icache[TARGET] = mint("icache_fill", "post_writeback_fill", address=TARGET, value=NEW, from_gen=backing[TARGET])
        action("fetch", "final_fetch", address=TARGET, value=NEW, resident_gen=icache[TARGET])
    else:
        # The valid line was filled before writeback and remains old afterwards.
        action("fetch", "final_fetch", address=TARGET, value=OLD, resident_gen=icache[TARGET])

    return {
        "name": name,
        "imm": imm,
        "source_word": source_word,
        "old_word": OLD,
        "new_word": NEW,
        "events": events,
    }


def replay(scenario):
    backing = {}
    regs = {}
    dcache = {}
    icache = {}
    generations = {}
    fetches = {}
    seen = set()

    for seq, ev in enumerate(scenario["events"], 1):
        assert ev["seq"] == seq
        kind = ev["kind"]
        tag = ev["tag"]
        if "gen" in ev:
            assert ev["gen"] not in seen
            seen.add(ev["gen"])

        if kind == "seed_backing":
            assert ev["address"] not in backing
            backing[ev["address"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": None, "origin": ev["origin"]}
        elif kind == "load":
            assert backing.get(ev["address"]) == ev["from_gen"]
            assert generations[ev["from_gen"]]["value"] == ev["value"]
            regs[ev["reg"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": ev["from_gen"], "origin": tag}
        elif kind == "xori":
            assert regs.get(ev["reg"]) == ev["from_gen"]
            assert (generations[ev["from_gen"]]["value"] ^ ev["imm"]) & 0xFFFFFFFF == ev["value"]
            regs[ev["reg"]] = ev["gen"]
            generations[ev["gen"]] = {
                "kind": kind,
                "value": ev["value"],
                "parent": ev["from_gen"],
                "origin": tag,
                "imm": ev["imm"],
            }
        elif kind == "dcache_store":
            assert regs.get("t0") == ev["from_gen"]
            assert generations[ev["from_gen"]]["value"] == ev["value"]
            dcache[ev["address"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": ev["from_gen"], "origin": tag}
        elif kind == "dcache_writeback":
            assert dcache.get(ev["address"]) == ev["from_gen"]
            assert generations[ev["from_gen"]]["value"] == ev["value"]
            backing[ev["address"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": ev["from_gen"], "origin": tag}
        elif kind == "uncached_store":
            # Fixture-scoped foreign writer. Same value still creates a new generation.
            backing[ev["address"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": None, "origin": ev["origin"]}
        elif kind == "icache_fill":
            assert backing.get(ev["address"]) == ev["from_gen"]
            assert generations[ev["from_gen"]]["value"] == ev["value"]
            icache[ev["address"]] = ev["gen"]
            generations[ev["gen"]] = {"kind": kind, "value": ev["value"], "parent": ev["from_gen"], "origin": tag}
        elif kind == "icache_invalidate":
            assert icache.get(ev["address"]) == ev["old_gen"]
            del icache[ev["address"]]
        elif kind == "fetch":
            assert icache.get(ev["address"]) == ev["resident_gen"]
            assert generations[ev["resident_gen"]]["value"] == ev["value"]
            fetches[tag] = ev["resident_gen"]
        else:
            raise AssertionError(kind)

    return generations, fetches


def ancestors(generations, generation):
    out = []
    while generation is not None:
        out.append(generation)
        generation = generations[generation]["parent"]
    return out


def by_tag(scenario, tag):
    return next(ev for ev in scenario["events"] if ev["tag"] == tag)


def expect_rejected(name, scenario):
    try:
        replay(scenario)
    except (AssertionError, KeyError):
        return name
    raise AssertionError(f"forged history accepted: {name}")


def main():
    scenarios = {
        "normal": build_scenario("normal", 0x00FF),
        "foreign": build_scenario("foreign", 0x00FF, foreign=True),
        "prefill": build_scenario("prefill", 0x00FF, prefill_before_writeback=True),
        "identity": build_scenario("identity", 0x0000),
    }

    summary = {}
    for name, scenario in scenarios.items():
        generations, fetches = replay(scenario)
        tags = {ev["tag"]: ev.get("gen") for ev in scenario["events"] if "gen" in ev}
        final = fetches["final_fetch"]
        chain = ancestors(generations, final)
        summary[name] = {
            "events": len(scenario["events"]),
            "source_word": scenario["source_word"],
            "final_word": generations[final]["value"],
            "final_chain": chain,
            "transform_gen": tags["transform"],
            "transform_reaches_final_fetch": tags["transform"] in chain,
            "foreign_gen": tags.get("foreign_same_value_store"),
        }

    assert summary["normal"]["transform_reaches_final_fetch"]
    assert summary["identity"]["transform_reaches_final_fetch"]
    assert scenarios["identity"]["source_word"] == NEW
    assert by_tag(scenarios["identity"], "actual_load")["value"] == by_tag(scenarios["identity"], "transform")["value"]
    assert by_tag(scenarios["identity"], "actual_load")["gen"] != by_tag(scenarios["identity"], "transform")["gen"]
    assert not summary["foreign"]["transform_reaches_final_fetch"]
    assert summary["foreign"]["final_word"] == NEW
    assert not summary["prefill"]["transform_reaches_final_fetch"]
    assert summary["prefill"]["final_word"] == OLD

    # Deliberately naive rule: if a previous XORI output equals final fetched bits,
    # attribute the fetch to that transform. It is false in the foreign-writer case.
    naive_false_positive = (
        by_tag(scenarios["foreign"], "transform")["value"]
        == by_tag(scenarios["foreign"], "final_fetch")["value"]
        and not summary["foreign"]["transform_reaches_final_fetch"]
    )
    assert naive_false_positive

    rejected = []

    forged = copy.deepcopy(scenarios["normal"])
    by_tag(forged, "transform")["from_gen"] = by_tag(forged, "decoy_load")["gen"]
    rejected.append(expect_rejected("equal_payload_decoy_transform_input", forged))

    forged = copy.deepcopy(scenarios["identity"])
    by_tag(forged, "cached_store")["from_gen"] = by_tag(forged, "actual_load")["gen"]
    rejected.append(expect_rejected("identity_xori_generation_collapsed", forged))

    forged = copy.deepcopy(scenarios["normal"])
    by_tag(forged, "post_writeback_fill")["from_gen"] = by_tag(forged, "target_old")["gen"]
    rejected.append(expect_rejected("stale_backing_generation_on_post_writeback_fill", forged))

    forged = copy.deepcopy(scenarios["prefill"])
    by_tag(forged, "pre_writeback_fill")["from_gen"] = by_tag(forged, "writeback")["gen"]
    rejected.append(expect_rejected("future_writeback_used_by_earlier_fill", forged))

    forged = copy.deepcopy(scenarios["foreign"])
    by_tag(forged, "post_writeback_fill")["from_gen"] = by_tag(forged, "writeback")["gen"]
    rejected.append(expect_rejected("same_value_foreign_writer_erased", forged))

    forged = copy.deepcopy(scenarios["normal"])
    by_tag(forged, "after_writeback")["resident_gen"] = by_tag(forged, "writeback")["gen"]
    rejected.append(expect_rejected("backing_generation_forged_as_icache_resident", forged))

    forged = copy.deepcopy(scenarios["normal"])
    forged["events"] = [ev for ev in forged["events"] if ev["tag"] != "writeback"]
    for seq, ev in enumerate(forged["events"], 1):
        ev["seq"] = seq
    rejected.append(expect_rejected("missing_writeback_kept_fill_claim", forged))

    forged = copy.deepcopy(scenarios["foreign"])
    events = forged["events"]
    a = next(i for i, ev in enumerate(events) if ev["tag"] == "writeback")
    b = next(i for i, ev in enumerate(events) if ev["tag"] == "foreign_same_value_store")
    events[a], events[b] = events[b], events[a]
    for seq, ev in enumerate(events, 1):
        ev["seq"] = seq
    rejected.append(expect_rejected("reordered_same_value_writers", forged))

    report = {
        "result": "PASS",
        "scenarios": summary,
        "naive_payload_false_positive": naive_false_positive,
        "forgeries_rejected": rejected,
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "model-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    print("MODEL_SHA256=" + digest)
    print("PASS: transform provenance survives only exact resident/backing generations; equal payloads do not bridge writer changes")


if __name__ == "__main__":
    main()
