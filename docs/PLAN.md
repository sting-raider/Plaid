# Research and Implementation Plan

## Current execution order

The immediate implementation order is ProgramMap, discovery trace, pinned Mupen
exporter and synthetic tests, ROM normalization, direct CFG, evidence merger,
indirect analysis, DMA/overlay analysis and fail-closed solver. This refines the
historical phase order below without restarting the architecture. STATUS and NEXT
record the verified scope and remaining work; native lowering follows useful
executable discovery.

## Thesis

Existing emulators already know how to execute arbitrary N64 programs dynamically, while N64Recomp proves that known N64 programs can be transformed into native host code. Plaid will bridge the two by converting runtime discovery into a complete, persistent program representation suitable for static/native linking.

## Phase 0 - Reproducible reference lab

Goal: make upstream research inspectable and stable.

Deliverables:

- pinned reference commits in `refs.lock.toml`;
- scripts that clone references into `.refs/`;
- source/license notes in `docs/SOURCES.md`;
- a test policy that never commits commercial ROMs.

Exit gate: every architectural claim points to either a test, a pinned implementation, or an experiment.

## Phase 1 - ROM ingestion and identity

Goal: canonicalize ROM input without pretending this is the hard part.

Deliverables:

- detect `.z64`, `.v64`, and `.n64` byte order;
- normalize to canonical big-endian representation in memory;
- parse header, entry point, region/version, CRC fields;
- hash canonical ROM for cache/metadata identity;
- never commit the ROM itself.

Exit gate: deterministic identity for local ROM inputs.

## Phase 2 - Dynamic executable-map extractor

Goal: turn a mature dynarec's "compile whatever PC reaches" behavior into a machine-readable discovery trace.

First reference target: Mupen64Plus `new_dynarec` at the pinned commit.

Capture at minimum:

- guest basic-block start/end addresses;
- direct branch/call edges;
- observed indirect branch targets;
- branch-delay-slot behavior;
- ROM->RAM executable DMA/copy events when detectable;
- overlay load/unload/relocation observations;
- RSP microcode hashes/locations;
- invalidation/self-modifying-code events if observed.

Preferred implementation: maintain a small patch series or fork used strictly as a research instrument, not as the final runtime.

Exit gate: deterministic trace schema and replayable traces from test ROMs.

## Phase 3 - Static discovery engine

Goal: recover everything that does not need execution.

Inputs:

- canonical ROM;
- entry point / boot information;
- instruction semantics/decoder;
- optional known-library signatures;
- optional dynamic trace evidence from Phase 2.

Analysis:

- recursive direct control-flow discovery;
- function-candidate recovery;
- jump-table recognition;
- pointer/reference tracking;
- code/data partition evidence;
- overlay and relocation inference;
- known libultra/library identification.

External tools are allowed initially (spimdisasm, Rabbitizer, n64sym). Long term, keep the project-owned executable-map format independent of any one tool.

Exit gate: on a known test corpus, our recovered map can be compared against independently known metadata and runtime traces.

## Phase 4 - Closed-world solver

Goal: determine whether a ROM can be safely frozen into a native executable.

The solver merges:

- static CFG edges;
- observed runtime edges;
- jump-table target sets;
- overlay maps;
- relocation information;
- executable memory writes/copies;
- known dispatch tables/signatures.

It must produce either:

1. `CLOSED`: all executable targets for the declared compatibility scope have a native representation; or
2. `OPEN`: unresolved edges remain, with exact diagnostics.

No "probably complete" state.

Exit gate: machine-readable unresolved-target report reaches zero for the first target ROM.

## Phase 5 - Native lowering and link model

Goal: emit permanent host code rather than ephemeral JIT blocks.

Key design constraints:

- preserve guest-visible N64 addresses even when host function addresses differ;
- represent guest-address->native-function mapping explicitly;
- lower direct calls to native calls where safe;
- lower finite indirect target sets to native dispatch structures;
- emit relocatable object code or an equivalent linkable intermediate artifact;
- keep guest memory semantics explicit.

Backend candidates:

- adapt concepts/code paths from N64Recomp;
- Cranelift object generation;
- LLVM only if evidence justifies the extra complexity.

Exit gate: synthetic MIPS program becomes a host-native executable/object and matches the reference execution state.

## Phase 6 - Native compatibility runtime

Goal: provide the N64 services the recompiled program expects without running a guest CPU.

Runtime domains:

- RDRAM/guest address model;
- PI/SI/VI/AI/MI behavior required by recompiled code;
- interrupts/timers/events;
- controller input;
- saves (EEPROM/SRAM/FlashRAM);
- libultra-style services where safe to replace natively;
- RSP task boundary;
- renderer boundary.

Study N64ModernRuntime, Gopher64, ares, and Mupen behavior. Do not assume implementation reuse until licensing is decided.

Exit gate: first target boots and runs in native-only mode with differential checks against a reference implementation.

## Phase 7 - Graphics and RSP strategy

Do not rewrite the universe early.

Initial plan:

- evaluate RT64 integration for native rendering;
- use existing RSP recompilation/reference work to design a native RSP path;
- identify custom microcode by content hash/signature;
- keep an explicit compatibility matrix for unsupported microcode.

Exit gate: rendering/audio/RSP path has no hidden guest CPU fallback.

## Phase 8 - Compatibility ladder

Suggested progression:

1. synthetic/system tests;
2. simple commercial title with mostly static code;
3. title with common libultra patterns;
4. overlay-heavy Zelda-family title;
5. Rare title with more aggressive/custom behavior;
6. custom-microcode / difficult titles;
7. representative set of ~25 games;
8. ~100 games;
9. full 388-game commercial-library campaign.

For every title record:

- closed-world status;
- unresolved edges;
- overlay count;
- indirect target coverage;
- RSP microcodes;
- boot/gameplay completion status;
- correctness regressions.

## What would count as a breakthrough?

Not "we wrote a MIPS compiler." That already exists.

The breakthrough is:

> An untouched ROM, with no game-specific ELF/symbol project supplied by the user, is automatically converted into a native package whose gameplay path contains no MIPS interpreter/JIT and whose behavior is verified against a reference implementation.
