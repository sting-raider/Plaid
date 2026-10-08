# ares VR4300 SD/SDL/SDR executable-byte mutation semantics

Status: **VALIDATED** for the bounded pinned-reference scope below. The initial
late-subwrite partial-commit sub-hypothesis is **REJECTED** for stable translation.

Plaid base inspected: `codex/executable-discovery` at
`3cf45dc323cbcd9e6463ccc781d3de093a433097`.

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
from `refs.lock.toml`.

Research branch: `research/64bit-store-mutation-gpt56`.

Executable experiment: `spikes/025-ares-64bit-stores/`.

## Question

Plaid's current CPU-store evidence is narrower than the architectural mutation
surface. In particular, can `SD`, `SDL`, and `SDR` rewrite executable bytes in
ways that cannot be represented as one aligned `SW`, and what does pinned ares
actually do at cache, endian, and fault boundaries?

The falsifiable starting hypothesis was:

1. `SD`/`SDL`/`SDR` are distinct executable-byte mutation classes;
2. `SDL`/`SDR` can decompose one guest instruction into multiple concrete memory
   writes;
3. cached and uncached forms do not create the same backing mutation event;
4. a later `SDL`/`SDR` subwrite might fault after an earlier subwrite has already
   committed.

Items 1-3 were validated. Item 4 was rejected for stable translation in the
pinned ares implementation.

## Pinned source map

### CPU instruction handlers

`ares/n64/cpu/interpreter-ipu.cpp`

- `SD` calls one `write<Dual>`.
- `SDL` and `SDR` branch on CPU endian and `vaddr & 7`.
- A single `SDL`/`SDR` instruction becomes one to three ordered
  `write<Byte/Half/Word/Dual>` calls.
- Every subwrite is naturally aligned and every touched byte remains inside the
  same aligned 8-byte window.

The exact handler-level decompositions are below. `B/H/W/D` mean
Byte/Half/Word/Dual; `+N` is the address offset from `vaddr & ~7`; `>>N` is the
right shift of the 64-bit source value before the write.

### Big-endian handler decomposition

| `vaddr&7` | `SDL` | `SDR` |
|---:|---|---|
| 0 | `D+0 >>0` | `B+0 >>0` |
| 1 | `B+1 >>56; H+2 >>40; W+4 >>8` | `H+0 >>0` |
| 2 | `H+2 >>48; W+4 >>16` | `H+0 >>8; B+2 >>0` |
| 3 | `B+3 >>56; W+4 >>24` | `W+0 >>0` |
| 4 | `W+4 >>32` | `W+0 >>8; B+4 >>0` |
| 5 | `B+5 >>56; H+6 >>40` | `W+0 >>16; H+4 >>0` |
| 6 | `H+6 >>48` | `W+0 >>24; H+4 >>8; B+6 >>0` |
| 7 | `B+7 >>56` | `D+0 >>0` |

### Little-endian handler decomposition

| `vaddr&7` | `SDL` | `SDR` |
|---:|---|---|
| 0 | `B+0 >>56` | `D+0 >>0` |
| 1 | `H+0 >>48` | `W+4 >>24; H+2 >>8; B+1 >>0` |
| 2 | `B+2 >>56; H+0 >>40` | `W+4 >>16; H+2 >>0` |
| 3 | `W+0 >>32` | `W+4 >>8; B+3 >>0` |
| 4 | `B+4 >>56; W+0 >>24` | `W+4 >>0` |
| 5 | `H+4 >>48; W+0 >>16` | `H+6 >>8; B+5 >>0` |
| 6 | `B+6 >>56; H+4 >>40; W+0 >>8` | `H+6 >>0` |
| 7 | `D+0 >>0` | `B+7 >>0` |

### Translation and cache path

`ares/n64/cpu/memory.cpp`

- normal CPU reads/writes apply the context's endian lane transform;
- cacheable writes route to `dcache.write`;
- uncached writes route synchronously to `busWrite`;
- a CPU write returns `false` only when address translation/alignment rejects the
  access before the cache/bus write path.

`ares/n64/cpu/dcache.cpp`

- a cacheable store mutates D-cache resident bytes and dirty mask;
- backing RDRAM is not synchronously updated by that store;
- backing changes occur later through D-cache writeback transactions.

`ares/n64/memory/bus.hpp`

- ordinary `Bus::write` is `void`; an RCP/bus freeze is not propagated as a
  `false` return to the already-translated CPU store helper.

`ares/n64/cpu/tlb.cpp`

- the minimum mapped page is 4 KiB;
- a translation failure happens before a concrete cache/bus write;
- because all `SDL`/`SDR` subwrites remain within one aligned 8-byte window, a
  stable mapping cannot let an early subwrite succeed and a later one cross into
  another minimum TLB page or segment.

## Executable experiment

`spikes/025-ares-64bit-stores/model.py` independently transcribes the handler
lane decomposition and checks all eight offsets in both endian modes plus complete
unaligned 64-bit pairs.

Model command:

```text
python3 spikes/025-ares-64bit-stores/model.py
```

Deterministic result:

```text
PASS: decomposition widths/lane uniqueness and unaligned SDL+SDR pairs
sha256 768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e
```

`driver.cpp` links against a separately built exact pinned ares checkout. CPU and
RSP recompilers are disabled. `run.py` executes every case twice and rejects any
byte difference between repetitions.

