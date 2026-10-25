# Rogue Squadron: Create Dirty Exclusive

Worker rs-cache-cde-67acc414; prepared base
`a1c570a1678dbcb6d128cffe2599326253b147bc`; ADR-0271.
No child agents. README is integrator-owned and untouched.

## Model and independent evidence

Exact ares pin: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
Read-only source inspection: `ares/n64/cpu/interpreter-ipu.cpp` CACHE,
`dcache.cpp` line hit/fill/write/writeBack/power, and the ISC license.
The shared reference was not fetched or modified. A private copy of the
current synthetic oracle is checked against the pinned revision and current
driver SHA256 before each comparison. No upstream source was copied into
production; ignored oracle copies retain their licenses.

NEC VR4300/VR4305/VR4310 user manual, CACHE operation table (printed p404):
https://hack64.net/docs/VR43XX.pdf . CDE sets the physical tag and dirty state
without loading RAM, writing back a different dirty victim. Pinned ares
retains the slot words and writes the victim, but clears its internal dirty
mask on a miss; subsequent stores dirty it. Native follows the manual on
this point. Tests do not describe pre-store writeback agreement with ares.

RAM continues to hold the latest native stores. A CDE retag snapshots known
old-slot bytes in dold/dstale; no target RAM fill occurs. A new per-slot
16-bit dunknown mask represents invalid-slot bytes that this model did not
retain. Writes clear only their byte bits. Reading unknown bytes faults 4;
known retained stale bytes remain readable. Full-line writes recover every
byte. If unknown dirty bytes are written back/evicted, mark destination RAM
line_lost so CPU and DMA cannot observe invented data. This is conservative:
invalidated slots may contain deterministic old bytes in ares, but native
has no witness for them. Discarded/lost lines keep their existing refusal.
Protected code, physical aliases, translation and non-RAM checks remain.

Native/ares tests compare full GPR/FPR/PC/HI/LO/FCSR and the 256-byte oracle
RAM log window for positive cases, plus SDK-runtime stop/dump behavior:

- allocate, overwrite four words, write back and inspect uncached;
- conflicting dirty victim written before new stores;
- old-slot read on retag, including an uncached overwrite making bytes stale;
- same-tag hit preserves contents;
- unknown read, known partial write followed by unknown read, partial writeback.

A separate native state contract checks manual dirty state before stores,
byte-mask recovery, known-byte read, exact read fault PC, writeback without
new stores, mapped physical tag, opposite-index alias, noncanonical/unmapped/
non-RAM addresses and user-mode refusal. Timing/event scope is unchanged
from the existing cache model; this is not a cycle-accuracy certificate.

Removing the generated unknown-read guard makes the unknown fixture exit
with fault 0 and the retained assertion fails (mutation killed; source restored).
The focused comparisons pass with the guard intact. Exact mutation timing
and initial compiler-warning correction are in ignored receipt logs.

## Reachability census and native result

Lowered-code CACHE census from the retained authenticated game maps:
RS: seven CDE sites (8000041c, 800137d8/dc/e0/e4, 8001399c, 80095040),
two Hit WB Invalidate, one Hit Invalidate and one Index WB Invalidate.
MP2: Index Store Tag I, Index WB Invalidate D, Index Invalidate I.
PM/BK/MM/SF64/OoT: no lowered CACHE sites (SDK replacements do maintenance).
There is no other unsupported form in this finite lowered scope. This is
not a proof of whole-ROM reachability. Index Load Tag needs retained invalid
tags, which the current model does not track; it remains refused.

ROM is user-supplied Rogue Squadron USA Rev1, SHA256
`4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d`.
Matched visible silent 30-second requests terminate early:

- before: VI 0/fault 12/PC 8000041c/RA 80001eb0;
- after: VI 0/fault 12/PC 80025bf4/RA 80025bb0, approximately 1.141s native.

Both have zero graphics/audio/PI counts and framebuffer 0. No game frame,
title or menu is reached, so there is no menu to drive with Start/A.
Build remains native_complete:false with 19 residual sites and zero blockers.

Next stop is MTC0 Status (`409b6000`) in raw SDK thread dispatch. Saved value
is 0000ff03 (IE and EXL set). Identification has 14 runtime functions and
misses thread create/start; host thread list is empty. The transition needs
a saved context/Status/EPC/ERET and scheduler contract, or authenticated SDK
body identification. It is not a small cache/COP0 extension: accepting the
Status write alone would bypass the existing interrupt/scheduler guard.
No such bypass was added. Generic identification/context work is next.

## Validation and integration receipt

All game runs use SDL_AUDIODRIVER=dummy and visible windows. Controls regenerate
CPU/RSP C from current lowering using retained ROM-content-verified load
inputs. Object reuse is checked by source/compiler/dependency/flag hashes.
The existing shared RT64 DLLs are copied into a local game-windows directory;
the shared shim is not rebuilt or overwritten. Shared .refs, oracle and shim
junction targets are untouched; no recursive deletion is used.

Required controls: PM/BK/MM/SF64/OoT 30s, MP2 30s with Start 600/1250 and
A 1360/1440/1520/1600/1680/1760 (all 4 retraces), plus OoT 60s saved-SRAM
reproduction with Start 1200 and A 1400/1550/1700/1850 (all 4 retraces).
Exact VI/fault/PC, native/pipeline timings and captured scenes are retained
in target/receipts/rs-cache-cde/*-run.json and the issue #4 closeout. Broad
visual/gameplay acceptance is not inferred from a fault 0 control.

The final staged tree is frozen across each required local command:

```text
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Per-command exits/timings, before/after native stops, cache census, mutation,
control screenshots and exact validated base/tree/landed SHA are in ignored
receipts and canonical issue #4 closeout. Fetch/head comparison and ordinary
fast-forward push serialize integration; no force flags, CI gate or PR.
No ROMs, copyrighted assets, screenshots, maps or saves are committed.
