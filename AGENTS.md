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

## Integration modes

Plaid supports two modes.

### Normal mode

A continuing primary implementation/integration session owns canonical integration. Parallel research workers operate in isolated branches/worktrees, publish evidence, and hand integration-ready work to the primary integrator.

### User-authorized direct-integration mode

When the user explicitly authorizes direct integration, multiple workers may prepare and validate independent production changes in parallel. Canonical writes are serialized by **exact-head compare-and-swap (CAS)**, not by a main-write lease.

A direct-integration worker must:

1. fetch current `main` and record exact SHA `A`;
2. reconcile its candidate onto `A`;
3. run the required local validation on that exact resulting tree;
4. refetch `main` immediately before the canonical write;
5. if `main != A`, reconcile onto the new head and rerun validation;
6. if `main == A`, create a commit whose parent is exactly `A` and atomically update `main` with `expected_sha=A`;
7. if the CAS is rejected, treat it as normal main drift, fetch the winner, reconcile, retest, and retry;
8. never force-push or bypass the expected-head check.

The invariant is simple: **nothing may land on `main` unless the final validated commit is a direct child of the exact canonical head against which that final validation was performed.**

Issue #4 claims coordinate semantic work ownership and prevent duplication. They do not reserve `main`.

## Capability preflight for direct integration

A worker must prove it can perform the required local validation **before it claims a direct-integration lane or begins implementation**.

At minimum verify:

```bash
git rev-parse --show-toplevel
git status --short
cargo --version
rustc --version
rustfmt --version
python --version
```

The checkout must be writable and must contain the current Plaid workspace. If the intended cluster depends on an exact pinned reference, the required revision must also be locally available or locally fetchable without relying on GitHub Actions.

If the worker lacks the basic local checkout/toolchain needed for the mandatory gates, it must **not** spend the session preparing a direct-integration candidate. It should return a short `CAPABILITY-SKIP` result and leave the lane unclaimed so an execution-capable worker can take it.

If a missing task-specific capability is discovered only after useful candidate work already exists, preserve the work as a `VALIDATION-HANDOFF` rather than calling the integration semantically `BLOCKED`. See `ORCHESTRATION.md`.

`BLOCKED` is for a real technical/integration blocker, not simply "this chat has no cargo".

## Agent workflow

`SWARM_BACKLOG.md` is a high-level/legacy task ledger rather than an instruction to duplicate work. All workers must read `ORCHESTRATION.md`; parallel workers must inspect issue #4 before starting overlapping work.

Read and maintain `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and relevant research notes. Commit coherent, tested milestones and continue through routine steps without waiting for approval. Executable discovery precedes serious native lowering.

For each task:

1. Read `README.md`, `docs/PLAN.md`, `docs/ARCHITECTURE.md`, `docs/SOURCES.md`, `ORCHESTRATION.md`, and this file.
2. In direct-integration mode, run the capability preflight before claiming work.
3. Read the relevant upstream/reference implementation at the pinned commit from `refs.lock.toml` when needed.
4. State the hypothesis or integration claim in issue #4 / the experiment note.
5. Make the smallest coherent change that proves, disproves, or productizes the intended invariant.
6. Add deterministic tests before claiming success.
7. Run the applicable local test suite.
8. Record measurements or behavioral diffs in `research/` or `experiments/` when the result affects architecture.
9. Update `SWARM_BACKLOG.md` only for task status/ownership, not as a substitute for technical documentation.

## Local validation

GitHub Actions is manual-only and is not the canonical gate for ordinary integrations.

When production Rust changes are involved, run locally at minimum:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
```

Also run focused regressions, relevant retained synthetic contracts, `python tools/progress.py --check` when progress data changes, and exact pinned-reference checks when semantics depend on a reference implementation.

Historical CI can support a claim, but it does not replace validation of the exact tree being proposed for `main`.

## Validation handoff

Useful candidate work must not be thrown away merely because the producing session cannot execute the final local gate.

A worker with a prepared candidate but an unavailable validation capability should post a `VALIDATION-HANDOFF` containing the candidate branch/head, prepared base, cluster, changed paths, already-reproduced evidence, exact remaining local commands, and the missing capability.

An execution-capable worker may then claim `VALIDATION-TAKEOVER`, reconcile the semantic candidate onto current `main`, run the complete local gate on the exact tree, and CAS-land it normally. The takeover worker owns the final validation and canonical closeout.

Do not weaken the validation standard to avoid a handoff.

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

Priority references include N64Recomp, Mupen64Plus core, ares, Gopher64, N64ModernRuntime, RT64, spimdisasm/Rabbitizer/n64sym, and n64-systemtest.

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
