# Direct integration receipt: bounded VR4300 PageMask geometry

- Worker: `gpt56sol-direct-pagemask-geometry-20261011`
- Initial canonical base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
- First reconciled base: `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`
- Final pre-document reconciliation base: `9154b30b12026c8c122f654d7fe90f0f67968dce`
- Integration branch: `direct-integration/pagemask-geometry-gpt56sol-direct-pagemask-geometry-20261011`
- Validation PR: #32

## Source research

This integration consumes only the bounded translation-geometry conclusion from:

- `research/tlb-pagemask-gpt56sol` at `409017c6be4aff64b53f1d93161cc23d4696aee6`;
- `research/ares-tlb-pagemask-fetch-provenance.md`;
- `experiments/tlb-pagemask/source_model.py` and `source_guard.py`;
- the already-harvested canonical `spikes/049-ares-pagemask-cache-remap` / ADR-0093 fixture;
- exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and the pinned n64-systemtest source evidence recorded by the research receipt.

The research branch is evidence, not a patch source. No research implementation or reference-emulator code is merged.

## Reproduced evidence against current main

A fresh disposable validation branch derived from the integration tree ran the canonical spike 049 fixture against an unmodified exact-pinned ares checkout in Actions run `38153630245`, job `114512003631`:

- six adversarial verifier tests passed;
- executed large-page scope reported page sizes `[16384, 65536]`;
- equal-content mapping rewrites and temporary mapping/context unreachability preserved the measured resident behavior;
- `EVIDENCE_SHA256=4227e340a3000607b70cde96339a379737ea46167a7cf10573fe7aba093050fd`;
- `RESULT_SHA256=d884a8ce86b01192750afd9f7539e2a618f5a0dcb72c54f777134c9561fe8a35`;
- producer ancestry, mutation coverage, executable lifetime and native completeness remained explicitly false.

The disposable evidence-only branch/workflow is validation scaffolding and is not part of the production integration.

Before the later canonical-main reconciliation, PR #32 Actions run `38153565891`, job `114511818906`, passed the exact decoder pin guard, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, synthetic CLI checks, every retained synthetic contract including PageMask/EntryHi/TLBR cache regressions, and the independent fetch-summary oracle. After `main` advanced to `9154b30b12026c8c122f654d7fe90f0f67968dce`, the branch was reconciled again and the same canonical gate was rerun before any main-write lease.

## Adopted invariant

Production now has a deliberately narrow geometry primitive for an entry that has **already** been independently selected and authenticated:

- raw PageMask `0x0000` means 4 KiB halves, selector `0x1000`, offset mask `0x0fff`;
- raw PageMask `0x6000` means 16 KiB halves, selector `0x4000`, offset mask `0x3fff`;
- raw PageMask `0x1e000` means 64 KiB halves, selector `0x10000`, offset mask `0xffff`;
- even/odd EntryLo selection follows the page-size selector, not a permanent virtual-address bit 12;
- the in-page offset is derived from the selected supported page size;
- malformed masks and larger page sizes whose current evidence is model/source-only fail closed.

The `0x0009_1000` 16-KiB counterexample is retained as a regression: bit 12 is set, but bit 14 is clear, so the validated geometry selects the even half. A fixed-4-KiB reconstruction would select the planted odd-half decoy and can fabricate a source even when values agree.

## Rejected or superseded approaches

- No mechanical merge of `research/tlb-pagemask-gpt56sol`.
- No fixed-bit-12 even/odd selection for large pages.
- No inference from equal payloads, equal virtual addresses, final cache tags, or current backing state.
- No import of ares PageMask normalization for malformed encodings as hardware truth.
- No production promotion of 256-KiB or 1-MiB page geometry from model/source evidence alone.
- No promotion of spike 049 cache indexing, miss/fill behavior or ares-specific resident policy into a universal N64 cache rule; the recorded ares/Gopher64 indexing disagreement remains unresolved.

## Files changed

- `crates/plaid-core/src/tlb_geometry.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

`progress.json` is intentionally unchanged because no whole-ROM/native milestone changed.

## Limitations and remaining proof obligations

This primitive is not a TLB translator or provenance certificate. The following remain OPEN and must be composed independently before any executable-origin or closed-world claim:

- TLB entry lookup/selection and overlap policy;
- VPN2/PageMask match semantics outside this bounded geometry primitive;
- ASID/global matching and translation-context generations;
- EntryLo valid/dirty/CCA semantics and selected PFN identity;
- PageMask/EntryHi/EntryLo writer chronology, TLBWI/TLBWR/TLBP/TLBR operation histories and save/restore/reset behavior;
- privilege/region/address-width semantics and aliases;
- physical-backing transaction provenance;
- I-cache/D-cache indexing, residency, fill, invalidation, writeback and stale-state generations;
- larger legal page sizes not dynamically exercised by the accepted scope;
- complete executable mutation census, executable lifetimes, exception/interrupt composition, whole-ROM closure and native completeness.

UNKNOWN remains UNKNOWN. The geometry receipt may only refine an already trustworthy mapping fact; it cannot manufacture that mapping fact.