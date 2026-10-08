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
