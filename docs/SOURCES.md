# Upstream / Reference Source Map

All commits below are pinned in `refs.lock.toml`. `scripts/fetch_refs.*` clones them into `.refs/`, which is gitignored.

These projects are **references by default**, not automatically vendored dependencies. Check each license before copying or linking code.

## N64Recomp/N64Recomp

Purpose:

- static N64 recompilation model;
- MIPS instruction lowering;
- direct-call/tail-call translation;
- jump-table/relocation handling;
- `LiveRecomp` host-code generation architecture.

Why it matters: this is the closest existing proof that N64 binaries can become standalone native code.

## mupen64plus/mupen64plus-core

Purpose:

- study `new_dynarec` runtime block discovery;
- understand how unknown guest PCs become translated blocks;
- observe mature handling of dynamic control flow and invalidation.

Planned use: instrumented discovery/reference fork or patch series. Not the final runtime.

## ares-emulator/ares

Purpose:

- accuracy-oriented N64 behavioral oracle;
- CPU/RSP/hardware semantics;
- differential testing/reference implementation.

Pinned core license: ISC with BSD SLJIT and additional upstream notices.
`spikes/003-ares-oracle/` builds separately and preserves LICENSE under ignored
target/. The bounded interpreter oracle agrees with Mupen on eight original
integer/control fixtures and verifies four cartridge/linked-memory/address-error
cases. No reference code is linked into Plaid core or a native artifact.
`spikes/004-ares-fetch/` additionally observes exact CPU fetches on the untouched
homebrew with a generated const debugger accessor. Its synthetic SP-entry/budget
scope excludes authentic PIF/IPL2 boot and complete-suite claims; streams remain
ignored and no RAM-copy or executable-lifetime inference is introduced.
`spikes/005-ares-physical-fetch/` records existing effective physical/cache inputs
in a generated CPU fetch TU. Cache-staleness, TLB remapping and endian-selection
fixtures pass; full broad checkpoint and v0-projection agreement remain exact.
The metadata establishes access context, not source backing or code lifetime.
`spikes/006-ares-rom-source/` forwards the actual ROM PI device once and records
returned halves in a bounded interpreter fetch window. Six original cases check
real source reads and rejection of latch/open-bus/prior-data contamination, with
unchanged CPU/PI checkpoints. Source/image promotion remains separate work.
`spikes/007-ares-rom-fetch/` extends that sensor to the bounded homebrew prefix:
1,852 reads at 65 canonical offsets, exact physical-capture projection and unchanged
checkpoints/messages. Other memory sources and executable lifetimes remain unknown.
`spikes/008-ares-pif-boot/` reads the existing NTSC CPU PIF firmware as an ignored
local input and records its digest, with no firmware bytes in project sources.
Natural CPU power entry and repeated checkpoints pass within a fixed NTSC/6102
profile. The reference PIF processor remains HLE; boot/source/lifetime scope is
not promoted into production or native mode. No firmware redistribution is added.
`spikes/009-ares-boot-profile/` versions the complete declared setup and checks
unchanged v3 projection/checkpoints. These metadata remain reference inputs;
source, executable-lifetime and hardware-equivalence claims are not promoted.
`spikes/010-ares-cache-snapshot/` reads selected instruction-cache fields at the
existing prologue, without coherence/translation/bus calls. Twelve original
fixtures preserve repeated CPU/timing and full RAM/cache checkpoints. Slot/data
observations remain finite context, with fill/copy/mutation lineage unresolved.
`spikes/011-ares-cache-fetch/` extends selected-line sensing to the bounded boot
prefix, with prior-stream projections and unchanged repeated CPU/device/memory/
cache checkpoints. Original Rust v5 data handling has a separate verified decision; snapshot
payloads establish neither fill provenance, epochs nor executable coverage.
`spikes/012-ares-cache-fill/` opts into a callback after the existing bus burst in
an ignored generated header, preserving upstream notices. Nine fills retain
unchanged controlled CPU/timing/RAM/cache goldens. Fill-event ordinals supply
no general lifetime or backing-source certificate; no reference code is promoted.
`spikes/013-ares-cache-tag/` executes original guest CACHE tag-store/invalidation
opcodes. A baseline without fill instrumentation and repeated sensor runs agree;
effective fetch pages can differ from historical fill pages without word changes.
Current tags/physical access therefore establish no byte-origin certificate.
`spikes/014-ares-cache-operations/` opts into a generated interpreter TU to retain
completed tag/data transitions. Three original guest CACHE operations match the
prior independent goldens and repeated state, without extra bus/translation/
timing calls. Default handlers stay original; production lifetimes stay unknown.
`spikes/015-ares-cache-outcomes/` extends original guest CACHE cases to hit/miss
invalidation, explicit fill and hit/miss writeback. Independent baseline and
sensor checkpoints match; uncached execution observes restored RAM after a stale
resident writeback. This is a finite identity-mapped RAM scope, not a general
bus/backing or write-success certificate.
`spikes/016-ares-rdram-bursts/` samples existing successful identity-mapped burst
results/stores in an ignored generated RDRAM header. Four read and one write
transaction preserve the prior complete projection/checkpoints; unsuccessful
attempts supply no valid backing witness. Default headers and source notices
are preserved; translated/degraded paths and executable lifetimes stay unknown.
`spikes/017-ares-rdram-boundaries/` uses declared direct-component chip/RI state
to verify remapping/degradation/failure exclusion and actual 16/32-byte identity
witnesses. Independent baseline and repeated returned words/CPU/RI/RAM/hidden
checkpoints agree. Requestor arguments supply no independent execution claim.

