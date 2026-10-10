# Generic Trace cross-kind event-role exclusivity

Result: **VALIDATED** against canonical `main` `211176e7a489fecf8331d02915ee982cd279cb62`.

## Question

Can one source-bound raw trace event identity be reused as more than one incompatible primitive event kind after `ProgramMap` editing or merge, even though the importer emitted that identity for exactly one trace record?

This investigation is deliberately narrower than trace authenticity. It asks only whether the already-retained session-qualified identity can be made to represent mutually exclusive primitive operations.

## Source contract

`merge::import_trace` computes one ID `trace:{session}:{seq}` for each raw trace record. For the three event variants tested here it passes a singleton `EvidenceRefs` containing that ID into exactly one of:

- `ObservedWordStore` for `CpuWordStoreObserved`;
- `ObservedIndirect` for `IndirectTargetObserved`;
- `ObservedEntryVerification` for `EntryBytesVerified`.

`CompileBegin` provenance used by `ObservedIndirect.source_unit` and `ObservedEntryVerification.source_unit` is stored explicitly and is reusable context. It is not the executed-event identity.

Therefore one imported event ID cannot truthfully be both, for example, a successful SW and an indirect transfer. Equal addresses, generations, values, or payloads do not repair that causal contradiction.

## Reproduction on current main

Branch: `research/generic-trace-cross-kind-exclusivity-gpt56sol`

Baseline test head: `dc38e9b84555288769785a55073161e8b1c247e1`

Actions run `38073536969`, job `114275674422`, compiled exact pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` and ran the 7-case focused regression against unchanged production validation.

Result: **3 controls passed / 4 adversarial assertions failed** because canonical `ProgramMap::validate()` accepted:

1. the same Trace ID as both `ObservedWordStore` and `ObservedIndirect` event evidence;
2. the same Trace ID as both `ObservedWordStore` and `ObservedEntryVerification` event evidence;
3. the same Trace ID as both `ObservedIndirect` and `ObservedEntryVerification` event evidence;
4. two individually valid maps whose merge launders one store-event identity into an indirect-event role. Both merge orders are asserted.

The passing controls establish that distinct primitive event IDs remain valid, explicit `CompileBegin` source-unit context can be shared, and a primitive Trace ID may propagate into a derived `Region` without being mistaken for another primitive operation.

## Candidate invariant

Candidate production commit: `417133155b0b5d6ac2736c0f5afc2c140215fefd`.

During `ProgramMap::validate()`, classify Trace evidence IDs appearing in the three tested primitive observation containers as one of:

- `cpu_word_store`;
- `indirect_target`;
- `entry_verification`.

A Trace ID may recur with the same role. It may also occur freely in derived facts. For `ObservedIndirect` and `ObservedEntryVerification`, an evidence ID equal to the row's explicit `source_unit` is skipped because that `CompileBegin` identity is reusable context rather than the primitive event identity. Reuse of one Trace ID across two different primitive roles fails closed with `primitive trace event reused across incompatible event roles`.

This is intentionally not global Trace-ID uniqueness.

## Falsification controls

The candidate was tested against cases that would reject an over-broad rule:

- distinct primitive event IDs coexist;
- the same explicit `CompileBegin` source-unit ID may be present as context on an indirect observation and entry verification;
- primitive event provenance may also support a derived `Region`;
- same-role reuse is not rejected by this cross-domain guard, leaving within-kind semantic uniqueness to the dedicated neighboring invariants.

## Executable evidence

Candidate Actions run `38073617342`, job `114275911970`: **SUCCESS**.

- focused regression: `7 passed; 0 failed`;
- full `cargo test --locked -p plaid-core`: **110 passed; 0 failed**;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: PASS;
- exact pinned Rabbitizer `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` compiled;
- candidate committed by CI as `417133155b0b5d6ac2736c0f5afc2c140215fefd`.

Reproduction commands:

```sh
cargo test --locked -p plaid-core --test generic_trace_cross_kind_exclusivity -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

## Composition with prior research

This composes rather than duplicates:

- `word-store-event-uniqueness`: one successful-SW event ID must not describe incompatible store tuples;
- `indirect-event-uniqueness`: one indirect-transfer event ID must not describe incompatible transfer tuples;
- `entry-verification-event-uniqueness`: one byte-verification event ID must not describe incompatible verification tuples;
- `copy-event-kind-exclusivity`: a `LoadMapping.copy_event` / DMA event ID must not masquerade as another primitive event kind.

Those lanes establish per-domain or DMA-copy identity. This result closes the remaining tested non-DMA cross-domain composition hole among store, indirect transfer, and entry verification.

## Closed-world impact

The current finite solver does not directly derive WholeRom closure from these raw observations, so this is not a new native-complete claim. The impact is on the evidence substrate that future closure must compose: without event-role exclusivity, independently plausible ProgramMaps can merge into an impossible causal history in which one concrete operation supplies multiple incompatible proof roles. That can contaminate executable mutation histories, indirect execution coverage, verification epochs, and any future whole-ROM certificate that counts or joins those facts.

## Remaining gaps

- Generic `Evidence { kind, producer, revision, detail }` still does not authenticate which immutable trace variant originally produced an ID. A Trace ID used in only one primitive role could still be forged from some unrelated event unless the original trace is re-imported or evidence becomes typed/source-bound.
- This branch does not absorb the neighboring within-kind uniqueness candidates or DMA/copy-event exclusivity candidate; it was based on canonical main.
- It does not prove trace completeness, event ordering, mutation completeness, indirect exhaustiveness, cache/TLB/lifetime composition, exception roots, RSP closure, or WholeRom closure.
- Explicit source-unit authenticity remains a separate obligation. The skip here only prevents a known reusable context ID from being misclassified by this particular role-collision check.

## Integration recommendation

Adopt the 43-line validator guard from `417133155b0b5d6ac2736c0f5afc2c140215fefd` plus the focused regression, then reconcile it with the neighboring `program.rs` uniqueness guards so event-role extraction is shared rather than duplicated. Preserve the narrow semantics: reject known cross-domain identity conflicts, do not infer event kind from equal values, do not impose global Trace uniqueness, and do not treat this structural check as trace authenticity.
