# SP-DMA RDRAM -> DMEM ingress provenance

Date: 2026-10-09

Status: **VALIDATED (bounded pinned-ares scope)**

## Conclusion

For pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a controlled
identity-mapped RDRAM -> SP DMEM read-DMA can mint exact latest-writer provenance
for the completed DMEM bytes when Plaid retains the actual successful RDRAM Word
transactions and the exact completed DMEM Word sinks under the active transfer.

The important distinction from the already validated IMEM path is structural:
for each 8-byte DMEM fragment, pinned ares performs two 32-bit RDRAM reads first
and only then performs the two 32-bit DMEM writes:

```text
read dram+0
read dram+4
write dmem+0
write dmem+4
```

Therefore a reducer that copies the IMEM path's "immediately preceding successful
read" rule is unsound for DMEM. The executable fixture makes both source Words
`0x11223344`; the first sink is for DRAM `0x1000`, while the nearest equal-valued
read is DRAM `0x1004`. The measured payload-only rule therefore chooses the wrong
producer despite all final bytes being correct.

A sound bounded join for this path needs the concrete source address/transaction
identity associated with each completed Word sink (or an equivalent transfer-row
and lane identity), not adjacency, current contents, descriptor equality, or
payload equality.

Every completed DMEM Word sink creates a fresh resident writer generation. A
byte-identical reload from a different RDRAM source therefore creates new writer
generations. Count/skip rows and modulo-DMEM wrapping are resolved by the actual
completed fragments. An out-of-range identity-RDRAM read that returns zero before
the successful-read observer leaves the resulting zero DMEM sink with UNKNOWN
backing origin. A later same-value CPU SP-memory Word write supersedes only the
bytes it actually writes.

This is a provenance result for completed effects. It is not a claim that ares's
internal read/write ordering is hardware timing, and it is not an RSP consumer
dataflow or executable-closure proof.

## Falsifiable hypothesis and result

Hypothesis:

> In exact pinned ares, each completed RDRAM -> DMEM SP-DMA Word sink can inherit
> backing origin only from the successful `RBusDevice::SP_DMA` RDRAM Word
> transaction for the exact source address and lane of that sink. Same-value
> reloads must advance writer identity; count/skip and DMEM wrap must follow
> actual completed fragments; missing successful backing reads remain UNKNOWN;
> later direct CPU DMEM writes replace only their concrete bytes. Descriptor or
> payload equality alone is insufficient.

Result: **VALIDATED for the controlled identity-mapped component fixture.**

The exact-pin executable run reproduced all positive cases, rejected all five
forged histories, preserved baseline/observer neutrality, and was byte-for-byte
deterministic across repeated traced executions. Two independent GitHub Actions
runs produced the same `results.json` SHA-256.

## Exact revisions

- Plaid canonical base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- research branch: `research/sp-dma-dmem-ingress-gpt56sol`
- branch head used by the authoritative pre-note run:
  `27caa460e70e694a7d59278d6031f185c1fa1bc7`
- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64 source comparison:
  `e96debac941a26ba4961e5145056c0821d3a56f7`

## Exact source map

### ares

`ares/n64/rsp/dma.cpp::RSP::dmaTransferStep` implements RDRAM -> SP read-DMA.
For DMEM (`pbusRegion == 0`) it:

1. reads `Word` at `dma.current.dramAddress + 0` with requester
   `RBusDevice::SP_DMA`;
2. reads `Word` at `dma.current.dramAddress + 4`;
3. writes the first Word to `dmem` at `dma.current.pbusAddress + 0`;
4. writes the second Word to `dmem` at `dma.current.pbusAddress + 4`;
5. advances both current addresses by eight bytes.

For count/skip, the same current request decrements `count`, adds `skip` to the
DRAM address between rows, and keeps the SP-memory address contiguous. The PBUS
address is `n12`, so it wraps modulo 4096 within the selected DMEM bank.

`ares/n64/rdram/rdram.hpp::RDRAM::Writable::read` on the controlled identity path
returns zero immediately when `address >= size`; that return occurs before the
successful backing read used by this spike's observer. An OOB DMA can therefore
produce a completed zero DMEM sink without a successful RDRAM-origin witness.

