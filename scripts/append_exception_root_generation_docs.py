#!/usr/bin/env python3
"""One-shot direct-integration helper for canonical exception-root docs."""
from pathlib import Path

UPDATES = {
    "docs/STATUS.md": """

- Cached BEV=0 general exception-root word provenance now has a bounded source-bound
  replay (ADR-0103). Successful backing writes and I-cache fills retain separate
  ordinal identities, so a backing rewrite does not relabel an older resident
  handler and same-valued writes remain distinct generations. An invalidate/refill
  can advance the supplying generation; a root fetch without captured resident/fill
  evidence remains UNKNOWN even when current RDRAM has equal bytes. This is only the
  validated 32-bit, EXL-clear, identity-RDRAM word at physical 0x180. Reachability,
  source-sensor completeness, full handler spans, mapping/cache lifetime, mutation
  census and whole-ROM/native completeness remain open.
""",
    "docs/NEXT.md": """

Production now also has a bounded source-bound cached BEV=0 general-root Word replay
(ADR-0103). Compose it with authenticated exception classification and BEV/EXL/mode
chronology, complete backing/cache/mapping mutation histories and full handler spans
before treating a selected root as executable provenance. Extend separately to TLB
refill/XTLB roots, BEV=1/PIF-backed roots, interrupts, reset/NMI and other execution
roots. Missing residency stays UNKNOWN; equal current bytes never recover a writer or
fill generation.
""",
    "docs/DECISIONS.md": """

## ADR-0103: Cached exception roots require resident-generation evidence

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

The accepted primitive does not certify source-sensor completeness, exception
reachability, ultimate storage ancestry, arbitrary cache operations, aliases/TLB
mappings, save/restore/reset behavior, the rest of the handler span, mutation or
root census completeness, executable lifetime, hardware-wide semantics, whole-ROM
closure or native completeness. Missing evidence keeps those obligations OPEN.
""",
}

for name, addition in UPDATES.items():
    path = Path(name)
    text = path.read_text()
    if "ADR-0103" in text:
        continue
    path.write_text(text.rstrip() + addition + "\n")
