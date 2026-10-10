# Region-to-overlay descriptor binding

Result: **VALIDATED** (candidate fix under branch verification)

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/overlay-region-binding-gpt56sol`

## Question

Can a serialized `ProgramMap` attach a `Region.overlay` reference to an unrelated `Overlay` descriptor that merely shares the same image label, while disagreeing on the canonical ROM source or guest load span?

This is a structural provenance question, not an overlay-lifetime proof. A future lifetime verifier must be able to trust that a Region which names an overlay is referring to the descriptor produced for that exact loaded byte span.

## Producer audit

`loads::record_load` is the only current producer found which sets `Region.overlay = Some(...)`. When overlapping distinct canonical executable sources create overlay candidates, it constructs the descriptor from the exact load tuple:

- `image = load.image`
- `rom_offset = load.rom_offset`
- `load_address = load.destination.start`
- `size = load.destination.size`

It then attaches that exact descriptor identity to a Region carrying the same image, ROM offset and guest range.

The canonical-base validator was weaker. It accepted a Region overlay reference whenever the named overlay existed and `overlay.image == region.image`; it did not bind ROM offset, load address or extent.

## Baseline falsification

Branch red head: `aba556e582bd00434589c918cf3a004bd4ad1a17`

GitHub Actions: run `38060060167`, job `114236318078`.

Focused command:

```text
cargo test --locked -p plaid-core --test overlay_region_binding
```

The run compiled the pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` and produced the intended red result: 2 passed, 3 failed.

Controls which passed on unmodified canonical-base code:

- exact descriptor binding remains valid across two Region generations;
- an already-existing different-image mismatch is rejected.

Forgeries which were incorrectly accepted:

- same image but Region ROM offset `0x80` referencing an Overlay sourced at `0x40`;
- same image/source but Region guest start `0x80002000` referencing an Overlay loaded at `0x80001000`;
- same image/source/start but Region size `0x10` referencing an Overlay extent `0x20`.

The adversarial matrix was then extended with an overlay-bound Region lacking any ROM source. The merge path was also audited: `merge_maps` already rejects two different descriptors that reuse the same overlay ID, so the reproduced bug is the local Region-to-descriptor binding, not a general overlay-map collision bug.

## Candidate invariant

Candidate production commit: `7277e4b5d472ea754797390367eb9920aedefd74`.

For every `Region.overlay = Some(id)`, validation now requires the referenced descriptor to agree on all producer-defined descriptor fields represented by the Region:

- image identity;
- canonical ROM offset (`Region.rom_offset == Some(Overlay.rom_offset)`);
- guest load start;
- guest extent.

Generation is intentionally **not** part of this binding. `Overlay` has no generation field, and distinct executable generations may legitimately reuse the same exact source/mapping while retaining separate generation identity. Physical backing is also intentionally not inferred from the descriptor: physical overlap is evidence that creates a conservative overlay candidate, but the current `Overlay` type does not encode physical identity.

No byte/value equality is used to repair or infer provenance.

## Closed-world impact

Today `solver::solve` already keeps any retained overlay OPEN because overlay lifecycle verification is not implemented. Therefore this bug does not by itself manufacture a current `DeclaredStaticImages == CLOSED` result.

It is still proof-system relevant: without this invariant, a later overlay-lifetime verifier could consume a Region-to-overlay relationship that the actual producer could never have emitted, confusing source span/lifetime identity even while all local objects validate. The fix makes the serialized relationship faithful to the current producer contract before stronger lifetime certificates are added.

## Limits

This work does **not** prove:

- overlay load/unload/reload chronology or retirement;
- complete executable-copy or mutation sensing;
- physical alias identity;
- cache-visible executable lifetime;
- TLB/context lifetime;
- relocation/decompression provenance;
- whole-ROM overlay closure.

Those obligations remain OPEN and must not be discharged from this structural check.

## Reproduction

Red baseline:

```text
git checkout aba556e582bd00434589c918cf3a004bd4ad1a17
cargo test --locked -p plaid-core --test overlay_region_binding
```

Candidate branch:

```text
git checkout research/overlay-region-binding-gpt56sol
cargo test --locked -p plaid-core --test overlay_region_binding
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

Final branch-wide CI receipt is recorded in the issue #4 closeout once the candidate run completes.
