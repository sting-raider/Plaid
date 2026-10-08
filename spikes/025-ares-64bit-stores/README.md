# Pinned ares VR4300 64-bit store mutation experiment

Pin: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

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
cannot split those subwrites. The executable harness checks invalid default-TLB
cases for fail-before-mutate behavior rather than assuming partial commit.

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

Local model check:

```text
python3 spikes/025-ares-64bit-stores/model.py
PASS: decomposition widths/lane uniqueness and unaligned SDL+SDR pairs
model-result SHA-256: 768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e
model.py SHA-256: b56cec125a2f2c2bc1dad389207700d41359b1aceecf0d7debaa5a9a2d916fad
```

The full pinned-reference command is:

```text
python3 spikes/025-ares-64bit-stores/run.py
```

The branch-only workflow `.github/workflows/research-64bit-stores.yml` checks out
the exact ares revision and runs the same command on Linux.

## Scope

This is an interpreter/reference experiment, not a production Plaid sensor. It
does not prove complete store coverage, arbitrary TLB histories, bus-device error
semantics, LL/SC, FPU stores, DMA/copy provenance, reset/restore, or executable
lifetime closure. The result must not be promoted to a whole-ROM mutation proof.
