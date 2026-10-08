# VR4300 SB/SH executable-byte mutation in pinned ares

Status: **VALIDATED** for the bounded pinned-ares identity-RDRAM semantics below.

Claim: issue #4 worker `gpt56sol-sb-sh-mutation-20261009`.

Tested Plaid research commit: `dbb3ee1abd20ff29b305811c32657ee5218879a1`.

GitHub Actions run: `37849855232` (`Research VR4300 SB SH stores`, success).

## Hypothesis

Ordinary `SB` and `SH` are executable mutation sources that cannot be omitted by an SW-oriented sensor. In pinned ares, successful uncached identity-RDRAM stores should mutate exactly one/two backing bytes; successful cached stores should mutate D-cache residency only until writeback; reverse-endian mode should alter physical lane selection by the shared size-specific transform; and alignment/TLB failures should commit no mutation.

The experiment tried to falsify exact width and fault-before-write behavior, not merely demonstrate that a store occurred.

## Exact references

`refs.lock.toml` pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
- Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`;
- n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`.

Relevant pinned ares contracts:

- `ares/n64/cpu/interpreter-ipu.cpp`: `SB` calls `write<Byte>` and `SH` calls `write<Half>` with the low integer-register payload.
- `ares/n64/cpu/cpu.hpp`: virtual-address `write<Size>` devirtualizes before the physical/cache write.
- `ares/n64/cpu/memory.cpp`: requested alignment is checked before segment/TLB translation; little-endian mode maps Byte physical address with `paddr ^ 7` and Half with `paddr ^ 6`; successful cached stores go to `dcache.write<Size>`, uncached stores to `busWrite<Size>`.
- `ares/n64/cpu/dcache.cpp`: a successful resident write updates only selected Byte/Half storage and marks the selected dirty lanes; a miss fills the line before the store.
- `ares/n64/rdram/rdram.hpp`: successful identity-mapped RDRAM writes enter the width-specific writable-memory path and hidden-bit update.
- `ares/n64/memory/lsb/writable.hpp`: Byte and Half are distinct width-specific writes rather than widened Word writes.

The successful source guard emitted:

- `ares/n64/cpu/dcache.cpp` SHA-256 `a1e2dd9c619cae7dbba4162eab8ab09a239f818019b50a88e49b09501488650b`;
- `ares/n64/cpu/interpreter-ipu.cpp` SHA-256 `495c2589d6c5b34e144a5d2cd02cf2372771dc8642af590e9d46389a157e6152`;
- `ares/n64/cpu/memory.cpp` SHA-256 `55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74`;
- `ares/n64/memory/lsb/writable.hpp` SHA-256 `52565f0359450110af0836d37540a7fb8f77cb10a6e444286a5b09c14c8fd2f0`;
- `ares/n64/rdram/rdram.hpp` SHA-256 `6a77c2fa0bbb320ff6b2855ea6379541a67096bed6b91cc6cd2697584112b1cf`;
- combined source-contract report SHA-256 `813fd2faf52ab7ad1b38e6724345f43e6f82902e0f50fbac9697f4d580463d41`.

Pinned Mupen provides a useful independent structural cross-check: its `mips_instructions.def` implements `SB` and `SH` with masks `0xff` and `0xffff` into the aligned-word write helper. That independently agrees that these are subword mutation sources, although Mupen's implementation shape is not evidence for ares cache chronology. Pinned n64-systemtest independently contains store-TLB-miss and address-error coverage.

## Experiment

`spikes/036-ares-sb-sh-stores/` reuses the exact-pin headless ares build recipe from spike 003. It does **not** patch or instrument ares; it invokes the real pinned CPU instruction handlers and observes existing architectural/cache/RDRAM state.

Matrix:

- operations: `SB`, `SH`;
- offsets: 0..7;
- contexts: big endian and controlled little endian;
- destinations: uncached identity RDRAM, cached identity RDRAM, unmapped TLB virtual address;
- each case executes twice and must produce byte-identical JSON;
- independent Python lane model runs 100,000 deterministic randomized checks.

The independent model report was:

