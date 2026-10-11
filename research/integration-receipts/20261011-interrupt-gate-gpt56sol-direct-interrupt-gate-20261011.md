# Direct integration receipt: bounded maskable interrupt root gate

Date: 2026-10-11
Worker: `gpt56sol-direct-interrupt-gate-20261011`
Initial canonical base: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`
Latest reconciled canonical base: `60c5af29a9199ae207d487b4d791b13fb21ae708`
Integration branch: `direct-integration/interrupt-gate-gpt56sol-direct-interrupt-gate-20261011`

## Source research

- `research/interrupt-roots-gpt56sol-20261009` at `716b0dc18a8bd0427dfa7c629b1bd3d5952d0ad1`
- `research/ares-maskable-interrupt-roots.md`
- `experiments/ares-interrupt-roots-gpt56sol/`
- issue #4 research closeout `6078668009`
- exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- exact pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- exact-reference Actions run `37915315945`, fresh run attempt 2, job `114508552511`
- durable `results.json` SHA-256 `2775206efc797f614c07c36a783909c5468b55d609d93c34764c097499777eaf`
- attempt-2 artifact ZIP SHA-256 `757e474c1b9fe626df09f574e19601007d8384bdcf77d4c95146b238af912bd7`

No upstream implementation code is copied into Plaid.

## Current-main reproduction

Canonical main already had `exception_roots.rs`, which selects the numeric BEV-sensitive general/TLB vector from already-classified exception state. It did not have a typed maskable-interrupt eligibility primitive, so no production boundary required the validated pending/mask/IE/EXL/ERL gate before admitting the general interrupt root.

The exact research matrix was re-read against the immutable source and runner rather than trusting branch labels. Its 32 cases cover both BEV states, all eight individual matching Cause.IP/Status.IM bits, a multi-bit match, disjoint/masked pending sets, IE clear, EXL set, ERL set, no pending bits and a zero interrupt mask.

Fresh exact-pinned run attempt 2 fetched and checked ares and Gopher64 at the revisions above, passed both source-contract guards, and reproduced 18 admitted plus 14 suppressed cases byte-identically. Admitted cases select only `0xffffffff80000180` (BEV=0) or `0xffffffffbfc00380` (BEV=1). This remains bounded reference evidence, not physical-hardware proof.

The production Rust regression reproduces the same 32-case gate and preserves the exact matched pending subset. Separate controls reject the weaker rule that pending bits alone imply reachability.

## Adopted invariant

For one already-authenticated architectural boundary state, a maskable interrupt root candidate exists iff:

```text
(Cause.IP & Status.IM) != 0
&& Status.IE == 1
&& Status.EXL == 0
&& Status.ERL == 0
```

When admitted, the root is the ordinary BEV-sensitive general exception vector, `base + 0x180`. Production reuses `resolve_exception_root(ExceptionClass::General, ...)` rather than duplicating vector constants.

The receipt retains the complete normalized pending/mask/gate input and the exact `pending & mask` subset. It does not attach producer identity to those bits. Returning no receipt means only that this supplied boundary state is suppressed; it is not evidence that the interrupt root is unreachable throughout a declared execution scope.

## Rejected and superseded shortcuts

The integration deliberately does **not** adopt any of these unsound upgrades:

- pending Cause.IP by itself as handler reachability;
- Status.IM by itself as reachability;
- final register equality as interrupt-producer provenance;
- emulator agreement as physical-hardware truth;
- a finite injected-pending matrix as proof that PI/SI/SP/VI/AI/DP/timer/software producers are reachable or unreachable;
- root transfer as proof that handler bytes were fetched or have known provenance/lifetime;
- a numeric vector as a complete execution-root certificate;
- any solver or native-complete waiver.

The research workflow, emulator harness and branch-specific build scaffolding are not production dependencies.

## Production files

- `crates/plaid-core/src/interrupt_roots.rs`
- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/tests/interrupt_roots.rs`
- this receipt

No `STATUS`, `NEXT`, `DECISIONS` or `progress.json` change is carried in the final reconciled delta. The BEV1 PIF-root and NMI-root integrations already advance separate root/provenance evidence, while `docs/NEXT.md` still correctly keeps independent interrupt-root discharge open. This bounded gate does not discharge producer causality, handler provenance/lifetime or the root census, so those higher-level canonical obligations remain unchanged. An earlier draft NEXT-only annotation was dropped rather than leaving a false ADR reference.

## Reconciliation chronology

The claim began on main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.

