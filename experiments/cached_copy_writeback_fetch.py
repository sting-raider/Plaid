from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
import hashlib, json, sys

ARES_PIN = "9408cb43d4948fc3ea6e152a307a34348df3fe04"
PRIOR = {
    "cpu_copy": {
        "branch": "research/cpu-copy-rdram-gpt56sol",
        "head": "9760f94fbfb9389b107ae58239db6817f8a7a964",
        "note_blob": "dd525733e5c574d36dd5e52d5ef6b55bcaf03f5b",
        "result_run": "37798119815",
        "result_artifact": "11559372938",
    },
    "dcache_eviction": {
        "branch": "research/dcache-eviction-lineage-gpt56sol",
        "head": "2f701615d77630f1b9407f2f1a2032894114a4e7",
        "semantic_head": "c7441f49160fe64cea83ed7cf36e37a07543880d",
        "note_blob": "3192ea9b1d89bc9579f8380f766cdfa0f73c5024",
        "result_run": "37850302734",
        "result_sha256": "79d0b886342701801f6441516fe15189422d21811b681a7f86dfe7d1f13c2cd3",
    },
    "uncached_fetch": {
        "branch": "research/ares-rdram-uncached-fetch-gpt56sol",
        "head": "77a268281fa330e6d117523c2e342abbdad7639e",
        "semantic_head": "08fc4f5a0f563e2501751d93e67ed9d9f6809a7b",
        "note_blob": "633fff4c2711ae4d7f3bbaf1d1c23c854d6252f7",
        "result_run": "37801666243",
        "result_sha256": "9580733c7af1b3ced1f5c38594e2e6fd123f79ba85b900d8d2205dcb5dd9c684",
    },
}

class Reject(Exception):
    pass

@dataclass(frozen=True)
class ByteCell:
    value: int
    chain: tuple[str, ...]

@dataclass
class CacheLine:
    tag: int
    base: int
    bytes: list[ByteCell]
    dirty_mask: int
    generation: int

@dataclass(frozen=True)
class RegWord:
    value: int
    bytes: tuple[ByteCell, ByteCell, ByteCell, ByteCell]
    generation: int
    source_paddr: int

def word_bytes(v: int) -> list[int]:
    return list(v.to_bytes(4, "big"))

def bytes_word(cells) -> int:
    return int.from_bytes(bytes(c.value for c in cells), "big")

def slot_for(paddr: int) -> int:
    return (paddr >> 4) & 0x1ff

def tag_for(paddr: int) -> int:
    return (paddr & ~0xfff) | 1

def make_initial(base: int, words: list[int], label: str) -> dict[int, ByteCell]:
    out = {}
    for wi, word in enumerate(words):
        for bi, v in enumerate(word_bytes(word)):
            addr = base + wi * 4 + bi
            out[addr] = ByteCell(v, (f"initial:{label}:{addr:08x}",))
    return out

def canonical_events():
    # Event payloads intentionally mirror the validated dirty-eviction chronology,
    # then add the already-validated uncached-fetch boundary contract.
    return [
        # Equal-payload decoy is resident too; payload matching must not select it.
        {"seq": 1, "kind": "fill", "base": 0x1100, "tag": 0x1001, "slot": 0x110},
        {"seq": 2, "kind": "fill", "base": 0x1000, "tag": 0x1001, "slot": 0x100},
        {"seq": 3, "kind": "load", "paddr": 0x1000, "reg": "t0"},
        # Same source backing is replaced after the cached load. This must not
        # retroactively rewrite resident/register provenance.
        {"seq": 4, "kind": "backing_write", "paddr": 0x1000, "value": 0x55667788, "writer": "source_alias_patch"},
        {"seq": 5, "kind": "fill", "base": 0x2000, "tag": 0x2001, "slot": 0},
        {"seq": 6, "kind": "cached_store", "paddr": 0x2000, "reg": "t0", "slot": 0, "tag": 0x2001},
        {"seq": 7, "kind": "backing_write", "paddr": 0x2000, "value": 0xdeadbeef, "writer": "dirty_lane_poison"},
        {"seq": 8, "kind": "backing_write", "paddr": 0x2004, "value": 0xfeedface, "writer": "clean_lane_poison"},
        {"seq": 9, "kind": "writeback", "base": 0x2000, "slot": 0, "tag": 0x2001, "width": 16, "dirty_mask": 0x000f},
        {"seq": 10, "kind": "fill", "base": 0x4000, "tag": 0x4001, "slot": 0},
        {"seq": 11, "kind": "fetch_begin", "id": "copied", "paddr": 0x2000},
        {"seq": 12, "kind": "backing_read", "id": "copied", "paddr": 0x2000, "value": 0x11223344},
        {"seq": 13, "kind": "fetch_end", "id": "copied", "paddr": 0x2000, "value": 0x11223344},
        {"seq": 14, "kind": "fetch_begin", "id": "clean", "paddr": 0x2004},
        {"seq": 15, "kind": "backing_read", "id": "clean", "paddr": 0x2004, "value": 0x01020304},
        {"seq": 16, "kind": "fetch_end", "id": "clean", "paddr": 0x2004, "value": 0x01020304},
        # Same payload, new writer generation. Later fetch must root here rather
        # than in the earlier cached-copy chain.
        {"seq": 17, "kind": "backing_write", "paddr": 0x2000, "value": 0x11223344, "writer": "same_value_post_writeback_patch"},
        {"seq": 18, "kind": "fetch_begin", "id": "post_patch", "paddr": 0x2000},
        {"seq": 19, "kind": "backing_read", "id": "post_patch", "paddr": 0x2000, "value": 0x11223344},
        {"seq": 20, "kind": "fetch_end", "id": "post_patch", "paddr": 0x2000, "value": 0x11223344},
    ]

