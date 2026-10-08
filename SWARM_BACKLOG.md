# SWARM BACKLOG

Statuses: `TODO`, `CLAIMED`, `BLOCKED`, `DONE`.

| ID | Status | Work item | Acceptance criterion |
|---|---|---|---|
| W001 | DONE | ROM format normalizer | Synthetic tests cover z64/v64/n64 byte order and canonical hashing input. |
| W002 | DONE | Define `ProgramMap` schema v0 | Schema represents regions, blocks, edges, indirect targets, overlays, evidence, unresolved items. |
| W003 | DONE | Mupen `new_dynarec` instrumentation design | Document exact hook points for block creation, links, invalidation, indirect target discovery. |
| W004 | DONE | Build dynamic trace format | Versioned machine-readable trace plus parser tests. |
| W005 | DONE | Direct CFG discovery | Starting from an entry PC, recursively recover direct branch/call targets with delay-slot semantics. |
| W006 | DONE | spimdisasm integration spike | Four synthetic function/table/truncation comparisons pass; PARTIAL verdict and production constraints recorded in spikes/001-spimdisasm. |
| W007 | DONE | Rabbitizer integration decision | Benchmark/assess using Rabbitizer vs project-owned decode layer; document ADR. |
| W008 | TODO | Known-symbol/signature discovery | Integrate or reproduce n64sym-style identification into evidence model. |
| W009 | TODO | Guest-address/native-symbol model | Prototype safe mapping without conflating guest pointers with host pointers. |
| W010 | TODO | Native backend spike | Emit one synthetic MIPS basic block as a relocatable host object and verify final machine state. |
| W011 | TODO | Differential verifier | Run equivalent synthetic block through reference and native paths and compare state. |
| W012 | TODO | Executable DMA/overlay tracing | Detect ROM->RAM code loads and represent relocation/load evidence. |
| W013 | DONE | Closed-world solver v0 | Report unresolved direct/indirect targets and refuse native-complete status while any remain. |
| W014 | TODO | Runtime boundary study | Map N64ModernRuntime/Mupen/ares/Gopher64 services to our planned runtime API. |
| W015 | TODO | First commercial-ROM validation protocol | Define legal local-ROM workflow and metadata-only expected-results fixtures. |

Broader corpus investigation: the pinned MIT n64-systemtest build is reproducible,
but the headless capture spike is PARTIAL (cartridge execution and CPU-oracle
limits). W010/W011 remain deferred; W012 still needs general source/write/lifecycle
coverage. See `spikes/002-systemtest-discovery/` and `docs/NEXT.md`.

Independent oracle foundation: `spikes/003-ares-oracle/` is VALIDATED for four
original cartridge/linked-memory/address-error cases and eight cross-reference
integer/control comparisons. W011 still requires a native path and broader
declared semantic coverage; this research does not complete W011 or W012.

Broader fetch sensing: `spikes/004-ares-fetch/` validates repeatable observations
of 52,424 RAM/548 SP/65 cartridge addresses on the pinned homebrew. Its synthetic
SP-entry/budget scope, startup failure and missing production adapter leave
W012 and whole-ROM closure open. No native backend work is promoted by this spike.

Raw capture import: typed 64-bit observations and full-source summary verification
now pass on the broader corpus (53,037 summaries; 4,999,998 accounted fetches).
Physical backing and execution generations remain unknown; W012 stays TODO.

Effective fetch context: the separate observer and v1 importer preserve physical/
cache variants with full-source rechecking and byte-identical v0 compatibility.
Cache/TLB/endian fixtures and both complete corpus checks pass. Actual byte-source
witnesses and lifecycle joins remain open; W012 stays TODO.

Finite ROM sources: delegated actual reads and v2 canonical-source import/recheck
now account for 1,852 fetches at 65 offsets while retaining all unknowns. Raw
provenance, source variants, legacy map hashes and OPEN gating pass. Boot/mode,
copy/cache/mutation lineage and executable lifetime remain open; W012 stays TODO.

CPU boot-input research: natural power entry with ignored firmware input now has
matching repeated CPU/device/memory checkpoints and explicit PIF-HLE/checksum
scope. The longer prefix leaves PI polling and reaches guest tests with matching
repeated checkpoints and no reported failures; full-suite completion is unverified. Complete
profile/input verification and production handling remain open; W012 stays TODO.
Research v4 now explicitly records the fixed boot profile and preserves the full
v3 projection/checkpoint baseline. Supplied-input verification remains separate;
W012 stays TODO.

