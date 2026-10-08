# RSP SP-DMA transfer lifecycle and identity

Date: 2026-10-08

Status: **PARTIAL**

## Conclusion

The bounded hypothesis was only partly correct.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` does have one active
`dma.current` descriptor and one `dma.pending` descriptor, but the pending
request is **not immutable after its length-register commit**. While a transfer is
active and the pending slot is already FULL, subsequent SP/DRAM address-register
writes mutate that same pending descriptor, and another length-register write
replaces/recommits its length/count/skip/direction. The old pending request can
therefore disappear before promotion.

That falsifies a tempting provenance rule: for this pinned ares path, Plaid cannot
assign an immutable higher-level transfer identity merely at the guest's pending
length-register write and assume the descriptor remains unchanged. A stable ares
request descriptor exists when `dma.pending` is promoted into `dma.current`, or an
observer must explicitly track all mutations to the pending descriptor before
promotion.

Two additional lifecycle requirements were validated in the executable fixture:

- a completed current transfer can hand directly to a pending request inside the
  same `dmaTransferStep()` call, leaving `dma.busy` asserted after the call; a
  BUSY falling edge is therefore not a reliable per-request completion boundary;
- count/skip sub-blocks remain one current request, and an IMEM transfer can wrap
  from `0xff8..0xfff` to `0x000..0x007`, so one transfer may have multiple wrapped
  destination spans.

The dangerous FIFO-full behavior is **not established as N64 hardware behavior**.
Pinned Mupen64Plus and Gopher64 both snapshot the second FIFO descriptor when it
is pushed and reject a third push while FULL. Their agreement against ares means
the ares pending-mutation/overwrite behavior must remain implementation-specific
until hardware-oriented evidence resolves the discrepancy.

## Falsifiable hypothesis and result

Hypothesis:

> Pinned ares has one current transfer plus one mutable pending slot. A sound
> bounded transfer witness can snapshot the request at the length-register commit
> that occupies a slot, retain that identity across count/skip rows, and complete
> it when the exact current request drains; full-slot ambiguity and IMEM wrapping
> must fail closed or be represented explicitly.

Result: **PARTIAL / snapshot-at-length-commit subclaim REJECTED for pinned ares.**

The first sentence was correct, but a pending length-register commit does not
freeze the descriptor. The executable adversaries show later MMIO writes mutate
or replace it before promotion. Count/skip grouping and explicit wrap handling
were validated. Cross-reference comparison rejects treating ares's FULL behavior
as an N64-wide invariant.

## Exact source map

### ares

Revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

- `ares/n64/rsp/io.cpp::RSP::ioWrite`
  - SP_PBUS_ADDRESS writes `dma.pending.pbusAddress` and `pbusRegion` directly.
  - SP_DRAM_ADDRESS writes `dma.pending.dramAddress` directly.
  - SP_READ_LENGTH / SP_WRITE_LENGTH write `dma.pending.length/count/skip`, set
    `dma.full`, and call `dmaTransferStart(thread)`.
  - There is no `dma.full.any()` rejection guard before those writes.
- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStart`
  - returns immediately only when `dma.busy.any()`;
  - otherwise promotes `dma.pending` to `dma.current`, copies `dma.full` to
    `dma.busy`, clears `dma.full`, and schedules the current request.
- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStep`
  - performs one row for the current transfer;
  - decrements `current.count` and adds `current.skip` between rows;
  - on the final row clears `dma.busy`, resets the current length, then calls
    `dmaTransferStart(*this)` in the same function, allowing immediate pending
    promotion without an externally visible BUSY=0 state;
  - `pbusAddress` is `n12`, so increments wrap modulo 4096.
- `ares/n64/rsp/rsp.hpp::RSP::DMA`
  - contains exactly `pending`, `current`, `busy`, `full`, and `clock`; the request
    descriptors contain region, PBUS address, DRAM address, length, skip, count,
    origin PC and CPU-origin flag.
- `ares/n64/rsp/serialization.cpp`
  - serializes both descriptors, busy/full direction bits and DMA clock. Any
    future external Plaid transfer identity must therefore either be serialized
    consistently or deliberately cut/reconstruct provenance across restore; the
    upstream descriptor state itself survives serialization.

Exact source SHA-256 values recorded by the successful CI source guard:

- ares `io.cpp`: `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`
- ares `dma.cpp`: `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`

### Mupen64Plus

Revision: `ba95bab92a76744753bfe61470823a4937850ab0`.

`src/device/rcp/rsp/rsp_core.c::fifo_push` checks
`SP_DMA_FULL_REG` first and returns with a warning if it is already full. When
BUSY and not FULL, it copies direction, length, memory address and DRAM address
from the registers into `fifo[1]`. Later register writes therefore do not mutate
that accepted second descriptor.

Source SHA-256:
`8f24582ff64748ac6164f4c468adf7d7d198a968f6c53ad6ff690469fe095b7f`.

### Gopher64

Revision: `e96debac941a26ba4961e5145056c0821d3a56f7`.

`src/device/rsp_interface.rs::fifo_push` likewise copies the register snapshot into
`fifo[1]` when BUSY and rejects a push while FULL (currently by panic). It therefore
agrees structurally with Mupen and disagrees with ares on the pending-mutation /
third-push cases.

Source SHA-256:
`a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053`.

### n64-systemtest

Pinned revision: `196f5421173220eb2f63a7a99c64795dc0ea0698`.

`src/tests/sp_memory/dma.rs` explicitly describes SP-memory DMA overflow as
remaining within the selected DMEM or IMEM bank and contains IMEM-overflow tests.
That hardware-oriented test source corroborates the modulo-IMEM wrap requirement.
This worker did not execute the systemtest suite, and no pinned systemtest case was
found here that resolves the BUSY+FULL third-write policy.

## Executed experiment

Durable fixture: `spikes/034-ares-sp-dma-lifecycle/`.

The driver uses the existing headless ares component build, disables both CPU and
RSP recompilers, forces identity-mapped 8-MiB RDRAM, and drives the actual pinned
RSP MMIO and DMA engine. It adds no reference instrumentation and records only
public component state and final memory effects. The same executable is run twice
and the full JSON stdout must match byte-for-byte.

### Case 1: pending descriptor mutation

1. Start A: RDRAM `0x1000` -> IMEM `0x000`, 8 bytes.
2. Commit B while A is BUSY: `0x2000` -> `0x080`, 8 bytes. FULL becomes 1.
3. Write only new address registers for C: `0x3000` -> `0x100`.
4. Observed pending state changes from B to C while FULL remains 1.
5. Completing A promotes C. IMEM `0x080` remains untouched and C later writes
   IMEM `0x100`.

This directly rejects immutable identity at B's length-register commit in ares.

### Case 2: third length commit while BUSY+FULL

With A active and B pending, C's address registers are programmed and the read
length register is written again with a 16-byte length. Pinned ares keeps FULL=1
but the pending descriptor becomes C with the new addresses and length. After A
finishes, C is promoted and writes both 8-byte payloads; B never executes.

This is executable ares behavior, not an asserted hardware rule.

### Case 3: count/skip and handoff

The current request copies two 8-byte rows from RDRAM `0x4000` and `0x4010` with
`0x4008` deliberately skipped. A second request is already pending.

After the first `dmaTransferStep()`:

- current remains the same request;
- count changes from 1 to 0;
- DRAM advances to `0x4010`;
- BUSY=1 and FULL=1.

After the second step:

- both rows of the first request are complete;
- the pending descriptor is already current;
- BUSY remains 1 and FULL becomes 0.

Thus BUSY has no observable falling edge between the two requests.

### Case 4: IMEM wrap

A 16-byte transfer starts at IMEM `0xff8`. The fixture observes the first payload
at `0xff8` and the second at `0x000`; the final PBUS address is `0x008`. Provenance
for such a request must use two modulo-bank spans rather than one ordinary range.

## Reproducibility receipt

Authoritative successful workflow run:

- GitHub Actions run: `37847044886`
- job: `113550383534`
- branch commit under test: `934f4a6caf6179feee3a742cef3de98f0926497e`
- runner: Ubuntu 24.04.5, image `20261004.327.1`
- exact ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- exact Mupen64Plus: `ba95bab92a76744753bfe61470823a4937850ab0`
- exact Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- driver SHA-256: `264eb52fe4bdd0444ad33fb9f31c87e72dddb7d224c425b19024e15c81366000`
- repeated reference stdout SHA-256:
  `035d27347ecbfcc421044da3b9c808460c82a58767b39c3ad6ab152fe797a156`
- `results.json` SHA-256:
  `513ddacabb7e8dec121fb6f3783d260b0671230ced070b772eddede94711fde0`
- uploaded evidence ZIP SHA-256:
  `5961cf4b893a1b2454594e595137d8b555a710d8336bb0e233e4ac641c37c25d`
- artifact ID: `11580128023`

The first workflow run `37846838471` produced the identical behavioral stdout and
`results.json` hashes but the job was marked failed because the shell attempted to
`tee target/sp-dma-lifecycle-run.log` before creating `target/`. The executable
experiment itself printed PASS. Commit `934f4a6c...` fixed only that evidence-log
plumbing, and the second run completed green.

Reproduce locally with:

```bash
python3 spikes/034-ares-sp-dma-lifecycle/run.py
```

## Architectural consequences

For Plaid's executable-provenance chronology:

1. Do not equate an SP length-register write with an immutable transfer identity
   unless the chosen oracle/hardware contract proves that enqueue semantics.
2. For pinned ares instrumentation, either track pending-descriptor mutations or
   assign the stable descriptor identity on `pending -> current` promotion.
3. Do not use a BUSY falling edge as the sole per-transfer completion witness.
4. One transfer identity must own every count/skip row until that current request
   finishes.
5. Represent destination effects as modulo-bank spans; crossing IMEM `0xfff`
   wraps inside IMEM rather than becoming a linear DMEM/IMEM range.
6. Keep the source backing-read witness from the earlier validated IMEM provenance
   work attached to each completed low-level fragment, then group those fragments
   under this higher-level request identity only when the request lifecycle itself
   is known.
7. Treat FULL-overflow semantics as unresolved hardware behavior. Mupen/Gopher's
   snapshot-and-reject agreement is evidence against promoting ares's overwrite
   behavior into production semantics without a hardware/systemtest oracle.
8. Across save-state restore, preserve/restore any Plaid transfer identity in lock
   step with the serialized upstream DMA descriptor or cut the identity and fail
   closed; silently retaining an external token while upstream state is restored
   independently would be unsound.

## Remaining unknowns

- Real N64 behavior for writes to SP address/length registers while BUSY+FULL is
  unresolved here. Pinned ares disagrees with both pinned Mupen and Gopher64.
- Mupen and Gopher64 were source-inspected, not executed as second behavioral
  oracles in this spike.
- `n64-systemtest` source corroborates wrap but was not executed, and no existing
  pinned test was identified for the full-FIFO discrepancy.
- Full CPU/RSP scheduler and interrupt timing under real games remains outside this
  component fixture.
- CPU writes interleaved with a multi-row DMA were not tested here.
- Reverse SP -> RDRAM transfers are not an executable-origin proof and were not the
  focus of this result.
- Reset/NMI/debugger mutation and actual save/restore execution were not exercised.
- This does not prove exhaustive RSP task/microcode reachability or whole-ROM
  closure.

## Recommendation

**PRIMARY-INTEGRATOR-REVIEW.**

Adopt the request-lifecycle proof obligations (no BUSY-edge shortcut, group
count/skip rows, explicit wrap spans, stable identity only after descriptor state
is actually stable). Do **not** adopt ares's pending-overwrite/FULL behavior as an
N64 architectural rule. Track that discrepancy as a targeted hardware/systemtest
follow-up before production semantics depend on it.
