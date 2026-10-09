# Spike 043: RSP microcode installation lifetime

Status: in-progress bounded research fixture.

This spike composes two already-validated Plaid research facts on exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`:

1. successful SP-DMA RDRAM reads can be joined to completed 8-byte IMEM writes and later RSP fetches;
2. an ares SP-DMA request becomes stable when `dma.pending` is promoted to `dma.current`, while BUSY can remain asserted across immediate current->pending handoff.

The falsifiable question is whether a promotion-scoped token plus completed fragment effects is sufficient to certify one complete installed microcode generation, rather than grouping by payload equality, programmed registers, or BUSY edges.

The fixture exercises:

- one 16-byte row producing two 8-byte fragments;
- a two-row count/skip request with an RSP fetch between rows, proving writer-known partial residency is not yet a complete installation certificate;
- 4 KiB IMEM wrap (`0xff8 -> 0x000`) under one transfer;
- two equal-payload transfers to the same IMEM destination with immediate handoff and no externally visible BUSY-low state;
- non-overlapping and overlapping CPU direct IMEM writes after installation;
- a pending descriptor whose addresses mutate after its length commit, showing the frozen descriptor must be the promoted `dma.current` state.

`run.py` independently derives all expected `(RDRAM source, IMEM destination)` fragment coordinates from each promoted descriptor and rejects missing, mis-owned, reordered, stale-descriptor, and omitted-overwrite histories.

Reproduce the pure replay adversary locally without a reference checkout:

```bash
python3 spikes/043-ares-rsp-microcode-lifetime/run.py --self-test
```

Run the exact-pinned reference experiment with `.refs/ares` at the revision above:

```bash
python3 spikes/043-ares-rsp-microcode-lifetime/run.py
```

The generated observer shadows upstream files in the build directory only. It adds no fields to ares CPU/RSP objects and performs no extra guest bus or memory reads. Baseline, observer-enabled, and repeated observer executions must report identical guest-visible fixture state before any result is accepted.

This spike does **not** claim hardware BUSY/FULL semantics, exhaustive RSP task reachability, save-state provenance, translated/degraded RDRAM coverage, or whole-ROM closure.
