# Status

2026-10-09. Milestone scope: M1–M3 synthetic executable discovery foundation.

Implemented:

- Decoded RSP DMEM writers now compose through actual CPU LW register definitions
  into normalized IMEM SW installations in a source-bound Rust consumer. It
  retains mixed/unknown byte parents and same-value generations, checks independent
  CPU steps/final snapshots, and reproduces three retained single-clock chains.
  Incoming RSP operand ancestry, IMEM execution and whole-ROM lifetime stay OPEN.

- SP captured-writer/executable-read composition reuses complete v3 boot sources
  and exact in-context CPU backing reads. Byte candidates preserve actual Word/
  DMA sink occurrences, equal-value supersession and permanent contradiction
  cuts. The retained 10,000-call source joins all 7,945 SP reads while preserving
  its old report; incomplete mutation sensing keeps ultimate ancestry uncertified.

- Cached general-root replay v1 composes full 32-byte I-cache fills, direct slot
  replacement and per-word captured backing writers with canonical pinned
  NMI/reset/power effects. Equal-value conflicting fills end residency; NMI
  preserves both domains, reset clears residency, power clears both. V0 stays
  compatible; finite receipts certify neither census nor executable lifetime.

- Source-preserving discovery solve admission composes externally expected trace
  sets with canonical raw-primitive, installed-entry and compiled-root rechecks before
  solving. Reports retain expected sessions and the exact validated map digest.
  Captured instruction snapshots constrain supplied solver bytes even for opaque
  labels. The CLI creates expectations once and rejects source/map deletions;
  whole-ROM coverage, other source domains and native readiness remain OPEN.

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
- An opt-in external queue identity sensor now passes six actual-container cases
  and 2,104 records, including equal event/deadline pairs, cancellation and full
  capacity. Reported dispatches, occupied serialized state and object size match
  original/disabled/repeated builds; save preserves identity and load discards it. Actual
  CPU/device dispatch and transfer-completion joins remain separate work.
- Explicit accepted PI I/O and actual CPU dispatch scopes now pass a 2,222-record
  component fixture with both request directions. Exact insertion/removal tokens
  identify two request/status links; canceled, rejected, unbound and direct calls
  fail closed. All 32 successful byte effects remain separate from scheduling.
  Original/disabled/repeated reported state agrees; no boot completion or image
  promotion follows from these finite component results.
- Recovered actual SP DMA lifecycle tests reproduce the worker's exact stdout/
  result hashes. Ares pending descriptors mutate while FULL, handoff can keep
  BUSY asserted, count/skip rows share one current request and IMEM spans wrap.
  Mupen/Gopher source disagrees on FULL policy; hardware semantics remain open.
- Actual PIF backing sensing passes nine fetch-stage adversaries with original
  synthetic and known local NTSC firmware. Baseline/instrumented/repeated reported
  checkpoints agree; mirrored fetch addresses retain distinct identity while
  sharing the actual masked source offset. Latch/RAM/lockout/cache/stale decoys
  supply no firmware witness. Full boot/lifetime and production promotion remain open.
- COP1 store research reproduces its 100,000-case payload model and 192 repeated
  actual SWC1/SDC1 cases. FR mode changes source lanes/pairs; cached stores retain
  resident changes and uncached stores mutate backing. CU1/alignment/TLB failures
  retain raw nonmutation. Reference write decomposition differs; callback counts
  supply no hardware atomicity proof. General mutation/lifetime coverage remains open.

Verification: 94 Rust integration tests and three unit tests, formatting, strict Clippy, CLI integration,
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

EBus HiddenRAM research now reproduces an exhaustive 65,536-pair header probe and seven reducer negatives. Its Word is derived from four hidden bits rather than copied RAM bytes; actual full fetch/epoch evidence remains PARTIAL (ADR-0062).

Reproduced TLBWI/alias/remap/ASID/global/reverse-endian fetch cases now retain actual per-fetch identity-RDRAM origins. Cached and failed translations fail closed; mapping lifetime and other page/mode cases remain open (ADR-0063).

Translated/degraded scalar Word reads reproduce exact backing/result receipts and stochastic sequence. Request address, translated raw origin and CCI-delivered value stay separate; full fetch and other-path evidence remains open (ADR-0064).

Actual D-cache eviction now reproduces the full outgoing 16-byte write, including a clean lane changed externally in backing, before slot reuse. Dirty masks/current RAM cannot reconstruct those origins (ADR-0065).

