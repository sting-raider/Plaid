# Entry-install event identity must be source-bound

Status: PARTIAL

Worker: `gpt56sol-entry-install-event-uniqueness-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/entry-install-event-uniqueness-gpt56sol`

Issue #4 claim comment: `6100550732`

## Question

Can one concrete discovery-trace `EntryInstalled` event identity be reused after import, hand editing, or `ProgramMap` merge as provenance for multiple incompatible executable entry/root identities, even though the validated source trace assigns that event to one installation?

## Result

Yes on current `main`.

`merge::import_trace` gives each trace event a session-qualified evidence identity of the form `trace:<sha256(ndjson)>:<seq>`. A real `EntryInstalled { unit, pc, register_mask }` event is attached to one imported `ProgramMap.entries[CodeAddress]` fact. However, `ProgramMap::validate()` checks only that an entry address is valid and that its evidence references exist. It does not know which generic `EvidenceKind::Trace` references represent installation events.

The baseline regression therefore demonstrated both of these current-main failures:

1. the exact same `EntryInstalled` event ID can be added to a second entry with a different PC, image identity, or generation while `ProgramMap::validate()` still accepts the map;
2. two individually valid map fragments can be merged so that one installation event ID authenticates two roots, and `merge_maps()` accepts the result.

GitHub Actions run `38074294667` on commit `2623642398c642eeb23832e82850991ac5ca92f3` reproduced the bug: three controls passed and the two adversarial regressions failed exactly because the forged maps were accepted.

## Important falsification: blanket Trace-ID uniqueness is wrong

A tempting fix is to require every `EvidenceKind::Trace` reference appearing on entries to occur on only one root. The experiment falsified that rule.

A valid synthetic trace compiled one unit containing two independently installed entries. The importer intentionally propagated the same `CompileBegin` trace evidence into both entries as compilation provenance. That control passed on current behavior and is required by Plaid's monotone provenance-union model. Therefore generic Trace evidence is not semantically equivalent to an installation-event witness.

The evidence `detail` string happens to contain a debug rendering of the source event, but parsing or trusting that mutable human-readable field would merely move the forgery surface. The session-qualified evidence ID commits to the complete trace bytes, but a standalone `ProgramMap` does not retain enough typed source-event information to prove the event role from the ID alone.

This means the bug cannot be repaired soundly by a local blanket uniqueness rule in `ProgramMap::validate()` with the current evidence schema.

## Candidate mitigation

The branch adds `crates/plaid-core/src/entry_install.rs` with:

- `verify_entry_install_projection(...)`
- `verify_entry_install_projection_with_rom(...)`

The verifier takes the exact complete `DiscoveryTrace`, re-runs the existing importer, computes the trace-session hash from canonical NDJSON, then examines only source events whose typed variant is `TraceEvent::EntryInstalled`.

For every such event it requires:

1. the candidate map contains the exact evidence object produced by re-import for that session-qualified event ID;
2. the re-imported source projection binds that event ID to exactly one `CodeAddress`;
3. the candidate map binds that event ID to exactly the same entry set.

The verifier deliberately does not impose uniqueness on other Trace events. Static and merged provenance may coexist on the legitimate entry.

## Adversarial cases

`crates/plaid-core/tests/entry_install_event_uniqueness.rs` covers:

- same installation event reused at a different PC;
- same installation event reused at the same PC with a different image identity;
- same installation event reused at the same PC/image with a different generation;
- independently valid fragments merged to launder one installation event into two roots;
- tampered evidence metadata for a real installation event;
- two distinct `EntryInstalled` events installing two distinct roots as a positive control;
- legitimate sharing of one `CompileBegin` Trace reference across two roots as the falsification control;
- an equivalent entry accumulating independent Static provenance as a positive control.

The adversarial tests explicitly confirm that generic `ProgramMap::validate()` still accepts the forged maps before the source-bound verifier rejects them. This is intentional: without the source trace, the current generic evidence schema cannot distinguish installation-event Trace references from shareable compilation Trace references soundly.

## Validation

Baseline/red reproduction:

```text
run 38074294667
commit 2623642398c642eeb23832e82850991ac5ca92f3
cargo test --locked -p plaid-core --test entry_install_event_uniqueness -- --nocapture
result: FAILED as expected, 3 passed / 2 failed
```

Candidate verification after formatting and clippy cleanup:

```text
run 38074757591
commit a486ac89bb23ad3a80ccf7aacea871c4de670a46
cargo test --locked -p plaid-core --test entry_install_event_uniqueness -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
result: all steps PASS; focused suite 6/6 PASS
```

The build used the repository lockfile. Cargo fetched Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`, matching `refs.lock.toml`. No emulator behavior was needed for this structural provenance experiment.

## Prior research composed or challenged

This composes:

- ADR-0009 deletion/fabrication resistance: a concrete discovery event must not be reusable to fabricate an additional root;
- ADR-0023 monotone provenance union: provenance may be shared or accumulated where its semantics permit it;
- the discovery-trace `EntryInstalled` single-event semantics;
- completed DMA/store/indirect/entry-verification event-identity research, which established the neighboring pattern that one concrete operation identity must not authenticate incompatible operation facts.

It also challenges an over-generalization of those earlier uniqueness rules: `EvidenceKind::Trace` itself is too coarse to enforce event uniqueness globally because valid compilation provenance is intentionally shared across derived entry facts.

The active `research/discovery-trace-source-recheck-gpt56sol` lane is the natural integration destination. This branch extends the same source-recheck idea to executable root installation rather than duplicating its selected DMA/store/indirect/entry-verification projections.

## Closed-world impact

An executable-root certificate that trusts `ProgramMap.entries` plus generic Trace references without rechecking the source trace can currently accept a fabricated extra root that borrows a real installation event identity. That weakens causal root provenance and any later lifetime/control-flow proof that treats the fabricated entry as genuinely installed.

The candidate verifier closes this specific fabrication path when the complete source trace is retained and supplied for verification.

This does **not** make the whole-ROM result CLOSED. In particular:

- `ProgramMap::validate()` and `merge_maps()` remain intentionally unable to authenticate Trace event roles without the source trace;
- the solver/certificate path does not yet require this entry-install source recheck;
- this verifier binds the concrete installation event to the imported `CodeAddress`, but does not by itself prove completeness of all execution roots, all entry masks, lifetimes, exceptions, overlays, mappings, or cache-visible state;
- `register_mask` and unit chronology remain represented in the source trace/import process but are not separately elevated into a reusable typed root-install certificate here.

## Integration recommendation

Do not integrate a blanket "Trace evidence may appear on only one entry" invariant.

Instead, fold `EntryInstalled` into the broader complete discovery-trace source-recheck/certificate pipeline so closure consumes a typed, source-bound installation projection. A longer-term schema improvement would preserve event kind and operation identity as machine-readable typed provenance rather than forcing downstream validators to recover semantic roles from generic Trace evidence.

The implementation on this branch is intentionally small and isolated so the primary integrator can either cherry-pick the verifier/tests directly or fold the projection logic into the broader source-recheck implementation.
