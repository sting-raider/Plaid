# RSP DMEM producer lineage through CPU copy into executable IMEM

Status: **VALIDATED** for the bounded identity-mapped interpreter composition described here.

Canonical base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`  
Validated branch code head: `0c98514e88e667909cdb26956b3d9e049908851a`  
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`  
Passing Actions run: `37920477662`  
Evidence artifact: `11611551818`, archive digest `sha256:464f42fb1f38ebc10e212fe01a906a73f5bbb56c3c1732b6bb1e5224ec401722`

## Question

Can the already-validated per-byte RSP DMEM mutation lineage be composed with the already-validated CPU SP `LW -> preserved GPR -> SW` copy witness so that executable IMEM retains the *ultimate per-byte* producer ancestry, including mixed and unknown source bytes, without using payload equality as provenance?

## Hypothesis

Yes, but only if the join is causal at each boundary. At the completed CPU SP read, capture the four latest DMEM byte generations. Bind that vector to the exact interpreted `LW` destination generation. Preserve it only while no instruction rewrites the GPR. At the interpreted `SW`, require the actual completed IMEM sink and carry the four ancestry entries to its four bytes. Storage-sink generation and source ancestry remain distinct identities.

A whole-word equality rule should fail on two adversaries: an equal-valued decoy read to another GPR immediately before the real store, and a mixed source whose four bytes have different writers.

## Existing evidence reused, not re-proved

The input boundaries were independently established by prior exact-pin work:

- `research/rsp-dmem-cpu-refetch-lineage.md`: actual scoped RSP DMEM effects are per-byte generations; same-value RSP writes advance them; CPU SP writes replace concrete bytes; out-of-context sinks cut lineage to unknown.
- `research/cpu-sp-dmem-imem-copy.md`: an actual CPU SP read can be joined through an interpreted `LW` GPR definition to a later interpreted `SW` and completed IMEM sink; equal values and CPU-thread identity alone are insufficient.

This experiment composes those boundaries in one execution rather than assuming transitivity from two separate runs.

## Exact pinned source semantics checked

At ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`:

- `ares/n64/rsp/io.cpp` routes SP-memory Word reads directly to `imem.read<Word>` when address bit `0x1000` is set, otherwise to `dmem.read<Word>`; Word writes similarly route directly to IMEM/DMEM, with IMEM writes invalidating the RSP recompiler at the written offset.
- `ares/n64/rsp/rsp.hpp` implements DMEM Byte/Half/Word/Dual storage on the backing array and decomposes unaligned writes into smaller primitive writes. This is the storage boundary patched by the existing scoped-RSP observer.
- `ares/n64/rsp/rsp.cpp` shows interpreted RSP execution fetching IMEM, running `instructionPrologue`, issuing/interpreting the decoded operation and completing the pipeline before the epilogue. The reused scoped instruction observer is therefore tied to an actual interpreted instruction window rather than inferred from a later PC/value match.
- `ares/n64/cpu/interpreter.cpp` decodes major opcode `0x23` as `LW`, `0x2b` as `SW`, and SPECIAL funct `0x21` as `ADDU`, matching the CPU instructions exercised by this fixture.

These source checks explain the instrumented boundaries; the result below comes from execution, not source reading alone.

## Fixture

The exact reference fixture performs, in order:

1. RSP scalar `SW` to DMEM word 0, then CPU `LW` and `SW` to IMEM word 0.
2. The same-value RSP `SW` again, then another CPU copy to IMEM word 1. All four ancestry generations must differ from step 1 despite identical bytes.
3. A CPU Word store establishes DMEM word 0; an out-of-context Byte write replaces byte 1; RSP vector `SBV` replaces byte 2; RSP scalar `SB` replaces byte 3.
4. CPU `LW t0,0(s0)` captures that mixed source.
5. `LW t1,4(s0)` reads a byte-identical decoy word with unrelated initial ancestry.
6. `SW t0,0x1008(s0)` must inherit the mixed source captured by `t0`, not the later equal-valued read into `t1`.
7. Same-valued `ADDU t0,t2,zero` rewrites `t0`; the following IMEM store must receive no copy certificate.
8. A direct CPU-thread IMEM write outside an executing instruction also receives no copy certificate.

The RSP producer micro-program executes from IMEM `0x100/0x104`; CPU-copy destinations are IMEM `0x000..0x010`, avoiding fixture self-overwrite.

## Independent deterministic reducer

`model.py` exercises the same ancestry rule without ares and fuzzes 5,000 word histories.

`MODEL_SHA256=a2f320b977dc79f14ef3a14ced25776b082495eb52ae8f35bc93d6a12956044d`

4,641/5,000 generated histories had mixed origin classes. For every such mixed history, the deliberately naive whole-word/value-only reducer could falsely choose a single equal-valued source. The model also requires a second same-value RSP Word to create a fresh four-generation vector and removes a certificate after a same-valued register rewrite.

The model is not a reference execution; it exists to make the intended verifier semantics falsifiable.

## Exact-pin execution

Reproduction:

```sh
python3 spikes/045-rsp-producer-cpu-imem-compose/model.py
python3 spikes/045-rsp-producer-cpu-imem-compose/run.py
```

The runner requires a clean `.refs/ares` at the pinned revision, uses the shared headless exact-reference builder with recompilers disabled, builds an uninstrumented baseline plus a sensor-capable binary, and compares:

- uninstrumented baseline;
- sensor-capable binary with callbacks disabled;
- sensor-capable binary with callbacks enabled;
- a second enabled execution.

Actions run `37920477662` passed all of those checks. The reference result ledger contains 38 ordered events, including 10 scoped primitive RSP DMEM sinks, 4 CPU SP reads, 6 CPU SP writes and 2 deliberately out-of-context/foreign DMEM sinks.

`RESULT_SHA256=c309038cbcf418fe343edcd520706a441aae38600beb301489a6beff7fbbb07c`

Final-state checkpoints, identical across baseline/disabled/enabled executions:

- RDRAM SHA-256: `1cb8a157c27dc20226afde238bb0ef07d6ffc867dc7740adbc867bee820e8f39`
- DMEM SHA-256: `6bc4311e9f9a16a7684d29ca17aa1f5207adedad406247beff0cb833ea8fb0d9`
- IMEM SHA-256: `5ccbd2ebda861a9240a49fd8fb55660d7911fcc939f8bb626e52d8255583422c`
- exception code `0`; SysAD not frozen; effective CPU count `90`.

Two enabled traces were byte-identical (`repeat_equal=true`).

### Causal certificates actually produced

Only the three intended CPU copies received certificates:

1. Phase 3, IMEM offset 0, value `0x11223344`:
   `rsp:p1:c1:o2`, `rsp:p1:c1:o3`, `rsp:p1:c1:o4`, `rsp:p1:c1:o5`.
2. Phase 6, IMEM offset 4, same value `0x11223344`:
   `rsp:p4:c11:o12`, `rsp:p4:c11:o13`, `rsp:p4:c11:o14`, `rsp:p4:c11:o15`.
   The identical payload therefore has a distinct four-byte producer generation.
3. Phase 13, IMEM offset 8, value `0xaaee7722`:
   `cpu:p7:o22`, `unknown:p8:o23`, `rsp:p9:c24:o25`, `rsp:p10:c29:o30`.
   The executable Word remains byte-wise mixed: CPU, UNKNOWN, RSP-vector, RSP-scalar.

The true mixed-source read is phase 11 into `t0`. Phase 12 performs a later equal-valued read (`0xaaee7722`) into `t1`. A value-only "latest equal read" rule therefore selects phase 12, while the causal register-generation rule correctly carries phase 11 into the phase-13 store.

The same-valued `ADDU` rewrite before phase 15 invalidates the `t0` copy certificate, and the out-of-instruction phase-16 equal-valued IMEM write also receives no certificate.

### Forged-history rejection

The replay verifier deliberately mutates the captured history and rejects all eight cases:

- `lost_same_value_rsp_context`
- `unknown_byte_wrong_offset`
- `forged_source_read_value`
- `forged_imem_bank`
- `duplicate_ordinal`
- `deleted_rsp_primitive`
- `decoy_forged_to_t0`
- `hidden_clobber_opcode`

Thus the result depends on ordered causal evidence, not merely successful payload comparison.

## Harness failures found during the experiment

Two failed runs are retained as useful negative engineering evidence:

1. Actions run `37919049705` was an **invalid false green** because `python ... | tee` lacked `pipefail`; its `exact.txt` was empty and `results.json` absent. Commit `1ef9482c72e9c02f5c083a7e8b3bb08a3dcd7abb` made the workflow fail closed and requires a non-empty result ledger.
2. Run `37919516488` then correctly failed because the initial fixture put the RSP producer at IMEM 0 while CPU-copy destinations also occupied that region; DMEM had the expected value but RSP never reached a valid `BREAK`. Commit `7a161e0bcca25250150c04186e76bc63838e6f20` moved the producer program to IMEM `0x100/0x104`.
3. Run `37919979112` got through the fixture but exposed a serializer mismatch: observer-disabled output formatted `events` over multiple lines while the parser requires one JSON record. Commit `0c98514e88e667909cdb26956b3d9e049908851a` made observer JSON single-line; run `37920477662` then passed under the fail-closed workflow.

No technical provenance conclusion is taken from the invalid/failed runs.

## Result

**VALIDATED** for this bounded path:

`latest per-byte DMEM storage generation -> completed CPU SP Word read -> exact interpreted LW register generation -> no intervening register writer -> interpreted SW -> completed executable IMEM Word sink`.

Ultimate source lineage must remain a four-byte ancestry vector. Same-value rewrites advance generation. Mixed and UNKNOWN bytes remain mixed/UNKNOWN. A later equal-valued read, a same-valued GPR rewrite, or an equal-valued out-of-instruction sink cannot replace that causal chain.

For Plaid architecture, this supports composing producer histories across copy boundaries by carrying byte-generation identities through an explicit register-generation/value-flow witness. It rejects whole-word payload equality as a provenance join rule.

## Scope and non-claims

This is a bounded identity-mapped interpreter composition. It does **not** prove:

- exhaustive RSP/CPU mutation sensing;
- every CPU load/store width or partial form;
- cached source/destination residency or delayed writeback;
- translated/TLB paths;
- asynchronous scheduler interleavings;
- DMA-to-DMEM ultimate ancestry;
- IMEM fetch/lifetime reachability after the copy;
- RSP recompiler behavior;
- physical hardware semantics;
- whole-ROM executable closure.

UNKNOWN remains an explicit provenance cut, not permission to infer the most convenient matching producer. The primary integrator should adopt the semantic rule, not merge this research branch wholesale.
