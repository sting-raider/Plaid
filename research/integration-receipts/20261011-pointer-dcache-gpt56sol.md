# Direct integration receipt: source-bound D-cache Word replay

Date: 2026-10-11

Worker: `gpt56sol-direct-pointer-dcache-20261011`

## Base and source research

- Initial canonical `main`: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`.
- After the serialized exception-root integration advanced canonical main, this batch was semantically rebased onto `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- After the serialized TLBWI-generation integration advanced canonical main again, this batch was semantically rebased onto `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`, preserving both concurrent production modules and all canonical TLBWI documentation.
- Pointer alias / immutability evidence: `research/pointer-table-alias-gpt56` at `ef31dc6066712c509fa7e7e33c1f7224b9a8dd9c` and `research/pointer-table-immutability-aliases.md`.
- D-cache load-source evidence: `research/pointer-table-dcache-load-source-gpt56sol` at `8da5cc98d03a522509c1f5c307de6552d08605f4` and `research/ares-pointer-table-dcache-load-source.md`.
- Issue #4 research closeout used: comment `6096882129`.
- Issue #4 direct-integration claim: comment `6110446975`.
- Exact pinned ares revision for the source experiment: `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

## Independently reproduced against current main

The production promotion does not trust the research branch's `VALIDATED` label or copy its patch. Five reference-shaped histories were independently reconstructed as Rust integration regressions against current Plaid:

1. `stale`: a resident Word remains A after backing becomes B; the dispatch witness names the resident source generation and separately reports current backing B.
2. `same`: a same-value backing rewrite A -> A advances backing generation without rewriting resident source identity.
3. `refill`: replacement and later refill after backing mutation selects the new fill generation and its exact captured backing generation.
4. `same_refill`: old fill, equal-payload conflict decoy and same-value rewritten/refilled table all contain A, but the dispatch witness selects the later table fill by chronology rather than payload equality.
5. `resident`: a cache-resident write B -> C creates a distinct resident-write generation while backing remains B.

Adversarial regressions additionally reject or distinguish deleted same-value writes, deleted dispatch reads, reordered writes, duplicated ordinals, forged slot/tag state, forged physical source, forged hit state, producer-claimed source fields, dirty replacement without writeback evidence, dangling/ambiguous fills, unknown schema fields, unaligned events and report self-recertification. A separate ordering regression inserts a same-value backing rewrite between a successful burst and the later miss: the earlier burst is rejected rather than being laundered into a post-write cache-fill generation.

## Production invariant adopted

`plaid_core::dcache_source` is an original, bounded compiler-time replay consumer for source-bound aligned D-cache Word evidence.

- The complete supplied source is bound to an externally supplied SHA-256 receipt.
- One strict contiguous ordinal orders initial/current backing state, successful backing writes, successful backing burst reads, cache fills, resident writes and reads.
- Backing writes mint new storage generations even when the payload is unchanged.
- A miss may consume only the immediately preceding successful backing burst for the same physical line; an intervening record breaks the pairing rather than leaving a stale burst available for causal reuse.
- Successful fill bursts snapshot the exact current backing generation for every Word; fill generations are then minted separately from those backing generations.
- Resident writes mint separate resident generations and retain the replaced resident generation as chronology, not as an invented dataflow source.
- Read witnesses name the exact resident line/Word generation that supplied the value and separately expose current backing generation/value.
- Report verification replays the complete source and exact-compares every output field.
- Slot and tag values are treated as source-recorded identities. No ares tag-bit/index formula is promoted as hardware truth.

All certification fields remain false: source-history coverage, mapping history, mutation coverage, executable lifetime and native completeness.

## Research patches rejected or superseded for production

The integration deliberately did **not** cherry-pick the research branch. In particular it did not import:

- generated/patched ares observer sources or reference binaries;
- the branch-only spike `047` path, which conflicts with current canonical spike numbering;
- research workflow/build scaffolding;
- the Python reducer as a runtime or production dependency;
- any ares-specific tag encoding as universal hardware behavior;
- any solver waiver, pointer-table immutability certificate or target-lifetime inference.

The research branch remains evidence. Its production-shaped patch history is superseded by the smaller original Rust consumer and adversarial regression suite recorded here.

## Production files changed

- `crates/plaid-core/src/dcache_source.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/dcache_source.rs`
- `crates/plaid-core/tests/dcache_source_order.rs`
- `research/integration-receipts/20261011-pointer-dcache-gpt56sol.md`

The serialized rebases preserve concurrent `exception_roots` and `tlb_history` integration in `lib.rs` and retain canonical documentation from `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`. No ProgramMap schema, solver rule, pointer-table blocker or progress milestone changes. `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `docs/progress.json` are deliberately unchanged by this batch: the high-level pointer-table milestone remains partial, the existing NEXT obligation to prove pointer-table immutability/guard coverage remains accurate, and no architectural policy changed. The implementation-specific state and validation record therefore live in this durable receipt rather than rewriting canonical status documents merely to announce activity.

