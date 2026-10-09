# ProgramMap merge conflict-index scalability

Status: **VALIDATED**

Research worker: `gpt56sol-programmap-merge-scalability-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Validated candidate head: `9f9235abb7636daab86b378f4de0cf8fd574c14f`

## Question

Does canonical `ProgramMap` union spend quadratic time detecting block/direct-edge contradictions, and can that phase be indexed without weakening the monotone-union rule or losing provenance?

## Existing behavior

After set union, `merge_maps` on the canonical base performs two all-pairs scans:

- every merged `BasicBlock` against every other block, looking for equal `CodeAddress start` with different `(size, delay_slot_entry)`;
- every merged `DirectEdge` against every other edge, looking for equal `(site, kind)` with different `(target, delay_slot)`.

Each contradictory pair inserts an `Unresolved` diagnostic. A later `canonicalize(&mut out.unresolved)` then merges diagnostics with the same semantic identity and unions their evidence references.

Therefore contradiction-free maps still pay Θ(B² + E²) comparisons even though blocks and edges are already ordered facts.

## Baseline measurement

`crates/plaid-core/tests/programmap_merge_scalability.rs` builds valid, disjoint synthetic maps and isolates block-only and edge-only cardinality. It times only `merge_maps` in a release build. Inputs deliberately use one valid static evidence record so ROM parsing, decoding, trace replay and large evidence maps do not dominate the measurement.

An independent untouched-main run (`Actions 38005476555`, job `114073152300`) showed the expected doubling curve:

| facts | blocks median ms | ratio | edges median ms | ratio |
|---:|---:|---:|---:|---:|
| 500 | 0.713 | — | 0.734 | — |
| 1,000 | 2.403 | 3.37x | 2.433 | 3.32x |
| 2,000 | 8.782 | 3.66x | 8.614 | 3.54x |
| 4,000 | 33.991 | 3.87x | 33.983 | 3.95x |
| 8,000 | 130.777 | 3.85x | 133.550 | 3.93x |

Peak RSS for that complete benchmark command was 30,964 KB. The untouched merge regression suite, full `plaid-core`, `cargo fmt --check`, and clippy all passed in that run.

The final A/B workflow (`Actions 38005891528`, job `114074474426`) remeasured baseline and candidate on the same runner. Its baseline was noisier but again clearly superlinear:

| facts | blocks baseline ms | edges baseline ms |
|---:|---:|---:|
| 500 | 0.387 | 0.383 |
| 1,000 | 1.361 | 1.274 |
| 2,000 | 4.760 | 4.543 |
| 4,000 | 18.112 | 18.092 |
| 8,000 | 101.447 | 90.423 |

## Candidate

`experiments/apply_programmap_merge_index.py` is source-bound to the exact quadratic block on the canonical base and refuses to patch if that source no longer matches uniquely. The branch-only workflow applies it, runs `rustfmt`, emits the resulting `indexed.patch`, and validates that patched tree.

The candidate indexes only the exact identities already used by the old comparisons:

- block key: `CodeAddress start`; semantic signature: `(size, delay_slot_entry)`;
- direct-edge key: `(CodeAddress site, EdgeKind)`; semantic signature: `(target, delay_slot)`.

For each key it records the first signature, a `conflicting` bit if any later signature differs, and the union of **all** evidence references under that exact key. If conflicting, it emits the same canonical unresolved diagnostic once.

No byte equality, payload equality, ROM offset equality, physical-address equality, or guessed provenance participates. Image and generation remain inside `CodeAddress`, so equal-looking addresses from distinct executable identities are never grouped.

### Why the diagnostic is equivalent

The old implementation emits one diagnostic for every contradictory pair and then canonicalizes diagnostics by semantic fact while unioning evidence. For a fixed conflict key:

1. if all signatures are equal, the old implementation emits no conflict and the indexed implementation emits no conflict;
2. if at least two signatures differ, every semantic variant participates in at least one contradictory pair with another variant, so the old post-canonicalization evidence set is the union of all facts under that key;
3. the indexed implementation directly computes that same union and emits the same `kind`, `site` and `detail` once.

The change therefore removes redundant pair enumeration; it does not select a winner or discard contradictory facts.

## Adversarial semantic checks

`crates/plaid-core/tests/programmap_merge_conflict_equivalence.rs` exercises:

- duplicate semantic block facts carrying disjoint provenance: one merged fact, both evidence refs, no fabricated conflict;
- three-way block conflict with two independent semantic dimensions (extent and delay-slot-entry), requiring all three evidence IDs;
- three-way direct-edge conflict with both target and delay-slot disagreement, requiring all three evidence IDs;
- merge-order reversal for both three-way conflicts;
- a second, non-conflicting identity key beside a conflicting key, proving identities do not bleed together.

The existing merge suite additionally retains checks for generation separation, byte/provenance identity, repeated sensor facts, static/dynamic provenance union, DMA/entry verification and indirect-proof conflict handling.

All focused and full tests passed with the indexed implementation.

## Candidate measurement

Same-run release medians from `Actions 38005891528`:

| facts | blocks indexed ms | block speedup | edges indexed ms | edge speedup |
|---:|---:|---:|---:|---:|
| 500 | 0.197 | 1.96x | 0.243 | 1.58x |
| 1,000 | 0.530 | 2.57x | 0.527 | 2.42x |
| 2,000 | 0.922 | 5.17x | 1.119 | 4.06x |
| 4,000 | 2.033 | 8.91x | 2.146 | 8.43x |
| 8,000 | 5.417 | **18.73x** | 7.435 | **12.16x** |

The whole indexed benchmark command used 30,884 KB peak RSS versus 30,952 KB for the same-run baseline. At 8,000 facts the indexed implementation therefore removed the dominant pairwise cost without trading it for material memory growth.

The measured indexed doubling ratios are noisy because several samples are below a few milliseconds, but the implementation itself performs one ordered-map insertion/lookup per fact plus evidence-set union, i.e. O((B + E) log n) conflict indexing rather than explicit B² + E² pair scans.

## Validation receipts

Final clean run: `38005891528`, job `114074474426`, head `9f9235abb7636daab86b378f4de0cf8fd574c14f`.

Passed:

- exact pinned Rabbitizer guard and build at `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`;
- release baseline benchmark;
- exact-source indexed transform + `git diff --check`;
- `cargo test -p plaid-core --test programmap_merge_conflict_equivalence -- --nocapture` (4/4);
- `cargo test -p plaid-core --test merge -- --nocapture` (14/14);
- `cargo test -p plaid-core` (full suite);
- `cargo fmt --all -- --check`;
- `cargo clippy -p plaid-core --all-targets -- -D warnings`;
- release indexed benchmark;
- artifact upload containing `baseline.log`, `indexed.log`, and generated `indexed.patch`.

Artifact ID: `11651376552`

Artifact ZIP SHA-256: `8d0cb1be2fbba523ab83a74450abc8202c91bf3f56b56716a68feddb7aee2c90`

An earlier handwritten unified-diff artifact was malformed and rejected by `git apply` before Rust was modified. It was deleted and is not semantic evidence. The source-bound transformer replaced it specifically to avoid silently patching the wrong source.

## Reproduction

```bash
cargo test --release -p plaid-core --test programmap_merge_scalability --no-run
MERGE_BENCH_SIZES=500,1000,2000,4000,8000 MERGE_BENCH_REPEATS=3 \
  /usr/bin/time -v cargo test --release -p plaid-core \
  --test programmap_merge_scalability benchmark_programmap_merge_scaling \
  -- --ignored --nocapture