`ares/n64/rsp/io.cpp::RSP::writeWord` routes direct SP-memory Word writes to DMEM
when the bank bit is clear. The fixture uses this real path for a same-value CPU
overwrite after DMA and records the completed direct sink separately.

### Independent Gopher64 source comparison

Pinned Gopher64 `src/device/rsp_interface.rs::do_dma` also transfers RDRAM -> SP
memory in 4-byte units and masks the SP-memory address modulo the 4 KiB bank.
However, Gopher64 interleaves each RDRAM read with its corresponding SP write,
whereas pinned ares batches two reads before two writes.

This supports Word-granular source/sink accounting as a useful cross-reference
observation but explicitly rejects elevating ares's callback adjacency/order into
an N64-wide invariant. Production provenance should retain causal transfer/lane
identity rather than infer it from one emulator's incidental event spacing.

## Executed experiment

Durable fixture: `spikes/043-ares-sp-dma-dmem-ingress/`.

The fixture uses the existing headless ares component build, disables both CPU
and RSP recompilers, enables deterministic entropy, and forces the controlled
identity-mapped 8 MiB RDRAM path. The pinned checkout remains unmodified; the
runner generates observer shadows in the build output.

The observer records only already-completed facts:

- successful ordinary RDRAM reads whose requester is `SP_DMA`;
- completed DMEM `write<Word>` sinks, with the exact source DRAM address/lane
  used by the same pinned source statement;
- completed direct CPU-visible DMEM Word writes.

It performs no additional guest memory reads, clock steps, or serialization.

Run:

```bash
python3 spikes/043-ares-sp-dma-dmem-ingress/run.py
```

### Case 1: equal-valued two-Word fragment

RDRAM `0x1000` and `0x1004` both contain `0x11223344` and are transferred to DMEM
`0x000`/`0x004`.

The observed prefix is:

```text
read  0x1000 = 0x11223344
read  0x1004 = 0x11223344
sink  0x000  <- source 0x1000
sink  0x004  <- source 0x1004
```

For the first sink, a naive latest-equal-payload rule guesses source `0x1004`.
The correct source is `0x1000`. This is a direct counterexample to payload or
nearest-read provenance.

### Case 2: byte-identical reload

The same two Word values are loaded from RDRAM `0x2000`/`0x2004` back into DMEM
`0x000`/`0x004`. The bytes are unchanged, but each completed sink receives a new
writer generation and a new backing source.

### Case 3: count/skip

A two-row transfer starts at RDRAM `0x3000`, with eight source bytes skipped
between rows. The accepted source Words are:

```text
0x3000, 0x3004, 0x3010, 0x3014
```

Poison Words at `0x3008`/`0x300c` never acquire DMEM lineage. The destinations are
contiguous DMEM `0x020`, `0x024`, `0x028`, `0x02c`.

### Case 4: DMEM wrap

A 16-byte transfer starts at DMEM `0xff8`. The four Word origins resolve as:

```text
DMEM 0xff8 <- RDRAM 0x4000
DMEM 0xffc <- RDRAM 0x4004
DMEM 0x000 <- RDRAM 0x4008
DMEM 0x004 <- RDRAM 0x400c
```

This confirms that writer state must address the modulo-DMEM bank, not assume one
linear destination span.

### Case 5: OOB source remains UNKNOWN

A request from `rdram.ram.size` writes two zero Words to DMEM `0x060`/`0x064`.
There is no successful RDRAM read event for either source Word, so both sinks get
fresh resident generations with UNKNOWN backing origin rather than an invented
RDRAM source.

### Case 6: same-value CPU overwrite

After DMA populated DMEM `0x020`, the fixture performs a direct CPU SP-memory Word
write of exactly the value already present. The direct write creates a new writer
generation for `0x020..0x023`; neighboring `0x024..0x027` retain their earlier DMA
lineage. Value equality does not preserve producer identity.

## Replay verifier and adversaries