`spikes/018-ares-ordered-history/` measures one original ledger across existing
transaction/cache/fetch callbacks and explicitly declared fixture writes. All 43
records, prior complete projection and independent/repeated checkpoints match.
This finite ordering does not promote general provenance or executable lifetimes.
The recovered `spikes/018-ares-cache-reset-restore/` also executes synchronized
restore and explicit cache power against the pin. Reported baseline/disabled/
traced fields agree; restore creates valid residency without a fill. Broader
reset varieties and production checkpoint provenance remain separate.
Recovered original scalar-fetch/CPU-copy, RSP IMEM, exception-vector and two
64-bit-store harnesses now reproduce against this pin. Their reported state,
source guards and narrow byte/access truth tables are recorded in
`research/parallel-research-review.md`. All generated upstream shadows remain
ignored, separately compiled with the same notices; no reference implementation
enters Plaid's Rust dependency graph. Source/model-only PIF/SP/NMI/LLSC/table
findings retain their evidence level and independent reference disagreements.
`spikes/026-ares-access-history/` composes scalar/fetch boundaries with the
controlled ledger; `spikes/027-ares-boot-history/` streams the bounded boot sidecar
while preserving the complete v5 bytes and reported reference checkpoint.
These original observers supply finite callback chronology, not copied runtime
implementations, complete mutation coverage or production lifetimes.
Original Rust access-history inspection validates both complete raw sources and
supplied inputs, records finite counts/hashes and reconstructs reports for
rechecking. It promotes no reference code, ProgramMap images or lifetime rules.

## gopher64/gopher64

Purpose:

- readable Rust implementation of N64 CPU/hardware behavior;
- additional behavioral oracle;
- useful reference for Rust-side data structures and semantics.

## N64Recomp/N64ModernRuntime

Purpose:

- study native runtime boundaries for recompilation projects;
- libultra-style services, events, saves, overlays, PI/VI/RSP integration.

## rt64/rt64

Purpose:

- evaluate modern native N64 rendering integration;
- avoid rewriting the RDP/rendering stack in the first research milestone.

## Decompollaborate/spimdisasm

Purpose:

- N64-focused MIPS static analysis;
- function/pointer/symbol discovery;
- candidate frontend or validation source for our `ProgramMap`.

Pinned source license: MIT. A separately built comparison in
`spikes/001-spimdisasm/` uses the backend with original fixtures and explicit
section/mapping inputs. Its PARTIAL verdict treats functions/tables as hints;
there is no production dependency or exhaustive coverage inference.

## Decompollaborate/rabbitizer

Purpose:

- MIPS/RSP instruction decoding and register tracking;
- compare against or integrate for early decoder work.

## shygoo/n64sym

Purpose:

- known N64 library-function signature discovery;
- identify libultra/common routines without requiring symbols from the user.

## lemmy-64/n64-systemtest

Purpose:

- correctness tests for CPU, exceptions, TLB, memory, RSP, and other N64 behavior;
- verification corpus for lowering/runtime work.

