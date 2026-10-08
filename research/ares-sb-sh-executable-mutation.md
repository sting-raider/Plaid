# VR4300 SB/SH executable-byte mutation in pinned ares

Status: **IN PROGRESS** (exact-pin executable matrix pending at initial commit)

Claim: issue #4 worker `gpt56sol-sb-sh-mutation-20261009`.

## Hypothesis

Ordinary `SB` and `SH` are executable mutation sources that cannot be omitted by an SW-oriented sensor. In pinned ares, successful uncached identity-RDRAM stores should mutate exactly one/two backing bytes; successful cached stores should mutate D-cache residency only until writeback; reverse-endian mode should alter physical lane selection by the shared size-specific transform; and alignment/TLB failures should commit no mutation.

The experiment tries to falsify the exact-width and fault-before-write parts, not merely demonstrate that a store happened.

## Exact reference

`refs.lock.toml` pins ares at `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Relevant pinned source contracts:

- `ares/n64/cpu/interpreter-ipu.cpp`: `SB` calls `write<Byte>` and `SH` calls `write<Half>` with the low integer-register payload.
- `ares/n64/cpu/cpu.hpp`: virtual-address `write<Size>` devirtualizes before the physical/cache write.
- `ares/n64/cpu/memory.cpp`: requested alignment is checked before segment/TLB translation; little-endian mode maps Byte physical address with `paddr ^ 7` and Half with `paddr ^ 6`; successful cached stores go to `dcache.write<Size>`, uncached stores to `busWrite<Size>`.
- `ares/n64/cpu/dcache.cpp`: a successful resident write updates only the selected Byte/Half storage and sets dirty bits `((1 << Size) - 1) << (paddr & 0xf)`; a miss fills the line before the store.
- `ares/n64/rdram/rdram.hpp`: successful identity-mapped RDRAM writes call the underlying `Memory::Writable::write<Size>` and hidden-bit update.
- `ares/n64/memory/lsb/writable.hpp`: Byte and Half are distinct width-specific writes, not widened Word writes.

The spike's `source_guard.py` checks these exact snippets and emits SHA-256 hashes of all five files from the pinned checkout.

Pinned n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698` independently contains TLB store-miss and address-error coverage, but this bounded worker does not claim that its controlled forced-little-endian fixture proves the complete hardware Status.RE/user-mode path.

## Experiment

`spikes/036-ares-sb-sh-stores/` reuses the exact-pin headless ares build recipe from spike 003 and does not instrument ares.

Matrix:

- operations: `SB`, `SH`;
- offsets: 0..7;
- contexts: big endian and controlled little endian;
- destinations: uncached identity RDRAM, cached identity RDRAM, unmapped TLB virtual address;
- each case executes twice and must produce byte-identical JSON;
- independent Python lane model runs 100,000 deterministic randomized checks.

Assertions include exact logical guest bytes, exact changed backing indices, exact cache dirty lanes, odd-`SH` Address Store Error with no mutation, and aligned missing-TLB Store Miss with no mutation. The model also verifies that `SB` can touch every byte lane of a 32-bit instruction and the two aligned `SH` placements cover all four instruction bytes.

## Preliminary source conclusion

Source structure strongly supports the hypothesis, but the result remains unvalidated until the exact pinned executable matrix succeeds. In particular, production provenance must attach to the successful cache/backing mutation boundary rather than to opcode observation alone.

## Limitations / separate obligations

This slice does not cover SW/SWL/SWR/SD/SDL/SDR/SC/SCD/COP1 stores, RSP writes, DMA/copy/decompression provenance, D-cache writeback chronology, I-cache stale-line visibility, save-state/reset/debugger mutation, translated/degraded RDRAM modes, or full guest-driven reverse-endian setup. It establishes mutation semantics, not commercial-ROM prevalence or closed-world reachability.
