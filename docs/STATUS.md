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
  agree on eight scenarios, with tracing enabled and disabled. Source-correlated
  x64 JR/JALR events cover in-unit and pagespan transfers, general lookup and
  inline return-cache hits. Custom links, likely annulment and register stress pass.
  Unsupported runtime
  services trap; flat memory and a sentinel stop policy exclude boot/devices/timing.
- A full pinned core session uses an original bootstrap, real PI DMA, RAM
  store/load and IS64 MMIO completion, with bundled dummy plugins. All GPRs,
  HI/LO/PC agree across interpreter/traced/untraced dynarec. Repeated 42-event
  traces match, and executed DMA-backed units import with verified ROM sources.
  Two further sessions replace the executable payload at the same physical RAM,
  using cached or uncached entry. Their 81/80-event traces and CPU states match;
  generations remain separate and explicit physical overlaps yield overlay
  candidates even when guest addresses differ. No alias identities are collapsed.
  A CPU-store mutation session executes changed instructions and retains unknown
  write/source blockers (78 events); a CPU-copy session executes cartridge reads
  and RAM stores without inventing PI DMA or verified load sources (33 events).
  With the new limited SW sensor enabled, the six full-core sessions produce
  43/83/82/82/34/48 deterministic events. Constant aligned cached-RDRAM stores
  retain source PC, destination and value; overlap with previously compiled
  physical regions adds Unknown executable-write evidence. A register/zero/
  delay-slot store stress fixture preserves full CPU state. Its invalidations
  expose executing-unit and restored-target identity gaps. Explicit source-unit
  tags identify the still-running older call unit. A successful dirty-entry lookup
  now supplies a byte-checked target snapshot for its pending return (49 events);
  competing identities and unsensed restore paths remain unresolved.
  PIF HLE/unknown-CIC fallback, dummy graphics/audio/RSP and a frontend stop
  request bound this synthetic session's scope; whole-ROM closure remains OPEN.
- Signature-based z64/v64/n64 normalization, canonical SHA-256 and header parsing.
- Pinned Rabbitizer direct CFG with delay slots, branch-likely annulment, calls,
  return continuations, block repartitioning and explicit unresolved paths.
- Deterministic static/dynamic merger retaining provenance and contradictions.
  Raw indirect observations survive ambiguous image identities. Target compilation
  may follow an execution event within its invalidation epoch. Explicit completed
  source-unit context identifies older executing units without guessing by PC;
  legacy events keep conservative same-epoch source joins. Targets retain the
  epoch restriction. Source-unit provenance is qualified by trace session.
  A dirty-entry snapshot check may identify a pending older target before the next
  invalidation. Captured words and installed entry/mask must match its completed
  unit. These raw checks are neither new compilations/copies nor execution proof.
  Imported sensor/write/diagnostic facts coalesce repeated semantics while
  retaining every event reference. Imports and expanded conflict diagnostics
  remain byte-identical when merged with themselves.
- Bounded local constant-target certificates, independent rechecking and recursive
  traversal of inferred in-image targets. Repartitioning can revoke a certificate
  while retaining its candidate evidence.
  Restricted cross-block certificates propagate through single-predecessor scalar
  chains and selected branch delay slots. They reconstruct CFG from bytes and
  reject joins, calls, loops, incoming unknown entries and unsupported effects.
  A guarded SLTIU/branch/SLL/ADDU/LW dispatch recognizer enumerates up to 256
  pointer-table snapshot entries as candidates, preserving hashes/assumptions.
  Missing sources and malformed pointers are explicit; immutability remains open.
- Canonical-byte-verified executable loads joined to DMA observations. Reloads
  preserve generations; overlapping sources are overlay candidates, and changed
  bytes remain unclassified executable-write blockers.
  Load mappings retain a separate copy-event reference with typed DMA/source/
  physical coverage checks. Recompilation under one event cannot establish reload;
  legacy maps lacking the reference retain uncertainty.
- Fail-closed solver reports and rechecks CFG/certificates against source bytes,
  including omitted and contradictory extra facts. Finite trace samples do not
  close indirect sites.
  Observations may extend incomplete candidate hypotheses without a contradiction;
  disagreement diagnostics require a claimed exhaustive target certificate.
- A disposable pinned spimdisasm/Rabbitizer comparison covers four original
  mapped fixtures. Direct-call/function and guarded-table hints are useful, but
  function extents include unreachable/padding words and truncated returns still
  need blockers. Manual section/mapping inputs and the shared decoder limit the
  result. No production adapter or runtime dependency is introduced.
- A larger pinned MIT n64-systemtest source build produces a deterministic
  2,742,284-byte research ROM with exact nightly and pinned nust64 packaging.
  The headless probe is PARTIAL: the dynarec exits on cartridge execution at
  B0001040; its incomplete trace is rejected. The pure interpreter reports nine
  upstream failures and stops on unimplemented LLD. This identifies broader
  source/oracle gaps; neither test-suite completion nor native execution is claimed.

Verification: 63 Rust integration tests, formatting, strict Clippy, CLI integration,
strict C99 exporter, actual pinned Mupen hook, CPU and full-core session tests pass.
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

Remaining gaps: broader reference sessions and device coverage, ProgramMap predecessor
state for pagespan entries, non-x64 runtime hooks, general join/loop and
immutable-table proofs, automatic boot/CIC
roots, overlay/relocation lifecycle, non-PI copies, exceptions/TLB/execution modes,
complete store/mutation and RSP policies. Header CRC fields are parsed, not verified.
Analysis scalability has not been benchmarked. See NEXT for the execution order.
