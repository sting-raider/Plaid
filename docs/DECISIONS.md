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

Status: Open

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

Status: Accepted for research, 2026-10-09.

The recovered full ares TLB fixture reproduces the exact worker receipt. Extend
the finite identity-RDRAM scalar/fetch join only for an actually resolved uncached
access. Retain virtual PC, current translated address and post-endian bus address;
equal-valued virtual aliases and TLBWI remaps are different contexts. Failed
translations and cached mappings provide no scalar-fetch witness. CCA 2/3 routing
is pinned ares evidence, not an N64-wide hardware assertion. Mapping generations,
TLBWR/restore, broader page/mode cases and exhaustive reachability remain open.
Original fixtures generate ignored licensed reference builds; no emulator code
or asset enters production. No ProgramMap or closure gate changes.

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

Status: Accepted for research, 2026-10-09.

The reproduced CPU-to-SP-IMEM fixture proves that successful SB/SH can overwrite
four bytes with shifted unmasked rt.u32; nominal opcode width/payload truncation
would lose both mutation span and source bits. Record post-translation/endian
concrete sink address, full aligned Word effect and exact payload. Faulting odd
SH supplies no mutation. Pinned systemtest/Gopher source agrees; Mupen masked
source disagrees, so preserve the oracle conflict. Forced endian/component tests
and source expectations do not replace physical hardware evidence or prove other
sinks/lifetimes. Original fixture builds ignored licensed ares separately; no
reference code or assets enter production.

## ADR-0067: D-cache lineage needs resident mutation revisions and exact scope

Status: Accepted for research, 2026-10-09.

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

## ADR-0104: Cache-error root exclusion requires target-hardware evidence

Status: Accepted for bounded production root policy, 2026-10-11.

For a declared Nintendo 64 / NEC VR4300 execution scope, encode the
cache-error exception class as `ExcludedByTargetHardware` using NEC manual
`U10504EJ7V0UM00`, Appendix B.1.7 / Table B-1. The target has no cache
parity/error mechanism and the cache-error exception does not occur. Preserve
the manual authority in the report and recompute it from an explicit typed
target; generic MIPS III remains `Unresolved`.

Emulator silence, finite traces, CacheErr register value equality, or absence
of a modeled transition are not exclusion evidence. This bounded negative fact
does not certify general/TLB/interrupt/watch/reset/NMI reachability, exception
chronology, handler bytes, cache/mapping lifetime, complete root census,
whole-ROM closure or native completeness. `whole_rom_roots_certified` and
`native_complete` remain false and no solver gate is weakened.
