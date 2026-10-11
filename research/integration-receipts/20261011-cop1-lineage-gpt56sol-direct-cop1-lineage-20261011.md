# Direct integration receipt: bounded COP1 FPR byte lineage

Date: 2026-10-11
Worker: `gpt56sol-direct-cop1-lineage-20261011`
Result at receipt creation: integration-ready pending main-write lease

## Base and source evidence

- Initial base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- Reconciled main before final validation: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Source research branch: `research/cop1-load-store-lineage-gpt56sol` at `a9e907d4b11b0b8478a2b1382779d04955c48d37`.
- Tested source-research head: `114bc1a3a4d556063ba5d60c69d1c6fd03a111d3`.
- Durable source note: `research/ares-cop1-load-store-lineage.md`.
- Executable research fixture: `spikes/043-ares-cop1-load-store-lineage/`.
- Issue #4 validated research closeout: comment `6078891467`.
- Original exact-reference Actions run: `37916051023`.
- The integration-harvest branch index classified this branch as `indexed_only` with no integration commit, so it was not assumed to require promotion until current main was checked for an equivalent consumer.
- Exact reference revisions remain those in `refs.lock.toml`; the behavioral reproduction used pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

This work is intentionally distinct from the concurrent COP1 store-mutation normalization lane. That lane classifies SWC1/SDC1 mutation domains and payload normalization; this lane retains source-read -> physical FPR byte generation -> later store ancestry. Neither substitutes for the other.

## Independent reproduction against current main

The research branch was treated as evidence rather than authority. A temporary branch-only workflow materialized only the validated spike-043 harness while keeping the integration branch based on current main, fetched exact pinned ares and rebuilt the reference fixture.

Actions run `38151426645`, job `114505524046`, reproduced:

- source guard: PASS;
- source-pair SHA-256: `48c5aa9ee8fef943fccdb80bae000ace0e815ab1f51710a41694548e3044d17e`;
- pure lineage model: 67 cases PASS;
- model SHA-256: `5a771c25653c96a8f858bc35b41d2acd835dd6d5c65ac9e65f82d8ccd617cf69`;
- exact pinned ares decoded matrix: 96/96 logical cases PASS;
- equal-value false joins exposed: 6;
- mixed-origin store results: 10;
- full load-origin store results: 26;
- result SHA-256: `f9c06faf9a98c48916d48f1b4409410b8dafca715074ff84585867850d6f0450`.

The 96-case matrix covers LWC1/LDC1 -> SWC1/SDC1 width/FR/ft combinations, same-value MTC1/DMTC1 overwrites, and CU1/alignment/TLB load-failure controls. Failed loads do not mint a memory-derived FPR generation. Equal-valued register overwrites replace the older origin. Mixed-width stores demonstrate that one store can carry bytes from different generations.

The temporary reproduction workflow was deleted after the receipt. It is not a production dependency. A branch-wide trigger briefly queued redundant reproduction runs after later commits; those runs are not used as evidence because run `38151426645` already reproduced the exact pin and durable hashes.

## Adopted production invariant

`plaid-core::cop1_lineage` now provides a source-bound compiler-time replay for a deliberately narrow capture protocol:

- histories must be bound to an externally trusted complete-source SHA-256;
- event ordinals must be contiguous;
- the admitted memory domain is successful aligned uncached identity-mapped RDRAM Word/Doubleword effects only;
- a completed LWC1/LDC1 FPR definition must cite one exact earlier completed read with the same context, phase, width and payload;
- a successful memory read may mint load-derived FPR bytes only through that explicit definition; value equality never selects a source;
- every physical FPR byte carries its own current origin generation;
- load-derived origins retain both the source-read ordinal and the FPR-write ordinal plus captured FR context;
- MTC1/DMTC1 definitions advance the selected physical byte origins even when the payload is unchanged;
- failed COP1 loads mint no FPR generation;
- SWC1/SDC1 ancestry is selected from the actual captured physical FPR and byte lanes at store time;
- mixed-origin stores remain mixed rather than being collapsed to one convenient source;
- report verification reconstructs the complete report from the bound source rather than trusting serialized conclusions.

The consumer deliberately **does not derive physical FPR selection from `FR` and architectural `ft`**. The capture must supply the physical register and selected byte lanes. This keeps the pinned ares odd-`FR=0` behavior as reference evidence rather than silently declaring it hardware truth.

The report hard-codes no closure promotion. `rdram_source_ancestry_certified`, `fpr_writer_census_certified`, `executable_lifetime_certified` and `native_complete` remain false.

## Production files changed