CPU SB/SH to SP IMEM now reproduces 32 actual cases: 24 widened full-word sinks and eight nonmutating faults. Sink width/payload follows device semantics, with a preserved Mupen source disagreement (ADR-0066).

The prepared `cpu_sp_subword` verifier is now consumed by production: completed
SB/SH SP Word effects must match the exact decoded context, GPR source, endian
lane, physical bank/offset and full payload. Missing effects mint no writer.
Primary reconciliation additionally rejects nonzero GPR0 and misaligned PCs,
and compares the saved actual SB +1 capture without a new reference build.
This is single-effect normalization with caller-owned authentication, mapping,
writer census and lifetime obligations; whole-ROM/native completeness stays OPEN.

The recovered actual PI read lifecycle fixture now matches both worker hashes across six phases, including full-queue copy without scheduling and save-preserved/load-cut identity. ADR-0057/0058 remain the governing finite contracts.

D-cache lineage research progressed from worker PARTIAL to a locally executed four-phase fixture. Two full-line writebacks certify bounded resident origins; dirty invalidate/drop does not. Six measured-history forgeries now fail, including a same-value intervening mutation (ADR-0067).

Independent SB/SH identity-RDRAM model and 96 actual cases now reproduce exact worker hashes. Successful subword backing/cache effects retain endian lanes, while faulting attempts mutate neither; these effects differ from SP IMEM widening.

The second SB/SH fixture now independently reproduces 100 actual cases and both executable-word construction families. Its runner has a distinct output root; source/result hashes match the worker.

Recovered RSP self-store code now passes 28 decoded probes: ordinary scalar/vector stores remain in DMEM and preserve IMEM, including the aligned SRV no-op. CPU/SP DMA/external IMEM mutation obligations remain open (ADR-0068).

Original bounded boot history v2 now records accepted PI requests, actual queue identities and CPU dispatch/status scopes. The 8,823,189-record prefix preserves exact complete v1/v0/v5 sources and all 1,638,808 ROM byte origins; three status links are identified and request 4 remains without status. Twelve synthetic/four actual forgeries fail. Rust v1 rechecking keeps its exact prior report hash and rejects v2. Original strict Rust v2 inspection/report rechecking now consumes the complete raw source and reproduces every scheduling count/link plus the entire unchanged nested v1 report. Six adversarial integration tests keep unknown/unbound/read/direct/canceled/rejected/save/load boundaries explicit. No guest/native completion or executable lifetime is promoted (ADR-0069/0070).

Explicit `inspect-pi-queue-boot-history`/`verify-pi-queue-boot-history` CLI commands now expose the strict finite v2 report. Canonical ROM byte orders, actual request links, source/report tampering, old-version rejection, truncated/forged captures and protection of every input pass original synthetic CLI tests. Native/guest completion remains false.

Original Rust observed PI-to-fetch lineage now joins successful raw v2 writers
through exact read/fill contexts while keeping backing and resident histories
separate. Full-prefix inspection/source rechecking agrees with independent Python:
10,954 fully attributed fetch observations in 185 samples, preserving every nested
prior report. Equal/changed reloads, ordinary/burst writes, mixed words, tag changes,
invalidation, unsupported fills, ambiguous reads and between-pass source changes
have adversarial tests. Mutation coverage/lifetime/native flags remain false.
The 599,046 remaining fetches are uncached CPU SP (596,991) and PIF (2055) paths;
actual SP backing-read capture is next, with ultimate producer history separate.

The separate `inspect-pi-fetch-lineage`/`verify-pi-fetch-lineage` commands now expose the observed-chain report. Synthetic CLI tests pass all ROM byte orders, raw writer attribution, source/report tampering, version/truncation rejection and protection of every supplied input.

Actual CPU SP backing sensing now passes an independent unchanged-reference,
disabled and repeated-enabled fixture: 18 CPU steps, 77 records, twelve exact
fetch/read joins, four normalized CPU stores and three DMA stores. Physical
mirrors and banks remain explicit; unrelated data reads, status IO and cached-SP
freeze cannot supply fetch backing. Seven measured-history forgeries fail.
Boot composition is in progress; producer census and lifetime remain open
(ADR-0072).

Latest worker research is reconciled: the decoded RSP self-store fixture now
passes 29 probes, including the added 15-byte SRV at `0x100f`. Repeated output
and final DMEM hash match the worker closeout; IMEM remains unchanged throughout.
The original 28-case result is preserved in its prior ignored directory.

