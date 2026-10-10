# Primitive Trace event-role exclusivity

## Result

**VALIDATED** against canonical `main` `211176e7a489fecf8331d02915ee982cd279cb62`.

A session-qualified discovery-trace evidence ID names one concrete `TraceEvent` record, and `TraceEvent` is a tagged enum with exactly one variant. However, current-main `ProgramMap::validate()` validates retained CPU word-store, indirect-target, entry-byte-verification, and source-unit provenance largely independently. A hand-edited map, or the merge of two individually valid maps, can therefore reuse one Trace evidence ID in mutually exclusive primitive roles and still validate.

The smallest tested candidate records only the primitive role claimed by each Trace ID while validating:

- `ObservedWordStore.evidence` -> `word_store_event`
- `ObservedIndirect.evidence` -> `indirect_event`
- `ObservedEntryVerification.evidence` -> `entry_verification_event`
- `ObservedIndirect.source_unit` / `ObservedEntryVerification.source_unit` -> `source_unit`

Repeated use in the same role remains valid. Reuse in a different primitive role fails closed. Trace provenance on derived Regions/CFG facts is deliberately not classified, so the fix does not erase legitimate provenance propagation.

## Why this is a distinct composition gap

Completed research already attacks one Trace ID naming conflicting semantic tuples *within* the word-store, indirect, and entry-verification kinds. The completed copy-event-kind-exclusivity lane separately prevents a DMA `LoadMapping.copy_event` identity from masquerading as another primitive operation. Those are necessary but do not compose automatically: on canonical main, a non-DMA raw event ID can still cross from one primitive kind into another, or masquerade as the CompileBegin event used for `source_unit`.

This work therefore composes ADR-0009 (fabrication resistance), ADR-0021 (executing/source-unit provenance), ADR-0022 (entry verification), and ADR-0023 (monotone provenance union). It does not re-test same-kind tuple uniqueness and does not absorb the separate DMA copy-event candidate.

## Source invariant

`crates/plaid-core/src/trace.rs` defines `TraceEvent` as one tagged enum. `DiscoveryTrace::validate()` requires contiguous sequence numbers. `merge::import_trace` creates `trace:{session}:{seq}` once per event record and projects the concrete variant into its corresponding retained primitive fact:

- `CpuWordStoreObserved` produces one `ObservedWordStore`;
- `IndirectTargetObserved` produces one `ObservedIndirect`;
- `EntryBytesVerified` produces one `ObservedEntryVerification`;
- `CompileBegin` evidence is separately retained as the source-unit identity used by indirect and verification records.

Thus a single sequence ID cannot truthfully be two of these primitive events. Numeric equality of PCs, targets, values, epochs, or bytes cannot repair that causal contradiction.

## Current-main adversarial reproduction

Regression: `crates/plaid-core/tests/primitive_event_kind_exclusivity.rs`.

Red GitHub Actions run: `38080685282`, job `114296794191`, head `0700cfffefa3f3b33dcc7ef3f876803499afbc40` derived directly from canonical main before the candidate source change.

Command:

```sh
cargo test --locked -p plaid-core --test primitive_event_kind_exclusivity
```

The exact pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` was compiled. Result: **2 passed, 4 failed**. The four failed assertions prove current main accepted:

1. one Trace ID as both a CPU word-store event and an indirect-target event;
2. one Trace ID as both an indirect-target event and an entry-verification event;
3. a CPU word-store event ID reused as a CompileBegin `source_unit` identity;
4. merge, in both orders, of two individually valid maps that assign one Trace ID to store and indirect roles.

Two controls passed on unchanged main:

- distinct raw event IDs with one CompileBegin source-unit ID legitimately shared across indirect and entry-verification facts;
- a raw store event ID propagated only as provenance on a derived Region.

This isolates role collision rather than generic Trace-provenance reuse.

## Candidate fix

Candidate production commit: `47ffb2c1ef7ea54b0514b021d339278a65f059c9` (`fix: reject cross-kind primitive trace roles`).

The validator adds a small role table keyed by Trace evidence ID and rejects only a second, different primitive role. The deterministic patcher is `spikes/primitive-event-kind-exclusivity/apply_candidate_fix.py`.

The candidate deliberately does **not** parse the human-readable `Evidence.detail`, infer an event kind from addresses/values, or infer provenance from equal bytes. It relies only on the structural places where ProgramMap already treats a Trace ID as a primitive event/source-unit identity.

## Candidate evidence

Passing Actions run: `38080834427`, job `114297223514`.

The workflow applied the candidate to the exact canonical-derived branch, normalized formatting, and ran:

```sh
cargo test --locked -p plaid-core --test primitive_event_kind_exclusivity
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

Results:

- focused adversarial/control regression: **6/6 passed**;
- complete `plaid-core` suite: **109/109 passed**;
- formatting gate: passed;
- clippy with warnings denied: passed;
- the tested candidate was committed back to the research branch as `47ffb2c1ef7ea54b0514b021d339278a65f059c9`.

## Falsification attempts and controls

The candidate was tested against cases that should remain legal:

- distinct event IDs across primitive kinds;
- one source-unit ID shared by multiple observations;
- repeated provenance of a raw event on a derived Region;
- both merge orders for the laundering attack.

The guard is role-based rather than value-based, so equal values/addresses do not collapse distinct events. It also does not globally reserve Trace IDs, which would incorrectly forbid a concrete event from contributing provenance to derived facts.

## Closed-world impact

Before the candidate, ProgramMap provenance union could manufacture an impossible raw history: one concrete trace sequence could become multiple mutually exclusive primitive operations after editing or merge. Any later solver or provenance composition that trusted those retained facts would be reasoning from fabricated causal history even if each fact looked locally well formed.

The candidate removes the tested non-DMA cross-kind fabrication path. It does **not** make WholeRom closure complete; it protects one structural premise needed before primitive observations can be safely composed.

## Remaining gap

- Same-kind semantic uniqueness remains the responsibility of the separate word-store, indirect, and entry-verification candidate branches; this branch intentionally does not duplicate them.
- DMA/copy-event kind exclusivity remains the responsibility of the separate completed copy-event lane; this branch does not silently absorb it.
- A generic `EvidenceKind::Trace` still does not cryptographically or structurally encode the original `TraceEvent` variant. A future typed event-role schema would be cleaner than accumulating validator-side role tables.
- Trace authenticity/completeness, sensor coverage, executable lifetime, cache/TLB provenance, and WholeRom closure remain separate obligations.

## Integration recommendation

**ADOPT selectively.** Integrate the role-exclusivity validator guard and regression together with the completed same-kind uniqueness and DMA copy-event guards, ideally refactoring the combined result toward an explicit typed trace-event identity/role representation. Do not treat this candidate alone as proof that all Trace evidence is authentic or complete.
