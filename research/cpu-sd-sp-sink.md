# Integer VR4300 `SD` into CPU-visible SP memory

Status: **IN PROGRESS**

Date: 2026-10-09

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Research branch: `research/cpu-sd-sp-sink-gpt56sol`

Exact references:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`

## Question

Does one interpreted integer VR4300 `SD` targeting CPU-visible RSP DMEM or IMEM produce an architectural eight-byte device mutation, or does the exact pinned ares RCP adapter complete only one four-byte SP Word sink?

This is deliberately separate from the already-completed RDRAM `SD`/`SDL`/`SDR` work and from active `SDL`/`SDR`, `SCD`, `SC`, and COP1-to-SP lanes. The relevant identity is the completed storage sink, not decoded opcode width.

## Falsifiable hypothesis

At the pinned ares revision a legal aligned `SD` calls `CPU::write<Dual>`, but `Memory::IO::write<Dual>` forwards only `data >> 32` into one `RSP::writeWord(address, ...)`. Thus a successful `SD` should mutate exactly one four-byte SP storage group containing the upper 32 bits of the GPR. A same-value successful `SD` should still yield a completed sink event even though storage bytes do not change. Misaligned and reserved-instruction executions must yield no SP sink.

If executable ares behavior changes two SP Words/eight bytes, the hypothesis is rejected. Even if the ares hypothesis is validated, it is not automatically an N64-wide rule: exact pinned Gopher64 is independently checked because its source topology appears to model integer `sd` as two Word writes.

## Source-derived baseline

Exact pinned ares:

- `ares/n64/cpu/interpreter-ipu.cpp`: `CPU::SD` rejects 32-bit non-kernel context then calls `write<Dual>(rs.u64 + imm, rt.u64)`.
- `ares/n64/memory/io.hpp`: generic RCP `write<Dual>` calls `writeWord(address, data >> 32, thread)` exactly once.
- `ares/n64/rsp/io.cpp`: CPU-visible SP writes commit through one `RSP::writeWord` into DMEM or IMEM.

The executable fixture in `spikes/043-ares-cpu-sd-sp-sink-gpt56sol/` uses the already-established project-owned post-device SP Word observer shadow, repeats every process, and checks observer-disabled state neutrality. It covers both banks, offsets 0/8, changed and same-value successes, misalignment, and a 32-bit user-mode reserved-instruction control.

The replay verifier explicitly rejects opcode-only, wrong-half, invented second-Word, wrong-bank and fault-with-fabricated-sink histories. It also demonstrates the intended same-value counterexample to a byte-difference mutation census.

## Reproduction

```sh
git checkout research/cpu-sd-sp-sink-gpt56sol
python3 -m py_compile spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/crosscheck.py
python3 spikes/043-ares-cpu-sd-sp-sink-gpt56sol/run.py
```

The branch workflow performs exact-pin checkouts and the executable run. Results, hashes, classification, limitations, and integration recommendation will replace this checkpoint after the exact-reference run completes.
