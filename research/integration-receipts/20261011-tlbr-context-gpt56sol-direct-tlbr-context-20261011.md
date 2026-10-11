# Direct integration receipt: source-bound TLBR context operations

Date: 2026-10-11

Worker: `gpt56sol-direct-tlbr-context-20261011`

Cluster: successful decoded TLBR translation-context operation generations

## Source research

- `research/tlbp-tlbr-effects-gpt56sol` at `d972ccbb2393b1adeafdc98659c236c0ab468d72`, especially `research/ares-tlbp-tlbr-effects.md`.
- `research/tlbr-icache-lifetime-gpt56sol` at `a625e4ac88482b6947c018dabf464073e58187bc`, with executable evidence head `dd84b71880cff84e1173b1950fe90bee38be8965`.
- Canonical retained evidence in `research/tlbr-cache-primary.md` and `spikes/054-ares-tlbr-cache-lifetime/`.
- Existing production `tlb_history` TLBWI replay was used only as a fail-closed source-binding pattern. TLBR does not reuse its installed-entry generation semantics.

Research branches are evidence, not authority. No research branch was mechanically merged.

## Reproduced evidence

Before adopting production code, current canonical main at `9154b30b12026c8c122f654d7fe90f0f67968dce` passed the retained synthetic TLBR cache-reactivation contract in canonical Actions run `38153549823`, job `114511771408`, together with exact decoder pin, formatting, strict workspace Clippy and the full locked workspace suite.

The independent exact-reference TLBR/TLBP effects workflow `37919649022`, job `113784223064`, completed successfully. Its steps fetched the exact pinned references, guarded the relevant source contracts, executed the exact-reference matrix and hashed/uploaded the durable result payload. The pinned ares revision is `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

The stronger TLBR/cache lifetime research run `37999435843`, job `114053639012`, also succeeded at the exact pinned ares revision. It executed real guest TLBR opcode `0x42000001`, retained a same-value successful TLBR as an operation, retained out-of-range Index 63 as an instruction occurrence without a successful context load, kept TLBP separate, and demonstrated stale resident-cache reactivation without installed-entry replacement. Its recorded result JSON SHA-256 is `3624aea92b6c3f77c455c4342ab967cc0fd3c56eb7044bc6f24bf9fe61e28d67`.

Production candidate validation then passed twice before this receipt:

- run `38154431261`, job `114514361581`: exact decoder dependency pin, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, focused `tlbr_history`, retained spike 054, and independent fetch-summary oracle all PASS.
- after reconciling onto canonical `24689113469e0a3325601d7b6fd41b4d06ecf761`, run `38154707884`, job `114515179620` repeated the same complete gate and PASSed.

A later final reconciliation/validation is required if canonical main changes again before the main-write lease; its exact head/run belongs in the issue #4 closeout.

## Adopted invariant

For one externally authenticated complete TLBR history:

1. A begin record must be an aligned decoded TLBR (`0x42000001`) and binds one captured CP0 Index, pre-operation context fingerprint, execution epoch and operation context.
2. A successful in-range TLBR requires one explicit load boundary whose selected slot is exactly the captured CP0 Index and whose selected-entry fingerprint equals the observed post-load active-context fingerprint.
3. Every such successful load mints a fresh ordered **TLBR operation generation**, even when the pre/post context fingerprints are identical. Same values do not erase occurrence.
4. A successful TLBR context load is not a TLB-entry mutation. The consumer never mints an installed mapping-entry generation.
5. Out-of-range Index and faulting/no-load attempts are retained as attempts but mint no successful context-load generation.
6. An in-range apparently successful TLBR without its load boundary, duplicate/fabricated load boundaries, reordered ordinals/epochs, wrong slots/opcodes/contexts, malformed fingerprints, selected-entry/post-context disagreement, and report/source deletion or flag forgery fail closed.
7. The entire supplied source is SHA-256 bound to an independently trusted expected digest and report verification replays the complete source rather than trusting serialized report claims.

This proves only the operation boundaries present in the authenticated supplied source. It does not prove that the source sensor observed every translation-context writer.

## Rejected or deliberately unadopted work

- The research fixture/model is not production code and is not imported.
- TLBP is not promoted as a context-write generation; it remains outside this production receipt.
- TLBR does not borrow `tlb_history`'s installed-entry generation semantics. Installed mapping mutation remains separate.
- Current ASID, equal register snapshots, matching selected values, matching addresses, cache tags, or later successful fetches cannot fabricate a missing TLBR operation/load boundary.
- The ares result is not promoted to universal VR4300 hardware truth. Pinned Gopher64/Mupen disagreements remain explicit research context.
- The consumer does not infer PageMask/global semantics, TLBWR chronology, cache residency/fill identity, current backing, executable lifetime, reset/save/restore continuity, root coverage or whole-ROM closure.

## Production files

Permanent integration paths:

- `crates/plaid-core/src/tlbr_history.rs`
- `crates/plaid-core/tests/tlbr_history.rs`
- `crates/plaid-core/src/lib.rs` (module export only)
- this receipt

A branch-only `.github/workflows/direct-tlbr-context.yml` exists solely because canonical Rust Actions were changed to manual-only while this direct integration was in flight. It must be removed before the production merge and is not a production artifact.

## Adversarial coverage

Focused Rust tests cover:

- two same-content successful TLBRs minting distinct operation generations;
- real context-content change while keeping installed-mapping certification false;
- equal payload/ASID in a different selected slot;
- selected-entry versus post-load fingerprint mismatch;
- out-of-range Index and exception attempts producing no generation;
- missing, duplicate, fabricated and wrong-context load boundaries;
- fault plus fabricated successful load;
- wrong opcode, ordinal gap/reorder, unaligned PC, malformed digest, unknown schema field and epoch rollback;
- complete-source deletion and forged report/certification flags.

The retained spike 054 supplies the cache/reactivation counterexamples that motivate keeping context operation, installed mapping, resident cache and backing generations distinct.

## Canonical documentation and milestone state

No `progress.json` milestone changes. No STATUS/NEXT/DECISIONS closure claim is changed by this bounded replay alone: ADR-0098 already records the TLBR research distinction, and the existing TLBWI/NEXT text still correctly leaves complete context-writer chronology, PageMask/ASID/global state, TLBWR, cache residency, save/restore/reset composition and full TLB mutation census OPEN. The durable production adoption is therefore recorded here rather than inventing a broader certificate.

## Limitations and remaining proof obligations

- Complete sensor/context-writer census is unproved. MTC0/DMTC0 EntryHi and other context producers must be composed explicitly.
- Installed TLB-entry provenance, TLBWR/random replacement, PageMask geometry, ASID/global state ownership and overlapping-entry behavior remain separate.
- Cache resident/fill generation, stale-cache lifetime and backing/writer ancestry remain separate.
- Save/restore/reset/NMI chronology and abandoned-future cuts remain separate.
- The normalized context fingerprint is supplied evidence; this module validates its syntax and causal placement but does not independently reconstruct every architectural field from a machine snapshot.
- Emulator/source disagreement means this is bounded evidence, not a hardware-complete semantic claim.
- Whole-ROM closure and `native_complete` remain OPEN/false. No runtime interpreter/JIT policy is affected.

UNKNOWN stays UNKNOWN. Successful same-value operations stay operations. Missing causal boundaries never become provenance by equality.
