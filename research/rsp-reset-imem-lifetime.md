# RSP IMEM lifetime across NMI and reset-like transitions

Status: experimental branch evidence, not integrated into `main`.

## Question

Plaid already has evidence that RSP executable identity is not `IMEM address + payload hash`: byte-identical reloads, overlapping CPU writes, SP-DMA transfer identity, partial residency and synchronized savestate restore all create distinct causal histories. The remaining reset/NMI question is whether reset-like events may be collapsed into one generic executable-lifetime boundary.

## Exact-reference source result

At exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, `RSP::power(bool reset)` calls `dmem.fill()`, `imem.fill()`, clears `dma`, resets the RSP pipeline/register/branch state, sets PC to zero and halts the RSP. `System::power(reset)` calls `rsp.power(reset)`. The RSP implementation does not conditionalize those effects on the `reset` argument. The same `reset=true` transition intentionally preserves RDRAM backing in `RDRAM::power`, so the RSP clear is a reset-specific storage decision rather than an artifact of treating the call as cold power. In contrast, CPU NMI enters `CPU::Exception::nmi()` and has no RSP storage/state mutation path.

At exact pinned Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`, `soft_reset_device()` schedules HW2 and NMI. The immediate `nmi_int_handler()` body does not call `poweron_rsp`, but stopping there is unsound: it calls `pif_bootrom_hle_execute()`. On the HLE path (`start_address != 0xbfc00000`) that function halts the SP and directly writes eight IPL2 words into IMEM offsets `0x000..0x01c`, while also copying IPL3 data into DMEM. Thus Mupen's soft-reset/NMI path is a conditional partial IMEM producer, not a blanket preserve and not a full clear. `reset_hard_handler()` separately calls `poweron_device()`, whose `poweron_rsp()` zeroes all `SP_MEM_SIZE`.

At exact pinned Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`, `reset_event()` resets CPU state and sets `SP_PC_REG` to zero, then calls `reset_pif()`. Following that callee shows PIF ROM/RAM updates only and no RSP-memory write/clear. At this pin, therefore, its reset-event path preserves IMEM bytes while changing RSP execution state.

The references therefore expose three materially different reset shapes: full RSP storage/state clear (ares `System::power(true)`), conditional partial executable IMEM production (Mupen HLE soft reset), and IMEM preservation with RSP PC reset (Gopher64 reset event). This disagreement is preserved. It is not legitimate to promote any one emulator's reset-button behavior into hardware truth.

## Executable ares experiment

`experiments/rsp-reset-imem-lifetime/driver.cpp` uses unmodified exact-pinned ares through Plaid's existing headless build harness.

The fixture intentionally seeds:

- nonzero RSP IMEM;
- nonzero RSP PC / running state;
- one active and one pending SP-DMA request (`BUSY=1`, `FULL=1`).

It then checks four transitions:

1. CPU NMI leaves the RSP IMEM hash, PC and active/pending DMA descriptor state unchanged.
2. `System::power(true)` clears RSP IMEM and resets RSP execution/DMA state.
3. Repeating `System::power(true)` with already-zero IMEM leaves the payload hash unchanged while still resetting live RSP execution/DMA state. This is the equal-payload counterexample: before/after byte equality does not imply that no lifetime-changing operation occurred.
4. Cold `System::power(false)` also clears a nonzero installed RSP image.

The exact CI receipt and hashes are recorded in issue #4 closeout/checkpoints for this branch.

## Adversarial proof implication

Neither generic policy is sound:

- `every reset-like event retires all RSP executable provenance` invents a full RSP mutation at ares CPU NMI and destroys a still-live causal installation identity;
- `every reset-like event preserves RSP executable provenance` misses ares's explicit RSP power/reset clear and Mupen's reset-time IPL2 IMEM writes;
- `reset means clear all IMEM` also overstates Mupen's partial producer and Gopher64's byte-preserving path.

The minimum evidence model therefore needs typed transitions **and byte-range effects**. NMI, HLE soft reset, hard reset/cold power and savestate restore are not interchangeable names for one generation increment. An RSP executable lifetime changes only where the chosen behavioral contract proves an effect that destroys/replaces resident storage or invalidates the relevant execution context. Partial reset-time writers must be represented as writers with their own provenance, not as a global epoch shortcut. Same address, same hash and same bytes do not repair or establish continuity.

For a portable whole-ROM/native-complete certificate, a reset-like transition whose RSP storage semantics are not independently established must remain an OPEN obligation. The solver must not discharge it from payload equality or a generic `reset` label.

## What this composes

- `research/rsp-imem-provenance.md`: equal bytes can have different writer provenance.
- `research/rsp-microcode-installation-lifetime.md`: installation identity/lifetime is causal and mutation-sensitive.
- `research/rsp-imem-dma-direct-write-interleave.md`: per-byte writer chronology survives transfer-level summaries.
- `research/rsp-savestate-microcode-epoch.md`: restore is a separate snapshot-qualified chronology transition.
- `research/reset-cache-lifetime.md`: NMI/reset/cold-power effects already differ for CPU cache and RDRAM, so one global reset generation is unsound.

## Remaining gap

This result establishes exact pinned-reference behavior and an executable ares counterexample. It does not establish physical N64 reset-button semantics. A dedicated n64-systemtest/hardware experiment is still needed to determine real soft-reset effects on SP IMEM byte ranges, RSP halt/PC state and in-flight SP DMA. Until then the reference disagreement itself is evidence that the hardware-facing rule is unresolved, and a portable certificate must remain OPEN rather than choosing whichever emulator behavior is convenient.
