# DMA copy-event identity must denote one transaction

Result: **VALIDATED**

Worker: `gpt56sol-dma-event-uniqueness-20261010`

Canonical base: `211176e7a489fecf8331d02915ee982cd279cb62`

Research branch: `research/dma-event-uniqueness-gpt56sol`

## Question

Can one `LoadMapping.copy_event` identity be attached to multiple semantically different `ObservedDma` transactions, allowing one purported copy operation to certify incompatible ROM-source or physical-destination histories?

The answer on the canonical base was yes.

## Why this identity is causal

`merge::import_trace` turns each `TraceEvent::RomDmaObserved` into one `ObservedDma` and gives that concrete event a session-qualified evidence ID of the form `trace:{session}:{seq}`. Later executable-load reconstruction carries that same ID as `LoadObservation.copy_event` and then `LoadMapping.copy_event`.

This is intentionally distinct from compilation or post-copy snapshot evidence. A single real DMA can cover multiple executable subranges, so multiple load records may legitimately reference the same copy event. Conversely, two different DMA transactions must not become the same causal event merely because a hand-edited or merged ProgramMap repeats an evidence string.

Before this work, `ProgramMap::validate()` checked each load independently with `copy_covers(...)`: it required that *some* DMA row bearing the selected event ID cover that load. It did not require all DMA rows bearing a used copy-event identity to agree on the transaction that event denotes.

## Reproduction on current main

The regression at `crates/plaid-core/tests/dma_event_uniqueness.rs` constructed one Trace evidence identity, `copy0`, and attached it to two incompatible DMA transactions:

- `(rom_offset=64, physical_destination=0, size=8)`
- `(rom_offset=80, physical_destination=32, size=8)`

Each downstream load had a matching Region and was independently covered by one of those forged DMA rows. The canonical-base validator accepted the map.

Baseline Actions receipt:

- run: `38005300277`
- job: `114072586532`
- head: `7ff4c3b78d5cec8830b73e500b22ec17c62312ea`
- command: `cargo test --locked -p plaid-core --test dma_event_uniqueness -- --nocapture`
- result: expected failure, 2 controls passed and `one_copy_event_cannot_name_two_distinct_dma_transactions` failed because `map.validate()` returned `Ok`
- pinned Rabbitizer compiled from `724a49a5b4dbfb99f1a9e6992e63964fd29c90c8`

Controls established that this was not merely forbidding provenance union:

- distinct copy-event IDs may describe distinct DMA transactions;
- the same transaction tuple may be represented again with additional provenance;
- one large DMA event may legitimately cover multiple executable subranges.

## Candidate fix

Production candidate commit:

`c395922ee15a3f48ce2b2d53f93489ebb940e9f2` (`fix: bind load copy events to unique DMA transactions`)

The validator now applies a narrow invariant only to evidence IDs actually used as `LoadMapping.copy_event`: every `ObservedDma` row containing that ID must agree on `(rom_offset, physical_destination, size)`.

This deliberately does **not** impose uniqueness on arbitrary shared evidence references. It preserves canonical provenance union for unrelated evidence and preserves the valid case where one real transfer covers several executable load subranges.

The validation error is:

`load copy event has conflicting observed DMA identity`

## Adversarial matrix

The final focused suite attacks the identity components independently and compositionally:

1. Same event, different physical destination -> rejected.
2. Same event, different ROM offset -> rejected.
3. Same event, different transfer size -> rejected.
4. Same event, fully incompatible DMA tuple -> rejected.
5. Different events, different transactions -> accepted.
6. Same event, same transaction, additional provenance -> accepted.
7. One 16-byte DMA event backing two separate 8-byte executable subranges -> accepted.
8. Two maps that each validate independently but assign the same event ID to different DMA transactions -> `merge_maps` rejects their composition.

The last case is the important higher-order proof attack: individually valid evidence fragments cannot compose into an impossible causal history merely because they share an identifier.

## Validation

Final pre-note Actions receipt:

- run: `38005637607`
- job: `114073668379`
- head: `ed4263e422fe47082fcc0d07c18c2a19449cad71`
- focused DMA identity suite: 6 passed, 0 failed
- complete `plaid-core` suite: 109 tests passed, 0 failed
- `cargo fmt --all -- --check`: passed
- `cargo clippy --locked -p plaid-core --all-targets -- -D warnings`: passed
- workflow confirmed `candidate fix already applied`, so the production change was already checkpointed in `c395922e...`

Exact reproduction commands:

```sh
cargo test --locked -p plaid-core --test dma_event_uniqueness -- --nocapture
cargo test --locked -p plaid-core
cargo fmt --all -- --check
cargo clippy --locked -p plaid-core --all-targets -- -D warnings
```

The branch-only workflow is `.github/workflows/research-dma-event-uniqueness.yml`. The deterministic patch reproducer is `spikes/dma-event-uniqueness/apply_candidate_fix.py`.

## Prior research composed or challenged

This finding composes the following existing design rules rather than introducing a new notion of identity:

- ADR-0009 deletion/fabrication resistance: a certificate must not become stronger when evidence is forged or rearranged.
- ADR-0010 actual-copy provenance: executable load provenance must name the operation that actually copied the bytes.
- ADR-0018 copy identity distinct from executable snapshot/compilation identity: recompilation is not a new copy, while a distinct sensed copy is a distinct causal event.
- ADR-0023 canonical provenance union: repeated identical semantic facts may accumulate provenance without inventing a different semantic fact.

The regression also relies on the existing `repeated_compilation_is_not_a_new_dma_reload` behavior: several executable loads may safely reuse one `copy_event` only when they are subranges of the same underlying DMA transaction.

## Closed-world impact

Before the fix, a forged or incorrectly composed ProgramMap could make one trace event causally occur as two incompatible DMA operations. Downstream executable-source facts could therefore appear individually well-founded while the combined provenance history was impossible.

The fix closes that internal consistency hole. It makes future executable provenance and lifetime composition stricter by ensuring a used copy-event identity has one DMA source/destination/extent meaning.

This does **not** make WholeRom closed. It does not prove trace authenticity, complete mutation accounting, CPU/RSP copy or transform provenance, cache/TLB visibility, overlay lifetime, interrupt roots, or the absence of unobserved writers. Those obligations remain independent and OPEN where not otherwise proved.

## Integration recommendation

Adopt the validator guard and regression tests. The production change is intentionally small and local to ProgramMap validation; it rejects only a causal contradiction that the importer itself cannot legitimately produce.

For canonical integration, reproduce or cherry-pick `c395922ee15a3f48ce2b2d53f93489ebb940e9f2` together with the regression coverage from this research branch. No merge into `main` was performed by this worker.
