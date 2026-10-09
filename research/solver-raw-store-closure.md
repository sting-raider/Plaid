# Solver raw-store closure deletion attack

Status: VALIDATED

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

## Result

Current main can manufacture `Scope::DeclaredStaticImages == CLOSED` after a
hand-edited/partial ProgramMap deletes a derived `ExecutableWrite` while retaining
the primitive successful `ObservedWordStore` that proves an executable-backing
mutation. The bug is executable and reproduced in GitHub Actions.

The smallest candidate fix in this branch makes `solver::solve` independently
re-derive the same physical-overlap relation already used by `merge::import_trace`.
If a retained successful cached-RDRAM SW overlaps a region with explicit
`physical_start` and no executable-write fact with that event's evidence remains,
the solver emits `unresolved_executable_write` and stays OPEN.

## Composition

This result composes three existing invariants rather than inventing a new source
model:

- ADR-0009: deleting blocker/control facts from a hand-edited/partial ProgramMap
  must not manufacture closure.
- ADR-0017: executable alias claims require explicit physical backing rather than
  virtual-bit or payload guesses.
- ADR-0020: a successful cached-RDRAM SW is retained as primitive evidence, and
  overlap with explicitly mapped executable backing derives an unknown executable
  write. The limited SW sensor is not complete write coverage.

`merge::import_trace` records every `CpuWordStoreObserved`, computes
`destination & 0x1fffffff`, and emits an `ExecutableWrite` when that four-byte
physical span overlaps a region with an explicit `physical_start`. Before this
patch, `ProgramMap::validate` accepted the retained primitive observation while
`solver::solve` trusted the deletable derived set.

## Adversarial witness

The regression uses an executable image at KSEG1 `0xa0000000` with explicit
physical backing `0x00000000` and a retained successful cached KSEG0 SW to
`0x80000000`. The aliases differ virtually but overlap exactly in physical
backing. The written value is deliberately equal to the first executable word
(`0x08000000`) so same-value mutation cannot be laundered into “no operation”.
The derived `ExecutableWrite` is deliberately absent while the raw fact and its
provenance remain valid.

On unmodified current-main solver code, Actions run `37933970403`, job
`113831280116`, failed exactly at the closure assertion:

```text
left: Closed
right: Open
```

The run compiled against the pinned Rabbitizer revision
`724a49a5b4dbfb99f1a9e6992e63964fd29c90c8` from `refs.lock.toml`.

## Falsification / negative controls

`crates/plaid-core/tests/solver_raw_store.rs` contains four cases:

1. retained overlapping raw store + deleted derived write => OPEN;
2. explicit physical backing that does not overlap the store => CLOSED;
3. missing `physical_start` => CLOSED, with no guessed KSEG alias provenance;
4. retained canonical derived write => one existing executable-write blocker, not
   a duplicate from the solver recheck.

The positive witness is same-value, so content equality does not erase storage
mutation provenance.

Focused Actions run `37934292441` passed all four cases. Final validation run
`37934338638`, job `113832515377`, passed both:

```sh
cargo test -p plaid-core --test solver_raw_store -- --nocapture
cargo test -p plaid-core
```

The full `plaid-core` run passed 107 tests with zero failures, including the
existing merge/store regression and solver deletion-attack tests.

## Closed-world impact

This closes one concrete monotonicity hole in the finite static-scope solver:
retained primitive evidence of an executable-backing mutation can no longer be
neutralized by deleting only the importer-derived write fact. It does **not**
advance whole-ROM mutation completeness, prove absence of unobserved writes, or
upgrade unknown physical mappings into aliases.

## Integration recommendation

Adopt the 24-line `solver.rs` re-derivation and the four regression tests. The
branch-only workflow is research scaffolding and need not be merged. Preserve the
fail-closed boundary: only explicit physical overlap is re-derived; value equality,
virtual alias shape, and absent mappings remain insufficient provenance.
