# Executable RSP IMEM reverse-DMA lineage

Verdict: **VALIDATED** for the controlled exact-pinned ares fixture. General N64
hardware behavior, complete IMEM producer coverage, arbitrary DMA concurrency,
and whole-ROM executable closure remain unproved.

## Question

Can a completed SP write-DMA whose source bank is executable RSP IMEM be
causally attributed to the current per-byte IMEM writer generations without
using payload equality as provenance, including same-value rewrites,
count/skip, an equal-payload decoy, and the 12-bit source-offset wrap?

The important adversarial edge is a descriptor starting at SP address `0x1ff8`.
A naive provenance implementation could observe the 12-bit source offset wrap
to `0x000` and silently relabel the second fragment as DMEM. That is not how the
exact pinned reference represents this DMA.

## Exact revisions

Plaid base for the isolated branch:

- `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned references inspected:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
- Mupen64Plus core `ba95bab92a76744753bfe61470823a4937850ab0`

The executable experiment is under
`spikes/047-ares-rsp-imem-dma-egress/` on
`research/rsp-imem-dma-egress-gpt56sol`.

## Source contract and independent comparison

At the exact ares pin, `ares/n64/rsp/io.cpp` latches the SP memory selection into
separate DMA fields: bits 3..11 become the 12-bit `pbusAddress` offset while bit
12 becomes `pbusRegion`. `ares/n64/rsp/rsp.hpp` stores those as separate
`n12 pbusAddress` and `n1 pbusRegion` fields.

In the write-DMA branch of `ares/n64/rsp/dma.cpp`, a set `pbusRegion` performs an
`imem.read<Dual>(dma.current.pbusAddress)` followed immediately by a completed
`rdram.ram.write<Dual>(..., RBusDevice::SP_DMA)`. The 12-bit address then
advances by eight. Because the bank is a separate field, wrapping that offset
does not itself select DMEM.

The checked-in `source_guard.py` fails closed against the exact ares and
Gopher64 pins and records source hashes. Exact pinned Gopher64 independently
latches `offset = dma.memaddr & 0x1000` and indexes the moving source as
`offset + (mem_addr & 0xfff)`, again keeping bank identity separate from the
wrapped offset.

Exact pinned Mupen64Plus was also inspected independently. Its
`src/device/rcp/rsp/rsp_core.c` fixes `spmem` to `sp->mem +
(dma->memaddr & 0x1000)` once for the DMA and wraps only
`(memaddr ^ S8) & 0xfff` while copying. This is a third emulator-source agreement
on the same structural rule. Agreement among emulators is corroborating
reference evidence, not hardware truth.

## Fixture

The exact-pinned ares headless fixture disables recompilers and initializes all
4096 IMEM bytes deterministically. It also initializes DMEM independently and
places `0xfeedface` and `0xc001d00d` at DMEM `0x000..0x007` so that an incorrect
bank switch at the wrap boundary produces observably different data.

The fixture then performs these actual CPU-visible IMEM writes through
`rsp.writeWord`:

1. phase 1: a same-value Word rewrite at IMEM `0x040`;
2. phase 2: changed Words at `0x044`, `0x048`, and `0x04c`;
3. phase 3: a newer equal-payload 8-byte decoy at `0x080..0x087` matching the
   true first DMA source `0x040..0x047`;
4. reverse DMA from SP `0x1040` to RDRAM `0x1000`, two 8-byte rows with
   `count=1` and `skip=8`, yielding destination rows `0x1000` and `0x1010`;
5. phase 4: changed Words at IMEM `0xff8`, `0xffc`, `0x000`, and `0x004`;
6. reverse DMA from SP `0x1ff8` to RDRAM `0x2000`, sixteen bytes spanning
   IMEM `0xff8..0xfff` then IMEM `0x000..0x007`.

The observer reuses existing generated SP-word and identity-RDRAM completion
callbacks. It performs no guest memory read, clock step, decode, reset,
serialization, or object-layout mutation. For each completed IMEM-source SP DMA
sink it records the live descriptor region, wrapped source offset, destination,
length/count/skip and completed value. Source identity is selected from the
live descriptor and the exact guarded immediate IMEM-read/sink sequence before
payload is used as an integrity check.

## Reproduction

Fetch the exact revisions from `refs.lock.toml` into `.refs/ares` and
`.refs/gopher64`, then run:

```bash
python3 -m py_compile \
  spikes/047-ares-rsp-imem-dma-egress/run.py \
  spikes/047-ares-rsp-imem-dma-egress/verify.py \
  spikes/047-ares-rsp-imem-dma-egress/source_guard.py
