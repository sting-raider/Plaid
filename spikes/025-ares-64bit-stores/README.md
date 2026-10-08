# Pinned ares VR4300 64-bit store mutation experiment

Pin: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

Result: **VALIDATED** for the bounded store/cache semantics below. The initial
late-subwrite partial-commit sub-hypothesis is **REJECTED** for stable translation.

Full analysis: `research/ares-64bit-store-mutation.md`.

## Hypothesis

`SD`, `SDL` and `SDR` are executable-byte mutation classes absent from Plaid's
current constant aligned `SW` observation. `SDL`/`SDR` decompose one guest
instruction into one to three successful byte/half/word/doubleword writes, so a
mutation witness must describe actual byte lanes rather than infer an atomic
word-sized store from the opcode and effective address.

The initial claim also proposed that a later subwrite might fault after an earlier
subwrite committed. Exact pinned source inspection produced a counter-hypothesis:
every `SDL`/`SDR` subwrite is aligned and remains within one aligned 8-byte window.
With stable address translation, segment and minimum TLB-page boundaries therefore
cannot split those subwrites. The executable harness confirms invalid default-TLB
cases fail before RDRAM/D-cache mutation.

## Experiment

`model.py` independently transcribes the pinned handler decomposition and checks
all eight offsets in both endian modes plus paired unaligned 64-bit stores.

`driver.cpp` uses the separately built pinned ares interpreter with both CPU and
RSP recompilers disabled. For every store form/offset/endian combination it records
actual guest-visible bytes and raw RDRAM bytes for:

- uncached KSEG1 writes;
- cached KSEG0 writes, with the uncached alias used to distinguish dirty D-cache
  residency from backing RDRAM mutation;
- an unmapped default-TLB address to test failure before mutation;
- complete unaligned `SDL`/`SDR` pairs at target offsets 1..7.

`run.py` builds the exact pin via the existing spike-003 recipe, repeats every case
byte-identically, compares actual bytes against the independent model, checks
aligned `SD` versus address-error cases, and hashes the complete results.

## Reproduce

```text
python3 spikes/025-ares-64bit-stores/model.py
python3 spikes/025-ares-64bit-stores/run.py
```

Model result:

```text
PASS: decomposition widths/lane uniqueness and unaligned SDL+SDR pairs
sha256 768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e
```

Exact pinned-reference result from GitHub Actions run `37801439305`, job
`113394390287`, branch commit
`c41dc462f55bf12a0fbdc15a68b0f138d34c899b`:

```text
PASS: 158 repeated pinned-ares SD/SDL/SDR cases
results_sha256=cf8f82bde400e23c0f2225ee55baaf727b7f09b87c2ca2489c2e295aed6c5f1e
```

The branch-only workflow `.github/workflows/research-64bit-stores.yml` checks out
the exact ares revision and runs the same commands on Linux.

## Key observations

- successful uncached stores update raw RDRAM synchronously;
- successful cached stores update resident D-cache bytes and dirty state while raw
  RDRAM and the uncached alias still expose old backing bytes at the immediate
  post-store checkpoint;
- one `SDL`/`SDR` instruction may produce 1-3 concrete writes;
- paired `SDL`/`SDR` stores materialize an arbitrary unaligned 64-bit value across
  adjacent aligned 8-byte windows;
- invalid-TLB `SDL`/`SDR` cases fail before raw/D-cache mutation in the tested path;
- `readDebug<Byte>` is not an architectural guest-endian byte observer in this pin;
  the final harness uses normal CPU byte reads for guest view and debugger-backed
  RDRAM reads only for raw backing state.

## Scope

This is an interpreter/reference experiment, not a production Plaid sensor. It
does not prove complete store coverage, arbitrary TLB histories, legal
reverse-endian user/TLB mode, bus-device error semantics, LL/SC, COP1 stores,
DMA/copy provenance, reset/restore, I-cache visibility, source-byte provenance, or
executable lifetime closure. The result must not be promoted to a whole-ROM
mutation proof.
