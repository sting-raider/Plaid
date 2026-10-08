# Status

2026-10-09. Milestone scope: M1–M3 synthetic executable discovery foundation.

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
- A separately built pinned ares interpreter oracle passes four original cartridge,
  LLD/SCD and address-error fixtures, including BD/EPC/BadVAddr and memory results.
  Its full GPR/HI/LO/PC state matches all eight existing Mupen integer/control
  fixtures across pure/traced/untraced modes; repeated states match exactly.
  Explicit initial state, renderer-owned hidden-RAM backing supplied by the
  harness, and a generated non-Vulkan renderer guard bound the scope. No boot,
  FPU/TLB, RSP or full homebrew-suite correctness is claimed.
- A separate ares debugger-based raw fetch probe executes the untouched pinned
  homebrew with a declared synthetic SP/IPL3 entry. At five million instruction
  calls it records 4,999,998 actual fetches and 52,424 RAM/548 SP/65 cartridge
  addresses. All cartridge words match the canonical ROM. Repeated 465,553,451-byte
  streams and plain/traced GPR/HI/LO/PC/Count, RAM/SP hashes and guest messages
  agree. A generated const accessor exposes the existing debugger word; CPU
  instruction code is unchanged. Startup Config mismatch and missing PIF/IPL2
  provenance remain explicit. The budget stop is not guest completion. This raw
  research format now imports as conservative raw summaries; it has no copy/lifetime
  or executable-generation inference.
- A generated ares fetch observer also records the existing effective physical
  word address and cache policy. Its five-million-call run has 4,806,689 cached
  and 193,309 uncached fetches; full checkpoints and the entire v0 projection
  match. Stale-cache/uncached-alias, invalidation, TLB-remapping and reverse-endian
  fixtures pass. Mapped cartridge capacity is explicitly 2,742,280 bytes, four
  fewer than file length. Access context supplies no backing or lifetime proof.
- Streaming raw-fetch import preserves typed 64-bit PCs, word/slot variants and
  capture-qualified exact first/last indices/counts. Complete raw-file SHA-256,
  strict sequence/footer/budget checks and a source rechecker protect provenance.
  Legacy maps default the new fields; merge retains capture identities and remains
  idempotent. Raw facts create no regions, blocks, entries, DMA or generations.
  An independent solver blocker prevents unresolved raw identities from closing
  even an otherwise closed declared-image CFG. The broad stream yields 53,037
  summaries in a 20,053,874-byte map, accounts for all 4,999,998 fetches, verifies
  against its complete raw source and self-merges byte-identically.
- Research v1 imports typed effective physical/cache facts with explicit mapped
  capacity. Remapping/cache variants remain distinct and source verification
  rechecks them. V0 bytes stay identical; mixed captures merge conservatively.
  Physical context creates no backing source, image or code-generation proof.
  Full v1 corpus verification accounts for all fetches in a 24,203,476-byte map;
  raw v1 data is 628,211,919 bytes. Both self-merge byte-identically and stay OPEN.
- A bounded ROM-device source experiment records actual delegated halfword reads.
  Direct/TLB/reverse-endian fetches acquire three source witnesses; identical PI
  latch words, unmapped file tail and prior data reads remain unknown. Original/
  plain/traced/repeated GPR/HI/LO/PC/Count/exception/PI checkpoints agree. Broader
  source capture and production source/lifecycle handling remain unimplemented.
- Broader source sensing now verifies 1,852 actual ROM reads at 65 canonical
  offsets, while retaining 4,998,146 unknown sources. Complete v1 projection,
  CPU/Count/RAM/SP/message checkpoints and repeated v2 streams match. V2 is
  768,248,958 bytes. Production source handling and executable lifetimes remain
  separate work.

- Research v2 source facts now import with strict policy/access/capacity checks and
  canonical word verification. Known and unknown variants remain distinct; the
  full raw-source rechecker protects their provenance. V0/v1 maps remain byte-
  identical. No regions, entries, copies, images or lifetimes are fabricated.
  Complete v2 import accounts for all fetches in 53,037 facts (65 known-source,
  52,972 unknown-source), verifies raw provenance and self-merges byte-identically.
  Its map is 27,016,450 bytes; the solver remains OPEN/native_complete=false.

