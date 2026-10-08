# Exact pinned-ares PI DMA-read request/dispatch lifecycle

Status: **IN PROGRESS** on isolated research branch `research/pi-read-lifecycle-gpt56sol`.

## Question

The validated `PI_DMA_Write` fixture established a fail-closed request -> successful queue insertion token -> valid removal -> CPU dispatch -> common `PI::dmaFinished()` identity chain, but explicitly did not execute a symmetric full-reference `PI_DMA_Read` request. This experiment tests that missing direction against exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Falsifiable hypothesis

For an accepted PI read-length MMIO request, pinned ares attempts the `PI_DMA_Read` queue insertion and then synchronously executes the RDRAM-to-PBUS `dmaRead()` copy. The later scheduled event can be joined to the original request only through the exact successful insertion identity carried to a valid removal and CPU dispatch. Therefore:

- full-queue insertion failure may still produce the immediate backing reads but must produce no request/completion token;
- PI status cancellation must retire the exact token and forbid later completion identity;
- equal event/deadline rows are not identities;
- save-only serialization preserves live queue identity under current ADR-0057, while load cuts it;
- `dmaFinished()` is a scheduling/status boundary, not the byte-transfer boundary.

Any exact-reference case in which the read path orders its RDRAM effects after dispatch, a rejected insertion suppresses the immediate copy, a canceled row reaches a certified completion, duplicate rows collapse identity, save-only loses a current token, or load silently reuses one falsifies the corresponding claim.

## Exact pinned source map

- `ares/n64/pi/io.cpp`: `PI_READ_LENGTH` stores the requested length, sets DMA busy/origin, calls `cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true))`, then calls `dmaRead()` synchronously.
- `ares/n64/pi/dma.cpp`: `dmaRead()` rounds the transfer length, selects PBUS timing/address, reads `Half` values from `rdram.ram` with `RBusDevice::PI_DMA`, and calls `busWriteHalf` for each value. `dmaFinished()` later clears busy, sets the PI interrupt bit and raises the PI IRQ.
- `ares/n64/pi/bus.hpp`: `busWriteHalf` updates `io.busLatch` before forwarding to a selected PBUS device.
- `ares/n64/cpu/cpu.cpp`: `CPU::synchronize` dispatches both `PI_DMA_Read` and `PI_DMA_Write` to the common `pi.dmaFinished()` handler.
- `nall/nall/priority-queue.hpp`: finite queue insertion can fail; only valid removals invoke callbacks.

`spikes/036-ares-pi-read-lifecycle/source_guard.py` checks these contracts at the exact pin before building.

## Experiment design

`spikes/036-ares-pi-read-lifecycle/actual.py` reuses the validated headless ares builder and queue-identity instrumentation rather than inventing a second container model. The observed variant additionally enables the existing successful identity-RDRAM scalar callback so the four actual `Half` reads inside each 8-byte PI read request are directly recorded while the causal request is open.

The driver executes normal, cancellation, capacity-rejection, equal-deadline duplicate, save-only and save/load cases. It compares an uninstrumented baseline, callback-capable/disabled build, callback-enabled build and repeated callback-enabled run. Architectural fixture facts and state hashes must match across baseline/disabled/enabled variants; enabled output must repeat byte-for-byte.

## Result

Pending exact-pin execution. This note will be updated with run identifiers, hashes, result classification and limitations before closeout.
