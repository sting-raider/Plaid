# Indirect-observation source-unit binding

Result: **VALIDATED provenance loss; structural candidate REJECTED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/indirect-source-unit-binding-gpt56sol`

Coordination claim: issue #4 comment `6097610766`

## Question

After `DiscoveryTrace::validate()` proves that an `IndirectTargetObserved.source_unit` names one exact completed compilation unit containing the executing JR/JALR site, does the exported `ProgramMap` retain enough typed structure to independently re-establish that exact relationship after import, serialization and merge?

This is distinct from indirect-event uniqueness. The observation event itself may have a unique identity and still carry a forged compilation-unit identity. It is also distinct from target correlation: ADR-0021 intentionally permits an older generated source unit to continue executing after invalidation advances the import epoch.

## Existing intended contract

`DiscoveryTrace::validate()` has the strong fact. When `source_unit` is present it:

1. requires that unit to exist;
2. requires its `UnitCompiled` words to already be present;
3. constructs the completed unit range; and
4. rejects an indirect site outside that exact unit.

`merge::import()` then stores the unit's session-qualified `CompileBegin` evidence ID in `ObservedIndirect.source_unit` and uses `unit_images[unit].address(site)` for the exact source identity during immediate correlation.

The older validated research in `research/mupen-executing-unit-identity.md` confirms why this is semantically important: the trace-local unit ID is embedded in generated JR/JALR callbacks specifically so an older unit can be identified without guessing from PC/current epoch.

After projection, however, `ProgramMap::validate()` checks only that an optional `source_unit` names an existing `EvidenceKind::Trace`. It does not retain or recheck the trace-local unit relation.

## Executable adversarial matrix

The branch adds `crates/plaid-core/tests/indirect_source_unit_binding.rs` and a branch-only workflow.

### A. Unrelated completed unit substitution

A valid trace compiles unit 0 at `0x80000000` (`JR $t0; NOP`), separately compiles unit 1 at `0x80000020`, then records an `IndirectTargetObserved` whose source unit is exactly unit 0. Trace validation and normal import succeed.

After import, the test changes only `ObservedIndirect.source_unit` from unit 0's real `CompileBegin` evidence ID to unit 1's real `CompileBegin` evidence ID. Current `ProgramMap::validate()` accepts the forged map.

For a desired fail-closed regression, commit `00128419bc30461c988ca1575489a9fd00ce8601` asserts `forged.validate().is_err()`. Actions run `38053152630`, job `114216197608`, fails exactly that assertion while the two stronger controls pass. The run compiles the exact pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`.

### B. Equal-byte, equal-address, equal-generation recompile

The stronger adversary compiles unit 1 with the same words, guest start, physical start and generation as unit 0 before the observation still names unit 0.

Import/merge canonicalizes the identical executable `Region` fact and unions provenance. The one matching Region therefore contains both unit 0 and unit 1 `CompileBegin` evidence IDs.

Changing the raw observation's source-unit ID from unit 0 to unit 1 still passes current validation. More importantly, it also passes the smallest plausible typed structural candidate described below. Equal bytes/address/generation do not turn two compilation operations into the same causal identity.

### C. A non-Compile trace event can masquerade as `source_unit`

The test replaces the exact unit-0 `CompileBegin` evidence ID with the real unit-0 `UnitCompiled` event evidence ID. Both are merely `EvidenceKind::Trace` after ProgramMap projection, and Region provenance contains both.

Current validation accepts this substitution, and the structural Region candidate also accepts it. Thus the projection loses even the primitive event-kind distinction required to say that the retained string denotes `CompileBegin` rather than another trace event.

## Candidate fix and falsification

The executable test implements the smallest plausible post-import check that does not parse human-readable evidence detail:

> If an indirect observation has `source_unit`, require that Trace evidence ID to occur in the provenance of some executable Region containing the observation's source PC.

This deliberately does **not** compare the Region generation to `ObservedIndirect.generation`, because ADR-0021 permits an older generated unit to continue executing after invalidation.

The candidate rejects adversary A. It fails adversaries B and C:

- provenance union puts both same-identity compilation IDs on the same Region;
- the Region also carries `UnitCompiled` evidence, so generic Trace kind plus Region membership cannot prove event kind.

Therefore the candidate is useful as a cheap consistency check at most, not an exact-unit certificate. Promoting it as the fix would simply convert an obvious forgery into a subtler accepted forgery.

Parsing `Evidence.detail` for `CompileBegin { unit: ... }` would not repair the proof boundary. `detail` is free-form producer text, not a typed source contract, and ProgramMap does not retain the canonical discovery-trace object needed to recompute/replay the session relationship independently.

## What information is missing

A future positive use of `ObservedIndirect.source_unit` needs a recheckable object that preserves at least:

- session-qualified compilation-unit identity;
- typed `CompileBegin` operation identity and start/physical/delay-slot context;
- completed word/range identity;
- image/generation association without collapsing distinct compilation operations;
- the exact `IndirectTargetObserved` event that names that unit;
- a source-bound trace/capture identity or equivalent immutable manifest so the relationship can be replayed rather than trusted from edited ProgramMap text.

One viable direction is a typed `CompilationUnitWitness` retained independently of Region/Block provenance union. Another is a strict full discovery-trace source rechecker analogous to Plaid's later complete-source fetch/history consumers. Either must preserve repeated same-value/same-address operations as distinct causal identities.

## Closed-world impact

Current canonical `main` does not become falsely CLOSED from this issue alone: whole-ROM mode is independently OPEN, and the current solver does not positively discharge closure using raw `ObservedIndirect.source_unit`.

The impact is on future composition. ADR-0021's exact executing-unit fact is strong at the trace-validation/import boundary, but the surviving ProgramMap string is weaker after projection. A future solver or executable-lifetime verifier that treats that string as independently proven exact-unit provenance would be unsound under the tested substitutions.

This composes with, but does not duplicate, the completed entry-verification source-unit result: two different consumers independently demonstrate that generic evidence refs plus merged Region provenance cannot preserve operation identity. It also complements indirect-event-uniqueness: event uniqueness does not repair a forged `source_unit` field inside one otherwise unique observation.

## Reproduction and receipts

Passing behavior/falsification matrix at commit `fe398ad6631cc3fd1ba11b948538169f43289c5b`:

```sh
cargo test -p plaid-core --test indirect_source_unit_binding -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

Actions run `38053051020`, job `114215907040`: all four workflow stages pass.

Desired fail-closed regression:

- commit `00128419bc30461c988ca1575489a9fd00ce8601`
- Actions run `38053152630`, job `114216197608`
- focused result: `2 passed; 1 failed`
- failing test: `unrelated_completed_unit_must_not_validate_as_exact_indirect_source`
- failure: `assertion failed: forged.validate().is_err()`

The final branch restores the passing adversarial/falsification matrix so branch CI remains green while the red commit stays in history as the regression receipt.

## Integration recommendation

**ADOPT the finding and adversarial regression artifacts; DO NOT adopt the Region-membership candidate as an exact fix.**

Before any closure/lifetime logic positively relies on `ObservedIndirect.source_unit`, retain typed compilation-unit evidence or a source-bound trace rechecker that can reconstruct `observation event -> exact completed unit -> containing source site` after merge. Keep compilation-operation identity separate from image identity, generation, bytes and unioned Region provenance.