def initial_state():
    backing = {}
    backing.update(make_initial(0x1000, [0x11223344, 0x11111111, 0x22222222, 0x33333333], "source"))
    backing.update(make_initial(0x1100, [0x11223344, 0xaaaaaaaa, 0xbbbbbbbb, 0xcccccccc], "equal_decoy"))
    backing.update(make_initial(0x2000, [0xaabbccdd, 0x01020304, 0x11223344, 0x55667788], "dest"))
    backing.update(make_initial(0x4000, [0xcafebabe, 0x0badf00d, 0x89abcdef, 0x13579bdf], "conflict"))
    return backing, {}, {}, 0

def replay(events, *, expect_all_fetches=True):
    backing, cache, regs, cache_generation = initial_state()
    last_seq = -1
    fetch_ctx = {}
    certs = {}
    audit = []
    writeback_snapshot = None

    def line_for(slot, tag):
        line = cache.get(slot)
        if line is None or line.tag != tag:
            raise Reject(f"cache identity mismatch slot={slot:#x} tag={tag:#x}")
        return line

    for event in events:
        seq = event["seq"]
        if seq <= last_seq:
            raise Reject("non-monotonic chronology")
        last_seq = seq
        kind = event["kind"]

        if kind == "fill":
            base = event["base"]
            if event["slot"] != slot_for(base) or event["tag"] != tag_for(base):
                raise Reject("forged fill slot/tag")
            cache_generation += 1
            cells = []
            for off in range(16):
                src = backing[base + off]
                cells.append(ByteCell(src.value, src.chain + (f"dcache_fill:g{cache_generation}:{base+off:08x}",)))
            cache[event["slot"]] = CacheLine(event["tag"], base, cells, 0, cache_generation)
            audit.append(f"{seq}:fill:{base:08x}:g{cache_generation}")

        elif kind == "load":
            paddr = event["paddr"]
            line = line_for(slot_for(paddr), tag_for(paddr))
            off = paddr - line.base
            cells = tuple(line.bytes[off:off+4])
            if len(cells) != 4:
                raise Reject("load outside resident line")
            # The expected source address is part of the causal certificate.
            if event.get("expected_source", 0x1000) != paddr:
                raise Reject("load source identity drift")
            regs[event["reg"]] = RegWord(bytes_word(cells), cells, seq, paddr)
            audit.append(f"{seq}:load:{paddr:08x}:{event['reg']}:g{seq}")

        elif kind == "cached_store":
            reg = regs.get(event["reg"])
            if reg is None:
                raise Reject("store has no register generation")
            paddr = event["paddr"]
            line = line_for(event["slot"], event["tag"])
            if event["slot"] != slot_for(paddr) or event["tag"] != tag_for(paddr):
                raise Reject("cached store slot/tag mismatch")
            off = paddr - line.base
            if not (0 <= off <= 12):
                raise Reject("store outside resident line")
            for bi, src in enumerate(reg.bytes):
                line.bytes[off+bi] = ByteCell(src.value, src.chain + (f"reg:{event['reg']}:g{reg.generation}:b{bi}", f"dcache_store:g{seq}:{paddr+bi:08x}"))
                line.dirty_mask |= 1 << (off + bi)
            audit.append(f"{seq}:cached_store:{paddr:08x}:from_g{reg.generation}")

        elif kind == "backing_write":
            vals = word_bytes(event["value"])
            paddr = event["paddr"]
            for bi, v in enumerate(vals):
                backing[paddr+bi] = ByteCell(v, (f"backing_write:g{seq}:{event['writer']}:{paddr+bi:08x}",))
            audit.append(f"{seq}:backing_write:{paddr:08x}:{event['writer']}")

        elif kind == "writeback":
            if event["width"] != 16:
                raise Reject("D-cache writeback width is not full resident line")
            line = line_for(event["slot"], event["tag"])
            if line.base != event["base"]:
                raise Reject("writeback base does not match outgoing resident generation")
            if event["dirty_mask"] != line.dirty_mask:
                raise Reject("writeback dirty-mask receipt mismatch")
            writeback_snapshot = {
                "seq": seq,
                "slot": event["slot"],
                "tag": line.tag,
                "resident_generation": line.generation,
                "dirty_mask": line.dirty_mask,
                "chains": [c.chain for c in line.bytes],
            }
            # Full line is written, including nominally clean lanes.
            for off, src in enumerate(line.bytes):
                backing[line.base+off] = ByteCell(src.value, src.chain + (f"dcache_writeback:g{seq}:{line.base+off:08x}",))
            audit.append(f"{seq}:writeback:{line.base:08x}:full16:dirty={line.dirty_mask:04x}")

        elif kind == "fetch_begin":
            fid = event["id"]
            if fid in fetch_ctx:
                raise Reject("duplicate fetch context")
            fetch_ctx[fid] = {"begin": seq, "paddr": event["paddr"], "reads": [], "ended": False}

        elif kind == "backing_read":
            fid = event["id"]
            ctx = fetch_ctx.get(fid)
            if ctx is None or ctx["ended"]:
                raise Reject("backing read outside fetch context")
            if event["paddr"] != ctx["paddr"]:
                raise Reject("fetch backing address mismatch")
            cells = tuple(backing[event["paddr"] + i] for i in range(4))
            actual = bytes_word(cells)
            if event["value"] != actual:
                raise Reject("fetch backing payload mismatch")
            ctx["reads"].append((seq, event["paddr"], actual, cells))

        elif kind == "fetch_end":
            fid = event["id"]
            ctx = fetch_ctx.get(fid)
            if ctx is None or ctx["ended"]:
                raise Reject("fetch end without active context")
            if event["paddr"] != ctx["paddr"]:
                raise Reject("fetch end address drift")
            reads = ctx["reads"]
            if len(reads) != 1:
                raise Reject("uncached fetch lacks exactly one backing read")
            rseq, paddr, value, cells = reads[0]
            if not (ctx["begin"] < rseq < seq):
                raise Reject("backing read not bracketed by fetch")
            if event["value"] != value:
                raise Reject("fetch result does not match backing read")
            ctx["ended"] = True
            certs[fid] = {
                "fetch_end_seq": seq,
                "read_seq": rseq,
                "paddr": paddr,
                "value": value,
                "byte_chains": [list(c.chain + (f"fetch_read:g{rseq}:{paddr+i:08x}",)) for i, c in enumerate(cells)],
            }
            audit.append(f"{seq}:fetch:{fid}:{paddr:08x}:read_g{rseq}")
        else:
            raise Reject(f"unknown event {kind}")

    if expect_all_fetches and set(certs) != {"copied", "clean", "post_patch"}:
        raise Reject("missing expected fetch certificate")
    if any(not c["ended"] for c in fetch_ctx.values()):
        raise Reject("unterminated fetch context")
    return {"certificates": certs, "audit": audit, "writeback": writeback_snapshot}

