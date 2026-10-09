# RSP promoted-transfer microcode installation lifetime

Date: 2026-10-09

Status: **VALIDATED** for the bounded exact-pinned-ares scope below.

## Question

Can Plaid group already-validated 8-byte RDRAM -> RSP IMEM provenance fragments into one exact completed microcode-installation lifetime by binding them to the stable SP-DMA descriptor at `pending -> current` promotion, rather than using payload equality, programmed registers, or BUSY edges?

## Hypothesis

For pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, one external research token minted immediately after `dma.pending` is copied to `dma.current` can own every completed IMEM fragment of that exact request until its final count row drains. A complete installation certificate is valid only after all fragment coordinates derived from the promoted descriptor have matching successful RDRAM-read + IMEM-write witnesses. Count/skip rows and 4 KiB IMEM wrap remain one request. Later overlapping IMEM mutation ends the exact resident-image lifetime even when replacement bytes are equal. Fetches before completion may have writer lineage but must not inherit a whole-installation certificate.

Result: **validated for this controlled scope.**

## Existing evidence composed by this experiment

`research/rsp-imem-provenance.md` already validated exact successful SP-DMA backing-read -> IMEM-fragment -> RSP-fetch lineage and showed that byte-identical reloads require distinct latest-writer generations.

`research/sp-dma-lifecycle.md` already showed that pinned ares pending descriptors are mutable until promotion, that count/skip rows stay under one current request, and that final-row completion can immediately promote pending inside the same `dmaTransferStep()` so BUSY need not be externally observed low between requests.

This spike tested the missing composition: whether the promoted descriptor is sufficient to derive, verify, and delimit the complete fragment set and its exact resident-image lifetime.

