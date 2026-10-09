# CPU `SCD` to CPU-visible SP memory: completed sink width and provenance

Result: **VALIDATED** for exact pinned ares behavior.

This note answers one bounded mutation-census question: when an interpreted VR4300 `SCD` is made eligible to store and targets CPU-visible SP DMEM or IMEM, what completed storage effect actually reaches the SP bank?

## Exact revisions

- Plaid canonical baseline inspected before the claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Research branch: `research/cpu-scd-sp-sink-gpt56sol`
- Passing fixture commit: `0b3732691fc5f40d2999553fc142cfb941dd3d54`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Hypothesis

In exact pinned ares, successful interpreted `SCD` to CPU-visible SP memory reaches the RCP adapter as a `Dual` write, but the adapter commits only one 32-bit SP word containing the upper half of the architectural source. Failed conditional stores and faulting misaligned stores should produce no completed SP sink. A same-value success should still count as a fresh writer generation even though a diff-only census sees no byte change.

## Relevant exact-pin source behavior

Pinned ares `CPU::SCD` checks the current `llbit`; if set, it calls `write<Dual>(address, rt)` and writes the boolean result back to `rt`. The generic RCP `write<Dual>` path calls exactly one `writeWord(address, data >> 32, thread)`. The CPU-visible SP adapter then writes that one word to DMEM or IMEM.

There is an important read-side asymmetry: the N64 bus rejects every `Dual` read outside RDRAM before dispatching to RCP devices. `freezeDualRead()` sets `cpu.scc.sysadFrozen`. Therefore an SP-targeted `LLD` cannot be used as the reservation producer in this exact ares revision. This is not a minor harness detail: the explicit final controls show that direct `LLD` from both DMEM and IMEM loads zero, sets `llbit`, sets `sysadFrozen`, and leaves the CPU unable to execute the following synthetic guest instruction until the harness clears the frozen state.

To test the storage sink rather than conflate it with that separate read-side restriction, the final fixture uses a real decoded uncached RDRAM `LLD` solely to establish `llbit` and load the 64-bit payload, then executes decoded `SCD` against SP DMEM or IMEM. This is valid for the bounded ares sink question because this revision's `SCD` implementation tests `llbit` but does not compare the store address against the linked address. It is **not** a claim about hardware LL/SC reservation-address rules.

Pinned Gopher64 structurally disagrees on store width and reservation lifetime: its `SCD` implementation performs two `data_write` operations for the two 32-bit halves and clears `llbit`. This disagreement is retained as reference evidence, not promoted to a hardware verdict.

Pinned n64-systemtest provides adjacent hardware-facing evidence only: its SP-memory test states and checks that plain `SD` to SPMEM writes only the upper 32 bits, while its LL/SC suite checks a successful full 64-bit `SCD` to ordinary RDRAM. The guarded SP-memory module contains no direct `SCD`-to-SPMEM oracle, so the combined hardware behavior remains unproven here.

## Fixture

Spike: `spikes/046-ares-cpu-scd-sp-sink/`

Both SP banks are tested:

- DMEM at `0xffffffffa4000000`
- IMEM at `0xffffffffa4001000`

Initial SP words are:

- word 0: `0x11223344`
- word 1: `0xffffffff`

The valid RDRAM `LLD` loads `0x11223344ffffffff`. The changed-value case then executes decoded `DADDIU +1`, producing `0x1122334500000000`. This intentionally changes **both** halves if a true 64-bit store is materialized. The same-value case leaves the payload unchanged.

Before the SCD matrix, each SP bank gets a direct decoded `LLD` control. Both controls deterministically record `loaded=0`, `llbit_after=true`, and `sysad_frozen=true`, proving why the reference cannot supply a matching SP reservation for the later store test.

For each bank the SCD matrix contains:

1. no linked load, then aligned `SCD`: conditional failure control;
2. valid RDRAM `LLD`, then misaligned `SCD +1`: AddressStore fault control;
3. valid RDRAM `LLD`, `DADDIU +1`, aligned `SCD`: changed-value success;
4. valid RDRAM `LLD`, aligned `SCD`: same-value success.

An additional equal-valued `write<Dual>` is issued outside decoded `SCD` execution context. This is a provenance decoy: equal address/value alone must not be sufficient to attribute a sink to an instruction.

The instrumented build observes the completed CPU-origin SP `writeWord` sink. The baseline build has the sensor compiled out. Both use the same guest operations and exact pinned emulator source. The runner also guards the exact ares CPU/context/bus/RCP/RSP source files, exact Gopher64 SCD implementation, and the adjacent n64-systemtest source statements.

## Reproduction

With the pinned refs checked out under `.refs/`:

```sh
python3 -m py_compile spikes/046-ares-cpu-scd-sp-sink/*.py
python3 spikes/046-ares-cpu-scd-sp-sink/model.py
python3 spikes/046-ares-cpu-scd-sp-sink/run.py
```

The strict final reproduction passed in GitHub Actions run `37921610783`, job `113790612930`, at Plaid fixture commit `0b3732691fc5f40d2999553fc142cfb941dd3d54`.

## Deterministic observations

Direct SP `LLD` controls, for both DMEM and IMEM:

- loaded value: `0`
- `llbit_after`: `true`
- `sysad_frozen`: `true`
- no completed SP write sink is involved

Successful changed-value `SCD` to both DMEM and IMEM:

- source: `0x1122334500000000`
- result register after `SCD`: `1`
- exactly one completed SP Word sink
- sink value: `0x11223345`
- final adjacent word remains `0xffffffff`
- no second-word sink exists

Thus the architectural low half `0x00000000` does **not** reach the SP storage sink in exact pinned ares.

Successful same-value `SCD` to both banks:

- source: `0x11223344ffffffff`
- result register: `1`
- exactly one completed SP Word sink with value `0x11223344`
- final SP bytes are unchanged

Therefore a diff-only mutation census misses two real completed same-value writer generations in this matrix.

Controls:

- two no-reservation cases returned `0` and produced no SP sink;
- two misaligned cases raised exception code `5` with the expected bad virtual address and produced no SP sink;
- the out-of-context equal-value decoy was observed separately and was not accepted as `SCD` provenance;
- both direct SP `LLD` controls froze before RSP read dispatch, so the final fixture never silently treats them as successful reservation producers.

Verifier summary from the strict passing run:

- completed events: `5` total = four successful `SCD` sinks plus one decoy;
- successful `SCD` sinks: `4`;
- successful second-word sinks: `0`;
- truncated changed Dual payload successes: `2`;
- same-value successes missed by a diff: `2`;
- failed `SCD` without sink: `2`;
- faulting `SCD` without sink: `2`;
- explicit SP `LLD` freeze controls: `2`;
- forged histories rejected: `7`.

The verifier rejected histories that dropped a same-value success, fabricated a failed-store sink, stole the equal-value decoy, erased the decoded `SCD` opcode, erased reservation context, pretended the lower word reached the sink, or hid the direct-SP-`LLD` freeze.

Instrumentation-neutrality and determinism checks passed: baseline architectural facts and freeze controls exactly matched instrumented facts and controls, and two instrumented executions were byte-identical.

Hashes from the strict passing run:

- source-derived model SHA-256: `2d4ec0edb50baaae1b8df361c5cf97b3f42bd73681ac58c4865926e04c727442`
- observed pre-verification record SHA-256: `96db3107d5f6e836d8f4c0758c45665a6dfb81fa9c3c4a4550c11e3d60501da0`
- instrumented trace SHA-256: `36abff3d44d1a4339df0cb96aec3f98adeaffa893cdd064dbf0abe37f0378bdb`
- verified result SHA-256: `201b70c18199300f5cc2a7cacd8ad8229ad0575ed4ff00ec90bec4c48314f729`