Original optional boot access-history v3 now composes actual SP Word results and
normalized DMA stores with the existing PI/queue chronology. The 10,000-call
capture has 7945 exact SP-backed fetches and preserves complete prior v2/v1/v0/v5
sources and unchanged-reference/disabled/repeated checkpoints. Eleven standalone
forgeries pass rejection tests. Full-prefix rechecking and strict Rust consumption
are in progress; no bank identity becomes ultimate origin or executable lifetime.

The original strict Rust v3 consumer now passes full 610,000-call inspection and
complete report source rechecking: 596,991 SP fetches, 920 samples and 512 DMA
store receipts. Its nested source report remains complete; every observation
retains raw v3 ordinals. Full Python nested replay is pending, while all smaller
capture observations/digests already agree independently. Three adversarial
integration tests bring the suite to 97 integrations plus three units; formatting,
strict Clippy and 22 retained research contracts pass. No production image,
lifetime or closed-world status is promoted.

Separate `inspect-sp-boot-history`/`verify-sp-boot-history` CLI commands now expose
the strict finite v3 report. Synthetic tests pass canonical ROM byte orders,
exact backing/sink witnesses, complete source/report tampering, uncertified flags,
version/truncation rejection and protection of all four inputs. Previous PI CLI
tests and strict Clippy still pass.

Full v3 SP composition is now independently validated: Python and Rust agree on
every 596,991 fetch witness, 920 samples, raw/ordered digest and the entire exact
prior v2 report. All prior v2/v1/v0/v5 bytes/checkpoints are unchanged. All 512
observed DMA stores correctly retain unknown receipts because their source
addresses exceed the declared RAM backing. Actual PIF reads and SP producer
history remain the next source gaps; native closure/lifetime stay OPEN.

Optional boot chronology v4 now adds actual PIF ROM reads and distinct delegated
write attempts. The initial writable-ROM assumption was falsified: Memory::Readable
writes are no-ops. Thirteen actual component cases preserve full independent
reference/disabled/repeated state and unchanged ROM backing. The smaller capture
identifies 2055 PIF fetches and preserves every prior source/checkpoint. Full
validation and strict Rust integration are continuing (ADR-0075).

Strict Rust v4 PIF inspection and complete source rechecking now pass on all
9,537,688 full-prefix rows. Independent Python agrees with every sample/count/
digest and the exact entire nested v3 report. The 2055 PIF-backed fetches all
match supplied firmware; no write attempts occur in this prefix. Together with
previous finite SP/RAM witnesses this closes the observed backing-domain gap,
while producer completeness, mutations and executable lifetimes remain OPEN.
All 100 integration tests plus three units and strict Clippy pass (ADR-0076).

Separate `inspect-pif-boot-history`/`verify-pif-boot-history` commands expose finite
v4 inspection. Synthetic tests pass canonical byte orders, read/attempt semantics,
full report/source binding, old-version rejection and all-input protection. All
older SP/PI CLI tests still pass; 23 retained research contracts/guards pass.

A full-source-bound SP writer-site inventory now finds 54,253 CPU effects at 69
sites: 51,991 SW, 2256 SB and six COP1 SWC1 effects. These are normalized actual
SP Word sinks; opcode width and source dataflow remain separate. Integer-SW-only
producer census would miss observed subword/FPR writers. RSP DMEM sink testing
is continuing; no mutation/lifetime certificate follows from this inventory.

Fresh captures using the final PIF sensor recipe now reproduce both 10,000- and
610,000-call sources, reports and independent checkpoints exactly. The full
source has actual backing witnesses for all 610,000 observed fetches across PIF,
SP and PI-backed RAM domains. Ultimate SP producers, executable mutation/lifetimes,
boot/exception coverage and whole-ROM native closure remain unproved.

Actual RSP DMEM mutation sensing now passes 30 decoded probes, 60 instruction
contexts and 209 primitive writes in 329 records. All full reported independent
reference/disabled/repeated checkpoints agree; byte replay and ten measured
forgeries pass. Same-value stores remain distinct, foreign sinks are excluded,
and all prior 29 self-store results remain exact. The controlled CPU refetch
composition now passes 31 records, eight RSP byte writes, one CPU Word write,
four backing-read samples and ten forged histories. Every reported independent
reference/disabled/enabled/repeated checkpoint agrees. The reconciled extended
fixture adds scalar/vector partial stores, neighboring writes and foreign-sink
boundaries: 78 records, fifteen RSP byte effects, two CPU Word effects, three
foreign effects and ten backing reads. Nineteen independent checkpoints agree;
seventeen forgeries fail, while three fool payload-only replay. Unknown sinks
cut only touched byte lineage. Complete mutation/lifetime/native coverage
stays uncertified (ADR-0077).

