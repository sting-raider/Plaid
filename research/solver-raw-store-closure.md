# Solver raw-store closure deletion attack

Status: IN PROGRESS

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

## Hypothesis

`Scope::DeclaredStaticImages` must not report `CLOSED` when a retained successful
`ObservedWordStore` proves a write overlaps the explicit physical backing of a
declared executable region, even if a hand-edited/partial ProgramMap deletes the
`ExecutableWrite` fact originally derived by trace import.

This attacks ADR-0009's invariant that removing blocker facts from JSON cannot
manufacture closure. It composes ADR-0017's explicit physical-backing identity
with ADR-0020's successful cached-RDRAM SW observation.

## Current source finding

`merge::import_trace` records every `CpuWordStoreObserved`, computes
`destination & 0x1fffffff`, and emits an `ExecutableWrite` when that four-byte
physical span overlaps a region with an explicit `physical_start`.

`ProgramMap::validate` independently validates the raw store but does not require
the derived write to remain present. `solver::solve` blocks on
`executable_writes` but does not currently re-derive overlap from
`word_store_observations`.

The adversarial regression uses an executable image at KSEG1 `0xa0000000` with
explicit physical backing `0x00000000` and a retained successful cached KSEG0 SW
to `0x80000000`. The aliases differ virtually but overlap exactly in physical
backing. The derived `ExecutableWrite` is deliberately absent while the raw trace
fact and provenance remain valid.

## Reproduction

```sh
cargo test -p plaid-core --test solver_raw_store -- --nocapture
```

Expected proof-system behavior: the test demands `OPEN` with an
`unresolved_executable_write` blocker. A failure showing `CLOSED` reproduces the
omission bug on current main.

## Boundaries

This research does not claim the limited SW sensor is a complete mutation census.
It only requires the solver to be monotonic with respect to primitive evidence it
already retains: deleting a derived blocker must not make a known overlapping
successful write disappear. Stores with no explicit physical overlap must not be
upgraded into executable mutations by value or virtual-address guesses.
