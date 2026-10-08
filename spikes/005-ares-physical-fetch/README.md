# Actual physical fetch access

Hypothesis: sampling the effective physical address and cache selection already
computed by the pinned CPU fetch function preserves execution and supplies
mapping context independently of virtual-PC guesses. The observer performs no
extra guest reads or translations and keeps code generation/lifetime unknown.

Record metadata after the reference's endian address adjustment, before the
existing cache/bus read. A namespace metadata value adds no CPU object fields or
layout changes. The existing debugger callback pairs it with the exact fetched
word/PC/delay-slot state. Disable CPU/RSP recompilation. This is an isolated
generated research instrument with upstream notices; no reference code enters
Plaid core or native mode.

Check a five-million-call untouched homebrew run against plain/repeat CPU,
memory/Count checkpoints and the v0 stream's entire PC/word/slot projection.
Keep mapped cartridge size explicit: the pinned loader rounds capacity down to
eight bytes, so file length alone cannot establish the mapped final word.

Run `python spikes/005-ares-physical-fetch/run.py` after spike 004 has produced
its ignored reference checkpoint. Windows uses WSL Ubuntu/G++ C++20. All outputs,
generated reference code and the preserved upstream LICENSE stay under ignored
`target/ares-physical-fetch-spike/`.

## Verdict: VALIDATED

### Evidence

- The five-million-call prefix records 4,999,998 fetches: 4,806,689 cached and
  193,309 uncached, with 53,037 virtual/physical/cache tuples.
- Plain/traced/repeated full CPU/Count and RAM/SP checkpoints, guest messages and
  repeated streams match. The complete PC/word/slot projection has the exact v0
  SHA-256 `2657fb26ab09059050e6d2a23e6c7e984f3ece26544db994c7fcf3a9a5abb78c`.
- The v1 stream is 628,211,919 bytes, SHA-256
  `c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1`.
- The fixture checks cached stale words, uncached aliases, explicit invalidation,
  two TLB physical mappings for one PC and user reverse-endian word selection.

### Constraints and surprises

The effective address is the argument used by the fetch/cache path, not proof of
the underlying word's source. Cached data may predate current RAM; physical
metadata supplies no copy, generation or executable lifetime. The source hook
records only after successful translation and endian selection. It performs no
extra reads/translations and changes no CPU object layout or opcode behavior.
Moving a generated CPU TU initially selected system/serialization.cpp through a
same-named relative include; all generated CPU includes now resolve explicitly
to their pinned originals.

The mapped cartridge capacity is 2,742,280 bytes, four fewer than the canonical
file. PIF/IPL2 provenance, startup Config mismatch and finite budget remain the
same limits as spike 004. No complete-suite or native execution is claimed.

### Recommendation

Promote only project-owned physical-access data handling through a separate
decision. Preserve all variants, full raw source and v0 compatibility; keep the
independent unknown-execution-identity solver blocker. Establish source and
lifecycle witnesses separately before constructing executable images.
