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
  This compile-only harness never executes generated host code.
- A separate headless execution harness runs synthetic integer/control programs
  on the actual pinned x64 dynarec and pure interpreter. Full GPR/HI/LO/PC results
  agree, with tracing enabled and disabled. Source-correlated in-unit JR/JALR
  events cover general lookup and inline return-cache hits. Unsupported runtime
  services trap; flat memory and a sentinel stop policy exclude boot/devices/timing.
- Signature-based z64/v64/n64 normalization, canonical SHA-256 and header parsing.
- Pinned Rabbitizer direct CFG with delay slots, branch-likely annulment, calls,
  return continuations, block repartitioning and explicit unresolved paths.
- Deterministic static/dynamic merger retaining provenance and contradictions.
  Raw indirect observations survive ambiguous image identities. Target compilation
  may follow an execution event; joins stay within the same invalidation epoch.
- Bounded local constant-target certificates, independent rechecking and recursive
  traversal of inferred in-image targets. Repartitioning can revoke a certificate
  while retaining its candidate evidence.
  Restricted cross-block certificates propagate through single-predecessor scalar
  chains and selected branch delay slots. They reconstruct CFG from bytes and
  reject joins, calls, loops, incoming unknown entries and unsupported effects.
- Canonical-byte-verified executable loads joined to DMA observations. Reloads
  preserve generations; overlapping sources are overlay candidates, and changed
  bytes remain unclassified executable-write blockers.
- Fail-closed solver reports and rechecks CFG/certificates against source bytes,
  including omitted and contradictory extra facts. Finite trace samples do not
  close indirect sites.

Verification: 50 Rust integration tests, formatting, strict Clippy, CLI integration,
strict C99 exporter, actual pinned Mupen hook and CPU execution integration pass.
The patch also passes application checking against the clean pinned Git index.
Rust/CLI/compile-only tests use Windows, Rust 1.98, Python 3.12 and GCC 15.2.
Execution tests use x64 Linux under WSL Ubuntu with GCC and NASM; other CPU hosts
are unverified.

`discover` still requires an explicit ROM/load mapping. `import-trace` checks the
canonical ROM and verifies captured DMA-backed code bytes. `solve [rom] map` emits
whole-ROM diagnostics; supplying the ROM provides hash-checked source witnesses.
Command success means a report was produced, not that the report is CLOSED.

A declared immutable, nontrapping integer-image scope can close with explicit
exclusions. Whole-ROM mode remains OPEN and `native_complete` is always false.
There is no native output, game compatibility claim or performance claim.

Remaining gaps: full reference sessions with devices, pagespan indirect execution
correlation, non-x64 runtime hooks, general join/loop and table proofs, automatic boot/CIC
roots, overlay/relocation lifecycle, non-PI copies, exceptions/TLB/execution modes,
executable mutation and RSP policies. Header CRC fields are parsed, not verified.
Analysis scalability has not been benchmarked. See NEXT for the execution order.
