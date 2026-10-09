# Integer VR4300 `SD` into CPU-visible SP memory

Status: **VALIDATED**

Date: 2026-10-09

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/cpu-sd-sp-sink-gpt56sol`

Exact references:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Question

Does one interpreted integer VR4300 `SD` targeting CPU-visible RSP DMEM or IMEM produce an architectural eight-byte device mutation, or does the exact pinned ares RCP adapter complete only one four-byte SP Word sink?

This is deliberately separate from the already-completed RDRAM `SD`/`SDL`/`SDR` work and from contemporaneous `SDL`/`SDR`, `SCD`, `SC`, and COP1-to-SP research lanes. The relevant identity is the completed storage sink, not decoded opcode width.

## Falsifiable hypothesis

At the pinned ares revision a legal aligned integer `SD` calls `CPU::write<Dual>`, but `Memory::IO::write<Dual>` forwards only `data >> 32` into one `RSP::writeWord(address, ...)`. Therefore a successful `SD` into CPU-visible SPMEM should cause exactly one four-byte SP Word sink containing the upper 32 bits of the source GPR, not two Words/eight bytes.

A successful same-value `SD` should still produce the Word sink even if a before/after byte comparison is unchanged. Misaligned and 32-bit non-kernel reserved-instruction cases must produce no SP sink.

The hypothesis would be rejected if exact executable ares behavior produced a second Word/eight-byte effect, omitted same-value writes from the sink history, or emitted an SP sink after either fault control.

## Source-derived baseline

Exact pinned ares:

- `ares/n64/cpu/interpreter-ipu.cpp`: `CPU::SD` rejects 32-bit non-kernel context then calls `write<Dual>(rs.u64 + imm, rt.u64)`.
- `ares/n64/memory/io.hpp`: generic RCP `write<Dual>` calls `writeWord(address, data >> 32, thread)` exactly once and does not issue an `address + 4` Word.
- `ares/n64/rsp/io.cpp`: CPU-visible SP writes route through `RSP::writeWord` into DMEM or IMEM.

Exact pinned Gopher64 disagrees structurally: its integer `sd` function performs two `device::memory::data_write` calls, including a second write at `phys_address + 4`, and the SP address map routes those writes to `rsp_interface::write_mem`.

Exact pinned n64-systemtest supplies a hardware-facing test expectation for this exact quirk. `src/tests/sp_memory/mod.rs` states that SPMEM `SD` writes only the upper 32 bits and touches only four bytes. Its `spmem: SD` test writes `0xABCDEF98_76543210`, expects the first Word to become `0xABCDEF98`, and expects the following Word to remain at its preset `0xBADDECAF`. This worker did **not** execute that ROM on physical hardware; this is pinned test-source evidence, not a fresh hardware measurement.

## Instrumentation and fixture

The executable fixture is under `spikes/043-ares-cpu-sd-sp-sink-gpt56sol/`.

`driver.cpp` runs exact pinned ares with the CPU/RSP recompilers disabled and uses the already-established project-owned SP Word observer shadow at the `RSP::writeWord` device boundary. The source GPR is fixed at `0x1122334455667788`, so the expected device sink payload is `0x11223344`.

The matrix covers:

- DMEM and IMEM;
- aligned offsets `0` and `8` for successful cases;
- changed-value successful stores;
- same-value successful stores with the target Word pre-seeded to the sink payload;
- misaligned `SD` using offset `4`;
- 32-bit user-mode reserved-instruction execution.

Every observer-enabled case is paired with an observer-disabled case. All architectural/storage state fields except the observer/sink record must match. Every executable process is also invoked twice and the JSON output must be identical.

`model.py` and the replay logic in `run.py` adversarially reject five forged histories:

1. decoded/executed `SD` with no completed SP sink;
2. a sink carrying the lower 32 bits instead of the upper 32 bits;
3. an invented second Word pretending SPMEM received all eight architectural store bytes;
4. a value-matching sink attributed to the wrong SP bank;
5. a fabricated SP sink attached to a faulting execution.

## First executable run: useful verifier failure

GitHub Actions run `37920361965`, job `113786548601`, passed exact reference checkout, Python compilation, and the ares/Gopher source-topology guard, then failed the executable verifier.

The failure was **not** a sink-width contradiction. For a DMEM `SD` of `0x1122334455667788`, the observer recorded exactly one sink:

```text
address = 0x04000000
bank = DMEM
offset = 0
value = 0x11223344
cpu = true
```

The helper `read<Word>` view of the backing storage returned numeric `0x44332211`, while its byte view was `44 33 22 11`. The initial verifier incorrectly required the helper Word presentation to numerically equal the causal sink payload. Commit `49c922d20eea651b2ec93d7c80588a616d01aa06` removed that assumption: the device-boundary sink is the payload oracle; helper reads are used only to establish footprint/change or no-change.

This failure is itself useful provenance evidence: a backing/helper presentation is not interchangeable with the value carried by the completed storage transaction.

## Successful exact-pin runs

### Corrected ares matrix

Run `37920587300`, job `113787276174`, at Plaid branch commit `49c922d20eea651b2ec93d7c80588a616d01aa06` passed:

```text
PASS: same-value sink retained; five forged histories rejected
PASS: 24 enabled/disabled exact-pin integer SD-to-SP observations; every process repeated
same_value_diff_rule_accepts=false
same_value_sink_rule_accepts=true
forged_histories_rejected=5
results_sha256=93ede941002cb35a39eb3c805dc0c48957ef0a2def5b8bb85fc99f69dabd0df1
```

### Three-reference run

Run `37920751474`, job `113787810010`, at branch commit `4fb10fed8bf561d5f07adc0d68222931f583f8f9` additionally checked out and guarded exact pinned n64-systemtest. It passed source guards, the standalone adversarial model, and the full exact ares executable matrix.

Cross-reference output:

```text
{"ares_rcp_dual_second_word":false,"ares_rcp_dual_writeword_calls":1,"ares_revision":"9408cb43d4948fc3ea6e152a307a34348df3fe04","ares_sd_dual_calls":1,"gopher_revision":"e96debac941a26ba4961e5145056c0821d3a56f7","gopher_sd_data_write_calls":2,"gopher_sd_second_address":true,"gopher_sp_map_to_rsp_write_mem":true,"systemtest_revision":"196f5421173220eb2f63a7a99c64795dc0ea0698","systemtest_sd_next_word_preserved":true,"systemtest_sd_upper_word_expected":true}
crosscheck_sha256=8a97b12c40be533cd1aa41d543a3bd2693b3c7472f28e748366f72d938998f38
PASS: ares one-Word SD matches pinned n64-systemtest expectation; pinned Gopher64 disagrees
```

The executable matrix reproduced the same deterministic result hash:

```text
PASS: 24 enabled/disabled exact-pin integer SD-to-SP observations; every process repeated
same_value_diff_rule_accepts=false
same_value_sink_rule_accepts=true
forged_histories_rejected=5
results_sha256=93ede941002cb35a39eb3c805dc0c48957ef0a2def5b8bb85fc99f69dabd0df1
```

## Deterministic observations

Within the declared fixture scope:

1. Legal aligned integer `SD` into both CPU-visible DMEM and IMEM emits exactly **one** observed `RSP::writeWord` sink.
2. That sink carries the **upper 32 bits** of the source GPR (`0x11223344`).
3. No second Word sink at `address + 4` is emitted; the following SP Word remains unchanged.
4. The same-value successful case still emits the same completed Word sink even though before/after byte comparison reports zero changed bytes.
5. Misaligned `SD` raises Address Error Store (`exception=5`) and emits no SP sink.
6. A 32-bit user-mode `SD` raises Reserved Instruction (`exception=10`) before the memory operation and emits no SP sink.
7. Enabling the observer does not change the compared architectural/storage result in this scope.
8. Repeated processes are deterministic; the final serialized result hash is stable across the two successful workflow runs.
9. Exact pinned n64-systemtest independently expects the same one-upper-Word SPMEM effect.
10. Exact pinned Gopher64 disagrees and models integer `sd` as two Word writes. Emulator agreement must therefore not be used as the proof criterion here.

## Result

**VALIDATED** for the declared scope.

For exact pinned ares interpreted integer VR4300 `SD` into CPU-visible RSP DMEM/IMEM, the actual device sink is one 32-bit Word containing the upper half of the source GPR. Same-value successful stores remain causally meaningful writers even when a byte-difference census sees no mutation. The fault controls emit no SP sink.

The exact pinned n64-systemtest source expectation corroborates the one-Word upper-half behavior as an intended N64 SPMEM quirk. Exact pinned Gopher64 conflicts with that evidence and should not be used as the oracle for this semantic without separate investigation.

## Integration recommendation

**ADOPT** the semantic result into Plaid's executable-mutation model for CPU integer `SD` targeting SPMEM:

- model the completed effect from the storage sink, not the opcode's architectural width;
- mint/retain a writer generation for successful same-value stores;
- do not synthesize a lower-half/second-Word mutation merely because `SD` is architecturally 64-bit;
- suppress the sink on faulting executions;
- preserve the exact reference/source evidence and the Gopher64 disagreement as provenance on the rule.

The primary integrator should reproduce or inspect the branch evidence before changing canonical mutation-census code.

## Limitations and explicit non-proofs

This experiment does **not** prove:

- that every RCP device treats `Dual` accesses identically;
- all virtual/TLB/alias paths into SPMEM;
- every alignment/address-wrap edge case;
- `SDL`, `SDR`, `SCD`, `SC`, COP1 stores, or RSP-originated writes;
- cache-mediated CPU stores into ordinary RDRAM;
- producer lineage of the source GPR bytes;
- executable lifetime effects after the SP Word is written;
- that the pinned n64-systemtest expectation was freshly confirmed on physical hardware in this session;
- that Gopher64's disagreement is a general emulator defect rather than a localized semantic mismatch;
- whole-program mutation completeness or closed-world execution.

## Reproduction

The workflow performs the exact reference checkouts automatically. Equivalent local commands, after placing the exact pins under `.refs/ares`, `.refs/gopher64`, and `.refs/n64-systemtest`, are:

```sh
git checkout research/cpu-sd-sp-sink-gpt56sol
python3 -m py_compile \
  spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py \
  spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py \
  spikes/043-ares-cpu-sd-sp-sink-gpt56sol/model.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/model.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py
```

Generated build/results remain under ignored `target/ares-cpu-sd-sp-sink-gpt56sol/`; no ROMs or generated traces are committed.