The exhaustive matrix contains 158 logical cases:

- 2 endian modes;
- 3 store forms (`SD`, `SDL`, `SDR`);
- 8 offsets;
- cached and uncached destinations;
- unmapped-TLB fault cases for every form/offset;
- complete unaligned `SDL`/`SDR` pairs for target offsets 1 through 7.

Full command:

```text
python3 spikes/025-ares-64bit-stores/run.py
```

GitHub Actions run `37801439305`, job `113394390287`, on branch commit
`c41dc462f55bf12a0fbdc15a68b0f138d34c899b` checked out exact ares commit
`9408cb43d4948fc3ea6e152a307a34348df3fe04` and reported:

```text
PASS: 158 repeated pinned-ares SD/SDL/SDR cases
results_sha256=cf8f82bde400e23c0f2225ee55baaf727b7f09b87c2ca2489c2e295aed6c5f1e
```

## Findings

### 1. `SD`/`SDL`/`SDR` are real mutation coverage gaps

An aligned-word-only `SW` observation is not sufficient to establish executable
immutability. `SD` writes eight bytes, while `SDL`/`SDR` can write arbitrary
prefix/suffix subsets of an aligned 8-byte window.

A complete unaligned 64-bit value can be materialized across adjacent aligned
8-byte windows using an `SDL`/`SDR` pair. The executable test validates target
byte offsets 1 through 7 in both endian modes while preserving the immediately
adjacent bytes.

### 2. One guest store is not necessarily one memory transaction

Pinned ares decomposes one `SDL`/`SDR` instruction into one, two, or three ordered
writes. A mutation/provenance sensor below the instruction layer may therefore see
multiple events for one architectural store.

For Plaid, transaction evidence should preserve enough ordering/grouping context
to avoid silently inventing an atomic aligned-word store that never existed.

### 3. Cacheable and uncached stores have different backing chronology

For every successful uncached case, the guest-visible bytes and the uncached alias
changed immediately and raw RDRAM backing changed synchronously.

For every successful cached case, the cache-resident guest view changed and the
D-cache line became dirty, while both raw RDRAM and the uncached alias retained the
old bytes at the immediate post-store checkpoint.

Therefore instruction/value/effective-address intent is not itself a backing
mutation witness. A later dirty-line writeback is a distinct chronological event
that must be joined if Plaid needs actual RDRAM byte provenance.

### 4. Late same-instruction translation partial commit is rejected here

The initial claim deliberately looked for the nastier failure mode: one
`SDL`/`SDR` subwrite succeeds, then a later subwrite faults and leaves only a
strict prefix committed.

That does not arise from normal stable address translation in this pinned path:
all subwrites are aligned, remain inside one aligned 8-byte window, and therefore
cannot newly cross a 4 KiB TLB or segment boundary. Unmapped-TLB cases in the
executable matrix faulted before changing raw RDRAM or creating a dirty D-cache
line. Unaligned `SD` similarly raised Address Error Store before mutation.

This is a rejection of that specific pinned-reference mechanism, not a universal
claim about every conceivable asynchronous state mutation or real-hardware fault.

### 5. Debugger byte reads are an instrumentation trap in little-endian mode

The first executable attempts intentionally failed because the harness used
`readDebug<Byte>` as if it represented guest-visible byte order. In pinned ares,
normal CPU accesses apply the context endian lane transform while the debug helper
does not. The final harness observes guest bytes through normal CPU reads and raw
backing separately.

This matters for future instrumentation: debugger convenience APIs must not be
silently treated as architectural byte-lane or provenance oracles.

## Plaid implication

A sound executable-mutation policy should not stop at aligned `SW`. At minimum it
needs a general store/mutation representation capable of expressing:

- `SD` eight-byte writes;
- `SDL`/`SDR` byte masks and ordered subwrites;
- cached resident mutation distinct from later backing writeback;
- uncached synchronous backing writes;
- endian/alias context;
- grouping from concrete transaction(s) back to the architectural store when that
  relationship is available.

This result supports broadening executable-store observation rather than adding a
special-case `SD` flag beside the existing `SW` path. The important abstraction
is byte-range mutation with chronology and backing provenance.

## Limitations / remaining unknowns

- Little-endian handler execution in this harness directly sets the CPU context to
  little endian while using direct KSEG addresses. That is a controlled handler
  semantics probe, not a claim that little-endian kernel KSEG operation is a
  normal N64 software mode. Architecturally legal reverse-endian user/TLB mode is
  a separate address-mode validation problem.
- The experiment does not cover `SB`, `SH`, `SWL`, `SWR`, `SCD`, COP1 stores,
  arbitrary TLB histories, LL/SC, RSP stores, DMA/copies, decompression, or device
  register side effects.
- It proves immediate cache/backing behavior for the tested pinned ares path, not
  that a later I-cache fetch observes newly written backing bytes. I-cache
  residency/invalidation remains a separate chronology obligation.
- It does not prove source-byte provenance for the value being stored.
- It does not prove whole-ROM executable closure or N64-wide hardware behavior.

## Recommendation

**ADOPT** the bounded semantic result and use it to shape the general executable
mutation/backing-event model. Do not merge this research branch wholesale; the
primary integrator should transplant the byte-mask/order requirements into the
canonical mutation instrumentation and verifier design, then reproduce against
current integration state.
