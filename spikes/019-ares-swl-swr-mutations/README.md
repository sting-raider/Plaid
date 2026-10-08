# Spike 019: ares SWL/SWR executable-byte mutations

Status: `PARTIAL` overall. The original mechanism hypothesis was wrong, but the mutation-coverage conclusion was validated for the bounded source-derived scope.

## Question

Can Plaid treat ordinary `SW` observation as sufficient coverage for guest CPU writes that may create or patch executable bytes, or do VR4300 `SWL`/`SWR` require distinct byte-granular mutation evidence?

This spike also checks whether pinned ares D-cache dirty bits can safely stand in for the bytes actually changed by partial stores.

## Pins

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

The relevant pinned ares paths are:

- `ares/n64/cpu/interpreter-ipu.cpp` (`CPU::SWL`, `CPU::SWR`)
- `ares/n64/cpu/memory.cpp` (`reverseEndianPaddr`, `CPU::write`)
- `ares/n64/cpu/dcache.cpp` (`DataCache::Line::write`, cached write path)
- `ares/n64/memory/msb/writable.hpp` (backing byte/half/word placement)
- `ares/n64/rdram/debugger.cpp` and `ares/n64/rsp/debugger.cpp` (consumers of `line.dirty`)

Independent expected vectors come from pinned n64-systemtest `src/tests/endian_re/mod.rs`.

## Run

```sh
python3 spikes/019-ares-swl-swr-mutations/run.py

g++ -std=c++20 -O2 \
  spikes/019-ares-swl-swr-mutations/dirty_probe.cpp \
  -o /tmp/plaid-dirty-probe
/tmp/plaid-dirty-probe
```

Expected Python summary:

```text
PASS ares SWL/SWR partial-store executable-mutation model
  lane matrix:       16 / 16
  unaligned pairs:   4104 / 4104
  RE oracle vectors: 8 / 8
  cache/direct:      16 / 16
  prefix-fail cases: 4
  dirty mismatches:  8
  result_sha256:     6be968120d9231b6775c5bae0b8acdfa2838c148f6ee7ab799e48356184d1bb4
```

Expected C++ probe output:

```text
base=0 half_dirty=0006 word_dirty=0078
base=4 half_dirty=0060 word_dirty=0780
base=8 half_dirty=0600 word_dirty=7800
base=12 half_dirty=6000 word_dirty=8000
```

The C++ probe source SHA-256 used during this session was
`a5cbfcce4ed7b9d8d340f1f1d0bf2480b2c52199b933ccb5a7c6f96f6c985dfc`.

## What the experiment establishes

Pinned ares does **not** implement `SWL`/`SWR` as one read-modify-write. It decomposes each instruction into one or two successful byte/half/word writes, and checks the return value of every sub-write. There is no memory read in the interpreter implementation.

For big-endian mode, the virtual byte lanes changed inside the aligned word are:

| offset | SWL | SWR |
| ---: | --- | --- |
| 0 | 0,1,2,3 | 0 |
| 1 | 1,2,3 | 0,1 |
| 2 | 2,3 | 0,1,2 |
| 3 | 3 | 0,1,2,3 |

For reverse/little-endian mode they mirror:

| offset | SWL | SWR |
| ---: | --- | --- |
| 0 | 0 | 0,1,2,3 |
| 1 | 0,1 | 1,2,3 |
| 2 | 0,1,2 | 2,3 |
| 3 | 0,1,2,3 | 3 |

A big-endian `SWL value, 0(A)` plus `SWR value, 3(A)` materializes all four bytes of an arbitrary word at any `A & 3`. Reverse endian uses `SWR value, 0(A)` plus `SWL value, 3(A)`. The deterministic fixture checks all eight alignment/endian combinations plus 4096 seeded random 32-bit values, with no writes outside the four intended virtual bytes.

The reverse-endian physical-backing results match all eight pinned n64-systemtest `SWL`/`SWR` expected vectors. That upstream test itself exercises cached and uncached TLB mappings in 32-bit and 64-bit user modes. This spike compares against its checked-in oracle vectors; it does not claim a new real-hardware run.

For a clean resident D-cache line, cacheable partial stores modify only the cache model; backing memory remains unchanged until writeback. The same logical operation on an uncached sink changes backing immediately. Therefore an executable mutation witness must preserve the cache/backing distinction rather than treating instruction completion as an immediate RDRAM mutation.

## Dirty-mask counterexample

Pinned ares big-endian `SWR` offsets 1 and 3 intentionally call `write<Half>` / `write<Word>` with an unaligned address and alignment checking disabled. `DataCache::Line::write` selects the actual half/word slot using shifted address bits, which effectively aligns the storage slot down. However, it computes the byte dirty mask from the original unaligned low nibble:

```text
dirty |= ((1 << Size) - 1) << (paddr & 0xF)
```

The exhaustive 16-byte-line sweep finds eight mismatches: two forms at each of four aligned word positions. At the last word in a line, `SWR` offset 3 mutates actual lanes 12,13,14,15 while the `u16` dirty mask retains only lane 15.

This does not stop ares from writing back the line because normal D-cache writeback only needs `dirty != 0` and writes the full line. It **does** mean `line.dirty` is not a trustworthy byte-origin/mutation mask for these cases. The pinned RDRAM cache-coherency debugger and RSP DMA taint debugger both consume that mask, so research instrumentation must not reuse it as authoritative byte provenance.

## Failure semantics

Every emitted sub-write is guarded as `if(!write<...>(...)) return;`. A failed first access therefore produces no mutation. A synthetic rejection of the second sub-write in each two-write case leaves the first mutation in place, because the wrapper has no rollback. Normal RDRAM sub-writes stay within one aligned word and ordinarily share translation fate, so the second-write rejection is an adversarial control-flow property, not evidence that ordinary RDRAM commonly produces half-completed `SWL`/`SWR` instructions.

## Plaid implication

An `SW`-only sensor is categorically incomplete for executable mutation discovery. `SWL`/`SWR` can write strict byte subsets and paired forms can materialize an arbitrary unaligned instruction word. The safe observation boundary is the successful byte/half/word mutation after address translation/endian mapping, with explicit destination byte lanes and cache-vs-backing identity. Do not infer byte coverage from the opcode name, a full-word destination, or ares `line.dirty`.

See `research/ares-swl-swr-executable-mutations.md` for the source map, limitations, and integration recommendation.