def require_contains(chain, token):
    if not any(token in x for x in chain):
        raise AssertionError(f"missing {token} in {chain}")

def validate_canonical(result):
    copied = result["certificates"]["copied"]
    clean = result["certificates"]["clean"]
    patched = result["certificates"]["post_patch"]

    # Copied word must preserve the original source backing through source fill,
    # exact load/register generation, cached destination store, full writeback,
    # and exact fetch backing read.
    for chain in copied["byte_chains"]:
        require_contains(chain, "initial:source:")
        require_contains(chain, "dcache_fill:g2:")
        require_contains(chain, "reg:t0:g3:")
        require_contains(chain, "dcache_store:g6:")
        require_contains(chain, "dcache_writeback:g9:")
        require_contains(chain, "fetch_read:g12:")
        if any("source_alias_patch" in x for x in chain):
            raise AssertionError("post-load source backing patch stole cached-copy ancestry")

    # Clean word was not locally dirtied, but the full-line writeback still
    # overwrites the poisoned backing and must retain destination-fill ancestry.
    for chain in clean["byte_chains"]:
        require_contains(chain, "initial:dest:")
        require_contains(chain, "dcache_fill:g3:")
        require_contains(chain, "dcache_writeback:g9:")
        require_contains(chain, "fetch_read:g15:")
        if any("clean_lane_poison" in x for x in chain):
            raise AssertionError("dirty-mask shortcut preserved poisoned clean backing")

    # Equal payload after writeback is a new backing writer generation.
    for chain in patched["byte_chains"]:
        require_contains(chain, "same_value_post_writeback_patch")
        require_contains(chain, "fetch_read:g19:")
        if any("dcache_writeback:g9:" in x for x in chain):
            raise AssertionError("same-value overwrite failed to cut older ancestry")

    wb = result["writeback"]
    if wb["dirty_mask"] != 0x000f or wb["tag"] != 0x2001 or wb["slot"] != 0:
        raise AssertionError("unexpected canonical writeback identity")

