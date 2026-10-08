# Plaid Parallel Research Orchestration

This file governs **auxiliary experimental research workers**. It complements `AGENTS.md`; it does not replace Plaid's architectural invariants.

## 1. Roles

### Primary integrator

One continuing Codex implementation session owns canonical integration. It decides what lands on the active integration branch, reconciles overlapping findings, reruns required tests, and updates `docs/STATUS.md`, `docs/NEXT.md`, and `docs/DECISIONS.md`.

### Research worker

A research worker owns one bounded hypothesis or experimental slice. It may freely:

- clone/fetch Plaid and pinned upstream references;
- create an isolated branch/worktree;
- patch Plaid, Mupen, ares, Gopher64, N64Recomp, or other legal reference code for experiments;
- compile and run software;
- build synthetic N64 fixtures and harnesses;
- instrument reference implementations;
- fuzz, benchmark, trace, disassemble, compare, and differential-test;
- create temporary tooling and prototype candidate implementations;
- produce commits/patches for later review.

Research workers do **not** own canonical integration unless explicitly promoted by the user/primary integrator.

## 2. Canonical state

Repository: `sting-raider/Plaid`

Current active integration branch: `main`

The user authorized direct work on `main` on 2026-10-09. The tested
`codex/executable-discovery` history was fast-forwarded into `main`; that older
branch remains a historical checkpoint. New canonical work uses small tested
commits on `main`. Research branches still require primary reconciliation.

Before selecting work, read in this order:

1. `AGENTS.md`
2. `ORCHESTRATION.md`
3. `docs/STATUS.md`
4. `docs/NEXT.md`
5. `docs/DECISIONS.md`
6. `SWARM_BACKLOG.md`
7. relevant files under `research/`, `spikes/`, `experiments/`, and `instruments/`
8. recent commits on `main`
9. open PRs/issues and the shared coordination ledger: GitHub issue #4

Then inspect the relevant pinned reference revision from `refs.lock.toml`.

## 3. Shared coordination ledger

Live claim ledger: `https://github.com/sting-raider/Plaid/issues/4`

Every parallel worker must inspect that issue before doing substantive work.

Before starting, post:

```text
CLAIM
worker: <short chat/session identifier>
started_utc: <timestamp>
lane: <bounded research slice>
hypothesis: <specific proposition to prove/disprove>
touching: <Plaid paths / upstream repos / experiments likely to change>
expected_output: <research note / spike / patch / tests / measurements>
```

Keep claims narrow enough that another worker can choose a genuinely different lane.

### Lease rule

Claims are leases, not permanent ownership.

A claim becomes recoverable after roughly **35 minutes without meaningful durable progress**. Meaningful progress is one or more of:

- a commit;
- a substantive claim-ledger update containing concrete evidence;
- a reproducible test result;
- a research note/spike update;
- a useful patch/harness/checkpoint.

`still working` is not meaningful progress.

If recovering an expired claim, inspect its branch, commits, notes, and artifacts first. Preserve useful work. Prefer semantic recovery/transplant over blind rewrites.

## 4. Isolation rules

Parallel research is intentionally aggressive; canonical integration is intentionally conservative.

- Never force-push or rewrite the active integration branch.
- Prefer `research/<topic>-<shortid>` branches or isolated worktrees for experiments.
- Do not directly merge into `main` unless the user or primary integrator explicitly assigns integration ownership.
- It is fine to make invasive temporary patches to upstream references in a disposable experimental checkout.
- Keep reference modifications clearly separated from project-owned production code and preserve license boundaries.
- No ROMs, firmware, copyrighted game assets, generated traces containing redistributed copyrighted content, secrets, or credentials in git.

### High-conflict paths

Treat these as integration-sensitive:

