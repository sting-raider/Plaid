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