python3 experiments/apply_programmap_merge_index.py
cargo fmt --all
cargo test -p plaid-core --test programmap_merge_conflict_equivalence -- --nocapture
cargo test -p plaid-core --test merge -- --nocapture
cargo test -p plaid-core
cargo fmt --all -- --check
cargo clippy -p plaid-core --all-targets -- -D warnings
```

## Closed-world impact

This investigation did **not** find a CLOSED/OPEN semantic laundering bug. It found a scalability defect in canonical evidence composition: contradiction-free ProgramMaps still pay quadratic conflict scans solely to prove that no same-identity block/edge contradiction exists. Whole-ROM closure work is expected to increase retained block/edge cardinality, so this cost can become a practical certificate-construction/merge bottleneck even when all semantic obligations are otherwise discharged.

The indexed candidate preserves the fail-closed contradiction model and all provenance while removing that avoidable all-pairs phase. This makes larger evidence composition materially more practical without weakening proof obligations.

## Remaining gap

This benchmark is synthetic and deliberately isolates block/direct-edge conflict detection. It does not prove all `ProgramMap` merge/validation paths scale well. In particular, indirect-site proof composition, evidence cardinality, unresolved diagnostics, validation, and whole-ROM serialization may become the next dominant costs once the pair scans are removed. Those require separate measurement rather than being smuggled into this result.

## Integration recommendation

Integrate the exact key-grouping change in `merge.rs` (the generated `indexed.patch` in the Actions artifact), keep the adversarial semantic-equivalence tests, and retain the ignored release scaling benchmark as a regression tool. Do not claim general ProgramMap scalability from this result; the validated claim is specifically that the block/direct-edge contradiction phase can be reduced from explicit all-pairs scans to exact-identity indexing without changing canonical conflict/provenance semantics.
