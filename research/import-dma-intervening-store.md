# Importer DMA provenance across an intervening CPU store

Status: VALIDATED

Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/import-dma-intervening-store-gpt56sol`

Candidate source commit: `f06766500ec08dca3cbde62fc6757ed226a6982a`

## Question

Can discovery-trace import safely attach a prior PI DMA as the executable byte origin when a successful CPU word store later writes part of the same physical span before the span is compiled, but the final bytes still equal canonical ROM?

No. Content equality cannot restore superseded writer provenance.

## Reproduced current-main bug

`merge::import` retained prior `RomDmaObserved` transfers and, at `UnitCompiled`, chose the latest covering DMA by physical extent. `record_load` then authenticated the captured compiled bytes against canonical ROM. A `CpuWordStoreObserved` was retained as a raw fact, but its executable-write consequence was derived only if a `Region` already existed at store time.

That leaves a first-compilation hole:

1. DMA canonical ROM bytes to physical RDRAM.
2. Execute a successful aligned `SW` to a word inside that future executable span.
3. Write the exact same word value already present there.
4. Compile the span for the first time.

There was no executable `Region` when step 2 happened, so the store did not become an `ExecutableWrite`. The final snapshot still matched ROM. Current main therefore created a `LoadMapping` whose `copy_event` named the old DMA even though the CPU store was the later successful writer of part of the compiled bytes.

This is a causal provenance error, not a byte-integrity error.

Semantic baseline GitHub Actions run `38072850810`, job `114273674231`, ran against unmodified production importer code and the pinned Rabbitizer revision `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`. Three controls passed and exactly the same-value post-DMA store witness failed. The failure printed the stale mapping with `copy_event = trace:<session>:0` while event 1 was the later overlapping store.

An earlier workflow run `38072763579` is discarded as evidence because the newly added test did not compile due to an integer type-annotation mistake.

## Candidate fix

The branch importer retains trace-order physical writer information for successful `CpuWordStoreObserved` events in addition to the existing DMA list.

When a compiled span has a covering DMA candidate, the importer now checks whether any later observed successful CPU store overlaps the compiled physical span. If so:

- the DMA is not accepted as the current byte origin;
- a unique equal supplied `CodeImage` is not allowed to replace the missing causal provenance;
- the imported image keeps `rom_offset = None`;
- an `intervening_executable_store` unresolved fact is emitted with the exact store-event evidence;
- ordinary `unknown_executable_source` remains visible.

The rule never compares the stored value with the ROM or compiled payload. A successful writer generation matters even when the bytes are unchanged.

A later covering DMA after the store restores DMA provenance normally, because that later copy supersedes the store. A non-overlapping store does not revoke the copy.

## Adversarial matrix

`crates/plaid-core/tests/import_dma_intervening_store.rs` covers seven cases:

1. DMA -> overlapping same-value store -> compile: DMA provenance must be revoked.
2. Same witness plus a byte-identical supplied known image: equality cannot restore source identity.
3. DMA -> same-value store -> invalidation -> compile: invalidation cannot resurrect the older DMA writer.
4. Overlapping store -> DMA -> compile: the later copy legitimately supersedes the store.
5. Store -> invalidation -> DMA -> compile: the later covering copy legitimately restores provenance.
6. DMA -> non-overlapping store -> compile: the unrelated store does not revoke the copy.
7. DMA -> overlapping changed-value store -> compile: the successful store is treated as the causal writer, rather than misdescribing the stale DMA as a snapshot mismatch.

Candidate validation run `38073213160`, job `114274729165`, passed all seven focused cases, the complete `plaid-core` suite (110 tests total), `cargo fmt --all -- --check`, and `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`. The job then committed the formatted candidate source and regression to the research branch as `f06766500ec08dca3cbde62fc6757ed226a6982a`.

## Composition with prior research

This composes rather than replaces:

- ADR-0009 deletion/fabrication resistance: retained primitive events must continue to constrain conclusions.
- ADR-0010 actual-copy provenance: an executable mapping must name an operation that actually explains the observed bytes.
- ADR-0018 copy identity distinct from compilation identity: compilation is not evidence that an older copy remains the current writer.
- ADR-0020 raw successful `SW` observations: a successful store is retained even when its payload equals prior memory.
- `research/W012-load-evidence.md`: final snapshot equality validates content, but by itself cannot establish latest-writer causality.
- completed raw-store solver work: solver-side handling of retained stores is still useful, but it does not repair an importer that already attached a stale DMA byte origin before the first executable `Region` existed.

## Closed-world impact

This closes one concrete provenance-laundering path in discovery import: a same-value CPU store can no longer disappear between a verified ROM DMA and first compilation, allowing the older DMA `copy_event` to masquerade as the current producer.

It does **not** establish complete mutation coverage or make whole-ROM closure possible. The trace sensor still observes only its declared successful aligned cached-RDRAM `SW` subset. Unobserved stores, other CPU write opcodes, RSP writes, cache-resident stale instruction state, aliases without explicit physical evidence, transformations, relocation and complete executable lifetimes remain separate obligations.

The candidate is intentionally fail-closed. It does not yet promote the CPU store into a positive executable source lineage; it only proves that the older DMA is no longer sufficient and preserves the source as unknown.

## Scalability note

The bounded candidate linearly checks accumulated observed word stores when evaluating a covering DMA for a compiled unit. This is simple and auditable but is not the final history-index design for very large traces. A production integration can preserve the same causal rule with a physical-range last-writer index or shared provenance-history structure if profiling shows the scan matters.

## Reproduction

Baseline semantic failure was obtained with the regression committed but unmodified production `merge.rs`:

```sh
cargo test --locked -p plaid-core --test import_dma_intervening_store -- --nocapture
```

Candidate validation:

```sh
cargo test --locked -p plaid-core --test import_dma_intervening_store -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

## Integration recommendation

Adopt the causal-writer check in `merge.rs` and the seven-case regression. Preserve these boundaries:

- use trace event order and explicit physical overlap, never byte equality, to decide whether a DMA remains current;
- do not fall back to an equal supplied image after an observed later writer;
- retain exact writer-event evidence on the unresolved fact;
- do not claim positive CPU-store source lineage from this limited sensor;
- consider replacing the linear writer scan with a shared indexed history representation separately, without weakening the provenance rule.

The research workflow and patcher are branch-only scaffolding. Nothing from this worker was merged into `main`.