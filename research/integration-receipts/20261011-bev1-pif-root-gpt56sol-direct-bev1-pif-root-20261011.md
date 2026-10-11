# Direct integration receipt: BEV=1 general-root PIF backing provenance

Date: 2026-10-11
Worker: `gpt56sol-direct-bev1-pif-root-20261011`
Initial canonical base: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`
Cluster: exact-fetch supplied-PIF backing provenance for the BEV=1 32-bit general exception root

## Source research

- Branch: `research/bev1-exception-pif-root-gpt56sol`
- Validated research head: `37c88e57cf4a5e3c5e65b919b31936fee2990ddf`
- Note: `research/bev1-exception-pif-root.md`
- Experiment: `experiments/bev1-exception-pif-root`
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Research workflow: Actions `38004246774`, job `114069254414`
- Recorded instrumented evidence SHA-256: `014521b49d3fe5bda2433d5328624af8e0d2284320df6b341c3d85e2ac662bf0`
- Recorded complete results SHA-256: `27ae59f4f372e19b5d62150be3895412a23351ba2c45eb0d30c09952b7341853`
- Recorded adversarial-model SHA-256: `5c08b240f42b970105354d53206871f4deeaacf1ccc94cc9e7bfc9e177517d16`

The research established a bounded causal distinction: a real BEV=1 general exception can fetch the handler word at virtual `0xffffffffbfc00380` / physical `0x1fc00380` through the ordinary PIF-ROM backing path, but identical address and returned bits do not imply that origin. In the SI-busy-latch control the same word executes at the same root with no PIF-ROM backing read. Lockout, prior equal-valued reads and physical/masked-offset decoys likewise cannot substitute for the same-fetch backing event.

## Reproduced evidence on current production semantics

Before adding a production composition primitive, the integration branch added `crates/plaid-core/tests/bev1_pif_root_reproduction.rs` against canonical `539ff0ce...`. The two regressions use only the existing public `exception_roots` and `pif_history` report types and demonstrate the missing consumer boundary:

1. an earlier PIF-backed sample with the same root address and instruction word can satisfy an address/value matcher for a later unwitnessed fetch even though its `first_fetch` is different;
2. the existing PIF report may coalesce repeated identical backed observations, so `(pc, physical, word, offset)` plus first/last metadata is not an exact occurrence receipt when `observations > 1`.

This reproduces the important research counterexample at the current production abstraction boundary without rerunning or modifying the reference emulator. The first PR run (`38152607200`) failed only the formatting gate for import order; no semantic gate ran after that formatting failure. After formatting and production integration, canonical PR Actions `38152808878` passed exact decoder pin, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, synthetic CLI checks, every retained synthetic contract suite and the independent fetch-summary oracle.

No fresh ares build was needed because this integration changes no reference semantic assertion: it composes the already validated exact-pin exception/fetch result with the already productionized strict PIF complete-source replay. Research instrumentation and emulator patches remain research evidence, not production dependencies.

## Adopted invariant

Production may issue a supplied-PIF source receipt for this bounded root only when all of the following hold:

- the supplied `ExceptionRootReceipt` is the validated BEV=1, EXL-clear, 32-bit-kernel **general** root at `0xffffffffbfc00380`;
- the caller selects one concrete fetch sequence inside a completely replayed v4 PIF history;
- the existing strict PIF history consumer retained exactly one singleton backing sample for that selected fetch (`observations == 1`, identical first/last fetch, identical first/last backing-read ordinal);
- that sample is the root fetch at physical `0x1fc00380`, normalized PIF offset `0x380`;
- its fetched word matches the supplied firmware bytes;
- the resulting receipt retains the selected fetch sequence, physical address, word, normalized PIF offset, backing-read ordinal, complete PIF-history SHA-256, ordered fetch/backing SHA-256 and supplied-firmware SHA-256.

The receipt verifier recomputes the complete PIF history from the original history stream, fetched-source stream, canonical ROM and supplied firmware, then rebuilds and exact-compares the receipt. It does not trust a detached report or caller-provided payload equality.

Repeated/coalesced identical observations are deliberately rejected rather than guessed. A future per-occurrence PIF report representation can relax that conservatism only while preserving exact same-fetch causal identity.

## Rejected or superseded approaches

- **Rejected:** vector address plus returned instruction value as PIF provenance. The SI-latch counterexample falsifies it.
- **Rejected:** nearest/prior/latest equal-valued PIF read. Equal payload does not identify a producer.
- **Rejected:** masked PIF offset or physical mirror equality as source identity without the active fetch witness.
- **Rejected:** treating a coalesced multi-observation `PifBackingFetchSample` as an exact fetch occurrence.
- **Rejected:** generalizing the validated general-vector result to BEV=1 TLB refill/XTLB roots, BEV=0 roots, 64-bit mode or nested EXL state without separate evidence.
- **Not adopted:** research-only ares instrumentation, workflow and model implementation. Production reuses only project-owned typed replay and the validated invariant.

## Production files changed

- `crates/plaid-core/src/exception_pif.rs` — source-bound bounded composition and receipt rechecker.
- `crates/plaid-core/src/lib.rs` — public module export.
- `crates/plaid-core/tests/bev1_pif_root_reproduction.rs` — current-production ambiguity regressions.
- `research/integration-receipts/20261011-bev1-pif-root-gpt56sol-direct-bev1-pif-root-20261011.md` — this receipt.
- Canonical `docs/STATUS.md`, `docs/NEXT.md` and `docs/DECISIONS.md` are reconciled at final integration because this adds a production evidence consumer. `progress.json` is unchanged because no milestone changes.

## Validation

Validated branch head before canonical-main reconciliation: `1460b14f8cac1fd6101b1d251a661c4984675016`.

Canonical PR Actions `38152808878`: **PASS**.

Passed gates:

- exact decoder dependency pin;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace` (includes six focused `exception_pif` unit regressions and the two current-production occurrence-ambiguity integration regressions);
- `python scripts/test_cli.py`;
- all retained synthetic CPU-copy/XORI/CPU-SP/RSP-CPU/cache/TLB/SP-DMA/RSP-store contract suites;
- independent fetch-summary assignment oracle.

The branch must be reconciled onto the latest canonical `main` and the full gate rerun if `main` has advanced before the MAIN-WRITE lease. That final reconciliation/test result is recorded in the issue #4 closeout.

## Limitations

This certificate authenticates the supplied-PIF byte source for one exact observed handler fetch in a finite, completely rechecked history. It does **not** prove:

- that an exception actually caused the selected fetch;
- that exception classification, BEV, EXL or address-mode writer chronology is complete or authentic;
- any BEV=1 TLB refill or XTLB source behavior;
- PIF firmware lifetime/authenticity beyond the supplied input digest and current read;
- cache/mapping executable lifetime around the handler;
- interrupt, watch, cache-error, reset or NMI roots;
- a complete root census, mutation census, whole-ROM closure or native completeness.

All such obligations remain OPEN. No solver or native-complete flag is weakened.

## Remaining proof obligations

1. Bind the selected root to authenticated exception-occurrence/classification and BEV/EXL/address-mode chronology.
2. Reproduce and productionize handler-byte provenance for BEV=1 refill/XTLB roots before extending this certificate beyond the general vector.
3. Compose root-byte provenance with mapping/cache residency and executable lifetime rather than treating one fetched word as a handler lifetime.
4. Establish independent interrupt/watch/cache-error/reset/NMI root obligations and a complete root census.
5. Preserve exact per-occurrence PIF backing identity if future report compression/coalescing is widened.
6. Keep hardware/reference disagreements and finite-capture limits explicit in any whole-ROM certificate.
