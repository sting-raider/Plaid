# Spike 043: decoded CPU producer context for SP Word sinks

Result: **IN PROGRESS** until the exact-pin workflow receipt is recorded.

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
- `SWC1` exercises FR=0 even, FR=0 odd-pair-high and FR=1 named-register-low
  source selection;
- CU1-disabled `SWC1` must fault before any SP sink.

`verify.py` re-decodes every attributed instruction from the recorded word and
independently derives the expected register-level payload. It rejects value-only
or address-only joins.

## Reproduction

```sh
python3 -m py_compile spikes/043-ares-cpu-sp-producer-context/*.py
python3 spikes/043-ares-cpu-sp-producer-context/run.py
```

The runner requires exact pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` under `.refs/ares`, source-guards the
CPU interpreter/store and SP sink path, builds through the existing headless ares
helper with the SP backing callback, then compares observer-disabled and repeated
enabled architectural facts.

## Non-claims

A successful result is register-level causal context for this controlled
interpreter scope. It is not a retirement proof for arbitrary JIT execution, not
ultimate source-byte provenance for prior GPR/FPR producers, not a complete CPU
store census, not RSP/DMA provenance, and not executable-lifetime closure.
