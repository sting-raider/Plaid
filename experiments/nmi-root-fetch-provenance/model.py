#!/usr/bin/env python3
"""Adversarial proof-composition model for NMI root transfer vs root-byte execution."""
from dataclasses import dataclass
import hashlib, json

ROOT = 0xFFFFFFFFBFC00000

@dataclass(frozen=True)
class Row:
    kind: str
    ctx: int | None = None
    pc: int | None = None
    offset: int | None = None
    word: int | None = None
    pending: bool | None = None
    source: str | None = None


def certify(rows):
    root_seen = False
    pending = None
    active = None
    reads = {}
    executed = []
    for i, r in enumerate(rows):
        if r.kind == "nmi_transfer":
            assert r.pc == ROOT
            root_seen = True
            pending = True
            active = None
        elif r.kind == "pending":
            pending = r.pending
        elif r.kind == "fetch_begin":
            if not root_seen or r.pc != ROOT or pending:
                continue
            active = r.ctx
        elif r.kind == "pif_read":
            if active == r.ctx and r.offset == 0:
                reads[r.ctx] = (r.word, i)
        elif r.kind == "fetch_end":
            if active != r.ctx or r.pc != ROOT:
                active = None
                continue
            witness = reads.get(r.ctx)
            if witness and witness[0] == r.word and r.source == "pif_rom":
                executed.append((r.ctx, r.word, witness[1], i))
            active = None
    return executed


def main():
    word = 0x3C1A1234
    cases = {
        "correct": [Row("nmi_transfer", pc=ROOT), Row("pending", pending=False), Row("fetch_begin", 7, ROOT), Row("pif_read", 7, offset=0, word=word), Row("fetch_end", 7, ROOT, word=word, source="pif_rom")],
        "transfer_only": [Row("nmi_transfer", pc=ROOT)],
        "persistent_reentry": [Row("nmi_transfer", pc=ROOT), Row("nmi_transfer", pc=ROOT)],
        "foreign_equal_read": [Row("pif_read", 3, offset=0, word=word), Row("nmi_transfer", pc=ROOT), Row("pending", pending=False), Row("fetch_begin", 7, ROOT), Row("fetch_end", 7, ROOT, word=word, source="pif_rom")],
        "pending_fetch_forgery": [Row("nmi_transfer", pc=ROOT), Row("fetch_begin", 7, ROOT), Row("pif_read", 7, offset=0, word=word), Row("fetch_end", 7, ROOT, word=word, source="pif_rom")],
        "latch_equal_payload": [Row("nmi_transfer", pc=ROOT), Row("pending", pending=False), Row("fetch_begin", 7, ROOT), Row("fetch_end", 7, ROOT, word=word, source="si_latch")],
        "wrong_context": [Row("nmi_transfer", pc=ROOT), Row("pending", pending=False), Row("fetch_begin", 7, ROOT), Row("pif_read", 8, offset=0, word=word), Row("fetch_end", 7, ROOT, word=word, source="pif_rom")],
        "wrong_offset": [Row("nmi_transfer", pc=ROOT), Row("pending", pending=False), Row("fetch_begin", 7, ROOT), Row("pif_read", 7, offset=4, word=word), Row("fetch_end", 7, ROOT, word=word, source="pif_rom")],
    }
    verdicts = {name: certify(rows) for name, rows in cases.items()}
    assert len(verdicts["correct"]) == 1
    assert all(not verdicts[name] for name in cases if name != "correct")
    payload = {
        "root": ROOT,
        "cases": {k: bool(v) for k, v in verdicts.items()},
        "forgeries_rejected": len(cases) - 1,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    payload["sha256"] = hashlib.sha256(encoded).hexdigest()
    print(json.dumps(payload, sort_keys=True))
    print("PASS root transfer alone cannot certify executed PIF root bytes")

if __name__ == "__main__":
    main()
