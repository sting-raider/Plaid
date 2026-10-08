# Exact pinned-ares PI DMA-read request/dispatch lifecycle

Status: **VALIDATED** for the bounded exact-pinned ares fixture below, 2026-10-09.

Branch: `research/pi-read-lifecycle-gpt56sol`.

This is a reference-implementation result, not an N64 hardware timing claim and not a general PBUS byte-origin proof.

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

- `ares/n64/pi/io.cpp` blob `2a41a8240e96ea3517bfb1fa67748829a900fb84`: `PI_READ_LENGTH` stores the requested length, sets DMA busy/origin, calls `cpu.queueInsert(Queue::PI_DMA_Read, dmaDuration(true))`, then calls `dmaRead()` synchronously.
- `ares/n64/pi/dma.cpp` blob `f2bd415495c6d84da779026b61fbe4c9f6ef7c88`: `dmaRead()` rounds the transfer length, selects PBUS timing/address, reads `Half` values from `rdram.ram` with `RBusDevice::PI_DMA`, and calls `busWriteHalf` for each value. `dmaFinished()` later clears busy, sets the PI interrupt bit and raises the PI IRQ.
- `ares/n64/pi/bus.hpp` blob `aaa7f8037c06e6ae8ca4b2bddf987b97e10b6d7c`: `busWriteHalf` updates `io.busLatch` before forwarding to a selected PBUS device.
- `ares/n64/cpu/cpu.cpp` pinned source: `CPU::synchronize` dispatches both `PI_DMA_Read` and `PI_DMA_Write` to the common `pi.dmaFinished()` handler.
- `ares/n64/n64.hpp` pinned source: `PI_DMA_Read` and `PI_DMA_Write` are distinct queue event values.
- `nall/nall/priority-queue.hpp` blob `17eb754bccdfd075f8dac206d7c0aafd28d01e37`: finite insertion fails at `size >= Size`; invalid rows are removed without invoking the event callback.

`spikes/036-ares-pi-read-lifecycle/source_guard.py` checks these exact contracts before every executable run. The first Actions attempt (`37850350686`) intentionally failed closed before compilation because one guard guessed the capacity spelling as `capacity` rather than the pinned template parameter `Size`; no semantic fixture ran in that attempt. The guard was corrected from the actual pinned header before the successful run.

## Experiment design

`spikes/036-ares-pi-read-lifecycle/actual.py` reuses the existing headless ares builder and the validated layout-neutral queue-identity sensor rather than inventing a second queue model. The observed variant additionally enables the existing successful identity-RDRAM scalar callback so the four actual `Half` reads inside each 8-byte PI read request are recorded while the causal request is open.

The driver executes six adversarial phases:

1. normal `PI_DMA_Read` request;
2. PI status cancellation after the immediate copy;
3. all 512 physical queue rows occupied before the real request;
4. two manually inserted `PI_DMA_Read` rows with equal event and deadline;
5. save-only queue serialization followed by normal dispatch;
6. save, reset, load and then dispatch.

It compares an uninstrumented baseline, callback-capable/disabled build, callback-enabled build and a repeated callback-enabled run. Architectural fixture facts and final CPU/RAM/hidden-RAM state hashes must match across baseline/disabled/enabled variants; enabled output must repeat byte-for-byte.

## Exact execution

GitHub Actions run `37850412674`, job `113561631656`, Ubuntu 24.04, completed **SUCCESS**.

Commands:

```sh
python3 spikes/036-ares-pi-read-lifecycle/source_guard.py
python3 spikes/036-ares-pi-read-lifecycle/actual.py
```

Receipts:

- actual trace SHA-256: `a50801cfe886d0d68a7314500378ee2c160053629860dc51b967c49164e9a673`;
- result JSON SHA-256: `a41a06188395ce46f4f98660705b91be461b44133de9cffce7d3699a3d45acde`;
- uploaded artifact ZIP SHA-256: `f0c79e5817ba055af98674621cd03bb558eb4013d90b47aaef17597b4c89dcad`;
- baseline / observer-disabled / observer-enabled architectural facts and state: equal;
- repeated enabled trace: byte-identical;
- queue records: 542;
- PI callback records: 5;
- RDRAM scalar records: 40.

