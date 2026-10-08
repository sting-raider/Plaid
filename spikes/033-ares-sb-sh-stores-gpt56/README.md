# Spike 033: pinned ares VR4300 SB/SH executable-byte mutations

Bounded question: can ordinary `SB`/`SH` stores mutate executable bytes in ways missed by Plaid's historical aligned-`SW` sensing, and what exact byte/backing/cache/fault boundaries must a normalized mutation witness preserve?

Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

The independent `model.py` checks byte-lane selection for offsets 0..7 in big- and controlled little-endian contexts. `driver.cpp` executes the real pinned ares interpreter handlers with both recompilers disabled. `run.py` builds the exact pinned reference using the existing spike-003 build helper, executes every logical case twice, rejects nondeterminism, and checks raw RDRAM separately from cached guest state.

Matrix:

- `SB` and `SH`;
- offsets 0..7;
- big- and little-endian CPU contexts;
- uncached RDRAM, cached RDRAM, and unmapped TLB destinations;
- odd-address `SH` address-error negatives;
- `SB` x4 and `SH` x2 construction of the same arbitrary 32-bit word without any `SW` instruction.

Run:

```sh
python3 spikes/033-ares-sb-sh-stores-gpt56/model.py
python3 spikes/033-ares-sb-sh-stores-gpt56/run.py
```

No upstream ares source is patched. The experiment therefore does not need an instrumented-vs-uninstrumented neutrality comparison; it executes the unmodified exact pin directly. Repeated JSON equality is still required for every case.

The little-endian direct-handler half is a controlled semantic probe. The independent pinned `n64-systemtest` reverse-endian user-mode matrix is the stronger checked-in oracle for architecturally legal RE mode. This spike does not claim a fresh physical-N64 measurement.
