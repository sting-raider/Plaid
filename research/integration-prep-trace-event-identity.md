# Integration prep: trace/event identity integrity

Status: **READY FOR PRIMARY-INTEGRATOR REVIEW**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Integration-prep branch: `integration-prep/trace-event-identity-gpt56sol`

Production candidate commits:

- `40a0db6442702a547e1ef1ab0f7991f3c02fb954` — source-bound `DiscoveryTrace` projection recheck, including exact `EntryInstalled` re-import binding;
- `be026b30b0e3f78510ced6c61abf520dd543a19f` — reconciled structural event-role and event-semantics invariant in `ProgramMap::validate()`.

The branch also retains the baseline regression/workflow commits used to reproduce the bugs and this integration note. Do not mechanically merge research branches.

## 1. Research reconciled

### VALIDATED inputs

- `research/dma-event-uniqueness-gpt56sol`
  - candidate production commit `c395922ee15a3f48ce2b2d53f93489ebb940e9f2`;
  - one concrete load `copy_event` must not name incompatible `(rom_offset, physical_destination, size)` DMA transactions.
- `research/word-store-event-uniqueness-gpt56sol`
  - baseline regression commit `257bd33efb6971084613b95f06955047337e78c2`;
  - validated formatted patch SHA-256 `be8147678948acc3bf23815b1991138dfc6647969842ef118034a5a92320fee3`;
  - one concrete store event must not fork `(site, destination, value, generation)`.
- `research/indirect-event-uniqueness-gpt56sol`
  - candidate production commit `da7b7ee5fd75a6411831208a989c7b1af54aa18d`;
  - one concrete indirect event must not fork `(site, target, delay_slot_pc, generation, source_unit)`.
- `research/entry-verification-event-uniqueness-gpt56sol`
  - final validated research head `b2a96a07363dc1d507cb00bd2c6ed4fa3572451c`;
  - one concrete verification event must not fork `(entry, register_mask, source_unit, verification_generation)`.
- `research/primitive-event-kind-exclusivity-gpt56sol`
  - candidate production commit `47ffb2c1ef7ea54b0514b021d339278a65f059c9`;
  - one concrete Trace event must not simultaneously claim incompatible primitive roles.
- `research/copy-event-kind-exclusivity-gpt56sol`
  - candidate production commit `b882ce7d44d8fcf2577076acbf9efdaba6ad34c3`;
  - a concrete DMA `copy_event` must not simultaneously masquerade as another raw primitive event.
- `research/discovery-trace-source-recheck-gpt56sol`
  - validated head `2e71d1da50b10ab6662aefbaaf3e9d69df0c88e4`, Actions run `38074159944`;
  - complete immutable source trace can authenticate raw DMA/store/indirect/verification projections without trusting `Evidence.detail` or value equality.

### PARTIAL input folded into the same source-bound abstraction

- `research/entry-install-event-uniqueness-gpt56sol`
  - validated source-recheck commit `a486ac89bb23ad3a80ccf7aacea871c4de670a46`, Actions run `38074757591`;
  - generic `ProgramMap` cannot distinguish a shareable `CompileBegin` Trace reference from a concrete `EntryInstalled` event, so installation identity must be checked against the complete source trace.
  - The standalone `entry_install.rs` module was intentionally **not** adopted. Its re-import check is folded into `trace_projection.rs` so there is one source-bound trace projection layer.

### REJECTED candidate preserved as a negative result

- `research/entry-verification-source-unit-binding-gpt56sol`
  - failing regression `26957335da71b1b00dac22c875722b69d5665f84`;
  - falsification commit `39d28acebbf7cee5f2802adf63834aa676c5aa51`;
  - the proposed Region-provenance membership join rejects an unrelated unit but **accepts an equal-byte, same-address, same-generation decoy** after provenance union.
  - That candidate is not present in this integration branch. The source trace recheck instead reconstructs the exact `CompileBegin` identity from ordered source events.

## 2. Bugs reproduced on current main

Baseline branch commit: `c732c3929677e18247e993e3ed6252be61b67d48`, with production still identical to canonical `main`.

GitHub Actions run `38108971659`, job `114380350153` first compiled the focused regression and then proved the following individually:

1. one `copy_event` can currently fork into two incompatible DMA transactions;
2. one store event can currently fork store semantics;
3. one indirect event can currently fork transfer semantics;
4. one verification event can currently fork verification semantics;
5. one Trace ID can currently cross primitive store/indirect roles;
6. a DMA `copy_event` can currently masquerade as a store event;
7. a DMA `copy_event` can currently masquerade as a `CompileBegin` source-unit identity;
8. independently valid maps can currently merge-launder one event across incompatible roles.

Each adversarial test was required to fail on unmodified production semantics, while the positive control proving legitimate reuse of one `CompileBegin` source-unit ID across distinct indirect events was required to pass. All nine baseline steps behaved as expected.

This also independently re-establishes the completed research against current `main`; the integration did not assume stale branch behavior.

## 3. Production invariant implemented

`ProgramMap::validate()` now applies one private `validate_trace_event_identities()` pass before consuming provenance references.