Controlled adjacent interpreted CPU-copy evidence now passes strict instruction/
GPR continuity and uncached-address checks. Exact pinned ares original/disabled/
enabled/repeated runs agree at fourteen reported instruction checkpoints. Two
LW/LWU-to-SW certificates survive, twelve forged histories fail and seven
synthetic contract tests pass. Equal-value decoys, ORI clobbers and NOP gaps do
not certify. This remains a research contract; production copy/lifetime/native
certificates are not installed (ADR-0088).

The bounded adjacent LW/LWU-XORI-SW contract now also passes twenty independent
reported instruction checkpoints, four intended transform certificates, thirteen
measured forgeries and six synthetic regressions. Wrong-source equal-bit XORI
does not certify; XORI zero retains a distinct observed transform context. Copy
mode is unchanged and excludes transforms. General transformation, executable
consumption/lifetime and production/native certificates remain OPEN (ADR-0089).

Controlled CPU-to-SP producer context now comes from actual decoder boundaries,
with GPR/FPR and FR/CU1 snapshots, physical bank/offset checks and guest-byte
replay. Eight independent reported checkpoints agree; six attributed writes,
one unscoped write and one denied-CU1/no-sink case survive in 21 records.
Sixteen measured forgeries and eight synthetic regressions pass. An IMEM host-
order snapshot error was caught and corrected through guest accessors. Ultimate
ancestry, census, hardware semantics, lifetime and native gates remain OPEN
(ADR-0090).

2026-10-11 integration harvest: finite-static closure now rejects contradictory
guest/physical executable ownership, overlapping instruction values, stale
content-derived image IDs and incompatible known Region/CodeImage provenance.
The primary reproduced seven false-CLOSED families on `211176e`, then retained
all nine consolidated regressions. Unknown metadata and generation labels do
not invent provenance or chronology. Whole-ROM closure remains OPEN (ADR-0078).

Trace primitive identities now reject incompatible roles or semantic forks,
including DMA copy vs source-unit collisions and merge laundering. A separate
complete-DiscoveryTrace rechecker authenticates raw DMA/store/indirect/verification
projections and optional exact installed entries. Explicit compilation-unit
context may be shared in provenance, with source metadata independently checked.
All 25 focused regressions pass. This authenticates supplied finite evidence,
not sensor completeness or executable lifetime (ADR-0079).

The solver now independently checks retained raw stores/transfers, restricted
entry masks, post-invalidation verification epochs and otherwise-empty fetch
captures. Removing derived diagnostics cannot erase these obligations. Store
scope exclusion composes with explicit physical mutation checks; source-unit
context alone cannot certify an indirect event. Six research candidates were
reconciled with adversarial controls (ADR-0080).

Typed target lookup/runtime-link facts now survive import, merge and JSON
roundtrip independently of diagnostics. The solver blocks uncorrelated dispatch
even at an already certified target PC. The shared role table/source rechecker
also authenticates dispatch kinds and generations; empty legacy maps preserve
their serialized shape (ADR-0081).

Executable Regions now reject unaligned or overflowing explicit physical spans.
Every load, including loads without a copy event, must match its declared
image/generation, guest range and ROM source Region. Overlay descriptors must
match their referenced Region's image, range and ROM source; a descriptor does
not invent generation or physical backing. Ten adversaries reproduced on prior
main; all 19 focused controls and the full locked core suite pass (ADR-0082).

Fetch summaries now require a jointly realizable finite sequence, rejecting
endpoint/quota collisions and sequence holes despite plausible aggregate counts
or equal payloads. Four adversaries reproduced on prior main. Seven focused
tests, including a bounded exhaustive concrete-history oracle against the Rust
validator, pass; the independent 20,000-case model reproduces its exact research
hash. Source authenticity and capture completeness remain separate (ADR-0083).

