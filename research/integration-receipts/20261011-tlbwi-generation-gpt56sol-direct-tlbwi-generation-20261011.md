# Direct integration receipt: source-bound TLBWI operation generations

Date: 2026-10-11
Worker: `gpt56sol-direct-tlbwi-generation-20261011`
Cluster: source-bound TLBWI mapping-operation generations

## Canonical bases and source evidence

- Initial canonical base: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Reconciled/frozen canonical base after the exception-root integration: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Source research branch: `research/tlbwi-mapping-generation-gpt56sol` at `62ff5f01639a2b088feb593c0add2523ddbc0bde`.
- Durable research note: `research/ares-tlbwi-mapping-generations.md`.
- Executable research fixture on that branch: `spikes/045-ares-tlbwi-mapping-generation/`. This branch-only spike is evidence only and is not imported into production.
- Issue #4 research closeout: comment `6079389384`.
- Original exact-reference Actions run: `37919698671`.
- Exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Reproduced evidence

Current `main` before this integration had extensive finite TLB/cache research but no production consumer representing TLBWI mapping-operation occurrence independently of mapping-content inequality. The source research was inspected rather than merged mechanically.

The independent adversarial model was reproduced with its exact deterministic result:

- seed: `362056669001`
- cases: 20,000
- legal writes: 10,035
- out-of-range attempts: 9,965
- same-value legal writes: 2,654
- snapshot-diff false negatives: 2,654
- equal-payload slot ambiguity cases: 3,262
- payload-first wrong-slot cases: 1,636
- explicit forgeries rejected: 4
- model SHA-256: `8c0350d8f1604b6935fcf68b0a148bb7688aaf1629355490b56816a7e7dee868`

The exact pinned-reference job was rerun during integration rather than relying only on its historical result. Fresh job `114506551511` on Actions run `37919698671` passed the exact ares fetch, source guard, independent model, real decoded TLBWI matrix, result hashing and artifact upload. It reproduced:

- `RESULT_SHA256=6ef416a44a0fb533a1e291b8adab42b158f0eb581ec81a9174509b3d6ab606e0`
- repeated stdout SHA-256 `3f4cb59ab36e9f12713002684e65e6c6d38d3591fdc286a2e6549131abd2ae33`
- model SHA-256 `8c0350d8f1604b6935fcf68b0a148bb7688aaf1629355490b56816a7e7dee868`
- uploaded result artifact ID `11707086199`
- uploaded artifact ZIP SHA-256 `55e529329cf9d965a0b2e93718a48f1e588d92b11c9bf14ea3901ba7abe06d2a`

The exact reference behavior retained by the production abstraction is narrow: decoded TLBWI uses the captured CP0 Index selected slot; a legal selected-slot write occurs even when the normalized entry content is unchanged; out-of-range Index and privilege-failed attempts produce no successful TLB write generation. Equal payload in another slot is not slot identity.

## Adopted invariant and production abstraction

`plaid_core::tlb_history` adds a strict compiler-time replay format, `plaid-tlbwi-history-v0`, with source-bound begin/write/end records.

A successful in-range decoded TLBWI mints one ordered `operation_generation` only when an actual matching selected-slot write boundary is present. The generation advances even when `before_entry == after_entry`. The selected slot must equal the captured CP0 Index; equal fingerprints at another slot cannot satisfy the write. An out-of-range or exception attempt may be retained as a no-write attempt but mints no successful operation generation.

The replay rejects noncontiguous/reordered ordinals, nested or truncated instruction contexts, context/epoch/PC mismatches, unaligned PCs, non-TLBWI words, invalid fingerprints, duplicate/fabricated write boundaries, an in-range successful instruction with no write boundary, a write paired with a faulting end, and unknown schema fields. The complete supplied source is bound to an externally trusted SHA-256. `verify_tlbwi_report` reconstructs the complete report from that source rather than trusting report flags or deletable derived fields.

The report deliberately leaves all of these false: sensor-coverage certification, mapping-semantics certification, translation-context certification, cache-residency certification, executable-lifetime certification and native completeness. Operation generation, selected-slot identity and entry-content identity are distinct facts.

## Adversarial regressions

The focused Rust tests cover:

1. repeated same-content legal writes mint distinct ordered operation generations;
2. an equal-payload different slot cannot steal write identity;
3. out-of-range and exception attempts mint no successful generation;
4. missing, fabricated, duplicate, context-mismatched and fault-with-write boundaries fail closed;
5. ordinal/epoch reordering, wrong opcode, unaligned PC, malformed fingerprint and schema forgery reject;
6. source deletion under the old receipt and report/native-flag forgery fail exact rechecking;
7. identical mapping content installed into distinct selected slots remains distinct operation history.

These controls directly target the research counterexamples: equal value is not provenance, a snapshot difference is not operation occurrence, and final state does not identify the selected slot or causal history.

## Rejected or superseded candidates

- The research branch, generated reference harness and research-only workflow were not merged mechanically.
- Snapshot-difference inference is rejected: it misses every reproduced same-value legal TLBWI.
- Payload-first/equal-payload slot inference is rejected: mapping content cannot choose the selected physical TLB slot.
- A mapping-content fingerprint is not promoted into an operation identity, mapping generation, translation-context generation, cache residency or executable lifetime.
- TLBWR, TLBP, TLBR and broader PageMask/ASID/global mapping chronology are not silently generalized from the TLBWI result.
- No finite source is treated as proof that the sensor observed every relevant operation.
- No reference implementation code or runtime dependency enters Plaid production/native mode.

## Files changed

- `crates/plaid-core/src/tlb_history.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/tlb_history.rs`
- `research/integration-receipts/20261011-tlbwi-generation-gpt56sol-direct-tlbwi-generation-20261011.md`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`

`progress.json` is intentionally unchanged because no milestone, whole-ROM closure state or native-complete state changes.

## Validation results

The first branch CI at `6ae0586521382ae3d74d43c961a41f49ec5a14de` failed only the formatting gate. The formatter's exact diff was applied; no semantic weakening was made.

After `main` advanced with the independent exception-root integration, this branch was reconciled without force to `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`. Reconciled head `c5973646a6cfeb0eeb026efa0d24844c7a7f1578` passed canonical Actions run `38151912118`, job `114506931601`, including:

- exact decoder dependency pin check;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- all retained CPU-copy/XORI/CPU-SP/RSP composition/cache/PageMask/PI/SP-DMA/RSP-store/EntryHi/TLBR contracts;
- the independent fetch-summary assignment oracle.

The separate fresh exact-pinned ares rerun described above also passed. Final documentation/receipt branch state is revalidated before main landing under the main-write lease; canonical post-merge CI is recorded in issue #4 closeout.

## Limitations and remaining proof obligations

This integration proves only the consistency of an authenticated supplied TLBWI operation history under the bounded format. It does not prove the source capture is complete, that the recorded entry fingerprint fully represents architectural mapping semantics, or that an installed mapping was used by a particular executable fetch.

Remaining obligations include complete TLB mutation census; TLBWR selection and occurrence; TLBP/TLBR/context-writer chronology; PageMask, ASID/global and translation-context generations; aliases and backing identities; cache fill/residency and stale-state composition; save/restore/reset/NMI chronology; executable byte provenance and lifetime; exception/root reachability; indirect-target closure; RSP identity; and whole-ROM/native-complete proof. Missing evidence remains OPEN.