It keeps **role identity** and **semantic identity** distinct:

- explicit `LoadMapping.copy_event` Trace IDs claim role `DmaCopy` and one DMA transaction tuple;
- Trace IDs directly witnessing `ObservedWordStore` claim role `WordStoreEvent` and one store tuple;
- Trace IDs directly witnessing `ObservedIndirect` claim role `IndirectEvent` and one indirect tuple;
- Trace IDs directly witnessing `ObservedEntryVerification` claim role `EntryVerificationEvent` and one verification tuple;
- explicit `source_unit` IDs claim role `SourceUnit`.

A Trace ID may repeat with the **same** role and same semantics, allowing canonical facts to accumulate provenance. It may not acquire incompatible semantics or a different primitive role.

The crucial reconciliation is that an explicit `source_unit` ID is skipped when scanning the observation's generic evidence set for event identity and is then claimed separately as `SourceUnit`. This preserves the validated control where one `CompileBegin` context is shared by multiple events. The standalone primitive cross-kind patch did not make that distinction when the source-unit ID also appeared in generic provenance, so it was not adopted verbatim.

The structural pass deliberately does **not** classify arbitrary Trace references on Regions, entries, blocks or other derived facts. Provenance propagation remains legal.

`trace_projection.rs` provides the stronger source-bound layer. It recomputes the canonical trace-session hash, replays invalidation generations and unit identities, checks exact typed primitive projection, requires each source primitive exactly once after canonicalization, rejects wrong event kinds/deletions/transplants, and optionally re-imports the source to authenticate exact `EntryInstalled -> CodeAddress` binding.

Neither layer infers provenance from equal values.

## 4. Research patches intentionally not adopted

- No research branch was cherry-picked wholesale.
- No global rule that a Trace evidence ID may appear only once. That is falsified by legitimate `CompileBegin` provenance shared across multiple entries/events.
- No parsing or trusting of `Evidence.detail` to recover event kind.
- No Region-membership proof for `ObservedEntryVerification.source_unit`; the equal-byte decoy falsifies it.
- No standalone `entry_install.rs`; the source-bound re-import logic is consolidated into `trace_projection.rs`.
- No O(loads × observations) copy-event cross-kind scan from the standalone patch; copy-event role is handled by the same role table as the other primitive identities.
- No attempt to turn source recheck into sensor-completeness or hardware-truth evidence.

## 5. Test results and reproduction

Red/current-main receipt:

```text
Actions run 38108971659
job 114380350153
head c732c3929677e18247e993e3ed6252be61b67d48
result: SUCCESS, meaning all eight expected-red adversaries reproduced and the positive control passed
```

Integrated candidate receipt:

```text
Actions run 38109076829
job 114380667130
production candidate created as be026b30b0e3f78510ced6c61abf520dd543a19f before tests
result: SUCCESS
```

That candidate run passed:

```sh
grep -F '724a49a5b4dbfb99f1a9e6992e63964fd29c90c8' refs.lock.toml Cargo.lock
cargo test --locked -p plaid-core --test trace_event_identity -- --nocapture
cargo test --locked -p plaid-core --test trace_projection -- --nocapture
cargo test --locked -p plaid-core --test trace_entry_projection -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
git diff --check
```

All passed. No emulator or hardware semantic claim is involved in this cluster; the exact pinned Rabbitizer dependency was still checked and used through the lockfile.

## 6. Remaining uncertainty

This integration closes event-identity self-contradiction and source-projection authenticity for a supplied complete `DiscoveryTrace`. It does **not** prove that the trace source observed every relevant hardware event.

Remaining OPEN obligations include:

- the solver/certificate path does not yet require the source-bound trace recheck before consuming trace-derived positive proof;
- a source trace can be internally complete yet externally incomplete as a machine observation;
- event identity does not discharge executable writer completeness, physical backing, aliases/TLB context, cache-visible generations, transforms/decompression/relocation, overlay lifetimes, exception/interrupt/reset roots, RSP executable identity or WholeRom closure;
- the current generic evidence schema still cannot authenticate event kind when the immutable source trace is unavailable;
- no positive closure inference is added by this patch, so unresolved provenance remains OPEN.

## 7. Recommendation to the primary integrator

Review this branch as one evidence-integrity cluster. Prefer the final **semantic shape** over any individual research patch:

1. retain the consolidated structural `validate_trace_event_identities()` guard and `trace_event_identity` regressions;
2. retain `trace_projection.rs` and its primitive + EntryInstalled source-bound regression suites;
3. keep the `source_unit` context exemption exactly scoped to the explicitly typed source-unit ID;
4. do not adopt global Trace-ID uniqueness, Region-membership source binding, or `Evidence.detail` parsing;
5. wire source-bound projection verification into the eventual certificate/closure boundary before any Trace-derived fact is allowed to discharge a positive proof obligation.

Landing this cluster should still leave native completeness and whole-ROM closure unchanged/OPEN. The value is that later composition receives a less forgeable causal event graph rather than a more optimistic solver.
