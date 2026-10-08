# Spike 018: reset/cache lifetime boundaries

Result: **VALIDATED for the pinned ares implementation; not an N64-wide hardware claim.**

Reference revision: `ares` `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
Plaid base: `3cf45dc323cbcd9e6463ccc781d3de093a433097`.

## Hypothesis

Reset-like transitions are not interchangeable executable-lineage boundaries. In
particular, an NMI can preserve stale instruction-cache bytes, system reset can
clear I-cache residency while preserving RDRAM bytes, and save-state restore can
resurrect an older cache/RDRAM state.

## Source map

At the pinned revision:

- `ares/n64/system/system.cpp`: `System::power(reset)` calls
  `rdram.power(reset)` and later `cpu.power(reset)`.
- `ares/n64/rdram/rdram.cpp`: `RDRAM::power(reset)` runs `ram.fill()` and
  rebuilds chip/mapping state only under `if(!reset)`. With `reset == true`, RAM,
  chip state, and `mapIdentity` are not reinitialized by this function.
- `ares/n64/cpu/cpu.cpp`: `CPU::power(reset)` always calls
  `icache.power(reset)`.
- `ares/n64/cpu/cpu.hpp`: `InstructionCache::power(bool reset)` ignores the
  argument operationally and clears every line's `tagKey` and words while
  restoring deterministic index fields.
- `ares/n64/cpu/exceptions.cpp`: `Exception::nmi()` changes status/ErrorEPC/PC
  only. It does not touch I-cache or RDRAM.
- `ares/n64/cpu/interpreter-scc.cpp`: `ERET()` with ERL set returns to
  `epcError`, allowing execution to resume at the pre-NMI PC.
- `ares/n64/cpu/serialization.cpp`: all I-cache `tagKey`, `index`, and `words`
  fields are serialized.
- `ares/n64/rdram/serialization.cpp`: RDRAM bytes, identity-map flag, and chip
  state are serialized.
- `ares/n64/system/serialization.cpp`: unserialize may call `power(false)` first
  for synchronized states, then deserializes RDRAM and CPU, overwriting those
  freshly powered fields with the saved state.

## Adversarial experiment

`model.py` is a deliberately tiny direct transcription of only those state
transitions. It creates a cached word `0x11110000`, mutates backing RDRAM to
`0x22220000`, and proves the cache remains stale. Then it exercises NMI + ERET,
system reset semantics, a newer `0x33330000` backing mutation, and restoration of
the older snapshot.

Run:

```sh
python3 spikes/018-reset-cache-lifetime/model.py
```

Key assertions:

1. NMI leaves both cache and RAM digests unchanged.
2. ERET refetch returns stale `0x11110000` without a fill while RAM is
   `0x22220000`.
3. reset=true preserves the RAM digest but invalidates the cache; the next fetch
   fills and returns `0x22220000`.
4. after advancing RAM to `0x33330000`, restoring the old snapshot makes the
   old stale cache (`0x11110000`) and old RAM (`0x22220000`) reappear; the first
   post-restore fetch is a hit, not a fill.

Deterministic checkpoints:

- initial/stale/NMI/ERET cache SHA-256:
  `4400cfd587a469a9e8fa4757a3042115ada231d62499943fddc35d296ce4c211`
- RAM after `0x22220000` mutation:
  `8a2545e25ad42c710dc6c78c43afea5c55be2330332f00638db15b2914537a31`
- post-reset-refill cache SHA-256:
  `992261360b5cd14d4a2d1a6d84a36bfbb865d0a77b2befab5eff3cdc0c8c328c`
- newer RAM SHA-256:
  `8df03d19bcc929629b617f7d04500b3c0612d0cf9caa4d6eb0e8fc2aaa735bec`
- restored state returns to the first cache hash and `0x2222` RAM hash.

## Interpretation

There is no sound single reset-like `generation++` rule:

- **NMI:** not an I-cache or RDRAM byte-lifetime cut in this implementation.
- **System reset (`power(true)`):** an I-cache residency cut, but not an RDRAM
  byte-origin cut. Backing-byte lineage must survive it unless a later write
  proves otherwise.
- **Full power (`power(false)`):** explicitly reinitializes RDRAM in
  `RDRAM::power` and clears I-cache in `CPU::power`; exact initial RAM entropy is
  outside this spike.
- **Save-state restore:** not a monotonic lifetime cut. It can move execution
  backward to a previously serialized cache/backing state. A trace that spans
  restore needs an explicit chronology/restore epoch or branch plus restored
  state identity; pretending later events simply supersede earlier ones is
  unsound.

This argues for distinct cache-residency and backing-byte lineage domains rather
than one global executable generation counter.

## Limitations

The experiment is source-derived and deterministic; no upstream ares binary was
instrumented or executed in this environment. It validates the pinned source
semantics and their logical counterexample, not physical N64 reset behavior.
Other reset/NMI sources and hardware-level timing remain separate work. No claim
is made that a restored cache line was executed before restore; only that ares
can restore it and a subsequent matching fetch can hit it without a new fill.
