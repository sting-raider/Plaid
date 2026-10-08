# Bounded ares SP fetch-backing contract

Result: **PARTIAL**.

Plaid base at selection time: `3cf45dc323cbcd9e6463ccc781d3de093a433097` on
`codex/executable-discovery`.
Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Hypothesis

With both recompilers disabled, a VR4300 instruction fetch through an uncached
direct segment to physical SP DMEM/IMEM is synchronously backed by the exact
selected SP word in pinned ares. A provenance sensor can therefore join that
backing read to the subsequent CPU fetch without issuing another guest read.
Successful CPU or SP-DMA writes to that word must end the previous byte lifetime.
Cached SP aliases must not inherit the same rule unless an independently observed
cache-fill path proves their resident bytes.

## Pinned source path

The following files were inspected at the exact pinned revision:

- `ares/n64/cpu/memory.cpp`, blob
  `f362ef67ab41ccf57330bbedd6f614e07a61dd17`: `CPU::fetch` sends uncached
  fetches to `busRead<Word>(paddr)` and cached fetches to `icache.fetch`.
- `ares/n64/memory/bus.hpp`, blob
  `367308207719c1048daa1bbf7ffca635ca0c97d5`: ordinary SP-range reads dispatch
  to `rsp.read<Size>`, but N64 `readBurst<ICache>` only accepts RDRAM through
  `0x03ffffff`; a cached SP fill falls into `freezeUncached`.
- `ares/n64/rsp/io.cpp`, blob
  `19bf54735fdfcf622374b1533c6c6e966b5ea51a`: `RSP::readWord` selects IMEM
  when address bit `0x1000` is set and DMEM otherwise; `RSP::writeWord` mutates
  the same banks for CPU-visible SP writes.
- `ares/n64/rsp/rsp.hpp`, blob
  `3f05ea5e7b266245c2091dac8a7aad7680f1361d`, and
  `ares/n64/memory/msb/writable.hpp`, blob
  `a5e1ad2cebe78c465ec46964ce405ba5c9e81a90`: DMEM and IMEM storage returns
  big-endian byte-backed values.
- `ares/n64/rsp/dma.cpp`, blob
  `d49cbd601b68244eff6f088e68da2380c200aad9`: RDRAM-to-SP DMA writes directly
  into `dmem` or `imem`, so DMA is an independent mutation source that bypasses
  `RSP::writeWord`.

The important negative result is deliberate: **physical SP address alone is not
sufficient provenance**. Cached and uncached accesses with the same physical
address follow different paths in this reference. A generic rule that assigns
SP backing by physical address would fabricate a witness for cached SP execution.

## Executable adversarial contract

Run:

```text
python spikes/024-ares-sp-fetch-backing/source_contract.py
python -m py_compile spikes/024-ares-sp-fetch-backing/source_contract.py
```

Expected terminal line:

```text
PASS: SP source-contract chronology: DMEM/IMEM distinct; CPU/DMA writes bound generations; cached SP fetch has no backing witness
```

The fixture attacks five failure modes:

1. the same low offset in DMEM and IMEM contains different words, so losing the
   bank-select bit is detected;
2. an uncached DMEM fetch is immediately paired with the exact selected backing
   read;
3. a successful CPU write to that word changes the next witness;
4. an SP-DMA write to IMEM changes the next witness while a neighboring CPU write
   does not change the fetched word;
5. the cached KSEG0 alias receives **no** SP backing witness because the pinned
   N64 cache-burst path does not route to SP memory.

This script is a source-contract test, not an N64 emulator and not an independent
reference oracle. It exists to make the source-derived policy executable and to
catch future reasoning/model mistakes deterministically.

## Actual ares instrumentation needed for validation

A follow-up run in an environment with the pinned checkout should use the existing
`spikes/003-ares-oracle/run.py` build machinery and preserve a clean reference
checkout. The smallest useful instrumentation is:

1. in generated `rsp/io.cpp`, record the completed value returned by
   `RSP::readWord` for the DMEM/IMEM range, including bank, physical address,
   request thread identity and a shared monotonic research ordinal;
2. in generated `RSP::writeWord`, record completed CPU-visible SP writes only
   after the backing mutation;
3. in generated `rsp/dma.cpp`, record completed RDRAM-to-SP writes after the
   corresponding `dmem.write`/`imem.write` calls;
4. retain the existing CPU `instructionPrologue` fetch observer, with no extra
   guest read or translation;
5. compare baseline, sensor-disabled, sensor-enabled and repeated sensor runs for
   full CPU/timing/SP/RAM state and exact event-stream equality.

Required actual-reference fixtures are the same adversarial cases above, plus the
cached alias counterexample. The observer must fail closed if an SP fetch lacks
exactly one immediately preceding compatible SP read in the unified chronology.

## Why this is only PARTIAL

This worker's execution sandbox had no usable ares checkout and outbound DNS was
unavailable, so the generated reference instrumentation could not be compiled and
run here. The exact pinned sources were inspected through the connected GitHub
API, and the deterministic source-contract test passed locally, but observer
neutrality and actual runtime event order are therefore **not validated**.

This spike also does not prove:

- provenance of the bytes that PIF/IPL2 or another producer originally places in
  SP memory;
- RDRAM source lineage of bytes later copied by SP DMA;
- cached SP execution behavior as an N64 hardware invariant;
- reset/restore/serialization lifetime boundaries;
- RSP instruction execution identity or its IMEM universe;
- complete byte/subword mutation coverage;
- whole-ROM executable closure.

Do not promote an executable image generation from this result alone. The safe
candidate rule is narrower: an observed uncached CPU SP fetch may carry a
per-fetch SP backing witness only when the actual device read is observed and
matches the fetch; any successful overlapping CPU/SP-DMA mutation terminates that
witness lifetime, and cached/unsupported paths remain unknown.