1. TLBWI operation generations landed as `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`; the interrupt integration was rebuilt semantically on that main and preserved `tlb_history`.
2. COP1 mutation normalization landed as `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`; the integration was rebuilt again and preserved `cpu_mutation`.
3. BEV1 exact PIF root-backing provenance landed as `9154b30b12026c8c122f654d7fe90f0f67968dce`; the integration preserved `exception_pif`, `cpu_mutation` and `tlb_history`.
4. RSP IMEM egress integration landed as `31c10020665e8386656fd943acab111b5c7e1671`; the integration preserved `sp_dma_egress`.
5. Canonical main advanced to `24689113469e0a3325601d7b6fd41b4d06ecf761` solely to make `.github/workflows/rust.yml` `workflow_dispatch`-only. The integration preserved that manual-only policy. An isolated validation child based on the exact clean integration tree passed Actions run `38154409694`, job `114514293385`.
6. Source-bound NMI root provenance replay then landed as `60c5af29a9199ae207d487b4d791b13fb21ae708`, adding `root_provenance`. The current integration preserves that module and again carries only the independent maskable-interrupt gate plus this receipt.

At each reconciliation, compare output was inspected instead of mechanically merging old research history.

Two main-write leases were invalidated by canonical-main drift before any write: the first expected `9154b30b...` and observed `31c10020...`; the second expected `31c10020...` and observed the workflow-only `24689113...`. Issue #4 records explicit releases for both races. No main write occurred under either stale lease.

## Validation

Initial PR validation on head `5883e4a4465bdbfc0eabc66f1262e125cf73638a`, Actions `38152632362`, failed only `cargo fmt --all -- --check`; later gates were skipped. The exact rustfmt diff was import ordering only and was applied without semantic changes. This failure remains recorded rather than being laundered into a green result.

A reconciled head on `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` passed canonical Actions `38153217712`, job `114510781300`.

The exact `9154b30b12026c8c122f654d7fe90f0f67968dce` composition passed PR Actions `38153763585`, job `114512379732`.

The exact `31c10020665e8386656fd943acab111b5c7e1671` composition passed PR Actions `38154012459`, job `114513116912`.

The manual-only `24689113469e0a3325601d7b6fd41b4d06ecf761` composition was validated through an isolated child whose only extra file was a branch-scoped validation workflow. Actions run `38154409694`, job `114514293385`, passed:

- exact decoder dependency pin;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- all three focused `interrupt_roots` regressions;
- landed `sp_dma_egress` and `tlb_history` regressions;
- synthetic CLI checks;
- all retained CPU-copy/XORI/CPU-SP/RSP/cache/TLB/PI/SP-DMA adversarial contracts;
- the independent fetch-summary assignment oracle: 21,845 exhaustive histories and 20,000 randomized oracle comparisons, semantic SHA-256 `7c7e9a402accdcb8e7d9288a946fdc5cb15d106f483fac61042f9ffc20ad5f2a`.

The focused interrupt tests passed:

- `reproduces_validated_32_case_gate_matrix`;
- `receipt_retains_full_state_and_only_enabled_pending_subset`;
- `pending_bits_alone_never_manufacture_reachability`.

Fresh exact-reference run attempt 2 of Actions `37915315945`, job `114508552511`, independently passed exact-pin fetches, source guards, syntax checks, matrix execution and artifact hashing, reproducing 32 cases, 18 taken and 14 suppressed, with the same `results.json` SHA-256 above.

Because canonical main subsequently added `root_provenance`, the exact `60c5af29...` composition must receive the complete canonical Rust/CLI/synthetic/oracle gate before any new main-write lease is acquired. A failure blocks integration; final revalidation results may be recorded in issue #4 closeout rather than mutating this receipt again.

## Limitations and remaining proof obligations

This integration does not prove:

- which interrupt producer owns any pending bit;
- producer reachability, acknowledgement or queue lifecycle;
- exact asynchronous visibility relative to arbitrary instructions or delay slots;
- software-IP, Count/Compare timer, MI/device or RDB producer completeness;
- NMI/reset provenance beyond separately integrated evidence, or watch/cache-error roots;
- handler-byte backing, mapping, cache residency, provenance or executable lifetime;
- refill/XTLB root backing beyond separately integrated evidence;
- root-set completeness for whole-ROM scope;
- physical VR4300/N64 hardware timing;
- native completeness.

Unknown producer or gate chronology remains UNKNOWN and must keep whole-ROM closure OPEN where it matters.
