#!/usr/bin/env python3
"""Executable composition model for RSP DMEM -> CPU copy -> IMEM -> RSP fetch provenance.

This does not emulate the N64. It composes three separately validated exact-pin
contracts and attacks the seam where a whole-word CPU copy could flatten mixed
per-byte ancestry.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "target/rsp-dmem-cpu-copy-imem-fetch"
WORD = 0x34087722

PRIOR = {
    "ares": "9408cb43d4948fc3ea6e152a307a34348df3fe04",
    "rsp_dmem_cpu_refetch_commit": "cda3b458dc1ac77c639a1afc02a05daac642e861",
    "rsp_dmem_cpu_refetch_result_sha256": "3bdbf149b3b382fb9fb38c8381a0fee32d4e1045f804f12bebb2ba1066091957",
    "cpu_dmem_imem_copy_commit": "5c13859e536bf42fcfae9e56b9104f5ff6292590",
    "cpu_dmem_imem_copy_result_sha256": "45f3126878657b9c084572a7e943a024ca05dad6c5c47a3cfa1e0cc7ab18a39c",
    "rsp_imem_provenance_base": "211176e7a489fecf8331d02915ee982cd279cb62",
}


def be_bytes(value: int, width: int) -> list[int]:
    return [(value >> (8 * (width - 1 - i))) & 0xff for i in range(width)]


def be_word(data: dict[int, int], addr: int) -> int:
    value = 0
    for i in range(4):
        value = (value << 8) | data[addr + i]
    return value


def origin_label(event: dict) -> str:
    kind = event["kind"]
    if kind == "cpu_dmem_word":
        return f"cpu-dmem:{event['producer']}:{event['ordinal']}"
    if kind == "rsp_dmem_byte":
        return f"rsp:{event['context']}:{event['pc']:03x}:{event['ordinal']}"
    if kind == "foreign_dmem_byte":
        return f"unknown-dmem:{event['ordinal']}"
    raise AssertionError(kind)


@dataclass
class RegDef:
    value: int
    kind: str
    event: int
    ancestry: tuple[str, ...] | None = None


class ReplayError(AssertionError):
    pass


def base_history(seed_producer: str = "cpu-seed-A") -> list[dict]:
    # DMEM+4 is a deliberately equal-valued decoy. Its initial origin differs,
    # but the copy uses t0 loaded from DMEM+0.
    return [
        {"ordinal": 1, "kind": "cpu_dmem_word", "producer": seed_producer, "addr": 0, "value": 0x34081111},
        {"ordinal": 2, "kind": "rsp_begin", "context": 2, "pc": 0x080, "word": 0xa0000000},
        {"ordinal": 3, "kind": "rsp_dmem_byte", "context": 2, "pc": 0x080, "addr": 3, "value": 0x22},
        {"ordinal": 4, "kind": "rsp_end", "context": 2, "pc": 0x080, "word": 0xa0000000},
        {"ordinal": 5, "kind": "rsp_begin", "context": 5, "pc": 0x084, "word": 0xe8000000},
        {"ordinal": 6, "kind": "rsp_dmem_byte", "context": 5, "pc": 0x084, "addr": 2, "value": 0x77},
        {"ordinal": 7, "kind": "rsp_end", "context": 5, "pc": 0x084, "word": 0xe8000000},
        # Same-value rewrite must advance producer generation for byte 3.
        {"ordinal": 8, "kind": "rsp_begin", "context": 8, "pc": 0x088, "word": 0xa0000000},
        {"ordinal": 9, "kind": "rsp_dmem_byte", "context": 8, "pc": 0x088, "addr": 3, "value": 0x22},
        {"ordinal": 10, "kind": "rsp_end", "context": 8, "pc": 0x088, "word": 0xa0000000},
        {"ordinal": 11, "kind": "cpu_lw", "instruction": 101, "reg": "t0", "addr": 0, "value": WORD},
        # Equal-valued decoy read into a different register.
        {"ordinal": 12, "kind": "cpu_lw", "instruction": 102, "reg": "t1", "addr": 4, "value": WORD},
        {"ordinal": 13, "kind": "cpu_sw_imem", "instruction": 103, "reg": "t0", "addr": 0, "value": WORD},
        {"ordinal": 14, "kind": "rsp_fetch", "pc": 0, "value": WORD},
        # Same-value post-copy mutation changes residency/lifetime at one byte.
        {"ordinal": 15, "kind": "foreign_imem_byte", "addr": 3, "value": 0x22},
        {"ordinal": 16, "kind": "rsp_fetch", "pc": 0, "value": WORD},
        # Refresh DMEM byte 2 with the same value, producing a new RSP generation.
        {"ordinal": 17, "kind": "rsp_begin", "context": 17, "pc": 0x08c, "word": 0xe8000000},
        {"ordinal": 18, "kind": "rsp_dmem_byte", "context": 17, "pc": 0x08c, "addr": 2, "value": 0x77},
        {"ordinal": 19, "kind": "rsp_end", "context": 17, "pc": 0x08c, "word": 0xe8000000},
        {"ordinal": 20, "kind": "cpu_lw", "instruction": 104, "reg": "t0", "addr": 0, "value": WORD},
        # Same-value register rewrite severs memory ancestry.
        {"ordinal": 21, "kind": "cpu_reg_write", "instruction": 105, "reg": "t0", "value": WORD, "op": "addu_same_value"},
        {"ordinal": 22, "kind": "cpu_sw_imem", "instruction": 106, "reg": "t0", "addr": 4, "value": WORD},
        {"ordinal": 23, "kind": "rsp_fetch", "pc": 4, "value": WORD},
        # Reload restores a causal source chain, then copy to a fresh IMEM word.
        {"ordinal": 24, "kind": "cpu_lw", "instruction": 107, "reg": "t0", "addr": 0, "value": WORD},
        {"ordinal": 25, "kind": "cpu_sw_imem", "instruction": 108, "reg": "t0", "addr": 8, "value": WORD},
        {"ordinal": 26, "kind": "rsp_fetch", "pc": 8, "value": WORD},
    ]


def replay(events: list[dict]) -> dict:
    if [e["ordinal"] for e in events] != list(range(1, len(events) + 1)):
        raise ReplayError("non-contiguous or duplicate chronology")

    # Two words are present before measured events. Word+0 is immediately
    # replaced by event 1. Word+4 is the equal-value decoy.
    dmem = {i: b for i, b in enumerate(be_bytes(0x340800aa, 4))}
    dmem.update({4 + i: b for i, b in enumerate(be_bytes(WORD, 4))})
    dmem_origin = {i: f"initial:{i}" for i in range(8)}
    for i in range(4, 8):
        dmem_origin[i] = f"decoy-initial:{i}"

    imem = {i: 0 for i in range(12)}
    imem_origin = {i: f"initial-imem:{i}" for i in range(12)}
    imem_resident = {i: f"initial-imem-gen:{i}" for i in range(12)}

    regs: dict[str, RegDef] = {}
    active_rsp: tuple[int, int, int] | None = None
    copies = []
    fetches = []
    reads = []

    for e in events:
        kind = e["kind"]
        ordinal = e["ordinal"]

        if kind == "cpu_dmem_word":
            vals = be_bytes(e["value"], 4)
            label = origin_label(e)
            for i, b in enumerate(vals):
                a = e["addr"] + i
                dmem[a] = b
                dmem_origin[a] = label

        elif kind == "rsp_begin":
            if active_rsp is not None or e["context"] != ordinal:
                raise ReplayError("invalid RSP context begin")
            active_rsp = (e["context"], e["pc"], e["word"])

        elif kind == "rsp_dmem_byte":
            if active_rsp is None:
                raise ReplayError("RSP sink outside context")
            if (e["context"], e["pc"]) != active_rsp[:2]:
                raise ReplayError("RSP sink/context mismatch")
            if not 0 <= e["value"] <= 0xff:
                raise ReplayError("invalid byte")
            dmem[e["addr"]] = e["value"]
            dmem_origin[e["addr"]] = origin_label(e)

        elif kind == "foreign_dmem_byte":
            if active_rsp is not None:
                raise ReplayError("foreign DMEM sink inside RSP context")
            dmem[e["addr"]] = e["value"]
            dmem_origin[e["addr"]] = origin_label(e)

        elif kind == "rsp_end":
            if active_rsp != (e["context"], e["pc"], e["word"]):
                raise ReplayError("invalid RSP context end")
            active_rsp = None

        elif kind == "cpu_lw":
            value = be_word(dmem, e["addr"])
            if value != e["value"]:
                raise ReplayError("CPU read payload disagrees with backing")
            ancestry = tuple(dmem_origin[e["addr"] + i] for i in range(4))
            regs[e["reg"]] = RegDef(value=value, kind="lw", event=ordinal, ancestry=ancestry)
            reads.append({
                "ordinal": ordinal,
                "instruction": e["instruction"],
                "reg": e["reg"],
                "addr": e["addr"],
                "value": value,
                "byte_origins": list(ancestry),
            })

        elif kind == "cpu_reg_write":
            regs[e["reg"]] = RegDef(value=e["value"], kind=e["op"], event=ordinal, ancestry=None)

        elif kind == "cpu_sw_imem":
            reg = regs.get(e["reg"])
            if reg is None or reg.value != e["value"]:
                raise ReplayError("CPU store source register mismatch")
            vals = be_bytes(e["value"], 4)
            resident = f"imem-write:{ordinal}"
            causal = reg.kind == "lw" and reg.ancestry is not None
            origins = reg.ancestry if causal else tuple(f"unknown-copy:{ordinal}:{i}" for i in range(4))
            for i, b in enumerate(vals):
                a = e["addr"] + i
                imem[a] = b
                imem_resident[a] = resident
                imem_origin[a] = origins[i]
            copies.append({
                "write_ordinal": ordinal,
                "instruction": e["instruction"],
                "source_reg": e["reg"],
                "destination": e["addr"],
                "value": e["value"],
                "source_read_ordinal": reg.event if causal else None,
                "source_byte_origins": list(origins) if causal else None,
                "resident_generation": resident,
                "certified": causal,
            })

        elif kind == "foreign_imem_byte":
            a = e["addr"]
            if imem[a] != e["value"]:
                raise ReplayError("fixture expects same-value IMEM mutation")
            # Occurrence is still a fresh storage generation. Payload equality
            # cannot resurrect the previous copy ancestry.
            imem[a] = e["value"]
            imem_resident[a] = f"foreign-imem:{ordinal}"
            imem_origin[a] = f"unknown-imem:{ordinal}"

        elif kind == "rsp_fetch":
            value = be_word(imem, e["pc"])
            if value != e["value"]:
                raise ReplayError("RSP fetch payload disagrees with IMEM")
            fetches.append({
                "ordinal": ordinal,
                "pc": e["pc"],
                "value": value,
                "resident_generations": [imem_resident[e["pc"] + i] for i in range(4)],
                "byte_origins": [imem_origin[e["pc"] + i] for i in range(4)],
            })

        else:
            raise ReplayError(f"unknown event {kind}")

    if active_rsp is not None:
        raise ReplayError("unterminated RSP context")

    return {"reads": reads, "copies": copies, "fetches": fetches}


def flat_copy_projection(result: dict) -> list[dict]:
    """Fields retained by the validated bounded Word-copy certificate today."""
    return [
        {
            "source_read_ordinal": c["source_read_ordinal"],
            "write_ordinal": c["write_ordinal"],
            "destination": c["destination"],
            "value": c["value"],
            "certified": c["certified"],
        }
        for c in result["copies"]
    ]


def verify_baseline(result: dict) -> None:
    copies = {c["write_ordinal"]: c for c in result["copies"]}
    fetches = {f["ordinal"]: f for f in result["fetches"]}

    c13 = copies[13]
    assert c13["certified"] and c13["source_read_ordinal"] == 11
    assert c13["source_byte_origins"][0] == c13["source_byte_origins"][1]
    assert c13["source_byte_origins"][0].startswith("cpu-dmem:cpu-seed-A:")
    assert c13["source_byte_origins"][2].startswith("rsp:5:")
    # Same-value phase at ordinal 9 must supersede older RSP byte-3 writer.
    assert c13["source_byte_origins"][3].startswith("rsp:8:")

    f14 = fetches[14]
    assert len(set(f14["resident_generations"])) == 1
    assert f14["resident_generations"] == [c13["resident_generation"]] * 4
    assert f14["byte_origins"] == c13["source_byte_origins"]
    assert len(set(f14["byte_origins"])) == 3  # CPU + vector RSP + latest scalar RSP.

    f16 = fetches[16]
    assert f16["value"] == f14["value"]
    assert f16["byte_origins"][:3] == f14["byte_origins"][:3]
    assert f16["byte_origins"][3] == "unknown-imem:15"
    assert f16["resident_generations"][3] == "foreign-imem:15"

    c22 = copies[22]
    assert not c22["certified"] and c22["source_read_ordinal"] is None
    assert all(x.startswith("unknown-copy:22:") for x in fetches[23]["byte_origins"])

    c25 = copies[25]
    assert c25["certified"] and c25["source_read_ordinal"] == 24
    # Byte 2 has a newer same-value RSP writer than the first copy.
    assert c25["source_byte_origins"][2].startswith("rsp:17:")
    assert c25["source_byte_origins"][2] != c13["source_byte_origins"][2]
    assert fetches[26]["byte_origins"] == c25["source_byte_origins"]


def claimed_report(result: dict) -> dict:
    return {
        "copies": deepcopy(result["copies"]),
        "fetches": deepcopy(result["fetches"]),
    }


def verify_claim(events: list[dict], claim: dict) -> None:
    truth = replay(events)
    verify_baseline(truth)
    if claim != claimed_report(truth):
        raise ReplayError("claimed composition differs from replayed causal history")


def adversaries(events: list[dict], baseline: dict) -> list[str]:
    rejected = []

    def must_reject(name: str, forged_events: list[dict], forged_claim: dict) -> None:
        try:
            verify_claim(forged_events, forged_claim)
        except (ReplayError, AssertionError, KeyError, IndexError):
            rejected.append(name)
            return
        raise AssertionError("forgery accepted: " + name)

    claim = claimed_report(baseline)

    x = deepcopy(claim)
    c = next(c for c in x["copies"] if c["write_ordinal"] == 13)
    c["source_byte_origins"] = [f"word-read:{c['source_read_ordinal']}"] * 4
    must_reject("flatten_mixed_source_to_word_identity", events, x)

    x = deepcopy(claim)
    f = next(f for f in x["fetches"] if f["ordinal"] == 14)
    f["byte_origins"][2], f["byte_origins"][3] = f["byte_origins"][3], f["byte_origins"][2]
    must_reject("swap_per_byte_ancestry", events, x)

    x = deepcopy(claim)
    c = next(c for c in x["copies"] if c["write_ordinal"] == 13)
    c["source_byte_origins"][3] = "rsp:2:080:3"  # stale equal-value predecessor.
    must_reject("reuse_stale_same_value_rsp_generation", events, x)

    x = deepcopy(claim)
    c = next(c for c in x["copies"] if c["write_ordinal"] == 13)
    c["source_read_ordinal"] = 12
    must_reject("equal_value_decoy_read_steals_copy", events, x)

    x = deepcopy(claim)
    c = next(c for c in x["copies"] if c["write_ordinal"] == 22)
    c["certified"] = True
    c["source_read_ordinal"] = 20
    c["source_byte_origins"] = next(r["byte_origins"] for r in baseline["reads"] if r["ordinal"] == 20)
    must_reject("same_value_gpr_clobber_ignored", events, x)

    x = deepcopy(claim)
    f14 = next(f for f in x["fetches"] if f["ordinal"] == 14)
    f16 = next(f for f in x["fetches"] if f["ordinal"] == 16)
    f16["byte_origins"] = deepcopy(f14["byte_origins"])
    f16["resident_generations"] = deepcopy(f14["resident_generations"])
    must_reject("same_value_post_copy_imem_mutation_erased", events, x)

    x_events = deepcopy(events)
    lw = next(e for e in x_events if e["ordinal"] == 11)
    lw["kind"] = "cpu_reg_write"
    lw["op"] = "forged_same_value_constant"
    lw.pop("addr")
    # Same value and subsequent SW/fetch bytes remain plausible, but ancestry vanishes.
    must_reject("missing_source_read_repaired_by_value", x_events, claim)

    x_events = deepcopy(events)
    sink = next(e for e in x_events if e["ordinal"] == 9)
    sink["kind"] = "foreign_dmem_byte"
    sink.pop("context")
    sink.pop("pc")
    # It now occurs while an RSP context is active, so strict replay rejects it.
    must_reject("forge_rsp_sink_as_foreign_same_value_write", x_events, claim)

    x_events = deepcopy(events)
    x_events[5]["ordinal"] = x_events[4]["ordinal"]
    must_reject("duplicate_chronology_ordinal", x_events, claim)

    x_events = deepcopy(events)
    sink = next(e for e in x_events if e["ordinal"] == 18)
    sink["addr"] = 1
    must_reject("same_value_refresh_wrong_byte", x_events, claim)

    return rejected


def projection_collision() -> dict:
    a = replay(base_history("cpu-seed-A"))
    b = replay(base_history("dma-equivalent-B"))
    verify_baseline(a)
    assert flat_copy_projection(a) == flat_copy_projection(b)
    fa = next(f for f in a["fetches"] if f["ordinal"] == 14)
    fb = next(f for f in b["fetches"] if f["ordinal"] == 14)
    assert fa["value"] == fb["value"] == WORD
    assert fa["resident_generations"] == fb["resident_generations"]
    assert fa["byte_origins"] != fb["byte_origins"]
    assert fa["byte_origins"][:2] != fb["byte_origins"][:2]
    assert fa["byte_origins"][2:] == fb["byte_origins"][2:]
    return {
        "flat_copy_projection_equal": True,
        "fetch_payload_equal": True,
        "resident_generation_equal": True,
        "strict_byte_ancestry_equal": False,
        "history_a_origins": fa["byte_origins"],
        "history_b_origins": fb["byte_origins"],
    }


def main() -> None:
    events = base_history()
    result = replay(events)
    verify_baseline(result)
    claim = claimed_report(result)
    verify_claim(events, claim)
    rejected = adversaries(events, result)
    collision = projection_collision()
    assert len(rejected) == 10

    out = {
        "schema": "plaid-rsp-dmem-cpu-copy-imem-fetch-composition/v0",
        "prior_contracts": PRIOR,
        "event_count": len(events),
        "events": events,
        "derived": result,
        "forgeries_rejected": rejected,
        "projection_collision": collision,
        "conclusion": {
            "mixed_byte_origins_survive_cpu_word_copy": True,
            "copy_sink_has_one_resident_generation": True,
            "copy_sink_may_have_multiple_upstream_origins": True,
            "whole_word_copy_certificate_sufficient_for_ultimate_origin": False,
            "value_equality_is_provenance": False,
            "native_complete": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "results.json"
    path.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    print(
        "PASS: mixed per-byte RSP/CPU ancestry survives certified CPU Word copy "
        f"into IMEM; {len(rejected)} forgeries rejected; "
        "flat certificate collision demonstrated"
    )
    print("RESULT_SHA256=" + digest)
    print("MIXED_ORIGINS=" + ",".join(next(f["byte_origins"] for f in result["fetches"] if f["ordinal"] == 14)))
    print("POST_MUTATION_ORIGINS=" + ",".join(next(f["byte_origins"] for f in result["fetches"] if f["ordinal"] == 16)))


if __name__ == "__main__":
    main()
