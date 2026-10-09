#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import json
import random
from typing import Any, Dict, List, Tuple

WORD = 4
BASE = 0x1000
REG = "t0"


class Reject(ValueError):
    pass


@dataclass(frozen=True)
class Cell:
    value: int
    generation: str
    root: str
    path: Tuple[str, ...]


def initial_memory(values: List[int], base: int = BASE) -> Dict[int, Cell]:
    return {
        base + i * WORD: Cell(v & 0xFFFFFFFF, f"mem:init:{i}", f"init:{i}", (f"init:{i}",))
        for i, v in enumerate(values)
    }


def replay(values: List[int], events: List[dict], base: int = BASE) -> dict:
    mem = initial_memory(values, base)
    regs: Dict[str, Cell] = {}
    last_seq = -1
    loads: Dict[str, Cell] = {}
    stores: Dict[str, Cell] = {}
    external: Dict[str, Cell] = {}

    for e in events:
        seq = int(e["seq"])
        if seq <= last_seq:
            raise Reject(f"non-monotonic ordinal at {e['id']}")
        last_seq = seq
        kind = e["kind"]
        eid = e["id"]

        if kind == "load":
            pa = int(e["pa"])
            reg = e["reg"]
            if pa not in mem:
                raise Reject(f"load from unknown backing {pa:#x}")
            src = mem[pa]
            if e.get("storage_generation") != src.generation or int(e.get("value", -1)) != src.value:
                raise Reject(f"load witness mismatch at {eid}")
            out = Cell(src.value, f"reg:{eid}", src.root, src.path + (f"load:{eid}",))
            regs[reg] = out
            loads[eid] = out
        elif kind == "reg_write":
            reg = e["reg"]
            value = int(e["value"]) & 0xFFFFFFFF
            regs[reg] = Cell(value, f"reg:{eid}", f"regwrite:{eid}", (f"regwrite:{eid}",))
        elif kind == "store":
            pa = int(e["pa"])
            reg = e["reg"]
            if reg not in regs:
                raise Reject(f"store from unknown register at {eid}")
            src = regs[reg]
            if e.get("register_generation") != src.generation or int(e.get("value", -1)) != src.value:
                raise Reject(f"store witness mismatch at {eid}")
            out = Cell(src.value, f"mem:{eid}", src.root, src.path + (f"store:{eid}",))
            mem[pa] = out
            stores[eid] = out
        elif kind == "external_write":
            pa = int(e["pa"])
            value = int(e["value"]) & 0xFFFFFFFF
            out = Cell(value, f"mem:{eid}", f"external:{eid}", (f"external:{eid}",))
            mem[pa] = out
            external[eid] = out
        else:
            raise Reject(f"unknown event kind {kind}")

    return {"memory": mem, "loads": loads, "stores": stores, "external": external}


def make_copy(
    values: List[int],
    src_index: int,
    dst_index: int,
    count: int,
    direction: str,
    interventions: Dict[int, List[dict]] | None = None,
) -> List[dict]:
    mem = initial_memory(values)
    reg_gen = None
    reg_value = None
    events: List[dict] = []
    seq = 0
    interventions = interventions or {}
    indexes = range(count) if direction == "forward" else range(count - 1, -1, -1)

    for iteration, i in enumerate(indexes):
        for item in interventions.get(iteration, []):
            seq += 1
            x = dict(item)
            x["seq"] = seq
            events.append(x)
            if x["kind"] == "external_write":
                pa = int(x["pa"])
                value = int(x["value"]) & 0xFFFFFFFF
                mem[pa] = Cell(value, f"mem:{x['id']}", f"external:{x['id']}", (f"external:{x['id']}",))
            elif x["kind"] == "reg_write":
                reg_gen = f"reg:{x['id']}"
                reg_value = int(x["value"]) & 0xFFFFFFFF
            else:
                raise AssertionError("unsupported intervention")

        src_pa = BASE + (src_index + i) * WORD
        dst_pa = BASE + (dst_index + i) * WORD
        src = mem[src_pa]
        seq += 1
        lid = f"L{iteration}"
        events.append(
            {
                "seq": seq,
                "id": lid,
                "kind": "load",
                "pa": src_pa,
                "reg": REG,
                "storage_generation": src.generation,
                "value": src.value,
            }
        )
        reg_gen = f"reg:{lid}"
        reg_value = src.value

        for item in interventions.get(-1000 - iteration, []):
            seq += 1
            x = dict(item)
            x["seq"] = seq
            events.append(x)
            if x["kind"] != "reg_write":
                raise AssertionError("after-load intervention must be reg_write")
            reg_gen = f"reg:{x['id']}"
            reg_value = int(x["value"]) & 0xFFFFFFFF

        seq += 1
        sid = f"S{iteration}"
        events.append(
            {
                "seq": seq,
                "id": sid,
                "kind": "store",
                "pa": dst_pa,
                "reg": REG,
                "register_generation": reg_gen,
                "value": reg_value,
            }
        )
        if reg_gen == f"reg:{lid}":
            root = src.root
            path = src.path + (f"load:{lid}", f"store:{sid}")
        else:
            root = f"regwrite:{reg_gen.split(':', 1)[1]}"
            path = (root, f"store:{sid}")
        mem[dst_pa] = Cell(reg_value, f"mem:{sid}", root, path)
    return events


