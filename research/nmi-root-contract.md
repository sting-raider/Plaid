# N64 external-NMI executable root and state contract

Status: **PARTIAL**

Date: 2026-10-09

## Question

For Plaid's exact pinned ares revision, what executable PC and CPU state transition are selected by the CPU's pending-NMI path, and which pieces can safely inform a whole-ROM executable-root certificate?

This deliberately does **not** redo reset/cache lifetime work. It isolates executable entry and the state needed to distinguish that entry from ordinary exceptions.

## Pins and execution base

- Plaid integration base inspected before claim: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

## Falsifiable hypothesis

Pinned ares's external pending-NMI path selects one fixed reset/NMI executable root rather than the ordinary BEV-dependent exception roots, sets ERL, and captures ErrorEPC from the interrupted CPU PC. Incoming BEV, EXL and ERL must not redirect it through `base + 0x000/0x080/0x180`. Delay-boundary and repeated-pending cases are adversaries: if either changes first-entry root selection, the proposed root contract is false.

## Exact pinned ares source contract

At the pinned revision:

- `CPU::instruction()` handles an eligible maskable interrupt first, then checks `scc.nmiPending`; when it is set, it calls the NMI debugger hook, steps one CPU cycle pair, calls `exception.nmi()`, and returns before instruction fetch.
- `Exception::nmi()` forces `Status.BEV=1`, clears `Status.TS`, clears `Status.SR`, sets `Status.ERL=1`, copies `ipu.pc` into ErrorEPC, and calls `pipeline.setPc(0xffffffffbfc00000)`.
- unlike ordinary `Exception::trigger()`, the NMI function does not consult EXL, does not select `base + 0x000/0x080/0x180`, and does not apply branch-delay correction to ErrorEPC.
- `pipeline.setPc()` resets the pipeline branch/delay state.
- `scc.nmiPending` is a plain serialized one-bit field. The CPU NMI branch does not clear it. The pinned PIF HLE contains one producer that sets it when the HLE state reaches `Error`.

Exact source SHA-256 values measured by the successful CI run:

| File | SHA-256 |
| --- | --- |
| `ares/n64/cpu/exceptions.cpp` | `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7` |
| `ares/n64/cpu/cpu.cpp` | `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1` |
| `ares/n64/cpu/cpu.hpp` | `6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27` |
| `ares/n64/pif/hle.cpp` | `4b7546a07b765e1cb825ab6ce060dbfcc652c0042f7a28dcfb4756c0b2b61442` |

## Executable experiment

Artifacts:

- `experiments/ares-nmi-root/driver.cpp`
- `experiments/ares-nmi-root/run.py`
- `experiments/ares-nmi-root/README.md`
- branch-only `.github/workflows/research-nmi-root.yml`

The driver boots the unmodified exact-pin ares N64 core headlessly with CPU/RSP recompilers disabled. It does **not** patch reference CPU code. It seeds a synthetic interrupted PC `0xffffffffa0000104`, ordinary EPC sentinel `0x1111222233334444`, incoming BEV/EXL/ERL/SR, TS=1, and optionally marks the current pipeline state as a delay slot. It then asserts `scc.nmiPending` and enters through normal `CPU::instruction()`.

The runner executes the full 32-case cross-product of incoming `{BEV, EXL, ERL, SR, delay-boundary}` and two additional cases that deliberately leave the pending bit asserted for a second `CPU::instruction()`. Every invocation is repeated and required to produce byte-identical JSON.

Authoritative run:

- GitHub Actions run: `37915643019`
- job: `113771024192`
- code head: `73e24e88fb442f1f0e6b3e2f1b2750b8e2095311`
- conclusion: success
- case count: 34
- result JSON SHA-256: `9dbd8ef2d125fc86d13e244ce60515b6a361b00240c2768c9d0b8d3344b9435b`
- artifact ID: `11608528658`
- uploaded artifact ZIP SHA-256: `3281431f251b20fcfea065158bcccec60da4d8c2d804b046807b4ea2df96c101`

The workflow log reports:

`PASS: 34 exact-pin NMI cases repeated byte-identically and matched the guarded ares transition`

## Deterministic observations

For **all 32 first-entry state combinations**:

1. first PC was `0xffffffffbfc00000`;
2. first ErrorEPC was exactly the synthetic interrupted PC `0xffffffffa0000104`;
3. incoming BEV did not affect root selection and became 1;
4. incoming ERL did not prevent entry and became 1;
5. EXL was preserved rather than cleared or forced;
6. ordinary EPC remained the sentinel and therefore was not the NMI return witness;
7. TS became 0;
8. SR became 0 in exact pinned ares, regardless of its incoming value;
9. a synthetic delay-slot state did not subtract four from ErrorEPC; after `pipeline.setPc()` the delay state was cleared;
10. `nmiPending` remained asserted after the CPU NMI branch.

The persistent-pending adversary then called `CPU::instruction()` a second time without clearing the latch. The second NMI re-entered the same root and overwrote ErrorEPC from the original interrupted PC to `0xffffffffbfc00000`. This demonstrates that the ares CPU-side pending bit is **not itself a unique NMI event/completion token**. Any Plaid trace that wants NMI event identity must bind to an actual producer/edge/lifecycle, not repeatedly interpret a level as distinct causal events.

## Independent reference comparison

### Gopher64 exact pin

`src/device/exceptions.rs::reset_event`:

- sets ERL, SR and BEV;
- clears TS;
- copies current CPU PC to ErrorEPC;
- sets CPU PC to `0xBFC00000`;
- resets the branch state to a normal step;
- resets RSP PC and PIF reset state as additional system effects.

This independently supports the fixed reset/NMI root, ErrorEPC=current-PC shape and branch-state reset, but **disagrees with ares on Status.SR**.

### Mupen64Plus exact pin

`soft_reset_device()` explicitly models a reset-button press by scheduling HW2 immediately and an NMI after 50,000,000 count units. Its pinned NMI handler sets ERL/BEV/**SR**, clears TS, and writes the current PC to ErrorEPC. Thus a second independent emulator agrees that reset-button NMI should set SR, not clear it. Mupen's reset/boot sources also use `0xbfc00000` as the reset start address.

### n64-systemtest exact pin

The hardware-oriented startup test says initial Status normally has SR clear, but explicitly accepts `soft_reset=true` because that occurs after the reset button. It also notes that ErrorEPC can differ after reset. This was source-audited here, not run on physical hardware in this session.

## Result

**PARTIAL.**

The executable-root portion is strongly supported: exact pinned ares execution across adversarial incoming state always selects `0xffffffffbfc00000`, and Gopher64/Mupen reset/NMI models independently support that reset entry address and ErrorEPC shape. For a Plaid whole-ROM certificate, `0xffffffffbfc00000` must therefore be represented as a reset/NMI executable root distinct from ordinary exception roots when the declared scope includes reset/NMI.

The broader state contract is **not** safe to elevate from ares to an N64 invariant. In particular, ares clears Status.SR while Gopher64, Mupen64Plus and n64-systemtest's reset-button expectation support SR being set. The ares `nmiPending` producer/lifecycle also does not by itself prove physical reset-button delivery semantics.

## What this explicitly does not prove

- It does not prove physical N64 reset-button timing or electrical NMI behavior.
- It does not execute n64-systemtest on hardware.
- It does not prove which arbitrary ROM scopes can reach reset/NMI; root enumeration and reachability remain separate.
- It does not prove PIF ROM bytes at `0xffffffffbfc00000`; byte provenance is a separate already-researched boot/PIF obligation.
- It does not cover the HW2 pre-NMI interval modeled by Mupen.
- It does not cover simultaneous eligible maskable interrupt plus NMI; an active worker already owns maskable-interrupt semantics, so this experiment intentionally avoids that overlap.
- It does not change the existing cache/RDRAM lifetime conclusion across NMI/reset/restore.
- It does not prove that leaving ares `nmiPending` asserted models real hardware. The repeated-entry case is specifically an implementation/lifecycle counterexample.

## Integration recommendation

**ADOPT** the narrow executable-root obligation and **REJECT** ares's Status.SR transition as a hardware-wide rule:

- represent reset/NMI entry root `0xffffffffbfc00000` separately from ordinary exception `base + {0x000,0x080,0x180}` roots;
- keep reachability and root-byte provenance independent;
- use ErrorEPC, not ordinary EPC, as the NMI/reset return-state register in the supported model;
- do not infer unique NMI events from a persistent pending level;
- keep reset-button Status.SR semantics reference-disputed until stronger hardware evidence resolves it.

Primary integration recommendation: **PRIMARY-INTEGRATOR-REVIEW**, because the executable-root fact is ready to adopt but the reset/NMI event model must preserve the explicit SR disagreement and producer-lifecycle caveat.
