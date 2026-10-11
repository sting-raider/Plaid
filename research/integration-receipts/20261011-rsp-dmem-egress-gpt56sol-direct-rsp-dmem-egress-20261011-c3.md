# Direct integration receipt: RSP DMEM reverse-DMA egress

Date: 2026-10-11
Worker: `gpt56sol-direct-rsp-dmem-egress-20261011-c3`
Claim base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
Reconciled main before final exact-pin validation: `31c10020665e8386656fd943acab111b5c7e1671`
Final reconciled main before lease: `24689113469e0a3325601d7b6fd41b4d06ecf761`
Cluster: source-bound RSP DMEM writer ancestry through completed reverse SP-DMA effects into RDRAM
Decision: ADR-0104

## Source research

- branch `research/rsp-dmem-dma-egress-gpt56sol`
- final research head `b02d281624e4b077709a6255c569bbb25f8ef486`
- executable evidence commit `2a395485b3828badb8e2f68178f626008da9fa61`
- note `research/rsp-dmem-dma-egress.md`
- fixture `spikes/043-ares-rsp-dmem-dma-egress/`
- exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- original exact-pin research Actions `37917520106`

The research branch was treated as evidence, not as an authority or merge source.

## Reproduced evidence

A fresh exact-pin reproduction was first run from current-at-claim main in Actions `38153305667`, job `114511037497`. The exact ares revision and guarded source hashes matched. The run reproduced 42 events, 17 RSP DMEM sink effects, one CPU DMEM sink, eight completed reverse SP-DMA Word effects, 13 exported RSP bytes, four exported CPU bytes and 15 fixture-initial bytes. All nine measured forged histories rejected; unchanged-reference neutrality and repeated enabled output were deterministic.

After main advanced and the independent IMEM reverse-DMA integration landed, this branch was explicitly reconciled with `31c10020665e8386656fd943acab111b5c7e1671` and the complete exact-pin validation was repeated in Actions `38154297446`, job `114513969889`. The immutable research fixture was checked out only for the reference run and then removed before Rust validation. The exact reproduced hashes were:

- event SHA-256: `060e97a1fa347dc1b2a928852491da320040a0dcaee6bf24dd8460de2c285060`
- scoped egress SHA-256: `4702a25853c06b1b082985076830a2e325ebc50965a68c63ce918a5065b0ac14`
- trace SHA-256: `25248a01ac69ebb9c7f5697a0fb010f632c7a852b5310475d9a7472f9b0dd927`
- result SHA-256: `03d5138badc899d3b19fe24401199a672db6ce2eb2e1e00957e882bff6e54274`

The final exact-pin evidence artifact is Actions artifact `11708021422`, ZIP SHA-256 `25db053eefe6fc425641b25b6c5b63a52815a69398a816eb4fadda9f7d5db946`.

Main then advanced once more to `24689113469e0a3325601d7b6fd41b4d06ecf761`, changing only `.github/workflows/rust.yml` to make the canonical Rust workflow manual-only. The branch incorporated that commit as explicit ancestry in `c5273cb41fccc7ca15c9c01a58e3c810964c3030`. Because the main-write protocol requires revalidation after any main movement, the focused and full canonical suite was rerun in Actions `38154679139`, job `114515095330`; every step passed. The temporary trigger used to execute that now-manual suite was removed from the production diff.

## Adopted invariant

Production now has a bounded source-bound replay for completed DMEM-source reverse SP-DMA Word effects. The completed DMA descriptor fragment selects the four DMEM source bytes before payload comparison. Payload equality is therefore only a consistency check and cannot identify a source, bank or writer generation.

Within an externally authenticated complete supplied history:

- every successful authenticated RSP or separately identified external DMEM write mints a fresh writer generation even when bytes are unchanged;
- a concrete unknown writer cuts provenance only for the byte lanes it touches;
- DMEM write/source addressing preserves 4-KiB wrap byte by byte;
- the DMEM bank bit, current descriptor fragment, effect address and derived source offset are rechecked;
- observed source bytes must agree with the exported Word, but an unobserved byte remains `Unobserved` rather than borrowing equal data from elsewhere;
- full source SHA binding and full report reconstruction are required for verification;
- mutation-census, SP-lifecycle, hardware-timing, RDRAM-lifetime, executable-lifetime and native-complete report flags remain false.

## Rejected or superseded patches/assumptions

- No research branch was mechanically merged.
- The research fixture's synthetic initial-generation label was not promoted. Production uses `Unobserved` until an authenticated writer is supplied.
- Equal values, final DMEM contents, matching addresses, nearest writes and another bank's evidence do not recover source identity.
- The independent IMEM reverse-DMA primitive is not reused as DMEM provenance; bank-specific evidence remains separate.
- The research spike and branch-only reproduction/format/fix/validation workflows were deliberately removed from the production diff after validation.
- No general CPU-to-SP writer classifier, scheduler/request-lifetime model, hardware timing claim, solver waiver or native-lowering dependency was added.

## Production files changed

- `crates/plaid-core/src/rsp_dmem_dma_egress.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

`progress.json` is unchanged because this integration reduces evidence-model debt without completing a declared milestone.

## Tests and results

Exact-pin reconciled validation, Actions `38154297446`:

- exact pinned ares source guard and behavioral reproduction: PASS
- 9/9 measured forged histories: rejected as expected
- `cargo test --locked -p plaid-core rsp_dmem_dma_egress`: PASS, seven focused adversarial tests
- `cargo fmt --all -- --check`: PASS
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS
- `cargo test --locked --workspace`: PASS

Final post-main-movement canonical validation, Actions `38154679139`:

- focused `rsp_dmem_dma_egress` tests: PASS
- exact decoder dependency pin: PASS
- `cargo fmt --all -- --check`: PASS
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS
- `cargo test --locked --workspace`: PASS
- synthetic CLI, CPU-copy, XORI, CPU SP producer, RSP CPU IMEM composition, XORI cache visibility, PageMask cache remap, PI cache visibility, SP DMA DMEM ingress, RSP store isolation, EntryHi cache reactivation and TLBR cache reactivation contracts: PASS
- independent fetch-summary assignment oracle: PASS

The focused production tests cover same-value fresh generations, equal-payload decoy sources, byte-local external/unknown overwrites, 4-KiB wrap, forged descriptor bank/source/payload/order, missing initial ancestry, and source/report receipt forgery.

Earlier canonical PR validation at Actions `38153978029`, before the later main reconciliations, also passed formatting, strict workspace Clippy, full workspace tests and the retained synthetic contracts. It is supporting evidence only; `38154297446` and `38154679139` are the current merge gates.

## Limitations and remaining proof obligations

This integration does not certify:

- completeness of the DMEM mutation sensor or whole-machine writer census;
- SP DMA request identity, queue lifetime, completion authenticity beyond the supplied completed effect, hardware timing/atomicity or arbitrary concurrent DMA;
- ultimate ancestry of `External` writers;
- downstream RDRAM storage-writer chronology after export;
- aliases/TLB translation history or cache-visible executable residency;
- eventual executable consumption or executable lifetime;
- save/restore/reset/NMI chronology;
- a complete RSP executable universe, whole-ROM CLOSED, or native completeness.

Any missing, reordered, forged or unclassified causal edge remains rejected or UNKNOWN. The next valid composition is with authenticated SP request/completion identity, downstream RDRAM writer ancestry and eventual executable-consumer/lifetime evidence. No unresolved obligation may be waived by this primitive.
