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
