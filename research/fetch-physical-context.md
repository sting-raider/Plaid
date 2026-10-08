# Effective physical fetch context

2026-10-08. Hypothesis: the physical word address and cache selection already
computed by the pinned interpreter can distinguish mapping contexts without
changing guest behavior or inventing byte-source/executable-lifetime proof.

Spike 005 records the effective word address after translation and reverse-endian
lane selection, before the existing cache/bus fetch. The debugger callback pairs
it with the actual fetched word, 64-bit PC and slot state. No additional guest
read or translation occurs. CPU object layout and opcode sources stay unchanged;
generated sources and upstream notices remain isolated under ignored target/.

The focused fixture repeats exactly and checks seven accesses: a cached word,
the same cached word after a backing-RAM change, an uncached alias reading the
new word, invalidation exposing the new word, two TLB mappings for the same PC,
and a user reverse-endian fetch selecting the other physical word lane. The stale
case demonstrates why effective physical address cannot imply current RAM bytes.

The untouched pinned homebrew's five-million-call prefix retains 4,999,998 fetches
and 53,037 virtual/physical/cache tuples, with 4,806,689 cached and 193,309 uncached
fetches. Plain/traced/repeated full GPR/HI/LO/PC/Count, RAM/SP hashes and guest
messages agree with the previous v0 checkpoint. The complete projected v0 stream
is byte-identical. V1 is 628,211,919 bytes, SHA-256
`c14917d5dd2037cb93c02039bff2f488cf3d60aa841152c43f31c5e3a4ba22d1`.
Actual mapped cartridge size is 2,742,280 bytes, four fewer than canonical file
length because the pinned loader rounds down to eight bytes.

The production importer accepts both versioned streams. V1 requires explicit
mapped capacity and a complete physical/cache pair on every event; v0 rejects
those wire fields. Unknown, duplicate, null, partial and misaligned inputs fail.
Access variants participate in tuple and endpoint identity. Complete-source
verification rechecks facts, metadata and capture-qualified provenance. Merge
preserves captures and variants. Legacy v0 fields remain omitted; its map retains
SHA-256 `c32b48621f4a86314a9e229241eb8e0cc3417fc5a611609ae60506386587f6d3`.

Reproduce after spikes 004/005 create their ignored captures:

```text
python scripts/test_fetch.py
python scripts/test_fetch_corpus.py
python scripts/test_fetch_corpus.py --physical
```

V1's 24,203,476-byte map accounts for every fetch, passes complete-source checks
and self-merges byte-identically. One Windows/Rust debug import under concurrent
verification took 41.8 seconds and peaked at 74,903,552 bytes process working set.
This is one host/run's cost, not a throughput, speedup or scalability claim.
The raw capture remains required for chronology and source rechecking.

Neither version creates executable regions, entries, copies, generations,
retirement or immutable-source proof. Both remain OPEN/native_complete=false
under the independent unknown-identity gate. Next establish actual cartridge
device read provenance and canonical word backing, including PI busy/latch and
unmapped-tail cases; physical range and byte equality alone are insufficient.