Pointer-table recognition now rejects alternate reachability that bypasses its
compare or dispatch prefix, and exceptional executed guard slots. Annulled slots
and unrelated image/generation facts remain valid controls. Eight adversarial
tests reproduced on prior main; 17 focused tests pass, including a primary remote
taken-branch control. Numeric candidates retain distinct content-immutability
and target-identity obligations; full core, fmt and strict Clippy pass (ADR-0084).

Discovery import now revokes an older covering DMA after a later overlapping
observed CPU store or partial DMA, including equal-value writes before first
compilation. Matching supplied bytes cannot restore that copy identity. Exact
writer evidence remains unresolved; a later full copy is a valid control. Five
adversaries reproduced on prior main, and nine focused cases pass. Complete-source
entry rechecking and the exact pinned Mupen hook/import fixture pass (ADR-0085).

Block/direct-edge merge contradictions now use exact identity indexes while
retaining every semantic variant and evidence reference. Four research cases
and a primary 256-subset pairwise-oracle comparison pass. Local release medians
at 8,000 facts improve from 224.453 to 11.273 ms for blocks and 154.773 to
14.700 ms for edges. This measures the synthetic merge phase only (ADR-0086).

Bounded indirect analysis now rechecks exactly two acyclic scalar paths that
independently derive the same JR/JALR target, retaining both path identities.
Five completeness regressions reproduced on prior main; all 14 join cases,
existing chain/slot tests and full locked workspace checks pass. Unsupported
effects and the final transfer slot remain independent closure blockers.
Whole-ROM/native completeness and general dataflow remain OPEN (ADR-0087).

Canonical Rust CI now runs exact decoder-pin checks, formatting, strict workspace
Clippy, the full workspace suite, synthetic CLI checks and the independent
fetch-summary oracle on code pushes/PRs. The first main run passed at `d74b2a0`
(Actions 38129473623). The added seven synthetic CPU-copy contract regressions
also pass in canonical CI at `72e557a` (Actions 38131501041). These are finite
history checks; pinned emulator neutrality remains a separate reference gate.
The six XORI contract regressions also pass at `05ed9cd` (Actions 38132454063).
Research-only emulator workflows are not promoted.

Canonical Actions run `38134178095` passes at exact head
`a990cfaa4ab4357579e43c01dac71a7a360eb88e`, including eight synthetic CPU SP
producer contracts and the existing Rust/CLI/copy/transform/model gates. The
separate pinned ares run supplies unchanged-reference neutrality evidence.

Controlled RSP DMEM -> actual CPU LW/GPR/SW -> IMEM composition now preserves
four source-byte generations separately from the sink. Sixteen unchanged-
reference checkpoints agree; 58 records yield three intended copy chains with
mixed/unknown bytes, decoy/clobber and unscoped controls retained. Twenty measured
forgeries and eight synthetic contracts pass, as do full core, fmt and strict
workspace Clippy. Ultimate input ancestry, census, executable consumption/
lifetime and native closure remain OPEN (ADR-0091).

Canonical Actions `38139630729` passes at exact head
`71ccb10b94a8c617250e4ec38984d4f686de4f96`, including the eight composition
contracts and all existing Rust/CLI/copy/transform/producer/model gates.

Canonical Actions `38140046718` passes at exact head
`4fed4b16898deede3bd766c78e3c81e2bd03962f`, including the added BREAK-context
negative control and all existing gates.

Canonical Actions `38140216494` passes at exact head
`0f00cdc2cde81811442a9d169a27504b0c1e769a`, including all ten composition
contracts and the existing Rust/CLI/producer/model gates.

Unmodified pinned ares now reproduces four XORI/cache visibility controls under
spike 048, with repeated identical selected facts and the historical evidence
hash. Writeback does not refresh resident instructions; early refill remains
stale. Four strict behavioral tests and an additional actual-XORI decoded-word
negative pass, along with full core, fmt and strict workspace Clippy. Abstract
generation replay is reviewed separately; measured ancestry, mutation census,
executable lifetime and native completeness remain OPEN (ADR-0092).

Canonical Actions `38141298481` passes at exact head
`b1d9d52a31ec48e5971237424181e2c3e59a8980`, including the four cache visibility
contracts, seventh actual-XORI negative and existing Rust/CLI/producer/model gates.

Unmodified pinned ares now reproduces the large-PageMask/cache-remap composition
in spike 049: selected 16-KiB/64-KiB tags, equal-payload remap misses, stale hits,
and resident preservation across same-value TLBWI/direct ASID staging agree with
historical evidence. Six strict contracts and full core/fmt/strict Clippy pass.
The branch model accepts a fabricated miss fill and is not adopted as a verifier.
Guest writer chronology, mapping/fill ancestry, census, hardware indexing and
executable lifetime/native closure remain OPEN (ADR-0093).

