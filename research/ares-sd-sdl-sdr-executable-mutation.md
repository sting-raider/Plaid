# VR4300 SD/SDL/SDR executable-byte mutation

Status: **VALIDATED for architectural byte effects, uncached RDRAM backing, misaligned-SD failure, and unmapped-TLB failure in the stated scope.** The original read-modify-write sub-hypothesis was **REJECTED** for pinned ares.

## Question

Plaid's current Mupen CPU store sensor observes only successful constant-address cached-RDRAM `SW`. Can `SD`, `SDL`, or `SDR` change executable bytes in ways that sensor misses, and what exact byte effect must a future general mutation witness represent?

## Exact references

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
  - `ares/n64/cpu/interpreter-ipu.cpp`: `SD`, `SDL`, `SDR`
  - `ares/n64/cpu/memory.cpp`: translation, reverse-endian physical lane mapping, cache/uncached write dispatch
  - `ares/n64/cpu/context.cpp`: endian/mode derivation
- Mupen64Plus Core: `ba95bab92a76744753bfe61470823a4937850ab0`
  - `src/device/r4300/mips_instructions.def`: independent big-endian `SDL`/`SDR` masks
  - `src/device/r4300/r4300_core.c`: masked aligned-dword write path
- Plaid baseline: `research/mupen-cpu-word-stores.md` documents the existing `SW`-only scope and explicitly leaves other store sizes unsensed.

No upstream reference is added as a Plaid dependency.

## Falsifiable hypothesis and correction

The useful part of the hypothesis survived: `SD`/`SDL`/`SDR` are a distinct executable-mutation class invisible to an `SW`-only witness, and endian-correct `SDL`/`SDR` pairs can materialize an arbitrary unaligned 64-bit payload.

One important premise did not survive source inspection. Pinned ares does **not** implement `SDL`/`SDR` as an architectural read-modify-write. It decomposes each instruction into aligned `Byte`/`Half`/`Word`/`Dual` writes and returns on the first failed write. Pinned Mupen expresses the same normal big-endian effect as a mask passed to `r4300_write_aligned_dword`, which emits two masked 32-bit memory writes. Untouched bytes therefore must retain their prior provenance; they should not acquire a fictitious load/read provenance edge merely because a host implementation needs to preserve them.

The first executable run also disproved my initial reverse-endian model: reverse endian changes the `SDL`/`SDR` lane direction, not merely the byte order of the payload.

## Experiment

Durable harness: `spikes/025-ares-sd-sdl-sdr/` on branch `research/sd-sdl-sdr-mutation-gpt56`.

The driver executes real guest opcodes through pinned ares' interpreter with the recompiler disabled. Successful cases target uncached direct RDRAM, so the post-state is actual RDRAM backing rather than a dirty D-cache line. The runner snapshots both guest-visible bytes and physical RDRAM bytes and checks a separately derived byte model.

Matrix:

- all 8 `SDL` offsets in big- and little-endian contexts;
- all 8 `SDR` offsets in both endian contexts;
- all 8 `SD` offsets in both endian contexts;
- endian-correct unaligned 64-bit pairs at all 8 starting offsets in both endian contexts;
- unmapped-TLB `SDL`/`SDR` at all offsets plus aligned `SD`, in both endian contexts;
- every case repeated twice and required to produce byte-identical JSON.

Total: **98 cases, 196 executions**.

GitHub Actions run `37800915448` on commit `06850bd30f3dbd59933ce1189fb79aca20de3341` passed. The generated result payload hash was:

```text
02ca3882b7067fc2101ce2d2a9e2b077d1d3f3afc003c9b159182010777ed9d3  target/ares-sd-sdl-sdr/results.json
```

## Byte truth table

Let `n = effective_address & 7`, let `Pbe` be the eight register bytes of the 64-bit payload in big-endian order, and `Ple` the same payload in little-endian memory order.

| Context | Instruction | Guest byte addresses changed within aligned 8-byte unit | Replacement bytes |
|---|---|---|---|
| big endian | `SDL` | `n..7` | `Pbe[0 : 8-n]` |
| big endian | `SDR` | `0..n` | `Pbe[7-n : 8]` |
| little endian | `SDL` | `0..n` | `Ple[7-n : 8]` |
| little endian | `SDR` | `n..7` | `Ple[0 : 8-n]` |
| either | aligned `SD` | all 8 | payload in that context's memory byte order |

