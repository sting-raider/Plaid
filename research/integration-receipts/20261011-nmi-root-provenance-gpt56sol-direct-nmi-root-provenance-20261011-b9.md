# Direct integration receipt: source-bound NMI root execution provenance

Date: 2026-10-11
Worker: `gpt56sol-direct-nmi-root-provenance-20261011-b9`
Cluster: NMI architectural root transfer -> fetch occurrence -> executed-byte provenance
Result at receipt creation: integration-ready pending final documentation/lease checks

## Base and source research

- Original claim base: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Reconciled current-main base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`.
- Integration head before this receipt: `e64f0632e43f8e22d6e0319eff1ac90db3eb2553`.
- Source research branch: `research/nmi-root-fetch-provenance-gpt56sol` at `6b22b7ebdf796f4032ca3c76534b868602f6917a`.
- Durable source note: `research/nmi-root-fetch-provenance.md`.
- Executable research fixture: `experiments/nmi-root-fetch-provenance/`.
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.
- Original validated exact-pin Actions run: `37970271648`, original job `113954819130`.
- Issue #4 source closeout: `6086491654`.

This integration did not mechanically merge the research branch. The research branch was treated as evidence for a bounded causal invariant and the production consumer was written independently in Rust against current canonical types.

## Reproduced evidence against current integration work

The exact pinned ares research job was freshly re-run during integration. Run `37970271648`, latest job `114509350476`, completed SUCCESS with all source guards, adversarial chronology model, exact-reference build/execution and result hashing green.

The validated bounded behavior remains:

1. An NMI architectural transfer can place PC at `0xffffffffbfc00000` while no root instruction fetch has occurred.
2. With the pending level still asserted, another real instruction step can re-enter NMI and again perform no root fetch.
3. After an explicit observed deassertion in the bounded positive fixture, the root fetch is uncached at physical `0x1fc00000`; an in-context PIF-ROM read at offset zero can supply the fetched word.
4. The same numeric root PC and the same returned word do not establish PIF provenance. An equal-valued SI latch and PIF lockout path provide counterexamples.
5. A prior real PIF read outside the active root-fetch context cannot be recycled as provenance for a later root fetch.

Fresh exact-pin execution preserves the source research result. The source branch records final result JSON SHA-256 `35e17aac669eb7efdab166e78d214efc98c0c7289864e1f6fb2ceab0b952185f` and independent adversarial-model payload SHA-256 `2c15ad692cd6927e146c2ab306c47f7158c418d2a52b1d0356a91cd4198cb900`.

Exact guarded source hashes from the validated research contract:

- ares CPU: `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1`
- exceptions: `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7`
- PIF I/O: `9bc87b9353a5b9c52f1b4b609aba4858e4a257f4a82d7007aee908a7faa2b86c`
- SI I/O: `6b63ba45c11d9242794aa211a8ee17ee742a4d8f348486a7a0c25382fca411ca`

The earlier research run `37969367759` is not semantic counterevidence. It failed a harness-only expectation that SI `ioBusy` would remain set after the equal-latch read. Exact pinned source showed `writeForceFinish()` clears it; only that assertion was corrected, and unchanged semantic experiments subsequently passed in `37969823321`, `37969879924`, and the final research-head run.

## Adopted production invariant

Production now has a bounded compiler-time evidence composer for externally captured NMI-root histories. It keeps three facts independent:

1. architectural NMI root transfer identity;
2. observed progress to an actual root fetch;
3. executed-byte source identity for that fetch.

The verifier requires contiguous original event ordinals and an externally supplied complete-capture SHA-256 namespace. A root fetch becomes eligible only after an observed post-transfer `pending=false` boundary. A PIF-ROM execution receipt requires one unique nonzero fetch context, exact NMI virtual/physical root addresses, uncached policy, exactly one matching offset-zero PIF read inside that context, a matching completed fetch word, and `PifRom` as the completed source classification.

The capture hash is an identity binding, not a completeness proof by itself. The source capture must still be independently authenticated/rechecked by its producer contract.

The following shortcuts remain forbidden:

- architectural root transfer => root fetch occurred;
- root address => PIF-ROM source;
- current/supplied firmware bytes => executed bytes;
- equal fetched/source values => provenance;
- an earlier/foreign source read => later fetch provenance;
- finite captured history => complete NMI/reset census.

## Adversarial regressions adopted

`crates/plaid-core/src/root_execution.rs` contains focused regressions covering:

- the one positive source-bound transfer/deassert/fetch/PIF-read/completion chain;
- transfer-only and persistent-NMI re-entry with zero certified root fetches;
- equal-valued foreign PIF reads and equal SI-latch payloads;
- fetch while NMI remains pending;
- wrong fetch context and wrong PIF offset;
- multiple matching source reads, which remain ambiguous rather than picking one;
- same-value source mismatch repaired by no other equal value;
- deleted/reordered ordinals;
- reused fetch contexts;
- malformed capture identity and truncated active fetch histories.

Missing or ambiguous evidence either remains unresolved or causes malformed supplied history to reject. No value-equality fallback exists.

## Files changed

Production integration:

- `crates/plaid-core/src/root_execution.rs`
- `crates/plaid-core/src/lib.rs`

Canonical documentation/receipt changes prepared with this integration:

- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- `research/integration-receipts/20261011-nmi-root-provenance-gpt56sol-direct-nmi-root-provenance-20261011-b9.md`

No `progress.json` change is justified: no native-complete, whole-ROM closure, or comparable milestone changes.

## Validation results

Initial PR validation intentionally exercised canonical repository CI and exposed only rustfmt differences before compilation. Those formatting-only failures were corrected; they are retained as audit history rather than hidden.

After current `main` advanced with the source-bound TLBWI integration, this branch was reconstructed as a single integration commit directly atop `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`, preserving `tlb_history`. `GitHub.compare_commits` reports it exactly one commit ahead and zero behind before documentation updates.

Canonical branch validation run `38152991626`, job `114510115755`, completed SUCCESS on the reconciled integration head. It includes:

- exact decoder dependency pin check: PASS
- `cargo fmt --all -- --check`: PASS
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS
- `cargo test --locked --workspace`: PASS
- synthetic CLI checks: PASS
- existing CPU-copy/XORI/CPU-SP/RSP-IMEM/XORI-cache/PageMask/PI-cache/SP-DMA/RSP-store/EntryHi/TLBR synthetic contracts: PASS
- independent fetch-summary assignment oracle: PASS

Fresh exact-pinned ares rerun: run `37970271648`, latest job `114509350476`, SUCCESS.

Final branch/head and main CI identifiers must be appended by the integration closeout after documentation and lease reconciliation, because the main-write protocol requires another full check if canonical `main` moves.

## Rejected or superseded patches/approaches

- No research branch was cherry-picked or mechanically merged.
- The research harness assertion that SI `ioBusy` remains set after the equal-latch read was rejected as incorrect against exact pinned source; it has no production semantic counterpart.
- No attempt is made to reuse the existing numeric exception-root resolver as NMI execution proof. ADR-0101's root-address selection boundary is intentionally kept distinct.
- No `ProgramMap` executable image/generation is fabricated from `0xffffffffbfc00000`, supplied PIF firmware, or a matching fetched word.
- No NMI/reset producer timing or repeated-reset policy is selected from a reference implementation.
- No solver blocker is waived and no native-complete state is promoted.

## Limitations and remaining proof obligations

This integration is deliberately bounded. It does **not** establish:

- complete NMI/reset producer or deassertion sensing;
- physical N64 reset-button timing or repeated-reset semantics;
- Status.SR hardware truth where references disagree;
- simultaneous interrupt/NMI priority;
- save/restore behavior for NMI producer identity;
- complete PIF/HLE or other possible root-source identity;
- reset root chronology as distinct from the bounded NMI path;
- cached handler generation/lifetime composition for other exception roots;
- a complete execution-root census;
- executable lifetime closure;
- whole-ROM CLOSED;
- native completeness.

If producer/deassertion history is missing, root-fetch occurrence remains unresolved. If a root fetch lacks a unique authenticated source chain, executed-byte provenance remains UNKNOWN. Those are proof blockers, not knobs to turn off.