Pinned source license: MIT. `spikes/002-systemtest-discovery/` builds guest source
with exact nightly-2022-07-10 and locked dependencies; the separately installed
MIT nust64 0.4.1 packager includes libdragon open-source IPL3. ROM/ELF/tool outputs
stay ignored and are not runtime dependencies. The PARTIAL headless probe exposes
unsupported cartridge execution in the dynarec and LLD/exception/LLAddr limits
in the interpreter. This pin cannot serve as a universal CPU oracle by itself.

`spikes/028-ares-pi-buffered-copy/` adds opt-in ignored generated PI boundaries
and delegates each actual ROM half-read once. Original transfer/lane validation
checks successful identity-RAM effects against canonical toy bytes and a separately
compiled original-source baseline. No reference PI code enters the Rust graph.
`spikes/029-ares-pi-fetch-history/` composes these source effects with actual CPU
fetch, burst/fill, SW and guest invalidation observations. Its original byte/
resident checker preserves separate histories, with the same isolation/notices.

## Source-use policy

`spikes/031-ares-pi-queue-contract/` separately compiles the pinned nall queue
header and checks PI/CPU routes. This is actual container execution plus source
evidence; it does not execute the CPU/PI components or certify hardware timing.
`spikes/030-ares-boot-pi-history/` composes actual PI source/buffer/write contexts
with the bounded boot sidecar under research v1. Original ROM-result forwarding
and source/effect checks preserve complete original-PI v0/v5 sources and reported
checkpoints. The existing v0 inspector deliberately rejects this version.
Separate original Rust PI inspection validates the complete typed v1 protocol,
canonical buffer origins and exact v0 projection without copying reference code.
Complete-source report rechecking preserves the finite inspection scope; no
queue completion or executable image/lifetime certificate is introduced.
`spikes/032-ares-queue-identity/` generates optional callbacks in an ignored pinned
nall header; external original metadata preserves actual insertion/heap identities
without changing object layout. Original/disabled/repeated container checkpoints
agree; save preserves identity and load cuts it. No CPU/device dispatch claim is made.
`spikes/035-ares-pi-queue-dispatch-context/` uses optional generated PI accepted-I/O
and CPU dispatch scopes to compose queue identities with actual component status
callbacks in both directions. Six forged joins fail and reported baseline state
agrees. No upstream implementation enters Rust or the native dependency graph.
`spikes/034-ares-sp-dma-lifecycle/` executes original component cases against pinned
ares without instrumentation and compares exact Mupen/Gopher source contracts.
Pending mutation/FULL disagreement remains reference-specific; source comparison
does not execute the GPL Mupen implementation or add any production dependency.
`experiments/pif-rom-backing/run_ares.py` generates isolated PIF-ROM backing/fetch
callbacks for nine actual fetch-stage tests, including the supplied local firmware
path. Reported original/instrumented/repeated checkpoints agree; no reference
implementation or firmware is copied into production. Full boot/immutability and
firmware authenticity are outside this bounded source contract.
`spikes/035-ares-cop1-stores/` executes actual pinned ares SWC1/SDC1 handlers and
an original independent payload model. Mupen/Gopher transaction decomposition is
source-only comparison; general mutation/lifetime and hardware atomicity remain
unknown, with no additional reference dependency in production.

Selected-cache v5 handling in Plaid is original Rust schema/import/verification
code. It checks the pinned reference's finite snapshot constraints while keeping
reference CPU code and firmware outside the production dependency graph.

Before introducing code copied or linked from an upstream project:

1. inspect its current license at the pinned commit;
2. record the decision in `docs/DECISIONS.md`;
3. preserve notices and obligations;
4. avoid contaminating a permissive component with GPL code accidentally;
5. when uncertain, use the project as a behavioral/reference oracle instead of copying implementation text.

`spikes/034-ares-ebus-hidden-fetch/` retains original project-owned header-probe/reducer code and its finite reference contract. Exact upstream headers are compiled only from the ignored pinned checkout; no upstream implementation or ROM data is vendored.

`spikes/036-ares-tlb-uncached-fetch/` reuses the original scalar/fetch sensor and executes actual pinned TLBWI/interpreter cases. n64-systemtest/Mupen comparisons remain source evidence, without hardware execution or extra production dependencies.

`spikes/033-ares-rdram-translated-backing/` generates optional reference shadows in ignored output, executes the original read/degrade once, and reproduces actual Word evidence. Gopher comparison stays source-only; no upstream source enters production.

`spikes/036-ares-dcache-eviction-lineage/` is an original project-owned model and actual guest transaction fixture with isolated optional reference shadows and preserved upstream licenses; no new production dependency.
