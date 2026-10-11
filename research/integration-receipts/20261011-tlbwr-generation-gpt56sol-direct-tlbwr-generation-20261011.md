# TLBWR selected-slot operation generation integration receipt

Date: 2026-10-11
Worker: `gpt56sol-direct-tlbwr-generation-20261011`
Cluster: source-bound TLBWR random-selected mapping-operation generations
Initial base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
Final validated canonical parent: `24689113469e0a3325601d7b6fd41b4d06ecf761`
Validated integration head before documentation: `03af6e53369d3710359ca35812fd52ce07eaad53`
Final validation Actions run: `38154288333`
Documentation finalizer Actions run: `38154502907`

## Source research

- `research/tlbwr-mapping-generation-gpt56sol` at
  `62f722a0c4db72963f6c873ddd33b8df95ddbc7e`
- `research/ares-tlbwr-mapping-generations.md`
- `spikes/044-ares-tlbwr-mapping-generation`
- research exact-pin Actions `37917241697` and `37917473981`
- issue #4 research closeout `6079063268`
- neighboring production ADR-0102 / `plaid-tlbwi-history-v0`, reviewed but
  deliberately not widened

The research branch is behavioral evidence, not production authority. Its Python
model, ares instrumentation/build path and workflow are not production dependencies.

## Reproduced evidence

Before adopting production code, Actions `38153324068` / job `114511093924`
materialized the exact research fixture from `62f722a`, checked its Git blob IDs,
fetched exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`,
passed the source guard and 10,000-history adversarial model, executed the real
TLBWR matrix and required `results.json` SHA-256
`405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c`.
After the only initial validation failure, a rustfmt-only correction, Actions
`38153779095` repeated the exact-pin reproduction successfully. The production PR
Rust gate `38153782154` then passed the exact decoder pin, formatting, strict
locked Clippy, full locked workspace tests, retained synthetic contracts and the
independent fetch-summary oracle. Focused TLB plus exact-reference run
`38153927826` also passed. The final validation run recorded above re-ran the
current canonical Rust gate, focused TLB regressions, all retained synthetic and
oracle checks, and the exact pinned ares reproduction after reconciliation onto
canonical `24689113469e0a3325601d7b6fd41b4d06ecf761`.

The decisive reproduced counterexamples are:

- a real same-value TLBWR can perform the operation while the complete before/after
  TLB snapshot has zero changed entries;
- CP0 Index can remain on an equal-payload decoy while the actual random-selected
  replacement slot is different;
- therefore operation occurrence and selected-slot identity cannot be reconstructed
  from final state, snapshot inequality, numeric Index or equal mapping payloads.

## Adopted invariant

Production uses a separate `plaid-tlbwr-history-v0` compiler-time source protocol
with explicit begin, observed selection, actual write and end boundaries. A
successful write is accepted only when its slot exactly equals the observed
selection and that selection is in the modeled TLB-entry range. Every accepted
write mints a new operation generation, including equal before/after content.
CP0 Index and Wired remain context only. Out-of-range selections and exception
attempts with no successful write are retained without inventing generations.
Complete-source SHA binding and full report rederivation are mandatory.

UNKNOWN remains UNKNOWN. The replay never infers a selected slot from CP0 Index,
snapshot diffs, equal values, later mappings or finite trace closure.

## Rejected or superseded approaches

- No mechanical merge of `research/tlbwr-mapping-generation-gpt56sol`.
- Do not generalize ADR-0102's TLBWI `selected_slot == CP0 Index` rule to TLBWR.
- Do not use before/after inequality to decide whether TLBWR occurred.
- Do not use equal entry payloads or later translations to select a replacement slot.
- Do not treat the pinned ares random sequence/distribution as hardware truth.
- Later duplicate TLBWR direct-integration claims on issue #4 were released after
  discovering the earlier live claim for this worker; no duplicate patch was used.
- Temporary branch-only reproduction/finalization workflows are deleted before
  landing and are not production dependencies.

## Production files

- `crates/plaid-core/src/tlbwr_history.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/tlbwr_history.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md` (ADR-0104)
- this receipt

## Tests and adversarial coverage

The final validation run recorded above executes:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- focused `tlb_history` and `tlbwr_history` tests
- every synthetic/oracle check retained by canonical `.github/workflows/rust.yml`
- exact pinned ares TLBWR source guard, 10,000-history adversarial model and real
  reference matrix with the expected result digest

The Rust regressions cover misleading CP0 Index, equal-value repeated writes,
identical payload in distinct selected slots, out-of-range/no-write attempts,
exception attempts, missing selection, write-without-selection, selected/write
slot substitution, duplicate selection, faulting writes, reordered ordinals and
epochs, wrong opcode, malformed fields/fingerprints/schema, complete-source
deletion, report deletion and forged closure/random-distribution flags. Existing
TLBWI tests remain a focused neighbor regression and its format/API is unchanged.

The first PR Rust run `38153582675` intentionally failed closed at formatting;
Clippy/tests were skipped and were not counted as passing. A rustfmt-only fix was
followed by fully green validation.

## Limitations and remaining proof obligations

This integration does **not** prove hardware random distribution or Wired edge
semantics, sensor completeness, a whole-machine TLB operation census, semantic
mapping validity, PageMask geometry, ASID/global behavior, TLBP/TLBR or EntryHi
writer chronology, alias/backing ancestry, D/I-cache residency or stale state,
save/restore/reset/NMI chronology, executable lifetimes, exception/root coverage,
indirect-target closure, RSP executable identity, whole-ROM closure or native
completeness. It does not clear solver blockers or enable a native-complete claim.

`progress.json` is unchanged because no whole-project milestone closed.
