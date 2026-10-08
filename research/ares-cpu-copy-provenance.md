# ares CPU-copy provenance: scalar uncached chain vs cached stale-source counterexample

Date: 2026-10-08

Result: **PARTIAL**

Integration recommendation: **ADOPT** the provenance invariant and the deterministic spike as research evidence; do not treat this as a general CPU-copy certificate yet.

## Question

Can ordinary VR4300 load/store copies be turned into trustworthy RDRAM byte-origin evidence without inferring origin from register equality or current RAM contents?

Bounded hypothesis: for a controlled identity-mapped KSEG1 `LW` -> `SW`, completed scalar RDRAM transactions are sufficient to witness the source read and destination write. Applying the same rule directly to KSEG0 cached copies is unsound because the load/store can terminate in D-cache residency; backing memory is observed at line fill/writeback boundaries instead. A KSEG1 alias mutation between cached load and cached store should provide a concrete counterexample to any rule that consults current source RAM at writeback time.

## Upstream source path

Pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

At this revision:

- `ares/n64/cpu/memory.cpp::CPU::read(PhysAccess)` sends cached accesses to `dcache.read<Size>` and uncached accesses to `busRead<Size>`.
- `CPU::write(PhysAccess, data)` sends cached accesses to `dcache.write<Size>` and uncached accesses to `busWrite<Size>`.
- `ares/n64/cpu/dcache.cpp` fills a D-cache line with `busReadBurst<DCache>` and writes a dirty line with `busWriteBurst<DCache>`. A cached store updates the resident cache line and dirty mask, not RDRAM immediately.
- `ares/n64/cpu/interpreter-ipu.cpp::CACHE` operation `0x19` performs D-cache hit writeback and clears the dirty mask after the completed writeback.
- `ares/n64/rdram/rdram.hpp` performs scalar identity-mapped writes with `Memory::Writable::write` plus hidden-RAM update, and burst writes with the corresponding four-word/eight-word backing updates.

The spike patches only generated copies of `rdram.hpp`; the pinned reference checkout must remain exact and clean.

## Sensor placement

`spikes/020-ares-cpu-copy-transactions/run.py` creates an instrumented generated header with two callbacks:

1. scalar identity-mapped RDRAM callback after the actual successful scalar read, or after the actual scalar write and hidden-RAM update;
2. burst identity-mapped RDRAM callback after the actual successful D/I-cache burst read/write.

Callbacks record a single monotonic ordinal, current CPU PC, phase, direction, backing address, width, requestor and payload. They do not issue a guest read, guest write or clock.

The runner separately builds `baseline.cpp` against the unmodified pinned reference and compares it with observer-disabled and observer-enabled instrumented executions. The traced execution is repeated and required to be byte-identical.

## Fixture

All bytes are synthetic. Recompiler is disabled. RDRAM uses the controlled identity mapping.

### Phase 1: uncached copy

- source physical `0x1000` = `0x11223344`;
- destination physical `0x2000` = `0xaabbccdd`;
- `s0 = 0xffffffffa0001000` (KSEG1 source);
- `s1 = 0xffffffffa0002000` (KSEG1 destination);
- guest sequence: `LW t0,0(s0)`; `SW t0,0(s1)`.

### Phase 2: cached stale-source adversary

Caches are reset for the controlled phase and backing memory is restored to the same initial words.

- `s0 = 0xffffffff80001000` (KSEG0 cached source);
- `s1 = 0xffffffff80002000` (KSEG0 cached destination);
- `s2 = 0xffffffffa0001000` (KSEG1 alias of the source);
- `t2 = 0x55667788`;
- guest sequence:
  1. `LW t0,0(s0)`;
  2. `SW t2,0(s2)` — uncached alias mutation of source backing RAM;
  3. `SW t0,0(s1)` — cached destination store;
  4. `CACHE 0x19,0(s1)` — D-cache hit writeback.

The point is adversarial: after step 2, current source backing RAM is no longer the byte value previously loaded into `t0`, while the source D-cache line is intentionally stale and still contains the old value.

## Observed evidence

Two clean GitHub Actions executions succeeded from the isolated research branch:

- run `37798077372`, source commit `bd5af54e76a71467a5345965a7250b143da1fd31`;
- run `37798119815`, source commit `890db70e7415464ec3d4ec8fa063ef5c53df2a60`.

The second run artifact was `cpu-copy-rdram-results`, artifact id `11559372938`, digest `sha256:e8cdf9a8134b9c7f72e033398007a33691322232317728bd253f5c8b22f9135b`.

### Phase 1

