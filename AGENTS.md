# AGENTS.md

## Mission

Build an automatic N64 ROM-to-native recompilation system. The final native gameplay path must execute host-native x86-64 or ARM64 code and must not depend on a runtime MIPS interpreter or runtime MIPS JIT.

## Hard invariants

1. **Correctness is defined by tests and reference behavior, never by model confidence.**
2. **No hidden emulation in native mode.** Compiler-time tracing, emulator instrumentation, and differential testing are allowed. The final native artifact may not silently fall back to guest instruction execution.
3. **Closed-world gate.** Do not emit a "fully native" artifact while any executable target, overlay, relocation, or indirect control-flow edge required by the supported execution model remains unresolved.
4. **No ROMs or copyrighted game assets in git.** Tests should use synthetic inputs, legal open test ROMs, hashes, metadata, or user-supplied local paths ignored by git.
5. **Do not copy code across repositories casually.** Check the source license first. Record reuse decisions in `docs/DECISIONS.md` and preserve required notices.
6. **No game-specific hacks disguised as general analysis.** A compatibility exception must be documented, isolated, justified, and preferably generalized before merge.
7. **Every compiler transformation needs a verifier.** At minimum test register state, PC/control flow, memory writes, exceptions, and relevant timing/event effects.
8. **No performance work without a baseline.** Correctness before speed.

## Agent workflow

Use one continuing **primary implementation/integration session** for canonical Plaid changes. Parallel experimental research workers are explicitly allowed under `ORCHESTRATION.md`: they may patch, compile, instrument, fuzz, benchmark, and test in isolated branches/worktrees, but the primary integrator owns reconciliation into the active integration branch.

`SWARM_BACKLOG.md` remains a legacy/high-level task ledger rather than an instruction to duplicate work. All workers must read `ORCHESTRATION.md`; parallel workers must inspect and use the shared claim ledger in GitHub issue #4 before starting overlapping work.

Read and maintain `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and relevant research notes. Commit coherent, tested milestones and continue through routine steps without waiting for approval. Executable discovery precedes serious native lowering.

For each task:

1. Read `README.md`, `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/SOURCES.md`, `ORCHESTRATION.md`, and this file.
2. Read the relevant upstream/reference implementation at the pinned commit from `refs.lock.toml`.
3. State the hypothesis in the issue/experiment note.
4. Make the smallest change that can prove or disprove it.
5. Add deterministic tests before claiming success.
6. Run the applicable test suite.
7. Record measurements or behavioral diffs in `research/` or `experiments/` when the result affects architecture.
8. Update `SWARM_BACKLOG.md` only for task status/ownership, not as a substitute for technical documentation.

## Native-mode acceptance

A native build is accepted only when:

- every reachable direct control transfer resolves;
- every supported indirect control transfer has a closed target set or an equivalent proven native dispatch representation;
- executable overlays and their relocations are known;
- executable DMA/copy behavior is accounted for;
- no runtime guest instruction decoder is linked into native mode;
- differential tests pass for the declared coverage scope.

## Reference implementations

Use the repositories pinned in `refs.lock.toml`. They are references, test oracles, and research sources. They are not automatically dependencies.

Priority references:

- N64Recomp: static-recompilation architecture and live recompiler.
- Mupen64Plus core: runtime dynarec discovery and mature compatibility behavior.
- ares: accuracy-oriented N64 behavior.
- Gopher64: readable Rust N64 implementation and behavioral reference.
- N64ModernRuntime: native runtime boundary design.
- RT64: modern native N64 rendering path.
- spimdisasm/Rabbitizer/n64sym: static analysis, instruction decoding, and known-symbol discovery.
- n64-systemtest: correctness corpus.

## Coding rules

- Rust is the default language for new project-owned code unless an experiment proves a stronger reason otherwise.
- Keep unsafe code narrow and documented.
- Favor explicit guest-address types over raw integers.
- Never conflate guest pointers with host pointers.
- Keep analysis artifacts deterministic and versioned by schema.
- Prefer machine-readable trace/map formats over log scraping.
- Do not optimize away N64-visible behavior for convenience.

## Definition of "done"

A task is not done because code compiles or a game reaches a title screen. It is done when its acceptance criteria are reproducibly verified and documented.