Canonical Actions `38141694889` passes at exact head
`809637ff7dda6cd706e6958545a1ca7e28fd348d`, including all six PageMask/cache
contracts and prior Rust/CLI/producer/model gates.

Controlled PI/cache visibility now has a strict finite reference fixture in
spike 050. Two 32-byte copies yield 117 fully checked records; completion leaves
old cached code executable, while a queue-less copy executes after invalidate/
refill. Eight selected checkpoints/final reported state agree across unmodified,
disabled and enabled builds; repeated enabled trace matches its historical hash.
Ten measured forgeries and eleven synthetic tests pass, along with full core,
fmt and strict Clippy. Queue labels are not authenticated tokens; producer/census/
lifetime/native certificates remain false (ADR-0094).

Canonical Actions `38142346588` passes at exact head
`4c05752a2f2a30dcb64c349ef38fe19b1224f3a9`, including eleven PI/cache
contracts and all prior Rust/CLI/producer/model gates.

Canonical Actions `38142551330` passes at exact head
`bff5bd874a16290f527940fb9f63640eb10e2706`, including the eleventh RSP/CPU
composition context-reuse negative and all prior gates.

Canonical Actions `38143662265` passes at exact head
`a4d7b99bbfb52d1195e2e08ed34e08fc6b22dd2e`, including retained relocation
deletion resistance and prior gates. Decompression/compact-ancestry/relocation
models were independently reproduced and reviewed without production promotion.

Forward SP-DMA DMEM ingress now has a strict finite reference fixture in spike
051: 27 complete records preserve paired Word source/sink lanes, same-value
reloads, count/skip, wrap, OOB unknown sources and a direct Word overwrite.
Unmodified/disabled/enabled reported state agrees and enabled traces repeat;
twelve measured forgeries and six synthetic tests reject the old runner's
unchecked payload/type/schema cases. Full core/fmt/strict Clippy pass. Ultimate
RDRAM ancestry, request lifecycle, census and executable/native closure remain
OPEN (ADR-0095).

Canonical Actions `38144459838` passes at exact head
`cc3cc925faf0871161e9cfe6a19e5bfbef33326d`, including the six strict DMEM
ingress contracts and all prior gates.

Unmodified pinned ares now reproduces 29 decoded RSP store-isolation probes in
spike 052, checking all IMEM bytes before/after every probe. Historical report,
all three source audits and repeated output agree. Four synthetic contracts and
122 measured report forgeries pass under strict typed expectations, along with
full core/fmt/strict Clippy. DMEM-only interpreter stores do not discharge CPU,
DMA, reset/restore/debugger, recompiler/hardware or complete lifetime/native
obligations (ADR-0096).

Spike 053 now retains actual guest MTC0 EntryHi stale-cache reactivation at the
unmodified pin. Historical measured facts and repeated output agree; all 36
report mutations reject under exact typed facts, tags, counters and cache digest.
Four synthetic contracts, full core/fmt/strict Clippy pass. Context inactivity
does not retire resident bytes; staged TLB/backing/reset operations do not close
writer census, generation ancestry, hardware policy or native gates (ADR-0097).

Canonical Actions 38146002739 passes at exact EntryHi integration head
`c1d4e72524f287984f62f161818eeaad5f8f554b`.

Spike 054 retains decoded TLBR stale reactivation with TLBP, same-value and
out-of-range controls. Fresh/repeated/historical facts agree, 38 measured report
mutations reject, and four synthetic contracts plus core/fmt/strict Clippy pass.
Successful context loads differ from instruction occurrence; complete writer,
mapping/resident ancestry and lifetime/native obligations remain OPEN (ADR-0098).

Canonical TLBR Actions 38146610641 passes at exact
`3a4ddabbdcd4cee2488936e0d1d9f211c263bc80`.

Validated CPU-copy/XORI findings now have an original reusable Rust consumer and
inspect/verify CLI, rather than only Python fixture checking. It retains exact
instruction/register continuity, source-read/sink-write ordinals and explicit
XORI-zero identity, with complete-source receipt/report rechecking. Saved actual
captures reproduce the independent two copy and four transform witnesses without
new reference builds. General producer ancestry, census, executable lifetime and
whole-ROM/native closure remain OPEN (ADR-0099).

