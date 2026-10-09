# Exact-pin ares NMI root experiment

## Question

What executable root and CPU state transition does the pinned ares N64 external-NMI path actually produce, and which parts are safe to use as Plaid whole-ROM root evidence?

## Hypothesis

The pending-NMI path selects a fixed `0xffffffffbfc00000` root independently of incoming BEV/EXL/ERL, sets ERL, captures the interrupted PC in ErrorEPC, and does not route through ordinary `base + {0,0x80,0x180}` exception selection. Adversarial incoming state and repeated pending delivery must expose any hidden dependence. Reference disagreement is retained rather than averaged away.

## Pins

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Fixture

`driver.cpp` boots the unmodified exact-pin ares N64 core headlessly with both recompilers disabled. It sets incoming BEV, EXL, ERL, Status.SR, a synthetic delay-slot boundary, and `scc.nmiPending`, then calls the normal `CPU::instruction()` entry point. The matrix covers all 32 combinations of those five one-bit inputs plus two persistent-pending two-entry adversaries. Every case is executed twice and must be byte-identical.

The runner guards exact source signatures for the pending path, NMI transition and PIF-HLE producer, records SHA-256 hashes for those exact pinned files, and emits `target/ares-nmi-root/results.json`.

Run locally with an exact `.refs/ares` checkout:

```sh
python3 -m py_compile experiments/ares-nmi-root/run.py
python3 experiments/ares-nmi-root/run.py
sha256sum target/ares-nmi-root/results.json
```

The branch-only GitHub Actions workflow `.github/workflows/research-nmi-root.yml` performs the same build and run from a fresh exact-pin clone and retains the JSON artifact.

## Adversarial assertions

For the exact pinned ares path the runner requires:

- first delivery root = `0xffffffffbfc00000` for every incoming BEV/EXL/ERL/SR/delay state;
- first ErrorEPC = the interrupted `ipu.pc`, including when the pipeline says the next instruction is a branch delay slot;
- ordinary EPC is unchanged;
- BEV becomes 1, ERL becomes 1, TLB-shutdown becomes 0, EXL is preserved;
- Status.SR becomes 0, exactly matching the pinned ares source even though independent references disagree;
- `pipeline.setPc()` clears the delay-slot pipeline state;
- the CPU NMI path does not consume `scc.nmiPending`; if the latch remains asserted, a second `CPU::instruction()` re-enters NMI and overwrites ErrorEPC with the NMI root itself.

That last case is deliberately not promoted to hardware behavior. It is a bounded fact about how this ares pending latch must be driven or cleared by its producer/lifecycle.

## Independent source cross-check

Pinned Gopher64 `src/device/exceptions.rs::reset_event` sets ERL, SR and BEV, clears TS, copies the current CPU PC to ErrorEPC and jumps to `0xBFC00000`. Pinned Mupen64Plus schedules reset-button NMI after an HW2 interrupt; its NMI handler sets ERL/BEV/**SR** and captures the current PC in ErrorEPC. Pinned n64-systemtest's startup test explicitly accepts Status.SR being set after the reset button.

Therefore the fixed reset/NMI executable root and ErrorEPC shape have independent support, while ares clearing Status.SR is a reference disagreement and must not become an N64-wide invariant.

## Non-goals

This does not prove reset-button timing, HW2 pre-NMI behavior, physical-hardware NMI delivery, cache/RDRAM lifetime across reset, simultaneous maskable-interrupt priority, PIF/CIC boot-byte provenance, or arbitrary-ROM reachability. Those are separate obligations. In particular, existing cache-lifetime research already covers that NMI and reset-like transitions cannot be collapsed into one global code-generation boundary.
