# Direct integration receipt: bounded maskable interrupt root gate

Date: 2026-10-11
Worker: `gpt56sol-direct-interrupt-gate-20261011`
Initial canonical base: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`
Final tested canonical base: `0e0e999b626dbda3f47cfd6aa89673618ae20350`
Integration branch: `direct-integration/interrupt-gate-gpt56sol-direct-interrupt-gate-20261011`

## Source research

- `research/interrupt-roots-gpt56sol-20261009` at `716b0dc18a8bd0427dfa7c629b1bd3d5952d0ad1`
- `research/ares-maskable-interrupt-roots.md`
- `experiments/ares-interrupt-roots-gpt56sol/`
- issue #4 research closeout `6078668009`
- exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- exact pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- exact-reference Actions `37915315945`, fresh attempt 2, job `114508552511`
- `results.json` SHA-256 `2775206efc797f614c07c36a783909c5468b55d609d93c34764c097499777eaf`
- attempt-2 artifact ZIP SHA-256 `757e474c1b9fe626df09f574e19601007d8384bdcf77d4c95146b238af912bd7`

No upstream implementation code is copied into Plaid.

## Reproduced evidence

Current production already selected numeric general/TLB exception roots from already-classified state, but had no typed maskable-interrupt eligibility boundary. The research matrix was re-read against its immutable source and rerun at the exact pinned references instead of trusting the research branch label.

The 32-case matrix covers both BEV states, all eight individually matching Cause.IP/Status.IM bits, one multi-bit match, disjoint pending/mask sets, IE clear, EXL set, ERL set, no pending bits and a zero interrupt mask. Fresh exact-pin attempt 2 passed both source guards and reproduced 18 admitted plus 14 suppressed cases. Admitted cases select only `0xffffffff80000180` (BEV=0) or `0xffffffffbfc00380` (BEV=1). This is bounded independent-reference evidence, not physical-hardware proof.

The production regression reproduces the same 32-case truth table and separately rejects the weaker rule that pending bits alone imply reachability.

## Adopted invariant

For one already-authenticated architectural boundary state, a maskable interrupt root candidate exists iff:

```text
(Cause.IP & Status.IM) != 0
&& Status.IE == 1
&& Status.EXL == 0
&& Status.ERL == 0
```

When admitted, the root is the existing BEV-sensitive general exception vector `base + 0x180`. Production reuses `resolve_exception_root(ExceptionClass::General, ...)`; it does not duplicate vector constants.

The receipt preserves the complete normalized gate input and exact `pending & mask` subset. It attaches no producer identity to those bits. `None` means only that the supplied boundary state is suppressed; it is not scope-wide evidence that the interrupt root is unreachable.

## Rejected / superseded shortcuts

The integration deliberately rejects:

- pending Cause.IP alone as handler reachability;
- Status.IM alone as reachability;
- final register equality as producer provenance;
- emulator agreement as hardware truth;
- finite injected-pending coverage as a producer census;
- root transfer as handler-byte provenance or executable lifetime proof;
- a numeric vector as a complete execution-root certificate;
- any solver/native-complete waiver.

The research workflow and emulator harness remain research evidence, not production dependencies.

## Files changed

Permanent production delta:

- `crates/plaid-core/src/interrupt_roots.rs`
- `crates/plaid-core/src/lib.rs` (one module export)
- `crates/plaid-core/tests/interrupt_roots.rs`
- this receipt

No `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` or `progress.json` change is carried. Those canonical documents already keep interrupt-root discharge open, and this bounded gate does not discharge producer causality, handler provenance/lifetime or the root census. An earlier draft documentation rewrite was detected by compare and reverted before integration.

## Reconciliation history

The branch was repeatedly rebuilt semantically on advancing canonical main rather than mechanically merging research history. It preserved, in order, independently landed `tlb_history`, `cpu_mutation`, `exception_pif`, `sp_dma_egress`, `root_provenance`, the manual-only canonical CI policy, and finally `exception_root_generation`.

Canonical parents encountered during integration included:

- initial `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`;
- TLBWI `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`;
- COP1 mutation `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`;
- BEV1 PIF root backing `9154b30b12026c8c122f654d7fe90f0f67968dce`;
- RSP IMEM egress `31c10020665e8386656fd943acab111b5c7e1671`;
- workflow-only `24689113469e0a3325601d7b6fd41b4d06ecf761`;
- NMI root provenance `60c5af29a9199ae207d487b4d791b13fb21ae708`;
- cached exception-root generation `0e0e999b626dbda3f47cfd6aa89673618ae20350`.

Two earlier main-write leases were invalidated by canonical-main drift before any write and explicitly released in issue #4. No stale lease was used to update main.

## Validation

Initial validation on `5883e4a4465bdbfc0eabc66f1262e125cf73638a` failed only rustfmt import ordering; later gates were skipped. That formatting-only failure is retained rather than hidden.

Subsequent reconciled compositions passed the full canonical gate on `bbfafdee...`, `9154b30b...`, `31c10020...`, `24689113...` and `60c5af29...`.

Final source/test tree validation is the isolated child `8d80229301d62b63b4abfc2af8f251b372616517`, whose parent is clean integration commit `54801b46776151ed12aa7c3f16ca2ec8a82aafa1` based directly on canonical `0e0e999b626dbda3f47cfd6aa89673618ae20350`. The child differs only by a branch-scoped validation workflow and never enters the production diff. Actions run `38155041825`, job `114516167606`, passed:

- exact Rabbitizer dependency pin;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- every retained spike 044-054 adversarial contract;
- independent fetch-summary assignment oracle.

The workspace log explicitly ran all three focused interrupt tests successfully:

- `pending_bits_alone_never_manufacture_reachability`;
- `receipt_retains_full_state_and_only_enabled_pending_subset`;
- `reproduces_validated_32_case_gate_matrix`.

It also passed the newly landed cached exception-root generation tests. The independent oracle reported 21,845 exhaustive histories, 20,000 randomized oracle comparisons, and semantic SHA-256 `7c7e9a402accdcb8e7d9288a946fdc5cb15d106f483fac61042f9ffc20ad5f2a`.

This receipt-only commit was made after that green run; it changes no Rust, test, canonical doc, workflow or proof logic. Final compare against the tested canonical parent must still show exactly the four permanent paths listed above before main integration.

## Limitations / remaining proof obligations

This integration does not prove:

- which interrupt producer owns a pending bit;
- producer reachability, acknowledgement or queue lifecycle;
- asynchronous visibility relative to arbitrary instructions or delay slots;
- software-IP, Count/Compare timer, MI/device or RDB producer completeness;
- watch/cache-error roots, or NMI/reset provenance beyond separately integrated evidence;
- handler-byte backing, mapping, cache residency, provenance or executable lifetime;
- refill/XTLB root backing beyond separately integrated evidence;
- whole-ROM root-set completeness;
- physical VR4300/N64 hardware timing;
- native completeness.

Unknown producer or gate chronology remains UNKNOWN and must keep whole-ROM closure OPEN wherever it matters.