## Validation

Canonical pull-request workflow run `38151729633` passed completely on frozen pre-rebase head `fdda961884072505128d293517a38f2740025f2e`, including the final immediate burst-pairing hardening and ordering regression. After the exception-root integration, post-rebase workflow run `38152247176` passed completely on `945bd883140df145582b96c46dcbe8a2da516228`. Canonical main then advanced again under the valid TLBWI-generation main-write lease; this exact production tree was semantically rebased onto `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`. The final receipt-bearing head is required to pass the full canonical workflow again before this worker acquires its own lease; that final run is recorded in the issue #4 integration closeout.

Focused regression results on the fully green earlier heads:

- `tests/dcache_source.rs`: 5 passed, 0 failed.
- `tests/dcache_source_order.rs`: 1 passed, 0 failed.
- The five semantic reference shapes and all integration adversaries described above passed.

Full canonical gates passed on those frozen production trees:

- exact pinned Rabbitizer dependency check: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS;
- `cargo test --locked --workspace`: PASS;
- `python scripts/test_cli.py`: PASS, including deterministic maps, target traversal, identity gates and OPEN whole-ROM reports;
- canonical synthetic CPU-copy, XORI, CPU-SP, RSP/CPU-IMEM, XORI-cache, PageMask-cache, PI-cache, SP-DMA-DMEM, RSP-store, EntryHi-cache and TLBR-cache contracts: PASS;
- independent fetch-summary realizability oracle: PASS with 21,845 exhaustive histories and 20,000 random oracle comparisons.

The first development CI attempts exposed only formatting and one Clippy warning in a test fixture helper. Both were corrected before the fully green frozen runs; no production semantic relaxation was used.

## Pinned-reference check

The exact source-research branch's final Actions validation, run `38047306633`, passed at pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` and exercised the actual interpreted LW-to-JR reference fixture plus its adversaries. This direct integration did not repeat or modify that reference build. Instead, the five resulting semantic shapes were independently restated and checked by the new production Rust replay against current main. No claim is made beyond the bounded pinned-reference behavior already recorded by that closeout.

## Known limitations and remaining proof obligations

This consumer authenticates and replays a supplied finite history. It does **not** authenticate that the sensor captured every relevant machine operation.

Open obligations remain:

- complete cache-operation/invalidation/writeback chronology beyond the represented subset;
- dirty eviction/writeback provenance;
- composition with the now-canonical `tlb_history` operation generations, plus PageMask/ASID/context/alias history; the existence of that separate primitive does not identify the mapping context of these D-cache reads;
- reset, NMI, save/restore and other resident-lifetime boundaries;
- complete CPU/RSP/DMA/debugger/frontend mutation census;
- ultimate provenance of the supplied initial backing state;
- pointer-table immutability over the declared execution lifetime;
- guard/path completeness beyond existing bounded recognizers;
- target executable-generation identity and lifetime;
- whole-ROM executable-universe closure and native completeness.

Unsupported or incomplete histories reject rather than becoming inferred provenance. Equal payloads never collapse generations.

## Milestone impact

No progress milestone changes state. `Pointer-table immutability proof` remains **partial**. The integration adds a reusable production evidence consumer needed by a future proof; it does not itself clear `pointer_table_immutability_unproven` or `pointer_table_target_identity_unproven` and does not justify regenerating the progress map.
