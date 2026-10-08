# Spike 036: ares dirty D-cache eviction lineage

This bounded experiment tests whether cached CPU-store provenance can survive until an ordinary D-cache index-conflict eviction, rather than only an explicit guest `CACHE` writeback.

Reference: exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.

## Hypothesis

A dirty outgoing D-cache line must be identified by its resident slot **and** physical tag/generation before replacement. On a conflict miss pinned ares writes the full 16-byte outgoing line to backing RDRAM, then fills and reuses the same slot for the incoming line. Therefore:

- current RDRAM bytes are not a source oracle for the outgoing line;
- the post-replacement contents of the cache slot are not a source oracle either;
- the dirty mask identifies which resident bytes were changed by cached stores, but the backing writeback still contains the entire 16-byte resident payload;
- a nominally clean resident byte can still overwrite newer backing data during a dirty full-line writeback;
- per-byte provenance must retain untouched fill-origin bytes alongside later store-origin bytes until the completed writeback boundary.

## Fixture

All bytes are synthetic and CPU/RSP recompilers are disabled.

Physical lines:

- source: `0x1000`, first word `0x11223344`;
- destination: `0x2000`, words `aabbccdd 01020304 11223344 55667788`;
- conflict: `0x4000`, words `cafebabe 0badf00d 89abcdef 13579bdf`.

`0x2000` and `0x4000` map to the same D-cache slot because pinned ares selects a line with `(vaddr >> 4) & 0x1ff`.

Guest sequence:

1. cached `LW` from source;
2. cached `SW` to destination, making only destination bytes 0..3 dirty;
3. uncached alias `SW` of `0xdeadbeef` to destination word 0, deliberately making current backing disagree with the dirty resident word;
4. uncached alias `SW` of `0xfeedface` to destination word 1, deliberately changing backing under a resident word whose dirty bits remain clear;
5. cached `LW` from the conflicting line, forcing destination writeback and immediate reuse of the same slot.

Expected backing/cache chronology is:

1. fill source line from `0x1000`;
2. fill destination line from `0x2000`;
3. uncached scalar backing write of `0xdeadbeef` to `0x2000`;
4. uncached scalar backing write of `0xfeedface` to `0x2004`;
5. dirty victim burst writeback to `0x2000` containing `11223344 01020304 11223344 55667788`;
6. fill conflicting line from `0x4000` into the same slot.

The final writeback is deliberately mixed-origin: bytes 0..3 came from the cached source load/store, while bytes 4..15 remain from the earlier destination-line fill. In particular, the clean resident word at `0x2004` overwrites the newer uncached backing value `0xfeedface` with its stale fill-origin value `0x01020304`. This makes the dirty mask insufficient as a description of physical backing mutation.

## Commands

```sh
python3 -m py_compile spikes/036-ares-dcache-eviction-lineage/model.py \
  spikes/036-ares-dcache-eviction-lineage/run.py
python3 spikes/036-ares-dcache-eviction-lineage/model.py
python3 spikes/036-ares-dcache-eviction-lineage/run.py
```

`run.py` requires `.refs/ares` to be exactly the pinned revision and clean. It builds an unmodified-reference baseline plus an instrumented generated copy of `rdram.hpp`. The pinned checkout itself is not patched.

The runner requires baseline, observer-disabled, observer-enabled and repeated observer-enabled final CPU/cache/RAM state to agree. The traced run must also be byte-identical across repetitions.

## Scope limits

This experiment covers only controlled identity-mapped RDRAM, one word-sized cached copy and one ordinary replacement miss. It does not prove behavior for remapped/degraded RDRAM, failed bus transactions, reset/serialization, reverse-endian modes, partial/dual stores, other CPUs/devices, decompression, general dataflow, or exhaustive executable closure.
