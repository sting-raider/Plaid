# RSP DMEM producer lineage through CPU copy into executable IMEM

Status: **IN PROGRESS** until the exact-pinned reference run recorded below succeeds.

Canonical base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`  
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Question

Can the already-validated per-byte RSP DMEM mutation lineage be composed with the already-validated CPU SP `LW -> preserved GPR -> SW` copy witness so that executable IMEM retains the *ultimate per-byte* producer ancestry, including mixed and unknown source bytes, without using payload equality as provenance?

## Hypothesis

Yes, but only if the join is causal at each boundary. At the completed CPU SP read, capture the four latest DMEM byte generations. Bind that vector to the exact interpreted `LW` destination generation. Preserve it only while no instruction rewrites the GPR. At the interpreted `SW`, require the actual completed IMEM sink and carry the four ancestry entries to its four bytes. Storage-sink generation and source ancestry remain distinct identities.

A whole-word equality rule should fail on two adversaries: an equal-valued decoy read to another GPR immediately before the real store, and a mixed source whose four bytes have different writers.

## Existing evidence reused, not re-proved

The input boundaries are independently established by prior exact-pin work:

- `research/rsp-dmem-cpu-refetch-lineage.md`: actual scoped RSP DMEM effects are per-byte generations; same-value RSP writes advance them; CPU SP writes replace concrete bytes; out-of-context sinks cut lineage to unknown.
- `research/cpu-sp-dmem-imem-copy.md`: an actual CPU SP read can be joined through an interpreted `LW` GPR definition to a later interpreted `SW` and completed IMEM sink; equal values and CPU-thread identity alone are insufficient.

This experiment composes those boundaries in one execution rather than assuming transitivity from two separate runs.

## Fixture

The exact reference fixture performs, in order:

1. RSP scalar `SW` to DMEM word 0, then CPU `LW` and `SW` to IMEM word 0.
2. The same-value RSP `SW` again, then another CPU copy to IMEM word 1. All four ancestry generations must differ from step 1 despite identical bytes.
3. A CPU Word store establishes DMEM word 0; an out-of-context Byte write replaces byte 1; RSP vector `SBV` replaces byte 2; RSP scalar `SB` replaces byte 3.
4. CPU `LW t0,0(s0)` captures that mixed source.
5. `LW t1,4(s0)` reads a byte-identical decoy word with unrelated initial ancestry.
6. `SW t0,0x1008(s0)` must inherit phase 4's mixed source, not phase 5's later equal-valued read.
7. Same-valued `ADDU t0,t2,zero` rewrites `t0`; the following IMEM store must receive no copy certificate.
8. A direct CPU-thread IMEM write outside an executing instruction also receives no copy certificate.

Expected mixed ancestry classes are exactly `CPU, UNKNOWN, RSP-vector, RSP-scalar` by byte.

## Independent deterministic reducer

`model.py` exercises the same ancestry rule without ares and fuzzes 5,000 word histories. Initial local execution passed with:

`MODEL_SHA256=a2f320b977dc79f14ef3a14ced25776b082495eb52ae8f35bc93d6a12956044d`

The second same-value RSP Word creates a different four-generation vector; mixed ancestry remains byte-distinct; a same-valued register clobber removes the certificate; and a value-only whole-word reducer selects an equal-valued decoy and falsely invents a single producer for mixed histories.

The model is not a reference execution; it exists to make the intended verifier semantics falsifiable.

## Exact-pin execution

Pending branch-only Actions execution. The runner requires exact clean ares pin, recompilers disabled by the shared headless builder, uninstrumented baseline == observer-capable/disabled == observer-enabled final state and CPU step ledger, two enabled traces byte-identical, strict replay certificates only for the three intended IMEM stores, an explicit latest-equal-value counterexample, and all forged histories rejected.

## Scope and non-claims

Even if validated, this is a bounded identity-mapped interpreter composition. It does not prove exhaustive DMEM producer sensing, every CPU load/store width, cached/TLB paths, asynchronous scheduler interleavings, DMA-to-DMEM ultimate ancestry, IMEM fetch/lifetime reachability, RSP recompiler behavior, physical hardware semantics, or whole-ROM closure. A mixed source must remain mixed; UNKNOWN is not permission to infer the most convenient matching producer.
