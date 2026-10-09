# CPU SP producer instruction/source context

Date: 2026-10-09

Status: **VALIDATED** for the controlled pinned-ares interpreter scope described below.

Worker: `gpt56sol-cpu-sp-producer-context-20261009`

## Result

For the three CPU store families present in the existing bounded boot SP-producer
inventory (`SW`, `SB`, `SWC1`), a concrete CPU-originated SP `writeWord` effect can
be joined to the exact currently executing decoded instruction plus the immediate
register-level source context without using nearest-same-PC matching or payload
equality.

The exact-reference fixture passed on pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` with both recompilers disabled.
Successful Actions receipt:

- workflow run `37915925049`, job `113771954343`;
- tested commit `971fd59dfaa693acaad7cccce03a8fc8b0ae88b0`;
- trace SHA-256 `2f00b296fef961db9bd76792912e4e7fd60ae7e293555a3d2c448be37b8b619f`;
- deterministic `results.json` SHA-256
  `f41331e4cbf7590c8b598c2385e573da49296f963da8fd0b5635f6bc83b7d725`;
- uploaded artifact ZIP digest
  `2f3f0f27dcbaa209e8e7d77d514c3e87e0c564851f31ad84c313fe2dcc916321`.

Pinned source guards in that run hashed:

- `cpu.cpp`: `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1`;
- `interpreter-ipu.cpp`: `495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152`;
- `interpreter-fpu.cpp`: `ba90518438cad45e7d4cf18b297e272f186f5e38d0ef354fdc59adb13a949676`;
- `memory/io.hpp`: `54089251052dbffddf7ae77819c3a3bb494cf7269ae874a3015a23907370a69c`;
- `rsp/io.cpp`: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`.

## Question

The bounded boot producer inventory in `research/sp-producer-sites.md` currently
normalizes CPU SP writes and classifies the fetched same-PC instruction. Can those
actual sinks instead be tied directly to the decoded CPU execution context and its
immediate source operand, so repeated PCs/values never become causal identity?

## Exact sources inspected

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

- `ares/n64/cpu/cpu.cpp`: interpreter `CPU::instruction()` performs the successful
  fetch, `pipeline.begin()`, `instructionPrologue(ipu.pc, instruction)`,
  `decoderEXECUTE(instruction)`, `instructionEpilogue<0>()`, and `pipeline.end()`
  synchronously.
- `ares/n64/cpu/interpreter-ipu.cpp`: `SW` passes `rt.u32` to `write<Word>`;
  `SB` passes the full `rt.u32` to `write<Byte>`.
- `ares/n64/cpu/interpreter-fpu.cpp`: `SWC1` gates CU1, then stores `FT(u32)`.
- `ares/n64/memory/io.hpp`: the RCP subword adapter shifts the unmasked incoming
  value before the common Word sink.
- `ares/n64/rsp/io.cpp`: SP-memory Word writes select DMEM/IMEM and replace the
  concrete Word backing.

Existing Plaid evidence used read-only:

- `research/sp-producer-sites.md`: the bounded prefix contains 51,991 `SW`, 2,256
  `SB`, and six `SWC1` normalized CPU SP effects, but the same-PC association is
  explicitly not a retirement/source-dataflow proof.
- `research/cpu-rsp-imem-subword.md`: CPU `SB`/`SH` SPMEM effects normalize at the
  full Word sink and may contain source bytes above the nominal ISA width.
- `research/ares-cop1-store-mutation.md`: `SWC1` source selection is FR-sensitive;
  FR=0 odd selects the paired even FPR high 32 bits, while FR=1 selects the named
  FPR low 32 bits.

## Executed experiment

`spikes/043-ares-cpu-sp-producer-context/` executes real encoded instructions
through `CPU::instruction()` and uses the existing research SP-backing callback at
`RSP::writeWord`. The fixture-owned producer context is active only for the
synchronous instruction call and is cleared before later synchronization.

The passing trace contains seven CPU-originated SP Word effects:

1. phase 1: `SW` at `0xffffffffa0006000` writes `0x55667788`;
2. phase 2: the exact same PC/instruction/address/value `SW` writes `0x55667788`
   again but receives a distinct event ordinal/generation;
3. context 0: direct `cpu.write<Word>` writes the exact same address/value
   `0x55667788` outside decoded execution and remains unattributed;
4. phase 3: `SB +1` produces the concrete widened SP Word sink `0x77880000`;
5. phase 4: FR=0, `SWC1 ft=0` produces `0x55667788`;
6. phase 5: FR=0, `SWC1 ft=1` produces paired-even high half `0x11223344`;
7. phase 6: FR=1, `SWC1 ft=1` produces named-FPR low half `0xddeeff00`.

Phase 7 executes CU1-disabled `SWC1`; it reports exception code 11 with
coprocessor-error 1 and produces no SP sink. The independent Python verifier
re-decodes every attributed instruction and recomputes its register-level payload.
It therefore rejects a join based only on PC, destination, or equal value.

The final first 16 IMEM bytes are deterministically
`77 88 00 00 55 66 77 88 11 22 33 44 dd ee ff 00`.

## Neutrality and determinism

The runner executes the same sensor-capable binary with the SP observer disabled,
enabled, and enabled again. A passing run requires:

- observer-disabled events to be empty;
- disabled/enabled/repeat architectural facts to match exactly;
- disabled/enabled/repeat exception outcomes to match exactly;
- the two enabled JSON traces to be byte-identical.

All checks passed in run `37915925049`.

The first build attempts failed before execution because the fixture named its
local record type `Event`, colliding with ares' imported `Event` type. Renaming it
`ProducerEvent` was the only code correction before the passing exact-reference
run; no semantic assertion was weakened.

## Interpretation

**Validated:** in this pinned interpreter scope, the actual SP sink can carry an
immediate producer witness consisting of exact decoded instruction generation,
PC/instruction word, source-register selector/mode, pre-store source snapshot, and
concrete post-RCP Word sink. Same PC/value is not identity. Failed/faulting stores
must not manufacture a sink witness, and out-of-instruction writes must not inherit
an instruction context.

For a production provenance design, use an explicit execution-generation/context
identity that is scoped to the decoded instruction and join it to the concrete
storage effect. Do not recover producer identity later by scanning for a matching
fetch, matching PC, or matching payload.

## Limitations and explicit non-proofs

This result does **not** prove:

- ultimate byte origin of the source GPR/FPR; earlier loads, arithmetic, copies,
  decompression, relocations, and transformations still need their own lineage;
- that every CPU store family is covered; only the three families observed in the
  bounded CPU->SP producer inventory are exercised here;
- recompiler/JIT instrumentation equivalence; the tested execution mode is the
  pinned ares interpreter with recompilers disabled;
- arbitrary asynchronous/reentrant producer lifetime beyond the synchronous store
  path used here;
- RSP/DMA producer provenance, D-cache delayed writeback provenance, overlay
  lifetime, executable closure, or native-complete proof;
- an N64-wide hardware invariant from one emulator.

The active RSP-DMEM-to-later-CPU-refetch work is a separate composition problem and
was intentionally not duplicated.

## Reproduction

```sh
python3 -m py_compile spikes/043-ares-cpu-sp-producer-context/*.py
python3 spikes/043-ares-cpu-sp-producer-context/run.py
```

The runner requires exact pinned ares under `.refs/ares`, source-guards the paths
listed above, builds the headless exact-reference fixture, executes the adversarial
sequence, performs neutrality/repeat checks, and writes the hashed result artifact.

## Recommendation

**ADOPT** the producer-context contract for future CPU->SP provenance integration:
assign explicit decoded-execution identity before the store, join it synchronously
to the concrete SP Word sink, record the ISA-correct immediate source selector,
and leave ultimate register dataflow as a separate provenance layer. Do not treat
the existing same-PC boot classification as causal proof.