python3 spikes/047-ares-rsp-imem-dma-egress/source_guard.py
python3 spikes/047-ares-rsp-imem-dma-egress/run.py
```

GitHub Actions run `37920899821` executed those checks on Ubuntu 24.04 and
passed. The exact ares source hashes reported by the guard were:

- `ares/n64/rsp/dma.cpp`:
  `b5d8a1c4b45c2d84c487d98725caa465ac4b5fbea4761beff51ca1a1ba93d7b6`
- `ares/n64/rsp/io.cpp`:
  `60cc9b1efb2e90c127098a736c5213ea0bf77d2e3bd6e5b112e55752289af860`
- `ares/n64/rsp/rsp.hpp`:
  `03d72d15b7cf3cf1c50615996be2dd1918b08e9af61098c599e16871e1adbe00`
- Gopher64 `src/device/rsp_interface.rs`:
  `a5864c02f742bc922284d7866bbe76fe80efda63d3a3c69af7e37c50fe661053`

## Deterministic observations

The successful run reported:

- 14 ordered provenance events;
- 10 completed CPU-visible IMEM Word sinks;
- 4 completed IMEM-source SP-DMA RDRAM Dual sinks;
- source/destination sequence:
  - IMEM `0x040` -> RDRAM `0x1000`, descriptor count 1, skip 8;
  - IMEM `0x048` -> RDRAM `0x1010`, descriptor count 0, skip 8;
  - IMEM `0xff8` -> RDRAM `0x2000`;
  - IMEM `0x000` -> RDRAM `0x2008`;
- every DMA source retained region 1, including the wrapped `0x000` fragment;
- 32 exported bytes attributed to actual CPU-visible IMEM writer generations;
- zero exported bytes attributed to the initial IMEM generation;
- the phase-1 same-value rewrite remained a distinct sink (`seq=1`);
- the equal-payload decoy was present and newer, but did not change source
  identity;
- no competing RDRAM writes in the controlled destination windows;
- all 9 deliberate history forgeries rejected;
- baseline, sensor-disabled, sensor-enabled and repeated-enabled final state
  matched exactly;
- repeated enabled raw output was byte-identical.

Hashes:

- event history SHA-256:
  `6d7b5637b7c2e3c0180fbd9828cc95d8d087026b4877a60818f0ba604b0c8ce5`
- bounded RDRAM egress SHA-256:
  `c2cd1728c8d35065c95eb223c0e0d2fffdc5ac78d895e4bf19051680246fd795`
- `results.json` SHA-256:
  `65032064adabbd8d5b0f0c3593021ddb465bb5bfa42782c19ddfbc372b3c8eb8`
- enabled trace SHA-256:
  `f7515a50835b69df0edcfd12b44b2da0011507e2572ac40bf203a12f1a282f89`
- uploaded Actions evidence ZIP SHA-256:
  `606f29004313554572995714f888e5b47cbd57d13458acf2ef01abb2c147280f`

## Adversarial replay

The fail-closed verifier rejects nine measured-history mutations:

1. delete the successful same-value executable rewrite;
2. redirect the first DMA to the newer equal-payload `0x080` decoy;
3. flip the first DMA source bank to DMEM;
4. flip the post-wrap `0x000` source bank to DMEM;
5. forge the post-wrap source offset back to `0xff8`;
6. delete a changed executable writer;
7. move a DMA sink into the count/skip hole;
8. corrupt a completed DMA payload;
9. corrupt event chronology.

The equal-payload forgery is important: payload equality remains true while the
claimed source identity is wrong, and replay rejects it. Provenance therefore
does not reduce to a value lookup.

## Result

For this exact pinned ares path, a completed reverse SP DMA sourced from IMEM can
be joined to current per-byte executable-memory writer generations using ordered
IMEM sink history plus the live promoted DMA descriptor and completed RDRAM sink.
The bank bit must remain part of descriptor/source identity independently of the
12-bit source offset. Same-value executable writes mint new generations. Payload
matching is only an integrity check after source identity is established.

The naive assumption that an IMEM DMA source crossing offset `0xfff -> 0x000`
therefore crosses into DMEM is **REJECTED** by the executed exact-pinned ares
fixture and is structurally contradicted by all three inspected pinned emulator
implementations.

## Limits and explicit non-claims

This does **not** prove hardware-wide SP DMA semantics. No hardware oracle was
run. Emulator agreement is not hardware truth.

The dynamic trace does not emit a separate callback for the IMEM source read.
Instead, source selection is derived from the live descriptor at the completed
RDRAM callback and guarded against the exact pinned source sequence in which the
IMEM Dual read immediately precedes that sink without descriptor mutation in
between. A future production-grade event model may prefer an explicit source-read
witness if it needs to survive implementation refactors without source guards.

The fixture does not cover FIFO overlap, competing CPU/RSP writes during an
in-flight DMA, save/restore, reset, arbitrary timing interleavings, non-CPU IMEM
writers, all SP-register producers, RSP-generated IMEM mutation, or transfer
failure/cancellation modes. It proves neither complete executable mutation
coverage nor executable lifetime closure.

Nothing here promotes a reference emulator into Plaid production, changes the
production architecture, certifies ProgramMap closure, or enables a native-complete
flag. Generated reference shadows, binaries and raw traces remain research-only.