The replay reducer maintains 4096 latest-writer DMEM byte cells. Each completed
Word sink creates one sink generation and four byte records. A DMA sink receives
RDRAM origin only when a unique earlier successful `SP_DMA` Word read matches its
explicit source address, width and payload. If no such successful transaction
exists, the origin is UNKNOWN. Direct writes create their own generation.

Five deliberately forged histories are rejected:

1. equal-payload wrong-source substitution;
2. deletion of a successful backing read;
3. joining a skipped poison source Word;
4. forged CPU identity on the direct overwrite;
5. duplicate chronology ordinal.

The measured naive value-only counterexample is:

```text
sink sequence: 3
correct source: 0x1000
latest equal-valued read guess: 0x1004
```

## Reproducibility receipt

Authoritative successful branch-head run:

- GitHub Actions run: `37916353399`
- job: `113773379652`
- branch commit under test: `27caa460e70e694a7d59278d6031f185c1fa1bc7`
- exact ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- event count: `27`
- neutrality: `true`
- repeated traced output deterministic: `true`
- rejected forged histories: all five listed above
- `results.json` SHA-256:
  `618b9def7180d8eec2624d348bd33e7c1d99b836d8b767439dd966bca04861b1`
- uploaded evidence artifact ID: `11608689691`
- evidence ZIP SHA-256:
  `468a56223619f648b836d1dabac002c1e3ebae9eb398809cb7f3ca89858b254d`

A second successful workflow run, `37916320010` / job `113773270723`, executed the
same experiment from parent commit `f79c7d91f393a0de61dec5fa98fbd98297cb55f5`
and produced the identical `results.json` SHA-256. The only later branch change
before the authoritative run was documentation, so the duplicate receipt is a
useful independent-run determinism check.

## Architectural consequences

For this bounded path, Plaid should:

1. mint DMEM latest-writer generations at completed storage sinks, not at DMA
   request creation;
2. retain the exact successful backing transaction or equivalent stable
   transfer-row/lane identity for every four-byte DMEM DMA sink;
3. not infer source origin from nearest read, value equality, final DMEM contents,
   or the current/requested descriptor alone;
4. group the two four-byte sinks under the higher-level DMA request separately
   from their concrete writer generations;
5. create fresh generations for byte-identical reloads and same-value direct
   writes;
6. map count/skip and modulo-bank wrap from actual completed transfer progress;
7. preserve UNKNOWN backing origin when a destination sink completes without a
   successful source transaction witness;
8. allow later CPU/RSP/direct writes to supersede only the bytes they actually
   mutate;
9. keep emulator-internal event adjacency out of any hardware-level invariant.

These requirements compose naturally with the existing SP-DMA lifecycle result:
request identity and completion/grouping are higher-level structure, while this
result establishes concrete source -> DMEM sink lineage for completed Word effects.

## Limitations / explicitly not proved

- RDRAM is forced through the controlled identity-mapped path. Translated/degraded
  RDRAM modes are outside this result.
- The fixture drives the real ares SP DMA component directly; it does not prove
  complete game scheduler, interrupt, or contention timing.
- It does not resolve the existing ares vs Mupen/Gopher BUSY+FULL FIFO-policy
  disagreement.
- Gopher64 was source-inspected only, not executed as a second behavioral oracle.
- No hardware timing claim is made about ares reading both Words before either
  DMEM write.
- This does not prove RSP load/register dataflow from DMEM, decoded RSP producer
  identity, reverse DMEM -> RDRAM DMA provenance, CPU SP refetch provenance, or
  RSP IMEM executable identity.
- Save/restore, reset/NMI, debugger mutation, and unusual non-DMA DMEM mutators
  remain separate obligations.
- Dynamic controlled observations are not exhaustive reachability or a whole-ROM
  closed-world certificate.

## Recommendation

**ADOPT** the bounded provenance invariant and verifier obligations above. Keep the
spike as a reference oracle; do not merge its generated ares instrumentation as
production architecture. Production chronology should represent exact completed
source/sink identities and per-byte latest writers, while the higher-level DMA
request/lifetime model handles grouping separately.
