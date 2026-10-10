"""Independent generation-aware replay for the cacheable table-load experiment."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "target/ares-pointer-table-dcache-load-source/evidence.json"
TABLE = 0x2000
CONFLICT = 0x4000
WORD = 4
PTR_A = 0x80007000
PTR_B = 0x80007100
PTR_C = 0x80007200
INITIAL_WORDS = {
    0x2000: None, 0x2004: 0x11112222, 0x2008: 0x33334444, 0x200C: 0x55556666,
    0x4000: PTR_A, 0x4004: 0x13579BDF, 0x4008: 0x2468ACE0, 0x400C: 0x0BADF00D,
}


class Invalid(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def generation(kind, ordinal, address):
    return f"{kind}:{ordinal}:{address:08x}"


def combined_events(case):
    events = []
    for kind, rows in case["events"].items():
        for row in rows:
            events.append((row["ordinal"], kind, row))
    ordinals = [x[0] for x in events]
    require(len(ordinals) == len(set(ordinals)), "duplicate event ordinal")
    return sorted(events)


def replay(case):
    facts = case["facts"]
    scenario = case["scenario"]
    initial = dict(INITIAL_WORDS)
    initial[TABLE] = facts["initial_table"]
    backing = {address: (value, f"init:{address:08x}") for address, value in initial.items()}
    geninfo = {gen: {"kind": "initial", "address": addr, "value": value, "parent": None}
               for addr, (value, gen) in backing.items()}
    slots = {}
    pending = {}
    dispatch = None
    table_fill_sources = []
    conflict_fill_sources = []
    scalar_table_writes = []
    cached_table_writes = []

    for ordinal, kind, e in combined_events(case):
        if kind == "scalars":
            if not e["write"]:
                continue
            require(e["bytes"] in (1, 2, 4, 8), "bad scalar width")
            require(e["uncached_cpu"], "fixture scalar write is not uncached CPU")
            require(e["bytes"] == WORD and e["address"] == TABLE, "unexpected observed scalar write")
            require((e["pc"] & 0xFFFFFFFF) == 0x6004, "scalar write at wrong guest instruction")
            gen = generation("scalar", ordinal, TABLE)
            backing[TABLE] = (e["value"] & 0xFFFFFFFF, gen)
            geninfo[gen] = {"kind": "scalar", "address": TABLE,
                            "value": e["value"] & 0xFFFFFFFF, "parent": None}
            scalar_table_writes.append((ordinal, gen))
            continue

        if kind == "bursts":
            if not e["dcache"]:
                continue
            require(e["bytes"] == 16 and (e["address"] & 15) == 0, "bad D-cache burst")
            base = e["address"]
            if e["write"]:
                raise Invalid("unexpected D-cache writeback in bounded dispatch cases")
            parents = []
            for lane, value in enumerate(e["words"][:4]):
                address = base + lane * 4
                require(address in backing, f"unknown backing word {address:#x}")
                current_value, current_gen = backing[address]
                require(current_value == value, "fill payload disagrees with current backing generation")
                parents.append((current_value, current_gen))
            pending[base] = {"ordinal": ordinal, "parents": parents}
            continue

        if kind not in ("dreads", "dwrites"):
            raise Invalid(f"unknown event kind {kind}")
        require(e["bytes"] == WORD, "bounded fixture expects Word D-cache accesses")
        base = e["paddr"] & ~0xF
        slot = e["index"]
        tag = e["tag"]
        require((tag & ~1) == (e["paddr"] & ~0xFFF), "resident tag does not match physical access")
        require(tag & 1, "resident line is not valid")

        if not e["hit_before"]:
            require(base in pending, "cache miss lacks immediately preceding backing fill")
            fill = pending.pop(base)
            words = []
            for lane, (value, parent) in enumerate(fill["parents"]):
                address = base + lane * 4
                gen = generation("fill", fill["ordinal"], address)
                geninfo[gen] = {"kind": "fill", "address": address, "value": value,
                                "parent": parent, "fill_ordinal": fill["ordinal"]}
                words.append((value, gen))
            slots[slot] = {"tag": tag, "dirty": 0, "words": words,
                           "line_generation": f"line:{fill['ordinal']}:{base:08x}"}
        require(slot in slots, "cache hit/mutation lacks resident slot")
        line = slots[slot]
        require(line["tag"] == tag, "slot tag/generation mismatch")
        lane = (e["paddr"] & 0xF) // 4
        value, source_gen = line["words"][lane]

        if kind == "dwrites":
            require(e["value"] & 0xFFFFFFFF == e["value"], "write width mismatch")
            gen = generation("dwrite", ordinal, e["paddr"])
            old_gen = source_gen
            line["words"][lane] = (e["value"], gen)
            line["dirty"] = e["dirty"]
            geninfo[gen] = {"kind": "dwrite", "address": e["paddr"], "value": e["value"],
                            "parent": old_gen, "pc": e["pc"]}
            require(e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == 0x6004,
                    "unexpected cached table mutation")
            cached_table_writes.append((ordinal, gen))
            continue

        require(value == e["value"], "D-cache load value disagrees with resident generation")
        require(line["dirty"] == e["dirty"], "D-cache load dirty state mismatch")
        if e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == facts["dispatch_pc"]:
            require(dispatch is None, "multiple dispatch loads")
            dispatch = {
                "ordinal": ordinal,
                "source_generation": source_gen,
                "source_value": value,
                "line_generation": line["line_generation"],
                "tag": tag,
                "slot": slot,
            }
        if not e["hit_before"] and e["paddr"] == TABLE:
            table_fill_sources.append(line["words"][0][1])
        if not e["hit_before"] and e["paddr"] == CONFLICT:
            conflict_fill_sources.append(line["words"][0][1])

    require(dispatch is not None, "missing exact dispatch load")
    require(dispatch["source_value"] == facts["expected_pointer"] == facts["dispatch_register"],
            "dispatch register/value mismatch")
    require(TABLE in backing, "missing table backing")
    backing_value, backing_gen = backing[TABLE]
    require(backing_value == facts["final_backing"], "final backing value mismatch")

    if scenario == "resident":
        require(len(scalar_table_writes) == 0, "resident case gained uncached backing write")
        require(len(cached_table_writes) == 1, "resident case must have one cached mutation")
        require(cached_table_writes[0][0] < dispatch["ordinal"], "resident mutation follows dispatch")
    else:
        require(len(cached_table_writes) == 0, "non-resident case gained cached mutation")
        require(len(scalar_table_writes) == 1, "non-resident case must retain one uncached backing write")
        require(scalar_table_writes[0][0] < dispatch["ordinal"], "backing rewrite follows dispatch")

    require(len(table_fill_sources) == (2 if scenario in ("refill", "same_refill") else 1),
            "wrong number of table resident generations")
    if scenario in ("refill", "same_refill"):
        require(len(conflict_fill_sources) == 1, "slot-reuse case lacks conflict fill")

    # Recheck the final cache state for the table slot.  This prevents a stale
    # source generation from being laundered through a post-dispatch slot view.
    final_slot = facts["resident_index"]
    require(final_slot in slots, "final table slot absent")
    line = slots[final_slot]
    require(line["tag"] == facts["resident_tag"], "final resident tag mismatch")
    require(line["words"][0][0] == facts["resident_word"], "final resident value mismatch")
    require(line["dirty"] == facts["resident_dirty"], "final resident dirty mismatch")

    return {
        "scenario": scenario,
        "dispatch_ordinal": dispatch["ordinal"],
        "source_generation": dispatch["source_generation"],
        "source_value": dispatch["source_value"],
        "line_generation": dispatch["line_generation"],
        "backing_generation": backing_gen,
        "backing_value": backing_value,
        "table_fill_generations": table_fill_sources,
        "conflict_fill_generations": conflict_fill_sources,
        "cached_write_generations": [g for _, g in cached_table_writes],
        "scalar_write_generations": [g for _, g in scalar_table_writes],
        "generation_info": geninfo,
    }


def verify_claim(case, claim):
    actual = replay(case)
    keys = ("dispatch_ordinal", "source_generation", "source_value", "line_generation",
            "backing_generation", "backing_value")
    require(all(claim.get(k) == actual.get(k) for k in keys), "certificate claim disagrees with causal replay")
    return actual


def expect_reject(name, fn, rejected):
    try:
        fn()
    except (Invalid, AssertionError, KeyError, ValueError):
        rejected.append(name)
        return
    raise AssertionError(f"forgery accepted: {name}")


def main(path=DEFAULT):
    document = json.loads(Path(path).read_text())
    require(document["schema"] == "plaid.pointer_table_dcache_load_source.v0", "wrong schema")
    cases = document["cases"]
    canonical = {name: replay(case) for name, case in sorted(cases.items())}

    # Relationship assertions are the semantic heart of the result.
    stale = canonical["stale"]
    same = canonical["same"]
    refill = canonical["refill"]
    same_refill = canonical["same_refill"]
    resident = canonical["resident"]
    require(stale["source_generation"] != stale["backing_generation"], "stale source collapsed to current backing")
    require(same["source_value"] == same["backing_value"] and same["source_generation"] != same["backing_generation"],
            "same-value backing rewrite collapsed generation identity")
    require(refill["source_generation"] == refill["table_fill_generations"][-1], "refill did not source dispatch from new resident generation")
    require(same_refill["table_fill_generations"][0] != same_refill["table_fill_generations"][1],
            "same-value refill collapsed resident generations")
    require(same_refill["source_generation"] == same_refill["table_fill_generations"][1],
            "same-value refill dispatch did not use newest actual fill")
    require(same_refill["source_value"] == PTR_A, "same-value refill payload changed")
    require(same_refill["conflict_fill_generations"], "missing equal-payload decoy fill")
    decoy = same_refill["conflict_fill_generations"][0]
    require(same_refill["generation_info"][decoy]["value"] == same_refill["source_value"],
            "decoy is not equal-payload")
    require(resident["source_generation"] == resident["cached_write_generations"][0],
            "resident-only mutation not consumed by dispatch")
    require(resident["source_generation"] != resident["backing_generation"],
            "resident-only mutation collapsed to backing")

    rejected = []
    # 1. Attribute a stale load to current backing.
    claim = {k: stale[k] for k in ("dispatch_ordinal", "source_generation", "source_value", "line_generation", "backing_generation", "backing_value")}
    claim["source_generation"] = stale["backing_generation"]
    expect_reject("stale_current_backing_attribution", lambda: verify_claim(cases["stale"], claim), rejected)

    # 2. Same payload is still a different backing generation.
    claim = {k: same[k] for k in ("dispatch_ordinal", "source_generation", "source_value", "line_generation", "backing_generation", "backing_value")}
    claim["backing_generation"] = "init:00002000"
    expect_reject("same_value_backing_generation_collapse", lambda: verify_claim(cases["same"], claim), rejected)

    # 3. Same-value refill cannot be attributed to the old resident generation.
    claim = {k: same_refill[k] for k in ("dispatch_ordinal", "source_generation", "source_value", "line_generation", "backing_generation", "backing_value")}
    claim["source_generation"] = same_refill["table_fill_generations"][0]
    expect_reject("same_value_old_fill_attribution", lambda: verify_claim(cases["same_refill"], claim), rejected)

    # 4. Equal pointer bits from the conflicting line are not table provenance.
    claim["source_generation"] = decoy
    expect_reject("equal_payload_conflict_line_decoy", lambda: verify_claim(cases["same_refill"], claim), rejected)

    # 5. Delete the exact dispatch load.
    forged = deepcopy(cases["stale"])
    forged["events"]["dreads"] = [e for e in forged["events"]["dreads"]
                                    if not (e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == forged["facts"]["dispatch_pc"])]
    expect_reject("deleted_dispatch_load", lambda: replay(forged), rejected)

    # 6. Delete a same-value backing rewrite. Values remain identical but chronology does not.
    forged = deepcopy(cases["same"])
    forged["events"]["scalars"] = []
    expect_reject("deleted_same_value_backing_write", lambda: replay(forged), rejected)

    # 7. Delete the resident-only cache mutation.
    forged = deepcopy(cases["resident"])
    forged["events"]["dwrites"] = []
    expect_reject("deleted_resident_store", lambda: replay(forged), rejected)

    # 8. Forge the dispatch physical source to the equal-index decoy.
    forged = deepcopy(cases["same_refill"])
    for e in forged["events"]["dreads"]:
        if e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == forged["facts"]["dispatch_pc"]:
            e["paddr"] = CONFLICT
            break
    expect_reject("forged_dispatch_physical_source", lambda: replay(forged), rejected)

    # 9. Reorder the actual backing write after dispatch while keeping its value.
    forged = deepcopy(cases["stale"])
    dispatch_ordinal = next(e["ordinal"] for e in forged["events"]["dreads"]
                            if e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == forged["facts"]["dispatch_pc"])
    forged["events"]["scalars"][0]["ordinal"] = dispatch_ordinal + 1000
    expect_reject("reordered_backing_write", lambda: replay(forged), rejected)

    # 10. Duplicate an ordinal, making total order ambiguous.
    forged = deepcopy(cases["refill"])
    forged["events"]["dreads"][0]["ordinal"] = forged["events"]["bursts"][0]["ordinal"]
    expect_reject("duplicate_ordinal", lambda: replay(forged), rejected)

    # 11. Retag the dispatch resident line without changing pointer bits.
    forged = deepcopy(cases["stale"])
    for e in forged["events"]["dreads"]:
        if e["paddr"] == TABLE and (e["pc"] & 0xFFFFFFFF) == forged["facts"]["dispatch_pc"]:
            e["tag"] += 0x2000
            break
    expect_reject("wrong_resident_tag", lambda: replay(forged), rejected)

    # 12. Collapse the resident-only source to unchanged backing.
    claim = {k: resident[k] for k in ("dispatch_ordinal", "source_generation", "source_value", "line_generation", "backing_generation", "backing_value")}
    claim["source_generation"] = resident["backing_generation"]
    expect_reject("resident_current_backing_attribution", lambda: verify_claim(cases["resident"], claim), rejected)

    require(len(rejected) == 12, "forgery matrix incomplete")
    summary = {
        "schema": document["schema"],
        "ares_rev": document["ares_rev"],
        "cases": {
            name: {k: value for k, value in cert.items() if k != "generation_info"}
            for name, cert in canonical.items()
        },
        "forgeries_rejected": rejected,
    }
    canonical_json = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("REPORT_SHA256=" + hashlib.sha256(canonical_json.encode()).hexdigest())
    print("PASS: strict replay binds each dispatch to its actual resident generation and rejects 12 provenance forgeries")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT)