## Exact pinned source map

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStart`: when not busy and FULL is set, copies `dma.pending` to `dma.current`, copies direction into BUSY, clears FULL, then schedules `(length + 8) / 8 * 3` clocks. The experiment mints its research-only transfer token immediately after this promotion.
- `ares/n64/rsp/dma.cpp::RSP::dmaTransferStep`: for RDRAM -> IMEM, each 8-byte fragment performs `rdram.ram.read<Dual>(..., RBusDevice::SP_DMA)` followed synchronously by `imem.write<Dual>`, then advances DRAM and the 12-bit PBUS address. If `count` remains it decrements count, adds `skip` to DRAM and schedules the next row. Otherwise it clears BUSY, resets current length and calls `dmaTransferStart(*this)` inside the same function.
- `ares/n64/rsp/io.cpp::RSP::ioWrite`: SP address and length registers modify `dma.pending`; a length write sets FULL/direction and calls `dmaTransferStart`. Direct CPU-visible SP IMEM words bypass DMA and write IMEM after recompiler invalidation.
- `ares/n64/rdram/rdram.hpp::RDRAM::Writable::read`: the observer records a successful ordinary backing read after the underlying read has returned, not a programmed/requested address alone.
- `ares/n64/rsp/rsp.cpp`: the fetch observer runs after the existing instruction word is selected for the RSP pipeline and performs no extra guest read.

The generated observer shadows upstream files only in the build directory. It adds no fields to ares CPU/RSP/RDRAM objects and does not add guest memory or bus accesses.

## Durable experiment

Artifacts:

- `spikes/043-ares-rsp-microcode-lifetime/driver.cpp`
- `spikes/043-ares-rsp-microcode-lifetime/run.py`
- `spikes/043-ares-rsp-microcode-lifetime/README.md`
- `.github/workflows/research-rsp-microcode-lifetime.yml`
- branch `research/rsp-microcode-lifetime-gpt56sol`

The component fixture covers seven promoted transfers:

1. one 16-byte row producing two 8-byte IMEM fragments;
2. a two-row count/skip request with an RSP fetch between rows, before request completion;
3. one 16-byte transfer wrapping `0xff8 -> 0x000`;
4. transfer A to one IMEM destination;
5. equal-payload transfer B to the same destination, promoted immediately when A completes while external BUSY remains asserted;
6. a current request used to hold another pending descriptor;
7. the pending descriptor after its address fields are mutated, proving that the promoted state rather than its earlier length-commit state owns the later effects.

After transfer 5, a non-overlapping direct CPU IMEM write must preserve transfer 5's exact-image lifetime; an overlapping direct CPU IMEM write must terminate it.

The fixture records `handoff == [1,1,1,0]`: BUSY/FULL are `1/1` before transfer 4's final step and `1/0` after the same step has completed transfer 4 and promoted transfer 5. There is therefore no externally observable BUSY-low state available as a safe request delimiter in this case.

## Replay verifier

`run.py` derives the expected fragment sequence independently from the promoted descriptor:

- row bytes = `length + 8`;
- each row contributes 8-byte source/destination fragments;
- DRAM advances by row bytes and then `skip` between rows;
- PBUS/IMEM advances modulo 4096;
- one transfer owns all `count + 1` rows.

For each IMEM fragment, replay requires the immediately preceding successful SP-DMA RDRAM read to have the same transfer token, source address, width and payload. Completion is rejected unless the exact derived fragment sequence has appeared and all installed bytes still have that transfer as latest writer.

A completed certificate stores promotion sequence, completion sequence, exact fragment coordinates and a content hash. The content hash is deliberately not identity: transfers 4 and 5 have equal content hashes but remain separate causal generations.

Any later overlapping IMEM mutation ends the exact resident-image lifetime at that mutation event. Same-value writes would still end that exact causal generation because provenance is writer identity, not value equality.

## Adversarial cases

The exact-pinned run rejected all five forged histories:

1. delete one IMEM fragment but retain completion;
2. attribute one fragment to another transfer token;
3. reorder `promote B` before `complete A` at immediate handoff;
4. remove the overlapping direct-write event while retaining the changed later fetch;
5. replace transfer 7's promoted descriptor with the stale pre-mutation pending addresses.

This is important because a verifier that groups by BUSY edge, payload equality, or the descriptor as it looked at an earlier length-register write would accept at least one of those false histories.

## Deterministic observations

The hardened exact-pin run at Plaid commit `66169e16f384030ea1f80eceb4fcce4df2af8c4f` passed all assertions:

- seven promotion-scoped transfer identities produced seven complete certificates;
- transfer 1 derived fragments `(0x1000 -> 0x000)` and `(0x1008 -> 0x008)`;
- transfer 2's count/skip fragments were `(0x2000 -> 0x100)` and `(0x2010 -> 0x108)`, excluding poison source `0x2008`;
- a fetch from `0x100` after only row 1 had exact writer identity `2` but **no complete-installation certificate**;
- after row 2 completed, the later fetch at `0x108` had writer `2` and a valid complete-installation certificate;
- transfer 3 derived wrap fragments `(0x3000 -> 0xff8)` and `(0x3008 -> 0x000)` under one identity;
- transfers 4 and 5 installed byte-identical payload at the same destination but remained distinct transfer identities and lifetimes;
- the non-overlapping direct write did not end transfer 5's `0x200` certificate, while the overlapping direct write did and the next fetch resolved to the direct writer rather than transfer 5;
- transfer 7 froze the mutated promoted descriptor and installed from `0x7100 -> 0x3c0`; the originally committed pending destination at `0x380` remained unchanged from its pre-case value;
- all five adversarially forged histories were rejected.

Instrumentation-neutrality and determinism checks also passed: untouched baseline fixture state equaled observer fixture state, and two observer executions produced byte-identical JSON.

## Execution receipts

Authoritative hardened run:

- Plaid experiment commit: `66169e16f384030ea1f80eceb4fcce4df2af8c4f`
- Actions run: `37916060358`
- Actions job: `113772404053`
- conclusion: success
- generated `results.json` SHA-256: `5bc9212a187bbd31d8d472a62b346c9504fad2f081f03d1fb4042624cc6ab95a`
- evidence artifact: `11608884520`
- artifact archive digest: `sha256:a4b1e3c0b1f513ff08f8d8fbff148ca78b807a9d8f6d6a699248631b8247f071`

An earlier pre-hardening run also passed with result SHA-256 `cbfd8ab4b1ea7225309b63b00094fece261decf11ed1d3cae862fb38eff07ea0`; the only fixture hardening replaced an assumption that untouched IMEM started at zero with an explicit before/after unchanged-value check.

## Reproduction

Replay-model self-test only:

```bash
python3 spikes/043-ares-rsp-microcode-lifetime/run.py --self-test
```

Exact reference fixture with `.refs/ares` checked out at the pinned revision:

```bash
python3 spikes/043-ares-rsp-microcode-lifetime/run.py
```

The branch-only GitHub Actions workflow fetches the exact ares revision, runs syntax/model tests, executes the baseline/traced/repeat experiment, uploads evidence and fails the job if the exact-pin experiment fails.

## What this changes for Plaid

For the bounded ares-backed provenance model, Plaid can distinguish three states that must not be collapsed:

1. **fragment writer known**: one or more IMEM bytes have exact latest-writer provenance;
2. **promoted transfer active**: those fragments belong to one stable current SP-DMA request, but all declared rows/fragments may not yet exist;
3. **complete exact installed image**: every fragment derived from the promoted descriptor has a successful backing-read/write witness and all bytes are still resident with that transfer as latest writer.

Only state 3 supports a whole-installation certificate. A later overlapping mutation ends that exact-image lifetime and creates a patched/mixed successor state; matching payload does not preserve origin identity.

The transfer identity should be bound at the stable promoted `current` descriptor boundary, not inferred from a length-register commit or a later BUSY transition.

## Limitations / explicitly does not prove

- This validates exact pinned ares behavior in controlled identity-mapped RDRAM. It does not resolve real-hardware SP FIFO/FULL semantics; prior Plaid work already found ares disagrees with pinned Mupen64Plus/Gopher64 on FULL handling.
- It does not prove translated/degraded RDRAM source backing, save/load/reset/NMI/debugger token continuity, reverse SP DMA, every direct/subword IMEM mutation source, RSP recompiler behavior, or arbitrary full-system CPU/RSP scheduler interleavings.
- The ares row loop performs all 8-byte fragments of one row synchronously inside one `dmaTransferStep`; this fixture therefore does not establish guest execution between fragments of the same row. It does demonstrate partial executable residency between count/skip rows.
- It establishes RDRAM backing coordinates for SP-DMA input, not ultimate producer lineage of those RDRAM bytes.
- Dynamic fetches remain observations. They do not prove exhaustive RSP task/root reachability, all microcode generations in a title, or whole-ROM closure.
- The research-only external token is not serialized. Production save/restore handling must either serialize equivalent identity/history or fail closed across unsupported restore boundaries.

## Recommendation

**ADOPT** the proof obligation and identity rule, not the research instrumentation wholesale:

- mint/derive stable SP-DMA installation identity at a proven current-descriptor activation boundary;
- derive the complete expected destination/source fragment set from that stable descriptor;
- require successful causal backing-read + sink-write witnesses for every fragment before certifying a complete installed image;
- keep partial-residency provenance separate from complete-image certification;
- terminate an exact-image lifetime on any overlapping successful mutation, including same-value writes;
- never use content equality or BUSY falling edges as transfer/lifetime identity.

Production integration should remain fail-closed anywhere the stable transfer identity, completion boundary, successful fragment effects, or intervening mutation census is not available.
