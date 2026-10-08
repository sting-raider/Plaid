# ares SWL/SWR executable-byte mutation coverage

Date: 2026-10-08

Result: `PARTIAL`

Recommendation: `ADOPT`

Worker: `gpt56sol-partial-word-stores-20261008`

## Scope

This note asks one bounded question: what byte-mutation evidence is required so Plaid cannot miss executable bytes written by VR4300 `SWL`/`SWR`, and can pinned ares byte-dirty metadata safely stand in for those mutations?

It does not claim coverage for the rest of the CPU store family (`SB`, `SH`, `SD`, `SDL`, `SDR`, `SC`, `SCD`, COP1 stores), DMA, RSP writes, MMIO side effects, or arbitrary self-modifying-code lifecycle closure.

## Hypothesis disposition

The starting hypothesis contained two separable claims.

1. **`SWL`/`SWR` are implemented as aligned read-modify-write operations.** `REJECTED` for pinned ares. `CPU::SWL` and `CPU::SWR` perform no memory read. They explicitly emit one or two Byte/Half/Word writes and return immediately if any sub-write fails.
2. **An `SW`-only executable-store sensor is insufficient, and sound coverage needs successful byte-granular mutation evidence.** `VALIDATED` for this bounded class. Single `SWL`/`SWR` instructions write strict byte subsets, while conventional pairs materialize arbitrary unaligned 32-bit values.

A third question emerged during falsification:

3. **ares `DataCache::Line::dirty` can identify the exact bytes modified by these stores.** `REJECTED`. Big-endian `SWR` offsets 1 and 3 produce a repeatable mismatch between actual storage lanes and the dirty-byte mask.

The overall result is therefore `PARTIAL`: the proposed mechanism was wrong, while the architectural coverage conclusion was strengthened.

## Exact pins

Plaid `refs.lock.toml` pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

No conclusions below depend on unpinned upstream HEAD behavior.

## Pinned ares source map

### `ares/n64/cpu/interpreter-ipu.cpp`

`CPU::SWL` / `CPU::SWR` are the semantic entry points used by this experiment. Depending on endian mode and `vaddr & 3`, they emit one or two `write<Byte/Half/Word>` calls. Each call is guarded by `if(!write(...)) return;`.

Important special case: big-endian `SWR` passes `alignedError=false` for all of its generated writes. Offsets 1 and 3 therefore send an unaligned half/word address deeper into the memory path rather than trapping on alignment.

### `ares/n64/cpu/context.cpp`

`Context::setMode()` selects configured big-endian behavior in kernel/supervisor mode and `configuration.bigEndian ^ status.reverseEndian` in user mode. Reverse-endian user mode is therefore a real CPU context, not a test-only fiction.

### `ares/n64/cpu/memory.cpp`

`reverseEndianPaddr<Size>` maps reverse-endian accesses with XOR 7/6/4 for Byte/Half/Word. `CPU::write(PhysAccess, data)` applies that mapping, then sends cacheable writes to `dcache.write` and uncached writes to `busWrite`.

This distinction is provenance-critical: a completed cacheable partial store mutates D-cache state, not backing RDRAM at that moment.

### `ares/n64/cpu/dcache.cpp`

`DataCache::Line::write<Size>` selects a storage element from `bytes`, `halfs`, or `words`. Half/word indexing uses shifted address bits and therefore identifies the aligned containing half/word even if the incoming `paddr` is deliberately unaligned.

It then records:

```text
dirty |= ((1 << Size) - 1) << (paddr & 0xF)
```

The dirty mask uses the original unaligned `paddr`. That difference is observable for big-endian `SWR` offsets 1 and 3.

Normal D-cache miss/eviction logic only tests `line.dirty` as nonzero before writing back the entire line, so the mismatched byte mask does not by itself prevent backing writeback.

### `ares/n64/memory/msb/writable.hpp`

Backing Byte/Half/Word helpers mask addresses to their natural alignment and store values MSB-first. This gives the same actual lane span used by the source-derived model.

### `ares/n64/rdram/debugger.cpp`