Canonical CPU-copy CLI Actions 38147498790 passes at exact
`3c0fbe7d3dc5d6b68538c8e168b966dfbe120131`. Rust witnesses now retain each
big-endian source/destination/XOR byte expression, matching all four measured
XORI cases. A sixth focused regression rechecks every lane and preserves
XORI-zero context despite copy-equivalent byte mappings.

Canonical byte-expression Actions 38147761501 passes at exact
`7009c308b2d1bf4370b2a8097e8df4a3dbd7e0e8`.

Separate Rust captured-definition inspection now follows source reads through
unrelated-register loads/NOP and one in-place XORI. Retained actual capture
supplies four copies versus two in the unchanged adjacent protocol; decoy source
read 17 does not replace the t0 definition from read 14. Same-value reloads,
equal-result ORI cuts, failed-load cuts and cross-protocol gates pass ten focused
Rust tests plus CLI/fmt/strict Clippy. General producer/capture completeness,
storage ancestry and executable lifetime/native closure remain OPEN (ADR-0100).


- Production now exposes a bounded `exception_roots` primitive for R4300
  general/TLB executable-root candidates. It keeps general, TLB-invalid and true
  TLB-miss classification explicit, selects BEV base independently, and preserves
  the 32-bit refill / 64-bit XTLB / nested-general distinction. Four Rust
  regressions replay the validated 28-case root matrix, and the exact pinned ares
  matrix was reproduced with its recorded result hash. This is not a root census,
  reachability proof, handler-byte provenance/lifetime certificate, or waiver for
  interrupt/NMI/reset/cache-error roots. The pinned Gopher64 XTLB disagreement
  remains explicit.

- Production now exposes bounded source-bound `tlb_history` replay for decoded
  TLBWI operation generations. A successful selected-slot write mints a fresh
  ordered generation even when before/after entry content is identical; equal
  payload in another slot cannot identify that write. Out-of-range and exception
  attempts mint no successful generation. Complete-source SHA binding, exact
  report reconstruction and seven adversarial Rust regression groups preserve
  fail-closed behavior. A fresh exact-pinned ares rerun reproduces result SHA-256
  `6ef416a44a0fb533a1e291b8adab42b158f0eb581ec81a9174509b3d6ab606e0`.
  Sensor completeness, mapping semantics, TLBWR/context chronology, cache
  residency, executable lifetime and whole-ROM/native completeness remain OPEN
  (ADR-0102).


- Production now exposes bounded source-bound `exception_pif` composition for the
  validated BEV=1 32-bit general exception root (ADR-0103). It replays the complete
  strict PIF v4 source and certifies only a caller-selected singleton fetch at
  `ffffffffbfc00380` / physical `1fc00380` / PIF offset `0x380` that actually
  matches the supplied firmware. The receipt retains fetch identity, backing-read
  ordinal and source/firmware digests; full source rechecking reconstructs it.
  Current-production regressions preserve the SI-latch/equal-value ambiguity and
  coalesced-repeat failure boundary. Address/value/mirror equality cannot supply
  origin. Exception causality/classification chronology, BEV=1 refill/XTLB source
  behavior, handler cache/mapping lifetime, remaining root classes, whole-ROM
  closure and native completeness remain OPEN.

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


- Production now has a bounded, source-hash-bound PI interrupt-producer replay. Explicit completion observations mint completion generations; raw MI.PI ancestry, MI-mask/poll generations and derived CPU RCP-pending state remain separate. Same-value mask writes still repoll, interrupt clear cuts the prior raw producer, restore boundaries return raw/mask ancestry to UNKNOWN, and PI copy payloads/current snapshots are rejected as completion evidence. Sensor coverage, hardware timing, CPU interrupt gate/root transfer, other producers, handler provenance/lifetime, whole-ROM closure and native completeness remain OPEN (ADR-0105).

- Production `interrupt_roots` now evaluates maskable eligibility at one supplied
  architectural boundary and rechecks its complete numeric-root receipt. All 32
  saved actual-reference cases agree: 18 admitted, 14 suppressed. Six Rust
  regressions retain gating, exact enabled bits, BEV selection and reject edited
  receipts/suppressed boundaries/type aliases. Producer and Status/BEV chronology,
  actual root transfer, handler byte lifetime and whole-ROM/native closure remain
  OPEN (ADR-0106).