- A bounded CPU power-entry experiment loads the existing ignored NTSC PIF
  firmware through the system pak, without host SP copying or register/PC seeds.
  Plain/traced/repeated CPU/COP0/PIF/PI/Count/RAM/SP checkpoints agree at one
  and ten million calls. Firmware sets Config 7006E463 and passes the checksum
  stage. The longer prefix leaves PI polling and runs StartupTest and subsequent
  cartridge-memory tests with no reported failures; full-suite completion remains
  unverified. Reference PIF HLE, fixed NTSC/6102 profile and finite budget remain
  explicit limitations.
  Research v3 records firmware identity; production rejects this boot scope.
  Firmware bytes remain ignored; no PIF backing or executable lifetime is inferred.
- Research v4 explicitly records firmware hash/size and the complete declared
  boot profile. Its one- and ten-million-call streams preserve the entire v3 projection,
  fixed CPU/device/memory checkpoint and plain/traced/repeat neutrality.
  Production handling now requires supplied-input and full-source verification.
- Research v4 imports typed declared boot inputs through explicit firmware CLI
  commands. Hash/size, complete supported profile and power-entry word/access/slot
  are checked. Full-source rechecking protects facts, metadata and provenance;
  missing/changed/unsupported inputs fail. Legacy maps omit the new field.
  Inputs create no regions, copies or lifetimes; the solver stays OPEN.
  Both complete boot corpora verify supplied firmware and raw provenance and
  self-merge byte-identically: one million fetches yield 1,155 facts in 589,862
  bytes; 9,999,998 fetches yield 54,279 facts in 27,649,768 bytes, including 65
  known-ROM-source facts. V0/v1/v2 map hashes remain unchanged.
- A separate instruction-cache snapshot experiment preserves selected slot/tag/
  index/eight-word context across twelve stale-word, invalidation, eviction,
  TLB/endian and virtual-bank cases. Plain/traced/repeated CPU/Count/COP0 and full
  RAM/cache checkpoints agree. Equal snapshots after eviction or in distinct
  slots prove no lifetime; broader capture and production handling remain open.
- Research v5 now retains selected-cache context on the one-million-call boot
  prefix: 400,954 snapshots at 32 resident tuples, with complete prior stream/
  checkpoint agreement and unchanged repeated CPU/device/memory/cache state.
  The ten-million prefix also matches: 9,399,022 cached fetches at 8,118 resident
  tuples; exact prior streams/checkpoints, repeated bytes and no reported guest
  failures in this finite prefix. Uncached fetches have no snapshot. Production,
  backing and lifecycle work remain separate.
- V5 snapshots now import with strict cache-policy, slot/tag/index/effective-lane
  checks through the supplied-firmware path. Every cached fetch requires a line;
  uncached/older formats forbid it. Distinct slots and resident payload variants
  survive coalescing and merge. Complete-source rechecking catches even unfetched
  lane changes. The one-million corpus verifies all fetches in 1,155 facts,
  self-merges exactly and stays OPEN; its map is 644,693 bytes. The ten-million
  corpus also passes, yielding 54,279 facts in 43,509,988 bytes. V0/v1/v2 and the
  both v4 corpora retain exact map hashes. No fill/lifetime/source identity is inferred.
- An opt-in completed-cache-fill sensor now distinguishes nine actual fills
  across twelve controlled fetches, including equal-payload refills and bank
  aliases. Plain/traced/repeated CPU/timing/RAM/cache goldens match. This observes
  fill event boundaries; tag/invalidation history, backing and general executable
  lifetimes remain unresolved. No production epoch is created.
- Guest CACHE tag stores now have a controlled counterexample: seven guest
  instructions, two fills and two retagged fetches using words from another
  historical fill page. Baseline/plain/traced/repeated CPU/timing/RAM/cache
  checkpoints agree. Effective fetch/tag addresses do not establish byte origin;
  explicit mutation and backing witnesses remain necessary.
- A separate completed-CACHE-operation sensor now records exact PC/operand and
  before/after tag/eight-word transitions for the three controlled guest
  tag-store/index-invalidate operations. Plain/traced/repeated complete goldens
  match. Additional operation outcomes, backing and a unified event history
  remain open; no lifecycle/image identity is promoted.
- Extended guest CACHE outcomes now cover hit/miss invalidation, explicit fill
  and hit/miss writeback: seventeen fetches, eight operations, four fills and one
  writeback. A later uncached fetch checks restored RAM after deliberate backing
  mutation. Separate baseline/plain/traced/repeated complete checkpoints match.
  Identity-mapped controlled RAM is the verified scope; general bus backing,
  failures/reset/restore and unified event/lifetime joins remain open.
