#!/usr/bin/env python3
"""Strict byte-lineage replay for the composed RSP DMEM -> SP DMA -> RDRAM -> CPU fetch fixture."""
from copy import deepcopy


class VerifyError(AssertionError):
    pass


def need(cond, msg):
    if not cond:
        raise VerifyError(msg)


def bytes_be(value, width):
    return int(value).to_bytes(width, "big")


def verify(history, machine):
    need(history.get("format") == "plaid-rsp-dmem-spdma-rdram-fetch-v0", "format")
    cases = {c["phase"]: c for c in machine["cases"]}
    need(sorted(cases) == [1, 2, 3, 4], "case phases")

    # Instruction contexts are explicit. A DMEM sink is accepted only inside the
    # begin/end pair that created its context token.
    bounds = {}
    for e in history["rsp_instructions"]:
        key = (e["phase"], e["context"])
        if e["begin"]:
            need(key not in bounds, "duplicate context begin")
            need(e["context"] == e["ordinal"], "context is not begin ordinal")
            bounds[key] = [e, None]
        else:
            need(key in bounds and bounds[key][1] is None, "orphan context end")
            bounds[key][1] = e
    need(all(end is not None for _, end in bounds.values()), "unterminated context")

    # This fixture intentionally composes the already-validated RSP primitive
    # sink boundary. Scalar SW reaches that boundary as four byte writes, not as
    # one synthetic word event. Keeping the primitive events is what lets writer
    # generation remain distinct even when all four payload bytes are unchanged.
    need(all(e["bytes"] == 1 and 0 <= e["value"] < 256 for e in history["rsp_sinks"]),
         "fixture expected primitive byte sinks")

    sink_counts = {p: 0 for p in cases}
    fetch_origins = {}
    fetch_read_ord = {}
    phase_stats = {}

    for phase, case in cases.items():
        initial = bytes_be(case["initial_word"], 4) + b"\0\0\0\0"
        dmem_values = list(initial)
        dmem_origins = [
            {"kind": "initial", "phase": phase, "offset": i} for i in range(8)
        ]
        rdram_values = {}
        rdram_origins = {}
        target = case["target"]
        source = case["source"]

        events = []
        events += [(e["ordinal"], "sink", e) for e in history["rsp_sinks"] if e["phase"] == phase]
        events += [(e["ordinal"], "rdram", e) for e in history["rdram"] if e["phase"] == phase]
        events += [(e["ordinal"], "fetch", e) for e in history["fetch"] if e["phase"] == phase]
        events.sort(key=lambda x: x[0])
        need(len({x[0] for x in events}) == len(events), f"phase {phase} duplicate ordinal")

        fetch_begin = fetch_end = None
        sp_dma_writes = 0
        cpu_writes = 0
        fetch_reads = 0
        latest_sink_context = None

        for ordinal, kind, e in events:
            if kind == "sink":
                sink_counts[phase] += 1
                key = (phase, e["context"])
                need(key in bounds, f"phase {phase} sink context missing")
                begin, end = bounds[key]
                need(begin["ordinal"] < ordinal < end["ordinal"], f"phase {phase} sink outside context")
                need(begin["pc"] == e["pc"] and begin["word"] == e["word"], f"phase {phase} sink context mismatch")
                width = e["bytes"]
                data = bytes_be(e["value"], width)
                for i, byte in enumerate(data):
                    off = (e["offset"] + i) & 0xfff
                    if source <= off < source + 8:
                        j = off - source
                        dmem_values[j] = byte
                        dmem_origins[j] = {
                            "kind": "rsp_sink",
                            "phase": phase,
                            "context": e["context"],
                            "event": ordinal,
                            "offset": off,
                        }
                latest_sink_context = e["context"]

            elif kind == "rdram":
                width = e["bytes"]
                need(width in (1, 2, 4, 8), f"phase {phase} rdram width")
                data = bytes_be(e["value"], width)
                if e["write"] and e["sp_dma"]:
                    sp_dma_writes += 1
                    delta = e["address"] - target
                    need(delta in (0, 4) and width == 4, f"phase {phase} unexpected SP DMA destination")
                    expected = bytes(dmem_values[delta:delta + 4])
                    need(data == expected, f"phase {phase} SP DMA payload not current DMEM source")
                    for i, byte in enumerate(data):
                        address = e["address"] + i
                        rdram_values[address] = byte
                        rdram_origins[address] = {
                            "kind": "sp_dma",
                            "event": ordinal,
                            "source": deepcopy(dmem_origins[delta + i]),
                        }
                elif e["write"] and e["uncached_cpu"]:
                    cpu_writes += 1
                    need(e["address"] == target and width == 4, f"phase {phase} unexpected CPU overwrite")
                    for i, byte in enumerate(data):
                        address = e["address"] + i
                        rdram_values[address] = byte
                        rdram_origins[address] = {
                            "kind": "cpu_write",
                            "event": ordinal,
                            "address": address,
                        }
                elif (not e["write"]) and e["uncached_cpu"] and e["address"] == target:
                    fetch_reads += 1
                    need(width == 4, f"phase {phase} fetch read width")
                    current = bytes(rdram_values.get(target+i, -1) for i in range(4))
                    need(data == current, f"phase {phase} fetch read does not match latest RDRAM bytes")
                    fetch_origins[phase] = [deepcopy(rdram_origins[target+i]) for i in range(4)]
                    fetch_read_ord[phase] = ordinal
                    need(int.from_bytes(data, "big") == case["final_word"], f"phase {phase} fetch value")

            else:
                # Phase 4 executes an unrelated uncached SW fixture at 0x7000 before
                # fetching the executable target. Only target fetch boundaries may
                # satisfy the provenance join; unrelated fetches remain in history.
                if e["bus_paddr"] != target:
                    continue
                if e["begin"]:
                    need(fetch_begin is None, f"phase {phase} duplicate fetch begin")
                    fetch_begin = e
                    need(not e["cache"], f"phase {phase} fetch unexpectedly cached")
                else:
                    need(fetch_end is None, f"phase {phase} duplicate fetch end")
                    fetch_end = e
                    need(not e["cache"], f"phase {phase} fetch end unexpectedly cached")
                    need(e["value"] == case["final_word"], f"phase {phase} fetch boundary value")

        need(sink_counts[phase] == case["expected_rsp_sinks"], f"phase {phase} RSP sink count")
        need(sp_dma_writes == 2, f"phase {phase} needs exactly two completed DMEM->RDRAM word writes")
        need(fetch_reads == 1 and phase in fetch_origins, f"phase {phase} missing exact CPU fetch read")
        need(fetch_begin is not None and fetch_end is not None, f"phase {phase} fetch boundary pair")
        need(fetch_begin["ordinal"] < fetch_read_ord[phase] < fetch_end["ordinal"], f"phase {phase} read not bracketed by fetch")
        need(cpu_writes == (1 if phase == 4 else 0), f"phase {phase} CPU overwrite count")
        phase_stats[phase] = {
            "rsp_sinks": sink_counts[phase],
            "sp_dma_writes": sp_dma_writes,
            "cpu_writes": cpu_writes,
            "fetch_read_ordinal": fetch_read_ord[phase],
            "latest_sink_context": latest_sink_context,
        }

    roots = {
        p: [o["source"] if o["kind"] == "sp_dma" else o for o in fetch_origins[p]]
        for p in cases
    }
    need(all(o["kind"] == "rsp_sink" for o in roots[1]), "phase 1 did not retain RSP roots")

    phase2_sinks = [e for e in history["rsp_sinks"] if e["phase"] == 2]
    need(len(phase2_sinks) == 8, "phase 2 needs eight primitive byte sinks")
    contexts = []
    for e in phase2_sinks:
        if e["context"] not in contexts:
            contexts.append(e["context"])
    need(len(contexts) == 2, "phase 2 needs two writer contexts")
    groups = [[e for e in phase2_sinks if e["context"] == ctx] for ctx in contexts]
    need(all(len(group) == 4 for group in groups), "phase 2 writer context sink cardinality")
    signature = lambda group: [(e["offset"], e["bytes"], e["value"]) for e in group]
    need(signature(groups[0]) == signature(groups[1]), "phase 2 stores are not same-value")
    latest = contexts[1]
    need(all(o["kind"] == "rsp_sink" and o["context"] == latest for o in roots[2]),
         "phase 2 fetch did not inherit latest same-value writer")

    need([o["kind"] for o in roots[3]] == ["initial", "initial", "initial", "rsp_sink"],
         "phase 3 partial-byte roots")
    need(all(o["kind"] == "cpu_write" for o in roots[4]),
         "phase 4 same-value CPU overwrite did not cut DMA/RSP lineage")

    return {
        "phases": phase_stats,
        "same_value_writer_generation_preserved": True,
        "partial_byte_roots": [o["kind"] for o in roots[3]],
        "post_dma_same_value_cpu_write_cuts_rsp_lineage": True,
    }