- Production `tlb_geometry` now derives validated 4-/16-/64-KiB half selection
  and in-page offsets for an independently selected mapping, with complete
  receipt rechecking against external mask/address. Six retained regressions
  preserve the bit12 decoy counterexample; three added groups reject field edits,
  equal-offset substitutions, malformed/unvalidated masks and extra claims.
  Saved actual-source fetches and canonical cache geometry agree without new
  reference builds. Mapping selection/generation/authentication, cache/backing
  ancestry and executable lifetime/native closure remain OPEN (ADR-0107).

- Production software_interrupt now replays externally hash-bound guest MTC0
  Cause operations. Successful same-value writes retain fresh generations;
  IP0/IP1 replacement preserves independently produced IP2..IP7. Eleven retained
  tests and three added adversarial groups reject missing/forged effects, source
  deletion, report edits, schema aliases and nonzero register-zero operands.
  All 21 saved state rows agree with the producer relation and next boundary gate.
  Synthetic protocol adapters do not certify sensed chronology, producer census,
  handler ancestry/lifetime or whole-ROM/native closure (ADR-0108).

- Production tlb_fetch now joins one mapped CCA=2 fetch to its exact completed
  in-window ordinary-RDRAM Word read, retaining separate virtual, mapping/context,
  translated and bus identities. It reuses strict tlb_geometry, rejects impossible
  low PFN bits, and retains alias/remap/endian/invalid-half/equal-value-decoy
  adversaries. Thirteen saved actual fetches agree with locally adapted fixtures;
  mapping labels/projection ordinals remain synthetic. Source-sensor coverage,
  mapping/context generations, cache residency, lifetime and closure/native
  completeness remain OPEN (ADR-0063).

- Production tlbwr_history now preserves observed selection and exact matching
  write separately from CP0 Index and mapping fingerprints. Successful unchanged
  writes remain fresh operations. Eight regressions and authenticated saved
  facts cover missing/forged selections, same-content generations and Wired
  bounds. Mapping semantics, Random distribution, context/cache lifetime, sensor
  census and whole-ROM/native completeness remain OPEN (ADR-0109).

- Production dcache_writeback now preserves resident fill/mutation revisions and
  all byte origins through an exact successful backing writeback. Nine focused
  tests and the authenticated four-phase saved capture agree: explicit writeback
  and dirty eviction export two receipts; clean replacement and dirty drop
  export none. A consistent forged slot/physical line rejects in the direct
  identity scope. Cacheability/alias/context, operand ancestry, complete census,
  executable lifetime and whole-ROM/native completeness remain OPEN (ADR-0067).

- Production cpu_copy now exposes separate captured-writer chronology reports for
  adjacent and live-definition copies. Six lineage tests preserve forward/
  backward overlap, equal-value differences, same-value non-copy writers and
  phase cuts. Contradictory reads cut stale writer candidates even when later
  bits match again. Existing ten copy/definition regressions pass. Ultimate
  source ancestry, full mutation census and executable/native closure remain
  OPEN (ADR-0110).

- Production cpu_sp_conditional now normalizes completed Word SC sinks bound to
  the captured pre-instruction context, direct KSEG1 mapping and SP bank/offset.
  Same-value sinks remain writer occurrences; absent sinks create no witness.
  Nine retained tests plus two architectural/order adversaries and all eight
  authenticated saved reference cases pass. Reservation prediction/lifetime,
  observer completeness, operand ancestry, downstream IMEM execution and
  whole-ROM/native closure remain OPEN (ADR-0111).

- Production timer_interrupt now replays observed Count/Compare writes and
  explicit timer-pending transitions. Same-value Compare writes remain fresh
  acknowledgements; Count writes preserve pending. Eight retained regressions
  and an unsupported elapsed-Count adversary retain fail-closed scope. Saved
  exact-reference facts cover timer producer/acknowledgement and boundary gates;
  scheduling disagreement, primitive authentication/census, timer/root chronology,
  handler lifetime and native completeness remain OPEN (ADR-0112).

- Production evidence_manifest now preserves external expectations for complete
  canonical discovery-trace sources and rechecks their existing typed ProgramMap
  primitive projections. Nine regressions cover session/fact deletion, equal-
  count substitutions, deterministic merge, conflicts, repeated JSON session
  keys and unexpected map sessions. This explicit API needs independently
  preserved expectations; it is not automatic solver admission or a sensor/
  whole-ROM/native completeness certificate (ADR-0113).