def memory_summary(result: dict, start: int, count: int) -> List[dict]:
    out = []
    for i in range(count):
        pa = BASE + (start + i) * WORD
        c = result["memory"][pa]
        out.append(
            {
                "pa": f"0x{pa:08x}",
                "value": f"0x{c.value:08x}",
                "generation": c.generation,
                "root": c.root,
                "path": list(c.path),
            }
        )
    return out


def snapshot_roots(src_index: int, dst_index: int, count: int) -> Dict[int, str]:
    return {BASE + (dst_index + i) * WORD: f"init:{src_index + i}" for i in range(count)}


def root_mismatches(result: dict, expected: Dict[int, str]) -> List[dict]:
    bad = []
    for pa, root in expected.items():
        actual = result["memory"][pa].root
        if actual != root:
            bad.append({"pa": f"0x{pa:08x}", "naive": root, "actual": actual})
    return bad


def fuzz(seed: int = 0x504C414944, trials: int = 10000) -> dict:
    rng = random.Random(seed)
    forward_bad = 0
    backward_bad = 0
    equal_payload_same_final_different_roots = 0
    total_forward = total_backward = 0

    for trial in range(trials):
        count = rng.randint(2, 8)
        shift = rng.randint(1, count - 1)
        size = count + shift + 2
        values = [rng.randrange(0, 4) * 0x11111111 for _ in range(size)]
        src = 0
        dst = shift
        direction = "forward" if rng.getrandbits(1) else "backward"
        result = replay(values, make_copy(values, src, dst, count, direction))
        bad = root_mismatches(result, snapshot_roots(src, dst, count))
        if direction == "forward":
            total_forward += 1
            if bad:
                forward_bad += 1
        else:
            total_backward += 1
            if bad:
                backward_bad += 1

        if trial % 97 == 0:
            equal = [0xA5A5A5A5] * size
            rf = replay(equal, make_copy(equal, src, dst, count, "forward"))
            rb = replay(equal, make_copy(equal, src, dst, count, "backward"))
            bytes_f = [rf["memory"][BASE + (dst + i) * WORD].value for i in range(count)]
            bytes_b = [rb["memory"][BASE + (dst + i) * WORD].value for i in range(count)]
            roots_f = [rf["memory"][BASE + (dst + i) * WORD].root for i in range(count)]
            roots_b = [rb["memory"][BASE + (dst + i) * WORD].root for i in range(count)]
            if bytes_f == bytes_b and roots_f != roots_b:
                equal_payload_same_final_different_roots += 1

    return {
        "seed": seed,
        "trials": trials,
        "forward_trials": total_forward,
        "forward_snapshot_mismatch_histories": forward_bad,
        "backward_trials": total_backward,
        "backward_snapshot_mismatch_histories": backward_bad,
        "equal_payload_same_final_different_roots": equal_payload_same_final_different_roots,
    }


def expect_reject(values: List[int], events: List[dict], label: str) -> str:
    try:
        replay(values, events)
    except Reject as exc:
        return f"{label}: {exc}"
    raise AssertionError(f"forged history accepted: {label}")