def reject_forgeries(history, machine):
    tests = []

    def rejected(name, mutate):
        h = deepcopy(history)
        m = deepcopy(machine)
        mutate(h, m)
        try:
            verify(h, m)
        except (VerifyError, KeyError, ValueError, OverflowError):
            tests.append(name)
            return
        raise AssertionError(f"forgery accepted: {name}")

    rejected("delete_latest_same_value_sink", lambda h, m: h["rsp_sinks"].pop(
        max(i for i,e in enumerate(h["rsp_sinks"]) if e["phase"] == 2)))
    rejected("move_sp_dma_destination", lambda h, m: next(e for e in h["rdram"] if e["phase"] == 1 and e["sp_dma"]).__setitem__("address", 0x6004))
    rejected("forge_partial_sink_value", lambda h, m: next(e for e in h["rsp_sinks"] if e["phase"] == 3).__setitem__("value", 0x57))
    rejected("move_cpu_overwrite", lambda h, m: next(e for e in h["rdram"] if e["phase"] == 4 and e["write"] and e["uncached_cpu"]).__setitem__("address", 0x6304))
    rejected("forge_fetch_read_value", lambda h, m: next(e for e in h["rdram"] if e["phase"] == 1 and (not e["write"]) and e["uncached_cpu"]).__setitem__("value", 0))
    rejected("forge_fetch_bus_paddr", lambda h, m: next(e for e in h["fetch"] if e["phase"] == 3 and e["begin"]).__setitem__("bus_paddr", 0x6300))
    rejected("orphan_rsp_context", lambda h, m: next(e for e in h["rsp_sinks"] if e["phase"] == 1).__setitem__("context", 0xffffffff))
    return tests