- `crates/plaid-core/src/cop1_lineage.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/cop1_lineage.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

No `progress.json` milestone is changed because this integrates one bounded provenance consumer, not a complete executable-universe or native-complete certificate.

## Focused and adversarial regressions

The Rust integration suite covers:

1. a mixed-width SDC1 whose upper bytes retain one LWC1 source generation while the remaining bytes retain distinct initial origins;
2. same-value MTC1 overwrite replacing the previous load origin;
3. equal payload plus changed FR/physical-lane selection failing to borrow ancestry from the wrong FPR storage;
4. failed load recording without an FPR generation;
5. missing/wrong read context rejecting a load-derived definition;
6. invalid lane shapes, payload mismatch, source-read reuse, deleted/reordered/noncontiguous events and forged ordinals rejecting;
7. complete-source SHA mismatch and forged report/native-complete fields rejecting under full replay.

These negatives specifically prevent provenance from being inferred from equal values, final FPR state, numeric architectural register names, finite execution alone, or a report detached from its complete source.

## Canonical Rust validation

After current main advanced to `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`, the integration branch was explicitly reconciled onto that commit before final validation.

Canonical PR workflow run `38152315207` on branch head `0f741801bfff93588dd23208d624e4d0e62ac6b5` completed successfully:

- exact Rabbitizer dependency pin guard — PASS;
- `cargo fmt --all -- --check` — PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings` — PASS;
- `cargo test --locked --workspace` — PASS;
- synthetic CLI checks — PASS;
- CPU-copy and XORI history contracts — PASS;
- CPU/SP and RSP/IMEM composition contracts — PASS;
- XORI/cache and PageMask/cache-remap contracts — PASS;
- PI/cache visibility and SP-DMA DMEM ingress contracts — PASS;
- RSP store isolation contracts — PASS;
- EntryHi/TLBR stale-reactivation contracts — PASS;
- independent fetch-summary assignment oracle — PASS.

Two pre-green failures were useful and are retained as audit history rather than hidden:

- run `38151963258` stopped at rustfmt before semantic tests;
- run `38152151785` passed formatting but strict Clippy found captured FPR-writer `fr` state was parsed and discarded. The integration was strengthened to retain FR and FPR-write generation identity in each relevant byte origin rather than suppressing the warning.

No semantic test failure was waived.

## Research patches rejected or kept research-only

- No research branch was mechanically merged or cherry-picked.
- No ares implementation code, generated instrumentation, branch-only build scaffold or reference workflow enters production.
- The exact-reference workflow used for reproduction was deleted.
- Any shortcut that selects provenance from matching payloads is rejected.
- Any shortcut that derives store ancestry from the current architectural `ft`/FR pair without an actual physical-lane receipt is rejected.
- Any shortcut that treats a failed CU1/alignment/TLB load attempt as an FPR definition is rejected.
- The pinned ares odd-`FR=0` physical mapping is not promoted as universal N64 hardware behavior.
- A finite 96-case matrix is not promoted into a complete FPR-writer census or whole-ROM closure proof.
- The concurrent COP1 mutation-normalization work is complementary and not superseded by this lineage consumer.

## Known limitations and remaining proof obligations

The following remain OPEN and must fail closed in broader certificates:

- ultimate writer ancestry of the source RDRAM bytes;
- complete FPR-writer coverage, including arithmetic, conversions and other COP1/register-producing operations;
- cached D-cache load/store residency, writeback and stale-state composition;
- successful TLB-backed COP1 memory paths and translation-context generations;
- reverse-endian and other unsupported access modes;
- complete CPU/RSP/DMA/reset/restore/debugger mutation census;
- composition with the separate COP1 SWC1/SDC1 mutation-domain normalizer;
- executable consumption of destination bytes, cache-visible executable state and executable lifetime boundaries;
- save/restore/reset/NMI effects and provenance revocation/retirement;
- hardware-oriented resolution of reference-specific FPR storage behavior;
- whole-ROM source/census/root/indirect-target closure and any native-complete claim.

Milestone change: none. Solver/native-complete behavior is unchanged and remains fail-closed.

## Post-claim canonical reconciliation

While this integration waited behind the serialized main-write lease, canonical
main advanced again to `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` with the
independent source-bound TLBWI operation-generation integration. The COP1 branch
was explicitly reconciled onto that commit before attempting its own lease.
`plaid_core::tlb_history`, its tests and its canonical documentation were kept;
`plaid_core::cop1_lineage` was added alongside it. Because the TLBWI integration
canonically occupied ADR-0102, the COP1 decision is renumbered ADR-0103 rather
than manufacturing a duplicate decision identity. The prior COP1 documentation
was not blindly merged over the new canonical ledgers.

The reconciled branch is re-run through the complete canonical Rust workflow
before main landing. The exact tested head/run and post-merge canonical CI are
recorded in the issue #4 main-integration closeout; no pre-reconciliation green
result is treated as permission to write the newer main.

