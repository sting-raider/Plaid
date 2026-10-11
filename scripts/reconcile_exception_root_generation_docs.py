#!/usr/bin/env python3
"""One-shot reconciliation of cached exception-root generation docs onto live main."""
from pathlib import Path

status = Path("docs/STATUS.md")
text = status.read_text()
marker = "Cached BEV=0 general exception-root word provenance now has a bounded source-bound replay"
if marker not in text:
    text = text.rstrip() + """

- Cached BEV=0 general exception-root word provenance now has a bounded source-bound
  replay (ADR-0104). Successful backing writes and I-cache fills retain separate
  ordinal identities, so a backing rewrite does not relabel an older resident
  handler and same-valued writes remain distinct generations. An invalidate/refill
  can advance the supplying generation; a root fetch without captured resident/fill
  evidence remains UNKNOWN even when current RDRAM has equal bytes. This is only the
  validated 32-bit, EXL-clear, identity-RDRAM word at physical 0x180 and is separate
  from ADR-0103's BEV=1/PIF root provenance. Reachability, source-sensor completeness,
  full handler spans, mapping/cache lifetime, mutation census and whole-ROM/native
  completeness remain open.
""" + "\n"
    status.write_text(text)

next_path = Path("docs/NEXT.md")
text = next_path.read_text()
marker = "bounded source-bound cached BEV=0 general-root Word replay"
if marker not in text:
    text = text.rstrip() + """

Production now also has a bounded source-bound cached BEV=0 general-root Word replay
(ADR-0104). Compose it with authenticated exception classification and BEV/EXL/mode
chronology, complete backing/cache/mapping mutation histories and full handler spans
before treating a selected root as executable provenance. ADR-0103 separately binds
one BEV=1 root occurrence to exact PIF backing; neither decision proves root
reachability or census completeness. Extend separately to TLB refill/XTLB roots,
interrupts, reset/NMI and other execution roots. Missing residency stays UNKNOWN;
equal current bytes never recover a writer or fill generation.
""" + "\n"
    next_path.write_text(text)

decisions = Path("docs/DECISIONS.md")
text = decisions.read_text()
if "## ADR-0104: Cached exception roots require resident-generation evidence" not in text:
    text = text.rstrip() + """

## ADR-0104: Cached exception roots require resident-generation evidence

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-11.

Compose ADR-0101's architectural root candidate with a separate source-bound finite
chronology for the validated BEV=0 general exception word. In the accepted scope the
root is `ffffffff80000180`, backed by identity RDRAM physical `0x180`, with EXL clear
and 32-bit kernel context. Every observed successful backing write keeps its own
ordinal identity even when the payload is unchanged. A captured fill binds its own
resident identity to the then-observed backing writer. Later backing writes do not
silently relabel that resident generation; only an observed invalidate/refill can
establish a later resident source. A root fetch whose resident/fill chain is missing
stays UNKNOWN even when current backing contains identical bits.

This rule was reproduced against exact pinned ares by executing a real SYSCALL into
the same numeric vector before and after a backing rewrite: stale resident handler A
continued executing until guest I-cache invalidation, after which refill selected
handler B. The production replay is original Plaid code and consumes only an
externally hash-bound finite history; it does not import reference implementation
code or infer occurrence from snapshots, numeric addresses or value equality.
ADR-0103's BEV=1/PIF root provenance is complementary: it authenticates a supplied
PIF-backed fetch, while this decision authenticates which captured resident/backing
generation supplied one cached BEV=0 root word.

The accepted primitive does not certify source-sensor completeness, exception
reachability, ultimate storage ancestry, arbitrary cache operations, aliases/TLB
mappings, save/restore/reset behavior, the rest of the handler span, mutation or
root census completeness, executable lifetime, hardware-wide semantics, whole-ROM
closure or native completeness. Missing evidence keeps those obligations OPEN.
""" + "\n"
    decisions.write_text(text)

receipt = Path("research/integration-receipts/20261011-exception-root-generation-gpt56sol-direct-exception-generation-20261011.md")
text = receipt.read_text().replace("ADR-0103", "ADR-0104")
reconcile_marker = "BEV1/PIF integration advanced canonical main"
if reconcile_marker not in text:
    anchor = "`bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` (ADR-0102 / source-bound TLBWI\noperation generations) before canonical documentation was updated.\n"
    addition = anchor + "\nBEV1/PIF integration advanced canonical main to\n`9154b30b12026c8c122f654d7fe90f0f67968dce` and claimed ADR-0103. The cached-root\nintegration was then rebuilt on that exact tree, preserving `exception_pif` and the\nBEV1 docs; this decision was renumbered ADR-0104.\n"
    if anchor not in text:
        raise SystemExit("receipt reconciliation anchor missing")
    text = text.replace(anchor, addition)
receipt.write_text(text)
