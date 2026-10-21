# Architecture Decision Log

## ADR-0001: Final native mode contains no runtime MIPS interpreter/JIT

Status: Accepted

Reason: this is the defining product goal. Instrumented emulation/dynarec execution is allowed during analysis and verification only.

## ADR-0002: Rust is the default language for project-owned code

Status: Accepted for bootstrap

Reason: memory safety, explicit data modeling, tooling, and suitability for binary-analysis/compiler infrastructure. This is not a performance claim over C++.

## ADR-0003: Reference implementations are pinned and kept out of the repository

Status: Accepted

Reason: reproducibility, license separation, and reduced repository noise.

## ADR-0004: No project license selected yet

Status: Superseded by ADR-0158 (MIT OR Apache-2.0)

Reason: dependency/reuse strategy is not final. Select a license only after deciding whether code from GPL projects will be incorporated or merely used as reference/oracles.

## ADR-0005: Ordered ProgramMap collections and versioned NDJSON traces

Status: Accepted, 2026-10-08.

ProgramMap v0 uses ordered sets/maps. Structured execution keys serialize as
sorted pair arrays, with duplicate keys rejected. Guest code identity includes
image and generation. Mupen compilation units remain distinct from basic blocks.
Trace v0 includes contiguous sequences and a mandatory end record: truncated
output is an error, not a successful discovery session. Invalidation includes a
separate global form. Target lookup and source-correlated indirect observation
are different events; neither finite samples nor installed entries prove closure.

## ADR-0006: Keep Mupen instrumentation in a separate GPL research patch

Status: Accepted, 2026-10-08.

Inspected pinned Mupen `LICENSES` and `new_dynarec.c` notices (GPL-2.0-or-later
for the instrumented file). The patch and sink are a GPL research instrument.
No Mupen implementation is copied into or linked with plaid-core. The wire
format is the boundary. Plaid's overall project license remains undecided.

## ADR-0007: Pin Rabbitizer as the discovery decoder

Status: Accepted, 2026-10-08.

Inspected `LICENSE` (MIT), the Rust API/build script, CPU examinations and target
getters at `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. Use its Rust/C library
through a revision-pinned Cargo dependency. Upstream source retains its MIT
notice; no decoder implementation is copied into Plaid. A C compiler is required
at build time. This is a decoder dependency for analysis, not a guest executor.
Discovery uses literal ISA target arithmetic because Rabbitizer's J target getter
treats PC zero as an unspecified address and substitutes KSEG0.

Explicit ROM/load mappings precede CFG analysis. No generic boot/CIC load mapping
is inferred from the header alone. Conditional, likely, call and delay-slot paths
are represented conservatively; exceptional/invalid/nested slots remain open.

## ADR-0008: Recheck local indirect certificates against bytes and current CFG

Status: Accepted, 2026-10-08.

Finite observations are stored independently from static candidate sets. A local
constant proof requires a single straight-line block prefix with no entry/candidate
bypass. Serialize the prefix hash, site and target; re-evaluate instead of trusting
producer labels. Later merges may invalidate a proof. These certificates do not
cover overlays, executable mutation, exceptions or the whole executable universe.

## ADR-0009: Scope closure is not native readiness

Status: Accepted, 2026-10-08.

Solver v0 re-derives instruction edges/sites from supplied bytes and rechecks local
certificates. Removing a blocker/edge from JSON cannot manufacture closure. A finite
immutable integer-image scope can report CLOSED with explicit exclusions; whole-ROM
mode stays OPEN until root/exception/DMA/overlay/write/RSP/execution-mode certificate
verifiers exist. No user-toggle booleans waive these obligations. `native_complete`
remains false: discovery closure is necessary but CPU lowering, runtime and behavioral
verification are also required. CLI `solve` defaults to whole-ROM scope.

## ADR-0010: Verify actual DMA copies before assigning executable sources

Status: Accepted, 2026-10-08.

The pinned cartridge hook records the actual copy extent after clipping at ROM
and RDRAM boundaries. Requested length and zero-filled bytes cannot establish
ROM provenance. Import joins prior covering DMA events with captured instruction
words and compares all bytes against canonical ROM content. Raw DMA observations
remain available independently. This proves a byte mapping, not overlay lifecycle,
relocation semantics or complete executable-copy coverage.

The synthetic harness invokes actual pinned compilation/copy routines without
executing generated host code. Runtime helpers trap if called. Its fixed interrupt
helper is test scaffolding, not a timing oracle; CPU differential testing is pending.

## ADR-0011: Retain inferred target evidence through bounded rediscovery

Status: Accepted, 2026-10-08.

Indirect targets inside a source image become traversal roots in a bounded CFG/
constant-analysis fixed point. Repartitioning may expose a bypass and revoke an
earlier local proof. Preserve its candidate and provenance rather than silently
dropping history. Iteration budgets produce blockers. Conditional link branches
separate taken calls, untaken fallthrough and possible return continuation; returning
does not execute the original call's delay slot again.

## ADR-0012: Trace completed indirect transfers before cache dispatch

Status: Accepted, 2026-10-08.

The optional x64 in-unit JR/JALR sensor is generated after delay-slot execution
and before the cycle check and mini_ht/general lookup split. It receives the saved
target operand, preserves allocated caller-save registers, and does not reuse
host addresses as portable identities. Trace capability names describe this
restricted coverage, not a whole-ROM execution guarantee. When disabled, no
execution sensor calls are generated. Validate state preservation against the
pinned pure interpreter and untraced dynarec; devices/timing remain excluded.

Persist raw indirect observations independently of image-resolved site edges.
The target may be compiled after the observation, so defer that identity join to
the end of the same invalidation epoch. Source identities are fixed at observation
time; ambiguity remains a blocker. Later generations cannot explain earlier jumps.

## ADR-0013: Reconstruct CFG for restricted cross-block proofs

Status: Accepted, 2026-10-08.

Propagate constants through unique direct predecessors in a scalar instruction
subset, applying only the selected edge's delay-slot effects. Entries and all
candidate/observed indirect incoming targets begin with unknown registers. Calls,
joins, loop invariants and memory effects are not summarized. Reconstruct direct
CFG from instruction bytes, then check supplied block/edge facts: deleting a
predecessor cannot manufacture a proof. Serialize selected edges, block identities
and word hash; independently recompute them when verifying. Bounded analysis may
remain unresolved. This is declared-CFG evidence, not whole-ROM coverage.

## ADR-0014: Pointer-table snapshots yield candidates, not closed targets

Status: Accepted, 2026-10-08.

A restricted SLTIU/branch guard followed by scalar address construction, SLL,
ADDU, LW and JR/JALR can suggest a bounded table. Enumerate at most 256 entries
from a supplied memory image, retaining guard/prefix/table hashes and assumptions.
Reject known bypasses, changed index registers, unsupported bounds, incomplete
sources and malformed pointers conservatively. These facts are candidate evidence:
neither table immutability nor all runtime entry paths are certified. The solver
must keep the indirect site and immutability obligation open. Pattern matches may
guide traversal but may never manufacture native readiness.

## ADR-0015: Carry pagespan source context to the separate delay-slot unit

Status: Accepted, 2026-10-08.

The research x64 predecessor records an indirect site tag; direct page-spanning
branches clear it. The separately compiled delay-slot unit checks the tag against
its predecessor PC and reports the saved target after executing the slot. This
avoids inventing JR/JALR events for direct predecessors or reading a source register
after a slot overwrite. Keep this transient single-core reference state out of
portable identities. Differential tests cover JR, custom-link JALR and direct
pagespan paths; ProgramMap's predecessor-state model is still an open obligation.

## ADR-0016: Exercise discovery through a separately built full reference core

Status: Accepted, 2026-10-08.

Build the pinned GPL core from a clean temporary Git export plus the research
patch; keep its library, headers and synthetic ROM under ignored `target/`.
Use public frontend/config/debugger APIs with bundled dummy plugins and an
original bootstrap. Real PI register writes, busy polling, DMA, RAM store/load
and IS64 output exercise device integration absent from the flat-memory harness.
Compare interpreter and traced/untraced dynarec CPU state and repeated traces.
Do not infer boot/CIC completeness, device accuracy or RSP/graphics coverage from
this session. Uncorrelated PIF-HLE boot copies and executable policy gaps remain
solver obligations; the reference core is never linked into Plaid/native mode.

## ADR-0017: Physical overlap is candidate evidence, not execution identity

Status: Accepted, 2026-10-08.

Different virtual executable ranges may share RAM. Compare load spans using
explicit, unique physical mappings retained by matching regions in addition to
guest overlap. This can expose overlay candidates across cached/uncached aliases.
Do not infer mappings from virtual bit patterns or collapse CodeAddress identities;
cache behavior, relocation, lifetime and dispatch still need independent policies.
Missing or contradictory physical mappings cannot establish a unique alias.
The full-core replacement fixtures validate separate generations and conservative
candidate overlays, not a complete overlay lifecycle certificate.

## ADR-0018: Copy identity is distinct from a compiled executable snapshot

Status: Accepted, 2026-10-08.

Cache invalidation and subsequent matching compilation do not establish another
copy. Add optional copy-event provenance to load mappings, validating Trace kind,
evidence membership and covering typed DMA/physical-region facts. Classify an
exact reload only when both snapshots refer to distinct observed copy events.
Legacy maps retain no inferred copy identity. Session-scoped copy references also
keep imported load evidence separate across traces. CPU copies without a sensor
and CPU-mutated snapshots remain unknown-source/write obligations, as verified
by original full-core fixtures; no pattern guess can waive executable policies.

## ADR-0019: Keep disassembler function/table hints outside closure proofs

Status: Accepted for research, 2026-10-08.

The separate pinned MIT spimdisasm/Rabbitizer experiment finds useful direct-call
and guarded-table hints on original inputs with explicit section/mapping spans.
Function extents also include unreachable words/padding, and truncated returns
still produce hints. Keep the disposable comparison outside production. Any
future adapter needs a separate design decision, canonical hashes, provenance,
image/generation/mapping identity and candidate-only semantics. A hint cannot
replace independently rechecked CFG or executable-universe/table certificates.
Both tools share Rabbitizer, so this comparison is not an independent CPU oracle.

## ADR-0020: Preserve partial successful CPU-store observations explicitly

Status: Accepted, 2026-10-08.

An opt-in x64 research callback runs after successful aligned SW to a constant
cached-RDRAM address, including any invalidation-stub return. Preserve caller-save
registers and copy the value before overwriting ABI arguments. Trace/ProgramMap
retain raw source/destination/value and conservative import epoch. Only overlap
with previously compiled explicit physical mappings adds Unknown executable-write
evidence; ordinary data stores remain raw facts. Do not infer complete write,
copy, relocation or lifetime coverage from this limited sensor. Differential
sessions cover patch writes, zero values, register pressure and branch delay slots.
Invalidation/restored-entry joins remain unresolved rather than crossing epochs.

## ADR-0021: Identify an executing indirect source by its compiled unit

Status: Accepted, 2026-10-08.

Invalidation can advance the import epoch while an older generated unit keeps
executing. Embed its trace-local compilation ID in each x64 JR/JALR callback,
including the predecessor unit for pagespan transfers. Validate completion and
source-PC containment before import; attach only to that exact decoded indirect
site. Preserve session-qualified CompileBegin provenance in raw observations.
This supports older sources without a PC-only cross-generation guess. Events
without unit context retain the conservative epoch rule. Target snapshots still
must be unique in the current epoch; a source tag does not establish a restored
target's active bytes or lifecycle. Differential CPU and full-core fixtures pass,
including generation 8 -> 9 in the store-stress call. Older return targets stay
unresolved and all whole-ROM reports stay OPEN.

## ADR-0022: A dirty-entry byte check can identify a pending older target

Status: Accepted, 2026-10-08.

Carry compilation-unit IDs on reference linked-list metadata and preserve them
when clean entries are copied. After a successful `get_dirty` byte comparison,
emit the installed PC/mask and complete saved words. Trace validation requires
exact equality with that completed unit and an installed entry/mask. ProgramMap
retains a typed entry-verification observation with verification epoch separate
from compilation generation. Use this snapshot only for a pending target in the
same epoch, preserving its verification provenance. Intervening invalidation,
missing sensor data or competing target identities prevent the join. A lookup
does not establish execution, a new copy, complete cache/lifecycle coverage or
an exhaustive indirect target set. The original store-stress return now resolves
its observed generation-9 -> 8 identity; its whole-ROM report still stays OPEN.

## ADR-0023: Imported facts share the merger's canonical provenance union

Status: Accepted, 2026-10-08.

Repeated semantic sensor facts differ only by event provenance. Normalize those
sets once after trace correlation, preserving all references, so self-merging an
import cannot change its bytes. Apply the same normalization to diagnostics
added after a map union; expanded evidence should extend one conflict rather
than duplicate it. Copy-event identities, generations, values and unit identities
remain semantic fields and are not discarded. This fixes an import/merge mismatch
without weakening blockers or treating repeated observations as coverage proof.

## ADR-0024: Treat broader reference failures as discovery/oracle limitations

Status: Accepted for research, 2026-10-08.

The pinned n64-systemtest source builds reproducibly, but the pinned dynarec
cannot fetch its IPL3 cartridge code at B0001040 and exits without a valid trace
footer. The interpreter boots farther, reports upstream failures and stops on
unimplemented LLD. Keep this PARTIAL evidence as a reference capability boundary,
preserve the guest, and reject the crashed trace. Extend general cartridge source
modeling/capture and independent oracles through separate decisions; these
failures do not authorize per-guest workarounds, fabricated completion, universal
CPU claims or early native lowering. No GPL reference code enters Plaid core.

## ADR-0025: Use a separately built, bounded ares interpreter oracle

Status: Accepted for research, 2026-10-08.

The pinned ares core runs four original cartridge/LLD/SCD/address-error cases
and independently matches every GPR, HI/LO and PC on the eight existing Mupen
integer/control fixtures. Use it as an additional oracle for this declared scope.
Build the ISC/BSD reference separately, preserve upstream notices, disable both
CPU/RSP recompilers and assert those settings. The headless recipe omits UI assets,
guards one renderer call in a generated System::run translation unit, and supplies
the hidden-RAM backing otherwise owned by Vulkan. CPU/RSP instruction sources
remain exact. Explicit synthetic initial state excludes boot and event-equivalence
claims. No reference code or decoder enters Plaid core or native mode. Broader fetch
sensing, FPU/TLB/RSP and native differential acceptance require separate work;
finite fixture agreement cannot close a whole-ROM executable universe.

## ADR-0026: Observe exact ares fetches through its debugger, with explicit bounds

Status: Accepted for research, 2026-10-08.

The existing interpreter instruction prologue passes its actual fetched word to
the debugger before opcode execution. A generated const disassembler accessor
exposes that word to a headless callback; no CPU fields/layout or instruction
semantics change. Disable history/mask suppression and recompilation, retain
64-bit PC and delay-slot context, and perform no additional guest reads or TLB
translations. Five-million-call tests preserve full GPR/HI/LO/PC/Count, RAM/SP
hashes and guest message bytes while repeated fetch streams match exactly.
Cartridge fetch words are checked against canonical bytes through the direct
segment mapping. This separate research format declares synthetic SP entry and
budget-stop scope; it is not a fabricated compilation/copy trace. Keep the startup
Config failure and unknown PIF/IPL2 state visible. Production schema, import,
changing-byte identity, copy/overlay lifecycle and scalable provenance require a
separate implementation decision. Neither fetched words nor broad finite samples
prove retirement, immutability, complete execution coverage or whole-ROM closure.

## ADR-0027: Import raw fetch summaries without inventing execution identities

Status: Accepted, 2026-10-08.

Add a streaming reader for the exact pinned observer format and conservative
ProgramMap raw facts. Preserve typed 64-bit virtual PCs, distinct words and slot
states, and one capture's exact first/last event indices and occurrence count.
The complete raw-byte SHA-256 qualifies capture identity and provenance; first/
last do not denote a contiguous interval or executable lifetime. Strict bounded
records, header/revision/initial-state checks, sequential events, budget and footer
checks precede import. A verifier regenerates summaries from their complete raw
source and rejects changed facts or provenance. Validate count conservation and
endpoint witnesses, preserve capture identities under union and default fields
when reading legacy maps. An independent solver blocker prevents unresolved raw
identities from closing an otherwise verified declared-image CFG. No regions,
blocks, entries, copies, generations, retirement or immutability are inferred.
This promotes project-owned data handling, not reference CPU code. Physical
backing, full chronology and executable-generation joins require separate work.

## ADR-0028: Sample effective physical fetch context without extra CPU accesses

Status: Accepted for research, 2026-10-08.

The pinned interpreter already computes translation, endian-selected word address
and cache policy before fetching. A generated source assignment records those
inputs in observer metadata without extra reads/translations or CPU layout changes;
the existing prologue pairs them with the exact word. Plain/repeat checkpoints and
the complete v0 projection match. Focused cases verify stale cached words, uncached
aliases, invalidation, TLB remapping and reverse-endian selection. Resolve generated
CPU quoted includes explicitly to avoid selecting same-named system files.
The research v1 header records actual mapped cartridge capacity, including the
pin's eight-byte rounding. This is effective access context, not proof of backing
bytes, retirement or executable lifetime. Preserve notices and build the ISC/BSD
reference separately; no reference instruction code enters Plaid or native mode.
Production handling and image/source/lifecycle joins require separate decisions.

## ADR-0029: Preserve versioned physical access in raw fetch summaries

Status: Accepted, 2026-10-08.

Import the pinned research v1 stream as project-owned data. Each observation may
carry typed effective physical address/cache policy; include both in semantic
uniqueness and endpoint witnesses so remappings or cache variants never collapse.
The capture's explicit mapped capacity identifies v1 and must match the pinned
loader's canonical-ROM capacity rounding. Require both access fields in every v1
event and reject them in v0; null, partial pairs and misalignment fail. Extend the
full-source rechecker to these facts and metadata. Default/omit additive fields to
preserve byte-identical v0 serialization. Keep v0 and v1 capture identities separate
under merge. Physical context creates no ROM/load source, image, generation or
retirement claim; the independent unknown-identity solver gate remains unchanged.
No reference CPU code is promoted. Backing-source and lifecycle witnesses need
separate evidence before any executable-image construction.

## ADR-0030: Test ROM fetch witnesses through actual delegated PI reads

Status: Accepted for research, 2026-10-08.

A project-owned PI wrapper forwards the pinned ROM device's address/read/write
operations once and records only returned halfwords. Clear its ledger before each
single interpreter call and pair reads at the existing pre-decoder prologue.
Require uncached effective address, consecutive source offsets and exact returned
word. Three synthetic reads acquire witnesses, while identical PI latch data,
unmapped file tail and prior data reads remain unknown. Original/plain/traced/
repeat CPU/Count/PI checkpoints match. This relies on the pinned interpreter call
boundary with both recompilers disabled; no additional guest reads/translations
or reference CPU changes occur. Keep this separately licensed research experiment
isolated. Broader corpus capture, canonical source verification and production
handling require further work; no generation/immutability/closure is promoted.

## ADR-0031: Extend actual ROM-read sensing to the bounded homebrew prefix

Status: Accepted for research, 2026-10-08.

Research v2 declares the delegated-halfword fetch-window policy and preserves
known or unknown source on every event. Actual ROM reads account for 1,852 fetches
at 65 offsets, with canonical bytes and mapped bounds checked. Other sources stay
unknown. Complete v1 projection, full checkpoints/messages and repeated v2 bytes
agree. Fixed golden hashes avoid racing other experiments' mutable outputs.
Existing observer modes and source-boundary fixtures pass. Keep the interpreter
window/recompilation constraints explicit and retain all boot/coverage/lifecycle
limits. Production data handling and executable-image identities remain separate
decisions; no reference CPU code or native execution is promoted.

## ADR-0032: Recheck finite ROM fetch sources without inventing code images

Status: Accepted, 2026-10-08.

Import research v2 with its explicit source policy and a known/unknown source on
every fetch. Cartridge facts require aligned mapped bounds, matching uncached
effective physical address and the exact canonical ROM word. Full-source
verification regenerates these facts and their capture metadata/provenance.
Source variants participate in semantic and endpoint identity; unknown latch
data remains separate even when words and addresses match. Use a strict empty
struct for the unknown variant so extra fields cannot be silently accepted.
Default/omit additive fields to retain byte-identical v0/v1 maps. Mixed captures
merge conservatively. The finite source witness does not establish immutable
images, generations, retirement or executable lifetime. Keep the independent
solver identity gate and create no regions/entries/copies from these facts.
Only project-owned data handling is promoted; no reference CPU/runtime is linked.

## ADR-0033: Observe natural CPU power entry with an explicit firmware input

Status: Accepted for research, 2026-10-08.

Load the pinned checkout's ignored NTSC CPU PIF firmware through the system pak
and start from CPU::power, without host SP copying or register/PC shortcuts.
Record firmware hash, PIF HLE and enforced checksum policy; retain the fixed
NTSC/6102/8-MiB/deterministic experiment profile. Plain/traced/repeated CPU/device/
memory checkpoints agree. The bounded prefix passes the checksum stage and sets
Config naturally, while remaining in PI DMA polling before guest tests begin.
Keep source words unknown unless actual device-read witnesses exist; PIF address
or firmware equality alone cannot exclude SI latches/ROM lockout. Research v3
is unsupported by production. Complete profile metadata and supplied-input
verification need a separate decision before promotion. Firmware/reference
objects stay ignored, notices preserved and no reference/native code is promoted.

## ADR-0034: Version the complete declared boot profile separately

Status: Accepted for research, 2026-10-08.

Research v4 carries firmware hash/size, NTSC region, CIC-NUS-6102, 8 MiB RAM,
deterministic entropy, reference PIF HLE and enforced checksum in one explicit
boot_inputs object. Preserve v3 as a distinct scope rather than retroactively
changing its header. Complete v3 projection and fixed CPU/device/memory checkpoint
hashes agree at one million calls, with matching plain/traced/repeated execution.
These are declared reference inputs, not automatic ROM-profile discovery. Future
production handling must check supplied firmware bytes and the complete source;
metadata does not establish PIF backing, executable generations or full coverage.

## ADR-0035: Require firmware bytes when importing declared boot inputs

Status: Accepted, 2026-10-08.

Import research v4 through an explicit firmware-input API/CLI path. Validate the
complete fixed profile, hash and size of supplied firmware, power-entry PC/access/
word/slot and complete raw source. Retain typed boot metadata in digest-qualified
captures and recheck it with every fact and provenance record. Missing, null,
partial, unsupported or changed inputs fail; the legacy path cannot silently
accept boot captures or ignore a supplied firmware file. V3 remains unsupported
because it lacks the full profile. Default/omit the additive map field to retain
legacy serialization. Header inputs identify supplied bytes and declared setup;
they do not authenticate firmware or prove PIF backing, hardware equivalence,
retirement or executable lifetime. No regions, copies or generations are created.
Keep the unknown-execution solver gate. Only project-owned data handling is
promoted; firmware assets and reference CPU/device code remain outside Plaid.

## ADR-0036: Sample selected cache-line fields without inventing a lifetime

Status: Accepted for research, 2026-10-08.

At the existing interpreter prologue, sample slot, tag/valid bits, index and eight
words from the line selected by virtual PC. Verify the fetched word with the
effective physical lane after endian selection. Add no coherence/bus/translation
call. Twelve controlled fetches preserve repeated CPU/COP0/timing and complete
RAM/cache checkpoints. Same bytes recur after eviction, and different slots hold
identical contents; retain slot/event identity and refuse lifetime inference.
Snapshot words establish finite resident context, not RAM/ROM lineage or execution
of every resident word. Broader capture, import and complete-source verification
need separate decisions. No reference CPU or native code is promoted.

## ADR-0037: Retain finite selected-cache context on the boot prefix

Status: Accepted for research, 2026-10-08.

Research v5 adds an explicit selected-line policy and resident snapshot to each
cached fetch; uncached fetches omit it. Retain all v4 boot inputs and existing
ROM-source policy. The one-million-call prefix has 400,954 cached observations
at 32 resident tuples, exact prior stream/checkpoint projections and matching
plain/traced/repeated CPU/device/memory/cache checkpoints. Validate slot, tag,
page index and effective word lane without extra guest accesses. Keep counts
distinct from fill/epoch identities; other resident words have no execution
claim. Production currently rejects this scope. Complete-source verification and
production import require separate handling; backing/lifetimes remain unknown.

The ten-million-call prefix also preserves the prior goldens and complete cache
checkpoint neutrality: 9,399,022 cached observations at 8,118 resident tuples.
Fresh v4/v2 reference builds retain earlier stream/checkpoint hashes. This extends
the measured finite scope without a fill/lifetime or complete-suite claim.

## ADR-0038: Import selected-cache snapshots as finite context

Status: Accepted, 2026-10-08.

Import research v5 through the existing explicit firmware-input path. Require
the supported boot/source/cache policies and a strict eight-word snapshot for
every cached fetch; uncached and older formats cannot carry snapshots. Check
virtual slot, physical tag/valid bit, page index and effective fetched lane.
Keep slot and all resident words in the semantic summary key, preserving variants
without manufacturing cache epochs. Rebuild all facts, metadata and provenance
from the complete raw source, including unfetched lanes. Additive optional map
fields preserve old serialization. The point snapshot proves no backing source,
fill/copy history, immutable lifetime or execution of other lanes. Keep the
unknown-execution solver gate; create no executable regions, entries or copies.
Only project-owned Rust data handling is promoted; reference code and firmware
stay isolated and ignored.

## ADR-0039: Observe completed cache fills without inferring cache epochs

Status: Accepted for research, 2026-10-08.

Add an opt-in callback after the pinned reference's existing instruction-cache
fill bus burst in an ignored generated header. Record array slot, effective
request/burst address and returned words, with monotonic event ordinals. Read no
additional guest memory and serialize no host pointers. Nine fills across twelve
controlled fetches distinguish equal-payload refills and cache-bank aliases;
plain/traced/repeated CPU/timing/RAM/cache goldens remain unchanged. The default
reference header stays unchanged. A last-fill link in these controlled cases
does not prove validity across CACHE tag stores, invalidations, reset/restores
or RAM/copy mutations. The burst address alone does not establish backing source.
Broader capture and production lifetime handling remain separate decisions.

## ADR-0040: Separate current cache tags from resident-byte origins

Status: Accepted, 2026-10-08.

Guest CACHE index-store-tag can change the effective hit page without refilling
or altering resident words. A seven-instruction controlled fixture retags page
0 to 0x4000 and back around an explicit invalidation/refill. Two effective fetch
pages differ from their last fill's burst page. Baseline without the fill hook,
plain/traced/repeated CPU/timing/RAM/cache checkpoints agree. Never infer byte
origin from the current tag or effective fetch physical address. Retain the
historical fill as finite data-history evidence, while requiring actual bus
backing witnesses and explicit tag/invalidation/reset/restore boundaries for
general lifecycle joins. The existing unknown-source/execution gates remain;
no production source or immutable lifetime certificate is fabricated.

## ADR-0041: Retain completed guest cache-operation transitions separately

Status: Accepted for research, 2026-10-08.

An opt-in generated interpreter TU samples existing selected-line fields before
and after supported CACHE handlers. Preserve instruction PC, effective virtual/
physical operand address and before/after tag/eight words, without additional
guest accesses or clocks. Three controlled tag-store/index-invalidate operations
match independently checked CPU/timing/RAM/cache goldens and repeated JSON. The
default build keeps its original handler; hooks are research-only. Invalid
translations have no completed event. Hit-invalidate/fill/writeback outcomes,
backing reads/writes, reset/restore and a unified event history need separate
verification. Completion is not a successful RAM-write or immutable-lifetime
certificate. Do not promote a cache lifecycle or executable image from this scope.

## ADR-0042: Verify cache hit/miss outcomes before lifecycle construction

Status: Accepted for research, 2026-10-08.

Extend controlled guest CACHE cases to hit/miss invalidation, explicit fill and
hit/miss writeback. Eight completed operations across seventeen fetches preserve
baseline/plain/traced/repeated CPU/timing/RAM/cache checkpoints, with four fills
and one writeback. Deliberately change RAM while resident data stays stale, then
require successful writeback and an uncached fetch of the restored word. Miss
operations preserve state. This validates finite outcomes for identity-mapped
RAM, not a general backing/write-success policy. Still require actual bus/copy/
mutation witnesses, failure/reset/restore boundaries and unified event ordering
before constructing executable lifetimes. No production epoch/image is promoted.

## ADR-0043: Observe actual identity-mapped RAM burst transactions

Status: Accepted for research, 2026-10-08.

An opt-in generated RDRAM header samples the existing returned words after
successful identity-mapped burst reads and input words after actual stores/hidden
updates. Four reads match the measured fills; one completed store explains the
controlled writeback. Invalid zero reads/ignored writes supply no valid witness;
translated/degraded paths stay unclaimed. Preserve complete prior JSON and
CPU/timing/RAM/cache goldens without extra accesses or clocks. Default builds
use the original RAM header, including when reusing a prior sensor directory.
These are RAM transaction witnesses, not ROM origins, complete mutation coverage
or executable lifetimes. Require broader mapping/failure/reset/restore and
unified history/copy witnesses before production source/lifecycle handling.

## ADR-0044: Keep nonidentity and failed RAM paths outside identity witnesses

Status: Accepted, 2026-10-08.

Direct-component tests remap bus address zero to another backing chip, store
through translation, exercise zero/partial degradation, missing mappings,
inactive RI and out-of-bounds access. None may produce a valid identity witness,
even when returned bytes match backing bytes. Actual 16/32-byte identity paths
retain witnesses. Baseline/plain/traced/repeated returned words, CPU/RI state
and full RAM/hidden-memory hashes agree, including deterministic degraded-word
goldens. This validates policy boundaries in declared synthetic component state,
not guest execution, hardware initialization or complete backing coverage. Keep
unsupported policies unknown; unified history and copy/lifetime work remain open.

## ADR-0045: Measure one controlled callback chronology before joining lifetimes

Status: Accepted for research, 2026-10-08.

Retain one original ordered ledger across existing successful RAM burst, fill,
CACHE completion and pre-decoder fetch callbacks. Include declared fixture writes
with explicit host attribution. Every payload is referenced exactly once; measured
read/fill/fetch and writeback/completion order, complete prior projection and
independent baseline/plain/repeated checkpoints agree. Reordered/missing/forged
records fail. This validates the controlled chronology, not a general causal
context, mutation census or executable lifetime. Ordinary scalar backing events
and reset/restore/copy/byte-write findings require separate integration. Historical
fill data is distinct from current effective tags. No production epoch is created.

## ADR-0046: Restore provenance cannot be inherited from the latest matching fill

Status: Accepted, 2026-10-08.

The recovered reference fixture saves a synchronized state, creates an equal-
payload refill, then restores the saved valid line without a new fill. An external
latest-tuple matcher incorrectly selects the later pre-restore fill. Baseline,
callbacks-disabled and repeated traced reported fields agree; explicit cache power
clears residency and forces a new fill. Analysis restore must identify a checkpoint
and capture branch, or leave restored origin unknown until separately witnessed.
Preserve distinct backing and cache lifetimes: source inspection/model shows NMI
does not clear either, system reset clears cache while preserving RAM, and full
power initializes both. These varieties are not equivalent transitions, and the
controlled restore result is not a hardware-wide reset certificate. No production
image/generation/closure rule is issued by the research fixture.

## ADR-0047: Preserve source context and successful byte effects before promotion

Status: Accepted for research, 2026-10-08.

Seventeen reviewed research tips supply distinct evidence levels. Independently
reproduced scalar-fetch and CPU-copy fixtures require explicit access boundaries,
successful backing transactions, separate resident/backing histories and later
register-dataflow proof. A fetch interval needs exactly one eligible scalar read
before an identity-RAM word witness is possible; equality and CPU requester alone
are insufficient. RSP DMA/fetch tests require latest-writer fragment history;
equal bytes cannot identify an installation lifetime. Independent SD/SDL/SDR
matrices require ordered successful byte effects, retaining untouched-lane history
without invented reads. Mode-sensitive exception vectors require separate handler
bytes and reachability proof. PIF/SP/NMI/LLSC/table contracts remain source/model
evidence where no reference fixture was executed. Retain the reviewed original
harnesses and explicit limitations, integrate narrow sensors into shared research
chronology next, and issue no production image/lifetime or whole-ROM certificate.

## ADR-0048: Combine successful fetch boundaries with the controlled chronology

Status: Accepted for research, 2026-10-08.

Two explicit shared-builder options retain ordinary successful identity-RAM
reads/writes and begin/end of successful CPU fetch accesses after endian address
selection. They compose with existing burst/fill/CACHE callbacks without extra
guest accesses or clocks. The 95-record controlled ledger retains the complete
previous 43-record projection and independent/disabled/repeated reported
checkpoints. Nine uncached word reads lie inside their actual fetch contexts;
nine debugger writes retain separate fixture attribution. Six forgeries fail.
The recovered independent scalar-fetch and CPU-copy fixtures preserve their full
traced JSON through this common recipe. Extend this narrow measured chronology
to the fixed boot profile before deciding source-linked production representation.
Failure/nonidentity paths and general mutations/copies/restore lifetimes remain
unclaimed; default recipe handlers and whole-ROM gates stay unchanged.

## ADR-0049: Retain bounded boot chronology alongside the unchanged v5 capture

Status: Accepted for research, 2026-10-08.

Stream existing scalar/burst/fill/CACHE/fetch-boundary/prologue results into a
separate versioned sidecar, preserving the existing complete v5 stream. The
one-million-call declared boot profile yields 5,051,089 records with unchanged
prior bytes and reported baseline/disabled/repeated machine checkpoint. Thirty-
two RAM-backed fills agree with adjacent actual bursts and complete resident
snapshots; nineteen data reads lie outside fetch contexts. This prefix contains
no uncached RAM instruction fetches, so its corresponding witness count is zero.
DMA writes remain backing effects without source/transfer-completion or image
lifetimes. Truncated timeout output fails; complete retained inputs/streams can
be rechecked without rerunning the CPU. The sidecar is reference research data,
not a production certificate. Implement original strict Rust inspection and
source rechecking under a separate decision before any identity promotion.

## ADR-0050: Inspect access history through both complete sources without image promotion

Status: Accepted, 2026-10-08.

Add original Rust typed streaming validation and an independent inspection report.
First validate the complete v5 source, ROM and supplied firmware/profile with the
existing importer; then compare every sidecar access/prologue against its paired
fetch and rehash the replay to reject source changes between passes. Require
bounded supported policy, unique contiguous ordinals, matching contexts/words,
typed transaction widths/addresses and complete footers. A scalar word witness
requires one eligible read; immediate cached backing additionally requires one
fill, an adjacent actual RAM burst and agreement with every paired resident word.
Ambiguous and unsupported paths stay unknown. Reports bind both complete hashes
and all finite counts; rechecking reconstructs the entire report, including
otherwise-unused source payloads. Five adversarial Rust tests and the complete
5,051,089-record boot corpus agree with the independent Python checker; legacy
tests stay OPEN and no ProgramMap field, image, generation or lifetime changes.
Reference code remains separately licensed/compiled; only original data handling
enters Plaid core. This is finite access inspection, not a mutation census,
hardware certificate, whole-ROM proof or native execution path.

## ADR-0051: Join buffered PI sources only through consumed lanes and successful effects

Status: Accepted for research, 2026-10-08.

Observe actual returned ROM halves, DMA block/buffer lanes, write attempts and
successful identity-RAM effects under distinct transfer ordinals. Whole buffers
are read before writes; adjacent-read matching is insufficient. Alignment can
discard source bytes or a whole first block. The eight-case reference fixture
retains 95 exact ROM byte origins, eight unknown open-bus writes and eight failed
destinations, preserving independent original-source/disabled/repeated reported
checkpoints. Equal reloads remain distinct; data effects and later busy/interrupt
completion remain separate. Direct component invocation proves no guest MMIO,
scheduler duration, complete mutation census or executable lifetime. Compose
these finite writers with actual fetch/fill chronology before a separately
reviewed boot-schema or production identity decision.

## ADR-0052: Preserve backing writers separately from resident byte origins

Status: Accepted for research, 2026-10-08.

The composed PI/CPU fixture joins each successful buffered byte writer to an
actual uncached fetch or adjacent burst/completed fill. A valid cached line
retains its first transfer's origins through identical and changed reloads and
a guest SW; actual guest invalidation removes residency before a new fill.
Three-byte reloads preserve mixed origins and untouched bytes without inventing
a contiguous ROM word. The 481-record, 16-fetch fixture preserves independent
original-source/disabled/repeated reported checkpoints, including full backing/
hidden/cache hashes. Seven forgeries fail and ambiguous reads lose attribution.
This validates finite byte provenance only under the controlled identity-RAM,
single-capture policy. Broader cache/restore/mutation and executable lifetime
obligations remain open. Extend versioned boot capture with PI source/transfer
contexts while preserving complete prior projections before production promotion.

## ADR-0053: Shared PI status transitions cannot certify transfer completion

Status: Accepted for research, 2026-10-08.

Pinned source routes both queued DMA directions to the same busy/interrupt
completion method and permits guest cancellation and silent insertion failure.
The actual queue-container probe retains duplicate identifiers, invalidated
entries consuming all 512 slots, cancellation without callbacks and one wrap
case. This is container execution plus CPU/PI source evidence, not full device
or hardware testing. A last-write observer context at a status transition is
only capture metadata; do not certify transfer completion from it. Future
completion evidence needs distinct successful insertion/dispatch identity,
direction, cancellation/removal and capture lifecycle. Keep completed byte
effects separate from queue success or completion and retain unknown obligations.

## ADR-0054: Capture finite boot PI origins under a distinct research version

Status: Accepted for research, 2026-10-08.

Research history v1 retains returned PI buffer halves, actual delegated ROM
results, attempts/returns and successful identity-RAM transfer/block/lane effects
alongside the existing chronology. The 610,000-call prefix joins 1,638,808 writes
to exact canonical ROM sources, preserving all complete original-PI v0/v5 bytes
and reported baseline/disabled/repeated checkpoints. The 8,823,134-record stream
repeats exactly; its v0 projection preserves ordinal/context relationships.
Four copy calls return and three status transitions occur; the final reference
busy bit remains set. Status observer contexts do not certify queue-to-transfer
completion under ADR-0053. Seventeen forged/truncated metadata/protocol cases
fail. Production v0 rejects research v1; only the original projected v0 can use
the existing inspector. Implement strict original Rust v1 source rechecking
under a separate decision before promotion; finite copy facts supply no complete
mutation census, executable identity/lifetime or whole-ROM certificate.

## ADR-0055: Inspect buffered PI effects through a typed streaming projection

Status: Accepted, 2026-10-09.

Add original Rust v1 inspection under a separate API and report schema. Validate
actual canonical ROM halves, consumed buffer lanes, attempts, successful identity-
RAM writes and matching returns while streaming an exact typed v0 projection into
the existing complete-source validator. Preserve both raw source hashes and a
digest of each finite byte effect including its successful writer ordinal.
Reconstruct the entire report for source rechecking. Reject duplicate/unknown
fields, unsupported versions, missing footers, inconsistent contexts and PI
events inside fetch intervals: dropping such records could conceal ordering
violations from the projected validator. The supported capture places synchronous
PI effects outside fetch intervals; broader contexts require separate evidence.
Five adversarial Rust tests and the complete 8,823,134-record corpus preserve
every independent Python count/hash and the exact prior v0 report. Last-write
contexts at status transitions remain metadata under ADR-0053; completion is
always uncertified. No ProgramMap, solver, image generation, executable lifetime
or native path changes. Reference implementation/firmware stays isolated and
ignored; only original typed data validation enters the Rust dependency graph.

## ADR-0056: Retain queue identity outside reference object state

Status: Accepted for research, 2026-10-09.

Generate opt-in callbacks at actual queue heap copies, insertion, cancellation,
removal and lifecycle boundaries. Original external metadata assigns a token
only after successful insertion and follows actual slot moves. Six actual-container
cases preserve original/disabled/repeated reported dispatches, occupied serialized
state and object size, including identical event/deadline pairs and full capacity
after cancellation. Serialization entry discards metadata; restored entries stay
unknown. Five forged records fail independent replay. This validates finite
container identities only, not CPU/device dispatch, PI transfer completion or
hardware timing. Compose actual request/dispatch/status contexts before stronger
joins. Keep generated reference code/notices isolated and out of the Rust graph.

## ADR-0057: Preserve queue identity on save and cut it on load

Status: Accepted for research, 2026-10-09.

Worker research exposes unnecessary save-only evidence loss under ADR-0056.
Use the existing serializer reading flag: saving leaves live sidecar identities
unchanged; loading clears them. Actual-container baseline/disabled/repeated state
and object size remain equal; save-only token 521 survives while the restored
entry remains unknown. This is a finite continuous-execution improvement, not
sidecar persistence or cross-load identity. Historical worker receipts retain
their earlier policy and scope. Five identity/validity/movement forgeries fail.

## ADR-0058: Join accepted PI requests through exact CPU dispatch scope

Status: Accepted for research, 2026-10-09.

New worker research separates immediate PI data effects from later queued status
callbacks. Original opt-in request boundaries snapshot the accepted I/O context
before insertion/copy; successful external queue tokens join through valid removal
and an explicit scope around the actual CPU callback. Five component cases cover
both request directions, cancellation, failed insertion with successful writes,
unbound queue entries and direct status invocation. Original/disabled/repeated
reported checkpoints agree, and six forged joins fail. Copy effects need no
successful queue insertion; status association requires exact dispatch identity.
This is finite reference component evidence without guest instruction/MMIO
execution or hardware timing. Keep canonical byte origins, restore identity,
boot schema promotion and executable lifetimes separate; v1 inspection still
certifies no transfer completion. Generated reference code/notices stay isolated.

## ADR-0059: SP transfer identity must follow actual descriptor lifecycle

Status: Accepted for research, 2026-10-09.

Recovered worker component/source evidence reproduces locally at the exact pins.
Pinned ares permits pending SP DMA address/length mutation while FULL; a length
commit therefore does not freeze an immutable request. Current-to-pending handoff
occurs within the finishing step with BUSY still asserted afterward. Bind an
ares request at actual promotion or retain all pending mutations; group count/
skip rows and represent modulo-bank destination spans explicitly. Mupen/Gopher
source instead snapshots pending descriptors and rejects a third FULL push.
Preserve that hardware-unresolved disagreement; do not make ares overwrite policy
a native invariant. Only ares component execution is validated here, without
general CPU/RSP scheduling, save/restore identity or whole-ROM closure.

## ADR-0060: PIF firmware origins require actual backing reads inside fetch scope

Status: Accepted for research, 2026-10-09.

Recovered optional PIF sensor evidence reproduces locally with an original image
and the known supplied NTSC firmware. Bracket the existing actual CPU fetch stage
and sense only the successful unlocked PIF-ROM backing branch. Nine adversaries
preserve reported baseline/repeated state while distinguishing mirrored physical
addresses from masked source offsets; equal-valued latch/RAM, lockout, cached
rejection and stale/non-fetch reads supply no firmware witness. Reference source,
firmware and generated builds stay isolated/ignored. This establishes a bounded
reference source contract, without full instruction/boot execution, firmware
authenticity, immutable lifetime or ProgramMap promotion. A future schema must
retain the declared input digest/device namespace separately from fetch address.

## ADR-0061: Concrete CPU mutation sensing must include COP1 stores

Status: Accepted for research, 2026-10-09.

Recovered SWC1/SDC1 evidence reproduces locally: 100,000 payload-model cases and
192 repeated actual ares handler cases preserve FR-sensitive raw source bits,
cached/backing distinction and fault nonmutation. Sense general successful CPU
cache/backing mutations below opcode-specific handlers; integer-only coverage
cannot prove executable immutability. FPR indices require FR/lane context or
normalization to actual payload bytes. Mupen/Gopher source exposes two Word writes
where ares uses one Dual write; preserve observed ordering without inferring
hardware transaction count or atomicity. This is pinned handler evidence, with
forced endian-context and combined-fault limits, not a complete mutation census,
second-reference execution, executable lifetime or whole-ROM certificate.

## ADR-0062: EBus HiddenRAM words are derived bits, not copied instruction bytes

Status: Accepted for research, 2026-10-09.

The recovered exact-header probe reproduces all 65,536 hidden-byte pairs: a Word
is derived from two two-bit fields, with only 16 possible values. Ordinary RAM
byte origins cannot describe that transform. Require an actual source-specific
read within fetch scope, retain mapped hidden offsets and transformation inputs,
or keep the source unknown. The compiled header/source/model evidence is PARTIAL
for full fetch provenance and does not establish hidden-storage epochs, restore
lineage, hardware correctness or an executable-image identity policy.

## ADR-0063: Resolve uncached TLB fetch origins per actual fetch context

Status: Accepted for bounded production replay, 2026-10-11.

The recovered full ares TLB fixture reproduces the exact worker receipt. Extend
the finite identity-RDRAM scalar/fetch join only for an actually resolved uncached
access. Retain virtual PC, current translated address and post-endian bus address;
equal-valued virtual aliases and TLBWI remaps are different contexts. Failed
translations and cached mappings provide no scalar-fetch witness. CCA 2/3 routing
is pinned ares evidence, not an N64-wide hardware assertion. Mapping generations,
TLBWR/restore, broader page/mode cases and exhaustive reachability remain open.
Original fixtures generate ignored licensed reference builds; no emulator code
or asset enters production. No ProgramMap or closure gate changes.

Production tlb_fetch now retains one exact completed ordinary-RDRAM Word read
inside the same mapped uncached fetch context. Recompute translated and
post-endian bus addresses from the supplied selected mapping; match the actual
transaction address and delivered word. Invalid halves, ASID/global mismatch,
cached mappings, missing/ambiguous reads and equal-valued outside reads cannot
supply a witness. Mapping/context labels remain opaque, not authenticated
operation generations.

Reuse ADR-0107's strict executed 4-/16-/64-KiB geometry. Malformed masks remain
unsupported even when the pinned emulator normalizes them to an exercised size.
Require architectural PFN bases with zero low12 bits; an arithmetically matching
forged base/read cannot replace a realizable mapping. Nonzero regions and
large-page reverse-endian combinations stay outside the retained evidence scope.
Authenticate all source bytes externally and reconstruct every report field.
All sensor/mapping/context/residency/lifetime/closure/native flags remain false.

## ADR-0064: Translated RDRAM raw origin and delivered transform are distinct

Status: Accepted for research, 2026-10-09.

The recovered actual Word scalar fixture reproduces six witnesses and both
stochastic values exactly, with original/disabled/enabled reported state agreement.
A completed read at translated backing/chip supplies raw byte origin; request
address identifies routing, and CCI supplies a separate delivered-value transform.
Never substitute request-address RAM or equal payload for the actual source.
Failed mapping, inactive RI, identity and EBus paths supply no translated witness.
Other widths, bursts/writes, actual fetch composition and degraded executable-image
identity remain open. Original project-owned sensor code generates isolated
ignored reference shadows with preserved upstream licensing; no production
emulator dependency or ProgramMap/closure change is introduced.

## ADR-0065: Writeback exports the entire outgoing resident line

Status: Accepted for research, 2026-10-09.

The reproduced guest eviction fixture overwrites an externally changed clean
lane with its older resident bytes before filling the replacement. Dirty mask
is not writeback span; current RAM and post-replacement slot state cannot recover
the outgoing source. Preserve per-byte resident origin/generation and capture
actual full backing transactions in writeback scope before retag/reuse. Exact
model/evidence hashes and reported baseline/repeat checkpoints agree locally.
This finite original fixture keeps generated upstream builds/licensing isolated;
full lineage verification, arbitrary stores/epochs and closure remain open.

## ADR-0066: Executable mutation width follows the concrete device sink

Status: Accepted for research, 2026-10-09; bounded production verifier, 2026-10-11.

The reproduced CPU-to-SP-IMEM fixture proves that successful SB/SH can overwrite
four bytes with shifted unmasked rt.u32; nominal opcode width/payload truncation
would lose both mutation span and source bits. Record post-translation/endian
concrete sink address, full aligned Word effect and exact payload. Faulting odd
SH supplies no mutation. Pinned systemtest/Gopher source agrees; Mupen masked
source disagrees, so preserve the oracle conflict. Forced endian/component tests
and source expectations do not replace physical hardware evidence or prove other
sinks/lifetimes. Original fixture builds ignored licensed ares separately; no
reference code or assets enter production.

Production `cpu_sp_subword` now verifies one independently authenticated
decoded SB/SH context against a completed SP Word effect. Preserve exact
context/effect ordinals, architectural GPR0, aligned instruction PC, signed
effective address, separately supplied translation, endian lanes, bank/offset
and unmasked low32 payload. No observed effect supplies no writer. This bounded
8-KiB-aperture primitive does not authenticate the caller's history/mapping,
infer ultimate register ancestry or prove writer uniqueness/completeness,
executable lifetime or native closure. Broader mirrored/device paths remain
unsupported. See the primary takeover receipt for source and local validation.

## ADR-0067: D-cache lineage needs resident mutation revisions and exact scope

Status: Accepted for bounded production replay, 2026-10-12.

The recovered previously PARTIAL fixture now executes locally: actual explicit
writeback/dirty eviction export two full-line resident certificates; clean
replacement and dirty invalidate/drop export none. Track generation plus every
successful resident mutation revision. A same-value store after writeback begin
changes origin even when payload equality survives. The primary measured reducer
now rejects that stale snapshot and five additional chronology/sink forgeries.
Require one exact nested backing write and pre-replacement resident origin;
dirty alone cannot establish transfer. Original generated shadow sources remain
ignored/licensed separately. The finite aligned-store fixture does not establish
all store families, restore epochs, full provenance completeness or ProgramMap
closure, and is not transplanted into the production solver.

Production dcache_writeback now reconstructs fill generation, every resident
Word mutation revision and per-byte origins from externally authenticated finite
history. Only an exact successful 16-byte backing write nested in the same
writeback snapshot exports those origins. Dirty invalidation/drop retires
unexported resident origins; a clean equal-payload replacement exports nothing.
Same-value intervening mutations still change revision and invalidate an old
pending snapshot.

Within this declared direct-KSEG0 identity scope, require the supplied slot to
match the low physical line-index bits. This does not authenticate an arbitrary
virtual index or justify TLB/alias extrapolation. Original cached-store operand
ancestry, collection completeness, cacheability, other store families, restore/
reset epochs, executable lifetime and whole-ROM/native closure remain separate.
The report reconstructs all fields and retains broader flags false.

## ADR-0068: RSP data-store addresses do not use the CPU SP bank selector

Status: Accepted for research, 2026-10-09.

Recovered original in-progress code now passes 28 actual decoded scalar/vector
probes, with 27 DMEM mutations and one required aligned-SRV no-op; every IMEM
byte remains unchanged. Exact source and independent Gopher/systemtest guards
support the separate DMEM address domain. Do not transfer CPU bit-12 IMEM routing
to ordinary RSP store handlers. DMEM-to-IMEM CPU/DMA copies and external mutations
still need separate provenance. This original fixture compiles ignored licensed
ares without patching it; bounded/source evidence is not general hardware/lifetime
or closed-world proof.

## ADR-0069: Boot PI status identity comes from actual request/queue dispatch

Status: Accepted for research, 2026-10-09.

Original optional history v2 now composes accepted PI IO scopes, actual queue
identity and CPU dispatch with complete buffered-source effects. The 610,000-call
prefix adds only 55 records and preserves every prior v1/v0/v5 byte/checkpoint.
Four requests receive tokens 6..9; three statuses are bound to actual valid-removal
and CPU dispatch of tokens 6..8. Request 4 remains without an observed status.
Do not infer identity from last copy, event/deadline equality or successful data
effects. Keep legacy v1 status metadata unchanged and independently scoped.

Twelve synthetic/four actual identity forgeries fail, complete final scheduling
replay passes, and the original strict Rust v1 report hash is unchanged. V2 is
research-only and rejected by that CLI. Implement an original strict complete-
source Rust v2 consumer/rechecker before exposing production evidence; no native,
transfer/lifetime or whole-ROM completion flag is promoted. Generated reference
sources retain licenses in ignored builds; no reference implementation or asset
enters production.

## ADR-0070: V2 inspection rechecks actual scheduling and every nested source

Status: Accepted for finite inspection, 2026-10-09.

An original streamed Rust adapter validates typed accepted requests, queue slot
identity moves/outcomes, immediate valid-removal/dispatch and copy/status joins.
It rejects new scheduling rows inside raw fetch/copy intervals before projection.
The unchanged v1 inspector then verifies buffered ROM origins, identity-RAM
effects and exact nested v0/v5 sources with supplied ROM/firmware. Complete report
rechecking binds every field and the raw source, including unused payloads.

Full retained-prefix inspection/rechecking reproduces all independent scheduling
facts and the entire prior v1 report. Six original adversarial integration tests
cover unknown, canceled, rejected, save/load, read and direct-handler boundaries.
This replays observed identities, not full heap contents, hardware transfer timing,
guest-suite completion or executable lifetime. Requests without observed status
are not a live-queue census. Keep every native/guest/transfer completion flag false;
no ProgramMap/solver behavior or reference runtime dependency is introduced.

## ADR-0071: Observed byte chains precede executable lifetime certification

Status: Accepted for finite inspection, 2026-10-09.

A separate original Rust report now replays the validated complete v2/v5 sources.
It retains raw PI writer ordinals and snapshots byte chains only through actual
adjacent identity-RAM burst/fill or unambiguous uncached read contexts. Backing
writes cannot retroactively replace resident cache history; ordinary scalar/burst
writes remove earlier PI chains even for equal payloads. Tag/invalidating/unknown
transitions fail closed. Separate source digests reject changes during replay.

Independent full-prefix Python replay agrees with all 185 samples and 10,954
PI-attributed fetch observations. Sample endpoints remain discrete observations;
unobserved same-value mutations cannot be excluded by value equality. Keep
mutation-coverage, executable-lifetime and native flags false and leave ProgramMap
and solver unchanged. Actual SP/PIF sources and their producers remain separate.

ADR-0071 composition follow-up (2026-10-12): reuse the same byte-chain engine on
complete v3 SP/PI sources after canonical SP/queue/PI/access/fetch validation.
Require independently expected raw v3/v5 digests and reject changes between
validation and replay, including SP rows unused by the RAM-chain engine. Keep
raw v3 ordinals; never substitute renumbered v2 projection ordinals. A typed
report retains the complete SP projection and false census/lifetime/native flags.
SP observations do not invent RAM origins. Existing v2 format/report bytes stay
compatible. Cached/uncached raw-clock contracts, forgeries, full local gate,
retained610k v2 report recheck and independent100k v3 replay pass. Larger20m
chain replay is pending; no native readiness or milestone promotion. See the
SP/PI fetch-clock integration receipt.

ADR-0071 actual-source follow-up: full20m v3/v5 Rust replay and independent Python
replay now agree on every field/sample/source/ordered digest.2472203 full
candidate fetches/172 samples/27 fills begin at the ROM entry: ROM0x1000,
four distinct raw PI byte writes and fill58083773 at cached RAM0x400. The prior
entire primitive projection is unchanged. Record this storage/install/residency/
consumption composition without promoting ultimate ancestry, mutation coverage,
continuous executable lifetime, whole-ROM or native closure. No Rust/CLI change,
new reference build or milestone. See the installed-entry receipt.

## ADR-0072: CPU SP fetch identity requires the actual bank read result

Status: Accepted for finite reference sensing, 2026-10-09.

The original controlled sensor observes the existing completed `RSP::readWord`
result, normalized `RSP::writeWord` effect and direct SP-DMA storage sinks in
generated separately licensed reference shadows. Physical mirrors remain raw
addresses; bank bit 12 and aligned modulo-bank offset identify backing. Cached
SP access and status IO cannot inherit a backing witness from their addresses.

Eighteen actual CPU steps preserve every independent baseline/disabled/repeated
checkpoint and full reported state. Twelve fetches have exact read contexts;
equal stores retain distinct events and SB records a full-word sink. Three DMA
stores pair to actual RAM receipts without inventing ultimate source lineage.
Seven measured-history forgeries fail. Compose these results into boot chronology
before introducing a strict Rust consumer. RSP DMEM writes and general producer,
reset/restore, mutation census and executable lifetime remain open; no reference
code/runtime dependency, asset or native-complete claim enters production.

## ADR-0073: SP backing events extend chronology without replacing old sources

Status: Accepted for finite research composition, 2026-10-09.

Original optional access-history v3 emits completed SP bank reads/normalized CPU
and DMA stores on the existing ordinal. Its strict projection restores every v2
raw context and exact prior source byte; old versions keep their formats/policies.
The 10,000-call experiment preserves independent unchanged-reference/disabled/
enabled/repeated state, all v2/v1/v0/v5 sources and 7945 exact SP-backed fetches.
Missing/ambiguous/foreign/cached reads and stale DMA source receipts stay unknown.

Bank/offset identifies the observed backing only. No ROM/firmware producer,
RSP DMEM mutation census, executable lifetime or whole-ROM closure is inferred.
Full-prefix verification and original strict Rust consumption precede broader
promotion. Generated pinned-reference sources/licenses/assets remain ignored;
no reference implementation enters the final native path.

## ADR-0074: Strict v3 inspection binds finite SP observations to nested sources

Status: Accepted for finite inspection, 2026-10-09.

An original typed streaming Rust adapter validates actual SP backing rows and
raw fetch contexts before projecting into the unchanged strict v2/v1/v0/v5
consumers. Full source rechecking binds each sample, normalized store receipt,
raw digest and complete nested report. Missing/ambiguous/foreign/cached reads
stay unknown; DMA receipts cannot cross an unrelated event.

Independent smaller-prefix Python evidence agrees on every finite fact/digest;
full-prefix Rust inspection/rechecking also passes. Three original adversarial
integration tests cover raw source and report binding. A bank read is current
backing identity only; store receipt matching is not ultimate byte origin or
DMA timing/lifetime proof. Keep all certification flags false and leave the
ProgramMap/solver unchanged. No reference runtime dependency is introduced.

## ADR-0075: PIF-ROM read identity and write attempts are separate observations

Status: Accepted for finite research composition, 2026-10-09.

Actual PIF ROM reads extend access-history v4 while preserving the exact prior
v3/v2/v1/v0/v5 sources. Only an existing matching read within the uncached fetch
interval supplies offset identity. Address/value equality cannot supply that
witness for latch, lockout, RAM or cached paths.

The actual write probe falsified writable-ROM assumptions: pinned ares uses
Memory::Readable and its delegate is a no-op. Retain delegated attempts as a
distinct record kind; never infer backing effects from their payloads. Thirteen
actual component adversaries preserve independent reference/disabled/repeated
state and unchanged ROM backing. The smaller boot prefix also preserves all
previous sources/checkpoints. No reference code, runtime dependency or asset is
added to production; producer completeness, lifetime and native closure stay open.

## ADR-0076: Strict PIF reports bind complete finite sources

Status: Accepted for finite inspection, 2026-10-09.

An original typed streaming v4 Rust adapter validates raw PIF read/attempt kinds,
normalized payloads and actual fetch contexts before complete unchanged nested
v3/v2/v1/v0/v5 verification. Every sample, attempted write, raw digest and nested
report is rebuilt during source rechecking. Three adversarial integration tests
and full-prefix independent Python/Rust comparison pass. Attempts confer no
mutation, and firmware equality is distinct from current backing identity.
Keep mutation/lifetime/native flags false and ProgramMap/solver unchanged.

## ADR-0077: RSP primitive sinks require actual instruction contexts

Status: Accepted for controlled research sensing, 2026-10-09.

An optional generated RSP sensor brackets existing interpreted instruction
prologue/epilogue scopes and observes completed primitive DMEM stores. Thirty
actual scalar/vector probes preserve independent reference/disabled/repeated
state and replay every sink. Same-value effects remain distinct; out-of-instruction
sinks cannot inherit RSP identity. The first 29 prior results remain exact.

Record actual initial backing bytes: the reference fill helper uses a host byte
pattern, so a guest-endian numeric-fill assumption failed. Primitive counts are
not atomicity or complete mutation/lifetime proof. Generated ISC-reference
shadows and required notices remain ignored; production gains no reference code
or runtime dependency.

The controlled CPU refetch composition now passes independent reference/
disabled/enabled/repeated checkpoints, including partial/vector and same-value
effects. Preserve each measured byte writer; an unmatched foreign sink cuts
only its touched bytes to unknown. In this synchronous fixture, a completed
CPU SP Word callback supersedes the exact preceding matching low-level sink.
This finite rule is not a general asynchronous producer correlation or census.
Payload replay alone fails causal adversaries. Ultimate producer dataflow,
complete-history integration and executable lifetime remain separate gates.

## ADR-0078: Static closure requires consistent executable identities

Status: Accepted, 2026-10-11.

Reproduced the static integration-prep cluster against current `main`: seven
adversarial families falsely closed. Before finite-static closure, authenticate
content-derived image IDs, require single-valued words at each execution identity,
reject distinct decoded guest/known physical ownership without a selector proof,
and recheck simultaneously-known affine Region and selected CodeImage provenance.
Equal bytes establish neither common provenance nor lifetime. Unknown metadata
stays unknown; generation labels alone create no lifecycle chronology. Opaque
legacy image labels and canonical-ROM source authentication remain separate API
obligations. Preserve the nine consolidated tests and reject the superseded
physical-only, generation-order and cross-fragment proposals. No upstream code
is reused; the existing exact MIT Rabbitizer dependency is unchanged. Whole-ROM
closure and native completeness remain unproved.

## ADR-0079: Trace operation identity and reusable context have distinct roles

Status: Accepted, 2026-10-11.

One concrete trace event cannot fork primitive semantics or cross DMA/store/
indirect/verification/source-unit roles. Explicit compilation-unit context may
be shared and propagated into provenance; generic derived-fact provenance is
not globally unique. Consolidate role checking in ProgramMap validation. Keep
source authentication in a separate complete-DiscoveryTrace verifier, replaying
epochs and exact primitive projections and optionally re-importing installed
entries. Do not parse evidence prose or join by equal bytes. The primary's
additional positive control falsified the prep rechecker's treatment of shared
source-unit provenance; the same explicit-context exemption now composes across
both layers, with independent source-unit metadata checks. Global uniqueness
and Region-membership source binding are rejected. No upstream code is reused.
Source authentication proves neither sensor completeness nor whole-ROM closure;
future positive certificates must require an appropriate verified-source input.

## ADR-0080: Primitive facts survive deletion of derived diagnostics

Status: Accepted, 2026-10-11.

Re-derive closure blockers from retained successful stores, unresolved executed
indirect transfers, restricted verified entries, post-invalidation verification
epochs and raw fetch captures. The immutable integer scope excludes successful
memory effects even when the destination is nonexecutable or unknown. Physical
write overlap needs explicit Region backing; missing mappings are not guessed.
Indirect correlation needs one event-linked source/target identity; shared typed
unit context is separate and cannot replace the event. Correlation remains a
structural consistency check, not source authentication. Verification epoch and
code generation are separate clocks. Empty capture counts/prose supply no source
verification receipt. Full source/expected-manifest and lifecycle completeness
remain separate obligations. No upstream implementation is reused.

## ADR-0081: Target dispatch is a retained primitive, not an executed edge

Status: Accepted, 2026-10-11.

Retain typed TargetLookup and RuntimeLink observations independently of removable
diagnostics. Preserve kind, delay-slot-entry context, epoch and exact event
provenance through merge. Block source-uncorrelated dispatch in the solver even
when a static certificate names the same numeric target. Extend the common
primitive role/source-projection checks to dispatch. Default/omit the additive
empty collection for legacy serialization. These finite observations prove no
source-site transfer, target lifetime or future execution completeness. No
upstream implementation is copied or linked.

## ADR-0082: Load and overlay provenance must agree with executable Regions

Status: Accepted, 2026-10-11.

Validate explicit physical Region alignment and span arithmetic independently
of guest spans. Require each load's exact image, generation, guest range and
known ROM offset to match an executable Region even without a copy event.
Require an overlay descriptor's referenced Region to match image, guest range
and ROM offset. Overlay generation remains a separate load/execution identity;
unknown physical backing is not inferred. Existing DMA/copy-event checks remain
additional obligations. This rejects contradictory metadata without proving
executable lifetime or source completeness. No upstream code is reused.

## ADR-0083: Fetch summaries must admit a concrete finite history

Status: Accepted, 2026-10-11.

Per-summary bounds, exact aggregate counts and interval coverage do not establish
joint consistency. Reserve each summary's first/last positions and schedule its
remaining quota strictly inside that interval using earliest deadlines over
endpoint gaps. Preserve existing value, endpoint and provenance checks. This
establishes existence of a consistent history, not agreement with a particular
raw capture; source rechecking remains independent. Prefer this stronger check
over the interval-union-only candidate. Independent assignment-oracle research
and an exhaustive bounded concrete-history test of the Rust validator agree.
No upstream implementation is reused; no lifecycle or closure proof follows.

## ADR-0084: Table candidates require the complete recognized guard path

Status: Accepted, 2026-10-11.

Withhold bounded table evidence when same-image/generation entry, direct or
indirect reachability bypasses the selected compare or dispatch prefix. A
standalone delay-slot entry bypasses the compare only when its sequential path
reaches the dispatch; a remote taken target is a separate case. Reject traps,
SYSCALL, BREAK and ERET in executed selected-edge slots using the pinned decoder
and existing CFG policy; preserve branch-likely annulment. Keep conservative CFG
edges. Table-content immutability and target executable identity/lifetime remain
separate unresolved obligations, even with a complete numeric snapshot. No
upstream implementation is reused and no exhaustive closure proof is added.

## ADR-0085: Later observed writers revoke an older executable DMA origin

Status: Accepted, 2026-10-11.

At first compilation, reject a covering DMA origin if a later successful observed
CPU word store or partial DMA overlaps the compiled physical span. Retain exact
writer evidence, with unknown executable source; equal snapshot bytes or a
matching supplied image cannot repair superseded provenance. A later complete
covering DMA supersedes earlier writers normally. Invalidation does not restore
an old origin. This composes retained primitive facts with import-time provenance
without inventing positive CPU-store or mixed-writer lineage. Sensor completeness,
cache residency and arbitrary executable lifetime remain independent obligations.
The bounded writer scan is unoptimized; no performance claim or upstream reuse.

## ADR-0086: Index merge contradictions by their existing exact identity keys

Status: Accepted, 2026-10-11.

Replace all-pairs block/edge conflict scans with groups keyed by block start or
(edge site, kind), preserving complete CodeAddress identity. A group with more
than one semantic signature retains all participating evidence in the same
canonical diagnostic. Preserve contradictory facts, not a selected winner.
The former pairwise rule is an independent test oracle; local release A/B
measurement reproduces the bottleneck and improvement. This optimizes only that
merge phase, not solver identity scans or complete-history processing. No proof
obligation, serialization contract or upstream implementation is changed.

## ADR-0087: Recheck bounded two-path indirect target certificates

Status: Accepted, 2026-10-11.

After local and single-chain analysis, allow exactly two acyclic root-to-site
paths whose independent scalar analyses derive the same canonical aligned
JR/JALR target. Rebuild CFG from current bytes and roots, require all path facts,
retain both path identities and digests, and reconstruct the certificate during
verification. Share path simulation with the existing chain prover without
widening its scalar/control whitelist. Reject excess paths, cycles, calls,
unsupported effects and unknown or divergent targets. A target certificate
cannot waive separate effect, final-delay-slot, source or lifetime obligations.
This expands only the declared immutable-image target analysis; whole-ROM and
native completeness remain unproved. No upstream implementation is reused.

## ADR-0088: Adjacent CPU-copy evidence requires architectural continuity

Status: Accepted for controlled research verification, 2026-10-11.

For the finite interpreted identity-RDRAM LW/LWU-to-SW contract, require exact
typed instruction/GPR/scalar histories, canonical aligned KSEG1 Word effects,
architectural load extension, full GPR continuity and sequential adjacent
captured PCs. Equal stored low bits cannot hide a changed register generation,
PC gap or cached address. Preserve failed-load, competing-source, same-value
clobber and NOP-gap negatives. A zero-register load is not a causal GPR writer.
Per-instruction reported-state checkpoints must agree with unchanged pinned
reference, disabled and repeated enabled runs.

The branch verifier accepted three new causal forgeries and is rejected as
written. Its reconciled original fixture uses optional shared-builder shadows;
upstream notices remain ignored and no reference implementation enters production.
This accepts only a controlled evidence primitive. Instruction callbacks miss
some early-return attempts, so complete source/attempt authentication and
executable consumption/lifetime must precede any production copy certificate.
No general dataflow or native closure gate is weakened.

## ADR-0089: Preserve explicit identity for bounded XORI transformations

Status: Accepted for controlled research verification, 2026-10-11.

Reuse the strict adjacent-copy instruction/scalar verifier under an explicit
XORI mode, requiring contiguous captured load/XORI/store contexts and exact
register def-use. Preserve source, transform and sink identities separately,
including XORI zero. Retain full architectural continuity, canonical uncached
Word effects and big-endian per-byte masks; ordinary copy mode excludes XORI.
The unmodified research verifier accepted three additional continuity/address
forgeries and is rejected. Per-instruction independent-reference checkpoints
and adversarial/equal-value controls precede acceptance of the bounded contract.

This is not a general transform algebra or complete execution/producer census.
Eventual executable consumption, lifetime and complete source authentication
remain required before production promotion. Original observer/shadow generation
is shared; upstream implementations, branch workflows and custom compiler
scaffolding are not imported into production. No native gate is weakened.

## ADR-0090: CPU SP producers require decoded context and normalized backing

Status: Accepted for controlled research verification, 2026-10-11.

Observe actual CPU decoder boundaries and completed SP Word writes. Derive the
operand selector and effective address from the captured instruction and full
GPR/FPR snapshots, including FR/CU1 mode. Require exact physical bank/offset and
guest-byte replay. An unscoped direct write cannot borrow a matching decoded
source, and a denied COP1 store must produce no sink. The unmodified research
verifier accepted selector/bank/bounds forgeries and is rejected.

Normalize snapshots through pinned guest accessors: generic IMEM host storage
and specialized RSP DMEM storage are different views. A primary host-order
snapshot error failed the initial-state gate; fix capture rather than loosening
verification. Preserve this pin's widened SB Word effects and FR-sensitive
SWC1 source selection as finite reference facts, not N64-wide hardware truth.
Independent unchanged-reference checkpoints include FPR bits. Ultimate register
ancestry, complete attempts/census, asynchronous execution and lifetime remain
separate obligations. No production/native producer gate is weakened.

## ADR-0091: Preserve source-byte and sink generations across CPU SP copies

Status: Accepted for controlled research verification, 2026-10-11.

Compose actual RSP DMEM effects with actual CPU LW/GPR/SW and completed IMEM
sinks under one chronology. Require full register continuity and decoded exact
virtual/physical bank bindings. Carry four source-byte writer identities apart
from the destination storage generation; mixed or unknown bytes stay mixed or
unknown. Equal-valued decoy loads cannot select a different source, and a
same-valued register definition cuts the old copy lineage.

The unmodified composition verifier accepted three additional high-GPR/address
forgeries and is rejected. The reconciled finite census retains adversarial
controls and independent unchanged-reference checkpoints. Original project
observers/fixture are shared; no upstream implementation or branch-only build
scaffolding is imported into production. A storage writer is not ultimate
register-input ancestry. Complete attempts/census, executable consumption and
lifetime remain prerequisites to production promotion; native gates stay open.

## ADR-0092: Cache visibility facts cannot substitute for measured ancestry

Status: Accepted for controlled research verification, 2026-10-11.

Retain the unmodified pinned-reference XORI/cached-store/writeback/refill fixture
with strict finite behavioral expectations. A completed backing write cannot
refresh a resident instruction line, and a refill made before writeback keeps
its earlier bits. A subsequent same-value writer cannot be identified from final
payload equality. Preserve identity-valued transforms as distinct instructions.

Review abstract generation replay separately from executed facts. Its accepted
oversized-immediate counterexample cannot satisfy main's actual decoded XORI
contract. Until one source-bound measured history connects register definitions,
cache residents/revisions, completed backing transactions and executable fetches,
leave ancestry, mutation coverage and lifetime uncertified. Reuse only the
project-owned ISC driver/shared builder; no upstream implementation or branch
workflow enters production. This finite reference fact does not establish
hardware truth or alter native/whole-ROM closure gates.

## ADR-0093: Preserve exact large-page remap behavior without certifying fills

Status: Accepted for controlled research verification, 2026-10-11.

Retain the unmodified 16-KiB/64-KiB PageMask/cache-remap fixture with strict
nested behavioral expectations. Fixed 4-KiB reconstruction cannot select backing
from equal payloads; temporary mapping/context unreachability is not resident
retirement. Preserve physical-tag/miss transitions apart from returned values.

The abstract branch hit verifier omits fill/writer/word checks on misses and is
rejected for production use. Actual fixture TLBWI calls and ASID/debugger writes
are staged directly, so they do not authenticate guest writer instructions or
mapping/fill generations. Source Gopher indexing disagreement stays unresolved;
no universal ares cache-index rule is adopted. Share only the original ISC
fixture/builder, keep upstream builds/notices ignored, and retain open census,
producer, cache/mapping/lifetime and native obligations.

## ADR-0094: PI completion cannot stand in for byte effects or cache visibility

Status: Accepted for controlled research verification, 2026-10-11.

Retain the actual two-transfer PI/cache fixture under strict complete finite
record expectations. A queued completion leaves stale cached instructions
executable; a synchronous copy can occur with a full queue and become executable
only after a later witnessed refill, despite absent completion. Preserve all
source halfwords, destination bytes, full backing/fill lines and fetch bindings.
The branch runner accepted source-tail, sink-tail and fetch-address forgeries and
is rejected as written. Baseline/disabled/enabled reported checkpoints precede
acceptance of this finite behavior regression.

Current Rust PI history already separates returned copies from observed status;
no lifecycle core patch follows. The fixture's last-pending label is not a queue
insertion token, and the reference model's extra same-value/restore cases are
abstract evidence. Keep those boundaries separate from a general source-bound
census, producer certificate or executable lifetime. Share original ISC fixture
and existing observer/builder code, retain ignored upstream notices, and import
no upstream implementation or branch-only CI/build scaffold into production.

## ADR-0095: Completed DMEM sink lanes require exact successful source identity

Status: Accepted for controlled research verification, 2026-10-11.

Retain the original ISC forward-DMA fixture with a strict typed finite census.
Pinned ares reads both source Words before either DMEM sink; nearest equal value
can therefore select the wrong lane. Keep each successful source transaction
and sink generation distinct, advance same-value reload writers and preserve
OOB unknown source identities. Count/skip and wrap follow completed fragments.
The original reducer's unchecked second-row payload/type/schema cases reject in
the reconciled verifier. Reported-state comparisons precede finite acceptance.

Successful source reads are not ultimate RDRAM storage ancestry. Direct component
DMA stepping and a staged CPU-visible Word write do not authenticate request
lifecycle or decoded CPU producers. Keep general census, RSP/CPU composition and
executable lifetime/native gates open. Generate original observer shadows only
under ignored output, preserve reference notices, and import no reference
implementation or branch-only CI workflow. Gopher's different interleaving is
source-only context; ares callback spacing is not a hardware invariant.

## ADR-0096: RSP data-store isolation is a bounded reference classification

Status: Accepted for controlled research verification, 2026-10-11.

Retain the unmodified decoded scalar/vector store fixture and strict per-probe
metadata/digest checks. All pinned interpreter store handlers target the
separate 4-KiB DMEM object; bit 12 and boundary wrap do not select IMEM. Actual
29-probe execution preserves each complete IMEM snapshot. Aligned SRV is a valid
zero-byte operation; its added nonaligned probe exercises the write path.

This classifies ordinary RSP data stores for the pinned interpreter/source
contract, not all executable mutations or hardware/recompiler behavior. Keep
CPU/SP-window writes, DMA, reset/restore/debugger/frontend changes and complete
task/lifetime census independently open. The old runner's unchecked instruction,
base and digest fields are superseded by strict typed report expectations.
Share only original ISC fixtures/audits and synthetic metadata; reference code
and notices remain ignored, with no branch workflow or upstream implementation
entering production/native mode.

## ADR-0097: Temporary ASID inactivity does not retire resident code

Status: Accepted for controlled research verification, 2026-10-11.

Retain the unmodified guest MTC0 EntryHi/cache fixture with complete typed finite
report expectations. At the pinned interpreter, context switches leave installed
entries and resident cache lines intact; a return can execute stale bytes after
backing changes. An unmatched-ASID fault does not fill or retire that line. Equal
payload at a different physical tag replaces it, allowing a later fresh refill.
Context reachability, mapping storage, backing and resident bytes therefore need
separate evidence; temporary inactivity alone is not a retirement boundary.

Do not turn selected facts, internal snapshot equality or miss counters into a
generation certificate. Direct setup/backing/reset operations do not establish
guest writer census. Preserve exact tags, counters and digest checks against the
old runner's accepted mutations. Keep Gopher's different cache-index policy
explicit and hardware/lifetime/native obligations open. Share original ISC
fixture/guards only; generated upstream code/notices remain ignored and no
reference implementation or branch workflow is imported into native mode.

## ADR-0098: Successful TLBR context loads differ from instruction occurrence

Status: Accepted for controlled research verification, 2026-10-11.

Extend ADR-0097's finite context/cache controls with actual decoded TLBR. At the
pin, successful TLBR loads staged EntryHi and can reactivate stale resident code
without replacing installed entries or cache contents. Same-value TLBR executes
despite snapshot equality. Out-of-range TLBR executes without a successful
context load; TLBP changes probe state without loading EntryHi. Preserve these
separate facts before designing a measured context-writer certificate.

Retain the original ISC fixture with strict typed report tags/counters/digest.
Internal installed/cache snapshots prove finite behavior rather than complete
state or history. Index/setup/reset/backing operations are staged, leaving
writer census and executable lifetimes open. Preserve independent reference
disagreements and import neither upstream implementation nor branch-only CI.

## ADR-0099: Consume validated CPU definitions through bounded Rust replay

Status: Accepted for compiler-time observed-history inspection, 2026-10-11.

Implement an original Rust consumer of the spike 044/045 CPU instruction/scalar
protocol. Bound successful producer witnesses to decoded LW/LWU, optional one
in-place XORI, and SW, with full GPR state and contiguous control/ordinal checks.
Retain actual read/write ordinals and distinguish XORI zero from no transform.
ORI/NOP cut the chain; failed loads and register zero supply no definition.
Reject unsupported operations/domains instead of guessing value-based lineage.

Require an externally trusted complete-source SHA and reconstruct every report
field when verifying it. This binds supplied records rather than authenticating
sensor completeness or source storage ancestry. Phase/segment boundaries cut
chains; they do not imply a complete execution census. Keep all general origin,
mutation/lifetime/native flags false and do not issue ProgramMap solver waivers.
Existing authenticated captures provide behavioral comparison without repeating
reference builds. No upstream implementation or native guest executor is added.

## ADR-0100: Track captured definitions independently of equal payloads

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-11.

Add a separate captured-definition protocol over ADR-0099's validated instruction,
GPR, control and Word-effect source. Preserve a loaded register's actual read
identity through unrelated loads/NOP and at most one in-place XORI. Advance a
definition on same-value reload; cut it on ORI, failed load and phase boundaries.
Do not choose a nearest equal-valued read or infer a source from value equality.
The original adjacent protocol and its inspection/rechecking behavior remain
separate and reject the new format.

This describes the supplied captured sequence, not every operation an executing
machine might perform. Unknown/unsupported operations reject; no arbitrary
dataflow, interrupt/capture completeness, ultimate storage ancestry, executable
lifetime or native waiver follows. Compare existing authenticated captures rather
than rerunning reference research. No upstream code or final guest executor added.


## ADR-0101: Exception roots are mode-sensitive candidates, not reachability certificates

Status: Accepted for bounded production root derivation, 2026-10-11.

Promote the independently reproduced 28-case R4300 exception-vector matrix into
an original typed resolver. General and TLB-invalid entries select base+0x180; a
true TLB miss with EXL clear selects base+0x000 in 32-bit kernel context or
base+0x080 in 64-bit kernel context; EXL set returns a miss to +0x180. BEV selects
`ffffffff80000000` versus `ffffffffbfc00200`. Keep TLB invalid distinct from a
true miss and retain vector class in the receipt.

The receipt is only a numeric root derivation from already-classified state. It
does not authenticate the exception classifier, BEV/EXL/address-mode writer
history, reachability, handler bytes, cache/mapping lifetime, or completeness of
execution roots. Delay-slot BD/EPC handling remains separate; interrupt/watch,
reset/NMI, cache-error and broader privilege/TLB cases remain OPEN. Exact pinned
ares re-ran byte-identically at integration; pinned n64-systemtest source
corroborates +0/+0x80/+0x180, while pinned Gopher64 lacks +0x80 and remains an
explicit disagreement. No reference code or runtime dependency enters production
and no solver/native-complete gate is weakened.

## ADR-0102: TLBWI operation generations follow observed write boundaries, not mapping inequality

Status: Accepted for bounded compiler-time observed-history replay, 2026-10-11.

Adopt a strict source-bound TLBWI begin/write/end replay. A successful in-range
decoded TLBWI boundary mints a fresh ordered operation generation even when the
before/after entry fingerprints are identical. Require the actual selected write
slot to equal the captured CP0 Index. Equal payload in another slot cannot select
or authenticate that operation. Out-of-range and exception attempts without an
observed successful write retain no-write receipts but mint no write generation.
An in-range successful end without a write, duplicate/fabricated writes, reordered
ordinals/epochs, mismatched contexts, wrong opcodes and malformed fingerprints or
schema fail closed. Bind the complete supplied source to an externally trusted
SHA-256 and reconstruct the entire report during verification.

Operation generation, selected-slot identity, mapping-content identity,
translation-context generation, cache residency and executable lifetime remain
separate facts. A content fingerprint is not a semantic mapping certificate, and
the finite supplied source does not certify sensor completeness. The fresh exact
pinned ares rerun at `9408cb43d4948fc3ea6e152a307a34348df3fe04`
reproduced result SHA-256
`6ef416a44a0fb533a1e291b8adab42b158f0eb581ec81a9174509b3d6ab606e0`
and the independent 20,000-case model SHA-256
`8c0350d8f1604b6935fcf68b0a148bb7688aaf1629355490b56816a7e7dee868`.
TLBWR, TLBP/TLBR, PageMask/ASID/global chronology, complete mutation census,
cache/mapping/lifetime composition and whole-ROM/native-complete proof remain
OPEN. No reference implementation code or runtime dependency enters production,
and no solver/native-complete gate is weakened.


## ADR-0103: BEV=1 PIF root provenance requires same-fetch backing identity

Status: Accepted for bounded production source composition, 2026-10-11.

Compose the typed exception-root candidate with the existing strict PIF v4 source
replayer only for the validated BEV=1, EXL-clear, 32-bit-kernel general vector at
`ffffffffbfc00380`. A supplied-PIF source receipt requires one caller-selected
fetch sequence that survives complete-source replay as exactly one singleton PIF
backing observation at physical `1fc00380`, normalized PIF offset `0x380`, with
the fetched Word matching the supplied firmware. Retain the exact fetch sequence,
backing-read ordinal, complete history digest, ordered fetch/backing digest and
supplied-firmware digest. Recompute the receipt from all original sources when
verifying it.

Do not infer provenance from vector address, returned bits, a prior/latest equal
PIF read, physical/masked-offset equality or a coalesced repeated sample. The
validated SI-busy-latch case executes identical bits at the identical root with
no PIF-ROM backing read, so missing same-fetch evidence remains UNKNOWN. Repeated
identical backed observations are conservatively rejected until production keeps
per-occurrence identity. This authenticates one observed handler fetch source; it
does not prove exception occurrence/classification chronology, BEV/EXL/mode
writer completeness, BEV=1 refill/XTLB behavior, PIF lifetime/authenticity,
cache/mapping executable lifetime, root census, whole-ROM closure or native
completeness. No upstream implementation or runtime dependency enters production.

## ADR-0104: Cached exception roots require resident-generation evidence

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
ADR-0103's BEV=1/PIF root provenance is complementary: it authenticates a supplied
PIF-backed fetch, while this decision authenticates which captured resident/backing
generation supplied one cached BEV=0 root word.

The accepted primitive does not certify source-sensor completeness, exception
reachability, ultimate storage ancestry, arbitrary cache operations, aliases/TLB
mappings, save/restore/reset behavior, the rest of the handler span, mutation or
root census completeness, executable lifetime, hardware-wide semantics, whole-ROM
closure or native completeness. Missing evidence keeps those obligations OPEN.


## ADR-0105: PI interrupt producer provenance follows completion and poll operations, not copied bytes

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-11.

A PI byte copy/request is not evidence that queued completion occurred. Only an explicit completion observation mints a completion generation and may become raw MI.PI producer ancestry. MI mask writes are distinct poll operations even at the same value; interrupt clear lowers the raw line and cuts older completion ancestry. Restore boundaries cut raw-line and mask ancestry to UNKNOWN rather than reconstructing them from equal-looking state. CPU RCP-pending is certifiable only when raw producer ancestry plus observed mask state justify it.

Bind the complete supplied history to an externally trusted SHA-256 and reconstruct the report during verification. Reject PI-copy/payload fields, reordered ordinals, zero/reused request or token identities, deleted source history and report mutation. Do not import emulator queue-capacity/scheduling details as hardware truth or infer producer identity from latest request, equal payload, final state or numeric vector address.

This primitive stops before CPU Status IE/IM/EXL/ERL eligibility and BEV root transfer. Source-sensor completeness, hardware timing, request-to-completion instrumentation coverage, other producers, handler bytes/cache/mapping lifetime, reset/save/restore chronology beyond explicit cuts, interrupt/root census, whole-ROM closure and native completeness remain OPEN. Existing PI queue/fetch evidence is complementary and keeps guest completion unclaimed unless independently evidenced.

## ADR-0106: Maskable boundary eligibility is separate from root provenance

Status: Accepted for bounded production candidate selection, 2026-10-11.

At one independently authenticated boundary, require an enabled pending bit,
IE set, EXL clear and ERL clear before selecting the existing BEV-sensitive
General exception vector. Preserve all normalized Cause.IP/Status.IM input bits
and their exact intersection. Recheck a serialized receipt by reconstructing it
from independently supplied state; a receipt's own edited state, equal numeric
vector or pending bits alone cannot substitute for that input.

The retained 32 actual ares cases support this bounded gate without new reference
builds. Source-only Gopher agreement is supporting context, not hardware-wide
proof. No upstream implementation enters production. This primitive does not
prove producer/status writer chronology, actual transfer, root reachability or
exclusion, handler byte provenance/lifetime, asynchronous priority, complete root
census or native closure. Compose those obligations explicitly; no solver waiver.

## ADR-0107: Selected-mapping geometry must retain the validated PageMask

Status: Accepted for bounded production derivation, 2026-10-11.

For an independently selected mapping, exact raw masks `0`, `6000`, `1e000`
select 4-/16-/64-KiB halves and corresponding offsets. A fixed virtual bit12 or
low12 offset rule can choose a valid equal-valued decoy when the actual large-page
half is invalid. Preserve the PageMask-specific geometry and reconstruct every
receipt field from independently supplied mask/address before accepting it.
Malformed masks and larger model-only page sizes stay unsupported in this version.

The saved actual mapped-fetch and cache-remap captures support this bounded
derivation without repeated reference builds. Keep actual translated/bus addresses
in access provenance rather than replacing them with geometry guesses. Geometry
does not select/authenticate an entry, mint mapping generations or prove ASID,
global/region/valid/dirty/CCA, backing bytes, cache residency, lifetime or complete
executable coverage. No upstream implementation or solver/native waiver is added.

## ADR-0108: Guest Cause writes produce only software pending generations

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-11.

An observed successful guest MTC0 Cause write replaces IP0/IP1 and preserves
IP2..IP7 as separately produced state. Mint a fresh operation generation for
every successful write, including unchanged pending bits; a faulting attempt
has no successful effect. Require decoded instruction context, matching raw
operand/pre-state, one actual effect boundary and completed instruction identity.
Architectural source register zero must supply zero.

Authenticate all typed source bytes against an externally trusted digest and
reconstruct every report field during verification. Reject omissions, reordered
or duplicate boundaries, operand/context decoys and edited certification flags.
Hardware changes between independent attempts do not imply guest Cause ownership.

The saved 21 actual ares state rows support the producer relation and independently
evaluated next-boundary gate. Their adapted protocol ordinals are synthetic, and
the reference driver stages Status.IM between boundaries: neither proves sensed
guest writer chronology. Exact pinned Gopher/Mupen sources support the ownership
contract; no upstream implementation enters production. Raw operand ancestry,
complete sensor coverage, hardware/timer producer semantics, interrupt chronology,
handler source/lifetime, root census and whole-ROM/native completeness remain
OPEN. All corresponding report flags remain false; no solver waiver.

## ADR-0109: TLBWR identity follows observed selection and matching write

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-11.

Retain an explicit selection boundary and require a subsequent actual write to
that exact selected slot in the same decoded TLBWR context. A successful write
mints a fresh generation even when before/after content matches. CP0 Index,
payload equality, snapshot differences and later translations cannot name the
replacement slot. Faulting attempts mint no writer.

Reconcile the two prepared candidates on their shared stronger contract: keep
selection/write correlation and require validated Wired <32 with selected slot
in [Wired,31]. Broad out-of-range model behavior stays unsupported. The primary
regression reproduced acceptance of a slot below Wired in the selection candidate
before adding the narrower candidate's guard. Complete source hashing and full
report reconstruction remain mandatory; preserve opaque content fingerprints
without claiming normalized mapping semantics.

Saved ares state facts establish the equal-value/snapshot/Index counterexamples
and the controlled range cases. Adapted protocol ordinals/fingerprints are
synthetic, not sensed callbacks or mapping ancestry. Exact source ordering is
supporting reference evidence, not hardware Random distribution. No upstream
implementation enters production. Sensor completeness, CP0/TLB census, mapping
semantics, context generation, cache residency, reset/restore lifetime,
whole-ROM closure and native completeness remain OPEN; broader flags false.

## ADR-0110: Captured CPU-copy writers are chronology candidates, not ultimate ancestry

Status: Accepted for bounded compiler-time observed-history inspection, 2026-10-12.

Reuse the strict adjacent-copy and live-definition source verifiers, then version
each captured successful Word store, including same-value and non-copy stores.
Retain a phase-scoped writer identity at later source reads and the copy's own
destination generation. Forward overlap can consume prior captured destination
writes; backward and equal-payload histories retain different chronology.

A read that contradicts a captured writer's value cuts that candidate to UNKNOWN.
Later equal bits cannot resurrect it; a fresh captured write is required.
This guard was reproduced against the prepared code before integration.
Clear captured writer state at phase boundaries and reconstruct every report
field from externally authenticated source bytes.

Even a compatible last captured writer does not prove ultimate read ancestry
without an independently complete mutation history. Source ancestry, mutation
census, cached/TLB/device/RSP/DMA interleavings, executable lifetime and native
completeness remain uncertified. Existing copy report formats/CLI and closed-world
gates remain unchanged. No upstream implementation or solver waiver is added.

## ADR-0111: Conditional SP writers require the completed sink and pre-store context

Status: Accepted for bounded compiler-time effect normalization, 2026-10-12.

Normalize a Word SC mutation only from an independently observed CPU-origin SP
Word sink joined to the exact decoded pre-instruction context. Reuse the existing
conditional-store decoder; retain pre-store GPRs because SC overwrites its source
register with the result. Check architectural GPR zero, aligned PC, ordered
context/effect identities, direct KSEG1 translation, SP bank/offset and payload.
Successful same-value sinks are distinct writer occurrences. Absence yields no
witness and never proves complete observation or why a reservation failed.

Reconcile prepared SC/SP candidates at this sink boundary. Do not import the
duplicate history model's reservation boolean as a reservation-policy proof.
Exact pinned ares saved captures support four successful sinks, four no-sink
attempts and an equal-value out-of-context decoy. Gopher source corroborates
conditional storage but differs in reservation handling; no upstream code enters
production. Source authentication/completeness, GPR ancestry, other mutation
families/aliases, reservation and executable lifetime, whole-ROM closure and
native completeness remain OPEN. No solver or progress milestone change.

## ADR-0112: Timer acknowledgement is an operation, including same-value Compare writes

Status: Accepted for bounded compiler-time observed-history replay, 2026-10-12.

Preserve every supplied successful Count/Compare operation as a fresh global
and per-register generation. Compare writes clear latched timer pending even
when the value is unchanged; Count writes cannot acknowledge it. Require an
explicit observed false-to-true assertion and exact before-state continuity.
Authenticate all source bytes externally and reconstruct every report field.

The schema consumes already observed primitive operations, not decoded guest
contexts or an event scheduler. It has no elapsed-time event; unexplained Count
progression rejects. Count-write generations do not count free-running ticks.
Pinned ares/Gopher/Mupen sources differ on Count rewrite scheduling, so that
timing remains unresolved. Saved exact-ares checkpoint facts support the bounded
operation contract and canonical boundary gate, not sensed event chronology or
hardware-wide timing. No upstream code enters production. Primitive capture
authentication/completeness, timer epochs, interrupt-gate chronology, handler
source/lifetime and whole-ROM/native completeness stay uncertified; no solver
waiver or milestone promotion.

## ADR-0113: Expected source sets must survive outside editable discovery artifacts

Status: Accepted for explicit source-available primitive verification, 2026-10-12.

Keep a versioned exact set of expected discovery-trace manifests independently
of the editable ProgramMap/source artifacts. Commit to canonical complete typed
NDJSON, ROM/producer and event count. Authenticate each supplied source against
that expectation, then reuse the canonical primitive projection rechecker.
Keyed union preserves independent commitments; a conflicting same-session
manifest rejects. Repeated JSON keys cannot choose a winner, and every retained
discovery-trace evidence identity must belong to an expected session/event.

Choose prepared source-available option B over a generic second semantic-root
schema without typed ProgramMap adapters. Primary regressions reproduced conflict
erasure by duplicate JSON keys and an unexpected map session bypass in the
prepared candidate before adding guards. Valid two-source map/manifest merges
continue to pass. Recomputing the expected set after an edit destroys the trust
boundary and provides no deletion resistance.

The API verifies currently modeled raw primitives. It does not replace stronger
entry/ROM-aware recheckers, authenticate other source domains, automatically
gate solver outputs, prove sensor coverage or determine the complete expected
set for a ROM execution model. Certificate-boundary wiring and those proof
obligations remain OPEN; no whole-ROM/native or progress milestone promotion.

## ADR-0114: Source-preserving closure admission composes expectations and projection checks

Status: Accepted for explicit discovery-source admission, 2026-10-12.

Authenticate an independently preserved expected discovery-source set before
running closure analysis. Compose the canonical primitive rechecker with the
stronger ROM-aware installed-entry re-import check, using the original import
known-image set and budget separately from solver instruction witnesses. Return
the unchanged solver result alongside the expected sessions and exact canonical
map digest. Authentication failure emits no closure report.

The trusted-boundary CLI creates a new expectation file exclusively and never
replaces one from later edited artifacts. Source-bound solving requires explicit
complete source inputs. Deterministic merged source sets preserve independent
sessions; a deleted negative session or installed-entry binding cannot be healed
by deleting diagnostics. Retained adversaries demonstrate that deleting a raw
store can make the ordinary finite-static solve CLOSED, while source-preserving
admission rejects the edit. Valid finite static scopes still close with their
existing assumptions; whole-ROM reports remain OPEN and native_complete false.

This is admission for the specified raw primitive and installed-entry domains,
not authentication of every compiled/derived image projection, a complete source
expectation census, or a whole-ROM certificate. Other fetch/cache/mutation/root
sources and coverage/lifetime obligations need their own adapters. ADR-0113's
standalone-helper boundary is now composed explicitly; no legacy solve API or
closed-world obligation is weakened. No upstream code or reference rebuild.

## ADR-0115: Cached root ancestry composes full-line residency and distinct lifecycle cuts

Status: Accepted for bounded pinned-reference root-history composition, 2026-10-12.

Reconcile PR #25's direct-mapped-slot invariant into the canonical existing
exception_root_generation API. Preserve v0's exact root-word-only format/policy
and serialized reports. An explicit v1 line profile admits aligned identity-RDRAM
full 32-byte fills, per-word captured backing writers, index invalidations and
canonical reset-cache transitions. Every fill replaces the complete resident
slot, even for equal payloads; each lane retains its own fill-time backing writer.
Missing backing remains unknown and later equal writes cannot heal it.

Reuse reset_cache_lifetime's exact pinned effect rule rather than adding a second
policy: NMI preserves cache/backing, system reset clears residency only, full
power clears both. V1 explicitly declares the existing ares reference profile;
these effects are not promoted to universal hardware truth. Reject restore,
translated/degraded accesses, schema mixing and unsupported root state.

Every root fetch still uses the canonical BEV0/EXL-clear/32-bit general-root
selector and exact physical 0x180. Current backing is diagnostic, never a stale
resident's source. Source/report rechecking binds the entire finite chronology.
Eight new composition regressions plus the retained ten root and twelve reset
regressions pass. Exact relied-on clean source hashes and authenticated retained
research establish the primitive contracts; no redundant reference rebuild.

The competing PR #25 module is superseded, not merged wholesale. Captured backing
writer compatibility is not ultimate byte origin. Actual event authentication,
complete writers/cache/mapping/root census, restore epochs, exception-delivery
composition, whole-ROM/native closure and progress milestones remain OPEN.

ADR-0115 restore follow-up (2026-10-13): v2 explicitly admits successful restore
boundaries as opaque cuts of all prior resident/backing observer ancestry. Equal
snapshot labels, cache words, PCs or physical addresses cannot recover earlier
writer/fill IDs. A refill before a fresh writer stays unknown even after a later
equal write; only a subsequent fresh fill can use that new writer. Snapshot SHA
labels are captured metadata, not authenticated snapshot bytes or component-root
certificates. V0/v1 continue rejecting restore and preserve their output shape.
Retained exact pinned restore counterexample binaries/source/manifests/results
authenticate and reproduce their original controls without rebuilding. The added
exception-root composition is synthetic; the old fixture runs ordinary PA0 code,
not exception delivery at PA180. Its shared I-cache restore invariant supplies
the cut rule, not a reachability/lifetime/hardware/whole-ROM claim. All proof flags
remain false. See the cached-root restore integration receipt.

## ADR-0116: Captured SP writers compose with actual executable reads without claiming a census

Status: Accepted for source-bound finite writer/fetch composition, 2026-10-12.

Extend the existing streaming SP replay with an opt-in writer/fetch report. Reuse
its exact complete v3/v2/v1/v0/v5 validation and in-context CPU SP Word-read join;
do not invent a new callback or independently supplied fetch event. Preserve the
legacy report/output. New reports require independently retained expected history
and fetch hashes and keep each captured byte writer in its actual bank/offset.

Every normalized Word/DMA sink is a fresh occurrence, including unchanged bits.
CPU sinks supersede only their full observed Word, retaining untouched DMA lanes.
Preserve actual DMA backing-read ordinals when bound, without guessing missing
request/lifecycle or source ancestry. Mirrored physical accesses retain their
own fetch identities while selecting actual bank storage. An incompatible actual
read cuts only affected byte candidates permanently; later equality cannot
resurrect them. Each writer identity is scoped to the containing source digest.

Compatible latest captured writers are not ultimate ancestry without complete
mutation sensing. Missing ordinary RSP/out-of-band producers remain a census gap;
all ultimate-ancestry/census/lifetime/native flags stay false. This composes real
storage and consumption facts, not atomic IMEM installation or RSP-universe
closure. PR #29's per-byte supersession invariant informed review; its promoted
request/lifecycle candidate is still unconsumed. No solver waiver or milestone
promotion. Four focused unit adversaries and complete-source CLI scenarios pass.
Authenticated retained 10,000-call replay retains all 7,945 SP fetch candidates
from 1,663 sink occurrences and preserves the entire prior report exactly.

A separate ignored ROM diagnostic invokes exact pinned ares mia IPL2-checksum
code under its ISC license, stored with the diagnostic, to identify the supplied
ROM as CIC-6105 (seed 0x91 checksum 0x8618a45bc2d3). No upstream production code
or game bytes enter Plaid/git. The existing 6102-only boot profile is not widened
by this result; a correct game capture remains a separate declared-source task.

## ADR-0117: Compilation roots and captured words survive source-preserving closure admission

Status: Accepted for explicit discovery-source admission, 2026-10-12.

Compose completed compilation projections with the existing primitive/install
checks. Canonical source re-import determines each completed unit's roots and
execution identity. Retain its exact begin/completion evidence and required
root provenance even when no EntryInstalled event was observed. Additional
legitimate merged roots are allowed; the solver independently rederives their
CFG. Supplied instruction words for captured identities must match the original
snapshot, including legacy opaque image labels. Missing instruction inputs stay
solver blockers rather than acquiring invented sources.

A primary red regression retained one closed self-loop and deleted a second
compiled unit containing unresolved JR, preserving both units' source metadata.
The old admission emitted CLOSED for the reduced declared-static map. New
admission rejects its missing compiled root. Another regression replaces opaque
solver instruction bytes with a self-loop while keeping authenticated compile
metadata/root identity; new admission rejects that word substitution. Extra
merged roots, existing install checks and positive bounded static closure remain
valid. Complete sources and original import context remain mandatory.

This strengthens ADR-0114's explicit boundary. Legacy primitive/installed-entry
helpers and ordinary solve keep their declared contracts. It does not infer
execution from compilation, prove sensor/byte lifetime or the complete root
universe, authenticate every derived field, or widen whole-ROM/native gates.
Eight focused admission tests, five existing install projection tests, CLI and
mandatory full local gate pass. No reference rebuild or progress milestone change.

## ADR-0118: RSP producers compose with CPU definitions and IMEM installs on the actual source clock

Status: Accepted for bounded compiler-time source composition, 2026-10-12.

Use the already validated unified decoder/sink chronology rather than joining
independently labeled RSP and DMA histories. Verify decoded RSP scalar store
operands, actual Byte effects, and the observed SBV vector-2/element-0 source.
Then propagate per-byte captured writers through an exact CPU LW register
identity into a completed direct-KSEG1 IMEM SW. Same-value RSP writes are fresh
occurrences. Equal-valued reads into another register cannot replace the selected
load definition; whole-register ADDU cuts it even if all result bits are equal.
Foreign DMEM mutations cut touched bytes. Unscoped IMEM stores retain content
without invented instruction attribution.

A generic typed protocol replaces fixture-event equality. Production assumes no
specific phase numbers, fixed code PCs, payloads or chain counts. Preserve raw
ordinals and captured full CPU/RSP snapshots, independent CPU steps and final
backing snapshots. Require an independently retained complete-source SHA and
reconstruct every report field. The explicit pinned profile permits controlled
RSP reentry seeds and CPU continuity, but excludes unobserved cache/TLB/DMA/restore
interleavings and unsupported instruction/vector sources. No guest executor or
reference implementation enters production; this is compiler-time verification.

Authenticated retained 58-record/16-checkpoint capture reproduces three chains,
including mixed CPU/unknown/vector/scalar byte origins. Twenty original measured
forgeries reject under the Rust protocol. Three unit regressions and generic CLI
cases pass, including phase/PC renaming to rule out a hardcoded fixture gate.
Full required local gate passes without a redundant emulator rebuild.

This consumes the stronger canonical source contract in rsp-cpu-imem-primary.md,
not the source research's rejected verifier or a raw branch module. PR #8's
broader scalar-load and PR #37's DMEM-DMA consumers remain pending; no invented
cross-clock bridge. Incoming scalar/vector operands, initial storage roots,
mutation census, IMEM execution/lifetime and whole-ROM/native completeness remain
uncertified. All corresponding flags stay false; no milestone or solver waiver.

ADR-0118 definition follow-up (2026-10-12): compose the prepared ORI/ADDU
primitive rules with the existing full RSP snapshot/DMEM/CPU/IMEM source clock,
not a selected-register schema or cross-clock value join. Explicit v1 admission
checks full after-state/control, mints raw-context parent nodes, associates
scalar sinks and clears tags at reentry. Equal definitions stay distinct;
opaque incoming and instruction roots remain uncertified. A68-event pinned
component/16 matched checkpoints independently reproduces four nodes/three
copies; retained v0 report bytes stay identical. Seven focused tests, source/
report/phase/input adversaries and full local gate pass. PR8 broader load/store
work remains pending. No census/execution/lifetime/native or milestone promotion.
See the RSP definition/IMEM integration receipt.

ADR-0118 completed-read follow-up (2026-10-12): extend the original clock with
an observed RSP LW return, preserving readUnaligned<Word> and using its result
once before assignment. Explicit v2 admission binds actual context/address/
offset/payload to four captured DMEM byte parents, then verifies full after-state
and carries the load/ADDU definition through later DMEM and CPU IMEM stores.
Discarded zero-register loads still require a read. Reclocked missing/duplicate
and equal-valued decoy reads cannot supply provenance. A79-event exact pinned
source/16 matched checkpoints independently reproduces six nodes/three copies.
V0/v1 report bytes remain identical; focused11 and full local gate pass (two
build jobs after Windows paging capacity failure). No census/execution/lifetime/
native/milestone promotion. See the RSP word-read/IMEM integration receipt.

ADR-0118 consumption follow-up (2026-10-12): controlled v3 joins the existing
RSP definition/DMEM/CPU IMEM graph to actual decoded words. Require full4096-byte
initial/final IMEM snapshots; record controlled host code seeds as opaque cuts
even when their payload repeats. Compare each instruction-prologue word against
current modeled bytes and retain four current writer IDs. This senses the existing
decoded word without adding a guest read. A97-event exact pinned fixture/17 matched
checkpoints independently reproduces six definitions, three copies and seventeen
fetches, including one actually executed installed NOP with CPU writer parents.
V0/v1/v2 reports remain exact. This proves discrete consumption; complete mutation
census, continuous executable lifetime, hardware consensus and whole-ROM/native
closure remain OPEN. See the installed-IMEM-fetch integration receipt.

ADR-0118 DMA-consumption follow-up (2026-10-12): reconcile PR37's completed
descriptor-selected DMEM byte-parent invariant onto the original full-snapshot
definition/consumption clock. Controlled v4 keeps each actual successful RAM Word
write separately, selects DMEM lanes from the current descriptor before comparing
payload and retains RSP definition/writer or unknown parents. Require a bounded
RAM snapshot, actual uncached fetch begin/read/end and immediate matching CPU
decoder context. Equal initial/final values do not replace writer identity.
A134-event exact pinned fixture/19 matched checkpoints independently reproduces
six definitions, two DMA writes, eleven CPU fetch/decoder pairs and seventeen RSP
fetches. The exported NOP executes at the next sequential CPU PC. V0-v3 reports
remain exact. No atomic DMA generation, accepted-request/completion lifetime,
general mutation census, cached/mapped/reset/restore or whole-ROM/native closure
is inferred. See the RSP DMEM DMA/CPU consumption integration receipt.

ADR-0118 promoted-DMA follow-up (2026-10-12): reconcile PR29's actual promotion/
completion hooks with complete descriptor progression on the existing DMEM/RAM/
CPU execution graph. Reject its looser grouping verifier: locally compiled
preparation accepts a24-byte request as complete after one8-byte sink. Controlled
v5 requires raw promotion identity, every expected Word/lane/row under length/
count/skip/PBUS wrapping and the exact completed endpoint. Individual latest-byte
writers remain distinct. Identity starts at actual pending->current promotion;
mutable pending commits and sampled BUSY edges are insufficient. The136-event
source agrees with all19 authenticated unchanged v4 controls; only the new sensor
was built. V0-v4 reports remain exact. No general FIFO/hardware rule, accepted
pending provenance, ingress/reset/restore/census/lifetime or whole-ROM/native
certificate follows. See the promoted-DMA/CPU integration receipt.

ADR-0118 IMEM-ingress follow-up (2026-10-12): reconcile remaining PR29 Dual
installation atoms with the original RSP/DMEM/RAM writer/request/CPU execution
graph. Controlled v6 requires each actual successful Dual RAM read before its
exact completed Dual IMEM sink, snapshots all eight current RAM byte parents and
installs distinct per-byte identities retaining read/install/promotion/address.
Actual RSP consumption retains those installed parents. Completion validates one
Dual install per ingress block separately from two egress Word writes, with full
count/skip/wrap/end progression. A142-event pinned fixture/21 matched checkpoints
independently reproduces both execution paths and the round trip; v0-v5 reports
remain exact. New guest behavior required a new small baseline/sensor; retained
sources supply compatibility without repeated builds. General FIFO/census/hardware/
cache/mapping/reset/restore/lifetime and whole-ROM/native remain uncertified.
See the DMA RAM/IMEM round-trip integration receipt.

ADR-0118 DMEM-ingress follow-up (2026-10-12): compose retained spike051's actual
two-Word-read/two-Word-store contract onto the original producer/RAM/request/
execution graph. Controlled v7 explicitly distinguishes DMEM egress, IMEM ingress
and DMEM ingress. Require both actual source reads before either lower DMEM store;
retain each lane's exact read/store/promotion and prior RAM byte parent through a
performed RSP LW definition. Equal returned values cannot identify the lane or
writer. Completion still validates complete count/skip/wrap/end progression;
missing successful/OOB reads cannot supply successful-source ancestry. A152-event
pinned source/23 matched checkpoints independently reproduces seven definitions
and all three directions; v0-v6 reports stay exact. General census/pending/FIFO/
hardware/cache/mapping/reset/restore/lifetime and whole-ROM/native remain OPEN.
See the DMEM ingress/RSP load integration receipt.

ADR-0118 pending-DMA follow-up (2026-10-13): reconcile retained spike034's mutable
pending/FULL-overwrite invariant into the existing source/writer/consumption graph.
Controlled v8 starts with an observed empty pending slot; capture address/length
mutations after their masked assignments and before transfer-start. Keep length
commit identity separate from latest PBUS/DRAM writer identity. FULL recommits
supersede prior occurrences even at equal values; later address writes still
mutate pending state. Actual promotion consumes only that latest state, including
immediate handoff after complete current progression. The180-event source/26
matched controls independently agrees on six commits, one supersession, five
promotions and subsequent RSP consumption. V0-v7 reports remain exact. This
reference-specific host-driven MMIO contract supplies no guest operand ancestry,
hardware/FIFO consensus, mutation census or continuous executable lifetime; all
general proof flags stay false. See the mutable-pending DMA integration receipt.

ADR-0118 decoded-MMIO follow-up (2026-10-13): controlled v9 checks actual CPU SW
effects into represented direct-KSEG1 SP address/length registers. Validate
decoded address, low32 payload, full context and unchanged GPR state; one pending
effect belongs to one SW. Synchronous promotion inside the decoder is admitted
only immediately after its exact accepted length mutation and retains the commit
decoder identity. The195-event source/29 matched controls independently joins
architectural r0's length write through promotion/install to RSP consumption.
Host address setup and backing code seeds keep their distinct unknown ancestry.
The explicit fixture drains separately after decoder completion; no generic
concurrent-device timing/hardware/census/lifetime claim follows. Nine v0-v8 reports
remain exact and all general certification flags remain false. See the decoded
MMIO/DMA integration receipt.

ADR-0118 cached-consumption follow-up (2026-10-13): controlled v10 requires actual
completed32-byte RAM burst followed immediately by its exact I-cache fill. Retain
all32 fill-time byte parents and reuse `FetchCacheLine.validate` for full selected
resident snapshots. Cached hits consume that frozen tuple and its original
parents, rather than current backing bytes. Separate cached burst/fill receipts
from uncached scalar-read receipts; invent no read for a hit. Explicit host PC
seeds preserve captured GPR state but cut register definitions and remain unknown
execution roots. The208-event source/31 matched controls executes cached NOP
after backing changes to BREAK. Missing-root207 capture rejects. All ten older
v0-v9 reports stay exact. General cache operation/mutation/mapping/root/restore/
continuous lifetime/hardware/whole-ROM/native obligations remain OPEN; flags stay
false. See the DMA/cached CPU integration receipt.

ADR-0118 invalidation follow-up (2026-10-13): controlled v11 binds one actual
completed guest HitInvalidateI to its decoded CACHE context, operation selector,
direct-KSEG0 effective address and complete before/after cache tuple. Matching
valid tags clear only validity; miss tuples remain unchanged. Track invalid slot
contents separately from resident fill eligibility, so repeated invalidation or
equal later words cannot recover ended fill parents. Subsequent completed burst/
fill snapshots capture their own fresh DMA byte writers. Actual228-event/
34-control source ends fill199, then fresh RAMwriter219 reaches cached CPU NOP
through fill225, retaining earlier DMEM ingress/RAM/RSP ancestry. Other operations,
TLB/aliases/restore/concurrency, complete mutation/root/lifetime and whole-ROM/
native remain OPEN; all flags stay false. All eleven v0-v10 reports remain exact.
See the DMA/cache invalidation integration receipt.

ADR-0118 CPU RAM copy follow-up (2026-10-13): controlled v12 reuses actual SP LW
and held-register continuity to bind one completed direct-KSEG1 CPU SW RAM writer.
Its receipt preserves load/read identities and original byte parents, checked
against the complete held GPR and decoded low32 store. A captured source without
a held load definition produces UNKNOWN cuts, even for equal writes. CPU RAM
byte writer IDs stay separate from SP DMA IDs. Existing resident fills retain
their old parents through equal CPU writes; later invalidation/refill captures
fresh CPU writer parents. Actual259-event/39-control history connects CPUwriter240
through load233/read234 to DMEM ingress/RAM/RSP ancestors, then cached consumption
through fill256. Explicit host roots remain opaque and cut register definitions.
All twelve v0-v11 reports remain exact; broad transforms/cached data copies/
source/mutation/mapping/root/lifetime/whole-ROM/native remain OPEN; flags stay false.
See the CPU RAM copy/cache integration receipt.

ADR-0118 CPU XORI follow-up (2026-10-13): controlled v13 retains one actual
in-place XORI context/expression on a held SP LW definition, following the existing
bounded `cpu_copy` policy. Verify full64 result with unsigned u16 immediate and
no memory effect. Keep original byte parents distinct from transformed bits;
repeated/renamed/unattributed transform sources lose candidate copy ancestry.
Transformed SP stores do not acquire identity IMEM-copy witnesses. Actual295-event/
45-control graph transforms NOP to ADDU r0,r0,r0 through CPU RAMwriter276; resident
fill256 still executes NOP, then guest invalidation287 and new fill292 expose the
transformed instruction to decoder294. Preserve transform270/load264/read265 and
earlier DMEM/DMA/RSP parents. All thirteen v0-v12 reports stay exact. Broad
transforms/decompression/relocation/complete mutation/mapping/root/lifetime/
whole-ROM/native remain OPEN, with all flags false. See the CPU XORI integration
receipt; no reference implementation is copied or linked into production.

ADR-0118 exception composition follow-up (2026-10-13): controlled v14 binds actual
BREAK before/after exception state to its fetched instruction/writer ancestry.
Reuse `resolve_exception_root`; check BEV0/kernel32, non-delay/non-nested General
vector, cause9, overwritten EPC, EXL and full unchanged GPRs. Its transfer must
complete in the same decoder then immediately reach a cached handler fetch and
decoder, without opaque reseeding or unrelated actors. Actual339-event/52-control
graph joins CPUwriter318/XORI312/load300/read301 to BREAK331/transfer332 and first
handler fetch334/fill336/decoder338. Handler NOP has separate CPUwriter307 and
original DMEM/RAM/RSP parents; no host PC setter supplies handler entry. All
fourteen v0-v13 reports stay exact. General exceptions/interrupts/TLB/reset/restore/
root census/mutation/mapping/lifetime/whole-ROM/native remain OPEN; flags stay
false. See the writer/BREAK/handler integration receipt; no upstream code copied.

ADR-0118 selected-EPC return follow-up (2026-10-13): controlled v15 retains the
live exception-produced EPC generation only through its permitted continuous
handler instruction stream. Opaque control roots cut candidate ownership, even
when EPC numerically equals a past capture; CP0 writers/reset/restore remain
unsupported. Check ERL0/kernel32/IE0 ERET current selected EPC, EXL/LLbit/full GPR
effects and immediate first cached returned-code fetch/decoder. The bounded frame
is consumed for this scope; physical EPC is not cleared. Actual365-event/57-control
graph joins BREAK transfer332 -> handler writer348/invalidation353 -> ERET358 ->
returned fill362/decoder364 with fresh DMEM/DMA/RSP parents. Handler and return
have no host PC setters. All fifteen v0-v14 reports stay exact. Retain common-EPC
research's current-writer obligation and exact pinned Mupen ERL stop disagreement;
this production scope claims neither guest EPC writes nor ErrorEPC/ERL support.
Static ERET remains unsupported and all general proof flags false. See the live
EPC return receipt; no upstream implementation copied or linked.

ADR-0118 guest-EPC writer follow-up (2026-10-13): controlled v16 composes actual
MFC0/MTC0 EPC accesses into the same handler/ERET/executable graph. Explicit
before/completed state checks admit only current EPC reads and same-value writes
from held current reads in the uncut kernel32/ERL0/IE0 frame. MFC0 sign-extends
low32 EPC; pinned MTC0 passes the full source GPR to the EPC setter. Keep these
CP0 definitions separate from physical-memory load parents; register rewrites
cut them even when bits agree. Each accepted MTC0 replaces selected writer
identity; a later equal write cannot borrow an old read. ERET keeps the exception
frame ID and distinct latest guest-writer ID. Actual375-event/59-control graph
joins read358 -> writer363 -> ERET368 -> fresh returned fill372/decoder374 with
replacement RAMwriter348/DMEM/DMA/RSP ancestry. All sixteen v0-v15 reports stay
exact; no host PC setters after handler entry. Broader writers/changed targets/
ErrorEPC/ERL/interrupt/root/mutation/mapping/lifetime/whole-ROM/native remain OPEN,
static ERET unsupported and general flags false. See the guest-EPC integration
receipt; no upstream code copied/linked or new research lane.

ADR-0118 transformed-EPC target follow-up (2026-10-13): controlled v17 reuses the
single in-place XORI receipt for a held current CP0 EPC read, without labeling it
a physical-memory load. MTC0 must bind the full computed GPR to completed EPC;
ERET and later reads must select the latest write's state, not the exception's
original captured value. Repeated/renamed/unattributed transforms remain cuts,
and old v16 keeps its stricter transform policy/report shape. Actual386-event/
61-control graph joins MFC0 read363 -> XORI367 -> MTC0 writer372 -> ERET379 ->
returned fill383/decoder385 at602c with separate CPUwriter353/load342/read343/
DMEM/DMA/RSP ancestry. All seventeen v0-v16 reports stay exact. Broader transforms/
arbitrary CP0/ERL/interrupt/reset/restore/mapping/root/mutation/lifetime/whole-ROM/
native remain OPEN; static ERET unsupported, general flags false. See the EPC
transform/target receipt; no reference implementation copied or linked.

ADR-0118 TLB/mapped-execution composition follow-up (2026-10-13): controlled v18
connects actual TLBWI write/synchronize callbacks and full raw32-entry state to
the existing writer/cache/exception/EPC/ERET graph. Normalize/recheck staged/current
entries and full table delta; derive fingerprints from entry data and reuse the
canonical operation-generation type. Never infer a write from diff/hash labels.
Mapped cached fetches require current table/ASID/kernel32/4KiB/CCA3/unique matching
entry and latest completed selected-slot operation. Invalid matching entries
also count for ambiguity; unsupported geometry/context/endian paths stay closed.
Equal write332 replaces325 while preserving resident fill292 until guest CACHE.
Actual400-event/63-control graph joins mapped BREAK345/exception346 -> EPCread377/
XORI381/writer386/ERET393 -> mapped returned fill397/decoder399 with independent
CPUwriter367/DMEM/DMA/RSP ancestry. All eighteen v0-v17 reports stay exact. Preserve
pinned ares virtual-slot vs Gopher physical-slot counter-reference; this fixture
uses matching colors and makes no hardware-wide synonym claim. General mapping/
context/census/root/reset/restore/lifetime/whole-ROM/native remain OPEN, static
ERET unsupported, all flags false. See the TLB/mapped root-return receipt.
No reference implementation copied/linked; only project-owned observational
callbacks/getters run in separately licensed ignored reference builds.

ADR-0118 EntryHi context composition follow-up (2026-10-13): controlled v19
observes actual MTC0 EntryHi at its masked setter boundary, preserving full source
GPR/decoded register and before/completed CP0/staged/32-entry snapshots. Only
ASID/VPN/region may change; installed entries stay unchanged. Keep context writer
occurrences separate from slot operations even on equal values. Mapped consumers
select latest completed context and slot writer, without retiring I-cache fills.
Actual421-event/66-control graph changes ASID7->8->7 then repeats7 at writes339/
346/353; mapped BREAK366/exception367 and returned fill418/decoder420 select353
and slot332 independently. Returned code keeps CPUwriter388/DMEM/DMA/RSP parents.
All nineteen v0-v18 reports stay exact. Initial context/register values remain
unknown inputs; broader sources/selection changes/hazards/TLBR/privilege/reset/
restore/census/root/lifetime/whole-ROM/native remain OPEN, all flags false, static
ERET unsupported. No reference implementation copied/linked. See EntryHi receipt.

ADR-0118 mapping/reactivation composition follow-up (2026-10-13): fixture20
reuses the v19 source protocol rather than adding another consumer or profile.
Actual TLBWI maps virtual e028 to physical6028; the exception EPC and transformed
ERET target remain virtual e028/e02c. Cached hits before/after EntryHi ASID
restoration retain fill292/CPUwriter276 despite changed RAM BREAK/writer318.
Only actual HitInvalidateI ends292; fresh BREAK/handler/return consume their
separate writer/fill parents. Context and installed-slot occurrences remain
distinct, even on equal values. Congruent cache colors avoid the unresolved
ares/Gopher index disagreement; no hardware synonym or hazard generalization.
General changed-physical selection/source/census/root/lifetime/whole-ROM/native
flags remain false; no milestone promotion. See mapping-reactivation receipt.

ADR-0118 staged-page/remap follow-up (2026-10-13): controlled v20 observes
actual guest MTC0 EntryLo0 after the masked setter and binds full source GPR,
decoder and before/completed CP0/staged/table state. Require installed entries
unchanged and normalized low-region/non-global/4KiB/kernel32/IE0 pre-trap scope.
Each TLBWI fixes its selected slot's completed page-writer parent; later staged
writes cannot retrospectively change installed ancestry. Keep that parent
separate from current ASID writes and operation/byte/cache identities. Actual
page398/405 (equal rewrite) -> TLBWI417 changes VAe028 from PA6028 to PAe028.
The staged-only hit retains old fill292; remapped BREAK refill428 retains new
CPUwriter391 despite equal BREAK at the old physical address. Natural handler/
EPC/ERET return retains PAe02c/CPUwriter452/DMEM/DMA/RSP parents. All earlier
reports retain their shapes/bytes. Broader CP0/global/geometry/privilege/hazards/
reset/restore/source/census/root/lifetime/whole-ROM/native remain OPEN; all flags
false, no milestone promotion. See staged-page/remap receipt.

ADR-0118 TLBR/context-load follow-up (2026-10-13): controlled v21 observes
successful guest TLBR after actual selected-slot copy, binds full normalized
before/completed staged/table/CP0 state and unchanged GPRs, and derives canonical
`TlbrContextGeneration` fingerprints. Retain selected installed TLBWI/page-writer
parents; the load neither writes a slot nor retires a cache fill. Current context
selects EntryHi or TLBR by latest occurrence, including equal writes/loads.
Reload also restores staged page ancestry from the selected slot for later
TLBWI; a newer uninstalled page write cannot be borrowed. Actual EntryHi424
moves ASID away; loads431/438 restore7, with equal438 selected at remapped BREAK
and returned consumption. Slot417/page405 and executable writer/fill ancestry
remain distinct. Reconcile spike054's invariant without importing its staged
component/CI scaffolding. Broader Index/no-load/privilege/global/geometry/reset/
restore/hazards/source/census/root/lifetime/whole-ROM/native stay OPEN; all flags
false, no milestone promotion. See TLBR/context receipt.

ADR-0118 conditional-store composition follow-up (2026-10-13): controlled v22
joins actual aligned direct-SP Word LL/SC and RSP executable consumption into
the shared chronology. Full before/completed GPR/CP0/link snapshots check the
pinned read/control transition. A writer requires the independently completed
Word sink through canonical `verify_sc_sp_effect`; neither opcode, success flag,
LLbit nor payload equality mints one. Bound pre-SC payload/address before rt is
overwritten, then cut held register ancestry. The direct-SP effect/result check
is specific to this exact interpreter scope; retain cross-reference reservation
disagreement rather than defining universal success/lifetime semantics. Failed
SC511 leaves writer50 selected; fresh LL reads519/533 feed equal writers525/539,
selected by actual RSP527/541. Explicit attempts distinguish no sink from success.
Opaque roots/other CPU instructions cut linked observer continuity, not physical
reservations. General faults/cached/mapped/endian/reservation/source/census/root/
lifetime/whole-ROM/native stay OPEN; all flags false, no milestone promotion.
See conditional IMEM composition receipt.

ADR-0118 subword/IMEM-transform follow-up (2026-10-13): controlled v23 binds
actual SB/SH raw device addresses separately from aligned completed SP Word
sinks, full GPR/control/endian before/completed state and direct-KSEG1 translation
to canonical `cpu_sp_subword`. The lower sink, not nominal opcode width, defines
mutation span. Optional IMEM-copy transforms reuse `CpuXorTransform`; explicit
shift-zero lanes (SB3/SH2) retain identity-word source ancestry, while other lanes
keep their mutation witness without borrowing that relation. Actual load547/
read548/XORI553 -> equal Word writers559/567 -> RSP561/569 retain distinct writer
generations and shared DMEM/DMA/RSP ancestry. A separate synthetic shifted-lane
history checks absent identity copy without executing its unsupported RSP word;
it is not an actual/hardware result. Earlier report shapes/policies remain exact.
Preserve masked-source/reference disagreement and general fault/alias/endian/
shift/source/census/root/lifetime/whole-ROM/native gaps. All flags false; no
milestone promotion or upstream production reuse. See subword IMEM receipt.

ADR-0118 RAM-load/IMEM follow-up (2026-10-13): controlled v24 connects actual
decoded aligned direct-KSEG1 Word LW to current RAM byte-writer ancestry rather
than reusing equal SP labels. Operand reads are distinct from instruction-fetch
reads and bind full GPR/control/link/endian before/completed snapshots and signed
64-bit result in the bounded kernel32/IE0/BEV0/EXL0/ERL0/non-delay/big-endian scope.
`SpByteOrigin::CpuRamLoad` is an ancestry wrapper inside subsequent copy receipts,
not an independently installed SP writer. It retains actual decoder/read/physical
byte identity and `RamByteOrigin`; current SP sinks still have their own actual
writer occurrences. Existing RAM/IMEM copy and XORI structures compose these
parents without creating a parallel consumer. Handler writer473 -> LW575/read576
-> identity XORI581 -> IMEMwriter587/RSP589 and equal RAMwriter595; fresh LW600/
read601 -> IMEMwriter607/RSP609. Earlier held reads retain473 while the fresh
read selects595. Unknown writers remain Unknown, including equal writes. All
earlier formats/shapes remain exact. Cached/mapped/degraded/failed/other loads,
global source/census/root/lifetime/whole-ROM/native remain OPEN; all flags false,
no milestone promotion or upstream production reuse. See RAM-load IMEM receipt.

## ADR-0119: Cached pointer reads consume the canonical D-cache resident state

Status: Accepted for bounded source composition, 2026-10-12.

Original-clock reuse follow-up (2026-10-13): extract the existing transition state
as internal `DcacheReplay` before adding decoded cached-operand composition. The
transition body is unchanged. Standalone sources retain complete contiguous
ordinals/external digests; containing authenticated sources may pass increasing
global-clock primitive occurrences, with backing-read/fill adjacency unchanged.
Event counts remain primitive counts rather than the final global ordinal.
Rejection consumes state so partially applied operations cannot be retried.
Existing v0/v1/v2 policies/reports/flags stay unchanged; this extraction supplies
no new capture, operand/source/census/lifetime or closure proof. See replay reuse
receipt; no reference rebuild is required for retained compatible consumers.

Reconcile the prepared pointer D-cache candidate into the existing writeback
engine rather than creating a second resident state machine. An explicit v1
source adds normalized completed cached Word reads and backing Word mutations.
Each read selects the exact direct-KSEG0 identity-RDRAM slot/line and returns its
captured fill generation, latest revision and four byte origins. Successful
full-line exports consume the same resident state. Equal payloads cannot borrow
ancestry from another backing write, mutation or equal-index replacement.

Captured backing words are separate diagnostic context. Uncached backing writes
do not change residency, while resident-only stores do not change backing until
an exact successful writeback. A later fill must agree with captured backing
writes where known. Unknown initial backing writers stay absent. The old v0
source/API/report serialization remain compatible; v1 has separate inspection
and full-report rechecking. Unsupported aliases, missing residency, contradictory
payloads, impossible indices and source/report forgeries reject.

Reuse the retained actual five-case capture authenticated by its original causal
replay receipt, exact pinned source inputs and canonical capture digest. All
captured cached reads reproduce, including stale/current-backing disagreement,
same-value backing generations, equal-value conflict/refill and resident-only
mutation. Ten fresh Rust CLI forgeries and the original twelve independent
forgeries reject. Three shared-state Rust regressions connect read ancestry to
backing exports and retain the nine v0 writeback tests. Full required local gate
passes without an emulator rebuild or Actions execution.

This supersedes PR #5 and its recovered duplicate's standalone resident engine.
No source instruction/register/dispatch definition proof is inferred from the
normalized Word callback. Physical-immutability histories remain pending; a
finite absence of observed writes cannot establish a complete mutation census.
Table/target identity, cache/mapping/reset/restore lifetime, hardware semantics
and whole-ROM/native closure remain OPEN. No solver or milestone promotion. No
reference implementation was copied into production.

ADR-0119 decoded cached-operand follow-up (2026-10-14): controlled v25 binds
actual direct-KSEG0 Word LW/backing burst/fill/delivered read to the same canonical
DcacheReplay. Full resident16-byte/tag/index/dirty and CPU control/endian/GPR
snapshots restrict the kernel32/IE0/BEV0/EXL0/ERL0/non-delay/big-endian clean scope.
Existing RAM writes enter that state's backing diagnostics on their actual
ordinals. Capture current RamByteOrigin at each actual backing burst; resolve
delivered bytes through canonical BackingFill identities to those frozen parents.
CpuCachedRamLoad ancestry wraps actual decoder/read/resident/physical byte and
RAM parents in existing CPU expression/copy receipts, not an installed SP writer.
Read618 and stale643 retain fill617/writer595 despite backing637/ADDU21; actual
HitInvalidateD657 then fresh fill664/read665 selects637, reaching IMEM671/RSP673.
No second resident policy or inference from backing equality. Full signed64
results and untouched resident lanes are checked; earlier reports stay exact.
Passive callbacks exclude debugger cache reads. Cached mutation/writeback/warm
unsensed/dirty/mapped/failed/other accesses and global source/census/root/lifetime/
whole-ROM/native remain OPEN; flags false, no milestone promotion or upstream
production reuse. See cached RAM-load/IMEM receipt.

ADR-0119 cached producer/export follow-up (2026-10-14): controlled v26 binds
actual cached Word SW to decoded GPR/control/endian before/completed boundaries,
exact changed Word/unchanged lanes/dirty mask and canonical resident revisions.
Retain source load/expression parents in separate occurrence-keyed mutation
receipts; equal stores create new revisions. CACHE0x19 must have actual matching
begin/completed16-byte RAM burst/end and verified unchanged-line/dirty-clear CPU
result. Reuse DcacheReplay's full outgoing origins, including untouched fill
lanes; never invent four Word writes or dirty-mask-only ancestry. Actual RAM
bytes receive DcacheWriteback occurrence parents. Cached reads of mutated Words
retain mutation identity and source receipts; exported RAM reads retain the
actual backing writer identity. Mutation692/export699 -> read706/IMEM712/RSP714
and cached read720/IMEM726/RSP728 compose both paths with DMEM/DMA/RSP ancestry.
Prior reports remain exact. General widths/mapping/cache operations/census/root/
lifetime/whole-ROM/native stay OPEN; all flags false, no milestone promotion or
upstream production reuse. See cached Word writeback/IMEM receipt.

ADR-0119 executable writeback follow-up (2026-10-14): fixture28 uses existing
v26 to connect full D-cache export699 with actual mapped cached CPU instruction
consumption. Equal backing cannot replace surviving I-cache fill503/CPUwriter473
at fetch731/decoder733. Guest HitInvalidateI740 ends503; fresh complete fill745/
decoder747 selects699, including all16 outgoing occurrences and Unknown remaining
fill lanes. Slot417/page405/TLBR438 mapping parents remain separate. Reuse the
existing verifier and typed byte-parent graph; no new schema/consumer/Rust policy
or native/lifetime promotion. Earlier report bytes stay exact. See mapped CPU
writeback receipt; whole-ROM/source/census/root/hardware/native remain OPEN.

## ADR-0120: Physical FPR byte generations compose with canonical COP1 store normalization

Status: Accepted for bounded source composition, 2026-10-12.

Adopt the prepared COP1 replay's physical-byte invariant and connect it to the
existing completed-store verifier. A completed uncached identity-RDRAM read
enters FPR storage only through its exact load definition/context/phase/width.
Same-value MTC1/DMTC1 writes replace selected byte generations. Failed loads
create no origin. Stores select actual supplied physical lanes, retaining
initial, memory-read and captured-move byte parents separately. FR or architectural
register numbers do not supply load ancestry.

Composition additionally runs the canonical CU1-aware SWC1/SDC1 verifier on
separately preserved normalization side inputs. Require a complete one-to-one
store set, exact occurrence ordinal, kind/FR/ft/storage/lane, replayed full FPR
state, semantic payload and direct-KSEG1 backing destination. Keep cache-resident
effects out of this uncached source contract. The canonical normalizer's existing
selection policy constrains this join; the generic FPR replay itself does not
infer physical lane selection or declare an emulator-specific odd-FR policy to
be hardware truth. Preserve the canonical CU1 gate and private wrapper unchanged.

Both CLI sources need independent external digests; full-report rechecking
reconstructs every field. Unknown event/report envelopes reject. New source
composition/adversarial regressions and the existing FPR/normalizer regressions
pass the required full local gate.

Existing swarm receipts retained the 96-case result but no accessible raw matrix.
One justified local exact-pin fixture reproduction matched that result and
retained detailed disabled/traced/repeated observations for future replay.
Rust reproduces 72 completed store joins, ten mixed-origin stores and six
equal-value false matches, plus eight same-value move cuts and 24 failed loads.
All 72 CU1-disabled side-input forgeries reject. No Actions execution or branch
workflow import. Original project Rust was reconciled; upstream implementation
and required notices remain only in ignored reference diagnostics.

Normalization contexts in this controlled matrix include declared instruction/
GPR seeds from the authenticated fixture, observed FPR0/1 snapshots and backing
effects, and initialized untouched FPR constants. FPR writer rows/selected lanes
are a checked fixture projection, not an additional raw writer sensor. This
does not prove decoded context/operand ancestry or complete writer coverage for
arbitrary ROMs. RDRAM producers, other FPR writers/arithmetic, cached/TLB/endian
paths, executable consumption/lifetime and whole-ROM/native closure stay OPEN.
All corresponding flags remain false; no solver or milestone promotion.

## ADR-0121: Ordered decoded store64 primitives compose with canonical backing export

Status: Accepted for bounded source composition, 2026-10-12.

Reconcile the prepared SD/SDL/SDR rechecker into the canonical D-cache engine
through explicit v2 source events. Bind each attempted architectural operation
to its captured opcode, base/source register values, GPR preservation and
control/exception result. Require the complete ordered Byte/Half/Word/Double
subwrite set, direct/endian physical identity, resident slot/line and full
post-mutation snapshot. A single operation may produce multiple primitives;
neither a fake Double-to-two-Word split nor payload equality supplies their
identities. Repeated same-value operations preserve fresh byte occurrences.

The same resident state supplies the exact full-line writeback receipt. Clean
lanes retain backing-fill parents while modified lanes retain their latest
operation/subwrite/byte identity. Missing effects, wrong order, false decoded
context, changed untouched lanes, borrowed earlier equal-value parents and
source/report forgeries reject. V0/v1 contracts stay compatible; the retained
v1 report-set digest is unchanged. Box the large private context variant to pass
strict Clippy without weakening checks or changing serialization.

The original 158-case matrix validated aggregate handler results, not a shared
primitive clock. Do not turn modeled decomposition rows into actual sensors.
Reuse spike 034's generic lower callbacks in a new integration fixture: 48
decoded cases, 82 attempts (two equal stores for each successful case), 34 actual
backing exports and 14 alignment failures. Original/disabled/repeated full GPR/
PC/control, HI/LO, timing count, RAM/hidden/cache hashes agree. Actual primitive
snapshots supply every byte parent; all 150 fresh source/report forgeries reject.
The necessary local source bridge and original aggregate/model evidence pass;
no Actions execution or branch workflow import.

The v2 profile is prefilled direct-KSEG0 identity-RDRAM, kernel32 with BEV1.
Register snapshots bind represented operands, not the ancestry of their writers.
General cached misses, uncached/TLB/degraded paths, other actor mutations,
hardware transaction/atomicity, restore/reset/mapping/cache lifetimes, executable
consumption and whole-ROM/native closure remain OPEN. All closure/census/native
flags stay false. No solver or progress milestone change. Only project-owned
instrumentation and Rust were integrated; upstream code/notices remain ignored.

ADR-0120 follow-up (2026-10-12): canonical completed-store normalization now
rejects nonzero architectural GPR[0], including absent-sink contexts. A red/green
forged-base regression and exact retained 96-case report replay verify the change;
no source/census/lifetime certificate or milestone is promoted. See the COP1 zero
primary receipt.

## ADR-0122: Execution-root classification carries an explicit target and hardware exclusion

Status: Accepted for target-qualified proof composition, 2026-10-12.

Adopt the prepared cache-error negative result using its explicit hardware basis.
The NEC VR4300 manual Appendix B.1.7/Table B-1, printed p632, excludes cache-error
exceptions; chapter 6.3.11/p178 describes unused compatibility CacheErr storage.
Reviewed the original seventh-edition PDF [manual mirror](https://hack64.net/docs/VR43XX.pdf#page=632).
Emulator silence alone is not an exclusion. Generic MIPS III remains unresolved.

Compose this typed target policy with the existing general/TLB vector resolver
at a new root-classification boundary. Numeric candidates and hardware-excluded
classes are separate report variants. The VR4300 vector contract is admitted
only for the explicit Nintendo64Vr4300 target; the existing vector API retains
its contract. Recompute full reports from target/class/context, rejecting forged
targets, classes, authority fields, handler/lifetime/native promotions and
unknown serialized fields. Existing root/lifetime/whole-ROM gates are unchanged.

Six focused tests include every existing class/BEV/EXL/address-mode combination.
Authenticated retained two-BEV CacheErr/readback-zero controls preserve sentinel
state and match four exact clean pinned source objects; the original negative
model hash reproduces. Full required local gate passes. No emulator rebuild,
Actions execution, source-workflow import or progress milestone change.

This resolves one target-level exclusion obligation, without proving exception
reachability, root census, handler bytes or executable lifetime. Other hardware
targets and reset/NMI/interrupt/watch/source/whole-ROM/native obligations remain
OPEN. All corresponding certification flags remain false. No manual text or
upstream implementation is copied into production.

ADR-0120 follow-up (2026-10-12): canonical completed-store normalization now
rejects nonzero architectural GPR[0], including absent-sink contexts. A red/green
forged-base regression and exact retained 96-case report replay verify the change;
no source/census/lifetime certificate or milestone is promoted. See the COP1 zero
primary receipt.

## ADR-0123: Explicit CIC configuration joins local ROM capture to boot-profile import

Status: Accepted for bounded reference discovery, 2026-10-12.

The supplied local ROM has an independently retained pinned-mia IPL3 diagnostic
for CIC-NUS-6105. Hardcoded 6102 reference setup is inappropriate for that input.
The existing shared profiled driver now accepts an explicit optional 6102/6105
selection. Its cartridge configuration and v4/v5 metadata use the same value.
Omitting the argument retains 6102 exactly; unprofiled/post-IPL2 interfaces keep
their existing scope. Other CIC/region/RAM/firmware/PIF modes remain unsupported.

Admit the declared NTSC/6105 boot-input profile in the existing typed importer,
retaining complete source/session/firmware checks and every executable-identity
blocker. A configuration declaration is not a ROM-CIC or hardware boot proof.
Exact pinned ares CIC configuration uses 6105 seed 0x91, checksum 8618a45bc2d3
and RealChallenge. CIC commands, PIF HLE and mia source objects were rechecked;
reference ISC licensing/notices stay in ignored builds. No upstream code or
firmware/ROM bytes are copied into production.

The general local recipe keeps outputs ignored, rejects unsupported selections,
checks disabled/repeated full existing checkpoints and repeated source bytes,
and reuses builds only when every recorded input matches. Build inputs include
the selector header. DrvFS uses serial index reads for the complete clean-source
check after a slow threaded scan; no source validation is skipped.

Actual local 6105 capture/import/rechecking passed for 10,000 calls: 2,055 PIF and
7,945 SP fetches, 305 summaries, no RAM fetches. Default/explicit 6102 trace,
checkpoint and messages reproduce retained homebrew bytes exactly without
another reference build. Fourteen focused tests, actual-source profile/firmware
adversaries and the full local gate pass. No Actions execution.

Extend actual writer/PI/SP/RAM chronology before granting executable source or
lifetime. Boot completion, mutation census, hardware consensus, whole-ROM and
native closure remain OPEN. No milestone promotion or game-specific hash rule.

ADR-0123 follow-up (2026-10-12): the retained million-call prefix reaches low RAM
at seq843555/PC ffffffff80000004 and preserves unknown executable identity. Align
the recipe budget ceiling with the existing driver's ten-million limit and stream
trace hashing. Actual digest replay, bounded-memory measurement and over-budget
rejection pass; no sensor, guest semantic, closure or milestone change. The larger
ongoing prefix is not a completion claim. See the local RAM-boundary receipt.

ADR-0123 follow-up: optional PI/queue/SP capture reuses canonical spike-040 and
source rechecking, with paired digests and independently retained baseline byte
equality. Actual 6105 data proves a returned 1 MiB ROM-to-RAM copy while leaving
request completion and ultimate SP ancestry uncertified. Debug/release reports
are byte-identical; use the optimized project reader for large streams without
rebuilding references. All census/lifetime/native flags and milestones remain
unchanged. See the local PI/SP clock integration receipt.

ADR-0123 capacity follow-up: explicitly bound driver/importer/map/recipe capture
at twenty million calls and reject malformed numeric arguments before narrowing.
Retained source/report compatibility and full local gate pass. A larger plain run
progresses beyond pending PI, but instrumented logging times out; partial streams
remain excluded. Measure and validate capture overhead without changing guest
semantics or source obligations before retrying. No native/closure milestone.

ADR-0123 buffering follow-up: explicit live 1 MiB stdio buffers preserve every
record/format/tracer/getter/guest effect. Matched100k capture29.827 ->5.837 seconds,
with exact source and checkpoint bytes. Close streams before freeing owned storage
even on flush errors. /dev/full failure and full local gate pass. Rejected raw-
disassembly bypass: no useful speedup and Random getter side effects require a
separate contract. No guest optimization, source waiver or milestone promotion.

ADR-0123 paired-history follow-up: align its finite call budget with the canonical
fetch ceiling rather than maintaining a stale independent one-million limit.
The full twenty-million source exposed this admission mismatch; history records
remain bounded at100million and all paired header/footer/source checks remain.
Six focused regressions and the full local gate pass. Complete actual v3/v5
reconstruction retains request1/token6/event1 status linkage and observed ROM
entry while keeping all ancestry/census/lifetime/native flags false. See the
local PI-entry receipt. No additional reference build or progress promotion.

## ADR-0124: Storage mutation sensing sits beneath identity-only RAM wrappers

Identity-only scalar/burst callbacks cannot exclude translated or EBus writes.
Add an opt-in passive observer to the exact pinned little-endian
Memory::Writable primitive. Preserve actual aligned/masked destinations and
truncated payloads, equal-value occurrence identity, Dual/unaligned/burst
component effects and stable writable-object identity. Existing protocols and
callbacks remain unchanged by default; toggling the recipe removes both shadows.

Fill, file load and reading serialization emit conservative whole-storage cuts,
not invented byte ancestry. Retirement cuts occur before freeing storage; saving
does not mint a restore. No extra guest access or object-layout change is made.
The25-effect/20-checkpoint actual component contract retains full ordinary/hidden
backing and baseline/disabled/repeat equality; exact source hashes fail closed
on drift. ISC reference code and notices stay in ignored generated builds, with
no reference implementation linked into production or native artifacts.

These callbacks must next compose with the existing original fetch/writer clock
and actual producer scopes. Requestor-labeled component calls do not authenticate
DMA tasks or guest execution. Hidden-RAM effects, raw pointer/JIT/Vulkan writes,
all lifecycle/scheduler paths and complete mutation coverage remain independent
obligations. No certificate, native flag or progress milestone is promoted.

ADR-0124 original-clock follow-up: history v5 retains ordinary storage effects
on the same counter/context as existing PI/queue/SP/fetch facts. Reuse the current
source projection and PI lineage state; scalar/equal effects revoke backing
parents, full fill/load cuts clear them, and no backing mutation refreshes a
surviving I-cache generation. Successful PI wrapper writer occurrences remain
distinct from preceding storage primitives. Source digests cover all added rows;
V3 source/report behavior stays unchanged, with new SP projection report-v1 only
for v5. Restore/retirement remain rejected under the uncut boot contract until
execution-epoch evidence composes. Retained69,513,732 records include3,027,381
additional effects with exact complete paired fetch/checkpoint/repeat controls.
No future execution, complete mutation census, hardware or native claim follows.

ADR-0124 physical-writer follow-up: a unique immediate Byte storage primitive
inside an authenticated PI attempt may supply the actual physical sink and
writer ordinal, using the existing returned ROM buffer parent. Validate PC,
payload, width and original-clock adjacency; select only on return. A successful
identity wrapper retains its own writer and must agree with the physical sink.
Missing primitives/ROM parents stay unknown; malformed or ambiguous intervals
reject. Legacy missing-identity-receipt counts do not refute translated success.
Actual requests/CPU execution retain110 events/eight full backing checkpoints.
The retained full commercial prefix passes a source/report-digest-bound delta
check over all1,048,576 attempts, permitting reuse of its earlier result without
another equivalent source replay. This shortcut rejects any newly selected
physical-parent branch. No mutation census, guest mapping/root proof, hardware
timing or native milestone follows.

ADR-0124 SP composition follow-up: freeze PI RAM byte parents at the source read
selected by the existing validated SP DMA receipt. Install those parents under
the separate SP writer occurrence and reuse the shared SP writer selection and
contradiction rules. Equal unscoped SP overwrites revoke attribution; later RAM
mutations cannot alter a frozen read. Missing or ambiguous reads stay unknown.
Consumed chains retain ROM/PI writer, RAM read, SP install and CPU SP backing-read
identities. New optional fields/report-v1 appear only when that path contributes
an attributed byte; unused paths retain legacy output and digests. The116-event,
twelve-checkpoint pinned baseline/disabled/enabled/repeat contract and independent
adversarial replay cover this finite join. Explicit host descriptor/mapping/DMA
stepping controls do not establish guest MMIO, RSP execution or scheduler timing.
No mutation census, executable lifetime, whole-ROM or native milestone follows.

ADR-0124 DMEM follow-up: extend the existing raw clock with completed lower DMEM
primitive effects in strict v6. Reuse the shared SP writer state to revoke only
the affected byte parents, even for equal writes; keep IMEM independent. Preserve
frozen DMA read receipts across their lower DMEM effects, before the separately
captured higher installation. No RSP register/task parent is inferred from a
sink callback. The pin's aligned RSP SW splits into four Byte effects, including
zero; the actual142-event/22-checkpoint control retains those measured lanes.
The supplied100k prefix adds1,008 effects with unchanged complete fetch/checkpoint
controls and canonical/independent agreement. V3/v5 behavior remains unchanged;
the new record rejects there. Complete census, other backends, lifecycle, hardware
and native obligations remain OPEN. ISC shadows/notices stay in ignored builds.

ADR-0124 RSP read/consumption follow-up: bind performed instructions to the exact
returned IMEM Word read, using original raw-clock IDs and shared SP writer/PI
parents frozen at that read. Reject the initial PC-only join: the pin preserves
JR/JALR low PC bits while masking Word addresses. Capture unused lookahead without
minting an execution occurrence, and retain begin-HALT state when a paired
instruction is actually performed. No extra guest read or reference object field
is added; default generated shadows remain exact. The222-event/28-checkpoint
baseline/disabled/enabled/repeat graph retains32 reads/24 performed instructions
and8 unused lookaheads. V7 source/optional RSP consumption report fields preserve
unknown roots and occurrence identity; old paths remain unchanged when unselected.
The early supplied100k prefix retains its complete legacy body and independent
consumer result. RSP register/task/hardware/census/lifetime and native obligations
remain OPEN; no progress milestone or proof flag is promoted.

ADR-0124 IMEM storage follow-up: extend the existing generic Memory::Writable
sensor to the exact IMEM object on strict raw v8. Completed aligned Byte/Half/
Word effects and whole-bank fill/load revoke shared SP ancestry, including
same-value writes. An earlier captured CPU/RSP read retains its frozen parents;
lower DMA effects occur before a separate higher installation with fresh writer
identity. No producer parent is inferred from a sink effect. Restore/retirement
still require an execution-epoch contract and reject. The retained pinned
342-event/40-checkpoint control graph and independently replayed 100k prefix
support only this bounded composition. Preserve old protocols when unselected,
all broad false flags and immutable captured receipts. Make the default-shadow
comparison portable across checkout relocation by normalizing only source/output
root prefixes; compare all remaining source text exactly at the same pinned head.

ADR-0124 scalar producer follow-up: share the existing ORI/ADDU expression
implementation between controlled RSP composition and explicitly rooted raw v9.
Keep original read/performed occurrence identity; attach computed definitions
through their begin context and exact read ordinal. Full before/after scalar
register snapshots verify the complete supported transition. Equal definitions
have fresh identities. Explicit monotonically advancing operand roots and all
unsupported producers cut held register candidates; captured root inputs remain
opaque. The register root does not rewrite already frozen executable-byte reads.
Commit every root and complete snapshot/definition occurrence to an ordered digest;
bound samples at 64 without claiming that samples are exhaustive. Legacy policies
reject operand fields/roots and preserve unselected outputs. The initial boot
recipe emits one opaque root and rejects later undeclared discontinuities; guest
task/control/reset composition remains necessary. The portable synthetic golden
contains only captured scalar/read observations from the original reference
fixture; its code byte origins remain unknown, and it does not stand in for the
full authenticated capture or writer census. All broad proof flags remain false.

ADR-0124 scalar sink follow-up: direct observed SB/SH/SW method scopes identify
actual RSP actors; temporal overlap alone is insufficient. Reuse the existing
scalar byte-lane verifier, check before/after GPR continuity and every completed
lane, and require exact decoded method/instruction ownership. Fresh shared SP
writer occurrences carry their read/instruction/root/method/register-definition
identities into CPU executable backing. Code bytes frozen before a register root
remain independent. A zero-scoped external effect always cuts ancestry, even
inside the method interval or with equal bits. Computed stores do not acquire
PI/ROM byte ancestry from equal values. Raw v10/report-v6 is explicit; old policy
semantics, serialized shapes and default reference shadows stay unchanged.
NOP/store register preservation is enabled only in v10; unsupported/vector
producers remain opaque. Scope and all completed effects join the ordered digest.
Bounded samples do not certify completeness. Task/control/reset, DMA/RAM computed
origin composition, writer/backend census, hardware/lifetimes and native closure
remain OPEN with all broad proof flags false.

## ADR-0125: Consumer-pulled priorities; synthetic native vertical slice permitted

Context: spikes 080-095 extended RSP/SP/DMEM/IMEM byte provenance one
composition step at a time. Each step was validated and fail-closed, but the
only real-ROM metric (the local Ocarina of Time conditional baseline: 293
blocks, 62 whole-ROM blockers, 44 unresolved indirect sites, recorded
2026-10-12) did not move. The provenance graph had no downstream consumer to
say how much precision is required, and decompression/relocation/signature
drafts (PRs #28, #31, #50) that commercial code loading depends on stayed
unmerged.

Decision: (1) every new cluster must name the consumer it advances: the OoT
blocker count, the synthetic native vertical slice, or known-library evidence,
and its receipt reports the effect; (2) RSP/SP lane, producer, task-root and
reverse-DMA composition beyond spike095 is paused until one of those consumers
is shown to need it; (3) narrow native lowering is permitted for synthetic,
already-CLOSED programs only, with ares differential tests and no interpreter or
JIT linked, to discover which proof facts the compiler consumes.

Unchanged: all AGENTS.md invariants, fail-closed semantics, exact-head CAS, no
ROM-derived bytes in git, `native_complete` and every broad certification flag
false. Commercial-ROM native lowering stays deferred until a commercial scope is
CLOSED. See the "Direction reset" section at the top of NEXT.md.

## ADR-0126: Reuse the N64Recomp ecosystem below discovery; lower through C

Context: Plaid's novel contribution is automatic executable discovery and
closure proof from an untouched ROM. N64Recomp (MIT) already lowers known
MIPS functions to C; N64ModernRuntime (GPL-3.0) and RT64 (MIT) already provide
the N64 runtime and RSP/RDP rendering that its shipped ports use. Rebuilding
those would delay the first native boot by a long way without testing Plaid's
claim.

Decision:
1. Lower through C. `crates/plaid-lower` emits one C translation unit from a
   CLOSED map: blocks are labels, direct transfers are `goto`, indirect jumps
   dispatch only over proven target sets, and anything outside the supported
   integer subset rejects the program. No guest decoder or interpreter is
   emitted. A host C compiler then produces x86-64 or ARM64 code. N64Recomp's
   lowering stays a reference to consult, not a dependency, until its function
   model is needed.
2. Reuse N64ModernRuntime and RT64 at the runtime milestone instead of writing
   a runtime/renderer. Licensing: a generated game application linked against
   N64ModernRuntime is GPL-3.0, like existing N64Recomp ports. Plaid's own
   compiler crates do not link it and keep their own (not yet chosen) license.
   Plaid has no LICENSE file yet; the owner must choose one before release.
3. First commercial target becomes Super Mario 64 (few code overlays, mostly
   uncompressed code); OoT remains the second target and its blocker count
   remains tracked. Decompilation-project symbol maps may be used locally
   only as an evaluation oracle for discovery recall, never as an input to
   discovery, and nothing derived from them is committed.
4. Assumption-qualified closure is expressed as explicit solver scopes, never
   by weakening an existing scope. New `DeclaredStaticImagesGuardedRam`
   admits RDRAM data loads/stores and pure compare/HI-LO arithmetic, and adds
   the assumptions that stores never reach executable bytes and that each
   16-byte RDRAM line is accessed through only one of KSEG0/KSEG1. The native
   artifact checks both at run time and aborts (faults 2 and 4) instead of
   executing. The second assumption exists because KSEG0 goes through the
   VR4300's write-back D-cache: mixed cached/uncached access to one line sees
   stale data on hardware and in ares, which a coherent native memory model
   would silently get wrong. The original
   `DeclaredStaticImages` contract is unchanged. Whole-ROM `CLOSED` and
   `native_complete` are unaffected.

First result (spike096): five synthetic programs covering ALU, shifts,
multiply/divide (including divide-by-zero and INT_MIN/-1), loops, all
supported branch kinds, delay slots, JAL/JALR links, a proven computed jump
and byte/half/word memory through KSEG0 and KSEG1 match the pinned ares
interpreter exactly (all GPRs, HI, LO and a 256-byte CPU-coherent RAM
window). A self-modifying store and a cached/uncached alias fault instead of
running. The slice surfaced the first
compiler requirement for discovery: `jr $ra` returns have no closure proof,
so any program with a function return is still OPEN.

## ADR-0127: Returns close under a runtime-checked call/return assumption

Context: milestone 1 showed that `jr $ra` had no closure proof, so no program
with a function return could reach CLOSED. Proving statically that `$ra` holds
the caller's link at every return needs stack-slot and callee-frame reasoning
that real code (`sw ra` / `lw ra` around calls) makes expensive, and a static
proof alone would still leave the lowered code unable to map returns to C.

Decision: `crates/plaid-core/src/returns.rs` partitions the program into
functions (call targets) and bodies (blocks reachable without entering a
call). A `jr $ra` site's certificate lists the functions whose bodies contain
it and the return continuations of every `$ra`-linking call into them; it is
recomputed from the map and bytes when rechecked. A site reachable from a
host-entered entry, or from no function, gets no certificate. The solver
accepts the certificate only in `DeclaredStaticImagesGuardedRam`, and only
with the added assumption that each return goes to the continuation of the
call that entered its function. Native code enforces it: each guest function
is one C function that receives its expected return address, and every
`jr $ra` compares `$ra` with it and aborts (fault 5) on mismatch. Whole-ROM
and `DeclaredStaticImages` scopes keep such sites OPEN.

Result: spike096 adds recursive, non-leaf, function-pointer and tail calls
with stack frames in the compared RAM window; all match the pinned ares
interpreter exactly, and a corrupted-`$ra` return faults 5 natively. On the
local OoT conditional baseline, 43 of the 44 unresolved indirect sites are
returns that now carry certificates; one non-return site remains. The
whole-ROM blocker count is unchanged (62), as intended for that scope.

## ADR-0128: 64-bit integer subset and checked overflow traps

Context: solving the OoT conditional window under
`DeclaredStaticImagesGuardedRam` (new `plaid solve <rom> <map> --guarded-ram`)
gave 143 blockers, 130 of them instructions outside the scope, led by
`LD`/`SD` and the doubleword shifts, multiplies and divides that libultra and
GCC emit.

Decision: the guarded scope also admits the VR4300 doubleword integer ops
(`DADD DADDU DSUB DSUBU DADDI DADDIU DSLL DSRL DSRA DSLL32 DSRL32 DSRA32 DSLLV
DSRLV DSRAV DMULT DMULTU DDIV DDIVU LD SD`) and the overflow-trapping
`ADD ADDI SUB`, under one more explicit assumption: trapping adds never
overflow. `plaid-lower` lowers them with ares's exact semantics (128-bit
products, `INT64_MIN / -1`, divide-by-zero results) and checks each trapping
add, aborting with fault 6 rather than raising a guest exception. Branch-likely
instructions, already admitted, now lower with the delay slot executed only
when taken.

Result: spike096's new `wide` program matches pinned ares exactly, and an
overflowing `addi` faults 6 natively. OoT guarded-scope blockers fall from 143
to 82. The rest are libultra system code (COP0, FPU context save, `CACHE`,
compiler `BREAK` traps), which is the runtime boundary.

## ADR-0129: Declared runtime functions are a discovery boundary

Context: after ADR-0128 the OoT guarded-scope blockers were libultra system
code (COP0, FPU context save, `CACHE`, `BREAK`). N64Recomp does not recompile
such functions: it marks them reimplemented and calls the host runtime's
version (`src/symbol_lists.cpp`, `src/main.cpp`). Its identification comes
from ELF symbols. Plaid has to start from the ROM, so identification is
evidence.

Decision: a `plaid-runtime-functions-v0` declaration (`plaid discover ...
[runtime.json]`, `plaid lower-c ... [runtime.json]`) names guest entries the
host runtime provides. Discovery records calls and tail-call jumps into them
but never decodes their bodies or adds their internal targets as roots; the
map carries them as `runtime_functions`, each backed by evidence. The solver
re-derives control flow with the same boundary. It accepts call and jump edges
(and linked indirect candidates) into runtime functions only under
`DeclaredStaticImagesGuardedRam`, adding an explicit ABI assumption that lists
them. A runtime entry that is also decoded as guest code (for example because
a branch reaches it) is a `runtime_function_decoded` blocker. Other scopes
report `runtime_boundary_outside_scope`. `plaid-lower` emits calls to
`int plaid_rt_<name>(plaid_state *)`. A tail call checks that the runtime
returns to the expected `$ra` (fault 5). The artifact gives the runtime no
guest entry points, so a runtime that tried to call back into guest code could
not.

Result: spike096 `boundary` calls and tail-calls a declared `sum` whose guest
body (it contains `SYNC`, outside the scope) runs on ares and is never
decoded natively; `spikes/096-native-slice/runtime.c` provides it, and the
results match ares exactly. A local OoT measurement that declared every
called function containing a system instruction (17 functions, chosen by a
heuristic, not evidence) leaves **1** guarded-scope blocker: the boot
function's own return to the host. That number is not closure. Coverage drops
from 293 to 190 blocks because runtime bodies are no longer decoded, and the
first thread's entry (`0x8000063c`, passed to `osCreateThread`) was never
discovered, before or after the boundary.

Consequences: the next gap is guest code that the runtime enters. Thread
entries and interrupt or event handlers are passed to runtime functions as
arguments, so a declaration must say which arguments are guest code
pointers, and discovery must prove their values at each call site and treat
them as host-entered functions. Identification evidence (PR #50 n64sym, or a
user-supplied symbol map) must also replace the heuristic; it is never
promoted to proof.

## ADR-0130: Runtime callbacks are proven code-pointer arguments

Context: ADR-0129 left the first OoT thread entry undiscovered. Its address is
an argument to `osCreateThread`, and a runtime that provides `osCreateThread`
must later enter that guest code.

Decision: a runtime declaration may list argument registers (`a0`-`a3`) that
carry guest code (`"callbacks": ["a2"]`). At every call or tail jump into the
function, `crates/plaid-core/src/callbacks.rs` proves the register's value
after the delay slot. It uses the local straight-line-prefix rule already used
for constant indirect targets (`indirect::prefix_state`). Proven targets become
discovery roots and functions the runtime enters. Their `jr $ra` returns get
certificates marked `runtime_entered`, because returning to the runtime is
closed by the declared boundary. An unproven argument, or a target without a
block, is an `unresolved_runtime_callback` blocker. `plaid-lower` emits
`plaid_enter(s, entry, ret)`, which switches only over proven callback targets
and faults 3 otherwise. It is the only way the runtime can enter guest code.

Result: spike096 `callback` passes a guest function to a runtime `spawn`.
Ares runs the guest `spawn` body; natively `runtime.c` calls back through
`plaid_enter`. The results match exactly. On OoT (local measurement; runtime
functions still chosen by heuristic, and `0x800030e0` identified as
`osCreateThread` by its call shape), the thread entry `0x8000063c` is
discovered and coverage grows from 190 to 613 blocks. Guarded-scope blockers
are 6: the boot function's return to the host, a `jalr` function-pointer call
(`0x80000f10`), a computed `jr` (`0x80003acc`), and three COP1 data moves
(`MTC1`, `SWC1`) in the thread entry.

## ADR-0131: COP1 data moves with 64-bit FPRs

Context: with ADR-0130, three of OoT's six guarded-scope blockers were COP1
data moves (`MTC1`, `SWC1`) in the first thread.

Decision: the guarded scope admits `MFC1 DMFC1 MTC1 DMTC1 LWC1 LDC1 SWC1
SDC1`, adding the assumption that COP1 is usable with 64-bit FPRs
(Status.CU1 = 1, Status.FR = 1) wherever they execute. That is the state IPL3
leaves for commercial games and ares's reset default. The native state gains
`u64 f[32]`. Following ares (`fgr_t`/`fgr_s` with FR = 1), 32-bit moves and
loads replace only the low word, `MFC1` sign-extends it, and the D-forms move
all 64 bits. FPU arithmetic, `CFC1`/`CTC1` and FR = 0 remain outside the scope.

Result: spike096 now compares all 32 FPRs. The oracle pins CU1 and FR, and a
new `fpu` program, which checks high-word preservation and an odd FPR,
matches ares exactly. The OoT measurement falls to 3 guarded-scope blockers:
the boot return, the `jalr` at `0x80000f10`, and the jump table at
`0x80003acc`.

## ADR-0132: Jump tables close under the guarded scope with store-protected bytes

Context: the OoT jump table at `0x80003acc` was missed for two reasons. GCC
schedules the index-scaling `SLL` in the bound check's delay slot, which the
recognizer did not accept. And recognized table candidates could never close,
because table immutability was unproven in every scope.

Decision: `tables.rs` also accepts the scale `SLL` in the delay slot of a
non-likely guard branch, since that slot runs on both paths. Analysis now
attaches the table evidence as a closure claim when the snapshot is complete,
aligned and the site has no other candidates. `tables::verify` rechecks it
from the current CFG and bytes, and `indirect::verify_static` (constant or
table) replaces `verify_constant` where function bodies and roots are
computed. Only `DeclaredStaticImagesGuardedRam` accepts a verified table: it
discharges the table immutability and identity obligations for that site and
adds the assumption that table bytes are read-only. `plaid-lower` adds the
table bytes to the store guard (fault 2) and dispatches over the snapshot
targets only. Every other scope keeps tables OPEN, as before.

Result: spike096 `table` (GCC-shaped table with in-bounds and default
indices) matches pinned ares, and `table_write` (a store into the table)
faults 2 natively. On the OoT measurement the table closes and its cases are
discovered (628 blocks). Six blockers remain: the boot return, `0x80000f10`,
and four `jalr t9` calls through a device-manager struct field in libultra's
PI manager thread. That thread is reached only because the heuristic runtime
declaration does not include `osCreatePiManager`, which N64Recomp reimplements.

## ADR-0133: Runtime functions are identified by n64sym signatures

Context: ADR-0129 declared runtime functions from a hand-written list. On OoT
that list left libultra's PI manager as guest code, and discovery followed
its memory-loaded device callbacks.

Decision: `plaid identify <rom> <rom-offset> <guest-start> <size> <sig>`
matches a code image against an n64sym `sig_v1` signature file and prints a
`plaid-runtime-functions-v0` declaration for the functions N64Recomp's
runtime reimplements. `signatures.rs` reimplements n64sym's matching rule:
CRC32 of the first 8 bytes and of the whole function, with the immediate
fields of `.targ26`/`.hi16`/`.lo16` words cleared, at every word-aligned
offset. A name that matches several addresses, or an address that matches
several names, is left undeclared and listed as ambiguous, so its body is
analyzed as guest code. Thread entries are marked as callbacks only for
`osCreateThread` (`a2`). A match names a function. It proves nothing: the
solver still lists the runtime ABI of every declared name as an assumption.
No signature file is vendored. The pinned n64sym `builtin_signatures.sig` is
a user input, and its SHA-256 is recorded in the declaration source.

Reuse: the matching rule follows n64sym `CSignatureFile::TestSymbol` (MIT,
Copyright (c) 2017-2020 shygoo). The function list is N64Recomp's
`reimplemented_funcs` (MIT, Copyright (c) 2024 Wiseguy). Both notices are
kept in `crates/plaid-core/src/signatures.rs`. No code was copied verbatim.

Result: on OoT US 1.2 the pinned signatures identify 39 runtime functions in
the IPL3 window, including `osCreateThread` at `0x800030e0`, the address the
heuristic had assumed, and `osCreatePiManager`. `__ull_rem` is ambiguous and
stays guest code. With these declarations discovery drops from 628 to 320
blocks and the PI manager thread is no longer analyzed. 21 guarded blockers
remain. Seven are in boot code: the boot return, the `0x80000f10` pointer
call, four `C.cond.S`/`BC1x` sites and one `SWL`. The other 14 come from
calls at `0x80000624` and `0x80000d94` into addresses that, at that point,
hold stale ROM bytes from the IPL3 copy, because the game DMAs its code
segment over them first. Those calls need the executable-DMA model, not
better identification.

## ADR-0134: Unaligned loads and stores follow ares, starting from N64Recomp's helpers

Context: the OoT boot code uses `SWL`, and libultra and GCC use
`LWL`/`LWR` pairs for unaligned copies. N64Recomp already implements these
as `do_lwl`/`do_swl`-style helpers (`include/recomp.h`, MIT, Copyright (c)
2024 Wiseguy).

Decision: `plaid-lower` adds `plaid_load_left/right` and
`plaid_store_left/right`, covering `LWL LWR LDL LDR SWL SWR SDL SDR`, plus
`LWU`. The merge arithmetic follows N64Recomp's helpers. Where they
disagree with the pinned ares interpreter, the oracle wins. ares sign-extends
`LWR` only when it loads bit 31 (misalignment 3) and otherwise keeps rt's
upper word; N64Recomp always sign-extends. The two agree for the usual
`LWL`+`LWR` pair and differ for a lone `LWR`. Loads read the containing
aligned word or doubleword through the existing checked access. Stores
write only the bytes they cover, like ares, so a partial store next to
executable bytes is not mistaken for a code write (fault 2), and one that
overlaps them still faults. `DeclaredStaticImagesGuardedRam` admits these
opcodes and states the access rule in its memory assumption. Other scopes
are unchanged.

Result: spike096 `unaligned` covers every misalignment of each form, lone
`LWR` on a register whose upper word is not a sign extension, and partial
stores into prefilled memory. It matches pinned ares. Replacing the `LWR`
rule with N64Recomp's always-sign-extend makes the program fail. Measured
ISA coverage rises from 85 to 94 of 209 forms. On OoT the `SWL` blocker at
`0x80003058` closes, leaving 20 guarded blockers, 6 of them in boot code.

## ADR-0135: COP1 compares use the MIPS condition rule, with NaN failing closed

Context: the OoT boot code branches on `C.EQ.S`/`BC1T`. N64Recomp lowers
compares to C relational operators and marks its unordered forms TODO: it
lowers `C.UN` as constant false and `C.UEQ` as `==`. Both are wrong for
NaN operands.

Decision: `plaid-lower` keeps the FCSR condition bit in `plaid_state.fcc`
and lowers every `C.cond.S/D` (cond = un|eq|lt|signaling) as
`(lt && a < b) || (eq && a == b)`, reading single operands from the low word
of the FR = 1 register. That is the pinned ares result for ordered operands,
denormals included. With a NaN operand, ares sets the condition to the `un`
bit or raises an exception, depending on the FCSR Invalid Operation enable,
which Plaid does not model. So a NaN operand aborts with the new fault 7, and
the guarded scope lists "no NaN compare operands" as a checked assumption.
`BC1F/BC1T/BC1FL/BC1TL` lower as conditional or likely branches on `fcc`.
`DeclaredStaticImagesGuardedRam` admits these opcodes. The COP1
usability/FR assumption now covers every COP1 instruction.

Result: spike096 `fcompare` runs all 16 conditions for single and double over
the following operand pairs:
- 1/2 and 2/1,
- equal values,
- -0/+0,
- denormal/0,
- -inf/+inf.

Each condition bit is recorded through `BC1TL` and `BC1F`. The run matches
pinned ares, including the condition bit now printed by both harnesses.
`fpu_nan` faults 7. ISA coverage rises from 94 to 130 of 209 forms. On OoT
the four compare/branch blockers close. 16 guarded blockers remain: in boot
code only the boot return and the `0x80000f10` pointer call, and 14 past the
code-segment DMA boundary.

## ADR-0136: Declared executable loads are verified by content at first entry

Context: after identification (ADR-0133), the remaining OoT blockers come
from calls into memory that the game fills with its `code` segment. OoT's
`code` file is Yaz0-compressed: boot DMAs the compressed bytes and its CPU
code decompresses them into place. So a model based on DMA observations
would not describe this load, and analysing the IPL3-copied bytes at those
addresses analyses stale data. Worse, stale bytes that happened to decode
cleanly would have been lowered silently.

Decision: a declared load (`plaid-loads-v0`: destination, decoded size, ROM
source, encoding `raw` or `yaz0`) names the bytes a program places at run
time, whatever the producer: DMA, CPU copy or decompression.
`declared_loads::compose` builds the composite image (the base window with
every load applied). Loads must be word-aligned, non-overlapping and
contiguous with the base. Discovery and lowering use the composite, and
`ProgramMap.load_images` records how it was built, so `solve` rebuilds it
from the ROM and checks its identity. Only `DeclaredStaticImagesGuardedRam`
accepts declared loads. A block that straddles a load boundary is a blocker,
because one entry check could not cover both sides.

The native artifact makes the declaration safe to be wrong:
- The host preloads only the base window.
- Every block inside load *L* starts with
  `if (!s->load_ok[L] && plaid_verify_load(...))`, which compares RAM with
  the declared bytes over *L*'s executable ranges. On a match it marks *L*
  verified; otherwise it aborts with the new fault 8.
- Before *L* is verified, stores into its executable bytes are allowed,
  since that is how it gets loaded. Once verified, they fault 2 like any
  code write.
- Host runtime functions must call `plaid_runtime_write` before writing
  guest RAM. It applies the same rule, which closes the gap where a
  runtime DMA could overwrite lowered code. The runtime ABI assumption now
  states this.

A load is verified at most once and never becomes unverified, so one byte
test per block entry is the steady-state cost. Unloading or reloading an
overlay over verified code faults 2 and is left to a later decision.

Reuse: the Yaz0 decoder is written from the format description (no code
copied). The `code` file's ROM range in the OoT measurement comes from the
game's dmadata table. Its VRAM comes from a local heuristic (internal `jal`
targets landing on prologues) that is not product logic and not evidence.

Result: spike096 `load` copies a routine through KSEG1 to a declared
destination and calls it; it matches pinned ares (the routine's result 10
included). `load_early` (call before copying) faults 8, and `load_patch` (a
store into the verified routine) faults 2. Unit tests cover the following:
- Yaz0 literals, overlapping and count-byte back-references, truncation and
  bad distances;
- composite patching and extension;
- rejection of gaps, overlaps, a Yaz0 source that is not Yaz0, and an empty
  declaration;
- guarded-only acceptance with its assumption;
- the straddle blocker.

The CLI test runs discover with `--loads`, then `solve` rebuilding the
composite, and rejects a gapped declaration and `--loads` on other commands.

On OoT US 1.2, declaring the `code` file (Yaz0, 0x103da0 bytes at
`0x800116e0`) takes discovery from 320 to 7451 blocks. The guarded solve
reports 748 blockers, now dominated by instruction coverage:
- 182 `BREAK`, GCC's divide checks;
- about 400 COP1 arithmetic, conversion and FCSR sites;
- 33 unresolved indirect sites;
- 7 unmapped or unresolved targets.

## ADR-0137: Return certificates share one closure context per map

Context: with the OoT `code` segment declared, discovery's final
return-certificate pass did not finish in over 25 minutes (release build,
7451 blocks, 723 indirect sites). `returns::certificate` recomputed, for
every `jr $ra` site, every call, callback and verified jump, plus the body
of every function, and each body walk scanned all blocks, edges and sites.
The solver's `verify` repeated this per site.

Decision: `returns::Closure` computes those map-wide facts once:
- an indexed successor relation;
- the bodies of all callees and host entries;
- an index from block to the functions that contain it.

`certificate`, `verify` and `annotate` answer each site from it. The solver
caches one per image, and lowering computes all bodies from one index. The
old per-site functions remain as wrappers. The semantics are unchanged,
including the first-block-wins rule for duplicate block starts.

Result: the OoT annotate pass takes 69 ms, and whole discovery about 1 s.
On the OoT boot window, discovery maps and guarded solve reports are
byte-identical before and after the change. The workspace tests and
spike096 pass unchanged.

## ADR-0138: BREAK is a checked abort under the guarded scope

Context: with OoT's `code` segment declared, 182 guarded blockers are
`BREAK` instructions. Nearly all are GCC's divide checks: `bnez divisor`
over `break 7` and an overflow check over `break 6`. On hardware a reached
`BREAK` raises a Breakpoint exception into the game's crash handler, which
Plaid does not model.

Decision: under `DeclaredStaticImagesGuardedRam`, `BREAK` is admitted. Its
discovery fact (`exception_or_unsupported_instruction`) is discharged, on
both the map's facts and the solver's re-derived facts, and the scope lists
"BREAK is never executed" as an assumption. `plaid-lower` emits an abort
with the new fault 9. This mirrors the overflow traps (ADR-0128): the
untaken path is exact, and the taken path fails closed instead of running
an unmodeled handler. `SYSCALL`, `ERET` and the conditional traps stay
unsupported. The ISA coverage measure counts `BREAK` as lowered because it
passes discovery, the guarded solve and lowering.

Result: spike096 `divcheck` (a GCC-shaped `div` with an untaken divisor
check) matches pinned ares, and `break_reached` faults 9. OoT, with its
declared `code` segment, drops from 748 to 566 guarded blockers. ISA
coverage is 131 of 209 forms.

## ADR-0139: COP1 arithmetic and FCSR under the guarded scope

Context: with BREAK admitted, 526 of OoT's 566 guarded blockers are COP1
arithmetic, conversions and FCSR access (`mul.s` 121, `cvt.s.w` 60, `div.s`
51, `cfc1`/`ctc1` 49, ...). The values these produce depend on the FCSR
rounding mode, and their exceptions depend on its enables.

Decision: the guarded scope admits `ADD SUB MUL DIV SQRT ABS MOV NEG` in
`.S` and `.D`, `CVT.S` from D/W/L, `CVT.D` from S/W/L, `CVT.W` and `TRUNC.W`
from S/D, and `CFC1`/`CTC1`. `plaid-lower` models FCSR as pinned ares does:

- `CTC1 $31` sets the rounding mode on the host FPU (`fesetround`), and each
  operation reads host exception flags into the cause and sticky bits.
- Every operation except `MOV`, `CFC1` and `CTC1` clears the cause bits
  first. This now includes compares and `BC1`.
- When FS is set, a subnormal result is flushed by rounding mode. A NaN
  result becomes ares's default NaN.
- `CVT.W` and `TRUNC.W` round explicitly in integer arithmetic, without
  libm, so a build's `rint` cannot change them.
- `CFC1 $0` reads revision `0x0a00`.

What ares raises as an exception faults 7 natively. Fault 7 now means "COP1
operation outside the modeled subset": a NaN or subnormal input, an
out-of-range conversion, an enabled cause, or an unimplemented-operation
case. The scope's COP1 assumption says so. A signalling-NaN input, which
ares lets through when Invalid is disabled, also faults: the fail-closed
side. `ROUND/CEIL/FLOOR` and the `.L` destination conversions stay
unsupported: ares computes them with SSE4.1 or libm depending on the build.

Reuse: the semantics follow pinned ares (ISC) as the oracle. N64Recomp's
helpers were not copied. Where they differ, for example in FCSR cause
handling, ares decides.

Result: spike096 `farith` matches pinned ares. It covers every new form,
the four rounding modes on `CVT.W` and division, sticky flags, overflow,
divide by zero, invalid `sqrt`, FS flushing under RN and RP, and `CFC1 $0`.
FCSR is now compared too. `fpu_enabled` (inexact enabled) and `fpu_range`
(`CVT.W` of 2^31) fault 7. Five lowering mutations each fail `farith`:
no cause reset, a wrong tie rule, no `fesetround`, a wrong RP flush, and no
sticky flags. OoT, with its declared `code` segment, drops from 566 to 42
guarded blockers. ISA coverage is 159 of 209 forms.

## ADR-0140: GCC's scheduled jump-table shapes

Context: after ADR-0139, 12 of OoT's 33 unresolved indirect sites are jump
tables that the ADR-0132 recognizer rejects. Each rejection traced to GCC
scheduling. An unrelated instruction can sit between `SLTIU` and its
`BEQZ`; one site has twelve of them. The table-base `LUI` can sit between
the scale `SLL` and the `ADDU`. And one loop re-enters the guard branch
from a `BNEL` whose delay slot repeats the same `SLTIU`.

Decision: the recognizer accepts these shapes, under the same rechecked
proof:

- The bound is the nearest earlier instruction that defines the branch's
  flag, within 32 instructions, and it must be the `SLTIU` on the index.
  Instructions in between must be ordinary, non-trapping and leave the
  index unchanged.
- The scale is the nearest `SLL` in the dispatch block that feeds the add.
  Instructions between it and the add must leave the scaled index unchanged
  and are folded into the base-value computation.
- Any entry into the compare-to-branch interval is still a bypass, with two
  exceptions: sequential fallthrough from inside the interval, and a branch
  whose delay slot holds the identical `SLTIU` word. The delay-slot bypass
  of ADR-0132 is unchanged.
- Every word that takes part goes into the evidence prefix hash. For shapes
  the old rule already accepted, the prefix is byte-identical, so existing
  evidence does not change.

Result: unit tests cover the scheduled shape and four rejections:

- the interval rewrites the index;
- the rebound slot uses a different bound;
- the rebound branch has no bound in its slot;
- the scaled index is rewritten before the add.

spike096 `scheduled_table` matches pinned ares. OoT, with its declared
`code` segment, closes all 12 tables. Discovery grows to 8082 blocks and
the guarded blockers drop from 42 to 31.

## ADR-0141: runtime identification over declared loads

Context: `plaid identify` scanned only the base window. OoT's `code`
segment, a declared load since ADR-0136, also links libultra. Two of its
functions were OoT's last instruction-scope blockers: `mtc0 Compare` in
`__osSetCompare`-style code, and `cache` in `osWritebackDCacheAll`.

Decision: `identify` accepts `--loads` and scans the same composite image
that `discover` builds. Nothing else changes. Ambiguity still fails closed:
a name that matches more than once is reported, not declared.

Result: OoT identification goes from 39 to 59 functions.
`osViGetCurrentFramebuffer` becomes ambiguous because a second match now
appears, so it is no longer declared. The guarded measurement drops from 31
to 29 blockers over 7684 blocks, and no instruction-scope blocker remains.
`scripts/test_cli.py` checks that a load copying an identified body makes
it ambiguous, which shows the loaded bytes are scanned.

## ADR-0142: Function-pointer calls through memory stay open

Context: after ADR-0141, 21 of OoT's 29 guarded blockers are `jalr` calls.
Nine are `_Printf`'s output callback, held in a parameter that one of its
callers loads from word 0 of a print struct. The others load a struct
field, a global cell or a list node.

Decision: Plaid adds no field-store census and no parameter-flow closure.
`research/function-pointer-points-to.md` traces every site back to a
memory load. The field has no fixed address. 520 `sw x, 0(base)` stores
in closed code, and the declared runtime functions, write through bases
that nothing proves. A census over stores that look like the field store
is therefore a guess. The native `jalr` dispatch already faults 3 outside
the candidate set. Accepting a runtime-checked guess as closure would let
any guessed set close, so the guess does not count. The one sound
extension measured is a store-guarded fixed-address cell, which
generalizes ADR-0132. It would close 1 of 22 sites, which does not justify
its machinery. Revisit it if SM64 shows such cells as a blocker class.

Result: the 21 sites stay unresolved. The OoT measurement is unchanged at
7684 blocks and 29 guarded blockers, and `native_complete` stays false.

## ADR-0143: ROUND, CEIL, FLOOR and the .L conversions

Context: ADR-0139 left `ROUND/CEIL/FLOOR.W` and every conversion to L
unsupported, because pinned ares computes them in a build-dependent way.
With SSE4.1 it uses `_mm_round`. Without it, it uses `round`, `ceil` and
`floor`. `round` rounds ties away from zero, whereas the VR4300 rounds them
to even.

Decision: the oracle is the pinned ares built as spike 003 builds it, with
`-msse4.1`. That is the SSE4.1 path, which agrees with hardware ties-to-even;
`CEIL/FLOOR` give the same values on both paths. The guarded scope admits
`ROUND/TRUNC/CEIL/FLOOR.W`, the same four `.L` forms, and `CVT.L` from S/D.

`plaid-lower` extends ADR-0139's exact integer rounding:

- The rounding mode comes from the function field (ties to even, toward
  zero, up, down). `CVT` uses FCSR.RM.
- Inputs follow ares's ranges: |x| < 2^31 for W, |x| < 2^53 for L. A W
  result that rounds out of range faults 7.
- Inexact is set exactly when a fraction remains.
- An L result writes all 64 bits of the FPR.

Result: spike096 `fround` matches pinned ares. It covers ties of both signs,
-0.5, a 1.75 fraction, -3.5 as a double, 2^40 + 0.5 through the four L
forms, and `CVT.L` under RP and RM. `fpu_round_range` (`CEIL.W` of
2^31 - 0.5) faults 7. Three mutations each fail spike096: L results written
as 32 bits, the wrong mode taken from the function field, and ties rounded
away from zero. ISA coverage is 175 of 209 forms. OoT is unchanged at 29
guarded blockers, since its reachable code uses none of these forms.

## ADR-0144: Discovery recall against a local reference map

Context: milestone 2 asks for SM64 discovery recall of at least 99%,
scored against a decomp map that serves only as a local oracle. Nothing
measured recall yet.

Decision: `plaid recall <map.json> <reference> [start end]` scores a map's
function entries against a reference symbol file. The reference stays at
an ignored local path and is never committed.

- Reference: either a GNU ld map, where a symbol counts when it is listed
  under a `.text` or `.text.*` input section, or a splat `symbol_addrs`
  file, where a line counts when it carries `type:func`. Aliases at one
  address count once. 64-bit addresses, zero- or sign-extended, fold to
  KSEG0.
- Discovered functions: map entries, direct call targets, candidates of
  linking indirect sites, and declared runtime functions. Comparison is by
  guest PC, because a reference has no image identity. Overlapping overlays
  would need one range per image.
- Report (`plaid-recall-v0`): reference and discovered counts, matches,
  recall, the 0.99 target, whether it is met, and every missed symbol.
  Discovered entries absent from the reference are counted but not scored
  as errors, because linker maps omit static functions.

Result: unit tests cover ld-map section filtering, sign-extended
addresses, aliases and splat `type:func` lines. `scripts/test_cli.py`
scores a synthetic map with one function never discovered: recall is 2/3,
the target is missed and the missed name is reported. Restricting the range
excludes that function and meets the target. An input with no code symbols
is rejected.

## ADR-0145: Branch-and-link, LL/SC, SYNC and conditional traps

Context: 21 of the 34 unlowered forms are ordinary guest-CPU instructions,
not runtime-boundary ones: `BLTZAL BGEZAL` and their likely forms, `LL LLD
SC SCD`, `SYNC`, and the twelve conditional traps (`TGE TGEU TLT TLTU TEQ
TNE` and their immediate forms).

Decision, following pinned ares:

- Branch-and-link writes `$ra` = pc + 8 whether or not the branch is taken,
  then tests `rs`, so an `rs` of `$ra` sees the new value. A taken branch is
  a call with the ADR-0127 return closure. The likely forms run the delay
  slot only when the branch is taken. Discovery and the solver already
  handled these forms as calls; only lowering was missing.
- `LL`/`LLD` load and set an LLbit in the native state. `SC`/`SCD` store and
  write 1 only when the LLbit is set, and otherwise write 0 and store
  nothing. Only `ERET` clears the bit in ares, and `ERET` is outside the
  model. The address that ares records for `LL` is visible only through
  COP0 `LLAddr`, which is also outside the model. The guarded scope admits
  these as guarded memory accesses.
- `SYNC` is a no-op.
- Conditional traps are discharged under the guarded scope like `BREAK`
  (ADR-0138), with their own assumption: they are never taken. Native code
  checks each one and aborts with the new fault 10. Discovery now continues
  past a conditional trap, because its not-taken path falls through. The
  `exception_or_unsupported_instruction` fact is still recorded, so other
  scopes stay blocked. The immediate unsigned forms compare against the
  sign-extended immediate.

Result: spike096 `system` matches pinned ares. It covers `SC` before any
`LL`, an `LL/SC` pair, `LLD/SCD`, `SYNC`, every trap form untaken, and five
branch-and-link cases: `bal`, untaken but linking, likely untaken with its
slot skipped, likely taken, and conditional taken. `trap_taken` faults 10.
Four mutations each fail spike096: `SC` ignoring the LLbit, a
zero-extended `TGEIU` immediate, the likely slot always run, and no link
when untaken. `tests/traps.rs` checks the fallthrough and that only the
guarded scope discharges the trap. ISA coverage is 196 of 209. The 13
forms left are COP0, TLB, `ERET`, `SYSCALL` and `CACHE`. OoT is unchanged
at 29 guarded blockers.

## ADR-0146: A host entry returns to the host

Context: ADR-0127 gave no certificate to a `jr $ra` reachable from a
host-entered entry, because the return address is unknown. Every boot path
has such a return. OoT's is the boot function at `0x8000058c`, after it
starts its threads, and it was one of OoT's 29 guarded blockers. Meanwhile
`plaid_run` already called the entry with the host's `$ra` as its expected
return, but treated a normal return as fault 5.

Decision: a host entry's return goes to the host, like a runtime-entered
callback's (ADR-0130).

- The return closure records, for each block, the host entries whose body
  contains it. A `jr $ra` there gets a certificate with those entries in
  `functions` and the new `host_entered` flag. Continuations from calls are
  unchanged, so a function that is both called and host-entered lists both.
- The guarded scope's return assumption now reads "returns to the
  continuation of the call that entered its function, or to the host's
  return address for a host-entered function".
- Natively, nothing new is trusted. The entry's C function still compares
  `$ra` with the host's `$ra` and faults 5 on mismatch. `plaid_run` now
  treats a normal return as handing control back, with `s->pc` set to the
  host's `$ra`.

Result: spike096 now enters every program with `$ra` = exit on both sides,
so `driver.cpp` changed and the oracle was rebuilt. `hostreturn` (a
non-leaf host entry with a stack frame) matches pinned ares and exits
through its own return. `host_bad_return` faults 5. Two mutations each fail
spike096: a wrong `s->pc` on the host return, and dropping the `$ra` check.
The lowering test now asserts a checked host return where it used to assert
OPEN. OoT drops from 29 to 28 guarded blockers: the 21 ADR-0142 sites and 7
calls into the 64DD driver, which ships on the disk, not the cartridge.

## ADR-0147: Guarded flag cells do not prune branches

Context: 7 of OoT's 28 guarded blockers are calls into the 64DD driver,
which is absent from the cartridge. Each sits behind a test of the byte at
`0x80121ae2`, which no closed store writes. The proposal was a guarded flag
cell: a fixed-address cell whose value set (initial value plus every
constant store) proves a branch one-way, with native checks on every store
that overlaps it.

Decision: not adopted. `research/guarded-flag-cells.md` records the
prototype and its measurement:

- Only cells above every image can assume zero as their initial value.
  IPL3 writes the low system area, and bytes in the IPL3 window may be BSS
  that boot code clears later.
- A conservative `%lo` rule rejects cells with cross-block writers.

With both rules, 15 cells decide 22 branches, make 163 blocks dead and drop
OoT from 28 to 20 guarded blockers. But several of the cells are runtime
state, written through struct pointers that no recognizer can see. Their
`{0}` value set is a blind spot, so pruning would delete live code. The
native guard would make the artifact fail closed on the first such write,
and the closure claim would rest on an assumption the game breaks in
normal play, which is the same reason ADR-0142 rejects guesses. A sound
version needs whole-program store points-to.

Result: the prototype is reverted and no code changed. OoT stays at 28
guarded blockers, and its sound frontier now needs store points-to or SM64.

## ADR-0148: Runtime functions can be named from a reference symbol map

Context: Mario Party 2's boot window (`research/mario-party-2-boot-window.md`)
is OPEN with 29 guarded blockers. 27 are libultra system instructions in
routines that `osInitialize` calls. n64sym's database lacks this SDK build:
the crcA of three `osInitialize` variants and of the cache routines matches,
but none of their crcB does. Signature coverage therefore depends on the
SDK build, which is also a risk for SM64. N64Recomp names reimplemented
functions from ELF symbols, not signatures.

Decision: `plaid identify <rom> <offset> <start> <size> <reference> --symbols`
reads a reference symbol map instead of a signature file. The parser is
ADR-0144's: a GNU ld map's `.text` symbols, or splat `type:func` lines. It
declares the functions on N64Recomp's reimplemented list whose entries are
word-aligned and inside the scanned image (the composite with `--loads`). A
name at more than one address is ambiguous and stays undeclared. The output
is the same `plaid-runtime-functions-v0` declaration, with no size. Its
source names the symbol map, with that map's sha256 and the ROM's. The
symbol map is user-supplied evidence, as signatures are, and the solver still
records the runtime ABI as an assumption.

crcA-only signature matches stay rejected, because a wrong name would bind
guest code to the wrong host implementation.

Result: unit and CLI tests cover in-image, misaligned, out-of-image and
ambiguous names. No local ROM has a symbol map, so no real-ROM number
changes: Mario Party 2 stays at 29 guarded blockers and OoT at 28. When the
SM64 ROM arrives, milestones 2 and 3 can use the same decomp map for recall
and identification.

## ADR-0149: Callbacks forwarded through a wrapper's argument

Context: SM64's game code is built with IDO at `-O0`. Its threads are created
through `create_thread(thread, id, entry, arg, sp, pri)`, which spills
`entry` to its argument home and reloads it before calling `osCreateThread`.
ADR-0130 proves a callback only when the argument register holds a constant
at the runtime call, so SM64 discovery stopped at 13 to 68 blocks, before the
idle thread.

Decision: when a callback argument is not a constant, `plaid-core/callbacks`
checks whether it is the enclosing function's own incoming argument. The
site's straight-line prefix must start at the function entry, and a
symbolic pass tracks `a0..a3` through register moves and word spills to
`$sp` slots:
- A store of another width through `$sp` clobbers the slots it may touch.
- Any other read of `$sp` lets the frame escape and clears every slot.
- A store through any other base is assumed not to write the slots, which
  C's object rules give for an argument home that is never address-taken.

If the argument is forwarded, the callback's targets are the values that
each direct call or tail jump into the wrapper passes, up to 4 wrapper
levels. This needs the wrapper to have callers and no other way in: it must
not be a program entry, a branch target, an indirect candidate or an
observation. If a wrapper is also a callback target, the runtime enters it
with unknown arguments, so every forwarded target is withdrawn. A caller
with an unproven value leaves that caller's call open as
`unresolved_runtime_callback`.

The solver records the assumption. Natively nothing changes: `plaid_enter`
already enters only proven targets and faults 3 on any other address, so a
broken assumption fails closed.

Result: `tests/forwarded_callbacks.rs` covers both callers' constants, the
guarded scope without callback blockers, and four fail-closed cases:
- the frame escapes;
- a byte store clobbers the slot;
- a caller passes a loaded value;
- the wrapper is also an entry.

spike096's new `forwarded` program enters both callbacks natively and
matches pinned ares exactly. On SM64 (`research/sm64-first-measurement.md`),
discovery grows from 13 blocks to 2936, with 8 guarded blockers and 8.1%
recall. OoT stays at 28 and Mario Party 2 at 29.

## ADR-0150: Disjoint declared loads leave holes in the composite

Context: SM64 loads its engine segment to `0x80378800` and goddard to
`0x8016f000`, both away from the main segment at `0x80246000`. ADR-0136
composes declared loads into one contiguous image and rejected any gap, so 4
of SM64's 8 guarded blockers were calls into code that could not be
declared. Filling a gap with bytes would put BSS and heap inside the image,
where code or table recognition could read them.

Decision: `compose` accepts loads that do not touch the base window or each
other. The composite spans all of them, and every byte that neither the base
window nor a load supplies is a `CodeImage` hole. `CodeImage::word` returns
nothing in a hole, so:
- discovery reports control that reaches a hole as `unmapped_target`;
- table recognition and signature or symbol identification cannot read hole
  bytes.

The image identity covers the hole layout as well as the bytes, through the
new `CodeImage::content_identity`, which the solver's identity check shares.
Loads must still be word-aligned and must not overlap each other.

Natively nothing changes: the artifact preloads only the base window, and
each declared load is verified by content when its code is first entered
(fault 8).

Result:
- `declared_loads` unit tests cover hole layout and word lookup.
- `tests/load_holes.rs` shows that a jump into a hole stays OPEN, while the
  same jump into the declared load decodes and closes.
- The CLI test now discovers and solves a gapped load.
- spike096's new `load_gap` program copies its payload past a gap, calls it,
  and matches pinned ares exactly.

On SM64, declaring the engine and goddard segments grows discovery from 2936
to **5337 blocks**. There are 12 guarded blockers, all function-pointer
calls: render and geo node callbacks, `level_script_execute`'s command
table, the 3 audio dispatches and the goddard vblank pointer. Whole-map
recall is **11.4%** (435/3832). OoT (28) and Mario Party 2 (29) are
unchanged.

## ADR-0151: IDO's jump-table bound in a previous branch's delay slot

Context: SM64's audio sequence interpreter, built by IDO, guards its switch
tables with `slti at, x, C; bnez at, L; sltiu at, i, N`, then
`beqz at, default; sll i, i, 2` and the table load. The bound is the
`sltiu` in the `bnez` delay slot, and the guard block starts after that
slot. ADR-0140's compare check rejected the `bnez` fallthrough as an entry
that bypasses the compare.

Decision: one more edge into the compare-to-guard interval counts as passing
through the bound. It is the fallthrough of a non-likely branch
(`DelaySlot::Always`) whose delay slot is the compare and which lands
directly after it. A branch-likely's fallthrough skips its slot, so the
flag may be stale, and that shape stays rejected.

Result: `tests/tables.rs` covers the IDO shape, which closes, and its
branch-likely variant, which is rejected. The positive test fails without
the change. spike096's new `ido_table` program matches pinned ares.

On SM64, 2 of the 3 audio tables close:
`sequence_channel_process_script` and `sequence_player_process_sequence`.
Discovery reaches 5580 blocks with 10 guarded blockers, and whole-map recall
is 11.5%. The third audio table, in `audio_signal_game_loop_tick`, sets
its bound before a `bnez` whose taken edge reaches the guard, which a
sequential search cannot follow, so it stays open. OoT (28) and Mario Party
2 (29) are unchanged.

## ADR-0152: Heuristic discovery roots from data pointers and layout

Context: after ADR-0151, SM64 recall was 11.5%. Most of the game is reached
only through function pointers held as data: behavior scripts, geo layouts,
level scripts and object tables. A ROM scan found about 983 reference
functions named only by such words. Code also takes addresses with
`lui`/`addiu` pairs, and some functions are referenced nowhere.

Decision: `plaid discover ... --data-roots` is an opt-in flag that adds
heuristic discovery roots. It never adds closure facts. `plaid-core/data_roots`
proposes:
- aligned big-endian words anywhere in the ROM, and `lui r, hi` followed
  within 16 words by `addiu`/`ori` from `r`, whose value is a function start
  in the image;
- in a second pass, after discovery, each address that follows a `jr ra`,
  its slot and any zero padding, when discovery has not already decoded it.
  This skips continuations after an early return, declared runtime functions
  and IDO's dead duplicate `jr ra` epilogue.

A function start must be a valid, non-zero instruction at the image start,
or right after a `jr ra` and its delay slot (with optional padding). The
roots become map entries, which also carry a `plaid-data-pointer-roots/v0`
evidence record. The solver re-derives control flow from every entry, so a
wrong root decodes junk whose blockers keep the map OPEN; it cannot make
anything close.

Result: unit tests cover data, padding and mid-function rejection, and
layout roots that skip decoded code and dead epilogues. The CLI test runs
the flag.

On SM64 (main, engine and goddard), discovery reaches 47976 blocks.
**Whole-map recall is 99.03% (3795/3832)** against the matching decomp map,
which meets milestone 2's 99% target. There are 1760 discovered starts not
in the reference:
- 502 of them are direct call targets, which are `static` functions the map
  does not list (the ELF has no symbols for them either);
- most others are jump-table case labels, which map entries count;
- 124 come from the layout pass.

The missing 37 are mostly unreferenced stubs that begin with `jr ra`, and
IPL3 symbols outside the windows. Under the guarded scope the rooted map has
227 blockers, because the roots decode code that the plain map never reached.

## ADR-0153: Address-taken dispatch scope for register calls

Context: after ADR-0152, SM64's rooted code has about 100 register calls
through function pointers loaded from memory: object behaviors, geo and
render callbacks, goddard draw functions and camera and cutscene tables.
ADR-0142 found no points-to proof for this class. Compiled C can only call a
function whose address it takes, so the closed target set is the
address-taken functions, if that set is complete.

Decision: a new solver scope, `DeclaredStaticImagesGuardedRamAddressTaken`
(`plaid solve ... --address-taken`). It includes everything in the guarded
scope, plus one assumption: every register call (`jalr` with a link
register) without another proof targets an address-taken function.

`plaid discover ... --address-taken` records the set in a new ProgramMap
field, `address_taken`, with `plaid-address-taken/v0` evidence. A function
is address-taken when it is a function start by layout (ADR-0152), its body
up to the first `jr ra` decodes as CPU code with no COP2/COP3 access, and
either:
- an aligned ROM word names it; or
- a `lui`/`addiu` (or `ori`) constant built inside a decoded block names it.
  Constants in undecoded bytes, such as a runtime function's body, do not
  count.

Discovery iterates until no new function appears, and the set's members
stay map entries. Declared runtime functions never join the set.

The solver re-checks the set before it uses it: the set must be non-empty,
and every member must be a decoded block start and still plausible. If any
check fails, every register call stays OPEN. Jump-register sites without a
link (`jr`) never use the set.

`plaid lower-c ... --address-taken` lowers each such call as a dispatch over
the set. Any other target faults 3 at run time. The fault keeps the
assumption checked rather than trusted.

Result:
- The `address_taken` test covers closing over a plausible set, keeping the
  site OPEN under the guarded scope, and voiding the set when one member is
  not a function start.
- spike096 adds `addrtaken` (one target taken by a code constant, one only
  by a data word) and `at_bad`. Both match pinned ares; `at_bad` calls 4
  bytes into a function and faults 3.

On SM64 (main, engine and goddard, `--loads`), discovery reaches 42856
blocks and 1313 address-taken functions. Guarded-scope blockers go from 120
to **32** under the address-taken scope:
- 12 `jr` sites: 11 goddard `switch` tables and 1 audio table;
- 18 TLB and COP0 instructions in `osMapTLB` and `osUnmapTLBAll`, which are not yet
  declared runtime functions;
- 2 from a junk direct target into `rspF3DBootStart`.

The layout pass is not part of this discovery, so recall on this map is
85.5%; milestone 2's 99.03% is measured with `--data-roots`.

## ADR-0154: Jump tables with a load-delay `nop` before the jump

Context: under ADR-0153, 11 of SM64's 12 remaining `jr` sites are goddard
`switch` statements. Goddard is built with IDO without instruction
scheduling, so a load-delay `nop` sits between the table `lw` and the `jr`.
The ADR-0140 pattern needs the `lw` right before the jump.

Decision: when the word before the jump is exactly `nop` (`0x00000000`),
the pattern takes the load from the word before that. The `nop` is part of
the hashed prefix, and any other word there still fails the match, because
it could change the jump register. Everything else (the bound, the guard
and the bypass checks) is unchanged. The `nop` lies inside the guarded
dispatch block, so an entry into it is still a bypass.

Result:
- the `tables` test closes the shape and rejects an `addiu` to the jump
  register in that slot;
- spike096 adds `delay_table`, which matches pinned ares.

## ADR-0155: TLB functions as runtime functions; plausible bodies stay in the image

Context: under ADR-0153, goddard's `load_dynlist` reaches `osMapTLB` and
`osUnmapTLBAll`, giving 18 TLB/COP0 blockers. Separately, SM64's graphics
task holds `rspF3DBootStart` as a data word. That RSP boot microcode
decodes as CPU code up to a `jr ra`, but its second word is
`j 0x84001068`, outside every image.

Decision:
- `RUNTIME_FUNCTIONS` adds `osMapTLB`, `osUnmapTLB`, `osUnmapTLBAll` and
  `osSetTLBASID`. These are the TLB functions N64Recomp lists in
  `ignored_funcs` at the pinned ffb39cd; N64ModernRuntime stubs
  `osUnmapTLBAll`. Like every runtime function, they are a discovery
  boundary under the recorded runtime-ABI assumption.
- An address-taken body (`data_roots::cpu_code`) must also keep every
  direct jump and branch target inside the image. The solver re-checks the
  same predicate.

Result:
- A `data_roots` unit test rejects a body that jumps to `0x84001068` and
  accepts one with an in-image branch.
- SM64 identification finds 56 runtime functions, up from 54.
- SM64 discovery reaches 45388 blocks with 1341 address-taken functions.
  Under the address-taken scope **1 blocker** remains: the
  `audio_signal_game_loop_tick` table, whose bound is computed before a
  taken `bnez` that jumps to the guard. The guarded scope has 92 blockers,
  all register calls.

## ADR-0156: A table bound before the only branch into the guard

Context: after ADR-0155, SM64's last blocker under the address-taken scope
is the table in `audio_signal_game_loop_tick`. The code runs:
1. `sltiu at, s4, 10` sets the bound;
2. `srl t9`;
3. `bnez t9` is taken to a block that starts with the guard,
   `beqz at, default`, with the scale `sll t1, s4, 2` in its slot;
4. the dispatch block follows.

The ADR-0140 walk goes backward linearly from the guard, so it reaches
unrelated code before the guard block and stops.

Decision: suppose the guard's block has exactly one incoming direct edge,
and that edge is a branch or jump with a delay slot. Then the backward walk
moves from the block start to that branch's delay slot and continues there.
- The branch word itself may not write the flag or the index.
- The slot and the words before it are checked as before.
- The bypass check covers both pieces of the path: the compare up to the
  branch's slot, and the guard block up to the guard. That branch is the
  one allowed way into the second piece, so any other entry, edge or
  indirect candidate into either piece rejects the table.
- Everything after the guard is unchanged.

Result:
- The `tables` test closes the shape, and rejects it when the branch's slot
  redefines the index or when a second branch enters the guard.
- spike096 adds `hop_table`, which matches pinned ares.

**On SM64 the solver now reports `closed` under
`DeclaredStaticImagesGuardedRamAddressTaken`, with 0 blockers.** That is
milestone 3. The map covers the main, engine and goddard segments: 45419
blocks, 4385 indirect sites and 1341 address-taken functions.

The scope's assumptions are all printed in the solve report:
- **Checked by the native artifact, with a fault code on violation:**
  address-taken dispatch (3), forwarded callbacks (3), returns (5), data
  accesses and stores (1, 2, 4), table immutability (2), COP1 (7), declared
  load contents (8), overflow traps (6) and BREAK (9).
- **Declared but not checked:**
  - the excluded execution sources (interrupts, exceptions, DMA, MMIO,
    overlays and the RSP);
  - the declared image entries;
  - the runtime-function ABI for 56 identified functions.

  Milestone 4's runtime has to discharge these.

The "Commercial ROMs CLOSED" count stays 0, because it counts whole-ROM
closure with no assumptions.

## ADR-0157: Lower a discovered ROM map; COP1 moves need `rs < 16`

Context: with SM64 closed (ADR-0156), milestone 4 needs the closed map as C.
`plaid lower-c` lowers only synthetic word files.

Decision: `plaid lower-map <rom> <map.json> <entry> <exit> <out.c>` lowers a
discovered map.
1. It rebuilds the map's images from the ROM, as `solve` does.
2. It checks that the map matches the canonical ROM.
3. It takes the declared-load base window as the host preload.
4. It calls the same `lower_c_with_preload`. That function re-solves the map
   and refuses any map that is not `CLOSED`.

Lowering SM64 found a bug in the COP1 data-move arm, which matched
`word & 0x7ff == 0`. `add.s $f0, $f4, $f16` (`0x46102000`) also has zero low
bits, so it was rejected as an unknown move. Moves have `rs < 16`, and the
guard now requires it; the solver's own check already did.

Result:
- spike096's `farith` adds `add.s $f0, $f1, $f2`. Before the fix it fails
  with "outside the lowered subset"; after it, the program matches pinned
  ares.
- `scripts/test_cli.py` lowers a closed CLI map, and `lower-map` refuses an
  OPEN one.
- **SM64:** `lower-map` emits all 45419 blocks in 47 s (a 47 MB C
  translation unit, 56 `plaid_rt_*` runtime entry points). `gcc -O0 -std=c99`
  compiles it in 58 s.
- A local smoke harness stubs `osInitialize` to return and stops at any
  other runtime function. Run natively, SM64 goes from `entry_point` through
  BSS clearing and `main_func` to
  `osCreateThread(&gIdleThread = 0x8033a730, 1, thread1_idle = 0x80246cf0)`,
  matching the decomp map.

Going further needs a host runtime (threads, messages, VI, SP tasks) and a
renderer. That is milestone 4, and it waits on the runtime license choice.

## ADR-0158: License MIT OR Apache-2.0; Plaid's own runtime with RT64

Context: milestone 4 needs a host runtime and a renderer. ADR-0126 planned
N64ModernRuntime, which is GPL-3.0 and would make every generated game
application GPL-3.0. The owner delegated the choice and preferred Plaid's
own stack, provided that is not too much work. RT64 (MIT) already
implements N64 rendering, shaders included, on D3D12, Vulkan and Metal.
Writing our own renderer would cost years and prove nothing about Plaid's
claim.

Decision:

1. **License.** Plaid is `MIT OR Apache-2.0`, in `LICENSE-MIT`,
   `LICENSE-APACHE` and every crate manifest. A reuse audit found no GPL code
   outside `instruments/mupen/`, which ADR-0006 already keeps as a separately
   licensed GPL instrument with its own `COPYING`. That directory is excluded
   from the grant. The reused N64Recomp symbol lists and the n64sym
   matching rule are MIT, and the ares-derived spike drivers are ISC; each
   is already credited where it is used.

2. **Runtime.** Milestone 4 uses Plaid's own permissively licensed host
   runtime, `runtime/`. It implements the declared runtime functions
   (`plaid_rt_*`) that lowered code calls. N64ModernRuntime stays a
   reference to read, never copied.
   - The runtime is written in C (C11 with pthreads), not Rust. Lowered
     programs are C translation units whose `plaid_state` layout comes from
     `plaid-lower`, and the renderer is C++. A C runtime links into the
     same build with no mirrored struct layouts.
   - Guest threads run on host threads under one baton: exactly one guest
     thread executes at a time, as on the single VR4300. A handoff saves
     the CPU register file from the shared `plaid_state` into the outgoing
     thread and restores the incoming one. RAM is shared.
   - Events (VI retrace, SP/DP completion, timers, PI) are libultra
     messages, posted by host-side sources and delivered at scheduling
     points.
   - A thread that never calls the runtime, such as an idle `while (1);`,
     must still be preemptible. `plaid-lower` will emit a safepoint check
     at every backward transfer, verified like every lowering change.
   - Runtime writes to guest RAM (PI DMA, controller data) go through
     `plaid_runtime_write`. Its executable-byte and declared-load checks
     still apply.

3. **Rendering.** RT64 consumes the game's display lists at `osSpTaskStartGo`
   for graphics tasks. Audio tasks go to a Plaid-owned audio path (HLE of
   the audio microcode, or a reference HLE such as the one in
   N64ModernRuntime's ecosystem if its license allows). That waits for a
   later milestone 4 step.

Consequences:
- ADR-0126 step 2 is superseded: N64ModernRuntime is not linked.
- A generated game application is under Plaid's license plus RT64's MIT
  terms. The user still supplies the ROM.
- Runtime behavior is tested by deterministic synthetic programs that call
  runtime functions, and by the SM64 native run reaching named checkpoints.
  The first checkpoint is the first graphics task.

## ADR-0159: Plaid runtime core, loop safepoints and a word protection map

Context: ADR-0158 chose Plaid's own C runtime. Lowered SM64 reaches
`osCreateThread` with stub runtime functions (ADR-0157). Going further needs:
- libultra threads, message queues and events;
- PI DMA from the ROM;
- a way to preempt a thread that spins without calling the runtime, such as
  SM64's idle `while (1);`.

Decision:

1. **`runtime/plaid_rt.c`** (MIT OR Apache-2.0, C11 and pthreads) implements
   the 56 runtime functions SM64 declares. It is built as one translation
   unit with the lowered program.
   - **Threads.** Each guest thread is a host thread, but only the holder of
     one baton runs guest code. A handoff saves and restores the CPU
     register file in the shared `plaid_state` and re-applies the FCSR
     rounding mode, which is per host thread.
   - **Scheduling.** The highest priority runs, FIFO within a priority.
     Starting or waking a thread of higher priority preempts the current
     one at once, and lowering your own priority yields.
   - **Message queues.** They live in guest RAM in the `OSMesgQueue` layout.
     Blocked threads are kept host-side.
   - **Events.** VI retrace runs at 60 Hz. Timers, SP/DP completion, SI and
     PI messages are marked pending by host sources and delivered only by
     the baton holder, so guest RAM has one writer. When every thread is
     blocked, the event pump delivers them itself.
   - **PI DMA** copies ROM bytes through `plaid_runtime_write`, so
     executable and verified-load bytes stay protected.
   - **Controllers, EEPROM, 64-bit helpers.** One standard controller and a
     4 Kbit EEPROM; `__ull_*` and `__ll_*` take o32 register pairs.
   - **Graphics tasks.** These report their task and display list (the
     first-frame checkpoint). Until RT64 is attached, both graphics and
     audio tasks complete immediately.

2. **Loop safepoints.** `plaid-lower` emits `PLAID_SAFEPOINT(s)` at every
   loop header, meaning the target of a backward direct transfer or of a
   backward table case.
   - Within a function, every other transfer moves forward and calls
     return. So a run that never returns passes a header again and again,
     and its preemption latency is bounded.
   - Without `PLAID_SAFEPOINTS` the macro is empty. The runtime build
     defines it as a check of `plaid_preempt`.

3. **Word protection map.** The store guard scanned every `plaid_code`
   range on every guest store: 45566 ranges for SM64. Executable ranges are
   word-aligned, so a per-word map built once from `plaid_code` (`prot` in
   `plaid_state`) answers the same question in constant time. It covers
   always-protected code, and code of declared load *n* once that load is
   verified. The guest store guard and `plaid_runtime_write` both use it.

Result:
- `runtime/test_runtime.py` lowers a synthetic program with three threads
  and checks the libultra order exactly: `1,2,3,7,4,5,0x99`. That order
  covers:
  - preemption on start and on send;
  - a blocking receive;
  - a priority drop;
  - a VI retrace preempting a spinning thread at its safepoint.

  It passed 6 of 6 runs.
- A `lower` test checks that only loop headers get safepoints.
- spike096 builds every program with `PLAID_SAFEPOINTS` and a runtime that
  takes every safepoint. All programs still match ares, and every
  fail-closed fault code is unchanged, including the store-guard faults 2.
- **SM64 runs natively to its first graphics task:** Fast3D microcode
  `0x8032b330` and a display list that begins with `G_MOVEWORD` segment
  setup. With the protection map it reached 3 graphics tasks in 11 VI
  frames, against 397 frames for the first task before it.

## ADR-0160: The COP1 register mode is a declared map property; libultra runs FR = 0

Context: lowered SM64 faulted 7 in `mtxf_lookat`. The code built the double
`1.0` with `mtc1 $at, $f11; mtc1 $zero, $f10`, an even/odd register pair. So
SM64 runs COP1 with Status.FR = 0, as libultra threads do: libultra never
sets FR. Lowering assumed FR = 1 (ADR-0131) and read `$f10` as `0.0`. The
fault caught this only because the divisor was 0. Any other value would have
given a silently wrong result, and the solver's listed assumption
("Status.FR = 1") was false for the game.

Decision: `ProgramMap.cop1_fr0` declares the mode. `discover --fr0` and
`lower-c --fr0` set it; it defaults to false, and merging rejects maps whose
modes conflict. The solver lists the declared mode as its COP1 assumption.
Under FR = 0, lowering follows pinned ares (`interpreter-fpu.cpp`, fgr_t,
fgr_s and fgr_d) exactly:
- arithmetic, compare, convert and move sources (fs) and 64-bit transfers
  (`DMFC1`, `DMTC1`, `LDC1`, `SDC1`) use the even register of the pair;
- a 32-bit transfer (`MFC1`, `MTC1`, `LWC1`, `SWC1`) of an odd register reads
  or replaces the upper word of its even partner;
- ft and fd index the register itself, as in ares.

FR = 1 output is unchanged.

Result:
- The spike096 ares driver takes an optional `fr0` argument; the oracle was
  rebuilt with `--rebuild`. The new `fpu_fr0` program matches ares running
  with Status.FR = 0. It builds doubles from 32-bit moves, uses odd
  `MFC1`/`LWC1`/`SWC1`, an odd `DMFC1` and an odd single-precision source.
- A `lower` test checks the odd-word mapping and the masked source.
- The CLI test checks that `--fr0` is recorded.
- SM64 is rediscovered with `--fr0`. It stays `closed` under the
  address-taken scope, and its report now lists Status.FR = 0.
- **SM64 now runs natively for 96 graphics tasks in 196 VI frames.** That is
  the game's own 30 fps, through the intro. The run stops with fault 2
  inside `bzero`, called from `load_to_fixed_pool_addr` on `0x8016f000`:
  the menu clears goddard's fixed-load region in order to DMA it again.
  Declared loads are protected for good once verified (ADR-0136), so the
  native code fails closed here. ADR-0161 gives loads a lifetime.

## ADR-0161: A verified declared load lives until its code bytes are written

Context: ADR-0136 verifies a declared load at the first entry into its code
and then protects its executable bytes for the rest of the run. SM64 reloads
goddard: when the menu returns, `load_to_fixed_pool_addr` clears the fixed
region at `0x8016f000` with `bzero` and DMAs the segment again. The
permanent protection aborted that `bzero` (fault 2), although the program
was only replacing a load with the same bytes.

Decision: verification has a lifetime.
- A store or runtime write (such as PI DMA) into a verified load's
  executable bytes clears that load's `load_ok`; it is not a fault.
  `plaid_protected` does this in the same per-word map lookup (ADR-0159).
- Every block of a load's code already begins with
  `if (!s->load_ok[L] && plaid_verify_load(...))`. That includes the return
  point after each call, because a call ends its block. So the next block
  entered compares RAM with the declared bytes again. A match re-verifies;
  a mismatch aborts with fault 8, as before.
- A store by the load's own code into its own executable bytes still aborts
  with fault 2. That is self-modifying code, and the running block could not
  be re-checked before its next instruction.
- Base-image code and jump tables stay protected for good.

Native code therefore never runs a block of a load whose RAM differs from the
declared bytes. A writer in another segment can no longer return into stale
code, since the return point is a block start and re-verifies. The solver's
declared-load assumption text says so.

Result:
- spike096 adds `load_reload`, which runs a load, clears and copies it again,
  then runs it again; it matches ares.
- `load_patch` patches a verified load from outside and re-enters it; it now
  fails closed with fault 8 at the re-entry, where it used to fail with
  fault 2 at the store.
- The new `load_self`, a load writing its own code through KSEG1, fails
  closed with fault 2.
- SM64 runs past the goddard reload: 96 graphics tasks and 395 PI DMAs
  (269 before). It then fails closed with fault 1 in goddard's
  `load_dynlist`, which reads dynlists through `osMapTLB` mappings at
  virtual `0x04000000`. ADR-0162 handles TLB-mapped data.

## ADR-0162: TLB-mapped data, with D-cache index aliasing

Context: after ADR-0161, SM64 failed closed (fault 1) in goddard's
`load_dynlist`. It DMAs the dynlists segment into the heap, maps that segment
at virtual `0x04000000` with `osMapTLB` (64 KiB pages), and walks pointers
there. `plaid_addr` accepted only KSEG0 and KSEG1, and `osMapTLB` was a no-op
runtime function (ADR-0155).

Decision:
- **TLB state.** `plaid_state.tlb[32]` holds each entry as TLBWI writes it:
  PageMask, EntryHi, EntryLo0 and EntryLo1.
- **Runtime functions.** `osMapTLB` packs the entry as libultra does: the
  page frame, noncoherent cached, dirty and valid, with -1 leaving a page
  invalid. `osUnmapTLBAll` points every entry into KSEG0, where no mapped
  address can match. `osVirtualToPhysical` translates mapped addresses.
- **Translation.** `plaid_addr` translates KUSEG, KSSEG and KSEG3 data
  accesses as pinned ares (`tlb.cpp`) matches them: the first entry whose
  VPN2 matches under its page mask decides, and the even or odd page is
  chosen by the page-size bit.
- **Fail-closed cases.** Lowered code models global entries only. So these
  all fault 1, where hardware would raise an exception:
  - a matching entry with an ASID (the runtime refuses to write one);
  - an invalid page;
  - a store to a clean page.
- **Cache index.** ares showed that the VR4300 D-cache is indexed by
  `vaddr[12:4]`. A 4 KiB page whose virtual bit 12 differs from its physical
  bit 12 caches a line at a different index than KSEG0 does, and the two
  views diverge. The per-line cache class (ADR-0126's fault 4) therefore
  gains a third value: cached at the other index. Any mix of classes on one
  line faults 4. goddard's 64 KiB pages always keep bit 12, so they never
  alias.

Result:
- spike096 adds `tlb`. On ares it maps entries with real MTC0 and TLBWI;
  natively the runtime writes the same entries. The program stores through a
  4 KiB even page, its odd page and a 64 KiB page, then reads back through
  KSEG2, KSEG0 and a second mapping at the same cache index. It matches ares.
- Three new programs fail closed:
  - `tlb_invalid` (fault 1);
  - `tlb_clean` (fault 1);
  - `tlb_alias` (fault 4). It is the case ares showed: a mapped store at the
    other index, then a KSEG0 read.
- SM64 no longer faults. In a 90-second native run it reaches the time limit
  after 2939 VI frames, 1459 graphics tasks (30 fps), 2931 audio tasks and
  9861 PI DMAs, with no fault. Display lists are reported but not drawn
  until RT64 is attached.

## ADR-0163: Graphics tasks go to RT64 through a C ABI bridge

Context: after ADR-0162, SM64 ran natively without faults, but its graphics
tasks were only reported. ADR-0158 chose RT64 (MIT, pinned 4337374) for
rendering.

Decision:
- **Bridge.** `runtime/rt64/plaid_rt64.cpp` (MIT OR Apache-2.0) builds
  `plaid_rt64.dll`: RT64 as a static library behind four C functions,
  `plaid_gfx_open`, `plaid_gfx_task`, `plaid_gfx_screen` and
  `plaid_gfx_closed`. So the gcc-built runtime and the MSVC-built renderer
  share only a C ABI. `runtime/rt64/CMakeLists.txt` builds it from the
  pinned checkout.
- **One renderer thread.** It owns the RT64 application and its SDL window,
  runs every RT64 call and pumps window events. Callers wait for each job.
- **RAM layout.** Plaid's guest RAM is big-endian, while RT64 reads RDRAM as
  host-order 32-bit words. Before each task the bridge copies in, swapped,
  only the words the guest changed since the previous task. So bytes RT64
  itself wrote to RDRAM, such as resolved framebuffers, survive unless the
  guest overwrote them.
- **Tasks.** `osSpTaskStartGo` hands a graphics task to the bridge. The
  bridge selects RT64's microcode from the task's `ucode` and `ucode_data`
  and interprets `data_ptr` as an HLE display list. SP and DP completion are
  still posted by the runtime.
- **VI registers.** The runtime derives them the way libultra's retrace
  handler does: from the `OSViMode` passed to `osViSetMode`, the framebuffer
  passed to `osViSwapBuffer`, and the `osViBlack` flag. It presents them on
  every VI retrace. Special features and the second interlace field are not
  modeled (a commented shortcut; SM64's non-interlaced mode needs neither).
- **Build.** `-DPLAID_RT64` turns the bridge on. Without it the runtime is
  unchanged. Building RT64 needs D3D12 headers newer than Windows SDK 22621,
  taken locally from Microsoft's DirectX-Headers (MIT) under `target/`.

Result:
- `runtime/test_runtime.py` adds a renderer-bridge check that needs no GPU.
  A stub `plaid_gfx_*` records the VI registers derived from a synthetic
  `OSViMode` and framebuffer, the task's ucode, data and display-list
  addresses, and the display-list word read from the big-endian RAM handed
  over.
- **SM64 boots natively to its title screen.** On an RTX 3060 under D3D12,
  RT64 draws the animated goddard Mario head over the "SUPER MARIO 64"
  backdrop with "PRESS START". This was checked by local screen captures,
  which stay out of git.
- In a 25-second run there is no fault: 404 graphics tasks and 818 VI
  frames. That is about 33 VI per second rather than 60, so the build runs
  slow. This is the speed baseline (`-O1`, a synchronous bridge with an
  8 MiB compare per task); no tuning is done before it is recorded.

## ADR-0164: Controller 1 from scripted presses and the renderer window

Context: after ADR-0163, SM64 stopped at "PRESS START", because
`osContGetReadData` reported an idle controller.

Decision: `osContGetReadData` fills controller 1's `OSContPad` (buttons,
stick, errno). Its buttons are the OR of two sources:
- **Scripted presses:** `--press <buttons>@<vi>:<frames>`, keyed to the VI
  frame count, so runs and tests are reproducible without a person.
- **The keyboard:** read from the RT64 window by the bridge
  (`plaid_gfx_input`) and mapped as follows:
  - X, C, Z: A, B, Z;
  - Enter: START;
  - Q, E: L, R;
  - I, K, J, L: the C buttons;
  - W, S, A, D: the D-pad;
  - the arrow keys: the stick.

Controllers 2 to 4 report absent (errno 8). Scripted presses set buttons
only, not the stick (a commented shortcut).

Result:
- `runtime/test_runtime.py` checks the merge with a stub window. A press due
  now is reported, a later press is not, the stick comes through, and
  controller 2 is absent.
- **SM64 gets past the title natively.** START at VI 600 and three A presses
  pass the title and the file select. The game then plays the intro: Peach's
  letter, then Lakitu over the castle grounds. A 60-second run has no fault:
  2014 VI frames, 994 graphics tasks and 3360 PI DMAs. That is 33.5 VI/s,
  the same speed as the ADR-0163 baseline.

## ADR-0165: The EEPROM persists in a save file

Context: the runtime's 4 Kbit EEPROM lived only in memory, so a native game
lost its save when it exited.

Decision: `--save <file>` names a 512-byte EEPROM image.
- **Loading.** The image is loaded at start. A missing file means a blank
  EEPROM. A file of any other size is refused (exit 2) and never
  overwritten.
- **Writing.** After every `osEepromWrite` or `osEepromLongWrite` the image
  is written to `<file>.tmp` and then renamed over `<file>`. An interrupted
  write therefore leaves either the previous save or the complete new one.
- **Recovery.** If only `<file>.tmp` exists, because the run stopped between
  removing the old file and renaming the new one, it is loaded instead.

Result: `runtime/test_runtime.py` runs a program that reads EEPROM block 1,
increments a counter and writes it back.
- Two runs read 0 and then 1.
- The file holds exactly the expected 512 bytes.
- No temporary file is left behind.
- A 100-byte file is refused and left unchanged.

## ADR-0166: VI retraces at NTSC rate on Windows

Context: native SM64 produced 32.7 VI frames per second, with or without
RT64 (2939 in 90 s; 818 in 25 s). That runs the game at about half speed.
The cause was timing, not rendering:
- On Windows, mingw's `nanosleep` rounds 1 ms up to the ~15.6 ms system
  timer tick (measured 15.64 ms on average).
- The event pump posted a VI only once 16.68 ms had passed since the last
  one, so it posted on every second tick, about every 31 ms.

The timers and the delivery to blocked threads had the same 15.6 ms
granularity.

Decision:
- **Sleep.** On Windows the pump sleeps on a high-resolution waitable timer
  (`CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`; measured 1.66 ms for a 1 ms
  wait). Elsewhere, or if that timer is unavailable, it uses `nanosleep`.
- **VI deadlines.** Retraces fall on fixed deadlines of 16 683 350 ns
  (60000/1001 Hz), so sleep jitter no longer stretches the period. A host
  stall longer than a frame drops the missed retraces rather than bursting
  them.

This changes no guest-visible semantics; it restores the intended VI rate.
ADR-0163's 33 VI/s baseline was measured with this bug.

Result:
- `runtime/test_runtime.py` asserts 54 to 62 retraces in one second. Three
  runs gave 60, 60 and 61.
- **SM64 runs at full speed.** A 60-second RT64 run with the ADR-0164 script
  gives 3596 VI frames (59.9 VI/s) and 1784 graphics tasks (29.7 fps, the
  game's own rate), with no fault. The game reaches gameplay: Mario in the
  castle grounds with the HUD up. The native code keeps up without any
  tuning.

## ADR-0167: RSP scalar microcode lowers to C

Context: SM64 is silent. Its audio thread sends RSP audio tasks, and the
runtime completes them at once without running them. The RSP runs
microcode that the game ships, so audio needs that microcode as native
code, the same way the CPU code is native. SM64's audio microcode
(`rspAspMainStart`, 0xe20 bytes at IMEM 0x080) has 489 scalar, 37 COP0
and 211 vector-unit (COP2) instructions, plus 108 LWC2 and 59 SWC2.

Decision: `plaid lower-rsp <rom> <offset> <size> <imem> <name> <out.c>
[--raw]` lowers a microcode text to `int plaid_rsp_<name>(plaid_rsp *r, u32
pc)`. It runs from `pc` until the microcode halts (returns 0) or faults
(returns 1). This ADR covers the scalar unit and COP0; any other
instruction, the vector unit included, is a lowering error.
- **Closed control flow by construction.** IMEM is 4 KiB and its text is
  fixed: DMA into IMEM faults. So every text word gets a label, and
  `jr`/`jalr` dispatch through a switch over exactly those labels. A target
  outside the text, a misaligned target, or running off the end faults 3. A
  transfer in a delay slot is a lowering error.
- **Semantics from pinned ares** (ISC, `ares/n64/rsp`): 32-bit registers,
  ADD/SUB without overflow traps, DMEM accesses byte-wise big-endian with
  each byte address wrapping at 4 KiB, and 12-bit link and branch
  addresses. BREAK sets broken and halted.
- **COP0** follows ares `io.cpp`: DMA addresses and lengths, SP_STATUS with
  its signals and halt, and the semaphore. Writing halt stops the
  microcode. DMA completes as soon as it is started, so the busy and full
  bits read 0. DMA into IMEM faults 2, DMA outside RDRAM faults 1, and the
  RDP command registers (COP0 8..15) fault 4 until a microcode needs them.

The host runs the lowered function on the RSP state that the task names.
No RSP interpreter is linked.

Result: `spikes/097-rsp-slice` assembles microcode at IMEM 0x080. Each
program is lowered, compiled, and run on pinned ares (9408cb43) from the
same IMEM, DMEM and RDRAM images. The final PC, the broken flag, all 32
registers, all of DMEM and RDRAM 0..0x2000 match for five programs:
- **alu**: every scalar ALU and shift form, writes to `$zero`, and
  sign-extended SLTIU.
- **mem**: every load and store width, unaligned addresses, and DMEM wrap.
- **branch**: every branch kind taken and not taken, links, J/JAL,
  JR/JALR through computed addresses, and a loop.
- **dma**: row DMA with a skip in both directions, the DMA registers read
  back, the semaphore, and SP_STATUS signals set and cleared.
- **halt**: the microcode halts itself through SP_STATUS.

A jump outside the text faults 3, DMA into IMEM faults 2, DMA beyond RDRAM
faults 1, and an RDP register faults 4. Unit tests cover the closed
dispatch, refusing vector and unknown instructions, and delay-slot errors.
On SM64's audio microcode the lowering stops at the first vector
instruction, a `vxor` at IMEM 0x1f0. The vector unit is ADR-0168.

## ADR-0168: The RSP vector unit lowers to ported C

Context: ADR-0167 lowers scalar RSP code but refuses COP2, LWC2 and SWC2.
SM64's audio microcode first uses a vector instruction at IMEM 0x1f0, and
more than a third of its instructions are vector instructions.

Decision: the RSP prelude gains the vector unit, ported from the scalar
(SISD) paths of pinned ares `interpreter-vpu.cpp` and the tables in
`rsp.cpp` (ISC):
- the state: 32 registers of eight halfwords, the 48-bit accumulator as
  three slices, the VCO, VCC and VCE flags, and the divide latch;
- the element selector;
- every load and store form, with DMEM wrapping per byte;
- the COP2 moves;
- every multiply, accumulate, add, compare, clip, logic and divide op.

Each instruction lowers to a call into this code with its fields as
constants. Encodings that ares runs as VZERO (VSUT, VADDB to VSUM, the
VEXT and VINS group), LWV, other LWC2 and SWC2 opcodes, and invalid COP2
moves are lowering errors. No microcode is known to use them, and their
hardware meaning is unverified. VNOP and VNULL lower to nothing.

The oracle is built with SSE4.1, so ares runs its SIMD paths there. The
differential test therefore also checks that the ported scalar paths agree
with ares's SIMD paths.

Result: spike097 adds 20 programs to its five scalar ones, assembled from
fixed seeds. All match pinned ares 9408cb43 in registers, all of DMEM, the
vector registers, the accumulator and the flags. The four negatives still
fault.

| Programs | What they cover |
| --- | --- |
| `vec0`..`vec7` | Every computational op on edge and chained values, with random element selectors and preset flags. vd, the accumulator and the flags are stored after each op. |
| `vflag0`..`vflag3` | Compare, clip, merge and carry ops chained on small-range values, with VCH then VCL forced so VCL reads VCH's VCE. |
| `vacc0`..`vacc2` | Accumulate chains that carry the 48-bit accumulator past 32 bits in both directions. |
| `vload0`, `vload1` | Every LWC2 form at every element, at random offsets and addresses, including DMEM wrap. |
| `vstore0`, `vstore1` | Every SWC2 form at every element, each into its own slot; the last slots wrap. |
| `vmove` | MTC2 and MFC2 at every element, and CTC2 and CFC2 on every control register. |

A mutation check broke six details of the port one at a time, and spike097
caught all six: VMULQ rounding, VCL's carry under VCE, the SFV element
order, the LRV start, the VRSQ shift and VMACU's clamp. The first version of
the programs missed three of them; the flag, accumulator and per-element
programs were added for those. Unit tests cover the decode and the refused
encodings.

SM64's audio microcode (`plaid lower-rsp` at ROM 0xe7740, 0xe20 bytes, IMEM
0x080) now lowers completely: 904 instructions. The result compiles with
`-Wall -Wextra` without warnings. Running audio tasks with it is ADR-0169.

## ADR-0169: RSP tasks run lowered IMEM snapshots

Context: ADR-0167 and ADR-0168 lower RSP code from a ROM offset that someone
has to find for each game. On hardware, libultra loads only a small boot
microcode into IMEM. The boot code then DMAs the task's real microcode over
IMEM, including the words it is running from. Those load addresses and
sizes are game data: SM64 passes `ucode_size` 0x800 with a note that it is
ignored. Lowering per ROM offset would not carry over to another game.

Decision: IMEM is plain bytes, and DMA can write it (fault 2 is gone). A
lowered text is a 4 KiB IMEM snapshot, located by running the game, not by a
ROM offset:
- **Liveness.** Every text carries its bytes. On entry, and after any mtc0
  that DMAed into IMEM, it marks which of its words IMEM still holds. Each
  word it no longer holds, and each transfer whose delay slot it no longer
  holds, leaves the text (return 2, with `r->pc`). So does every target
  outside the text, and the register-jump dispatch default.
- **Selection.** The runtime runs a registered text that covers the PC and
  whose word at the PC matches IMEM. A text that left at a PC is not chosen
  again for that PC until IMEM changes.
- **Fail closed.** When no text holds the word, the task stops with
  "unlowered RSP code". With `--rsp-dump <dir>` the runtime saves IMEM as
  `imem-<pc>-<fnv32>.bin` first. `runtime/rsp_texts.py` lowers each
  snapshot whole and writes the registry, so the next build runs further.
  Words a whole snapshot cannot lower, such as leftover data, become fault-6
  stubs instead of lowering errors, and are reported.
- **Task start.** `osSpTaskLoad` does libultra's work for tasks other than
  graphics:
  - it copies the task to DMEM 0xfc0 with its seven pointers made physical;
  - it puts `ucode_boot` in IMEM 0.
  `osSpTaskStartGo` runs from PC 0 until the RSP halts, then posts the SP
  event. Yielded tasks other than graphics fail.
- **RDRAM writes.** RSP DMA into RDRAM goes through `plaid_runtime_write`,
  with the CPU's write checks.
- **DPC_STATUS.** Reads return 0x80, an idle RDP, ready. Graphics tasks have
  completed whenever another task runs here, and ares reads the same at
  power. The other RDP registers still fault 4.
- **Audio out.** `osAiSetFrequency` follows libultra's divider. `--wav
  <file>` writes each `osAiSetNextBuffer` buffer as 16-bit stereo PCM.
  `osAiGetLength` returns 0, which means no host playback timing yet.

Nothing in this is specific to SM64: the boot code, the microcode and its
location all come from the game at run time.

Verification:
- spike097 against ares 9408cb43:
  - `dma_imem` DMAs into IMEM and reads it back;
  - `dpc_status` reads the idle RDP;
  - `imem_stale` faults after running code that a DMA overwrote, when no
    text holds the new bytes.
- `runtime/test_runtime.py` runs a boot-plus-ucode task, shaped like
  rspboot, through the snapshot protocol:
  - two runs save the boot and ucode snapshots;
  - the third run computes and DMAs out the expected RDRAM words and the
    vector sums, and posts the SP event.
- spike098 (new) loads a captured task (`--rsp-capture <n> <dir>`) into
  ares: all of RDRAM, IMEM and DMEM plus the scalar, vector and status
  state. It runs the task to halt and compares everything with the native
  result.

Result: SM64 needs two snapshots:

| Snapshot | Contents | Fault stubs |
| --- | --- | --- |
| IMEM 000 | rspboot | none |
| IMEM 080 | aspMain | 26, all in leftover bytes past the microcode |

With them, SM64 runs 20 seconds with 1190 audio tasks and no fault. A 30
second WAV at 32006 Hz carries the intro and title audio; the user listened
to it and confirmed it sounds right. spike098 matches
pinned ares exactly on two real tasks:
- task 1: 6478 instructions;
- task 600: 94150 instructions, 2972 RDRAM bytes of mixed audio.

Captures, snapshots, lowered C and the WAV are game-derived and stay local.

Next: ADR-0170 plays the samples on the host in real time, with AI length
timing.

## ADR-0170: AI DMA is timed, and audio plays on the host

Context: ADR-0169 runs SM64's audio tasks natively, but `osAiGetLength`
returned 0 and nothing played. Games pace audio from the AI: SM64 sizes
each frame's buffer from the samples still queued (`osAiGetLength`), and
other games wait for the AI event or test `osAiGetStatus`. With a length of
0 SM64 overproduced by about 4%, so live output would drift and build up
latency.

Decision: the runtime models the AI as pinned ares does (`ai/ai.cpp`,
`ai/io.cpp`):
- **FIFO.** A two-entry DMA FIFO of buffer lengths, 18 bits rounded down to
  8 bytes. `osAiSetNextBuffer` returns -1 while both entries are taken,
  like libultra's busy check.
- **Draining.** Once `osAiSetFrequency` turns DMA on, the head drains one
  4-byte sample per DAC period on the runtime's host clock, at the rate
  libultra derives from the NTSC VI clock. When it empties, the next buffer
  starts at that instant.
- **AI event.** Raised when a buffer enters an empty FIFO and when the next
  buffer starts, as the AI interrupt is. The event pump checks every
  millisecond.
- **Registers.** `osAiGetLength` reads the bytes left in the playing
  buffer. `osAiGetStatus` reads full (bits 31 and 0), busy (30), DMA on
  (25) and the constant bits 24 and 20.
- **Playback.** With RT64, each buffer is also handed to the shim
  (`plaid_audio_play`), which plays it through SDL at the AI rate. The
  model and the device run on different clocks; if more than 200 ms queue
  up, the queue is dropped rather than resampled. Without an audio device,
  the game runs silent.

Verification: `runtime/test_runtime.py` runs a guest program against a
host-audio stub:
- three buffers are offered and the third is refused;
- the status bits are checked full, busy and idle;
- the second AI event arrives one buffer of DAC time after the first (the
  measured COUNT ticks are within 0.8 to 1.5 of 1024 samples);
- the FIFO drains to length 0;
- the WAV file and the host hook get the right samples.

Result: SM64, relinked, runs 30 seconds with no fault: 1768 audio tasks,
with sound playing through SDL. Its audio now keeps pace with the run:

| `osAiGetLength` | WAV audio from a 30 s run |
| --- | --- |
| always 0 (before) | 31.3 s, about 4% too much |
| ADR-0170 model | 29.5 s; the AI starts about 0.5 s in, after boot |

The user played it past the title with live audio and confirmed it works.

Nothing here is specific to SM64: it is the AI register model, and the
playback takes whatever buffers the game sends.

## ADR-0171: Runtime functions named from the ROM's own bytes

Context: milestone 5 retires SM64's declared assumptions one by one. One of
the two that no native check backs is the runtime ABI (assumption 11 of the
address-taken scope): the declared functions really are the libultra
functions of their names. All 56 of SM64's names came from its decomp
symbol map (ADR-0148). That map is an external oracle, and most games have
none. n64sym signatures alone found 49 names, and 51 with the declared
loads. Two names came back ambiguous:
- `__ull_rem` matches relocation-free code at two addresses. The second
  copy is the game's `__ll_rem`, which compiles to the same instructions.
- The `osEepromLongWrite` signature matches both `osEepromLongWrite` and
  `osEepromLongRead`. The two differ only in the `jal` at offset 0x44,
  which the signature masks as a relocation to `osEepromWrite`.

`osInitialize` and `osContInit` match no n64sym variant: SM64's SDK build
is not in its database.

Decision: identification uses more of what the signature file already
says, and records where each name comes from.
- **Call relocations.** Each `.targ26` relocation names the symbol it
  calls. If that symbol is identified elsewhere, the matched `j`/`jal` must
  target its entry, or that signature variant is dropped. This repeats
  until nothing changes. A relocation to an unidentified symbol constrains
  nothing.
- **Identical copies.** A name may stand at several addresses when none of
  its matching variants has a relocation, so every copy is the same code.
  The ProgramMap now allows a runtime name at several entries if each
  declares the same callbacks. Lowering is keyed by address, so each copy
  calls the one host function.
- **Reference map as fallback.** `identify <rom> ... <sigs> --reference-map
  <map>` takes the signatures first. It adds a map name only when the ROM
  leaves it open. A map name that a signature puts elsewhere, or at an
  address a signature names otherwise, disagrees with the ROM: it is
  dropped and reported as ambiguous.
- **Evidence per function.** Each declared function records `evidence:
  signature` or `reference map`. `discover` gives map-only names their own
  evidence record, and the solver states them in a separate assumption.
  Older `--symbols` files count as map-only throughout.

Verification:
- unit tests:
  - a call relocation separates two otherwise identical bodies, and stays
    open while its callee is unidentified;
  - relocation-free copies name every address;
  - the map fills only open names and drops both kinds of disagreement;
- `scripts/test_cli.py` covers the combined identification, the
  per-function evidence and the solver's map-only assumption.

Result on SM64 (main, engine and goddard, `--loads`):
- Signatures alone identify 53 names at 54 entries, with nothing
  ambiguous. `__ull_rem` is identified at both of its copies, and
  `osEepromLongWrite` at its own address only.
- With `--reference-map`, the decomp map adds only `osInitialize`,
  `osContInit` and `osEepromLongRead`, down from 56 names.
- Discovery and the solver still reach **`closed`** over 45419 blocks
  under the address-taken scope. The new assumption names those three
  functions.

The rest of the runtime-ABI assumption stands: host functions replace
guest bodies.

The same scope measured on Ocarina of Time (boot plus the Yaz0 `code`
segment) gives 9764 blocks and 13 blockers:
- 5 in exception-return code (`eret`);
- 3 calls into the 64DD driver, which is not on the cartridge;
- 4 unresolved direct targets.

OoT's game states and actors are relocatable overlays loaded at heap
addresses, which no scope covers yet. That is the next milestone 5 piece.

## ADR-0172: ROM-owned relocatable overlays with checked load bindings

Milestone 5. The fixed OoT image excludes heap-loaded game states, actors and
effects. A native overlay must retain its link-time identity while executing
with the actual load address. Finding a table is not a closure certificate.

Design:
- Discover descriptions from the ROM's own file and overlay tables, with no
  title, actor ID, ROM offset or table address in the recognizer. The initial
  format profile is Zelda64's 16-byte file table and section-relative MIPS
  relocation trailer. Other formats require their own explicit profiles.
- Lower each executable overlay at its link address. Relocated immediates and
  links use a checked section binding, following N64Recomp's section-address
  model at pinned MIT revision `ffb39cdad1da5de07eaaa48bd1db4a89a7986771`.
- A runtime binding must identify one candidate and its real RAM address,
  compare relocated executable bytes before first entry, and reject mismatch
  or ambiguity. Writes revoke a binding; an active overlay cannot modify its
  own protected code. Returns, indirect targets and pointer tables must use
  that binding's generation. This extends ADR-0136/0161, not a general claim
  that arbitrary heap bytes are executable.
- Relocation semantics and relocated execution need independent synthetic
  checks against ares before the runtime path can be accepted. No decoder or
  MIPS fallback belongs in that path.

Implemented first stage:
- `inspect-overlays <rom> <map.json> <out.json>` rebuilds the map's source
  images from the ROM and emits candidates bound to those image identities.
- The file table must be unique, sorted, terminated and contained in its own
  uncompressed file entry. Decoding is bounded by the declared file size.
- Overlay tuples must agree with an actual file and its text/data/rodata,
  relocation trailer and BSS span. The trailer precedes BSS in RAM; a
  zero-text data overlay is valid but supplies no executable text.
- MIPS 32/26/HI16/LO16 sites are checked for bounds, alignment, duplicates,
  supported encodings and register-matched pairs. Segmented data pointers
  retain their bytes. Relocation targets outside the declared overlay reject.
  The model materializes relocated bytes at an explicit load address; it does
  not replace the guest loader or establish a runtime binding.

Format/behavior references: N64Recomp's `cgenerator.cpp` and `recomp.h`, and
the [documented Zelda64 trailer](https://github.com/zeldaret/oot/blob/8a3634ca774a9b58d822cbc2cc09309f31eac6a4/tools/fado/z64_relocation_section_format.md)
and [loader behavior](https://github.com/zeldaret/oot/blob/8a3634ca774a9b58d822cbc2cc09309f31eac6a4/src/libu64/loadfragment2_n64.c).
These are references; no upstream implementation or game code is imported.

The local OoT image contains 469 structurally matching overlays, 468 with
nonempty text, and 52,643 relocation records. The catalog and decoded bytes
remain ignored. This does not close any of its fixed-image blockers.

The next compiler component emits standalone C byte verifiers via
`plaid_lower::overlay::verifier`. Each verifier reconstructs expected relocated
bytes in bounded temporary storage, compares the full file and zeroed BSS,
and leaves guest RAM untouched. Relocation sites and opcodes are resolved at
compile time; the emitted code contains no guest instruction decoder. Multiple
verifiers coexist using numeric section IDs. Invalid addresses, insufficient
RAM, allocation failure and any byte mismatch return failure.

`runtime/test_overlays.py` compiles the generated C with strict warnings. It
checks five load addresses against the Rust model and explicit arithmetic
expectations, reused/interleaved HI halves, signed-low carry, segmented
pointers, data-only images, every-byte corruption, BSS, bounds and allocation
failure. The full runtime test invokes it. This is the first-entry check
component, not a runtime binding or relocated-execution differential claim.
Its contract requires the complete freshly loaded image: callers cannot
silently accept an already-mutated data/BSS snapshot on first registration.

Still pending: link-address overlay lowering, verified runtime registration,
rebinding/invalidation and ares differential execution; then OoT fixed-code
closure, native title and its RSP snapshot/audio campaign. ADR-0172 is not
complete until those overlay execution checks pass.

## ADR-0173: One map index for per-site proofs

Status: accepted. Milestone 5 tooling; user-directed ("speed is king").

Context: the per-site proofs (local constants, jump tables, callbacks,
return closures, the solver's per-site checks and lower-map's table
ranges) each rescanned the whole map. That made them quadratic in map
size. SM64's 45419-block map spent almost all of discovery, solve and
lowering in these scans.

Decision: `indirect::MapIndex` is built once per map. It holds:
- the blocks of each image and generation, sorted by start, with the
  largest size;
- entries plus indirect candidates and observations;
- direct edges keyed by target.

Every proof keeps its old public form (`verify_static`, `verify_constant`,
`tables::verify`), which builds an index. The `_in` forms take an index that
the caller builds once. `tables::table_range` now takes one.

The solver also changes three things:
- it finds overlapping blocks of distinct identities by binary search
  instead of comparing every pair;
- it looks up re-derived edges, sites and blocks in sets;
- it locates edge sites and runtime functions through the index.

lower-map groups blocks by start once.

The `indirect_chain` certificates return `None` before building their
roots when the image exceeds `MAX_WORDS`, where `expected_map` refuses
anyway.

AGENTS.md rule 8 now makes speed a priority. A bottleneck is removed as
soon as it slows iteration. Before and after timings go in the receipt,
and outputs stay identical unless the change is intended.

Verification: every query answers the same predicate as the scan it
replaces, and the existing unit, CLI, runtime and spike096 suites pass
unchanged. On SM64 (release build, same inputs), the outputs before and
after the change are byte-identical, and the timings are:

| Step | Before | After |
|---|---|---|
| `discover --address-taken` | 14 min 56 s | 17â€“30 s |
| `solve --address-taken` | 55 s | 3 s |
| `lower-map` (47 MB C) | 130 s | 4 s |

Next: the 47 MB translation unit takes minutes in gcc. Splitting
`lower-map` output into several units that compile in parallel is the
next bottleneck.

## ADR-0174: Lowered C splits into parallel units; JALR sets share a dispatcher

Status: accepted. Milestone 5 tooling (AGENTS.md rule 8).

Context: SM64 lowered to one 47 MB C file. gcc `-O1` took 784 s to build
it, and nothing could run in parallel. 25 MB of that file came from 94
address-taken JALR sites. Each inlined a `switch` over all 1341
address-taken functions, with a call, a return check and a jump per case.

Decision:
- A JALR with two or more proven targets calls `plaid_call_<k>(s, t, ret,
  pc)`. That is one dispatcher per distinct target set, which returns the
  callee's result or `plaid_fault(s, pc, 3)`. The site keeps its order: it
  reads `t`, writes the link, runs the delay slot, returns a nonzero
  result, and otherwise continues at the link. This is what every inline
  case did. Single-target calls and JR switches stay inline.
- `plaid_lower::lower_c_parts` and `lower-map --parts N` write the main
  unit, which the runtime includes, plus `<stem>.part<k>.c` units. The
  part units hold contiguous, size-balanced shares of the guest functions.
  - With more than one part, the guest functions, `plaid_build_prot`,
    `plaid_verify_load` and the dispatchers get external linkage.
  - Each part declares them and repeats only the prelude's `static
    inline` helpers. `plaid_code`, the load-image data and
    `plaid_runtime_write` stay single-instance in the main unit.
- With one part, the output is the same program as before. It changed only
  where a dispatcher replaced inline cases.

Verification:
- spike096 lowers its `addrtaken` program through `plaid_call_0` and
  still matches pinned ares, including the fail-closed fault 3.
- `scripts/test_cli.py` splits a closed map into parts. It checks that
  the main unit defines no guest function and that the parts define
  exactly the single-unit functions. It then compiles each part with
  `-Wall -Werror` and links them with `runtime/plaid_rt.c`.
- On SM64, the old single-unit executable and the new split executable
  print identical results for 30 graphics tasks and 58 audio tasks: every
  task line, the RAM dump and the stop state.

| SM64 | Before | After |
|---|---|---|
| lowered C | 47 MB, one unit | 33 MB; main unit plus 15 parts of ~1.6 MB |
| build (gcc -O1, 20 threads) | 784 s | 48 s |

## ADR-0175: OoT's fixed code is CLOSED under the address-taken scope

Status: accepted. Milestone 5.

Context: OoT's fixed image (boot plus the Yaz0 `code` segment) had 13
address-taken-scope blockers, in two groups:
- the libultra exception and thread-switch code (`__osEnqueueAndYield`,
  `eret`), reached through two address-taken roots;
- direct calls into 0x801c7740.., which no supplied image covered.

Findings:
- Both roots were words read from Yaz0-compressed bytes. The
  address-taken scan (ADR-0153) read the whole ROM as raw words, so
  compressed streams produced noise. One root (0x80004498) sat inside
  `osInvalDCache`. The other (0x80005c20, `osYieldThread`) also appears in
  real data: a table of libultra pointers in decoded `code` (VRAM
  0x800ff4e4) that is handed to the 64DD driver.
- 0x801c7740 is that driver's segment. It is in the cartridge ROM
  (dmadata entry at ROM 0x7b20: VROM 0xb8ada0..0xb9da70, stored as Yaz0 at
  0xafde00), not only on the disk. The code at 0x800adaac DMAs it there
  when its "64DD present" flag is set.

Decision:
- `data_roots::rom_words` scans a decodable Yaz0 stream's decoded words in
  place of its compressed bytes, then resumes at the next aligned word
  after the stream. Yaz0 is a format, not a game. Undecodable "Yaz0"
  magic stays raw data. `declared_loads::yaz0_stream` reports the bytes
  consumed and refuses decoded sizes above 64 MiB.
- `osYieldThread` joins `RUNTIME_FUNCTIONS`. n64sym signs it; N64Recomp
  lists it under `ignored_funcs` rather than `reimplemented_funcs`.
  `plaid_rt.c` implements it: the caller queues behind the runnable
  threads of its own priority.
- The 64DD segment is declared as a second load in the local OoT loads
  file, next to `code`. Load declarations remain local measurements.
  Discovering loads automatically from the ROM's DMA calls is still open.

Result:
- OoT: 29,511 blocks, 2,562 indirect sites. `solve --address-taken`
  reports **`closed`**, 0 blockers, 13 assumptions.
- OoT discovery takes 8 s.
- SM64 has no Yaz0, and its map is byte-identical.

Verification:
- `yaz0_streams_contribute_decoded_words_not_compressed_bytes`: a stream
  whose aligned compressed word is a function start and whose decoded word
  is another; only the decoded one and the word after the stream count.
- `runtime/test_runtime.py` adds an equal-priority thread: `osYieldThread`
  runs it first and is then resumed ahead of it, in libultra order.

Open:
- 13 runtime functions OoT declares are not in `plaid_rt.c` yet.
- The overlays (ADR-0172) are not executed natively.
- SM64's 79 MIO0 streams are still scanned raw. SM64 closes regardless,
  but MIO0 should be decoded the same way.

## ADR-0176: OoT's boot reaches its first overlay with the full libultra runtime surface

Status: accepted. Milestone 5.

Context: after ADR-0175 the OoT map lowered, but the link needed 13 runtime
functions that `plaid_rt.c` lacked. The first run then faulted in boot's
`bzero` on the D-cache coherence rule.

Decision:
- `plaid_rt.c` implements the libultra functions identification names in
  OoT. None of them is OoT-specific:
  - threads and timers: `osGetThreadId`, `osStopThread`, `osStopTimer`;
  - memory: `osGetMemSize` (4 MiB);
  - PI: `osCartRomInit`, `osEPiStartDma`, `osEPiReadIo`;
  - VI: `osViGetCurrentFramebuffer`, `osViGetNextFramebuffer`,
    `osViSetXScale` and `osViSetYScale` (no-ops);
  - SI: `osContInit`, `osContStartQuery`, `osContGetQuery`, `osContSetCh`;
  - the rumble pak: `osMotorInit` and `__osMotorAccess` report no pak.

  Unsupported uses fail closed: a stop of a blocked thread, DMA through a
  non-cartridge handle, a cartridge write, and DMA outside the ROM. The
  runtime's own handles live in RAM above the 4 MiB the game is told it
  has.
- Coherence rule (fault 4) refined: only cached accesses fill the
  D-cache. A line used only uncached so far may therefore become cached.
  Once cached, any other access class still faults. The spike096
  `uncached_first` program matches pinned ares.
- The stop report also prints `$t9`, the ABI's call register, so a fault 3
  names its target.

Result (OoT 1.2, local, lowered RSP):
- boot runs 680 PI DMAs and two VI retraces;
- it creates the 64DD handle and probes the drive, finding none;
- it runs one RSP task as lowered microcode;
- it stops fail-closed at a call to 0x803b4df0. That is a game-state
  overlay that `Overlay_Load` relocated into the heap, which is ADR-0172's
  next stage.

No reference map was used.

## ADR-0177: CPU access to RCP memory and the PI bus is modelled as hardware

Status: accepted. Milestone 5.

Context: naming every function that touches hardware does not scale. Games
ship libultra and libleo variants that n64sym does not sign; OoT's
`osDriveRomInit` matched only through a decomp symbol list. Games also
touch hardware from their own code: OoT reads RSP output from DMEM 0xff4.

Decision:
- Lowered loads and stores to physical 0x04000000..0x1fffffff go to
  `plaid_state.io`, which the runtime sets. The access must be uncached
  (KSEG1 or an uncached TLB page). The default NULL, cached access, and an
  unhandled address all fault 1, as before.
- `plaid_rt.c` models words as pinned ares does (`rsp/io.cpp`,
  `pi/io.cpp`, `pi/bus.hpp`):
  - SP DMEM/IMEM. At boot DMEM holds ROM 0x40..0xfff, as the PIF leaves
    it (mupen64plus `bootrom_hle.c`). With `PLAID_RSP` they are the lowered
    RSP's own memories, and an IMEM write invalidates its texts. A task the
    runtime completes without running its microcode (any graphics task, or
    any task without `PLAID_RSP`) leaves SP memory unknown, and reads then
    fail closed.
  - `PI_STATUS` reads idle, since runtime DMA completes before the caller
    resumes.
  - The BSD DOM1/DOM2 timing registers are latched with ares' masks, and
    DOM1 starts from the ROM header.
  - The cartridge ROM reads as itself. The 64DD range 0x05000000..
    0x07ffffff is declared absent and reads as ares' open bus: the low
    address half, twice.
  - PI register DMA, bus writes, SRAM/FlashRAM and other devices fault.
- With this, `osDriveRomInit` and `LeoDriveExist` run lowered and need no
  name. OoT gets as far without the decomp symbol list as with it.

Verifier: `runtime/test_runtime.py` `rcp_io` covers DMEM boot bytes,
DMEM write/read, idle status, masked timing, open bus and ROM words. It
also checks that an SRAM read and a cached RCP access each fault 1. The
existing RSP-task test passes over the boot DMEM image.

## ADR-0178: Discovery labels returns once and resumes rounds from their roots

Status: accepted. Milestone 5 tooling (rule 8, speed).

Context: composing OoT's 469 catalog overlays at their link addresses
(ADR-0172) gives a 138,829-block map. Discovering it took 459 s. A profile
showed three costs:
- the address-taken loop (ADR-0153) labelled return certificates after
  every round, although they add no roots;
- each round restarted the indirect fixed point from its entries;
- each return certificate scanned every block and every call edge.

Decision, behaviour-preserving:
- `pipeline::discover_labelled(.., label)`: the address-taken rounds run
  unlabelled. Return certificates label the final round once, unless the
  budget ran out, as before.
- Each round is seeded with the previous round's roots, so it does not
  repeat the indirect passes that found them. Roots only grow (the inner
  loop already keeps candidates across passes), so the fixed point is the
  same.
- `returns::Closure` keeps the map's `MapIndex` and indexes calls by
  callee. The containing block is `MapIndex::containing(..).last()`, the
  first containing block in map order, exactly as the linear scan found
  it. `Closure::certificate` drops its now-redundant map parameter.
- The indirect fixed point indexes the previous pass's sites by address
  instead of scanning them per site.

Maps and solve reports are byte-identical for SM64, for OoT's fixed image,
for OoT with 50 overlays and for OoT with all 469.

| Run (release) | Before | After |
|---|---|---|
| SM64 discover | 30.7 s | 6.7 s |
| OoT discover | 8.5 s | 3.3 s |
| OoT + 469 overlays discover | 459 s | 44 s |
| OoT + 469 overlays solve | 19.3 s | 4.5 s |
| SM64 solve | 2.1 s | 1.2 s |

With the overlays composed, `solve --address-taken` reports 29 blockers:
28 unresolved indirect sites and one decoded runtime function. That
measurement is local. Overlays are not executed yet: that is ADR-0172's
next stage.

## ADR-0179: Discovery places the ROM's relocatable overlays at their link addresses

Status: accepted. Milestone 5, ADR-0172 stage 2a.

Context: ADR-0172 catalogs a ROM's relocatable overlays from its own file
and overlay tables. Their code was still outside every discovered image.

Decision:
- `plaid discover … --overlays` builds the image with declared loads as
  before, then catalogs overlay tables in that image with
  `overlays::discover`, without title, table address or file index inputs.
- `overlays::loads` turns each executable overlay into a `DeclaredLoad` at
  its link address: the file bytes as the table stores them, raw or Yaz0
  per its table entry, marked `relocatable`. Then the image is composed
  again.
- Data-only overlays supply no code and are left out. So are overlays
  whose link ranges collide, since a link address must name one file.
- The loads carry `plaid-overlay-catalog/v0` evidence over the catalog's
  hash. `relocatable` is omitted when false, so existing maps and load
  files are unchanged.
- Link-address code is analysis only. The game runs an overlay wherever
  it loads and relocates it. Lowering must bind each overlay at run time
  (ADR-0172) before any of its code runs. Until then `lower-map` refuses
  such maps, because they are not CLOSED.

Measurement (OoT 1.2, local): 468 of 469 overlays placed in 43 s, giving
138,829 blocks. `solve --address-taken` reports 29 blockers:
- 28 jump tables whose GCC scheduling the ADR-0140 recognizer does not
  accept. Examples: the scale inside the compare-to-branch interval, a
  branch-likely in that interval, the table base in the guard's delay slot.
- one overlay function whose bytes match a runtime signature.

Verifier: the `overlays` unit test checks that `loads` places an
overlay at its link address from its table entry, that colliding link
ranges drop both overlays, and that data-only overlays supply nothing.

## ADR-0180: Jump-table bounds proven over every path into the dispatch

Status: accepted. Milestone 5.

Context: with its overlays at link addresses (ADR-0179), OoT had 28
unresolved jump tables. GCC had scheduled their guards in ways the
ADR-0140 shape matcher does not accept:
- the index scale between the compare and the guard branch;
- a branch-likely inside that interval;
- the table base `lui` in the guard's delay slot;
- the scale in an earlier branch's delay slot, with the guard block
  reached through a branch-likely.

Adding more shapes would not generalize, so this ADR replaces shape
matching with a path proof.

Decision: when the shape matcher fails, `tables::guarded` walks backwards
over the CFG from the dispatch `addu base, scaled; lw; jr`, along every
incoming path, crossing each edge's delay slot only when that edge runs
it. Each path must establish:
- `scaled` is `sll index, 2` and is not rewritten before the add;
- `base` is a `lui`, plus `addiu` adjustments;
- a branch on a flag selects the dispatch only when the flag is set, and
  the flag's definition is `sltiu flag, index, count`;
- `index` is unchanged between the compare and the shift, in either order.

All paths must agree on the table and its count. The walk fails closed on:
- any entry, edge or indirect target strictly inside a walked block or
  at a guard branch;
- a delay-slot entry on the guard's fallthrough;
- an entry point at a walked block start;
- call, return or exception edges;
- loops, more than 16 blocks, or more than 4,096 instructions;
- a branch that dispatches when the bound flag is clear.

The evidence keeps the producer and format of ADR-0132 tables. It hashes
every word the walk read, so `verify` recomputes it from the current CFG
and bytes. Table immutability remains a scope assumption, as before.

Result:
- SM64 and OoT's fixed-image maps are byte-identical, since the shape
  matcher still decides them.
- OoT with its 468 overlays is **CLOSED** under the address-taken scope:
  140,154 blocks, 0 blockers.
- The last blocker before this ADR, an 8-byte `osVoiceControlGain`
  signature inside an overlay, came from running identify over overlay
  loads. The pipeline identifies runtime functions in the static images
  only, because libultra links there.
- Whole-ROM with no assumptions, the same map has 14,812 blockers.

Verifier: `tests/tables_guarded.rs` has the three GCC shapes as positive
cases. It also has four that must fail closed: a guard that dispatches out
of range, an index changed between compare and scale, an entry that skips
the compare, and an entry at the dispatch. The existing predecessor-bypass
and slot-entry tests still pass. One expectation in `tests/tables.rs`
changes. A second branch into the guard used to be rejected, but it is
reached only through the compare, so every path is bounded. The test now
also checks that adding an entry at that branch rejects the table.

## ADR-0181: Relocatable overlays run natively through a verified binding

Status: accepted. Milestone 5. ADR-0172 stage 2b.

Context: with its overlays at link addresses (ADR-0179, ADR-0180), OoT is
CLOSED, but the game loads each overlay into the heap and relocates it.
Natively, boot stopped at its first call into a relocated game-state
overlay (fault 3 at 0x800a151c).

Decision: overlay code is lowered once, at its link address, and runs
only through a binding to where RAM really holds it.
- Relocatable declared loads leave the fixed-load machinery: they are not
  in `plaid_code`, the table ranges or `plaid_declared`.
- Relocated instructions read their immediates from the bound copy at run
  time: a HI16 `lui` takes the low half of the RAM word at `pc + delta`,
  and a LO16 `addiu` or load/store offset takes its signed low half. The
  verified bytes equal the loader's output, so this is the value the CPU
  executes, including shared HI16s and segmented pointers the loader left
  alone. Any other relocation on an executed word rejects lowering.
- Return addresses written in overlay code are the bound copy's
  (`link + delta`), so checked returns compare real addresses.
- An indirect transfer whose proven targets include overlay code, and
  `plaid_enter`, first translate the target with `plaid_link`. A real
  address in bound text maps to its link address. In unprotected RAM, it
  binds the unique overlay and base at which a function entry lands on
  the target and the ADR-0172 verifier accepts the whole relocated file
  and zeroed BSS. Two candidates, a second live copy of a bound overlay,
  bound text overlapping code, or an unbound link address yield no case:
  fault 3.
- Binding marks the text words 255. A store or runtime write into them
  revokes the binding and clears the marks; from the overlay's own code
  it aborts (fault 2). Every block of overlay code checks its binding
  (fault 8). A direct call to another overlay's link address aborts.
- Address-taken layout: a word right after a hole starts a function, as
  the image start does, because a declared load begins with one.

The solver adds the assumption for relocatable overlays and keeps the
fixed-load assumption for fixed loads only.

Result:
- spike096 `overlay`: a Zelda64-format overlay with shared HI16s, a load
  and store LO16, an `addiu` LO16, an R_MIPS_26 `jal` and an R_MIPS_32
  function pointer runs at 0x80003000, is revoked by a write, and runs
  again at 0x80007fc0, where the LO16 carries. It matches pinned ares on
  all registers and RAM. Fail-closed cases: tampered bytes (fault 3), the
  overlay writing its own text (fault 2), a callee revoking the binding
  before the overlay resumes (fault 8).
- OoT with 468 overlays stays CLOSED (141,268 blocks, 14 assumptions).
  Natively it runs through its relocated game-state overlay to its first
  graphics task (686 PI DMAs). SM64 and OoT's fixed image keep their
  blocks; SM64 gains two address-taken functions after holes.

Verifier: spike096 differential against pinned ares, plus the three
fail-closed programs; `runtime/test_overlays.py` still covers the byte
verifier itself.

## ADR-0182: OoT reaches its title and file select with RT64

Status: accepted. Milestone 5.

Context: with overlays running natively (ADR-0181), the RT64 build of OoT
drew one frame of its boot logo and stopped. Five gaps were behind it, all
general.

Decision:
- **AI registers as hardware.** OoT's `osAiSetNextBuffer` runs lowered and
  reads `AI_STATUS`. The runtime's I/O hook now models `AI_DRAM_ADDR`,
  `AI_LEN`, `AI_CONTROL`, `AI_STATUS` and `AI_DACRATE` as pinned ares
  `ai/io.cpp` does, feeding the same two-entry FIFO as the HLE functions.
- **Data symbols settle identification.** `osViGetCurrentFramebuffer` was
  ambiguous because the current- and next-framebuffer getters differ only
  in the relocated global they load. n64sym signatures name those globals
  (`.hi16/.lo16 __osViCurr`). A variant now survives only if each data
  symbol has the address that settled matches give it and no other named
  global has that address, beside the ADR-0171 call rule. n64sym's
  section-relative names (`vimgr_data_0010`) may alias a global and decide
  nothing. `osViSwapBuffer` pins `__osViNext`, so the getter loading that
  address is not `osViGetCurrentFramebuffer`. Without this, OoT's
  scheduler read libultra's own VI state, which the HLE swap never
  updates, and waited forever for its swap.
- **A declared load begins with a function.** OoT packs overlays back to
  back at their link addresses, so the word before an overlay is the last
  one's data, not a `jr ra`. Each actor's first function, usually its
  init, was never address-taken. Load starts now count as layout
  boundaries in discovery and in the solver's re-check.
- **Constants across blocks.** GCC puts a pointer's `lui` in a branch
  delay slot and its `addiu` in the branch target. Address-taken pairing
  now follows up to 16 decoded words in address order until the register
  is redefined. Extra candidates only widen the dispatch set.
- **SRAM.** PI DMA through a handle on domain 2 (`0x08000000`) reads and
  writes 32 KiB of byte-addressed SRAM, kept in `--sram <file>`. FlashRAM
  commands still fail closed.
- **VI special features.** `osViSetSpecialFeatures` now sets and clears
  gamma, gamma dither, divot and the dither filter in the control word
  that `osViSetMode` resets. OoT turns gamma off; ignoring that washed
  out every colour.

Result:
- OoT + 468 overlays stays CLOSED: 154,414 blocks, 14 assumptions;
  whole-ROM 16,239 blockers. The fixed image: 29,542 blocks. SM64's map
  keeps its blocks and 1,343 address-taken functions.
- Natively with RT64 and its lowered audio microcode, OoT plays its boot
  logo, title and file select (checked by eye by the user, colours
  correct after the gamma fix), writes a 32 KiB SRAM save, and accepts
  keyboard input.

Verifier: unit tests for data-symbol settling (with a section-alias
negative case), load-start plausibility, and a cross-block constant
(`tests/address_taken.rs`). The AI registers follow ares `ai/io.cpp`
field by field. The full gate passes.

## ADR-0183: ROM in, native out; Majora's Mask runs its intro natively

Status: accepted. Milestone 5.

Context: every game so far needed hand-written inputs: the boot and code
segments as declared loads, and sometimes a curated identification. To
find out what a third game would need, Majora's Mask (USA) went through
the same pipeline with nothing written by hand for it. Every gap it showed
was general.

Decision:
- **Loads are inferred.** `plaid infer-loads <rom> <loads.json>` writes
  `plaid-loads-v0` from the ROM alone:
  - The *reset stub* is the boot-window bytes before the first
    identity-mapped file. It is declared as a revocable load.
  - A file-table file is a fixed load when two things hold. Its virtual
    start is a `lui`/`addiu`/`ori` constant in code already found. Its
    destination is the unique constant RAM address where at least 95% of
    its own `jal` targets begin a function (after `jr ra`, its slot and
    zero padding), with at least one call per 4 KiB.
  - Accepted files join a worklist, and overlapping placements are an
    error.
  - A ROM with no file table gets no static loads and takes `--loads`.
- **`scripts/native.py <rom>`** runs the whole pipeline: infer-loads,
  identify, discover (with overlays when there is a file table), solve,
  lower in 16 parts, compile in parallel, and the RSP snapshot loop
  (ADR-0169). It builds nothing unless the address-taken scope is CLOSED.
  `--rt64` also links the window build.
- **Identification:**
  - An 8-byte signature must also start a plausible function. Two words
    match mid-function too often.
  - `osFlash*` leaves the runtime set: FlashRAM is now modelled and the
    library runs as guest code.
  - `osGetIntMask` joins the set. It is in N64Recomp's ignored functions,
    and OoT passes its address to the 64DD driver.
- **Closure:**
  - An `andi` mask on a non-linking `jr` index bounds the table on that
    path. Called (`jalr`) arrays still need a guard.
  - The table limit rises from 256 to 1024 entries.
  - Padding after a `jr ra` whose delay slot does work (not a `nop`)
    precedes a function.
  - Address-constant pairing walks the CFG from each `lui` along
    non-call edges and call continuations, up to 64 instructions per path,
    until the register is redefined. ADR-0182's 16 words in address order
    missed a `lui` hoisted into the slot of a far branch.
- **Runtime:**
  - `__osInitialize_common` (libultra 2.0K+) is `osInitialize`.
  - The Voice Recognition Unit is absent: its calls return
    `CONT_ERR_NO_CONTROLLER`.
  - A thread starts 16 bytes below its stack top, as libultra's
    `osCreateThread` does; MM's stack check walked into its list.
  - An Expansion Pak is present: `osMemSize` and `osGetMemSize` report
    8 MiB. Runtime PI handles moved from the top of RAM to `0x80000200`.
  - The first VI comes one frame after boot, not at once.
  - The stop report gains all 32 GPRs.
- **An exact VR4300 D-cache.** ADR-0176's single-segment rule faulted on
  MM's ordinary cache maintenance. Lowered code now tracks the real cache:
  - 512 direct-mapped 16-byte lines, indexed by vaddr bits 4-12 and
    tagged by physical page. Each line has a dirty bit, a mask of stale
    bytes, and the older bytes a cached read still returns.
  - Stores still go to RAM at once.
  - A miss writes back (restoring older bytes that hardware never wrote)
    and fills.
  - `osWritebackDCache`, `osWritebackDCacheAll` and `osInvalDCache` act
    on the tags.
  - PI DMA writes leave resident lines stale; DMA reads check for dirty
    lines.
  - Still fail-closed (fault 4): an uncached access to a dirty line, a
    line resident at two indexes, and a line lost to an invalidate. RSP
    DMA reads of dirty lines are not yet checked, since the RSP has no
    read hook.
- **FlashRAM.** The MX29L1101 is modelled as pinned ares
  `cartridge/flash.cpp`:
  - It becomes the domain-2 device on the first command written to
    `0x08010000`; otherwise domain 2 stays SRAM.
  - Erase and program complete at once.
  - The 128 KiB save is kept in `--flash <file>`.

Result:
- MM with its overlays, with no hand-written input, is CLOSED under the
  address-taken scope: 214,963 blocks, 19,138 indirect sites, 14
  assumptions. `--guarded-ram` leaves 891 blockers and whole-ROM 21,313.
- OoT now discovers more: 29,613 blocks for the fixed image, 155,770 with
  its overlays (whole-ROM 3,120 and 16,338). Both stay CLOSED.
- Natively with RT64 it plays the mask intro, the Happy Mask Salesman and
  the Clock Town attract scene (screenshots taken by the runtime's own
  window). Headless, the longest run reached 3,181 VIs, 1,125 graphics and
  3,167 audio tasks, then stopped fail-closed at a call to a relocated
  heap overlay (fault 3).
- SM64 is unchanged.

Verifier:
- spike096 adds `clean_uncached`, `evicted_uncached`, `stale_cached` and
  `stale_overwritten`, matched against pinned ares, which reads the RAM
  dump through its D-cache. `cache_alias` still faults.
- Unit tests cover load inference, masked tables (with negative and
  `jalr` cases), padding after a working slot, and a far-hoisted
  constant.
- The CLI test's 8-byte signature fixture is widened to 12 bytes, since
  its `j .` after `jr t0` is no longer a plausible start.
- The full gate passes.

## ADR-0184: The boot image and its segments come from the ROM alone

Status: accepted. Milestone 5.

Context: F-Zero X (USA) has no decompilation and no Zelda-style file table.
`scripts/native.py` found 10 blocks in it. Three assumptions behind
ADR-0183's pipeline failed, each in general terms:
- the header's entry point is where the game runs;
- IPL3's 1 MiB copy is all main-image code at its link address;
- only a file table names segments.

Decision:
- **Boot address.** CIC-NUS-6103 and 6106 boot code jumps 1 or 2 MiB
  below the header entry. `RomHeader.boot_address` applies that offset.
  The CIC is identified as n64sym (MIT) does, by the CRC32 of ROM
  0x40..0x1000: `0x0B050EE0` is 6103 and `0xACC8580A` is 6106.
- **Boot image size.** The libultra entry stub clears BSS from
  `_bssStart` before it jumps to main, so the main image ends there.
  `CanonicalRom::boot_image_size` evaluates the stub's
  `lui`/`addiu`/`ori` constants up to its first `sw zero, 0(base)`. It
  gives none for any other shape, and then the 1 MiB window stays.
  `rom-info` reports it, and `infer-loads` and `native.py` use it. For
  SM64 it gives 0xF4580, the size so far declared by hand.
- **Segments without a table.** When `file_table` fails, a candidate file
  is a ROM range whose start and end offsets the code builds within four
  words of each other, as `_segmentRomStart`/`_segmentRomEnd` DMA
  arguments are. It is read raw and placed by ADR-0183's rule: the unique
  RAM constant where at least 95% of its own calls begin functions.
  Accepted segments join the search.

Result:
- **F-Zero X**, from the ROM alone:
  - boot address 0x80067000, a 0x71030-byte main image;
  - three segments: ROM 0x98080 at 0x800FC730, 0x1459A0 at 0x80115DF0,
    and 0x72120 at 0x80403010 (561 of 562 calls begin functions);
  - 11,398 blocks and 20 address-taken blockers, up from 10 blocks.
  - All 20 blockers are calls into two overlay slots (0x80115DF0 and
    0x801439D0). Several ROM files load into each slot by game mode, with
    sizes the code computes from link symbols. Overlays that share a
    link range are still left out (ADR-0181), so these fail closed.
- **SM64:** the table-free rule finds its engine segment exactly as
  declared by hand: ROM 0xF5580 at 0x80378800, 0x13490 bytes. Goddard is
  loaded from a level script, not from code constants, and is not found.
- **OoT and MM:** inferred loads are unchanged. With the bounded boot
  image both stay CLOSED with the same blocks (155,770 and 214,963).

Verifier: unit tests for the boot-image bound (the stub shape, and a jump
before any clear), for the CIC default, and for a table-free ROM range
(with a range built too far apart as the negative case). The full gate
passes.



## ADR-0185: executable files that share a fixed slot

Context: F-Zero X swaps several files into the same RAM ranges. Treating one
file as the permanent image either leaves calls unresolved or gives another
file's bytes authority. Milestone 5 needs each alternate represented separately.

Decision:
- `infer-loads` can mark overlapping executable files as `slot` alternates.
  Without a file table, candidate text ends after the last return before a
  non-CPU word; candidate data is bounded by the next named ROM file and a
  256 KiB cap. These are discovery heuristics, not an executable census.
- Each alternate gets a distinct analysis address above RAM, preserving its
  low 16 address bits. Synthesized J/JAL, pointer-word and HI16/LO16 relocations
  let existing discovery and lowering inspect it there. At execution, its
  addresses refer to the original shared slot through the overlay binding.
- Calls and address-taken pointers into a slot expand to the decoded alternate
  functions at that offset. A taken declared runtime function dispatches to its
  host implementation and is never decoded as guest code.
- The solver recomputes slot mappings and text bounds from declared source
  bytes, binds them into the image identity, and rejects mismatched metadata.
  Admission is limited to the guarded assumption scope. Whole-ROM closure is
  still OPEN; inferred alternates do not establish completeness.
- At every binding, generated native code compares every executable byte with
  the expected relocated text. Slot data remains mutable RAM. Writes revoke
  bindings; overwritten slots are checked again. No match or multiple matching
  alternates fault. Nothing decodes guest instructions at run time.

Verification: the public-CLI synthetic contract loads two files into one slot,
calls them directly and indirectly, and compares the complete result with pinned
*ares*: 7, then 11, then 7 after replacing the first file. Tampered and ambiguous
text fault. Rust regressions cover identity, forged slot views, relocation,
pointer fan-out, and a verifier that must compare all text. The retained mutation
check confirms the text-bound regression detects a weakened comparison.

The F-Zero X candidate grows from 11,398 blocks / 20 scoped blockers to
27,621 blocks / 0 scoped blockers. Native game acceptance, raw PI DMA and
graphics-microcode support are the next runtime integration, not established
by this compiler result.


## ADR-0186: compiled graphics microcode and a raw RDP command boundary

Context: the pinned RT64 display-list path does not implement F-Zero X's
F3DFLX2 reflection/alpha behavior. Substituting ordinary F3DEX2 left flat vehicle
surfaces. The existing native RSP backend can execute the original computation;
a game-specific renderer workaround is unnecessary.

Decision:
- Opt-in `--rsp-gfx` executes graphics tasks through the existing compiled IMEM
  snapshot registry. Each word keeps its IMEM identity guard. Missing text stops
  and is compiled before relinking; the artifact contains no runtime MIPS/RSP
  interpreter or JIT. The option requires an RT64 build.
- An optional DPC callback exposes the same registers to CPU MMIO and native
  RSP COP0. START/END masking, first pending START, freeze clearing order,
  source selection, current advancement and read-only registers follow pinned
  ares `ares/n64/rdp/io.cpp` within the synchronous idle model. Unsupported
  RDRAM ranges, reversed ranges and DMEM submissions over 4 KiB fault.
- Raw command bytes, including wrapped DMEM lists, reach RT64 in its host-word
  layout. RT64 retains partial RDP commands between submissions. Changed RSP
  DMA pages are synchronized; each task and CPU submission also account for
  CPU RAM writes. Native graphics tasks leave readable SP memory rather than
  marking its contents unknown as a skipped high-level task does.
- RT64's loadTile ignored reversed S but allowed reversed integer T, underflowing
  its unsigned row count and reading beyond RDRAM. A generated build copy adds
  the empty vertical-range guard, following the pinned ares parallel-rdp
  load-tile rule. Exact patch context is required once; .refs stays unchanged.
  RT64 is MIT, Copyright (c) 2024 RT64 Contributors. Its license/notices remain
  with the pinned dependency; no GPL reference code was copied.
- Raw handle PI DMA reuses the host runtime's checked PI transfer routine and
  its o32 stack size argument. It completes synchronously and posts no queue
  message. Cartridge writes and out-of-range reads are refused.
- `native.py --rt64 --rsp-gfx` validates visibly, collects missing snapshots,
  caches objects by source/dependencies/compiler/flags, and writes a launcher
  with ROM/save arguments but no scripted input or time limit. Temporary object
  replacement and stamp invalidation protect failed rebuilds. The graphics-RSP
  executable is named separately from the earlier HLE build.

Verification: native synthetic graphics tasks test shared CPU/RSP DPC state,
freeze/resume, DMEM wrap, RDRAM command bytes, CPU RAM visibility and post-task SP
reads. Raw PI DMA tests its ABI, output and refusal cases. The GPU-free RT64
contract tests vertical empty uploads, unchanged TMEM and a split raw command.
Standalone RSP DPC tests cover masking, append, missing bus and refused ranges.
The cache contract covers headers, flags, source changes and compilation failure.
Pinned-ares spikes096/097 pass; retained real audio task 600 again matches all
RDRAM/IMEM/DMEM and RSP state through spike098 (94,150 instructions).

Visible F-Zero X runs show vehicle markings/shading and complete 65-second race
validation without a runtime fault. These are finite runs. IMEM discovery still
comes from observed executions; DPC/RSP tasks complete synchronously; runtime,
rendering and CPU assumptions remain. No assumption is retired and whole-ROM
closure remains OPEN. `native_complete` stays false.


## ADR-0187: inactive overlay rebinding with native-frame pins

Context: an erased-save Majora's Mask startup calls `805665e0` from `800b6928`.
The relocated overlay at that heap base verifies completely, but its identity
is still bound at `8053b600`, whose unchanged bytes also verify. Text writes
alone do not observe heap deallocation. Rejecting every second copy therefore
faults even when no native frame can still use the previous binding.

Decision:
- Retain one selected binding per overlay identity. A uniquely verified copy
  may replace an inactive binding. Verify the complete existing file/BSS
  contract and check destination protection before releasing old protection.
- Every generated overlay function has a wrapper that increments its active
  native-frame count and decrements it on every normal or fault return. Nested
  calls, tail paths, callbacks and suspended host threads retain the pin until
  they return. A second base while any frame is active still faults.
- Unknown/ambiguous targets, protected overlaps, executable write revocation,
  full relocated-byte verification and the address-taken closure scope retain
  their existing checks. No loader hook, game-specific address or runtime
  instruction interpreter/JIT is introduced.
- Deduplicate exact callee identities before function-body analysis, preserving
  first occurrence. Repeated address-taken sites otherwise analyze the same
  bodies millions of times. MM lowering fell from an unfinished approximately
  449-second run to 14.215 seconds; four retained contracts emit identical C.

Verification: the synthetic heap-copy contract selects B1 -> B2 -> B1 and
matches pinned ares across PC, registers, FPU and observed RAM. Active-frame
rebinding, changed text and protected destinations refuse; fault exits balance
pins and runtime writes revoke the selected binding. Restoring the old rejection
condition makes this regression fail. The retained overlay self-write and
revoked-return cases still fault 2 and 8; shared-slot ambiguity still faults 3.
Formatting, clippy, 710 Rust tests (one ignored), CLI and runtime gates pass.

The rebuilt MM executable reaches VI 5358, 2401 graphics tasks and 4990
audio tasks with fault 0 at the 90-second time limit stop, using a fresh erased
FlashRAM copy and a visible RT64 window. This is finite native execution,
not a loader-lifetime proof. Assumption 12 remains assumed; no assumption is
retired, whole-ROM closure remains OPEN and native_complete remains false.

Pinned N64ModernRuntime's explicit unload/replacement mapping was read for
design comparison only; no third-party code was copied or linked. Measurements,
source coordinates and local reproduction commands are in
`research/mm-heap-overlay.md`; ROMs, RAM dumps and generated output stay ignored.

## ADR-0189: Lowered RSP code shares the host state layout

Context: MM submitted audio tasks at the expected rate but emitted only zero
PCM. Its retained generated C embedded the pre-DPC `plaid_rsp` layout while the
host runtime used the current layout. Recompiling the stale generated text
preserved the mismatch. Task submission counts hid premature returns, and
`--rsp-capture` reported success before checking task completion.

Decision: generated RSP C includes canonical `rsp_state.h`, just like the host
and registry. The compiler command must supply that header. A successful RSP
task must halt; capture acceptance follows fault/unknown-code/completion checks.
Native validation accepts `--require-audio`, which writes validation.wav and
rejects empty or zero PCM without making game-specific assumptions about when
sound should begin.

Verification: a retained synthetic text, separately compiled from its host,
passes register/PC/DMEM/halt/fault checks both before and after a header-only
layout mutation; the old generator fails that mutation. Unknown and incomplete
RSP tasks fail even when captured. Three synthetic WAV cases check silent,
empty and signed stereo output. Spike097: 27 positive and four negative cases
match pinned ares. Final visible MM: 60 seconds, PCM peak 32569, fault 0;
SM64: 15 seconds, peak 28116, fault 0. MM task 600 matches all captured RSP state
and RDRAM/IMEM/DMEM after 68,417 ares instructions (4,641 changed RDRAM bytes).
No vector/DMA semantics, AI address translation, guest instructions or closure
assumptions changed. No reference code reused. Evidence: research/mm-audio.md.

Local gate: formatting, strict workspace/all-target Clippy, 714 Rust tests
(1 ignored), CLI and full runtime tests pass. See the research note for the
shared-checkout ownership boundary and exact local gate logs.

## ADR-0188: ROM-derived RSP selection with fetch-verified native dispatch

Context: task DMAs can include mutable data after audio instructions. Comparing
the complete DMA range rejects valid tasks despite the existing per-word IMEM
identity verifier. A static text/data partition is unnecessary for this supported
execution model: execution itself decides which bytes require identity.

Decision: derive candidate texts from ROM image roots and overlay descriptors,
then lower them ahead of time. Select exactly one initial placement by words
reachable from its entry through direct control flow, including branch arms and
delay slots, stopping each path at an indirect transfer. Zero or multiple matches
refuse before RSP execution. Direct-loaded tasks use the same rule. Recognized
standard boots also select the text loaded by their actual DMA size, irrespective
of advertised ucode_size. No game-specific address or text boundary is used.

Every subsequently executed word must still match the instruction it was lowered
from, including JR targets, delay slots and fallthrough outside the startup mask.
The ADR-0167 closed native IMEM dispatcher faults if no lowered word matches.
Unknown executable DMA therefore cannot silently become guest execution. The
registry remains complete:false: this is an enforced supported dispatch model,
not proof that every ROM task or executable overlay is discovered. No runtime
MIPS decoder, interpreter, JIT or snapshot fallback is linked.

The default scripts/native.py pipeline uses only ROM-derived RSP texts. Snapshots
are oracle-only; --rsp-dump captures comparison inputs without recompiling them.
The snapshot hand input is removed for the demonstrated SM64, MM and F-Zero X
paths. Whole-ROM closure and the solver's general RSP-policy obligation remain
open; finite runs do not retire the full assumption. No reference code reused.

Verification: four focused Rust contracts check direct reachability, both arms,
delay slots, remaining pending paths and placement exits. Fourteen synthetic
ROM-task contracts check standard/direct loading, startup corruption and
ambiguity refusal, LH/JR target and subsequent fallthrough mutations refusing
at the exact fetch PC, and unexecuted mutated data succeeding. Existing native
RSP state/DMA/instruction verifiers remain in force. Visible ROM-only RT64 runs
with bounded timeouts pass for F-Zero X (20 s, --rsp-gfx), SM64 (20 s) and MM
(60 s), each with fault 0 and nonzero PCM through the --require-audio checker.
Exact counters, local gates, OoT outcome and limits: research/rsp-from-rom.md.

## ADR-0190: analysis-time ares boot harvest for ROM-produced text (partial)

Status: partial implementation; BK remains scoped OPEN. Milestone 5.

Use pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 as the boot CPU/device
executor, rather than extending Plaid's initial integer executor. Reset runs
through the hash-checked NTSC PIF firmware, with CIC selected from IPL3 CRC32,
8 MiB RAM, deterministic entropy and a neutral controller 1. No supplied save
or RAM snapshot is an input. Unknown IPL3 signatures refuse. Each boot stops
at 100,000,000 instruction calls or 3,600 VI; discovery permits eight rounds.
Budget exhaustion is not evidence that input is required.

The existing separately built headless oracle provides passive instruction,
RAM scalar/writeback and PI DMA callbacks. Reference CPU/RSP recompilers are
disabled in this analysis process. Tracking starts at the inferred game entry
after authentic IPL3 execution. At the first fetch of a missing KSEG0 target,
capture a contiguous produced RAM image only when its word-aligned bytes agree
with resident instruction-cache lines. Missing producers, other-device writes
and stale cache generations refuse. Provenance records the whole canonical ROM,
firmware and core identities, first fetch PC, instruction budget/count, observed
PI request source/destination ranges, completed CPU writes/writebacks and image
digest. PI-derived consumed ROM ranges are not an exhaustive CPU-read lineage.

The ROM-only native pipeline harvests only after scoped closure is OPEN, then
repeats identification, discovery and closure. Multiple requested targets can
be captured in one boot; newly exposed frontiers replay that deterministic boot.
Static loads and earlier images are preserved by subtracting overlaps. Encoding
`ares_boot` names whole-ROM source zero and its first-fetch `entry`. Composition
re-executes ares, validates identity/ranges/budget/digest, and derives only a
bounded subrange of the regenerated image. RAM snapshot files are outputs only;
there is no on-disk replay cache. A process-local memo avoids duplicate entries
within a composition. All existing native executable-byte guards remain:
mutation revokes verification and mismatched text faults 8. The final native
artifact links no ares CPU, MIPS decoder, interpreter or JIT.

The predecessor's `boot` encoding and integer executor remain for pure integer
paths and their synthetic differential contract; no device semantics were
added. Its copy/XOR loop still matches ares in all 32 registers, PC and checked
RAM, and native tampering faults 8. New synthetic tests exercise the ares
harvest itself from an explicitly declared post-IPL test state: deterministic
bytes/PC/CPU-write ranges, budget/no-producer/stale-cache refusal, overlap
preservation and production refusal of an unknown-CRC synthetic IPL3 in
all three byte orders. This fixture does not prove synthetic reset/CIC boot.

BK advances 276 -> 32,321 blocks with three recovered images. Scoped blockers
are 1 -> 223 -> 117 -> 72, exposing a larger executable frontier rather than
closing it. The next barrier includes ERET at 80002b5c, 47 unsupported scope
effects, seven unmapped targets and decoder/indirect candidates requiring
classification. The normal --rt64 --seconds 60 --require-audio pipeline refuses
before lowering. Analysis reaches VI 187; native VI/fault/PCM are unmeasured.
SF64/MK64/PM/GE remain 298/31/204/7. No assumption is retired.

Reuse decision: the existing pinned ISC/BSD ares core remains a separately built
analysis dependency, with its complete LICENSE retained by the builder. The
new adapter reuses project-owned observer tooling; no upstream implementation
code was copied into production. Native git now performs the same full HEAD
source check on DrvFS (0.044 s versus a Linux check interrupted after >110 s).
The passive instruction callback avoids debugger disassembly: the same complete
BK capture is byte-identical at 14.591 -> 2.581 s. Full results, map comparisons,
local gates and remaining obligations are in research/rom-sweep.md.


## ADR-0191: Identify independent SDK copies in disconnected supplied images

Context: a composite image can hold independently linked SDK copies. Global
name uniqueness left relocated copies ambiguous, while settled functions from
one copy rejected valid data relocations in another. In BK the boot
osInitialize CRC matches the pinned signature, but its osClockRate/osViClock
addresses disagree with the recovered SDK's globals. This is not missing
signature coverage or failure to scan recovered bytes.

Decision: preserve whole-image identification, and additionally resolve
signature name uniqueness and data-symbol constraints in each connected
supplied image, separated by existing unmapped holes. Combine the results;
conflicting names or sizes at one address select no runtime boundary. Calls
still check settled callee addresses across the composite in each resolution. Within one component,
multiple relocated copies and conflicting names remain ambiguous; signature
bytes cannot cross a hole. Adjacent supplied loads remain one namespace. This
is identification evidence under the existing runtime ABI assumption, not a
proof of SDK equivalence or an instruction-scope exemption. No game identity,
address or added runtime boundary is used. No decoder or emulator is added to
the native artifact. No reference implementation code was copied.

Verification: synthetic independent globals/duplicate relocated names,
lookalike getters, hole-crossing refusal and cross-component call tampering
join the retained single-image identification regressions. The broader ROM
sweep and final local gate are recorded in research/rom-sweep.md. BK scoped
closure and later native stages remain the task's acceptance gate.

Constant-return two-instruction stubs (`jr ra; addiu/ori v0,zero,imm`) are
left as guest code even when a service signature matches: the bytes cannot
identify a particular runtime service. BK's switch case returning 11 matched
osVoiceInit and removed the table's guest target from discovery. Effectful
small signatures remain eligible. A synthetic lookalike/refusal regression
covers both encodings and an effectful control. Existing table/return/native
instruction verifiers apply to the recovered guest block.

Control-map review found that component-only matching loses cross-component
VI-global evidence in OoT. Preserve whole-image identification and combine it
with component recovery from the same scanned candidates. Conflicting names
or sizes at one address select no runtime boundary. A split-image getter
regression and explicit name/size conflict tests retain this requirement;
scanning is shared, not repeated. Final verification supersedes the earlier
component-only checkpoint and its gate in the research receipt.


## ADR-0192: Paired-stream executable slot catalogs (partial BK closure)

Status: implemented; BK remains scoped OPEN. No assumption is retired.

The pinned ares store observer identifies BK's loader at 80251da0, the paired
decompression wrapper at 8023dd24 and slot writes at 8023e5f8/8023e7e4. The
loader indexes a physical source table initialized by boot code (80001bf0,
table 803ffe10); its unrelated segment table contains obsolete virtual source
offsets. ROM-only structural analysis recovers the physical table from literal
stores and matches its complete pair census to a unique segment table in a
boot-named compressed container. No title IDs, fixed offsets or captured RAM
are production inputs. This recognition declares candidate files; it does not
prove that every executable source or future loader state is known.

Extend plaid-loads-v0 with rare_pair, rom_end and text_size. Each bounded 1172
stream has a big-endian decoded size and raw DEFLATE payload. The first stream
is text, the next data; the complete catalog must agree with the segment table,
including an explicitly empty entry. Refuse missing/ambiguous metadata and
damaged/truncated catalogs rather than admitting a valid suffix. Decoding
requires stream end, exact size, alignment and bounded file padding. Recompute
the declared text size from the ROM before composition. Slot data supplies
table reads but cannot supply instructions, including fallthrough/delay slots.
An explicit branch into it remains an OPEN obligation.

Reuse ADR-0185 slot placement/relocations and ADR-0187 content verification and
native-frame pins. Format-owned text bounds replace the return-scan boundary
for this encoding. Data/BSS state is guest memory, never silently decoded as
MIPS at run time. Existing raw/Yaz0/boot load encodings are preserved.

Use the locked flate2 1.1.10 Rust dependency (MIT OR Apache-2.0), with its Rust
backend, rather than writing another DEFLATE implementation. No upstream code
was copied or vendored; Cargo.lock retains the transitive versions. The API
contract was checked against https://docs.rs/flate2/1.1.10/flate2/ . The pinned
ares reference remains separately built and licensed. Python zlib provides an
independent research parser; synthetic native state/RAM/PC/fault comparisons
with pinned ares cover raw and paired shared slots, switching and refusal.

BK has 13 slot files and improves 29 -> 1 scoped blocker. __osGetSR remains
unsupported: the current HLE interrupt mask is not a verified architectural
Status model. Do not identify away the remaining read or fabricate its value.
Native gameplay/audio acceptance remains unreached. See research/rom-sweep.md
for exact results, controls, commands and final gate.

Review hardening retains conflicting literal writes (including partial and malformed
initializers), refuses matching prefixes/suffixes of longer segment tables and
validates row ordering before arithmetic. Identical duplicate initializers agree.
Six deterministic Rust regressions and independent Python contracts retain the
required counterexamples. See research/integration-receipts/20261017-paired-slot-primary.md.

## ADR-0193: Preserve enabled IE when restoring a saved zero bit

__osRestoreInt restores valid saved IE values by OR, not assignment. A saved
zero leaves an already-enabled context enabled. Keep the existing delivery
and preemption path when IE is enabled. This is a correction to the runtime
Boolean IE operation, not a complete architectural Status model.

Retain a synthetic public lower-c/runtime differential against pinned ares,
with exact driver hashes, nested/repeated restores, preserved ABI GPR/HI/LO,
RAM and exit/fault checks. The old assignment fails the enabled-zero case.
Only the analysis-time oracle executes the independently assembled COP0
reference routines. No SDK code or game asset is copied.

Do not admit __osGetSR or retire an assumption: verified mask bindings, full
saved/live Status and event/thread semantics still remain open. See
research/integration-receipts/20261017-interrupt-restore.md.
## ADR-0194: Retain conservative per-copy SDK scalar address bindings

Identification retains optional data_bindings for selected SDK functions.
Require adjacent LUI plus ADDIU/ORI/LW/SW, valid register flow, instruction
bytes and agreement across every use and surviving signature variant. Missing,
unsupported, duplicate or conflicting evidence supplies no binding. Distinct
SDK copies retain distinct globals; conflicting selection removes metadata.
Reference-map names alone cannot create address evidence.

This is static address evidence, not immutable global contents or a verified
SDK mask variant. Existing declaration consumers ignore the optional field;
ProgramMap, lowering and runtime consumption remain a separate boundary. Do not
admit __osGetSR or replace missing bindings with a fixed mask.

No upstream implementation or game code was copied. Synthetic Rust/CLI tests
retain signed-low/ORI distinctions, disagreement and refusal cases. See
research/integration-receipts/20261017-sdk-data-bindings.md for the artifact
contract, pinned reference, controls and validation protocol.

## ADR-0195: Post-IPL SP memory from the ROM's own IPL3 in pinned ares

Status: accepted; declared assumption. Milestone 5.

The PIF copies ROM 0x40-0xfff into DMEM, but the ROM's IPL3 then runs from
DMEM and leaves both SP memories changed at the game entry. Games may read
that state: BK requires DMEM word 0 = ffffffff and IMEM word 0 = 000017d7
before it loads rspboot (ROM 0xb70 to 802820c0); with the PIF-only copy it
never does, and its first audio task finds no boot microcode. In pinned ares
DMEM 0x00-0x3f is all ff, DMEM 0x40-0xfff differs from the ROM copy in 3,957
bytes and IMEM is fully written.

At analysis time native.py runs pinned ares 9408cb43 from reset through the
hash-checked NTSC PIF and the ROM's IPL3, under the CIC selected from its
IPL3 CRC32 (ADR-0190's executor and refusals), to the first fetch of the
inferred game entry, and records DMEM then IMEM at that instant. The native
runtime starts SP memory from those 8 KiB (PLAID_SP_BOOT); builds without
them keep the PIF copy. A run that never reaches the entry builds nothing.
The native artifact contains the bytes only, never ares.

Declared assumption: post-IPL SP memory is pinned ares' result of the ROM's
IPL3 under deterministic entropy. It is retired by agreement with real
hardware dumps per CIC. The run-time --rom is not checked against the build
ROM, as for the rest of the artifact. Other IPL3 side effects (RDRAM
configuration words, SP/MI registers) are not modelled by this decision.

Tests: the synthetic ares fixture records 8 KiB of SP memory at the entry
fetch, identical whether the run stops there or continues; the runtime test
starts DMEM/IMEM from a declared state rather than ROM 0x40-0xfff. No
upstream implementation or game code was copied.

## ADR-0196: osContInit creates the EEPROM timer queue

Status: accepted. Milestone 5.

libultra's osContInit ends with osCreateMesgQueue(&__osEepromTimerQ,
&__osEepromTimerMsg, 1); osEepromLongWrite waits on that queue for 12 ms
after each block. The runtime's osContInit omitted it, so BK's first EEPROM
write (blank save) armed a timer on an all-zero queue: the expiry send found
msgCount 0, was dropped, and the main thread blocked forever. Only the idle
thread and audio then ran; no graphics task was issued. Pinned ares with a
512-byte EEPROM attached shows BK's own osContInit creating 802847b8 with
message 802847d0 at VI 137, eight completed write delays at VI 143-150 and
the first graphics task at VI 175. The analysis harness attaches no EEPROM,
so its BK runs skip the save path; that harness difference is not a model
input.

Identification binds __osEepromTimerQ in most libultra variants only through
a split pair: lui a0; lui a1; addiu a1; addiu a0. ADR-0194 bindings now accept
a pair split by up to seven instructions when the LUI is not in a delay slot,
nothing between writes its register or transfers control, and no transfer in
the function (including a register jump other than jr ra) can enter the
window. A ProgramMap runtime function carries the optional eeprom_timer
(queue, message) for osContInit only; lowering calls
plaid_rt_osContInit_eeprom, which creates the queue once. Variants whose
osContInit does not reference the queue get no binding and no creation. A
variant that references it in a form the binding still refuses would keep the
old omission; it is not detected.

Tests: split-pair acceptance plus clobber, inner branch, entering branch and
delay-slot refusals; the controller-policy fixture creates the queue from
declared bindings and a non-blocking send succeeds, while the unbound build
leaves it invalid. No upstream implementation or game code was copied.

## ADR-0197: Image words name address-taken functions; missing jump tables are harvested

Status: accepted. Milestone 5.

BK stopped at VI 17 with fault 3: 8034b620 calls 8034c360 through t9, a call
pinned ares makes too (same a0, VI 154). 8034c360 lies in the harvested
80277020 image and nothing named it: its address is a data word of the loaded
image, not of the ROM bytes, because BK's code and data reach RAM through a
load whose ROM form is not the plain words (ADR-0190 captures the produced
RAM). ADR-0153 scanned only aligned ROM words and code constants.
discover_address_taken now also scans the aligned words of every supplied
image, under the same plausible_at filter, so a pointer that exists only after
a load names its function.

Scanning more words changed which functions discovery reached first, and the
first-fetch harvest then no longer captured rodata 80277020..80284c20: six jump
tables became pointer_table_source_missing. harvest_boot.py now also captures
at the first fetch of each such table's site, and keeps a produced piece that
overlaps a table, so a table's words come from the run that reads them rather
than from fetch-order luck. BK gains the load 80277020 size 0xd730 (entry
8025f11c) and closes with 41 ROM-derived RSP texts.

Tests: a pointer that exists only in an image word, with empty ROM bytes, is
address-taken (fails without the scan); test_ares_boot.py harvests a synthetic
missing jump table. Other ROMs are not re-swept by this change.

## ADR-0198: osViSwapBuffer's __osViNext->framep; a frozen RDP holds the DP interrupt

Status: accepted. Milestone 5. Superseded for VI by the planned VI hardware
model.

With BK closed, the run was accepted with audio but issued no graphics task.
Its main thread loops until osViGetCurrentFramebuffer() equals a 0x40-byte
function at 80265150 that loads __osViNext->framep, a form no n64sym
osViGetNextFramebuffer signature matches, so it runs as guest code. libultra's
osViSwapBuffer stores the framebuffer in __osViNext->framep; the HLE kept it
only on the host, so the guest read __osViInit's value forever.
Identification already binds osViSwapBuffer's __osViNext (ADR-0194); the map
carries it as vi_next, osViSwapBuffer only, and lowering calls
plaid_rt_osViSwapBuffer_next, which writes framep and then swaps as before.

BK then issued two graphics tasks and stalled. After each frame its scheduler
sets DPC_STATUS freeze and clears it at a later retrace, and it takes the next
task's DP interrupt as that frame's completion. In pinned ares (rdp/io.cpp) a
frozen RDP consumes nothing and the DP interrupt follows the thaw's flush; the
runtime posted it when the task started. A graphics task started while the RDP
is frozen now holds its DP event until a DPC_STATUS write clears freeze, in
both the RT64 and --rsp-gfx DPC models. ares and native then agree on the
cadence: a swap and a graphics task every two retraces, alternating 803a5d00
and 803c49c0.

Left alone: swaps still take effect at once. The exact retrace-time
__osViSwapContext was tried and BK does not need it, but it remains an
assumption, and the planned VI hardware model retires it together with this
binding. __osViNext->state's VI_STATE_BUFFER_UPDATED is not set,
__osViCurr->framep is not written, and freeze does not hold the SP interrupt
(an RSP FIFO microcode would stall on a full FIFO). The visible BK run now
shows the logos, intro and title, but the outdoor sky is black in both RT64
and --rsp-gfx. Its asset DMAs match ares exactly and the CPU writes no
framebuffer pixels, so the cause is still open.

Tests: test_vi_dp.py checks the framep store and that a frozen RDP's DP event
arrives only after the thaw. Removing either change fails it.

## ADR-0199: libultra's VI code runs as guest code against VI registers

Status: accepted. Milestone 5. Supersedes the VI parts of ADR-0163 and
ADR-0198.

The runtime replaced osCreateViManager, osViSetMode, osViSetSpecialFeatures,
osViBlack, osViSwapBuffer, osViSetEvent, osViGetCurrentFramebuffer,
osViGetNextFramebuffer and osViSetX/YScale (N64Recomp's list) with host
models. Each was an assumption that the model has every side effect of the
game's copy, and BK broke that twice: its own next-framebuffer read saw a
context the HLE never wrote (ADR-0198), and the HLE's swap took effect at once
where libultra's takes effect at the next retrace. These functions only
program VI registers and libultra's own VI contexts, so they are no longer
runtime functions. Each game's own VI manager thread, __osViInit,
__osViSwapContext and getters run as lowered code.

The runtime models the VI registers as pinned ares vi/io.cpp does: the bits
each register keeps, a mirror every 0x40 bytes, a VI_V_CURRENT_LINE write
acknowledging the interrupt, and a read giving the field and the half-line
count for VI_V_SYNC, counted by host time from the VI_V_INTR line. An
interlaced mode alternates fields at each retrace. The retrace is the VI
interrupt, sent like any other event to the queue the guest registered with
osSetEventMesg(OS_EVENT_VI); the renderer gets the registers as the guest last
wrote them, and only while VI_CONTROL selects a color depth. The stop report's
"framebuffer" is now VI_DRAM_ADDRESS.

Running the VI manager makes its timer-interrupt branch reachable, and with it
__osSetCompare, a COP0 Compare write that the static scope cannot contain. It
is now a runtime function in the timer core: Count reaching Compare is the
timer interrupt, sent as OS_EVENT_COUNTER to the registered queue, as
libultra's handler sends it. osSetTimer remains a host timer, so the guest's
own timer list stays empty and its handler finds nothing to do.

Kept as shortcuts: the interrupt follows the fixed NTSC period, not the
programmed VI timing, and it arrives at the frame boundary rather than at the
VI_V_INTR line. The thread, message, interrupt-mask and timer core stays
replaced: a static recompiler cannot cheaply resume lowered code at the
arbitrary PC that libultra's exception handler would eret to.

BK closes with the extra guest code (80,850 blocks) and its visible 60 s run
is accepted: 1,273 graphics tasks, 1,789 audio tasks, no fault. The frames
match the ADR-0198 build, so the black outdoor sky is not a VI effect.

Tests: test_vi_dp.py checks the kept bits and the mirror; the retrace as
OS_EVENT_VI near VI_V_INTR in field 0; Compare as OS_EVENT_COUNTER; and the
DP freeze hold. The scheduling and renderer-bridge runtime tests now register
OS_EVENT_VI and program the VI registers directly. The identification fixtures
that name VI functions keep their own name list.

## ADR-0200: preserve IPL3's RDRAM prefix at native startup

Status: accepted for the bounded native startup-data scope. Milestone 5.

BK's visible native run reached its intro/title with audio and fault 0, but
the Nintendo opening and outdoor sky had missing backgrounds. Task captures
showed the expected display lists and colored vertices. Against pinned ares,
the native projection's depth coefficients differed: -2 and -1875 instead of
approximately -0.50032 and -5.00166. The guest projection routine observed
zeroed low RDRAM and selected its fallback clip distances. Ares retained the
bytes the ROM's IPL3 had written before game entry.

Extend the existing first-entry analysis-time SP capture with physical RDRAM
[0, 0x400), the vector/boot-parameter prefix below the normal game image.
The native builder requires the matching entry outside that prefix, exact
payload lengths and byte values; it emits ignored startup headers and a
provenance/payload-hash receipt. The runtime initializes the prefix before
installing its executable image. No game check, expected game word, projection
routine or per-ROM exception is added or changed.

This preserves a bounded observed startup-data state under the existing
pinned-ares/NTSC/cold-start assumption. It does not certify higher RDRAM,
cache/register/device state, boot execution roots or whole-ROM closure. The
final artifact still executes compiled host code, with no guest interpreter
or JIT. No assumption is retired.

The normal ROM-only BK pipeline is scoped CLOSED/0 with 80,850 blocks and 41
ROM-derived RSP texts. Its visible 60-second audio-required run reaches VI
3578, 1270 graphics tasks, 1785 audio tasks and 3750 PI transfers, fault 0,
PCM peak 32767. Separate visible inspection restores the Nintendo opening's
blue background/sun/lens flare and Banjo's forest/waterfall backdrop. This is
finite visual coverage, not pixel-perfect/full-playthrough or mixing proof.

Tests retain entry-time prefix bytes even after the synthetic guest changes
them, reject malformed startup payloads and overlapping entries, and check
native reads through both KSEG aliases, later writes/guards and independent
executable-image loading. Deleting initialization kills the native test.
Research, commands, measurements and remaining native-RSP graphics fault:
research/native-bk-graphics.md. Final exact-tree gate results are recorded in
the integration closeout and ignored target/bk-sky/ gate receipt.


## ADR-0201: return completed renderer framebuffer transfers to native RAM

BK's puzzle transitions showed outlines around black interiors because RT64
resolved rendered pixels into bridge-private RDRAM, while the native CPU read
its separate big-endian RAM. An isolated copyback experiment restores the
colored interiors; disabling only that transfer reproduces the black result.
The production correction applies to both display-list and raw-RDP submissions,
with no ROM identity, guest address, pixel pattern or game-code exception.

Report exact color/depth row spans immediately after the pinned RT64
`State::fullSync` completes `copyNativeToRAM`. Return those completed host
transfers synchronously before guest execution resumes, including equal-valued
bytes. Convert RT64's word-swapped bytes by absolute physical address. For each
span, the runtime first checks bounds and protected executable ranges, then
preserves modeled resident D-cache bytes with the existing DMA write rule,
then copies the bytes. Update the bridge's input snapshot only after success
and only within that span. A partial transfer cannot repair an unrelated lost
cache line. Value differences and whole-RAM copies are not write coverage.

This is a census of completed renderer readback transfers, not a proof of each
RDP pixel write or hardware-equivalent rendering/timing. RT64's existing
render-to-RAM boundary remains an HLE assumption. Native CPU/RSP execution and
scoped closure are unchanged; no interpreter/JIT, native-complete promotion or
assumption retirement is introduced.

The upstream reference remains RT64 43373749dac9bbc1b653e6a02aed40a9e1783bed,
MIT (Copyright (c) 2024 RT64 Contributors). Extend the existing build-copy
patch mechanism, preserve its notice, and leave `.refs` untouched. Reused
upstream context is confined to that patch; transfer/cache code is Plaid-owned.

Synthetic contracts verify partial/unaligned byte order and coverage,
equal-valued transfers, refusal leaving the input snapshot unchanged, cached
old versus uncached new data, explicit invalidate/refill, protected text,
out-of-range writes and partial/full lost-line repair. Removing pre-write
cache bookkeeping kills the regression. Two visible production 75-second BK
runs reach fault 0; captured title and file-select transitions show colored
piece interiors. Research, finite coverage and local gate receipts:
research/native-framebuffer-readback.md and ignored target/bk-puzzle/.


## ADR-0202: infer bounded raw section slots and exact cache SDK identities

Recognize adjacent, independently passed raw-section descriptors with shared
linked slots and contiguous ROM ranges. Require the section-reading call-site
shape, tracked descriptor loads, alignment, exact file/text/data/BSS relationships
and ROM/RAM bounds. This is structural candidate evidence, not a loader-lifetime
proof. Re-read descriptors during composition; source, decoded size, link and
text extent must match. Existing content-bound slot checks remain mandatory.
Data after the format-owned text boundary cannot supply instructions or targets.

Extend SDK identification with exact address-independent full-body SHA-256
profiles for three reviewed cache routines and their supported variants.
Store fingerprints only, never commercial instruction arrays. Include terminal
delay slots in both the identity and guarded function extent; preserve valid
same-name copies and reject conflicting identities. Runtime semantics and the
declared HLE assumption remain unchanged. No arbitrary CACHE-scope exception,
game-address exception or native-complete promotion is introduced.

Paper Mario improves from scoped OPEN/164 to OPEN/142. Its remaining E000
effect code needs TLB-aware source, binding and lifetime evidence; accepting
an E000 pointer as ordinary KSEG RAM would be incorrect. Local decomp metadata
at pmret/papermario 1104f1f71b824042a5fa1f958f2d861b603320fd was diagnostic
only; it has no root license and no source/game code was copied. Production
inference depends only on ROM bytes. Tests and evidence:
research/paper-mario-native-frontier.md.

## ADR-0203: batch exact first-fetch replays during load composition

Compose accepted ares-produced loads with one reset replay for all missing
entries. Capture every requested entry at its own first fetch, even if an
earlier capture's produced range covers it. Preserve legacy range-cover harvest
behavior separately. Validate all rows and the completion footer before any
new capture enters the in-process memo; missing, duplicate, rejected, malformed
or unrequested payloads fail closed. No on-disk cache or native guest executor
is added. The pinned ares adapter remains an analysis-only separate build under
its existing ISC notices; no new upstream code is copied or linked.

The retained synthetic fixture changes a later entry between fetches and
requires batch/independent bytes, hashes and capture steps to agree. A local
three-entry Paper Mario comparison also preserves CPU-write and PI-DMA ranges:
15.292 s / 76,282,317 interpreter calls becomes 7.557 s / 27,609,595 calls.
Whole-pipeline harvest budgets remain unchanged; the result does not establish
idle-loop termination or exhaustive executable coverage. Receipt:
research/paper-mario-native-frontier.md and ignored target/paper-mario/.


## ADR-0204: Refine raw copy-call and indexed source candidates

The ROM-only builder can revisit its rebuilt discovery image before another
oracle harvest. `infer-call-loads` checks the ROM identity and every original
load declaration, reconstructs authoritative bytes, and appends deterministic
raw slot candidates. Repeated refinement is idempotent. A changed original
source requires rediscovery, and fixed executable ranges are not overwritten.
Explicit user-supplied load files are not changed by the automatic pipeline.

A wrapper witness supplies constant aligned ROM start/end and RAM destination
to a common helper, then immediately calls that destination. Distinct wrappers
must name adjacent source ranges sharing the helper and destination. The helper
has a bounded 128-word linear affine scan: its downstream calls exhibit
(source, destination, chunk) followed by (source+chunk, destination+chunk,
end-source-chunk). Calls with unknown arguments are skipped as witnesses but
still kill caller-saved values; conditional loops and their delay slots are
scanned structurally. This is candidate evidence, not a path or copy proof.

The same helper shape supports an indexed descriptor consumer: an index scaled
by a power-of-two stride selects a row, and loads at offsets 0/4/8 supply the
outer helper's source/end/destination arguments. A contiguous bounded run may
start with one whole zero record. At least two distinct nonoverlapping files
sharing a destination must have adjacent ROM extents. Other fields are opaque;
the 256-row limit is a resource budget, not a verified valid-index bound.

These declarations retain the existing raw text-bound heuristic and exact
native executable-byte binding. They neither certify catalog completeness nor
retire the static-image, loader-lifetime or runtime-ABI assumptions. No MIPS
executor or game-specific addresses are added. E000 executable translations
still require a separate virtual/physical/generation binding model.

Authored tests cover address and stride changes, argument/row clobbers, delay
slots, unknown calls, branch aliases, unsupported transfers, scan budgets,
source bounds, malformed/overlapping rows and stale/foreign CLI inputs.
Removing the wrapper destination-call equality makes its negative regression
fail. Paper Mario measurements and remaining obligations are recorded in
research/paper-mario-native-frontier.md.

A negative ROM file-table result is retained across discovery rounds to avoid
replaying boot loads for the same failed overlay probe. Successful overlay
discovery still inspects each rebuilt image; other failures still stop the
builder. A controlled round improves from 60.517 to 55.778 seconds with an
identical serialized map; the receipt records the hash and scope.

## ADR-0205: unchanged TLB executable sources and guarded tail cells

Keep raw mapped executable bytes unchanged in compact analysis slots; derive
J/JAL regions from architectural virtual PCs. Native bindings retain separate
virtual and physical deltas, winning TLB entry and monotonically advanced
generation. Inactive mapping/code changes revoke; changes affecting active
frames fail before mutation. Bind/protect source cells that justify finite tail
dispatch, without freezing unrelated data. Infer source candidates from bounded
indexed mapping/copy consumers, including sparse records; resource budgets are
not index or universe proofs. Native CFG bodies stop at binding boundaries while
return analysis propagates continuations through tails. Pinned ares supplies
semantic/reference behavior; no reference code or game code/assets were copied.
Paper Mario remains OPEN/18 and unaccepted. See
research/native-tlb-executable-bindings.md for evidence and limits.

## ADR-0206: scheduled bounded indexed dispatch proofs

Recover a dispatch register's surviving LW and its table-pointer definition
over the existing bounded all-predecessor proof, including pointers scheduled
before their guard. Accept SLLV only with an exact proven constant shift of 2.
Keep matching index values across definitions, reject shared unresolved
constant/base obligations, and recheck CFG/source/generation/snapshot evidence.
Unknown calls, entries and unresolved cycles remain open. Retained authored
counterexamples and native full-state/checkpoint comparisons with pinned ares
cover the extension; table writes fault and wrong strides refuse emission.
Paper Mario remains OPEN/17 with 56,495 blocks and no accepted native run.
The native builder defaults its Cargo subprocess to measured release
incremental compilation while preserving explicit user overrides.
See research/scheduled-table-dispatch.md and research/native-build-iteration.md.

## ADR-0207: inductive unchanged table-dispatch predicates

Permit a repeated backward CFG frame only when the full pending proof state
matches at the exact same block start, anchor and exclusive end, after block
transfer. All non-cycle predecessors must still ground the proof. Preserve
entry/call barriers, resource limits and complete source/target rechecking.
Reject the base-only shortcut: an authored counterexample can replace a
three-entry guard with seven on a later iteration. Native preheader and
captured-pointer/guard fixtures match pinned ares, including a changed current
index register whose old value was already captured. Paper Mario remains
OPEN/16 with 56,799 blocks; no native artifact or run is accepted. See
research/loop-table-dispatch.md for evidence and remaining entry/call work.


## ADR-0208: retain independently evidenced internal decode entries

Keep inferred decoder roots distinct from external inputs across inner and
outer discovery rounds, retaining candidate/evidence history before analysis.
An internal-entry tag must agree with independent content-addressed entry
witnesses; ordinary entry facts survive merges and cannot be erased by adding
a candidate-parent tag. Recheck all incoming candidate and observed JR paths,
including delay slots, executable identity and placed-slot binding. Calls,
returns, address-taken functions, SDK callbacks and unknown entry state retain
their proof barriers. Complete target-set and source-byte checks still govern
closure. Authored regressions include a formerly accepted merged explicit-root
forgery; the native case-backedge loop matches pinned ares. Paper Mario remains
OPEN/16 with 56,799 blocks and 162 loads; five sites retain 84 recovered
candidate edges but no new closed proofs. No native run is accepted. See
research/derived-entry-discovery.md for evidence, timing and limits.


## ADR-0209: bounded longer predecessor paths for table proofs

Raise the backward table walk's general frame cap from 16 to 32 while retaining
the independent 4,096 instruction-read budget and every semantic proof check.
An authored 24-block case path now reaches its initializer; clobbered bases,
unknown entries, changed cycle predicates and over-budget paths still reject.
The native long case chain matches pinned ares. Fresh ROM-only Paper Mario is
OPEN/15 with 56,799 blocks and 162 loads: one 56-entry dispatch closes and no
new blocker sites appear. Native emission remains refused. See
research/table-path-budget.md for the diagnostic, regressions and timings.


## ADR-0210: bounded guest-callee no-write summaries

Carry an already-discharged table index/guard and pending base across a direct
JAL only when a bounded traversal of all reachable callee instructions proves
that none writes the required GPR. Check nested direct calls and delay slots;
reject unknown transfers, recursion, missing text, unsupported traps and slot
ambiguity. Count every read against the shared 4,096-word budget and include
all callee words in source verification. Retain full-predicate loop induction.
Every incoming return source must belong to a proven callee at that exact
continuation. Independent checked-return/control-flow contracts still apply;
no guest ABI assumption or omitted guest execution is introduced. Authored
native calls, RAM stores and stack effects match pinned ares. Paper Mario is
OPEN/14 with 56,799 blocks and 162 loads; a 24-entry dispatch closes, with no
new blocker sites. No native run is accepted. See
research/callee-register-preservation.md for tests, limits and timings.


## ADR-0211: terminate callee proof paths at checked BREAK

A standalone BREAK cannot reach a normal call continuation in the existing
guarded native model: lowering aborts with fault 9 at that PC (ADR-0138).
Count and hash that exact mapped word, then stop the callee path. It is not
a normal-return witness. BREAK-only functions and delay-slot BREAK still
reject; ordinary scope still has the BREAK-site blocker. No handler/resumption,
guest ABI assumption or new exception semantics is introduced. Authored
RED/GREEN, changed-word, scope and abort-PC regressions pass; normal native
call-loop state matches pinned ares. Paper Mario is OPEN/13 with 56,799 blocks
and 162 loads; one five-entry dispatch closes and no new blocker appears.
Native emission remains refused. See research/checked-break-callee-paths.md.


## ADR-0212: preserve flag value versions before pruning impossible paths

A backward path requiring the same unchanged GPR to be both zero and nonzero
is infeasible. Skip only that incoming edge after hashing its branch and
executed delay slot; keep all other predecessor and full-cycle checks.
Every non-SLTIU GPR write must first kill old flag constraints, including
pointer/scale transfers that return early. Retained baseline and naive-rule
counterexamples catch stale guard booleans; native valid/invalid-index loops
match pinned ares. Paper Mario remains OPEN/13 with 56,807 blocks and 162
loads: eight more blocks are discovered but no blocker site closes. Callee
and external-entry obligations still prevent native emission. See
research/branch-flag-feasibility.md for evidence, timing and control limits.


## ADR-0213: Preserve captured table values through checked guest calls

Extend bounded no-write callee effects to every still-live backward table
obligation, including captured addresses and flags. A matched index/bound is
already discharged; no ABI preservation is inferred for its old GPR. Source
reads may traverse fixed text and the explicitly current placed alternate,
never another alternate or its data tail. Each GPR consumes the same shared
4096-read budget; full Need induction, source hashes, caller-slot transfers,
external entries, return closure and global binding/lifetime gates remain.
All callee instructions execute natively; this adds no assumption.

Authored captured-call baseline RED, 14 module and25 focused integration
tests, native full-state/RAM pinned-ares contracts and a caught pending-address
deletion mutation support the effect rule. Independent Luna xhigh review found
no correctness issues and independently ran module/flag/native tests. The
ROM-only inferred-input probe improves OPEN13 to OPEN12 at unchanged56807
blocks/162loads, closing the five-word/four-target dispatch80aac6f0. No native
Paper Mario artifact or run is accepted. Exact committed-tree local gates
remain required. See research/captured-callee-values.md for limits/receipts.


## ADR-0214: Prove affine table offsets and checked fixed returns

Track a normalized low-word byte-offset minus four-times-index expression
while proving bounded tables backward. Supported nontrapping arithmetic may
substitute terms; only an exact zero expression discharges the relation.
Full-width range guards, complete path induction, every pending GPR's callee
effect, source/table hashes and global binding/lifetime gates remain required.
Constant definitions have one owner; SLLV adds an exact shift requirement.

For a placed caller, an incoming fixed-text source may be read only as an
exact JR RA covered by its checked no-write callee effect. The read consumes
the existing budget and participates in the source hash. Other alternates,
data tails and unmatched returns retain their rejection rules. No native
runtime guest execution, ROM constants, ABI assumption or new acceptance
exception is added.

Authored baseline/shift/fixed-return counterexamples, forward arithmetic
verification, native full-state pinned-ares contracts and a caught exact-zero
mutation support the rule. Independent Luna xhigh reviews find no correctness
issues. The final ROM probe improves OPEN12 to OPEN11, adding six blocks and
closing one five-entry table; the earlier OPEN15 failed-verifier probe is
retained. No Paper Mario artifact or run is accepted. See
research/affine-table-index.md for receipts, timings and remaining proof gaps.


## ADR-0215: Bind mapped callee effects to traversal-local sources

A bounded no-write callee proof may resolve a linked entry only through one
unambiguous declared load and its matching placed text, image and generation.
The source declaration, linked/placed addresses, all traversed words, constant
source cells and canonical return PCs participate in the enclosing table proof.
Identical linked and placed addresses still retain their source witness.

A mapped traversal owns its binding authority. Returning from it restores the
caller's context; each queued branch/tail path carries its own context. A prior
raw call cannot authorize a later numeric placed call or fallthrough. Mapped
fallthrough cannot escape its text into adjacent analysis storage. The inherited
red test demonstrated a real proof-wide authority leak and remains a regression.

Canonical non-return JR tails require the existing exact rechecked constant-cell
certificate and no-write effects through every target under the shared bounded
read/depth limits. Unknown transfers, ambiguity, clobbers, stale source/cell/
generation evidence and unrelated return sources reject. This proves register
effects, not a guest ABI or complete call/return, memory or timing semantics.

Discovery now carries declared source context before every indirect-analysis
round, including outer address-taken and added-slot/layout rounds. Public legacy
entry points default to no context. Slot/content validation occurs at the public
boundary, not per register; declared loads remain distinct from observed DMA.
Tail-cell proofs run before table proofs, with the final all-producer recheck.

The fresh ROM-only Paper Mario probe improves scoped OPEN/11 to OPEN/9 and
56,813 to 56,851 blocks, with 162 loads. Native emission remains refused. No
runtime guest instruction execution, game-specific rule, SDK boundary or new
assumption is introduced; mapping generations, active-frame pins and source-cell
protection remain mandatory. Synthetic callee/table/source controls, four killed
mutants, and authored native full-state pinned-ares contracts verify this slice.
No upstream implementation is copied; the ares ISC oracle stays separately built.
See research/mapped-callee-effects.md and ignored target/paper-mario/0215-recovery/.


## ADR-0216: Reuse source-bound callee effects within an immutable table walk

A successful bounded no-write effect may be reused for the same architectural
callee target and required GPR during one backward table walk. Map, source image
and caller slot are immutable in that walk and form the rest of the query
identity. No cache crosses walks, discovery rounds or certificate verification.
Each verifier redoes the source proof from current declarations and bytes.

Cache misses consume the existing shared 4,096-read budget. Hits perform no new
source traversal but still contribute every instruction/cell word, linked/placed
binding and normal return witness to the enclosing certificate. Existing call
delay-slot, all-predecessor, binding-generation, active-frame and closed-world
gates remain mandatory. There is no ABI assumption or resource-limit increase.

This general reuse closes two resource-limited Paper Mario dispatches: scoped
OPEN/9 -> OPEN/7, still 56,851 blocks and 162 loads. Three independent entry
barriers, two callee register-effect proofs and two stack-cell pointer proofs
remain refused. Native emission remains gated. Authored repeated-call native
state matches pinned ares. Four caught mutants cover absent reuse, missing
source words and missing target/GPR cache identity; a shared-return negative
ensures target identity is tested independently of return-witness rejection.
No reference implementation is copied. See research/table-effect-reuse.md and
target/paper-mario/0216 receipts. No README or progress milestone changes.


## ADR-0217: Prove exact frame-local table-pointer reloads without alias assumptions

A backward pending table pointer may cross an exact SW/LW stack-cell pair only
when every incoming path proves unchanged SP and an enclosing negative ADDIU
SP,SP allocation. Nonnegative aligned offsets must fit all four bytes inside
the frame. Every other store, CACHE or COP0 operation while the cell is pending
refuses; distinct virtual addresses alone do not prove distinct physical bytes.
Register-only call summaries cannot discharge cell or frame obligations.
Independent entries, unsupported SP definitions and unmatched cycles still refuse.

The saved source must independently satisfy the existing ADDU/scale/base/index
proof. ADDU's sign-extended result survives SW/LW; no arbitrary 64-bit register
or guest ABI preservation is assumed. Source words, including dead clobbers,
spill/reload and allocation, join the rechecked certificate. No runtime MIPS
execution or game-specific fact is added. Index-cell versions, multiple live
cells, nested-call memory effects and broad alias proofs remain unsupported.

Five new Rust tests and four native index/SP-base checkpoint comparisons
against pinned ares verify this general rule. Five semantic mutants are killed.
Fresh PM remains scoped OPEN/7 (56,851 blocks, 162 loads), with an identical
ProgramMap. All three remaining groups remain refused; no PM native artifact
or run is accepted. This is partial progress. No reference code is copied.
See research/stack-table-pointer.md and ignored target/paper-mario/0217 receipts.

Frame ownership does not consume SP arithmetic: the allocating ADDIU must still
run the ordinary pointer/flag transfer. A decoy-table counterexample and native
SP-derived-base fixture verify this review correction before the final gate.

## ADR-0218: Validation-only residual-dispatch mode

Decision: `plaid solve|lower-map --residual-dispatch` (scope
`DeclaredStaticImagesGuardedRamResidualDispatch`, `scripts/native.py
--residual-dispatch`) accepts a map whose only remaining blockers are
`unresolved_indirect_site`. Each such site is lowered as fail-closed dispatch
over every lowered entry through the existing `plaid_call_*` dispatch and its
mapped-code byte/generation/pin guards; any other target faults 3 and no guest
instruction is ever interpreted. Every other blocker still refuses. The report
and manifest record `native_complete: false`, the mode and the residual site
list, so the artifact is never accepted as fully native. The default scope,
the closed-world gate and native-mode acceptance are unchanged.

Why: it lets a ROM with a few unproven sites run natively far enough to find
the next real blocker (the exact site, target and state at the fault) instead
of continuing to prove sites blind.

Verification: Rust solver tests (only the residual scope closes; default
refuses; every other blocker still refuses; residual list reported) and a
runtime contract in which a lowered-entry target matches pinned ares and a
non-entry target faults 3. Mutation: disabling the residual gate's refusal
makes the acceptance/refusal test fail.

Runtime fixes found by the first Paper Mario run are general hardware/SDK
behaviour: every libultra Controller Pak operation reports PFS_ERR_NOPACK,
CPU writes to cartridge space are ignored (pinned ares), and EPi DMA accepts a
full cartridge address.

## ADR-0219: Revoke inactive fixed text through the shared CPU/device write gate

Date: 2026-10-21. ADR-0218 is reserved by the separate Paper Mario worker.

An RSP task may modify its own microcode's RDRAM copy. Those bytes can also be
conservatively discovered as possible CPU entries. Treating every such decoded
base-image block as permanently immutable faults a legitimate SP DMA. Removing
the possible CPU entry, suppressing protection for microcode, or selecting a
policy by ROM identity would weaken the supported execution model.

Fixed CPU text now uses the existing shared write boundary for CPU stores and
runtime/device DMA. A write into inactive fixed text marks its words revoked.
Before executing a block, its revoked words must equal the original compiled
words; differing bytes fault 8. Restoration can revalidate them. There is no
guest decoder, interpreter, JIT, or alternate instruction implementation.

Every fixed native function pins its complete emitted body, including return
continuations, until all exits unwind. Stack-local frames form an intrusive
list so suspended SDK threads remain pinned and may leave in non-LIFO order.
Writes overlapping any active body fault 2. Fixed proof-bearing table/cell data
has a separate immutable protection tag; declared-load tags retain their byte
verification and additionally respect active fixed frames. Active relocatable
overlays also refuse runtime writes, regardless of whether they use a TLB.

The RSP callback still calls plaid_runtime_write without a policy exception.
The closed-world solver, default maps, discovery, and assumption ledger do not
change. This extends dynamic write verification; it is not a static lifetime
proof or whole-ROM acceptance. Source reference: pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04, ares/n64/rsp/dma.cpp.
No upstream code was copied.

Synthetic coverage: CPU/RSP inactive revocation, ordinary-data DMA, stale entry
refusal, restoration/re-entry, actual active native call, suspended frame list,
immutable proof data, and active overlay runtime writes. Accepted CPU state
matches pinned ares. Six semantic policy mutations are rejected. Bounded game
and passing full-gate receipts are recorded in research/rsp-from-rom.md and ignored
 target/oot/0219; incomplete runs do not establish acceptance.

## ADR-0220: Boot fetch coverage and ROM-word discovery expressions

Pinned ares confirms that the first residual-validation fault reaches existing
IPL-loaded text, rather than a newly decompressed main image. Bounded lexical
expressions may propose address-taken discovery roots from uncached cartridge
words. These are speculative roots, never target certificates: PI latches and
branch paths can disagree with the guessed value, and whole-ROM closure still
refuses the unresolved site. Calls stop the scan; unknown writes kill values;
alignment, ROM bounds and the existing CPU-function/layout filter remain.
Native execution retains fail-closed dispatch and existing load content guards.
No game-specific production values are introduced.

The ADR-0190 adapter can additionally stop at the first uncovered KSEG0 RAM
fetch after boot entry. Coverage includes the native-excluded vector prefix
and declared executable slots. Completed-producer/cache checks remain mandatory;
only uncovered pieces are composed through replayed, guarded ares_boot loads.
This finite neutral-input run supplies discovery/provenance, not closure.

Review corrections to ADR-0218 retain known missing-candidate blockers, write
the residual manifest even when ordinary closure succeeds, and preserve PI
write latch/busy effects. The existing immediate DMA/HLE timing scope remains.
An inherited diagnostic change broke the raw EPi failure contract and is
restored. Absent-Pak and full-cartridge-address paths now have regressions.
Pinned oracle builds cache independently fingerprinted C++ objects so adapter
edits do not rebuild unchanged core objects. The full local gate passes; the
Paper Mario result is in research/paper-mario-native-frontier.md.

## ADR-0222: Observed call targets as address-taken discovery roots

Date: 2026-10-21. ADR-0221 is reserved by the separate OoT worker.

A call whose target is computed from data no instruction names (for example a
ROM checksum) has no candidate, no address-taken constant and no uncovered
fetch when its target lies inside an already declared image. Discovery never
reaches the callee, and the native address-taken dispatch faults 3 although
the computed value is correct.

The ADR-0190 analysis-time pinned ares replay now receives the open call sites
(no closed proof, linking register) and records the target register value as
each one executes. `harvest_boot.py` adds new pairs to the loads file as
`observed_roots`; discovery adds those targets to the address-taken roots
after the existing plausibility filter, alongside ROM-word and ROM-expression
roots. Computed jumps are not listed: their targets are usually returns or
labels inside a function, not function starts.

Observed targets are discovery inputs, never target certificates. The site
keeps no closed proof, whole-ROM closure still refuses it, and the native
address-taken dispatch remains fail-closed for every other value. The replay
is finite, deterministic and neutral-input, so it can only add roots that this
run executed. No game-specific value enters production code.

Verification: Rust tests show an observed target discovered and dispatched
while its site stays an unresolved indirect site under WholeRom, and an
implausible or misaligned target ignored. The oracle test records the exact
register target of a listed transfer, reports nothing for an unexecuted site
and rejects a misaligned site list; the harvest test lists only calls and adds
a repeated observation once. Dropping the roots, skipping plausibility,
disabling the oracle record and listing jumps are all caught. The Paper Mario
result is in research/paper-mario-native-frontier.md.

## ADR-0223: Residual sites dispatch over their own candidate targets

Date: 2026-10-21. Validation-only, extending ADR-0218.

A residual site dispatched only over lowered function entries. A jump table
whose case labels the map lists as candidates, but cannot prove closed, faulted
on every case, and its case blocks were not lowered at all: function bodies
follow only proven indirect edges, so the labels had no native code.

A residual jump now also reaches its candidate and observed targets when the
lowering computes function bodies, and its dispatch set includes them: block
starts for a jump (as `goto` labels), entries for a call. A jump candidate that
is not a label of the current function is left to the fault-3 default instead
of refusing the build. The default scope never passes residual sites, so its
bodies and dispatch are unchanged; manifests stay `native_complete: false`.

Verification: a lowering test strips the closure proof from a proven jump:
default lowering refuses it, residual lowering emits its candidate as a label
and keeps the fault-3 default. Excluding residual jumps from bodies and
dropping their own targets from dispatch are both caught.

## ADR-0224: PI DMA into a TLB-mapped destination

Date: 2026-10-21.

libultra starts a PI transfer with `osVirtualToPhysical(dramAddr)`, so a DMA
into a TLB-mapped buffer is written at the physical page the current TLB maps,
contiguously from there. The host DMA translated the address only for D-cache
bookkeeping and then refused the virtual address as outside KSEG0/KSEG1.

The host DMA now writes the translated physical address through the existing
runtime write gate (fixed-text, proof-data and declared-load protections are
unchanged). KSEG0 and KSEG1 destinations translate as before; an unmapped or
out-of-RAM destination is still refused. Verification: a raw PI DMA test maps
a 4 KiB page with `osMapTLB`, transfers ROM bytes into its virtual address and
reads them back through KSEG0; the previous code stops with "runtime write
refused" on it, as Paper Mario did.


## ADR-0225: ROM-backed PI DMA ranges as RSP search sources

Date: 2026-10-21.

A task boot can be copied from cartridge into RAM outside every discovered CPU
image. CPU-image-only RSP extraction cannot see those bytes. Analysis-time boot
harvest now records aligned, ROM-bounded PI DMA ranges outside all existing
images as `rsp_sources` in the loads file. They do not become CPU loads or
roots and do not require another CPU discovery round by themselves.

`rsp-from-rom --loads` reads those ranges from the canonical ROM as RSP-only
images. A DMA image is searched only at its start, and only when an existing
CPU image's data or decoded constant expressions name that address. Source
ranges must be nonempty, word-sized, eight-byte aligned and inside 8 MiB RDRAM;
ROM bounds are checked before constructing an image. A recognized task boot
shorter than IMEM may become its own IMEM-zero candidate. Existing full-size
placements, overlay hints, deduplication and runtime content/reachability guards
remain in force. `native.py` passes the harvested loads file to extraction.

These finite replay observations are candidate search inputs, never proof of
byte provenance, exhaustive coverage or target closure. Stale, transformed or
conflicting bytes must still pass native task guards; unknown tasks fail before
side effects. Manifests remain `complete: false`; no guest executor, reference
implementation code or per-game production constant is added. ROM-specific
observations belong in research/paper-mario-native-frontier.md.

Verification: deterministic harvest tests check filtering, deduplication and
no CPU rediscovery for RSP-only additions. The synthetic native contract moves
a boot outside the CPU image, checks extraction and native task output, and
requires fail-before-side-effects refusal without its source. It also rejects
empty/out-of-RAM/out-of-ROM ranges and ignores an unnamed source containing an
internal pointer. Integration measurements and mutation results are recorded
in the research note.

## ADR-0226: Replay evidence validates observed call entries

Date: 2026-10-21.

An observed call target is evidence that execution reached an entry, so
discovery may accept it without the usual preceding `jr ra` layout clue. The
entry must still pass `executed_start`: it is aligned, begins with a valid
instruction, and its body is CPU code. Discovery records the replay evidence
separately from static address-taken evidence. The guarded address-taken
solver accepts this alternative only when that evidence is present; an
observation alone does not close the originating indirect site's target set.

Synthetic regressions cover a called entry after a `j .` wait loop, rejection
when its replay evidence is removed, rejection when `executed_start` fails,
and mutation checks showing both discovery and solver clauses are required.


## ADR-0227: source-checked relocated replay sites and bounded call coverage

Date: 2026-10-21.

Analysis PCs in a composed image can differ from the addresses a replay CPU
fetches. Harvest projects open call sites using the ProgramMap's declared
load-image base and linked slot ranges; it requests both KSEG aliases. At the
actual instruction observation, sites and targets are projected back through
that same declaration set. A linked raw/segment source must match replay RAM
byte-for-byte, with no conflicting resident I-cache words, before its mapping
can contribute an observed root. Shared slots select only a unique matching
map address; missing or multiple matches refuse the observation. Fixed images
retain their declared addresses. Undiscovered targets retain their runtime
address for subsequent discovery. Numeric coincidence is not a slot identity.

Supported linked sources are unmodified raw bytes and format-bounded segment
or TLB-raw text. Raw ranges conservatively compare the entire declaration.
Compressed slots, dynamically placed relocating overlays, non-direct-mapped
runtime sources and multiple composed load images are not guessed: unsupported
open-site projection refuses harvest and unmatched target bindings contribute
no root. This is a conservative observation limit, not a new native binding
rule or a claim of provenance from equal bytes.

Replay retains the default 100M instruction calls. With requested open calls,
it may extend observation up to 1B calls or 3600 VI, stopping after the default
budget once every requested runtime site has an admitted observation. Earlier
uncovered-image stops still return immediately. Beyond 100M only call roots
are collected; snapshot capture stays within its existing reproducible budget
and Rust verification contract. Receipts report projected bindings, observed
and unobserved runtime sites, consumed steps/VI, stop reason and replay time.
The outer discovery loop remains bounded. A budget ceiling is not coverage.

Observations remain discovery roots, never finite-target closure certificates.
Native dispatch still rejects unknown targets; residual artifacts continue to
state native_complete: false. No runtime guest decoder, per-game production
constant, reference code reuse or additional dependency is introduced. The
analysis adapter continues to use the separately built pinned ISC ares source
with its notices; no ares code is copied into the native artifact.

Verification: synthetic fixed/relocated sites, shared-slot source selection,
equal-byte ambiguity, target projection, KSEG aliases, missing/unsupported
bindings, malformed inputs, finite-budget misses and later observations.
Mutation checks and local gate/game measurements are recorded in
research/paper-mario-native-frontier.md.


## ADR-0229: retain completed switch paths as candidates without closure

A bounded all-path table walk can finish a valid initialized predecessor and
then fail at a separate entry, clobber, unsupported edge or resource limit.
Discarding the completed witnesses loses discoverable case blocks even in the
explicit residual-validation mode. Keep the walk's already completed results
for non-linking switches when they agree on table base and count, and read their
complete source snapshot
through the existing caller-slot projection. Do not explore past failed paths,
raise budgets, bypass independent entries or infer an ABI. Nullable function-call
arrays retain their existing all-path behavior.

Evidence records incomplete_paths: true and explicitly states that other paths
remain unproven. Such evidence can add candidate targets and derived case decode
roots; it never supplies a closed_proof. The independent table verifier rejects
incomplete paths even if a certificate is forged. Complete-path evidence keeps
its existing serialized shape and exhaustive verifier. Incomplete candidates
impose no table-immutability or target-identity assumption: the unresolved
indirect site itself remains OPEN outside residual dispatch, and candidate
blocks and native target guards are still required. An unknown runtime target
continues to fault 3. No runtime guest decoding is introduced.

This is a generic analysis rule, with no game addresses, names, constants or
branches, and no new dependency or reference-code reuse. Synthetic fixed and
placed-slot cases cover initialized and independent paths, missing source/base,
forged closure and reachable native case coverage. Native CPU/PC/RAM state is
compared with pinned ares; a runtime table change to an unlisted target faults.
Mutation checks, discovery controls, full local gate timings and the visible
Paper Mario frontier are recorded in research/paper-mario-native-frontier.md.

## ADR-0230: discover completed raw occupants inside covered shared slots

Numeric executable coverage does not identify a slot's resident source. During
analysis-only pinned ares replay, retain complete aligned ROM-to-identity-RAM PI
transfers that intersect declared raw slots, including adjacent continuations.
Each byte must be observed after its write and match the exact ROM source.
Join only adjacent complete ranges with the same ROM/RAM displacement and load
site. Overlapping writes, including equal-value writes, invalidate the retained
producer; uncertain RDRAM mapping invalidates the history. Requests and partial
or misaligned effects alone cannot authorize an image.

At the producer's first instruction fetch, compare the whole range against
supported declared images. A matching prefix or shorter declaration does not
cover a larger occupant. When no declaration supplies the complete occupant,
require full ROM/RAM identity, coherent valid instruction-cache words, the actual
physical fetch and the fetched word. Emit a raw source declaration through the
existing content-bound shared-slot path. Python independently checks the complete
canonical ROM slice and bounds before appending it. No prefix search selects a
source; completed DMA provenance and complete content distinguish equal prefixes.
Unresolved/ambiguous projection still refuses observations and native dispatch.
A completed subrange of the same declared ROM source is already known even
if unrelated bytes elsewhere in that declaration differ. This does not relax
the existing projection guard or authorize a new observation.

Preserve existing slot declaration order when adding an alternate, so earlier
source-bound observed roots retain their synthetic map placements. Replay may
observe up to 2B instruction calls/3600 VI (formerly 1B); the ROM-only driver allows
16 refinement rounds (formerly eight). Snapshots still stop at 100M instructions
and retain ADR-0190/0220 reproduction and verification. Extended raw-source and
call observations never certify closure. The explicit residual artifact remains
native_complete: false; no interpreter, JIT or fallback is added to native mode.
ADR-0187 active-frame pins and all native content/alias controls remain unchanged.

Synthetic tests cover covered ranges, unequal full content after equal prefixes,
ROM byte orders, aliases, ambiguous declarations, adjacent producer chunks,
equal-value overwrites, partial producers, malformed source captures, stable
slot placement and stale later cache words despite an unchanged fetched word.
Mutation checks, exact-parent BK/F-Zero X/MM discovery comparisons, full local
gate receipts and the visible Paper Mario frontier are recorded in
research/paper-mario-native-frontier.md.

Pinned ISC ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 remains a separately
built analysis oracle. Its PI request/write/completion, RDRAM identity and CPU
fetch/cache boundaries were inspected; no upstream implementation is copied or
linked into the native artifact. Existing notices remain intact. No game-specific
production constants, ROM data or copyrighted capture is committed.

## ADR-0231: Bind TLB host register effects into callee certificates (partial)

A table-base requirement may cross a direct call to an explicitly declared
osMapTLB, osUnmapTLB or osUnmapTLBAll host boundary. Those project-owned host
implementations change TLB/binding state without writing GPRs or entering guest
callbacks or the scheduler. This is a host-effect contract under the existing
runtime ABI scope, not a guest callee-save convention or a proof about the
undecoded SDK body's registers. Other runtime names remain unsupported.

The boundary must have the current image/generation, no decoded guest block,
no callback or auxiliary ABI metadata, and no overlapping placed/linked slot
text. A successful effect consumes the existing shared budget, records the
exact runtime declaration, and contributes it to the table certificate hash.
The independent verifier recomputes the effect and declaration. Tail jumps to
runtime boundaries remain refused; unrelated guest return witnesses cannot be
supplied by a host contract. Guest writes, entries, source bindings, memory
lineage and full-path obligations retain their existing checks. The global
solver still refuses every declared runtime boundary outside runtime scope.
No executable guest decoder, game-specific fact or new scope is introduced.

Synthetic table loops cover direct/nested boundaries, source/metadata changes,
unsupported names, callbacks, unknown entries, decoded guest bodies and later
register clobbers. A host harness compares all state except the intended TLB
entries/generations, including full 64-bit GPRs, FPRs, PC, HI/LO, RAM and event
state. Existing pinned-ares/native TLB execution contracts remain mandatory.
No upstream implementation is copied.

Paper Mario remains OPEN with eight residual sites. The new contract passes
one earlier osMapTLB barrier, then correctly rejects a deeper guest overwrite;
no site receives a certificate merely because it has candidate targets. The
classification and exact validation receipts are in
research/paper-mario-native-frontier.md. Default native emission remains refused.