- Actual successful identity-mapped RAM burst sensing now records four reads
  matching the fills and one completed write matching the controlled writeback.
  Invalid attempts supply no valid backing witness. Complete prior projection,
  repeated CPU/timing/RAM/cache state and fresh default-observer goldens match.
  Translated/degraded paths, ordinary stores/copies and general lifetimes remain
  unknown. A separate recipe regression prevents stale observer headers on reuse.
- RAM boundary tests now cover remapping, translated stores, zero/partial
  degradation, missing mappings, inactive RI and out-of-bounds access; all stay
  outside the identity-only witness policy. Actual 16/32-byte identity paths
  retain witnesses. Baseline/plain/traced/repeated words, CPU/RI snapshots and
  full RAM/hidden hashes match. This is direct-component synthetic scope, not
  guest execution or general backing/lifetime coverage.

- One ordered controlled ledger now measures all 43 fixture-write/RAM-burst/fill/
  CACHE-completion/fetch records, with complete prior projection and independent
  baseline/plain/repeated CPU/timing/RAM/cache agreement. Five forged histories
  fail. Ordinary scalar fetch backing and general copy/mutation/reset/restore
  coverage remain separate; no production lifecycle identity is promoted.

- A recovered reset/restore reference fixture now passes on the primary host:
  synchronized restore reinstalls a valid cache line without a new fill, so the
  external latest-tuple matcher selects the wrong historical fill. Independent
  baseline/disabled/repeated reported PC/s0/timing/RAM/cache fields agree; explicit
  cache power forces a new fill. General restore/capture provenance remains open.

- Reviewed all 17 fetched research tips and retained their notes/original fixtures
  individually. Fourteen standalone contracts/guards, including one million PIF
  cases, pass locally. Source-derived NMI/reset, pointer aliases, PIF/SP selection
  and LL/SC disagreements remain explicitly distinct from executed evidence.
- Explicit fetch boundaries now join direct uncached identity-RAM instruction
  words to the successful scalar backing read. Data-read decoys, cached fetches,
  translated/degraded/missing/OOB RAM and EBUS supply no fabricated witness.
  Independent baseline/disabled/repeated reported fields agree; six forged
  context/read histories exercise conservative rejection. General contexts and
  production backing/lifetime identity remain open.
- CPU-copy experiments reproduce an exact uncached LW/SW backing sequence and a
  stale-source cached copy surviving a later uncached alias write. Destination
  backing changes only on D-cache writeback. Baseline/disabled/repeated reported
  fields agree. Register dataflow, general copies and executable lifetimes remain
  uncertified.
- RSP interpreter/DMA tests reproduce eight fetched IMEM words with latest-writer
  fragment history: equal-byte reloads retain different origins, count/skip selects
  actual source words, direct writes supersede history, DMEM stays separate and
  OOB DMA has unknown source. Baseline/repeated reported state and RAM/SP hashes
  agree. Transfer-completion identities, wrap/interleavings and RSP closure remain
  open.
- All 28 guest-triggered exception-vector cases repeat with mode/BEV/EXL/BD/EPC
  truth-table agreement. Independent 158-case cached/uncached and 98-case uncached
  SD/SDL/SDR matrices repeat with exact byte/fault effects. Forced endian contexts
  do not establish legal guest setup; handler provenance, general mutation sensing
  and mode coverage remain open. These fixtures change no production certificates.

- Shared opt-in scalar and fetch-boundary sensors now coexist with burst/fill/
  CACHE callbacks. Ninety-five controlled records restore the exact previous
  43-record projection when new access records are removed; baseline/disabled/
  repeated reported checkpoints agree and six forgeries fail. Independent
  scalar-fetch and CPU-copy fixtures retain complete earlier JSON through the
  shared recipe. Broader boot chronology and production identities remain open.

- The one-million-call boot prefix now retains a byte-identical 859,502,085-byte
  ordered sidecar with 5,051,089 records. All 32 fills join actual RAM bursts in
  their fetch contexts and match the full paired resident snapshot; 19 uncached
  CPU data reads stay outside fetch contexts. This prefix has no uncached RAM
  instruction fetches. Complete v5 bytes, fresh default baseline and reported
  plain/enabled/repeated checkpoints agree. Scalar DMA writes are observed backing
  effects; transfer-origin/completion, general mutations and lifetimes remain open.
  Original Rust source-linked inspection now validates both complete sources and
  supplied inputs, matches the independent Python counts/hashes and rechecks the
  877-byte report exactly. Five new tests cover ambiguous reads/unfetched lanes,
  malformed histories, all-source tampering and changes between replay passes.
  No ProgramMap identity or closure rule is promoted.
  CLI inspection/rechecking now requires both raw sources and actual inputs;
  all ROM byte orders produce identical reports. Report/input tampering and
  truncated histories fail, and report output cannot overwrite an input file.

