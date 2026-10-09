# RSP producer -> CPU SP copy -> executable IMEM composition

Bounded exact-pinned-ares experiment for one missing provenance composition:

`RSP/CPU/unknown DMEM byte generations -> completed CPU SP read -> interpreted LW register generation -> interpreted SW -> completed SP IMEM sink`.

The fixture includes a pure RSP `SW` source copied to IMEM, a byte-identical second RSP `SW` that must create fresh ancestry, one mixed source word whose bytes are latest-written by CPU, unknown/out-of-context, RSP vector `SBV`, and RSP scalar `SB` producers, an equal-valued DMEM decoy load into another GPR immediately before the mixed-word store, a same-valued `ADDU` clobber of the copy GPR, and an equal-valued out-of-instruction CPU IMEM sink.

The strict replay carries four source-byte generations through the GPR definition. It intentionally rejects any rule that chooses an origin from whole-word value equality.

## Reproduce

With `.refs/ares` checked out exactly at `9408cb43d4948fc3ea6e152a307a34348df3fe04`:

```sh
python3 spikes/045-rsp-producer-cpu-imem-compose/model.py
python3 spikes/045-rsp-producer-cpu-imem-compose/run.py
```

`run.py` builds an uninstrumented baseline, a sensor-capable binary with callbacks disabled, and two enabled executions. It requires baseline/disabled/enabled state and CPU-step equality plus byte-identical repeated traces. It also mutates the trace/step history and requires every forged history to fail.

This is a research fixture. It does not prove complete RSP/CPU writer coverage, scheduler reachability, hardware truth, IMEM lifetime closure, or whole-ROM closure.
