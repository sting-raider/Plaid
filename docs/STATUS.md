# Status

2026-10-08. Milestone scope: M1–M3 synthetic executable discovery foundation.

Implemented:

- ProgramMap v0: typed ROM/guest/physical identities, image generations, executable
  regions, blocks, entries, edges, indirect candidates/observations, overlays,
  DMA/load mappings, relocations, writes, microcode identities and provenance.
  Serialization is deterministic; validators reject invalid versions, ranges,
  missing evidence and duplicate keys.
- Discovery trace v0: guest compilation units and captured words, installed
  entries/masks, links, lookups, invalidation and actual ROM DMA copies. No host
  pointer identities. Contiguous sequences and a complete footer are required.
- Separate GPL instrument against pinned Mupen: the actual recompiler and
  cartridge copy handler pass a synthetic four-unit harness, including pagespan
  entry installation, outgoing links, invalidation and clipped DMA transfers.
  Generated host code is never executed; runtime helper traps guard that boundary.
  This verifies compilation/copy hooks, not a running N64 CPU behavioral oracle.
- Signature-based z64/v64/n64 normalization, canonical SHA-256 and header parsing.
- Pinned Rabbitizer direct CFG with delay slots, branch-likely annulment, calls,
  return continuations, block repartitioning and explicit unresolved paths.
- Deterministic static/dynamic merger retaining provenance and contradictions.
- Bounded local constant-target certificates, independent rechecking and recursive
  traversal of inferred in-image targets. Repartitioning can revoke a certificate
  while retaining its candidate evidence.
- Canonical-byte-verified executable loads joined to DMA observations. Reloads
  preserve generations; overlapping sources are overlay candidates, and changed
  bytes remain unclassified executable-write blockers.
- Fail-closed solver reports and rechecks CFG/certificates against source bytes,
  including omitted and contradictory extra facts. Finite trace samples do not
  close indirect sites.

Verification: 45 Rust integration tests, formatting, strict Clippy, CLI integration,
strict C99 exporter tests and actual pinned Mupen hook integration all pass.
The patch also passes application checking against the clean pinned Git index.
Tested on Windows with Rust 1.98, Python 3.12 and GCC 15.2; other hosts are unverified.

`discover` still requires an explicit ROM/load mapping. `import-trace` checks the
canonical ROM and verifies captured DMA-backed code bytes. `solve [rom] map` emits
whole-ROM diagnostics; supplying the ROM provides hash-checked source witnesses.
Command success means a report was produced, not that the report is CLOSED.

A declared immutable, nontrapping integer-image scope can close with explicit
exclusions. Whole-ROM mode remains OPEN and `native_complete` is always false.
There is no native output, game compatibility claim or performance claim.

Remaining gaps: running reference execution, source-correlated JR/JALR events,
inline assembly lookup coverage, cross-block/table proofs, automatic boot/CIC
roots, overlay/relocation lifecycle, non-PI copies, exceptions/TLB/execution modes,
executable mutation and RSP policies. Header CRC fields are parsed, not verified.
Analysis scalability has not been benchmarked. See NEXT for the execution order.
