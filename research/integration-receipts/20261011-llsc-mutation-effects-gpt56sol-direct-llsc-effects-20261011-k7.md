# Direct integration receipt: completed LL/SC direct storage effects

Date: 2026-10-11

Worker: `gpt56sol-direct-llsc-effects-20261011-k7`

Cluster: source-bound completed VR4300 `SC`/`SCD` direct storage-effect mutation normalization

Claim base: `24689113469e0a3325601d7b6fd41b4d06ecf761`

Receipt-authoring canonical parent: `82088cd569cc11f3a70f5408485d9b7769f6ca85`

## Source research

- `research/llsc-store-effects-gpt56sol` at `cb037060c43c8bc4bace1b7db1fc8b607be3a8d3`
- `research/llsc-store-effects.md`
- `spikes/043-ares-llsc-store-effects`
- exact pinned ares revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- prior reservation-semantics disagreement work `research/llsc-provenance-gpt56sol` at `8abead9a26e5e086d54a395e060505a1002a1704`
- research-preservation commit `55076a90441c7d61975e0b0aaad031c725ab8529` was evidence-only and did not integrate a production consumer.

The integration harvest classified the LL/SC store-effect branch as indexed-only with no integration commit before this work.

## Reproduced evidence

Before adopting production code, the retained exact-pin ares fixture was transplanted only onto a disposable branch rooted at then-current `main`. Actions run `38154351786`, job `114514122293`, passed all 12 decoded `SC`/`SCD` cases, rejected all 5 forged histories, preserved baseline/plain/traced machine-state equivalence and produced result SHA-256 `08e7b5c6a79883663afb377514167170017ebcdca9379ffea59f7ac2b8d48569`.

After reconciling the production code onto NMI-enabled canonical state, exact-pin Actions run `38155057301`, job `114516212295`, again passed 12/12 cases, rejected 5/5 forgeries and produced the identical result SHA-256. The same reconciled production tree passed Actions run `38155000399`, job `114516052135`: focused `cargo test --locked -p plaid-core llsc_mutation` (12/12), `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, `python scripts/test_cli.py`, retained synthetic contracts 044 through 054, and the independent fetch-summary realizability oracle.

After canonical Watch integration, the candidate was validated again by Actions run `38155505450`, job `114517539045`: exact decoder pin, focused LL/SC regressions, format, strict workspace Clippy, full locked workspace tests, CLI, every retained synthetic contract 044 through 054, and the independent oracle all passed. The corresponding exact-pin ares run `38155539654`, job `114517642345`, again passed 12/12 cases, rejected 5/5 forgeries and produced result SHA-256 `08e7b5c6a79883663afb377514167170017ebcdca9379ffea59f7ac2b8d48569`.

Canonical `main` then advanced once more with the independent source-bound TLBR context-operation generation integration. This receipt is included in the TLBR-reconciled candidate and does not authorize a main write by itself. The required final focused/full validation against the lease-time canonical parent is recorded in issue #4's `MAIN-WRITE LEASE` / `MAIN-INTEGRATION CLOSEOUT` entries.

## Adopted invariant

Plaid may normalize an `SC` or `SCD` mutation only from an independently observed completed direct storage effect. Executing or decoding the instruction alone never mints a writer.

- No completed direct effect means no mutation witness. This is the required result for failed or faulting attempts once lower-observer completeness is independently established.
- `SC` consumes exactly the low 32 bits of the pre-instruction `rt` value and requires an exact 4-byte guest-order payload.
- `SCD` consumes the full 64-bit pre-instruction `rt` value and requires an exact 8-byte guest-order payload.
- Effective address computation uses the pre-instruction GPR snapshot, including the `base == rt` case. The post-instruction `rt` success flag is never substituted for source payload provenance.
- The supplied physical sink identity and mutation domain are retained as observed facts. This verifier does not reconstruct a TLB mapping, infer cacheability from the virtual address, or collapse cache-resident and backing effects because their bytes happen to match.
- A successful same-value effect remains a first-class event through its nonzero effect ordinal. Before/after equality does not erase the operation.
- A later 16-byte D-cache writeback is not the direct `SC`/`SCD` effect. Cached conditional-store ancestry must be composed through a separate resident-writer/writeback lineage.
- The bounded production primitive accepts only aligned effects entirely inside the current 8 MiB RDRAM scope.

## Rejected and superseded approaches

The production integration does not import or choose one emulator's LL/SC reservation-success semantics. Pinned references disagree on reservation behavior, so predicting success from LLAddr, address equality, final GPR state, current memory contents or one reference implementation remains unsound.

The integration also rejects value-equality provenance, address-only association, cache-tag-only association, final-state reconstruction, using the architectural `rt=1` success result as store payload, and treating a later whole-line writeback as the direct conditional-store mutation.

The research branch remains evidence, not authority. No research patch was mechanically merged.

## Files changed

- `crates/plaid-core/src/llsc_mutation.rs`: bounded decoder, completed-effect verifier, mutation witness and 12 adversarial unit tests.
- `crates/plaid-core/src/lib.rs`: exports `llsc_mutation` while preserving all canonical modules landed by intervening workers, including TLBR history.
- `research/integration-receipts/20261011-llsc-mutation-effects-gpt56sol-direct-llsc-effects-20261011-k7.md`: this receipt.

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `progress.json` are intentionally unchanged because this bounded sink normalizer does not discharge a canonical closure milestone or alter a solver/native-complete decision.

## Remaining proof obligations

This primitive does not prove lower-observer completeness or authenticate which completed sink belongs to which instruction attempt; callers must provide trustworthy effect ordering/association rather than searching equal payloads or addresses. Register-generation ancestry of the pre-instruction GPR values also remains separate.

Physical mapping provenance, TLB/alias identity, reverse-endian concerns outside the validated scope, D-cache resident-writer to writeback ancestry, invalidation/replacement chronology, non-RDRAM and SP/PIF sinks, complete CPU/RSP/DMA mutation census, save/restore/reset chronology, executable lifetimes, indirect-target/root closure, whole-ROM closure and native completeness all remain OPEN. `UNKNOWN` remains `UNKNOWN`.