Exact guarded source hashes are emitted by the runner and preserved in the Actions receipt, including ares bus/context/IPU/memory/RCP/RSP, Gopher64 CPU instructions, and the two n64-systemtest modules.

## Adversarial false start: backing-code rewrite is not fetched-code identity

An earlier fixture repeatedly rewrote the same physical code word between logical `LLD`, `DADDIU`, and `SCD` steps. The resulting run appeared to show zero decoded `SCD` sinks. Inspection showed that source values remained zero, no misaligned-store exception occurred, and `llbit` remained set. That was not a surprising `SCD` semantic result.

Two separate effects were exposed while debugging:

1. rewriting instruction backing alone is unsafe evidence because the I-cache may retain previously fetched instructions;
2. more importantly for the final failure, SP-targeted `LLD` itself invokes ares' non-RDRAM `Dual`-read freeze, after which `CPU::instruction()` only advances frozen time and executes no new guest instruction.

The final fixture explicitly invalidates the synthetic code-slot I-cache after each harness rewrite and uses RDRAM for the decoded reservation-producing `LLD`. The direct-SP-`LLD` freeze remains an explicit deterministic control instead of being erased from the successful path. This false start is retained because it is directly relevant to Plaid's broader rule: current backing contents and intended opcode are not evidence of the bytes actually fetched/executed, and a prior bus-side freeze can invalidate later causal assumptions.

## Result

**VALIDATED** for exact pinned ares:

A decoded `SCD` that is eligible to store and targets CPU-visible SP DMEM/IMEM produces one completed 32-bit SP Word sink containing the upper half of the 64-bit source. It does not materialize the lower 32-bit half. Failed and misaligned/faulting cases produce no SP sink. Same-value successful writes remain distinct causal writer generations despite leaving final bytes unchanged.

The exact-reference result additionally establishes that direct SP `LLD` cannot be used as the matching reservation producer in this ares revision because non-RDRAM Dual reads freeze before RSP read dispatch. That is a limitation of the reference path, not evidence that hardware behaves the same way.

## Consequence for Plaid

For executable-mutation provenance, instruction opcode width is not storage-effect width. Plaid should census the completed sink transaction and retain its causal instruction context, conditional outcome, and writer generation. Specifically, a 64-bit conditional-store opcode cannot be represented as an unconditional eight-byte mutation merely because the decoded instruction says `SCD`.

The experiment also reinforces existing architectural distinctions: equal payload is not provenance; a same-value completed write is still a new writer generation; and backing-memory modification is not equivalent to instruction-fetch identity when cache/freeze state intervenes.

## Limitations / what this does not prove

- This proves exact pinned ares behavior, not an N64-wide hardware invariant.
- No direct hardware `SCD -> SPMEM` test was found in the guarded pinned n64-systemtest SP-memory module.
- The reservation-producing `LLD` is RDRAM-backed because pinned ares freezes on any non-RDRAM `Dual` read.
- This does not establish hardware reservation-address matching, LL/SC invalidation rules, or whether hardware permits a successful `SCD` to SPMEM under a legitimate linked-load history.
- Only direct uncached CKSEG1 CPU-visible DMEM/IMEM targets are covered.
- TLB aliases, cache aliases, RSP-origin writes, DMA, COP1 stores, `SC`, `SDL`/`SDR`, timing-sensitive interactions, source-payload lineage, and executable lifetime after the write are out of scope.
- It is not executable-mutation completeness or a whole-ROM closure proof.

## Integration recommendation

**ADOPT** the mutation/provenance rule that completed sink effects, not decoded store width or final-byte diffs, define the mutation record. Preserve the ares-specific SP `SCD` width result as reference-scoped evidence. If Plaid needs to claim exact hardware `SCD -> SPMEM` semantics, **INVESTIGATE** with a direct hardware-capable n64-systemtest fixture rather than inferring the combined behavior from separate `SD -> SPMEM` and `SCD -> RDRAM` tests.
