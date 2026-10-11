# Direct integration receipt: RSP DMEM reverse-DMA egress

Date: 2026-10-11
Worker: `gpt56sol-direct-rsp-dmem-egress-20261011-c3`
Claim base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
Final canonical reconciliation base: `0e0e999b626dbda3f47cfd6aa89673618ae20350`
Cluster: source-bound RSP DMEM writer ancestry through completed reverse SP-DMA effects into RDRAM
Decision: ADR-0105

## Source research

- branch `research/rsp-dmem-dma-egress-gpt56sol`
- final research head `b02d281624e4b077709a6255c569bbb25f8ef486`
- executable evidence commit `2a395485b3828badb8e2f68178f626008da9fa61`
- note `research/rsp-dmem-dma-egress.md`
- fixture `spikes/043-ares-rsp-dmem-dma-egress/`
- exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- original exact-pin research Actions `37917520106`

The research branch was evidence, not a merge authority.

## Reproduced evidence

Fresh exact-pin reproduction from claim-base-era main ran in Actions `38153305667`, job `114511037497`: exact ares/source guards matched; the fixture produced 42 events, 17 RSP DMEM sink effects, one CPU DMEM sink and eight completed reverse SP-DMA Word effects. Fixture attribution was 13 RSP bytes, four CPU bytes and 15 synthetic-initial bytes. All nine measured forged histories rejected; disabled/reference and repeated enabled outputs were deterministic.

After reconciliation with the independently landed IMEM egress primitive, exact-pin plus production validation ran in Actions `38154297446`, job `114513969889`. Hashes: event `060e97a1fa347dc1b2a928852491da320040a0dcaee6bf24dd8460de2c285060`; scoped egress `4702a25853c06b1b082985076830a2e325ebc50965a68c63ce918a5065b0ac14`; trace `25248a01ac69ebb9c7f5697a0fb010f632c7a852b5310475d9a7472f9b0dd927`; result `03d5138badc899d3b19fe24401199a672db6ce2eb2e1e00957e882bff6e54274`. Evidence artifact `11708021422`, ZIP SHA-256 `25db053eefe6fc425641b25b6c5b63a52815a69398a816eb4fadda9f7d5db946`. Focused tests, fmt, strict Clippy and full workspace tests passed.

Main later changed its canonical Rust workflow to manual-only at `24689113469e0a3325601d7b6fd41b4d06ecf761`. After explicit ancestry reconciliation, Actions `38154679139`, job `114515095330` reran focused DMEM tests, exact decoder pin, fmt, strict workspace Clippy, full workspace tests, CLI, all retained synthetic contracts and the fetch-summary oracle; every step passed.

Canonical main then advanced to `0e0e999b626dbda3f47cfd6aa89673618ae20350` with the cached exception-root-generation integration. That integration occupied ADR-0104, so this DMEM decision was renumbered to ADR-0105 before landing. The branch was rebuilt from that canonical tree while preserving the already-tested DMEM module blob byte-for-byte (`cfe45a098f76ad3531866898b936d5cbde4deae7`).

## Adopted invariant

Production exposes bounded source-bound replay for completed DMEM-source reverse SP-DMA Word effects. The completed DMA descriptor fragment selects the four DMEM source bytes before payload comparison; payload equality is only a consistency check and never identifies a source, bank or generation. Authenticated successful RSP or external writes mint fresh generations even for equal bytes. Concrete unknown writers cut only touched byte lanes. DMEM wrap is per byte. Unobserved initial bytes remain `Unobserved`. Full source SHA binding and full report reconstruction are required. Mutation-census, SP-lifecycle, timing, RDRAM-lifetime, executable-lifetime and native-complete flags remain false.

## Rejected or superseded assumptions

- No research branch was mechanically merged.
- The fixture's synthetic initial-generation label was not promoted.
- Equal values, final state, matching addresses, nearest writes and another bank's evidence do not recover source identity.
- IMEM reverse-DMA evidence is not substituted for DMEM provenance.
- Branch-only reference/format/fix/validation workflows were removed after use.
- No CPU-to-SP census, scheduler/request-lifetime model, hardware timing claim, solver waiver or native-lowering dependency was added.

## Production files changed

- `crates/plaid-core/src/rsp_dmem_dma_egress.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

`progress.json` is unchanged because this reduces evidence-model debt without completing a declared milestone.

## Tests and results

Focused production tests cover same-value fresh generations, equal-payload decoy sources, byte-local external/unknown overwrites, 4-KiB wrap, forged descriptor bank/source/payload/order, missing initial ancestry, and source/report receipt forgery.

Pre-final runs: Actions `38154297446` and `38154679139` passed the exact-pin, focused, mandatory workspace and retained synthetic/oracle gates as described above.

Final reconciliation validation against canonical base `0e0e999b626dbda3f47cfd6aa89673618ae20350`: Actions `38155441657`, job `114517351446`, PASS. The run passed focused `rsp_dmem_dma_egress` tests, exact Rabbitizer dependency pin verification, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, synthetic CLI checks, CPU-copy/XORI/CPU-SP/RSP-CPU-IMEM/cache/PageMask/PI/SP-DMA/RSP-store/EntryHi/TLBR contracts, and the independent fetch-summary assignment oracle. The two branch-only refresh/validation workflows were deleted after this green run and are not production changes.

## Limitations and remaining proof obligations

This integration does not certify completeness of the DMEM mutation sensor or whole-machine writer census; SP DMA request identity, queue lifetime, completion authenticity beyond the supplied completed effect, hardware timing/atomicity or arbitrary concurrent DMA; ultimate ancestry of `External` writers; downstream RDRAM storage-writer chronology; aliases/TLB or cache-visible executable residency; eventual executable consumption/lifetime; save/restore/reset/NMI chronology; a complete RSP executable universe; whole-ROM CLOSED; or native completeness. Missing, reordered, forged or unclassified causal edges remain rejected or UNKNOWN. Next composition is authenticated SP request/completion identity plus downstream RDRAM writer ancestry and eventual executable-consumer/lifetime evidence. No unresolved obligation may be waived.
