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