- `crates/plaid-core/src/program.rs`
- `crates/plaid-core/src/fetch.rs`
- `crates/plaid-core/src/solver.rs`
- `crates/plaid-core/src/merge.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- `instruments/mupen/discovery.patch`

Multiple workers may study them, but only one active claim should own the same implementation slice. Prefer new `research/` notes and numbered `spikes/` for parallel experiments.

## 5. Work selection

Choose work in this order:

1. recover valuable expired executable/research work;
2. take a high-value unclaimed blocker from `docs/NEXT.md`;
3. independently attack a current assumption with an adversarial fixture or second oracle;
4. investigate a distinct reference implementation path that can reduce an open blocker;
5. prototype a future subsystem only when it cannot destabilize current architecture and clearly labels itself exploratory.

Do not manufacture work merely to keep a worker busy. Search existing notes/commits first.

## 6. Current high-value research lanes

These are broad lanes, **not claims**. Workers must claim a bounded subproblem.

### A. Executable-byte provenance / backing transactions

Current top priority. Observe actual backing reads/writes and unify the ordering of:

- bus/device reads;
- RAM/SP/PIF backing changes;
- instruction-cache fills;
- cache operations and writebacks;
- CPU stores/copies;
- DMA/copies;
- instruction fetches.

Goal: determine what evidence is sufficient to construct a trustworthy executable image identity/lifetime without confusing PC, physical address, cache tag, or current RAM contents with byte origin.

### B. Non-PI executable copies and mutation

Extend beyond the current partial constant aligned cached-RDRAM `SW` sensor:

- other store sizes/forms;
- general addresses;
- uncached and TLB paths;
- CPU memcpy-style loops;
- SP/RDRAM movement;
- source provenance;
- restored executable targets;
- executable mutation classification.

### C. Indirect-control-flow closure

Attack finite target proofs rather than mere samples:

- pointer-table immutability;
- guard coverage;
- cross-block propagation;
- joins/loops;
- ABI patterns;
- adversarial tables and aliases;
- proof invalidation after executable/data mutation.

### D. Overlays, decompression, relocation, aliases

Research and test:

- decompression into executable RAM;
- CPU copies after DMA;
- address aliases;
- overlay unload/reload;
- relocation and instruction patching;
- same-address/different-generation behavior;
- different-address/same-physical-history behavior.

### E. Whole-ROM closure obligations

Develop evidence/verifiers for:

- boot/CIC roots;
- exception and interrupt entry paths;
- TLB/address/execution modes;
- executable mutation policy;
- RSP identity/execution universe;
- load/copy/overlay lifetime completeness.

No flag may simply waive these obligations in a native-complete claim.

### F. Reference-oracle expansion

Use ares, Mupen, Gopher64, n64-systemtest and other pinned references to add independent checks for:

- exceptions;
- TLB;
- LL/SC;
- COP0;
- COP1/FPU;
- cache behavior;
- RSP behavior;
- timing-visible semantics.

Instrumented and uninstrumented checkpoints must agree within the declared scope.

### G. Static-analysis enrichment

Investigate:

- `n64sym`/known library signatures;
- spimdisasm-derived evidence adapters;
- source/license-safe signature databases;
- provenance-bearing hints that never silently become closure proof.

### H. Scalability / artifact size

Measure before optimizing:

- raw trace volume;
- ProgramMap size;
- import/verify time;
- memory usage;
- streaming/coalescing strategies;
- chronology retention costs.

Do not trade away evidence required for rechecking simply to shrink files.

### I. Native-backend exploration (deferred integration)

Tiny isolated prototypes are allowed, but serious production lowering remains deferred until executable discovery is demonstrably useful. Any worker exploring native codegen must avoid changing Plaid's production path and must include differential reference tests.

## 7. Experimental contract

Every experiment begins with a falsifiable hypothesis.

A good experiment records:

1. exact Plaid commit and upstream pinned revision;
2. hypothesis;
3. baseline behavior;
4. smallest instrumentation/patch needed;
5. fixture/input construction;
6. exact commands;
7. deterministic observations;
8. instrumentation-neutrality check when applicable;
9. negative/counterexample cases;
10. result: `VALIDATED`, `REJECTED`, `PARTIAL`, or `BLOCKED`;
11. limitations and what the result **does not** prove.

Never upgrade:

- observation -> exhaustive proof;
- physical address -> byte origin;
- cache tag -> resident-byte history;
- compilation -> execution;
- repeated runs -> universal coverage;
- one game's behavior -> N64-wide invariant.

## 8. Testing expectations

Research workers are expected to run software, not merely read it.

Prefer:

- controlled synthetic MIPS programs;
- paired instrumented/uninstrumented runs;
- independent oracle comparison;
- deterministic replay/checkpoints;
- state hashes;
- adversarial cases designed to break the proposed invariant;
- complete raw-source verification where provenance matters.

When touching Plaid production code, run the relevant Rust tests plus formatting/Clippy where practical. When patching a reference implementation, prove the instrumentation did not change the reference result for the tested scope.

## 9. Durable outputs

A useful worker session should leave at least one durable artifact:

- `research/<topic>.md`;
- `spikes/<NNN>-<topic>/`;
- deterministic test fixture/harness;
- isolated branch commit;
- patch/diff;
- benchmark/trace summary;
- precise negative result that closes a bad approach.

Do not dump gigantic generated traces into git. Record hashes, commands, summaries, schemas, and ignored artifact locations instead.

## 10. Closeout

Before a worker stops, post to issue #4:

```text
CLOSEOUT
result: <VALIDATED / REJECTED / PARTIAL / BLOCKED>
artifacts: <branch, commit(s), note, spike, test commands>
key_evidence: <concise concrete findings>
remaining_gap: <what is still unknown>
integration_recommendation: <ADOPT / REJECT / INVESTIGATE / PRIMARY-INTEGRATOR-REVIEW>
```

If time is running out, publish a useful checkpoint early rather than keeping all progress only in chat/context.

## 11. Integration handoff

The primary integrator should:

1. inspect the worker's evidence and exact scope;
2. rerun or independently reproduce important claims;
3. compare against current `docs/STATUS.md` / `docs/NEXT.md` and newer commits;
4. cherry-pick, transplant, or reimplement only the useful semantic slice;
5. avoid merging stale branch state wholesale;
6. update authoritative docs only after integration/reproduction;
7. close or redirect superseded claims.

Research branches are disposable. Evidence is not.

## 12. North star

Parallelism exists to shorten the path to:

```text
N64 ROM
  -> trustworthy executable-byte provenance
  -> complete ProgramMap
  -> closed-world proof for a declared scope
  -> MIPS-to-native AOT compilation
  -> verified native runtime
  -> no runtime MIPS interpreter/JIT in native-complete mode
```

The workers are not competing to write the most code. They are competing to eliminate uncertainty without duplicating each other.
