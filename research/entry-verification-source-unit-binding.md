# Entry-verification source-unit binding

Result: **VALIDATED provenance gap; narrow candidate REJECTED**

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/entry-verification-source-unit-binding-gpt56sol`

Coordination claim: issue #4 comment `6090922670`

## Question

After `DiscoveryTrace::validate()` proves that an `EntryBytesVerified` event belongs to one exact completed compilation unit, does the exported `ProgramMap` retain enough typed structure to independently re-establish that exact `ObservedEntryVerification.source_unit` relationship after import/merge?

This is deliberately separate from the concurrent solver lanes that consume the verification's `register_mask` or verification epoch. Those fields can conservatively create blockers without using source-unit identity. This investigation asks whether `source_unit` itself is trustworthy enough for any future positive provenance/lifecycle discharge.

## Relevant existing contracts

- ADR-0021 treats the executing compilation unit as a distinct identity rather than a PC/value guess.
- ADR-0022 says dirty-entry verification is tied to a completed unit and keeps verification epoch separate from compilation generation.
- ADR-0023 unions repeated semantic facts while preserving provenance.
- `DiscoveryTrace::validate()` checks `EntryBytesVerified.unit` against the exact completed unit words and the exact installed `(pc, register_mask)` pair.
- `merge::import()` converts that trace-local unit into `ObservedEntryVerification.source_unit` by storing the unit's session-qualified `CompileBegin` evidence ID.
- `ProgramMap::validate()` later checks only that the referenced ID exists and has `EvidenceKind::Trace`, plus that the `entry` exists.

The last check does not reconstruct the original unit relationship.

## Executable adversaries

The branch adds `crates/plaid-core/tests/entry_verification_source_unit.rs`.

### A. Unrelated compilation unit substitution

1. Build a valid trace with unit 0 at `0x80000000`, an installed entry there, and a later successful `EntryBytesVerified { unit: 0, ... }`.
2. In the same valid trace, compile unrelated unit 1 at `0x80000020`.
3. Import normally.
4. Replace only `ObservedEntryVerification.source_unit` with unit 1's genuine session-qualified `CompileBegin` evidence ID.

Current `ProgramMap::validate()` accepts the forged map. The intended regression at commit `26957335da71b1b00dac22c875722b69d5665f84` fails exactly on `assert!(forged.validate().is_err())`.

GitHub Actions run `38004198131`, job `114069101922`:

- `equal_byte_same_identity_recompile_defeats_region_provenance_join`: PASS
- `unrelated_compile_unit_must_not_validate_as_verified_entry_source`: FAIL
- failure: `assertion failed: forged.validate().is_err()`

The run used the repository's exact pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`; no decoder behavior is material to the result.

### B. Equal-byte, equal-address, equal-generation decoy

The stronger trace compiles unit 1 with the same words, same guest start, same physical start and same invalidation generation as unit 0, with the same installed entry/mask.

After import, both compilations collapse to the same executable `Region` identity. `merge_maps()` canonicalizes identical `Region` facts by clearing their evidence from the semantic key and unioning the evidence sets. Consequently the one matching Region carries both unit 0 and unit 1 CompileBegin provenance IDs.

Swapping the verification from unit 0 to unit 1 still passes current validation.

This is intentionally an equal-payload decoy: same bytes/address/generation do not make the two compilation-unit provenances identical.

## Smallest candidate fix and falsification

The branch implements a branch-local candidate validator in the regression file:

> Require `source_unit` to be Trace evidence and to occur in the provenance of a Region with the verification entry's `(image,generation)` that contains the verified PC.

This candidate rejects adversary A and accepts genuine imports.

It **also accepts adversary B**, because provenance union has already erased the per-compilation grouping. Therefore a Region-membership check is not a sound production fix and must not be promoted merely because it makes the easy regression green.

Parsing `Evidence.detail` for `CompileBegin { unit: ... }` / `EntryBytesVerified { unit: ... }` would appear to recover the relationship in today's importer output, but `detail` is explicitly free-form producer text rather than a typed/recheckable wire contract. The ProgramMap also does not retain a canonical discovery-trace source object whose session hash can be independently recomputed. Treating debug text as causal proof would just move the unsound assumption.

## What information is missing

After import/merge the typed ProgramMap has no compilation-unit fact that preserves, as one recheckable object:

- the exact session-qualified unit identity;
- CompileBegin range/physical context;
- completed word identity;
- installed `(pc, register_mask)` set;
- its image/generation association;
- the exact EntryBytesVerified event that names that same unit.

Regions and blocks are executable identities, not compilation-unit identities, and their provenance is intentionally unioned. Therefore they cannot reconstruct a distinction that merge has discarded.

A future positive use of `ObservedEntryVerification.source_unit` needs either:

1. a typed session-qualified compilation-unit witness retained in ProgramMap and linked by the verification, with its completed words/installed entries rechecked; preferably also a source-bound trace-capture identity, or
2. a full discovery-trace source rechecker analogous to the source-bound fetch work, so the `(verification event -> unit -> completed words -> installed entry/mask)` chain can be independently replayed from canonical source bytes.

Until then `source_unit` may be useful as imported historical annotation, but should not by itself discharge a closed-world provenance/lifetime obligation.

## Closed-world impact

This does **not** make current whole-ROM reports falsely CLOSED: whole-ROM is independently OPEN, and current main's solver does not positively consume entry-verification source-unit identity.

It matters at the exact frontier Plaid is approaching: composing independently validated evidence. The trace reader has a strong exact-unit fact, but that fact becomes weaker after projection into ProgramMap. A future solver that treats the surviving `source_unit` string as equivalent to the original trace validation would silently cross a provenance gap.

The active mask/epoch solver lanes remain compatible with this finding when used monotonically: a retained nonzero mask or post-invalidation epoch can conservatively create a blocker without trusting the claimed unit identity. Positive target/lifetime discharge must wait for stronger unit/source binding.

## Reproduction

Focused matrix:

```sh
cargo test -p plaid-core --test entry_verification_source_unit -- --nocapture
```

Full core regression:

```sh
cargo test -p plaid-core
```

Baseline before converting the first test into the intended failing regression:

- commit `e7a6e41aeb889f20df5a4550899b81e80310dd5b`
- Actions run `38004068653`: SUCCESS; focused 2/2 plus full `plaid-core` green.

Intended failing regression:

- commit `26957335da71b1b00dac22c875722b69d5665f84`
- Actions run `38004198131`: expected FAILURE in the unrelated-unit assertion.

Candidate-falsification matrix:

- commit `39d28acebbf7cee5f2802adf63834aa676c5aa51`
- genuine import: candidate accepts
- unrelated-unit swap: current validation accepts, candidate rejects
- equal-byte/same-identity swap: current validation accepts, candidate also accepts (candidate falsified)

## Integration recommendation

Do **not** integrate the Region-membership candidate into `ProgramMap::validate()` as a claimed fix. It is a useful cheap consistency check at most, not an exact-unit proof.

Retain the adversarial regression/model and design a typed compilation-unit/source-recheck primitive before any closure logic relies positively on `ObservedEntryVerification.source_unit`. Preserve compilation-unit identity separately from content identity, generation, executable Region identity and merged provenance sets.
