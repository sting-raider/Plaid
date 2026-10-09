# Raw indirect execution must survive solver rechecking

Status: VALIDATED candidate fix on `research/solver-raw-indirect-closure-gpt56sol`.

Baseline: canonical `main` at `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`.

## Question

Can `Scope::DeclaredStaticImages` report CLOSED after an importer-derived
`uncorrelated_indirect_observation` diagnostic is deleted while the primitive
`ObservedIndirect` execution event remains in the `ProgramMap`?

This matters because `merge::import_trace` deliberately retains raw indirect
execution observations separately from their image-resolved `IndirectSite`
observations. ADR-0009 requires the solver to resist closure manufactured by
removing derived blocker facts. ADR-0012 and ADR-0021 preserve source/target
identity and executing-unit context specifically so equal PCs are not treated as
causal provenance.

## Result

Yes on baseline main. The solver re-derived instruction CFG facts but never read
`ProgramMap::indirect_observations`. Therefore a valid otherwise-closed static map
could retain concrete raw indirect execution evidence outside its declared
executable universe and still report CLOSED once the importer-derived unresolved
row was removed.

The baseline focused Actions run `37969137609`, job `113950972092`, compiled the
current-main-derived branch against pinned Rabbitizer
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. Three cases ran before any solver
change:

- uncorrelated raw transfer `0x90000000 -> 0x90000010`, generation 7: solver
  returned `Closed` where the regression required `Open`;
- equal source/target guest PCs matching a declared constant-JR edge, but without
  the raw event evidence attached to that derived edge: solver again returned
  `Closed`;
- positive control with the exact raw event evidence attached to the unique
  `IndirectSite.observed[target]`: remained CLOSED.

The first two assertions failed exactly as `left: Closed, right: Open`. This is a
closure monotonicity bug, not a claim about MIPS execution semantics.

## Importer-origin reproduction

The final regression also constructs a real `DiscoveryTrace` accepted by
`import_trace`:

1. compile a known constant-JR image;
2. record an actual `IndirectTargetObserved` from that unit to an address with no
   target image;
3. verify the importer retains the raw `ObservedIndirect` and emits
   `uncorrelated_indirect_observation`;
4. run the existing constant-target analyzer so the declared source site has a
   valid finite static target certificate;
5. delete only `uncorrelated_indirect_observation`;
6. solve the resulting valid map under `DeclaredStaticImages`.

Baseline solver logic has no independent raw-indirect gate, so step 5 can erase
the only blocker for the executed out-of-universe transfer. The candidate solver
recheck rejects the laundered map from the retained primitive event.

## Candidate invariant

For every raw indirect event provenance ID retained in an `ObservedIndirect`, the
solver requires exactly one declared source/target observation carrying that same
raw provenance ID.

Source matching is intentionally stricter than guest-address equality:

- with no explicit `source_unit`, the source `IndirectSite` must match the raw
  source PC and the observation generation;
- with `source_unit`, the site must carry that exact trace unit provenance. This
  permits ADR-0021's stale-but-still-executing compiled unit without pretending
  the current epoch identifies it;
- the derived target must match the raw target PC and its `observed` evidence must
  contain the exact raw event provenance ID;
- target generation is not guessed from the raw epoch. Existing entry-verification
  evidence may legitimately identify an older installed target;
- zero matches and multiple matches both remain OPEN.

The candidate blocker is `unresolved_raw_indirect_execution`. If there is exactly
one plausible declared source it is reported as the blocker site; otherwise site
identity remains unknown rather than being invented.

## Adversarial controls

`crates/plaid-core/tests/solver_raw_indirect.rs` covers:

- raw source/target entirely outside the declared map;
- exact resolved-event provenance positive control;
- equal guest source/target addresses without shared raw-event provenance;
- same PCs with a mismatched implicit source generation;
- an explicit executing-unit provenance that correctly identifies an older source
  generation;
- a source-unit ID that exists as trace evidence but is not bound to the declared
  source site;
- the importer-origin diagnostic-deletion laundering path described above.

No test treats payload equality, PC equality or generation-number coincidence as
provenance.

## Scope and limitations

This closes one production solver monotonicity hole for retained raw indirect
execution evidence. It does not prove indirect-target completeness for arbitrary
whole-ROM execution, pointer/jump-table immutability, target executable lifetime,
cache residency, TLB mapping, exception roots, or absence of unobserved transfers.

The raw sensor itself remains finite observational evidence. Whole-ROM remains
OPEN under its independent obligations. The fix also does not make a dynamic
sample a closure certificate: the existing indirect proof verifier is still
required for a declared finite target set.

## Reproduction

```sh
git checkout research/solver-raw-indirect-closure-gpt56sol
cargo test -p plaid-core --test solver_raw_indirect -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

Baseline failure is preserved by checking out commit
`6f5865b986c99287147f2c5df49e2f7bbeeec6f7` and running the focused test. The
candidate solver change is commit `195c0a800aece3305319839e37663fdc52a09992`.

## Integration recommendation

Adopt the solver-side independent raw-event recheck and the regression matrix.
Keep the branch-only Actions workflow as research scaffolding. The important
boundary is provenance identity: never discharge a raw executed transfer merely
because some declared edge has equal guest PCs.