Thus one `SDL` or `SDR` can replace any contiguous 1..8-byte edge subset of an aligned doubleword. This is strictly more expressive than an `SW`-only mutation witness.

### Unaligned 64-bit pair

For an arbitrary byte address `A`:

- big endian: `SDL rt, 0(A)` then `SDR rt, 7(A)`;
- little endian: `SDL rt, 7(A)` then `SDR rt, 0(A)`.

The matrix verified that these pairs replace exactly bytes `A..A+7` with the payload in the active memory byte order and leave neighboring bytes unchanged for all eight alignments. If `A & 3 != 0`, that eight-byte mutation intersects **three 32-bit instruction words**. If `A & 3 == 0`, it intersects two.

That gives a concrete adversarial counterexample to any executable-mutation representation that assumes one CPU store affects at most one instruction word.

## Failure behavior observed

### Misaligned `SD`

For offsets 1..7, in both endian contexts:

- ares raised Store Address Error (`ExcCode = 5`);
- no tested RDRAM byte changed.

Aligned offset 0 replaced all eight bytes.

### Unmapped TLB

For every `SDL`/`SDR` offset and aligned `SD`, in both endian contexts:

- ares raised TLB Store Miss (`ExcCode = 3`);
- the watched RDRAM backing remained byte-identical.

Because each ares `SDL`/`SDR` decomposition stays inside one aligned eight-byte unit, its component writes also stay inside one 4 KiB page. In the tested unmapped-page case the first translated subwrite failed before any backing mutation. This does **not** prove absence of partial effects for arbitrary MMIO/device behavior or every possible exception source.

## Independent source oracle

Pinned Mupen's normal N64 big-endian path reaches the same masks through a structurally independent implementation:

- `SDL`: derives `n = address & 7`, right-shifts the register value, and writes a low-bit mask covering `8-n` bytes;
- `SDR`: derives `n`, left-shifts the register value, and writes the complementary high-bit mask covering `n+1` bytes;
- `r4300_write_aligned_dword` splits the masked 64-bit write into two masked 32-bit handler writes.

This agrees with the big-endian byte truth table while differing materially from ares' Byte/Half/Word/Dual decomposition. I do **not** claim Mupen as an independent oracle for the synthetic reverse-endian cases.

## Consequence for Plaid

A successful-`SW` sensor is insufficient for executable closure. At minimum, a general CPU executable-mutation witness must be able to represent:

1. instruction kind or, preferably, the normalized successful byte effect;
2. effective virtual address and resolved destination identity/alias;
3. exact byte mask/span, including 1..8-byte partial stores;
4. exact replacement bytes or register-derived provenance for written lanes;
5. preservation of prior provenance for untouched lanes;
6. success/fault outcome, with no mutation emitted for the tested faulting cases;
7. chronology relative to cache state, because a cached store can mutate D-cache state without immediately changing RDRAM or an already resident I-cache line.

The normalized byte effect is safer than treating `SD`, `SDL`, and `SDR` as special cases downstream. It also composes naturally with relocation/patching and with provenance joins over multiple writes.

## Limitations / remaining unknowns

- Successful mutation runs deliberately used **uncached** RDRAM. They establish byte semantics and backing effects, not D-cache writeback/I-cache stale-line chronology. Existing cache-ordering research must be joined with this result.
- The little-endian matrix forces the pinned core's context endianness so lane behavior is executed, but it does not prove the complete guest-driven `Status.RE` + user/TLB setup path.
- No MMIO, SP memory, PIF memory, device-specific bus error, or cached store path is covered here.
- This does not prove that real games use these instructions for executable patching; it proves Plaid cannot soundly exclude them by architecture.

## Recommendation

**ADOPT** the byte-effect requirements into the future general executable-store/mutation witness. Do not model `SDL`/`SDR` as provenance-generating reads of preserved bytes. Keep cache chronology/backing-origin proof as a separate obligation.

## Primary-checkout reproduction

2026-10-08, x64 WSL Ubuntu/G++ 15.2: All 98 cases repeat and pass locally, retaining result SHA-256 `02ca3882b7067fc2101ce2d2a9e2b077d1d3f3afc003c9b159182010777ed9d3`. The independent byte-effect table agrees with actual uncached reference memory and fault outcomes. General cache/lifetime/source-value and legal reverse-endian execution-mode proofs remain open.