```text
cases=100000
SB payload=[0x44]
SH big payload=[0x33,0x44]
SH little payload=[0x44,0x33]
sha256=fc756e4a7482ce8950da990ddf0b52a1d37364745e42b5b8889231d18104f57b
```

The exact-pin executable matrix passed:

```text
PASS: 96 repeated pinned-ares SB/SH cases (48 successes, 48 faults)
results_sha256=587d6539e575fc10010024f90796ac24c2b8cdf08d21ef16d15e578af36649a0
```

Two earlier CI attempts failed only because the source guard incorrectly demanded uniqueness for snippets shared by normal/debugger or normal/EBUS paths. The guard was narrowed to path-specific contracts before the executable matrix was allowed to run; there was no suppressed semantic failure.

## Result

### Successful uncached identity-RDRAM stores

- `SB` changed exactly one physical backing byte.
- aligned `SH` changed exactly two adjacent physical backing bytes.
- no hidden Word widening was observed.
- big-endian physical start is the logical guest offset.
- controlled little-endian physical start is `offset ^ 7` for `SB` and `offset ^ 6` for `SH`.
- guest-visible bytes match the architectural payload: `0x44` for `SB`; `0x33 0x44` in big endian and `0x44 0x33` in little endian for `SH`.

### Successful cached identity-RDRAM stores

- the cached guest view changed by exactly the architectural Byte/Half effect;
- uncached alias/backing remained unchanged before writeback;
- D-cache dirty coverage matched only the selected physical Byte/Half lanes;
- therefore an opcode-level or backing-only mutation observer is insufficient for cached executable stores. The mutation first exists in D-cache residency and only later reaches backing through cache writeback.

The dirty mask is useful here as a tested width/state indicator; it is **not** by itself byte-origin provenance.

### Fault-before-write behavior

- odd-address `SH` raised Store Address Error (`ExcCode=5`) before any backing or D-cache mutation, for cached, uncached, and mapped-address-test variants;
- missing-TLB `SB` and aligned `SH` raised TLB Store Miss (`ExcCode=3`) with no backing or D-cache mutation;
- odd `SH` against the missing-TLB virtual address still raised the alignment error first, with no mutation.

A normalized provenance event must therefore be emitted at a **successful mutation boundary**, not merely on decoding/attempting `SB` or `SH`.

### Executable relevance

The independent lane model verifies that `SB` can select every byte lane of a 32-bit instruction word. The two aligned `SH` placements cover both halfwords, and therefore all four instruction bytes collectively. Omitting `SB`/`SH` from Plaid's general executable mutation census leaves real instruction-patching capability unmodeled.

## Plaid implication

**ADOPT** the semantic result into the generalized executable-mutation model:

1. Treat successful `SB` and aligned `SH` as first-class mutation sources alongside the already studied Word/subword-merge/64-bit families.
2. Record exact width and normalized physical byte lanes after endian/address translation.
3. Distinguish cached-resident mutation from backing-memory mutation; do not claim backing provenance until the later successful writeback transaction.
4. Emit no mutation witness for alignment/TLB-failed attempts.
5. Do not infer byte origin from a D-cache dirty mask alone; source payload/provenance and cache/writeback chronology remain separate obligations.

This does not require production code from this branch. The durable value is the exact-pin semantic contract and reusable spike for a future generalized store observer.

## Limitations / still unknown

This slice does not cover:

- prevalence/reachability of `SB`/`SH` self-modifying code in arbitrary commercial ROMs;
- full guest-driven Status.RE/user-mode reverse-endian setup (the little-endian matrix controls the ares context directly);
- non-identity/degraded RDRAM mapping;
- D-cache eviction/writeback ordering and byte-origin transfer into backing;
- I-cache stale-line visibility or invalidation after these mutations;
- MMIO/non-RDRAM destinations;
- SW/SWL/SWR/SD/SDL/SDR/SC/SCD/COP1 stores beyond their separate research slices;
- RSP writes, DMA, CPU copies, decompression, relocations, restore/debugger paths, or closed-world reachability.

Conclusion: **VALIDATED** for the declared pinned-ares scope; recommendation **ADOPT** the semantics and **PRIMARY-INTEGRATOR-REVIEW** for how the future generalized mutation sensor composes them with cache/writeback provenance.