Every real 8-byte request in phases 1, 2, 3, 5 and 6 produced exactly four request-scoped successful scalar reads at consecutive `+0,+2,+4,+6` RDRAM addresses. Each receipt reported `size=2`, `device=5`; the exact source guard ties that callback location to `RBusDevice::PI_DMA` rather than treating the integer device value as self-describing provenance.

## Results

### Normal request: validated request -> copy -> dispatch chronology

Request `1` received insertion token `1`. The successful insertion record occurred first; four actual RDRAM `Half` reads then occurred while request `1` was open; only later did the same token reach a valid queue removal and the common `dmaFinished()` callback. The PBUS latch already held the final copied halfword pattern before dispatch, while PI remained busy and not interrupted.

This validates, for this pinned fixture, the direction-specific chronology:

`PI_DMA_Read request -> successful queue token -> synchronous RDRAM reads/PBUS writes -> later valid removal -> CPU dispatch -> dmaFinished`

The token identifies the scheduled completion. It does not identify the byte-transfer instant.

### Cancellation: copy survives, completion identity does not

Request `2` received token `2` and completed all four RDRAM reads before the PI status reset invalidated that exact token. Draining the invalid row produced no `dmaFinished()` callback. A copy effect therefore cannot be used as evidence that a live completion remains scheduled.

### Full queue: strongest counterexample

With all 512 physical queue rows occupied, request `3` produced the real insertion-rejection event **before** its four actual `RBusDevice::PI_DMA` RDRAM reads. No successful insertion token existed and no PI completion callback occurred.

This directly rejects any join rule of the form:

`observed PI copy effect => scheduled PI completion identity`.

Pinned ares can execute the copy even when no completion event was successfully enqueued.

### Equal event/deadline rows remain non-identical

Two manually inserted `PI_DMA_Read` rows at the same deadline received distinct tokens `515` and `516`. Both traversed the real CPU dispatcher and common completion handler, but both retained request identity `0`. Matching by event value, deadline, current PI state or “nearest request” would fabricate provenance.

### Save-only preserves live identity

A real request received token `517`. Queue serialization in writing mode emitted the existing save boundary without clearing the sidecar; the same token later reached removal and `dmaFinished()` still bound to the original request. This independently exercises current ADR-0057 policy with a real `PI_DMA_Read` request rather than only the queue-container fixture.

### Load cuts identity

A later real request received token `518`. Saving preserved it, but queue reset/load cleared the external sidecar. The restored reference event still dispatched and invoked `dmaFinished()`, while the observer reported request/token `(0,0)`. No cross-load identity is inferred.

## Conclusion

**VALIDATED** for this exact pinned-ares scope.

The previously validated request/queue/dispatch identity contract is direction-symmetric for the executed `PI_DMA_Read` fixture, and the current save-only/load-cut sidecar policy survives the real read path. The strongest architectural lesson is the same in both PI directions: scheduling identity and byte-transfer evidence are separate facts and must stay separate in Plaid's provenance model.

## Limitations / remaining unknowns

- This is ares behavior at revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`, not an N64 hardware timing oracle.
- The fixture uses identity-mapped RDRAM, aligned 8-byte transfers and one PBUS/open-address setup. It does not cover every PI length, DRAM/PBUS alignment, BSD page crossing, PBUS device, device-side write effect or error path.
- The observed backing evidence proves the successful RDRAM `Half` reads used by this `dmaRead`; it does not by itself establish durable byte provenance inside an arbitrary writable PBUS target device.
- The result does not prove overlapping real PI requests, reentrancy, every reset/frontend lifecycle, arbitrary save-state provenance reconstruction or hardware bus contention.
- Load deliberately remains a provenance cut. A future sidecar-persistence scheme would require an independently validated identity format and restore join.
- Callback neutrality is demonstrated only for the fixture's reported architectural facts/state and repeated stream, not all ares behavior.
- No production ProgramMap/closed-world integration was attempted. General executable lifetime, non-PI copies, cache lineage and mutation completeness remain open.

## Integration recommendation

**ADOPT** the bounded semantic result: treat `PI_DMA_Read` and `PI_DMA_Write` request scheduling symmetrically at the request/token/dispatch layer, retain actual transfer transactions as a separate chronology, preserve live queue identity across save-only serialization, and fail closed across load. Do not promote `dmaFinished()` to a byte-transfer boundary or infer a completion identity from copy effects.
