# SP DMEM/IMEM fetch backing provenance

Date: 2026-10-08

Plaid selection base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`.
Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
Worker branch: `research/sp-fetch-backing-gpt56`.
Verdict: **PARTIAL**.

## Question

Can Plaid attach a trustworthy SP-memory byte witness to a VR4300 instruction
fetch without confusing the fetch physical address with byte origin, and what
mutations must invalidate that witness?

The falsifiable hypothesis was restricted to direct uncached CPU fetches from SP
DMEM/IMEM in pinned ares with both recompilers disabled. It explicitly predicted
that cached aliases would fail the same witness rule.

## Source-backed result

The hypothesis is supported for the source routing contract and its cached-alias
counterexample.

At the pinned revision:

1. `CPU::fetch` in `ares/n64/cpu/memory.cpp` sends a direct uncached fetch to
   `busRead<Word>(paddr)`. A cached fetch instead enters `icache.fetch`.
2. `Bus::read` in `ares/n64/memory/bus.hpp` sends ordinary physical SP reads to
   `rsp.read<Size>`.
3. `RSP::readWord` in `ares/n64/rsp/io.cpp` returns the selected DMEM/IMEM backing
   word. Address bit `0x1000` is the bank selector.
4. CPU-visible SP writes pass through `RSP::writeWord` and mutate the selected
   backing bank.
5. RDRAM-to-SP DMA in `ares/n64/rsp/dma.cpp` writes directly to DMEM/IMEM, so a
   complete mutation history cannot rely only on `RSP::writeWord`.
6. N64 `Bus::readBurst<ICache>` supports RDRAM through `0x03ffffff`, not SP memory.
   A cached SP miss reaches `freezeUncached` rather than an SP backing read.

Exact inspected blob IDs are recorded in
`spikes/024-ares-sp-fetch-backing/README.md`.

This establishes an important policy boundary: a physical address in the SP
range is not itself a byte-origin witness. The cache policy and actual device
transaction matter.

## Executed adversarial contract

`spikes/024-ares-sp-fetch-backing/source_contract.py` makes only the inspected
routing rules executable. It is intentionally not an N64 emulator.

The local worker run passed and Python bytecode compilation succeeded. The tested
cases are:

- same low address offset with deliberately different DMEM and IMEM words;
- uncached DMEM and IMEM fetches paired to the exact preceding backing read;
- successful overlapping CPU write changing the next fetched word;
- successful SP-DMA write changing the next IMEM fetched word;
- neighboring CPU write leaving the fetched word unchanged;
- cached KSEG0 SP alias producing no SP backing witness.

Worker-local source-contract SHA-256 before the durable formatting cleanup was
`cb01fbc9c347ecc42a9fe9364c4f3179a2c8a29f2ba2f0006b5822a4685ac6f2`.
The terminal result was:

```text
PASS: SP source-contract chronology: DMEM/IMEM distinct; CPU/DMA writes bound generations; cached SP fetch has no backing witness
```

## Candidate evidence semantics

If an actual reference sensor validates neutrality and event ordering, the
smallest safe evidence primitive is a per-read witness rather than an inferred SP
image:

- CPU fetch virtual PC;
- translated physical word address;
- uncached/direct access policy;
- selected bank: DMEM or IMEM;
- exact completed word returned by the SP device read;
- shared chronology ordinal tying the SP read to the following fetch;
- later overlapping successful write events, classified at least as CPU-visible
  SP write or SP-DMA write.

A fetch may inherit that witness only from the exact compatible observed read.
A successful overlapping mutation ends the old backing lifetime. A write to a
non-overlapping word does not. Cached, unsupported, ambiguous or missing-read
paths remain unknown.

Do **not** infer an executable generation merely because consecutive reads have
the same bytes. Equal payloads can belong to different write/DMA histories.
Likewise, a DMA write proves a destination mutation but does not by itself prove
the ultimate origin of its RDRAM source bytes.

## Why not VALIDATED

The worker container had neither a usable `.refs/ares` checkout nor outbound DNS.
The connected GitHub API was sufficient to inspect the exact pinned files, but it
cannot substitute for compiling and running the instrumented reference. Therefore
this session did not establish:

- observer neutrality against an uninstrumented ares binary;
- actual runtime adjacency/reentrancy properties of a shared event ordinal;
- complete CPU store-size/subword mutation coverage;
- PIF/IPL2 producer provenance for SP contents;
- source lineage through the RDRAM side of SP DMA;
- reset/restore/serialization boundaries;
- RSP instruction-fetch identity/lifetimes.

The spike README gives the concrete instrumentation and differential run required
to close the first two gaps.

## Architectural consequence

This result should prevent one unsound implementation immediately: **never assign
SP byte origin from physical address alone**. For the declared pinned-reference
scope, uncached CPU SP fetches have a plausible exact transaction witness point;
cached SP accesses do not share that proof and must remain open.

No production `ProgramMap`, solver or authoritative architecture document is
changed on this worker branch. The primary integrator should reproduce the actual
ares sensor run before promoting a new production provenance/lifetime rule.
