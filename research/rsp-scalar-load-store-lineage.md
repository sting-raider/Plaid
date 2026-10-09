# RSP scalar DMEM load -> GPR -> store lineage

Result: **VALIDATED** for the bounded exact-pin interpreter scope below.

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned behavioral reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Pinned independent source comparison: Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`

Passing exact-pin execution: GitHub Actions run `37921269956`, branch head `313140d0adf9931d6b0da2346b7b4adae5d1c6c6`.

Deterministic result SHA-256: `3b6e009212e209ddf81c922026e966087160ef2dac7cb6599bb804f426599e1a`.

## Hypothesis

For the bounded ares RSP interpreter scope, an actual scalar `LB/LBU/LH/LHU/LW/LWU` may mint a fresh GPR generation tied to the concrete DMEM source byte lanes selected by that decoded instruction. A later `SB/SH/SW` may inherit those byte origins only while replay shows that the store source GPR still carries that generation. Equal payloads are not identity. A whole-GPR writer must replace the generation even when its result is numerically identical.

## Result

The hypothesis is **VALIDATED for the controlled scalar fixture**, with one important scope boundary: the load edge is reconstructed from actual decoded execution, pre-instruction GPR state, explicit replayed DMEM state and exact pinned interpreter semantics rather than from a separate primitive successful-read callback.

The passing run executed 14 scenarios and recorded 138 ordered instruction/sink events. It minted 16 scalar load generations and verified 14 later store edges. The uninstrumented baseline, observer-capable binary with observers disabled, enabled sensor and enabled repeat produced identical machine projections; the two enabled histories repeated exactly. Eight independently forged histories were rejected.

The decisive adversarial observations were:

- `equal_two_loads`: two different words, `0x180..0x183` and `0x184..0x187`, both contain `0x11223344`. The store consumed load context 29, the later concrete load, and inherited `initial:184..187`. Matching payload alone cannot choose that producer.
- `same_source_reload`: the same source was loaded twice. The later load context 33 was selected as the live GPR generation even though the ultimate source bytes were unchanged.
- `ori_same_value_clobber`: `LW` produced `0x00001234`; `ORI r2,r0,0x1234` recreated exactly `0x00001234`; the subsequent store had **no inherited load producer**. Numeric equality therefore cannot preserve lineage through a new whole-GPR write.
- `addu_same_value_clobber`: `ADDU r2,r2,r0` also preserved the numeric value, but this bounded verifier cut lineage because it does not claim provenance-preserving arithmetic semantics.
- `unrelated_writer`: writing `r4` between the `r2` load and store did not kill the `r2` generation; the store still inherited load context 44 and `initial:200..203`.
- `lh_wrap`, `lw_wrap` and `bit12_alias` correctly preserved exact source lanes across the 4 KiB DMEM wrap/mask: `fff,000`; `ffe,fff,000,001`; and `000..003` respectively.
- Signed versus unsigned byte/half loads changed the full GPR value but did not change the low byte lanes consumed by same-width stores. `LB/SB`, `LBU/SB`, `LH/SH` and `LHU/SH` all retained the exact concrete source byte origins.

The verifier rejected eight forged histories covering duplicate chronology, deletion of the same-value `ORI` clobber, forged clobber instruction identity, a missing primitive `SW` sink, wrong sink offset, wrong post-load GPR value, reordered equal-value load identities and a sink moved to the wrong instruction context.

## Why this matters

Existing Plaid research can record actual RSP DMEM store sinks and can establish producer lineage for SP DMA ingress. This result fills a bounded missing causal link for scalar RSP code: a load can establish a register generation and a later scalar store can inherit the loaded byte origins only through ordered register-generation replay. A value match between DMEM, a GPR and a destination store is not enough.

For Plaid's future provenance model, the safe rule exposed by this experiment is generation-based rather than value-based:

1. a validated scalar load mints a fresh destination-GPR generation with concrete source byte lanes;
2. a scalar store may consume that lineage only if the source GPR still names that exact generation;
3. any whole-GPR writer whose provenance transform has not itself been proved replaces or kills the prior generation, even when the result is numerically identical;
4. an unrelated register write does not invalidate another register's generation;
5. a same-source reload is a fresh register generation even when ultimate byte origin is unchanged.

## Reference source map

At the exact ares pin, `ares/n64/rsp/interpreter-ipu.cpp` implements scalar loads directly through `dmem.read<Byte>` or `dmem.readUnaligned<Half/Word>` and writes the result to the instruction's destination GPR. Scalar stores consume the source GPR through `dmem.write<Byte>` or `dmem.writeUnaligned<Half/Word>`. `RSP::Writable::readUnaligned` decomposes half/word reads through smaller reads, while the backing masks addresses into 4 KiB DMEM. `ORI` and `ADDU` are whole 32-bit GPR writers.

Passing-run source guards recorded:

- `ares/n64/rsp/interpreter-ipu.cpp` SHA-256 `fa02091fd2cd5a311ab964b2fafecda944997d505af5be7a442a7cbad85ef89d`;
- `ares/n64/rsp/rsp.hpp` SHA-256 `03d72d15b7cf3cf1c50615996be2dd1918b08e9af61098c599e16871e1adbe00`;
- `ares/n64/rsp/rsp.cpp` SHA-256 `d475d3f891710750123fbde27f4064913b3d9f5e7f8a0d1ca8fc10854f489390`.

Pinned Gopher64 `src/device/rsp_su_instructions.rs` independently implements the same scalar RSP load/store families against RSP memory with 4 KiB masking and whole-GPR scalar writers. Its guarded source SHA-256 was `bfba98fd2c4fe9fb8a0d919d1c4aa5efacc707eaf80c2c7db43e080a28c09037`. This is source corroboration only; Gopher64 was **not** behaviorally executed, and implementation agreement is not promoted to hardware truth.

## Fixture and instrumentation

`spikes/043-ares-rsp-scalar-load-store-lineage/driver.cpp` executes fourteen small actual decoded RSP programs with both recompilers disabled. The matrix includes signed/unsigned byte and half loads, word loads, unaligned wrap, the bit-12 DMEM alias, equal-valued alternate sources, a repeated same-source load, same-value `ORI`/`ADDU` clobbers, and an unrelated-register writer.

The instrumented build reuses the research-only instruction begin/end and primitive completed DMEM write callback recipe from `spikes/042-ares-rsp-dmem-history`. The fixture records pre/post values for decoded `rs/rt/rd` at the instruction boundary and primitive store sinks. It records the complete initial DMEM image before guest execution. No observer callback performs a guest access, clock step, reset, serialization or reference-state write.

`verify.py` replays each phase in instruction order. A load source address is derived from the actual pre-instruction base GPR plus its sign-extended immediate and the exact 4 KiB addressing semantics. The reconstructed load value must equal the observed post-instruction destination GPR before a fresh register generation is minted. A store must have the exact expected primitive byte sinks before it can inherit the live source-register generation. `ORI` or `ADDU` writing that register cuts the modeled load lineage; no preservation is guessed from equal numeric results.

## Neutrality and failure history

Run `37921269956` passed exact reference pin checks, Python syntax, both compiled ares variants, all four neutrality executions, lineage verification and all eight adversarial forgeries.

The immediately preceding run `37920972542` failed before execution because the runner copied `driver.cpp` into `target/`, changing the base for its relative include of spike 003. Commit `313140d0adf9931d6b0da2346b7b4adae5d1c6c6` fixed only that experiment-wrapper defect by compiling a generated wrapper that includes the real fixture at its repository path. The failed run is retained in issue #4 and branch history; it is not research evidence for or against the hypothesis.

## Current limitations

The load edge is reconstructed from actual decoded execution plus exact pinned load semantics, explicit pre-instruction GPR state and explicit DMEM replay state. This experiment does **not** add a primitive successful DMEM-read callback. It therefore should not be generalized to asynchronous memory, MMIO or an implementation where a decoded load can source bytes through a different path without further evidence.

This does not establish a complete RSP GPR-writer census, preservation through arithmetic/logical transforms, vector-register lineage, DMA composition, scheduler/interrupt timing, debugger/save/restore/reset mutations, recompiler behavior, hardware truth, executable lifetime or whole-ROM closure. In particular, cutting `ADDU` is conservative: it demonstrates a safe unknown-transform policy, not that arithmetic can never preserve provenance.

## Reproduction

```sh
python3 spikes/043-ares-rsp-scalar-load-store-lineage/run.py
```

The runner refuses wrong or dirty ares/Gopher64 pins, builds the pinned ares interpreter, executes all neutrality variants, replays the lineage, rejects adversarial forgeries and writes `target/ares-rsp-scalar-load-store-lineage/results.json`.

## Integration recommendation

**ADOPT** the bounded invariant that RSP scalar register provenance is generation-based, not payload-based: successful modeled loads mint fresh GPR generations; stores inherit only the currently live generation; unproved whole-GPR writers cut it even for same-value results. Keep arithmetic/vector preservation, a complete writer census and primitive successful-read evidence as separate future obligations rather than silently generalizing this fixture.
