# Entry-verification event uniqueness

Result: **VALIDATED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/entry-verification-event-uniqueness-gpt56sol`

Coordination claim: issue #4 comment `6097269206`

## Question

Can one concrete `EntryBytesVerified` trace-event identity be reused after import or merge as provenance for multiple semantically incompatible `ObservedEntryVerification` operations?

This is distinct from whether `register_mask`, verification epoch, or `source_unit` are themselves sufficient closure evidence. The question here is earlier and structural: after the importer assigns one identity to one concrete verification event, can a hand-edited or composed ProgramMap make that event appear to have happened twice with different semantics?

## Importer contract audited

`merge::import_trace` assigns every concrete discovery-trace record a session-qualified evidence ID of the form `trace:{session}:{seq}`. For `EntryBytesVerified`, the importer emits exactly one `ObservedEntryVerification` whose `evidence` contains that current event ID.

The `source_unit` field has a different role: it stores the session-qualified Trace evidence ID of the unit's `CompileBegin`. Therefore the concrete verification-event identity and the compilation-unit provenance identity are separate even though both are `EvidenceKind::Trace`.

On the canonical base, `ProgramMap::validate()` validated each `ObservedEntryVerification` independently: the entry had to exist, its evidence references had to resolve, and `source_unit` had to name Trace evidence. It did not require one verification event identity to have one semantic meaning across the whole map.

## Executable adversaries

The branch adds `crates/plaid-core/tests/entry_verification_event_uniqueness.rs`.

One synthetic `EntryBytesVerified` event identity (`verify7`) is retained while exactly one semantic axis changes:

- executable entry identity;
- register mask;
- source-unit identity;
- verification generation/epoch.

A fifth adversary creates two independently valid ProgramMaps, gives each a different verification tuple backed by the same concrete verification event identity, and then merges them. This attacks composition rather than only direct hand editing.

Controls demonstrate the intended boundary:

- distinct verification-event IDs may describe distinct operations;
- one source unit may legitimately produce multiple distinct verification events;
- the explicitly typed `source_unit` Trace reference may be shared as unit provenance across those events;
- equivalent verification semantics may union additional non-Trace provenance.

The test does not infer operation identity from equal values, equal addresses, or generation arithmetic.

## Canonical-main reproduction

Baseline commit containing only the adversarial regression/workflow: `fc3597754da86c5918e8805bc733a4aedb713fb0`.

GitHub Actions run `38050490341`, job `114208450942`, executed against unmodified canonical production code:

- three controls passed;
- `one_verification_event_cannot_describe_two_different_operations` failed because current `ProgramMap::validate()` accepted the first conflicting reuse (changed entry);
- `independently_valid_fragments_cannot_merge_one_event_into_two_verifications` failed because `merge_maps()` accepted the composed contradiction.

The hosted run compiled the exact pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`. Decoder behavior is not material to this core validator result, but the pin remained intact.

## Smallest candidate fix

`research/entry-verification-event-uniqueness.patch` adds a map-wide validator guard. For each `ObservedEntryVerification`, every referenced Trace evidence ID other than the separately typed `source_unit` ID is bound to:

`(entry, register_mask, source_unit, verification generation)`

A later incompatible use of the same Trace identity is rejected with `entry verification trace event has conflicting semantics`.

The `source_unit` exemption is deliberate. `CompileBegin` is not an `EntryBytesVerified` operation, and one completed compilation unit can legitimately support multiple verification events. Treating all Trace provenance as globally unique would reject valid histories and confuse unit identity with operation identity.

Patch SHA-256: `da824fe7b7c2a00997a441421f8c709162d6e4e4f32e3f393cf7129812a4f991`.

## Validation

Candidate run `38050653464`, job `114208927210`, established the semantics before formatting cleanup:

- patch application: PASS;
- focused matrix: 6/6 PASS;
- full `cargo test --locked -p plaid-core`: PASS;
- formatting only: FAIL, with mechanical rustfmt diffs.

Those exact rustfmt diffs were applied without changing the invariant.

Final semantic/tooling run `38050758684`, job `114209235202`, head `b2a96a07363dc1d507cb00bd2c6ed4fa3572451c`:

- candidate patch applies cleanly: PASS;
- `cargo test --locked -p plaid-core --test entry_verification_event_uniqueness -- --nocapture`: 6/6 PASS;
- `cargo test --locked -p plaid-core`: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: PASS.

The earlier run `38050615432` failed before compilation because the research patch file had an incorrect unified-diff hunk count. That was a harness/artifact formatting error, not a semantic result; the corrected patch then applied and passed the matrix above.

## What prior research this composes

- **ADR-0009**: deletion/fabrication resistance. A retained concrete operation identity must not fork into contradictory operations after projection or merge.
- **ADR-0022**: dirty-entry byte verification. The verification record is a meaningful event/lifetime fact, so its concrete event identity must survive composition consistently.
- **ADR-0023**: canonical provenance union. Equivalent facts can accumulate provenance; provenance union must not make one concrete event acquire multiple semantic meanings.
- **Entry-verification source-unit binding**: that completed research showed `source_unit` itself is not independently source-recheckable after provenance union. This result does not pretend to repair that gap; it only prevents a concrete verification-event identity from forking.
- **DMA / word-store event uniqueness**: neighboring precedent that an imported concrete operation identity must have one semantic meaning. The event type and semantic tuple here are independently tested rather than assumed identical to those lanes.

## Closed-world impact

This is an evidence-integrity fix, not a claim that WholeRom or current declared scopes become CLOSED.

Without the invariant, one actually observed entry-byte verification event can be copied onto multiple entries, masks, units, or verification epochs. Future closure logic could then consume a fabricated event graph when reasoning about dirty-entry safety, executable lifetimes, indirect-target verification, writer chronology, or overlay/cache/mapping composition. A map that passes structural validation should not be able to make one concrete verification operation happen in two incompatible places in history.

The cross-map adversary matters because independently valid fragments are expected to compose. Local validity alone is insufficient if merge can create a contradictory causal history.

## Remaining gap

The candidate proves only **uniqueness of meaning for Trace IDs attached to `ObservedEntryVerification`**. Generic `Evidence` metadata still does not authenticate that a non-`source_unit` Trace ID originally came from an `EntryBytesVerified` source record rather than another trace-event kind. Full authenticity requires typed trace-event evidence or independent source-bound re-import/recheck against the immutable trace.

Likewise, this does not repair the completed source-unit-binding gap: a `source_unit` string that names Trace evidence is not by itself a recheckable proof that the original verification named that exact compilation unit.

This work does not solve executable-mutation completeness, transforms/relocations, overlay lifetimes, cache/TLB composition, exception roots, RSP executable identity, or WholeRom closure.

## Integration recommendation

**ADOPT selectively.** Apply the small validator guard from `research/entry-verification-event-uniqueness.patch` together with the focused regression. Do not merge the research branch wholesale.

Longer term, prefer a typed verification-event/source-recheck primitive over relying on generic `EvidenceKind::Trace` metadata. The small guard is still useful now because it prevents contradictory reuse of identities produced by the current importer without inventing any value-based provenance rule.

## Reproduction

```sh
git apply research/entry-verification-event-uniqueness.patch
cargo test --locked -p plaid-core --test entry_verification_event_uniqueness -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

No changes were made to canonical `main` by this worker.
