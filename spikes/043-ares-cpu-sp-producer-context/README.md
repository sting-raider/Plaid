# Spike 043: decoded CPU producer context for SP Word sinks

Result: **VALIDATED** for the controlled pinned-ares interpreter scope.

## Falsifiable question

Can an actual CPU-originated SP-memory Word sink be attributed to the exact decoded
VR4300 producer instruction and register-level source context without using
nearest-same-PC matching or payload equality?

The scope is deliberately limited to the three producer families observed in the
bounded boot inventory: `SW`, `SB`, and `SWC1`. It does not attempt ultimate
GPR/FPR dataflow.

## Experiment

`driver.cpp` executes real encoded instructions through pinned ares
`CPU::instruction()` with recompilers disabled. The existing project-owned SP
backing callback observes the concrete `RSP::writeWord` sink. A fixture-owned
scope is active only for the synchronous `CPU::instruction()` call, so later
`synchronize()` work and direct CPU writes are not silently assigned to the
instruction.

Adversaries:

- two same-PC, same-instruction, same-address, same-value `SW` executions must
  remain two writer generations;
- an equal-address/equal-value direct `cpu.write<Word>` outside decoded execution
  must remain context zero;
- `SB +1` must preserve the already validated widened full-Word SP sink;
- `SWC1` exercises FR=0 even, FR=0 odd-pair-high, and FR=1 named-register-low
  source selection;
- CU1-disabled `SWC1` must fault before any SP sink.

`verify.py` re-decodes every attributed instruction from the recorded word and
independently derives the expected register-level payload. It rejects value-only
or address-only joins.

## Validated observations

Exact pinned ares revision:
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Passing Actions run `37915925049`, job `113771954343`, tested commit
`971fd59dfaa693acaad7cccce03a8fc8b0ae88b0`:

- seven concrete CPU-originated SP Word sink events;
- six events attributed to decoded `SW`/`SB`/`SWC1` contexts;
- one equal-address/equal-value direct CPU write kept at context zero;
- two identical `SW` executions retained distinct ordinals/generations;
- widened `SB +1` sink was `0x77880000`;
- FR-sensitive `SWC1` sinks were `0x55667788`, `0x11223344`, and `0xddeeff00`;
- CU1-disabled `SWC1` raised exception code 11 / CE=1 and emitted no SP sink;
- observer-disabled and enabled architectural facts/outcomes were identical;
- repeated enabled traces were byte-identical.

Trace SHA-256:
`2f00b296fef961db9bd76792912e4e7fd60ae7e293555a3d2c448be37b8b619f`.

`results.json` SHA-256:
`f41331e4cbf7590c8b598c2385e573da49296f963da8fd0b5635f6bc83b7d725`.

Uploaded artifact digest:
`sha256:2f3f0f27dcbaa209e8e7d77d514c3e87e0c564851f31ad84c313fe2dcc916321`.

## Reproduction

```sh
python3 -m py_compile spikes/043-ares-cpu-sp-producer-context/*.py
python3 spikes/043-ares-cpu-sp-producer-context/run.py
```

The runner requires exact pinned ares under `.refs/ares`, source-guards the CPU
interpreter/store and SP sink path, builds through the existing headless ares
helper with the SP backing callback, then compares observer-disabled and repeated
enabled architectural facts.

## Non-claims

This validates register-level causal context for these controlled interpreter
stores. It is not a retirement/producer proof for arbitrary JIT execution, not
ultimate source-byte provenance for earlier GPR/FPR producers, not a complete CPU
store census, not RSP/DMA provenance, and not executable-lifetime or closed-world
proof.
