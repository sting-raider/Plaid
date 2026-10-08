# Spike 034: pinned-ares SP DMA lifecycle

Status: **PARTIAL / executable result obtained**

This spike extends the validated RDRAM -> RSP IMEM byte-provenance work in
`spikes/018-ares-rsp-imem-provenance/` by asking what constitutes one higher-level
SP-DMA transfer identity.

The experiment does **not** instrument ares. It drives the exact pinned ares RSP
MMIO and `dmaTransferStep()` implementation directly through the existing
headless component fixture, runs the same fixture twice, and checks the resulting
DMA descriptors and IMEM effects. A separate source guard compares the exact
pinned ares, Mupen64Plus and Gopher64 implementations.

## Reproduce

The standard runner expects the reference checkouts under `.refs/` at the exact
revisions in `refs.lock.toml`:

```bash
python3 spikes/034-ares-sp-dma-lifecycle/run.py
```

The research workflow performs those exact fetches automatically:

```text
.github/workflows/research-sp-dma-lifecycle.yml
```

## Cases

1. **Pending descriptor mutation after FULL**
   - Start request A (`RDRAM 0x1000 -> IMEM 0x000`).
   - Commit request B while A is busy (`0x2000 -> 0x080`).
   - Without another length write, write new SP/DRAM address registers for C
     (`0x3000 -> 0x100`).
   - In pinned ares, the full pending descriptor itself changes from B to C.
     When A finishes, C is promoted and B never executes.

2. **Third length write while BUSY+FULL**
   - Start A and fill the pending slot with B.
   - Program C's addresses and write the read-length register again.
   - Pinned ares does not reject a third request. The one pending slot is
     overwritten/recommitted as C, including its new length. C is later promoted.

3. **Count/skip plus current -> pending handoff**
   - The first current request uses two 8-byte rows with one skipped 8-byte source
     region.
   - `dma.current` remains one descriptor across both rows.
   - On the final row, ares clears `busy` and immediately promotes the pending
     request in the same `dmaTransferStep()` call. There is therefore no externally
     observable `BUSY=0` state between two queued requests.

4. **IMEM wrap**
   - A 16-byte transfer starting at IMEM `0xff8` writes eight bytes at `0xff8`
     and eight bytes at `0x000` because `pbusAddress` is 12 bits.
   - The final current PBUS address is `0x008`. The transfer must be represented as
     wrapped destination spans, not one ordinary linear IMEM interval.

## Cross-reference result

Pinned Mupen64Plus and Gopher64 disagree with ares on the dangerous FIFO-full
cases. Both copy the register values into an explicit second FIFO entry when the
second request is pushed, and both reject a third push while FULL (Mupen logs and
returns; Gopher64 panics). Later address-register writes therefore do not mutate
the already-snapshotted second FIFO entry in those implementations.

This is deliberately recorded as a discrepancy, not averaged into a fictional
consensus. The ares behavior is an exact oracle fact for that implementation but
is **not** established as N64 hardware behavior.

The pinned `n64-systemtest` suite independently contains SP-memory DMA overflow
cases stating and testing that a DMA which crosses the end of IMEM wraps within
IMEM rather than spilling into DMEM. That corroborates the wrap requirement, but
this spike did not execute that hardware-oriented suite and it does not resolve
the FIFO-full discrepancy.

## Implication for provenance identity

The original hypothesis that a pinned-ares pending request could simply be
snapshotted at its length-register commit is rejected. In ares, that descriptor
can still be mutated while FULL. A sound observer for this exact implementation
must either:

- track every mutation of the pending descriptor until it is promoted to
  `dma.current`, assigning the stable transfer identity at that promotion; or
- instrument a higher-level accepted-request abstraction whose semantics are
  independently proven to match hardware.

For any implementation, completed transfer identity must not be inferred from a
BUSY falling edge alone: ares can hand current -> pending off without exposing one.
Count/skip rows must remain children of one request identity, and wrapped IMEM
writes must be represented as separate modulo-4096 spans.

## Files

- `driver.cpp`: actual pinned-ares component fixture, no reference instrumentation.
- `source_guard.py`: exact-revision/source guards for ares, Mupen64Plus and Gopher64.
- `run.py`: build, repeat-determinism assertions, behavioral assertions, evidence JSON.
- `.github/workflows/research-sp-dma-lifecycle.yml`: exact-pin CI reproduction.

Generated build products and `results.json` live under ignored `target/`; no ROM,
firmware or giant trace is committed.
