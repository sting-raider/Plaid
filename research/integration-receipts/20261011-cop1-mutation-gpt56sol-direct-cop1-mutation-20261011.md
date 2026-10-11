# COP1 store mutation integration receipt

Date: 2026-10-11

Worker: `gpt56sol-direct-cop1-mutation-20261011`

Initial base: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

Integration cluster: bounded, source-checked normalization of completed VR4300 `SWC1`/`SDC1` mutation effects.

## Source research

- `research/cop1-store-mutation-gpt56sol` at `b95a51d4f5ec8fcba3b8ac85c222a11dafe05a49`
- `research/ares-cop1-store-mutation.md`
- `spikes/035-ares-cop1-stores/`
- original research Actions run `37849520956`
- issue #4 research closeout `6069760858`
- pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- existing ADR-0061 and the executable-mutation obligations in `docs/NEXT.md`

The research branch was used as evidence, not merged mechanically.

## Reproduced evidence against current integration code

A one-off branch-only workflow checked out the exact pinned ares revision and was removed immediately after the run. Actions run `38151911005`, job `114506928522`, completed successfully on integration head `adc3c023cda96c9fa7b7c0341485e8a0684de7f0`:

- independent FR payload-selection model: **PASS**, 100,000 adversarial register cases;
- model SHA-256: `3c5075ecc450af75d167dd3a225943c410e6dcc1e0f4c4877604f08f353aa285`;
- exact pinned ares `SWC1`/`SDC1` matrix: **PASS**, 192 repeated cases;
- result SHA-256: `f85760603c11f51ede16e4a9d4b4965703c6a635e5b925401d8014494ab68e05`.

The digests exactly match the validated research result. The production code itself contains no reference-emulator implementation, build dependency, generated shadow source, or runtime dependency.

Pre-rebase canonical Rust validation on branch head `58e7a9d30f8debe54ef6964b7dac857970ce8823`, Actions run `38152081954`, job `114507427603`, also completed successfully:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- canonical CLI checks;
- synthetic CPU-copy, XORI, CPU-SP producer, RSP-to-CPU-IMEM, XORI/cache, PageMask/cache, PI/cache, SP-DMA DMEM-ingress, RSP-store, EntryHi/cache and TLBR/cache contracts;
- independent fetch-summary assignment oracle.

Final current-main reconciliation and canonical-main CI are recorded in issue #4 closeout rather than guessed here before they occur.

## Adopted invariant

Plaid may normalize one independently observed, completed `SWC1` or `SDC1` effect only when the supplied architectural context and sink effect agree.

The production primitive:

- decodes only `SWC1` and `SDC1`;
- derives the virtual destination from the captured base GPR plus the signed immediate;
- preserves the requested FPR index separately from the actual raw FPR storage selected by FR mode;
- for FR=0, models paired raw-FPR storage explicitly: even `SWC1` uses the pair's low 32 bits, odd `SWC1` uses the pair's high 32 bits, and `SDC1` uses the full even-pair 64 bits;
- for FR=1, uses the named FPR, with `SWC1` selecting its low 32 bits and `SDC1` its full 64 bits;
- requires a claimed completed effect to be impossible when CU1 is disabled;
- treats absence of a completed effect as absence of a mutation witness;
- checks effect width, alignment, bounded 8-MiB RDRAM span, destination and exact semantic guest-order payload;
- preserves `cache_resident` and `backing` as different mutation domains even when their payload bytes are equal;
- retains an explicit effect ordinal rather than manufacturing identity from equal values or final state.

The primitive verifies a supplied completed effect. It does not itself discover or authenticate the lower mutation sensor, reconstruct TLB translation, choose a physical destination from a virtual address, infer endian routing, or establish the effect's ultimate source ancestry.

## Adversarial controls retained

Production tests reject or distinguish:

- CU1-disabled context with a forged completed sink;
- failed/no-effect stores, which create no writer;
- equal payload produced by different FR source identities;
- payload equality that disagrees with the selected raw FPR bytes;
- cache-resident versus backing effects with equal payloads;
- forged virtual destinations;
- misaligned completed effects;
- out-of-RDRAM physical effects;
- unsupported integer-store opcodes.

These controls intentionally keep content identity separate from source/register identity and mutation domain.

## Rejected or superseded integration approaches

The integration does **not**:

- extend the old aligned-`SW` trace event and pretend that opcode coverage is complete;
- infer a writer merely because an `SWC1`/`SDC1` instruction executed;
- infer a backing write from a cached resident mutation;
- join FPR provenance by equal numeric payload;
- infer physical mapping from KSEG/TLB-looking addresses;
- use final before/after equality to conclude that no operation occurred;
- promote ares's one `Dual` callback for `SDC1`, or Mupen/Gopher's two `Word` callbacks, into a hardware transaction-count or atomicity rule;
- merge the research branch or import its temporary reference build workflow.

An initial public verifier revision accepted a claimed completed effect without carrying CU1 context. That shape was rejected during integration review. The public API now requires CU1 and rejects a completed sink when CU1 is disabled.

## Production files

- `crates/plaid-core/src/cpu_mutation.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/cpu_mutation.rs`
- this receipt

No `progress.json` milestone changes. ADR-0061 already states the underlying architectural decision, so no duplicate ADR is introduced.

## Limitations and remaining proof obligations

This integration does not close executable mutation accounting. The following remain OPEN:

- an authenticated, complete below-handler CPU mutation sensor/census across successful and failed effects;
- general address translation, aliases, TLB generations, reverse-endian/routing and physical-backing identity;
- causal FPR definition/producer ancestry and same-value generation changes;
- D-cache resident generation/revision, writeback, invalidation, refill and restore composition;
- integer subword/unaligned/64-bit stores, LL/SC families, other coprocessor effects, DMA, RSP and out-of-band writers as one complete mutation universe;
- overlapping/partial writes and writer chronology at arbitrary executable spans;
- executable consumption and lifetime/retirement proof;
- complete exception/reset/save-restore interaction;
- whole-ROM mutation census, closure and native-complete certification.

`UNKNOWN` remains `UNKNOWN` whenever those obligations are not independently established. This primitive cannot waive a solver obligation and does not make a finite trace exhaustive.
