# Aligned first-use table snapshots

Worker `ge-closure-r2-14bd4091`; source baseline ADR0283, `83540201`.
All game inputs and generated maps remain local and ignored. No children,
commercial bytes, shared-reference refetch or bridge changes.

## Hypothesis and policy

An aligned word in a fallback ROM window is not necessarily the table that
occupies that guest address after initialization. The existing first-use repair
only requested tables with unaligned snapshot words. Aligned instruction words
could therefore become impossible target candidates and stop source refinement.

Also request a neutral data replay when pointer-table evidence for the same site
has candidates without decoded blocks or declared runtime entries. Compare the
complete PC/image/generation identity. Ignore foreign producers and foreign-site
evidence. This is bounded search policy: missing candidates do not authorize
executable entries, prove target closure or make fallback words trustworthy.

Preserve the existing unique replay address, physical slice, complete returned
bytes, aligned captured values, duplicate checks and source-preserving range
splitting. Emit only `ares_data` declarations. Composition repeats the neutral
reset replay; native data/source/table checks remain mandatory. Counterfactual
roots never provide these snapshots, and no source formula or game constant is
introduced.

## Fixed-source comparison

Both policies start from the same ADR0283 map and 222 authenticated engine pages.
Use the existing late naturally authenticated data entry, selected by the
existing replay policy. Raw executable sources remain fixed.

| Measure | Existing malformed-only repair | Aligned missing-target repair |
| --- | ---: | ---: |
| Data ranges repaired | 2 | 10 |
| Blocks | 46950 | 47161 |
| Residual blockers | 196 | 124 |
| Indirect-target blockers | 92 | 20 |
| Direct-target blockers | 37 | 37 |
| Unmapped targets | 9 | 9 |
| Unsupported slots | 42 | 42 |

The unrepaired starting map has 46512 blocks and 202 residual blockers. The
candidate's 124 comprise slots42, direct37, indirect20, unmapped9, runtime-body8,
callbacks7 and TLBWR1. Emission is still refused. No native GoldenEye executable,
VI, logo/title or completeness claim is made.

Recorded cached-replay/identify/discover/solve seconds are
0.109/6.406/41.985/4.140 before and 0.125/3.531/32.015/3.235 after. These overlap
other local validation and cover different decoded maps; they are work receipts,
not evidence of a speedup. Maps, input declarations, replay metadata, exact counts
and timing vectors are ignored under `target/ge-table-policy-before/` and
`target/ge-production-tables/`.

## Verification and remaining work

The synthetic first-use contract now reproduces the aligned missing-target case
without an invalid-word diagnostic. The retained implementation fails its
positive assertion. A private inversion of the missing-target condition is
detected. Equal PCs in different image/generation identities remain distinct;
known blocks/runtime entries, foreign producers/sites and empty candidates do
not request replay. Existing duplicate, partial/missing bytes, wrong physical
slice, unaligned captured values and conflicting-source refusals remain tested.

This changes only replay search policy. Existing native replay-data contracts
compare complete CPU/FPR/PC/HI/LO/FCSR/RAM against pinned ares and verify first-use,
post-write and missing-guard mutations. Full exact-tree gates, source/code-section
checks and visible silent controls belong under
`target/receipts/ge-table-snapshots/` before canonical integration. Default
GCC15.2 and the RT64 bridge are unchanged; no shared shim rebuild is needed.

The pinned ares9408cb43 ISC/SLJIT oracle and neutral adapter are unchanged; their
existing notices remain. No reference implementation body is copied into Plaid.
Return-certificate source boundaries, new page requests, cross-fragment slots,
runtime callbacks and native refill/Random/Wired/exception semantics are separate
obligations. An isolated return-certificate candidate and later refill probes
must not be counted in this fixed-source reduction.