Relevant scalar events were exactly:

1. ordinal 2: read physical `0x1000`, 4 bytes, VR4300 uncached requestor, value `0x11223344`;
2. ordinal 3: write physical `0x2000`, 4 bytes, VR4300 uncached requestor, value `0x11223344`.

There were no Phase-1 D-cache bursts. Destination backing RAM was `0x11223344` immediately after the store.

For this controlled scope, the completed scalar transaction chain is a direct backing read/write witness. It still needs instruction/dataflow correlation before it can become a general compiler certificate.

### Phase 2

Relevant ordered events were exactly:

1. ordinal 5: D-cache burst read at physical `0x1000`, 16 bytes, first word `0x11223344`;
2. ordinal 6: uncached scalar write at physical `0x1000`, 4 bytes, value `0x55667788`;
3. ordinal 7: D-cache burst read at physical `0x2000`, 16 bytes, first word `0xaabbccdd`;
4. ordinal 8: D-cache burst write at physical `0x2000`, 16 bytes, first word `0x11223344`.

Immediately after the cached `SW` but before guest `CACHE 0x19`:

- destination backing RAM was still `0xaabbccdd`;
- current source backing RAM was already `0x55667788`;
- resident source D-cache word remained `0x11223344`;
- resident destination D-cache word was `0x11223344`;
- destination D-cache dirty mask was `0x000f`.

After `CACHE 0x19`:

- destination backing RAM became `0x11223344`;
- destination dirty mask became zero;
- the only backing mutation for the cached destination was the D-cache burst writeback.

This falsifies the unsafe rule “at destination writeback, matching/current source RAM identifies the copied origin.” Current source RAM is `0x55667788`, but the destination receives `0x11223344`, whose usable history is the earlier D-cache fill/load plus intervening cache residency.

## Neutrality and reproducibility

The unmodified-reference baseline, generated sensor build with callbacks disabled, and generated sensor build with callbacks enabled had identical recorded final state. The traced run repeated byte-for-byte.

Final shared state from the successful run:

- exception code: `0`;
- effective Count: `222`;
- D-cache misses: `2`;
- D-cache writebacks: `1`;
- RAM SHA-256: `d3d19c778fa5f275ae190c732c487a30371a789ce603774a5b3ad16c3c64c9b3`;
- hidden-RAM SHA-256: `178889c8ba55d2c643783b65b01834e7bed6d49018c7fb08f7de4828c4d9bc05`;
- D-cache SHA-256: `2adcee2881f140962052673a02aea7258555ea673cba203af7cbb5f1fae0a524`;
- I-cache SHA-256: `f359f1fa6e09a838b687b6b473d2bc0849ef2b1fefced8973591c57540786cde`.

Reproduce from a checkout whose `.refs/ares` is exactly the pinned revision:

```sh
python3 spikes/020-ares-cpu-copy-transactions/run.py
```

Expected final line:

```text
PASS: uncached LW/SW has exact scalar backing chain; cached copy remains D-cache-resident until writeback and survives an uncached stale-source alias mutation
```

## What is safe to adopt

1. Do not infer CPU-copy provenance from equality of register values or from source RAM contents observed later.
2. A completed uncached scalar RDRAM read and subsequent completed uncached scalar RDRAM write can contribute exact backing evidence for this controlled identity-mapped word-copy case, provided the compiler also proves the value/dataflow connection and excludes intervening transformations.
3. Cached copy provenance must be versioned through D-cache line/lane state. A backing-origin witness enters on the relevant D-cache fill/read history; cached stores mutate resident lineage; backing destination mutation occurs on verified writeback/eviction/CACHE behavior.
4. KSEG0/KSEG1 aliases make “physical address + current bytes” insufficient as lineage identity. Chronology and cache state are mandatory.

## Remaining gaps

This is not a general CPU-copy proof. Untested or unresolved territory includes:

- byte, halfword, dualword, partial/unaligned load/store families and merge instructions;
- TLB-mapped aliases, remapped/degraded RDRAM and address/error paths;
- dirty eviction caused by index conflicts rather than explicit `CACHE 0x19`;
- LL/SC and exception/restart behavior;
- loops with cross-block register/dataflow joins;
- transformations, decompression and relocation/patching rather than byte-preserving copies;
- copy lifetimes, overwrite generations and executable-consumer correlation;
- RSP/PI/SI/SP memory paths;
- exhaustive detection of all CPU copy implementations.

Therefore the overall research lane closes **PARTIAL**, while the specific stale-source counterexample and the controlled uncached transaction witness are validated.
