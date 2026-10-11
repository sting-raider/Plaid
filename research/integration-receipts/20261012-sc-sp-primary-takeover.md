# Primary takeover: completed SC -> SP normalization

Base: 524ea197b1642e59ac9e959956402ab3894b2ae2.
Prepared PR #43 head: 9bd0d860530e45c9e746099a7f5860f2e7084881.
Source: research/cpu-sc-sp-sink-gpt56sol at
47db2b2baa9a640111085b68a722fe316ed5e43e; closeout 6079357267.
Duplicate writer candidate 82b2723 is review evidence, not a second integration.

Hypothesis: completed CPU-origin Word sinks bound to exact decoded pre-SC
context can be normalized without predicting reservation semantics. Matching
bits do not erase successful writes or grant provenance to unrelated sinks.

Keep the prepared effect-driven API and nine regressions. Reuse canonical
llsc_mutation's decoder, excluding SCD. Primary deterministic regressions fail
against the prepared module for nonzero architectural GPR zero and matching
unaligned PC, then pass after guards. Require the effect to follow its context
in the same externally authenticated event namespace. Verify direct KSEG1
physical mapping, SP window/bank/offset, alignment and low pre-store source Word.
Absent effects yield no witness without claiming a complete absence census.

Reuse historical final-head artifact 11610989658, authenticated ZIP SHA-256
8a01891d61f738c52c1ab3f92e998c24a722eb25c117f476c474f90694cecde8.
Saved results SHA-256:
454ea55a300bee86480f55d6152cdd2970495e60121eb0b93e3d8a8ff0f4e6d2.
Retained verifier and five forged-history rejections pass locally. All eight
saved cases agree with the production API: four completed sinks, two reservation
failures without sink and two faulting attempts without sink. Two same-value
successes remain writers; an unrelated equal-value direct write remains a decoy.

The local adapter derives base/GPR values for the controlled driver and assigns
synthetic shared context/effect ordinals. It does not claim these were sensed
instruction boundaries or that the saved sink-only trace supplies a full event
census. Historical baseline/instrumented state digests and repeat equality are
supporting evidence, not a new full-state hardware comparison.

Clean exact ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 and Gopher64
e96debac941a26ba4961e5145056c0821d3a56f7 source checks match the saved LF bytes.
Reviewed CPU SC, RCP Word and RSP storage dispatch plus Gopher conditional store.
Gopher clears the reservation differently; no hardware reservation policy is
inferred. No upstream code copied, reference rebuild, Actions dispatch, branch
workflow or raw research merge. SCD and broader aliases remain excluded.

Final required local gate: fmt check, strict locked workspace all-target Clippy,
locked full workspace tests (including the actual fixed-point deletion adversary),
CLI tests and diff check. Exact-head refetch/CAS force=false required to publish.
Logs and saved evidence: target/sc-sp-primary (ignored).

Operand ancestry, event source authentication/completeness, reservation lifetime,
mutation census, downstream executable visibility/lifetime and whole-ROM/native
completeness remain OPEN. Progress map and solver gates unchanged (ADR-0111).

Outcome: all eleven focused regressions, saved-capture checks and required
fmt/strict Clippy/full workspace/CLI gates PASS on the exact base. Supersede
prepared PR #43 and both duplicate direct-integration writer branches; source
research remains evidence. Preserve raw research scaffolding outside production.
