# Exact ares adjacent CPU-copy dataflow

Date: 2026-10-09

Result: **VALIDATED** for the deliberately narrow adjacent interpreted uncached word-copy certificate described below.

Integration recommendation: **ADOPT** the evidence contract and conservative certificate shape as a bounded provenance building block. Do **not** treat it as general CPU-copy closure or general register dataflow.

## Question

Can the already-validated completed identity-RDRAM transaction witness be joined to actual VR4300 instruction/register execution strongly enough to prove a causal byte-origin link for an adjacent `LW/LWU rt -> SW rt`, rather than merely observing equal source/destination values?

## Exact versions

Plaid canonical base inspected before the claim:

`ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Experiment branch:

`research/ares-cpu-copy-dataflow-gpt56sol`

Successful experiment source commit:

`c1d57fd0d2e028feaf9fe0a9962ed6f6497091bf`

Pinned upstream ares revision from `refs.lock.toml`:

`9408cb43d4948fc3ea6e152a307a34348df3fe04`

Successful GitHub Actions run:

`37915748860`

Result artifact:

- name: `ares-cpu-copy-dataflow-results`
- artifact id: `11608833877`
- artifact ZIP SHA-256: `8152bec09c6ed2141e024da4e9351b75454ab4c99e83bf70ef4df72485f651eb`
- `results.json` SHA-256: `0a10e68ebe27bac70cf6d3d2233f1ee2eab0e67caa50e9e7f49b118e948d9b2e`

Two earlier CI attempts failed before the semantic fixture executed: run `37915286989` hit the shared builder's required physical-fetch option guard, and run `37915519360` exposed an instrumentation-composition guard because the shared builder had already relocated the CPU TU. Both were fixed explicitly; neither produced a semantic result. The successful run composes against the builder-generated CPU/header shadows instead of replacing them.

## Hypothesis

With the CPU recompiler disabled, an ordered history containing:

1. the exact fetched interpreted instruction word;
2. GPR state immediately before and after that instruction;
3. the completed identity-mapped uncached RDRAM transaction occurring inside that instruction; and
4. the immediately following exact `SW` instruction and its completed backing write

is sufficient to certify a narrow `LW/LWU rt -> SW rt` copy when the load's completed read matches the effective address, the load produces the architectural sign/zero-extended GPR result, and the store reads that same GPR.

Matching values, guest PCs without instruction identity, or later/current RAM contents are not sufficient.

## Reference behavior inspected

At the exact ares pin, `ares/n64/cpu/cpu.cpp::CPU::instruction()` performs a successful fetch, begins the pipeline, calls `instructionPrologue(ipu.pc, *data)`, executes `decoderEXECUTE(*data)`, calls `instructionEpilogue<0>()`, then ends the pipeline. This gives a real interpreter execution boundary around the instruction rather than a guessed PC/value join.

At the same pin, `CPU::LW` only assigns its destination GPR if `read<Word>` succeeds. The shared Plaid ares builder's identity-RDRAM observer is placed after the actual successful backing read/write. The experiment therefore joins completed storage effects to exact instruction execution, not request creation or decoded opcode names alone.

## Instrumentation

`spikes/043-ares-cpu-copy-dataflow-gpt56sol/prepare.py` composes a project-owned `PlaidCpuInstructionObserver` with the shared generated CPU shadow. It emits no reference-object fields. The callback fires:

- after `instructionPrologue` and before `decoderEXECUTE` for instruction begin;
- after `instructionEpilogue<0>` and before `pipeline.end()` for instruction end.

`observer.hpp` snapshots all 32 GPRs at both boundaries. Completed scalar RDRAM effects use the existing project-owned generated scalar observer. Both event families share one monotonic ordinal and the RDRAM event carries the active instruction context.

The source guard requires the generated unity TU to include exactly the CPU shadow that has both physical-fetch support and the instruction observer. The upstream checkout itself is required at the exact pin and clean.

## Fixture

All code/data are synthetic. ares CPU and RSP recompilers are disabled. RDRAM uses the controlled identity mapping. Guest data operations use KSEG1 so successful word loads/stores terminate in scalar RDRAM transactions rather than D-cache residency.

Six phases execute actual VR4300 instructions:

1. **Positive LW**: `LW t0,0(s0); SW t0,0(s1)`, source `0x1000 = 0x89abcdef`, destination `0x2000`.
2. **Positive LWU**: `LWU t0,0(s0); SW t0,0(s1)`, same source, destination `0x2004`.
3. **Equal-value decoy**: `LW t0,[0x1000]; LW t1,[0x1100]; SW t0,[0x2008]`, with both sources containing `0x89abcdef`.
4. **Equal-value clobber**: source `0x1000 = 0x00001234`; `LW t0,[source]; ORI t0,zero,0x1234; SW t0,[0x200c]`.
5. **Conservative gap**: `LW t0,[source]; NOP; SW t0,[0x2010]`.
6. **Failed load**: misaligned `LW t0,1(s0)` with `t0 = 0xfeedface` before execution.

The replay verifier decodes the captured instruction word, recomputes the effective physical backing address from the captured pre-instruction GPR state, checks the one successful uncached Word transaction, checks `LW` sign extension or `LWU` zero extension, and verifies the following `SW` source register/value/write. It emits a certificate only when the successful load is the immediately previous instruction in the same phase.

## Exact command

From a checkout with `.refs/ares` at the pinned revision:

```sh
python3 spikes/043-ares-cpu-copy-dataflow-gpt56sol/run.py
```

The branch-only workflow `.github/workflows/research-ares-cpu-copy-dataflow.yml` performs the exact checkout and command on Ubuntu 24.04.

## Deterministic observations

The successful run emitted exactly two certificates:

```text
phase 1: LW  source 0x1000 -> destination 0x2000, value 0x89abcdef
phase 2: LWU source 0x1000 -> destination 0x2004, value 0x89abcdef
```

Their event contexts were:

```text
phase 1 load_context=1  store_context=4
phase 2 load_context=7  store_context=10
```

The complete per-phase storage effects were:

```text
phase 1: read  0x1000 = 0x89abcdef; write 0x2000 = 0x89abcdef
phase 2: read  0x1000 = 0x89abcdef; write 0x2004 = 0x89abcdef
phase 3: read  0x1000 = 0x89abcdef; read 0x1100 = 0x89abcdef; write 0x2008 = 0x89abcdef
phase 4: read  0x1000 = 0x00001234; write 0x200c = 0x00001234
phase 5: read  0x1000 = 0x89abcdef; write 0x2010 = 0x89abcdef
phase 6: no scalar RDRAM transaction
```

Architectural checks also observed:

- phase-1 `LW` produced `t0 = 0xffffffff89abcdef`;
- phase-2 `LWU` produced `t0 = 0x0000000089abcdef`;
- the failed misaligned load left `t0 = 0xfeedface` and produced exception code `4`;
- final RDRAM SHA-256 was `cfa5218b0a2a7e1bed9cd262db73a0e7d9c15210cbcab7eada7494e72f7ea1bc`;
- the captured history contained 28 instruction-boundary events and 11 scalar RDRAM events.

## Counterexamples and adversarial checks

### Equal-value source selection is concretely wrong

A deliberately naive nearest-prior-equal-value reducer selected these source/destination pairs:

```text
phase 1: 0x1000 -> 0x2000
phase 2: 0x1000 -> 0x2004
phase 3: 0x1100 -> 0x2008   # WRONG: SW reads t0 from the first load
phase 4: 0x1000 -> 0x200c   # bits match despite ORI replacing the causal writer
phase 5: 0x1000 -> 0x2010   # outside the deliberately adjacent certificate
```

Phase 3 is the direct falsifier: both reads have identical payloads, but only the first load writes `t0`; nearest value matching chooses `0x1100`, whose load writes `t1` instead.

### Equal final bits do not preserve the load's causal writer

Phase 4 loads `0x1234`, then `ORI t0,zero,0x1234` overwrites `t0` with identical bits before the store. The narrow verifier refuses this chain because the immediately preceding instruction is not the successful load. A value-only rule would silently claim false provenance.

### A safe-looking gap is still outside this proof

Phase 5 inserts a NOP. The bytes do remain unchanged in this synthetic case, but this verifier intentionally emits no certificate. Extending beyond adjacency requires a real def-use/control-flow/exception proof rather than widening the rule because one NOP happened to be harmless.

### Failed load cannot be upgraded from opcode/address intent

Phase 6 decodes an `LW` but its address is misaligned. It raises AddressLoad, performs no completed scalar RDRAM read, and leaves `t0` unchanged. Therefore opcode plus effective address intent is not a storage-origin witness.

### Forged histories fail closed

The runner mutates the successful trace three ways and requires the replay verifier to reject each:

1. change the load's claimed backing address;
2. change the captured `SW` source register while preserving the backing write;
3. fabricate a successful scalar read inside the failed misaligned load.

All three forged histories were rejected in the successful run.

## Instrumentation neutrality and repeatability

The runner builds and executes:

1. an unmodified-reference baseline fixture;
2. the generated observer build with callbacks disabled;
3. the generated observer build with callbacks enabled;
4. a repeated enabled run.

Baseline, disabled and enabled runs had identical **reported fixture facts and reported final state**. The enabled trace repeated byte-for-byte. This neutrality check covers the fixture's destination words, selected GPR outcomes, final exception, PC/count and whole-RDRAM hash. It is not a complete equality proof over every CPU/COP0/FPU/cache/queue field.

Successful run output:

```text
PASS three forged transaction/instruction histories rejected
RESULT_SHA256=0a10e68ebe27bac70cf6d3d2233f1ee2eab0e67caa50e9e7f49b118e948d9b2e
PASS exact interpreted adjacent LW/LWU->SW dataflow; equal-value decoy/clobber/gap and failed load stay uncertified
```

## Result

**VALIDATED:** for this controlled interpreted identity-mapped KSEG1 scope, exact instruction begin/end GPR history plus the completed scalar backing transactions is sufficient to certify an adjacent `LW/LWU rt -> SW rt` causal copy without relying on value uniqueness. The experiment also gives a concrete equal-value counterexample to value-based source attribution.

This advances the earlier transaction-only CPU-copy evidence by supplying the missing actual-reference instruction/dataflow correlation for the smallest useful certificate.

## Limitations / explicitly not proved

This does **not** prove:

- general register last-writer/dataflow across arbitrary intervening instructions;
- branches, jumps, delay slots, calls/returns, joins, loops, interrupts or exceptions between a successful load and store;
- byte, halfword, dualword, `LWL/LWR/LDL/LDR` or other merge/partial families;
- transformations, decompression, relocation or instruction patching;
- cached source/destination residency or D-cache lineage (covered by separate partial evidence, not this certificate);
- TLB-mapped/remapped/degraded RDRAM or address-error variants beyond the failed-load negative;
- recompiler/JIT execution identity;
- executable lifetime/generation or eventual instruction-fetch consumption of the copied destination;
- exhaustive discovery of all CPU copy implementations;
- hardware truth beyond this exact pinned ares behavioral oracle.

## Recommendation: ADOPT

Adopt the narrow certificate as a provenance primitive only when the captured evidence proves the exact instruction word, pre/post GPR state, completed backing read/write and immediate adjacency. Keep non-adjacent or transformed chains unknown until Plaid has a real register-def/use and control/exception model. Never substitute matching values for that causal history.