def mutate(events, name):
    e = deepcopy(events)
    if name == "equal_payload_wrong_source":
        load = next(x for x in e if x["kind"] == "load")
        load["paddr"] = 0x1100
    elif name == "dirty_mask_as_write_width":
        next(x for x in e if x["kind"] == "writeback")["width"] = 4
    elif name == "slot_retag_before_writeback":
        wb_i = next(i for i,x in enumerate(e) if x["kind"] == "writeback")
        fill_i = next(i for i,x in enumerate(e) if x["kind"] == "fill" and x["base"] == 0x4000)
        e[wb_i], e[fill_i] = e[fill_i], e[wb_i]
        # Renumber in list order to isolate semantic reorder rather than fail
        # merely on descending sequence IDs.
        for n,x in enumerate(e, start=1):
            x["seq"] = n
    elif name == "omitted_writeback":
        e = [x for x in e if x["kind"] != "writeback"]
    elif name == "omitted_fetch_read":
        e = [x for x in e if not (x["kind"] == "backing_read" and x["id"] == "copied")]
    elif name == "fetch_wrong_backing":
        read = next(x for x in e if x["kind"] == "backing_read" and x["id"] == "copied")
        read["paddr"] = 0x2004
        read["value"] = 0x01020304
    elif name == "forged_same_value_old_ancestry":
        return e
    else:
        raise KeyError(name)
    return e

def main():
    events = canonical_events()
    result = replay(events)
    validate_canonical(result)

    rejected = {}
    for name in [
        "equal_payload_wrong_source",
        "dirty_mask_as_write_width",
        "slot_retag_before_writeback",
        "omitted_writeback",
        "omitted_fetch_read",
        "fetch_wrong_backing",
    ]:
        try:
            replay(mutate(events, name))
        except Reject as exc:
            rejected[name] = str(exc)
        else:
            raise AssertionError(f"forgery unexpectedly accepted: {name}")

    # Certificate-only same-value forgery: history says post-patch fetch is rooted
    # in generation 17. Claiming generation 9 must be rejected even though bits equal.
    patched_chain = result["certificates"]["post_patch"]["byte_chains"][0]
    if any("dcache_writeback:g9:" in x for x in patched_chain) or not any(
        "same_value_post_writeback_patch" in x for x in patched_chain
    ):
        raise AssertionError("same-value provenance substitution was not rejected")
    rejected["forged_same_value_old_ancestry"] = "post-patch fetch roots in backing_write g17, not writeback g9"

    summary = {
        "ares_pin": ARES_PIN,
        "prior_receipts": PRIOR,
        "canonical": {
            "copied_fetch_value": f"{result['certificates']['copied']['value']:08x}",
            "clean_fetch_value": f"{result['certificates']['clean']['value']:08x}",
            "post_patch_fetch_value": f"{result['certificates']['post_patch']['value']:08x}",
            "writeback_dirty_mask": f"{result['writeback']['dirty_mask']:04x}",
            "writeback_width": 16,
            "copied_root": "initial:source",
            "clean_root": "initial:dest",
            "post_patch_root": "same_value_post_writeback_patch",
        },
        "rejected_forged_histories": rejected,
        "audit": result["audit"],
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()
    print(json.dumps(summary, sort_keys=True, indent=2))
    print(f"REPORT_SHA256={digest}")
    print("PASS: cached-copy lineage survives resident D-cache -> full-line writeback -> exact uncached fetch without value-equality shortcuts")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