def main() -> None:
    unique = [0x11111111, 0x22222222, 0x33333333, 0x44444444, 0x55555555]
    forward_events = make_copy(unique, 0, 1, 3, "forward")
    backward_events = make_copy(unique, 0, 1, 3, "backward")
    forward = replay(unique, forward_events)
    backward = replay(unique, backward_events)

    assert [forward["memory"][BASE + i * WORD].value for i in range(4)] == [0x11111111] * 4
    assert [backward["memory"][BASE + i * WORD].value for i in range(4)] == [
        0x11111111,
        0x11111111,
        0x22222222,
        0x33333333,
    ]
    assert [forward["memory"][BASE + i * WORD].root for i in range(1, 4)] == ["init:0"] * 3
    assert [backward["memory"][BASE + i * WORD].root for i in range(1, 4)] == [
        "init:0",
        "init:1",
        "init:2",
    ]

    equal = [0xA5A5A5A5] * 5
    equal_f = replay(equal, make_copy(equal, 0, 1, 3, "forward"))
    equal_b = replay(equal, make_copy(equal, 0, 1, 3, "backward"))
    assert [equal_f["memory"][BASE + i * WORD].value for i in range(4)] == [0xA5A5A5A5] * 4
    assert [equal_b["memory"][BASE + i * WORD].value for i in range(4)] == [0xA5A5A5A5] * 4
    assert [equal_f["memory"][BASE + i * WORD].root for i in range(1, 4)] != [
        equal_b["memory"][BASE + i * WORD].root for i in range(1, 4)
    ]

    rewrite_events = make_copy(
        equal,
        0,
        1,
        2,
        "forward",
        {1: [{"id": "Wsame", "kind": "external_write", "pa": BASE + WORD, "value": 0xA5A5A5A5}]},
    )
    rewrite = replay(equal, rewrite_events)
    assert rewrite["memory"][BASE + 2 * WORD].root == "external:Wsame"

    clobber_events = make_copy(
        equal,
        0,
        1,
        1,
        "forward",
        {-1000: [{"id": "Rsame", "kind": "reg_write", "reg": REG, "value": 0xA5A5A5A5}]},
    )
    clobber = replay(equal, clobber_events)
    assert clobber["memory"][BASE + WORD].root == "regwrite:Rsame"

    rejects = []
    forged = copy.deepcopy(forward_events)
    forged[2]["storage_generation"] = "mem:init:1"
    rejects.append(expect_reject(unique, forged, "stale-initial-source-generation"))

    forged = copy.deepcopy(forward_events)
    forged.pop(1)
    rejects.append(expect_reject(unique, forged, "deleted-overlap-writer"))

    forged = copy.deepcopy(forward_events)
    forged[3]["register_generation"] = "reg:L0"
    rejects.append(expect_reject(unique, forged, "wrong-register-generation"))

    forged = copy.deepcopy(forward_events)
    forged[2]["seq"] = forged[1]["seq"]
    rejects.append(expect_reject(unique, forged, "duplicate-reordered-ordinal"))

    forged = copy.deepcopy(rewrite_events)
    load_after_rewrite = next(e for e in forged if e["id"] == "L1")
    load_after_rewrite["storage_generation"] = "mem:S0"
    rejects.append(expect_reject(equal, forged, "equal-payload-rewrite-substitution"))

    snapshot_bad_forward = root_mismatches(forward, snapshot_roots(0, 1, 3))
    snapshot_bad_backward = root_mismatches(backward, snapshot_roots(0, 1, 3))
    assert snapshot_bad_forward and not snapshot_bad_backward

    report: Dict[str, Any] = {
        "model": "overlap-cpu-copy-lineage-v1",
        "composition_inputs": {
            "plaid_base": "211176e7a489fecf8331d02915ee982cd279cb62",
            "ares_pin": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
            "adjacent_cpu_copy_research_head": "7079fe6d46b6a7ec5a0bc34cf52049e1b5d7385c",
            "adjacent_cpu_copy_code_receipt": "c1d57fd0d2e028feaf9fe0a9962ed6f6497091bf",
            "adjacent_cpu_copy_actions_run": 37915748860,
        },
        "forward_unique": memory_summary(forward, 0, 4),
        "backward_unique": memory_summary(backward, 0, 4),
        "equal_payload": {
            "final_values_equal": True,
            "forward_roots": [equal_f["memory"][BASE + i * WORD].root for i in range(1, 4)],
            "backward_roots": [equal_b["memory"][BASE + i * WORD].root for i in range(1, 4)],
        },
        "same_value_backing_rewrite_root": rewrite["memory"][BASE + 2 * WORD].root,
        "same_value_register_clobber_root": clobber["memory"][BASE + WORD].root,
        "naive_initial_snapshot": {
            "forward_mismatches": snapshot_bad_forward,
            "backward_mismatches": snapshot_bad_backward,
        },
        "forged_histories_rejected": rejects,
        "fuzz": fuzz(),
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    print(json.dumps(report, sort_keys=True, indent=2))
    print(f"REPORT_SHA256={digest}")
    print(
        "PASS overlap copy requires per-read storage generation and per-store register generation; "
        "equal final payload does not recover ancestry"
    )


if __name__ == "__main__":
    main()
