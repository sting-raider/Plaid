# Conflicting executable region mappings can manufacture static closure

Status: VALIDATED on canonical base `211176e7a489fecf8331d02915ee982cd279cb62`.

Worker: `gpt56sol-solver-conflicting-region-mapping-20261010`

Coordination claim: issue #4 comment `6090217688`.

## Question

Can `Scope::DeclaredStaticImages` report `Closed` when one executable identity
(`image`, `generation`) assigns two incompatible explicit physical backings to the
same guest executable bytes?

This is deliberately distinct from the completed
`solver-physical-alias-closure` sibling. That work covers *different* executable
identities overlapping the same physical storage. This experiment holds the
executable identity and guest bytes fixed and makes the guest-to-physical mapping
itself non-functional.

## Baseline reproduction

The regression fixture creates a tiny immutable direct CFG at guest
`0x8000_0000` with image `mapping-conflict`, generation `7`, and identical
instruction bytes in every case. `ProgramMap::validate()` accepts the maps.

Two contradictory cases were tested:

1. The same guest range `0x8000_0000..0x8000_0008` maps to both physical
   `0x0000_0000` and physical `0x0000_1000`.
2. A partial overlap maps guest `0x8000_0004` to physical `0x0000_0004`
   through one region and physical `0x0000_2000` through another.

Two falsification controls were also tested:

- overlapping regions whose affine guest-to-physical relation agrees over the
  overlap remain admissible;
- an explicit mapping paired with an unknown mapping, and disjoint mapped guest
  ranges, are not fabricated into conflicts.

Red artifact:

- regression commit: `61a7e72c9a74a0eb665a104ce5b197904328c3af`
- workflow head: `b1e1efabf0feab28c2239f5b153a7cc43cbd2d17`
- Actions run: `37998809156`
- job: `114051544354`
- exact command: `cargo test -p plaid-core --test solver_conflicting_region_mapping -- --nocapture`
- exact pinned decoder observed in the log: Rabbitizer
  `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`
- result: 2 controls passed; both contradictory cases failed because the solver
  returned `Closed` where the regression required `Open` (`left: Closed`,
  `right: Open`).

Therefore equal instruction payload, equal `CodeAddress` identity, and successful
per-record validation are insufficient to establish one physical backing history.

## Root cause

`ProgramMap::validate()` validates `Region` records independently. The static
solver then checks block coverage existentially: a block is accepted if *some*
matching `(image, generation)` region contains it. Nothing on current main checks
that overlapping explicit regions for the same executable identity describe one
consistent guest-to-physical relation.

The completed cross-identity physical-alias candidate intentionally skips pairs
where `image` and `generation` are equal, so it does not cover this case.

## Candidate fix

For `DeclaredStaticImages`, pair regions that have the same `(image, generation)`
and explicit `physical_start`. If their guest ranges overlap, evaluate both affine
mappings at the first overlapping guest byte. Because each region mapping has
unit stride, equality there implies equality throughout the overlap. If the two
physical addresses disagree, emit
`ambiguous_executable_physical_mapping` and keep closure OPEN.

The check deliberately does not guess when either physical mapping is unknown,
and it accepts overlapping subregions that encode the same affine relation.

Candidate implementation commit: `0a86887ebfa8453d4312aa32e30561bad09cb524`.
Formatted branch head before this note: `9a3bf73b1cd30f3378b9cbd7e201f17143a4fc49`.

## Validation

Focused green run on the candidate fix:

- run `37999004297`, job `114052194976`
- 4/4 adversarial tests passed.

Acceptance run on formatted sources:

- run `37999137568`, job `114052637468`
- `cargo fmt --all -- --check`: PASS
- `cargo clippy -p plaid-core --all-targets -- -D warnings`: PASS
- focused conflicting-region regression: PASS
- `cargo test -p plaid-core`: PASS

The workflow is branch-only and does not modify `main`.

## Prior research composed or challenged

- ADR-0009: contradictory retained facts must not be ignorable in a way that
  manufactures CLOSED.
- ADR-0017: explicit physical mappings are candidate alias/backing evidence;
  missing or contradictory mappings cannot establish unique identity.
- `research/solver-physical-alias-closure-gpt56sol`: sibling invariant for
  distinct executable identities sharing physical backing. The two checks are
  complementary, not substitutes.

## Closed-world impact

This closes one concrete false-CLOSED path in the declared static scope. A single
`CodeAddress` identity can no longer stand for mutually incompatible explicit
physical backing at the same guest bytes merely because the current instruction
payload is equal and the CFG itself is finite.

The result is intentionally modest. It does **not** prove dynamic TLB mapping
lifetimes, cache residency, remap chronology, executable mutation completeness,
or whole-ROM closure. `WholeRom` remains OPEN for its existing obligations.

## Remaining gap and integration recommendation

Adopt the invariant, not necessarily this research branch wholesale. The primary
integrator should combine this same-identity guest-mapping consistency check with
the completed cross-identity physical-overlap check in one executable-region
consistency pass, preserving separate blocker kinds because they diagnose opposite
mapping failures:

- one identity -> incompatible physical backings;
- multiple identities -> overlapping physical backing without alias/lifetime proof.

Do not infer equivalence from equal bytes. Unknown physical mappings remain
UNKNOWN rather than guessed. Dynamic translation contexts and lifetimes require
separate evidence before multiple time-varying mappings can be reconciled.