- Buffered PI component provenance passes eight original cases and a 479-record
  ledger: 95 exact ROM byte origins, eight unknown open-bus writes and eight failed
  RAM destinations. Equal-byte reloads remain distinct; consumed lanes account
  for misalignment, odd lengths and a discarded row-boundary block. Independent
  original-source/disabled/repeated reported checkpoints agree. Guest scheduling,
  resident-cache provenance and executable lifetimes remain unclaimed.
- A 481-record composed PI/fetch fixture now joins 99 successful byte writers to
  actual fetch/fill contexts. Valid cached fetches retain the first transfer's
  writers through equal/changed backing reloads and guest SW; guest invalidation
  forces a new fill. A partial reload keeps mixed origins and untouched bytes.
  Sixteen CPU fetches, baseline/disabled/repeated reported checkpoints and seven
  malformed-history rejections pass. This supplies finite resident provenance,
  leaving general cache transitions, scheduling and executable lifetimes open.

- Actual pinned queue-container tests preserve duplicate PI event IDs,
  cancellation without callbacks, 512 invalid entries occupying capacity and one
  clock-wrap case. Source routes read/write completion through the same method;
  last-write context cannot certify transfer completion. CPU/PI scheduling and
  hardware execution remain unverified by this container/source-only experiment.
- Research boot history v1 retains 8,823,134 records at 610,000 calls, with exact
  canonical ROM origins for all 1,638,808 successful PI byte writes. Complete
  prior v0 history/v5 fetch bytes and original-PI/disabled/repeated reported
  checkpoints agree. Four copy calls return and three status transitions occur;
  final busy is 1 and transfer completion remains uncertified. Production v0
  rejects v1, keeping executable lifetimes separate.
- Original Rust PI inspection validates the complete v1 stream and paired v5
  source, preserving the exact v0 projection and canonical buffered byte effects.
  Separate report rechecking reconstructs every hash/count. Strict typed metadata,
  duplicate keys, missing footers and PI events inside fetch intervals fail closed.
  The complete retained boot corpus agrees with independent Python evidence;
  status contexts still certify no transfer completion or executable identity.

Verification: 86 Rust integration tests, formatting, strict Clippy, CLI integration,
strict C99 exporter, actual pinned Mupen hook, CPU and full-core session tests pass.
The patch also passes application checking against the clean pinned Git index.
Rust/CLI/compile-only tests use Windows, Rust 1.98, Python 3.12 and GCC 15.2.
Execution tests use x64 Linux under WSL Ubuntu with GCC and NASM; other CPU hosts
are unverified. The ares spike additionally uses G++ C++20; the two earlier spikes
and deterministic homebrew packaging/known negative outcomes also pass.
Raw-fetch CLI tests cover v0/v1/v2/v4/v5 and rejection of v3, all ROM byte orders, wide
PC/word/access/source variants, forged canonical bytes, source
tampering and missing footers. Full-corpus import/source verification/self-merge
and OPEN gating pass. A single Windows debug import under concurrent verification
took 75.7 seconds and peaked at 74,719,232 bytes of working memory; this is a cost
baseline, not an isolated throughput or scalability claim.

`discover` still requires an explicit ROM/load mapping. `import-trace` checks the
canonical ROM and verifies captured DMA-backed code bytes. `solve [rom] map` emits
whole-ROM diagnostics; supplying the ROM provides hash-checked source witnesses.
Command success means a report was produced, not that the report is CLOSED.
`import-boot-fetch <rom> <firmware> <raw> <map>` and `verify-boot-fetch` require
the actual local firmware input for the declared research v4/v5 scopes.

A declared immutable, nontrapping integer-image scope can close with explicit
exclusions. Whole-ROM mode remains OPEN and `native_complete` is always false.
There is no native output, game compatibility claim or performance claim.

Remaining gaps: broader reference sessions and device coverage, ProgramMap predecessor
state for pagespan entries, non-x64 runtime hooks, general join/loop and
immutable-table proofs, automatic boot/CIC
roots, overlay/relocation lifecycle, non-PI copies, exceptions/TLB/execution modes,
complete store/mutation and RSP policies. Header CRC fields are parsed, not verified.
Analysis scalability has not been benchmarked. See NEXT for the execution order.
