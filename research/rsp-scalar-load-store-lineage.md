# RSP scalar DMEM load -> GPR -> store lineage

Result: **PENDING exact-pin execution**

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned behavioral reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Pinned independent source comparison: Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

## Hypothesis

For the bounded ares RSP interpreter scope, an actual scalar `LB/LBU/LH/LHU/LW/LWU` may mint a fresh GPR generation tied to the concrete DMEM source byte lanes selected by that decoded instruction. A later `SB/SH/SW` may inherit those byte origins only while replay shows that the store source GPR still carries that generation. Equal payloads are not identity. A whole-GPR writer must replace the generation even when its result is numerically identical.

## Why this matters

Existing Plaid research can record actual RSP DMEM store sinks and can establish producer lineage for SP DMA ingress. That does not yet connect bytes read by RSP scalar code through a register to a later mutation. A value match between DMEM, a GPR and a destination store would be insufficient provenance because equal values can have different causal histories.

## Reference source map

At the exact ares pin, `ares/n64/rsp/interpreter-ipu.cpp` implements scalar loads directly through `dmem.read<Byte>` or `dmem.readUnaligned<Half/Word>` and writes the result to the instruction's destination GPR. Scalar stores consume the source GPR through `dmem.write<Byte>` or `dmem.writeUnaligned<Half/Word>`. `RSP::Writable::readUnaligned` decomposes half/word reads through smaller reads, while the backing masks addresses into 4 KiB DMEM. `ORI` and `ADDU` are whole 32-bit GPR writers.

Pinned Gopher64 `src/device/rsp_su_instructions.rs` independently implements the same scalar RSP load/store families against RSP memory with 4 KiB masking and whole-GPR scalar writers. This is source corroboration only, not a second executed oracle.

## Fixture and instrumentation

`spikes/043-ares-rsp-scalar-load-store-lineage/driver.cpp` executes fourteen small actual decoded RSP programs with both recompilers disabled. The matrix includes signed/unsigned byte and half loads, word loads, unaligned wrap, the bit-12 DMEM alias, equal-valued alternate sources, a repeated same-source load, same-value `ORI`/`ADDU` clobbers, and an unrelated-register writer.

The instrumented build reuses the research-only instruction begin/end and primitive completed DMEM write callback recipe from `spikes/042-ares-rsp-dmem-history`. The fixture records pre/post values for decoded `rs/rt/rd` at the instruction boundary and primitive store sinks. It records the complete initial DMEM image before guest execution. No observer callback performs a guest access, clock step, reset, serialization or reference-state write.

`verify.py` then replays each phase in instruction order. A load source address is derived from the actual pre-instruction base GPR plus its sign-extended immediate and the exact 4 KiB addressing semantics. The reconstructed load value must equal the observed post-instruction destination GPR before a fresh register generation is minted. A store must have the exact expected primitive byte sinks before it can inherit the live source-register generation. An `ORI` or `ADDU` writing that register cuts the modeled load lineage; no preservation is guessed from equal numeric results.

## Adversarial cases

The central equal-value cases are deliberately hostile to payload matching:

1. `equal_two_loads` loads the same `0x11223344` from two different DMEM words into the same GPR before storing it. A value-based rule has two candidates; ordered register-generation replay must select the second load.
2. `same_source_reload` loads the same source twice. The ultimate bytes have the same origin, but the second load is still a fresh register generation.
3. `ori_same_value_clobber` loads `0x00001234`, overwrites the destination register with `ORI r2,r0,0x1234`, then stores it. The numeric value never distinguishes old versus new generation, so old load provenance must be cut.
4. `addu_same_value_clobber` applies `ADDU r2,r2,r0`, also preserving the numeric value. Because this bounded verifier does not claim provenance-preserving arithmetic transforms, the whole-GPR writer cuts the load generation rather than guessing.
5. `unrelated_writer` writes another GPR between load and store and must not kill the loaded register's generation.

The verifier also mutates measured histories to ensure malformed chronology, missing store sinks, wrong offsets, wrong post-load values, forged instruction identity and wrong store context are rejected.

## Neutrality obligation

The runner compares an independently compiled uninstrumented baseline, an observer-capable binary with observers disabled, an enabled sensor and an enabled repeat. Machine projections must be exactly equal across all four; enabled histories must repeat exactly; baseline and disabled histories must be empty.

## Current limitations

The load edge is reconstructed from actual decoded execution plus exact pinned load semantics, explicit pre-instruction GPR state and explicit DMEM replay state. This experiment does **not** yet add a primitive successful DMEM-read callback. It therefore should not be generalized to asynchronous memory, MMIO or an implementation where a decoded load can source bytes through a different path without further evidence.

This does not establish a complete GPR-writer census, preservation through arithmetic/logical transforms, vector-register lineage, DMA composition, scheduler/interrupt timing, debugger/save/restore/reset mutations, recompiler behavior, hardware truth, executable lifetime or whole-ROM closure.

## Reproduction

```sh
python3 spikes/043-ares-rsp-scalar-load-store-lineage/run.py
```

The runner refuses wrong or dirty ares/Gopher64 pins, builds the pinned ares interpreter, executes all neutrality variants, replays the lineage, rejects adversarial forgeries and writes `target/ares-rsp-scalar-load-store-lineage/results.json`.

Exact execution results and integration recommendation will replace this pending section after the branch-head workflow completes.