Declared boot-input import: v4 now requires supplied firmware bytes, supported
profile, checked power entry and complete-source verification. No code images or
lifetimes are created; the solver stays OPEN and W012 remains TODO.
Both boot corpora now recheck complete sources/firmware and self-merge exactly,
with all legacy map hashes unchanged. Cache/copy/mutation lineage remains open.
Selected-cache research now preserves slot/tag/index/words with twelve controlled
cases and matching CPU/timing/RAM/cache checkpoints. Broad source/lifecycle joins
remain open; W012 stays TODO.
Broader cache context now preserves selected-line snapshots on the one-million
boot prefix with exact prior-stream and checkpoint agreement. Production,
fill/copy/mutation and executable lifetimes remain open; W012 stays TODO.
The ten-million cache prefix and fresh v4/v2 regressions now preserve prior
goldens too. Cache fill origins and execution lifetimes remain open.
V5 selected-cache context now has strict Rust import/full-source verification and
snapshot-variant tests, without executable identity promotion. W012 remains TODO.
Both complete v5 corpora now verify full sources/firmware and self-merge exactly,
with OPEN gating and preserved v0/v1/v2/shorter-v4 map hashes. W012 remains TODO.
Controlled completed-cache-fill sensing now distinguishes nine fills without
altering CPU/timing/RAM/cache goldens. Tag/invalidation/backing witnesses and
general executable lifetimes remain open; W012 stays TODO.
Guest CACHE retags now demonstrate differing effective and historical fill pages
with unchanged reference checkpoints. Explicit mutations/backing witnesses stay
open; W012 remains TODO.
Completed CACHE tag-store/index-invalidate sensing now preserves exact operand/
tag/data transitions and prior complete goldens. Additional outcomes, backing
and unified history remain open; W012 stays TODO.
Controlled cache hit/miss invalidation/fill/writeback outcomes now pass with a
separate baseline and actual uncached RAM result. General backing, failure/reset/
restore and unified event/lifetime joins stay open; W012 remains TODO.
Successful identity-mapped RAM burst witnesses now match four actual fills and
one completed writeback, with unchanged prior goldens and invalid attempts kept
unknown. General backing/copy/mutation/lifetime handling remains open; W012 stays TODO.
RAM remapping/degradation/failure boundary tests now retain unsupported paths as
unknown while verifying 16/32-byte identity witnesses and full hidden-memory
checks. Unified transaction/cache/fetch/copy/lifetime history remains open; W012 stays TODO.
Controlled shared chronology now measures 43 transaction/cache/fetch/fixture-write
records with independent checkpoints and forged-history rejection. General
contexts, scalar backing, copy/mutation/reset/restore and lifetimes remain open.
Recovered synchronized-restore/cache-power execution now demonstrates restored
residency without a fill, with baseline/disabled/repeated reported fields equal.
General checkpoint/capture and byte lifetimes still leave W012 TODO.
Seventeen research tips are reconciled individually. Scalar-fetch/copy, RSP IMEM,
exception-vector and two 64-bit store matrices now reproduce on the primary host;
fourteen source/model contracts also pass. Combine explicit access boundaries
with the shared ledger next. General mutation/lifetime coverage leaves W012 TODO.
Shared access boundaries now pass the 95-record controlled history and original
primitive fixtures. The bounded boot sidecar preserves v5/checkpoints across
5,051,089 records and 32 RAM-backed fills. Strict Rust inspection/rechecking now
passes complete sources. Buffered PI component cases join actual ROM halves and
consumed lanes to 95 successful byte origins; open-bus and failed destinations
remain unknown. A composed 481-record fixture now preserves writer/fetch/fill
origins through reloads, CPU patches, invalidation and partial words. Versioned
boot transfer capture now passes 8,823,134 records and 1,638,808 exact PI byte
origins with complete prior projections/checkpoints. Strict original Rust v1
inspection/rechecking now preserves every complete source/count/hash. Real queue
insertion/removal identities now pass the actual container with unchanged
reported checkpoints. Compose real PI request and CPU dispatch/status next; general
mutation/lifetime obligations leave W012 TODO.

2026-10-09: four additional PI research contracts now reproduce locally, including
the exact actual-reference write fixture. Accepted request/actual CPU dispatch
scopes also pass both PI directions; rejected insertions retain independent byte
effects. Save preserves external queue identity; load remains unknown. Canonical
integration is now `main` by user instruction. Broader boot joins and lifetime
obligations keep W012 TODO.

SP DMA lifecycle, nine-mode PIF backing (synthetic and supplied firmware), and
192 repeated COP1 store cases now reproduce locally. Keep pending/full policy,
physical/source identity and cache/backing mutation obligations explicit; broader
lifetime and mutation completeness still keep W012 TODO.

2026-10-09 primary: retained/reproduced `ebus-hidden-fetch-gpt56sol` (`fe15ab6`), header/model evidence only; actual hidden-read capture remains open.

2026-10-09 primary: TLB mapped uncached fetch fixture locally reproduced; complete mapping history/closure remains open.

2026-10-09 primary: translated/degraded scalar Word fixture locally reproduced; full fetch/other widths and executable-identity policy stay open.

2026-10-09 primary: actual dirty eviction/clean-lane overwrite counterexample reproduced; general resident-byte lineage remains open.