Homebrew-mode cache-coherency diagnostics intersect a requested byte mask with `line.dirty`. Thus `line.dirty` is consumed as byte-granular metadata in debugger logic, not merely a boolean everywhere.

### `ares/n64/rsp/debugger.cpp`

`RSP::Debugger::dmaReadWord` also intersects RSP DMA byte ranges with `line.dirty` and propagates the selected dirty bits into DMEM/IMEM taint metadata. Therefore Plaid research instrumentation must not assume this existing mask is an authoritative byte-origin witness for partial stores.

## Independent pinned oracle

Pinned n64-systemtest `src/tests/endian_re/mod.rs` contains reverse-endian `SWL`/`SWR` expected backing-memory vectors. Its partial-store test loops over:

- cached and uncached TLB mappings;
- 32-bit and 64-bit user mode;
- all four instruction offsets.

The Plaid spike reproduces the eight `SWL`/`SWR` expected vectors exactly from the pinned ares semantics. This is an independent checked-in expected-value oracle. The current session did **not** execute a fresh n64-systemtest run on real N64 hardware, so these results must not be presented as new hardware measurements.

## Experiment

Durable spike: `spikes/019-ares-swl-swr-mutations/`

Files:

- `run.py`: executable source-derived lane/backing model, seeded fuzzing, independent oracle comparison, cache-vs-backing fixture, failure injection, and dirty-mask sweep.
- `dirty_probe.cpp`: minimal C++ reproduction of the pinned `DataCache::Line::write` indexing and `u16 dirty` expression.

Commands used:

```sh
python3 spikes/019-ares-swl-swr-mutations/run.py

g++ -std=c++20 -O2 \
  spikes/019-ares-swl-swr-mutations/dirty_probe.cpp \
  -o /tmp/plaid-dirty-probe
/tmp/plaid-dirty-probe
```

Environment observed in the research container:

- Python 3.13.5
- g++ 14.2.0

Deterministic Python result:

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

`run.py` Git blob on the research branch: `959c992e07cb3675610ad4ae6cc842bc0507a813`.

The session-local C++ probe source SHA-256 was `a5cbfcce4ed7b9d8d340f1f1d0bf2480b2c52199b933ccb5a7c6f96f6c985dfc`.

## Byte-lane results

The lane numbers below are virtual byte offsets inside the containing aligned word.

### Big-endian

| `vaddr & 3` | `SWL` | `SWR` |
| ---: | --- | --- |
| 0 | 0,1,2,3 | 0 |
| 1 | 1,2,3 | 0,1 |
| 2 | 2,3 | 0,1,2 |
| 3 | 3 | 0,1,2,3 |

### Reverse/little-endian

| `vaddr & 3` | `SWL` | `SWR` |
| ---: | --- | --- |
| 0 | 0 | 0,1,2,3 |
| 1 | 0,1 | 1,2,3 |
| 2 | 0,1,2 | 2,3 |
| 3 | 0,1,2,3 | 3 |

These are not merely masks on one conceptual full-word transaction. Several cases are emitted as two ordered sub-writes with different sizes and addresses.

## Arbitrary unaligned executable word construction

For big-endian mode:

```text
SWL value, 0(A)
SWR value, 3(A)
```

For reverse/little-endian mode:

```text
SWR value, 0(A)
SWL value, 3(A)
```

The spike checks every `A & 3` for both endian modes with `0x11223344`, then 4096 seeded random 32-bit values. All 4104 cases reproduce the exact four intended virtual bytes and leave the surrounding tested bytes untouched.

This directly falsifies any discovery rule equivalent to “watching `SW` is enough to see 32-bit code materialization.” A ROM can construct an arbitrary unaligned instruction word using no `SW` opcode at all.

## Cacheable versus backing mutation

For a clean resident D-cache line, the experiment treats the cache image and backing image separately, matching pinned `CPU::write` routing:

- cacheable `SWL`/`SWR`: mutate the D-cache image; backing remains byte-for-byte unchanged until explicit writeback;
- uncached `SWL`/`SWR`: mutate the backing image immediately;
- after writing back the controlled clean line, backing agrees with the direct-path result for all 16 endian/instruction/offset cases.

This is intentionally a clean-line fixture. It does not attempt to re-prove the already-separate dirty-victim/fill/writeback chronology problem owned by other active research claims.

## Dirty-mask counterexample

The full 16-byte D-cache-line sweep finds exactly eight mismatches, all in big-endian `SWR`:

- offset 1 halfword, once at each aligned word position in the line;
- offset 3 word, once at each aligned word position in the line.

Representative cases:

```text
word base +0, SWR off1: actual lanes [0,1], dirty bits [1,2]
word base +0, SWR off3: actual lanes [0,1,2,3], dirty bits [3,4,5,6]
word base +12, SWR off1: actual lanes [12,13], dirty bits [13,14]
word base +12, SWR off3: actual lanes [12,13,14,15], dirty bits [15]
```

The compiled C++ probe confirms the exact `u16` masks:

```text
base=0 half_dirty=0006 word_dirty=0078
base=4 half_dirty=0060 word_dirty=0780
base=8 half_dirty=0600 word_dirty=7800
base=12 half_dirty=6000 word_dirty=8000
```

The last case matters disproportionately for provenance: three actually changed cache bytes are absent from `line.dirty`.

## Failure behavior

Every generated sub-write is checked before proceeding. The fixture verifies that rejecting the first write leaves memory unchanged in every case.

Four endian/instruction/offset combinations use two sub-writes. An adversarial failure injected before the second write leaves the first write applied, because the instruction wrapper has no rollback. This proves only a control-flow/transactionality fact. Under ordinary RDRAM mappings both sub-writes remain within one aligned word and normally share translation fate, so this spike does not claim to have observed a real second-sub-write-only RDRAM fault.

## Required Plaid mutation witness

For this store class, the useful semantic event is not “opcode SWL/SWR completed” and not “D-cache dirty mask changed.” A future executable-write observer should be able to represent each successful sub-mutation with at least:

```text
observer sequence / chronology key
source CPU PC
source instruction identity (optional diagnostic field)
original guest virtual address
translated physical address presented to the sink
actual destination byte lanes after endian/alignment behavior
payload bytes for those lanes
cacheable vs uncached route
sink identity: D-cache resident bytes vs backing bus/RDRAM
cache-line resident identity/generation when the sink is cache
```

For a cached sink, later backing provenance still requires a separate verified cache-writeback join. For an uncached RDRAM sink, the successful backing write can be immediate evidence. This recommendation composes with the separate active cache/backing chronology work rather than replacing it.

Most importantly, derive actual lanes from the successful storage mutation itself. Do not substitute:

- opcode nominal width;
- original unaligned address plus nominal width;
- `DataCache::Line::dirty`;
- current RDRAM contents after the fact.

## What remains unknown

- `SDL`/`SDR` are structurally similar but were not exhaustively modeled here.
- `SB`, `SH`, `SD`, `SC`/`SCD`, and COP1 stores still need their own coverage in the general executable-write observer.
- This session did not compile and execute the full pinned ares tree with added instrumentation, because the bounded question was answerable from exact pinned source plus a deterministic model and independent pinned systemtest vectors. Dynamic whole-emulator neutrality therefore remains outside this spike.
- No claim is made that ares `line.dirty` mismatch affects ordinary full-line writeback correctness; the demonstrated risk is byte-granular debugger/taint/provenance use.
- No new physical-hardware run was performed.

## Integration recommendation

`ADOPT` the architectural requirement that executable mutation discovery observe successful byte-granular sink mutations and cover `SWL`/`SWR`, with cache residency distinguished from backing memory.

`REJECT` any implementation that treats the current SW-only Mupen sensor or ares `DataCache::Line::dirty` as complete byte-level executable-write provenance.

The primary integrator should transplant the requirement, tests, and the dirty-mask counterexample into the eventual general CPU-store mutation observer rather than merging this standalone model as production emulator logic.
