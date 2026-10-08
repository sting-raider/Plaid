# Pointer-table immutability requires alias and data-cache provenance

Date: 2026-10-08

Result: **PARTIAL**

## Question

Can Plaid eventually discharge `pointer_table_immutability_unproven` by proving that
no writes overlap only the guest-virtual range from which the current pointer-table
snapshot was read?

Hypothesis under test:

1. a guest-virtual-range-only exclusion is unsound because direct and TLB aliases
   can mutate the same physical bytes; and
2. binding the table snapshot to a physical backing span and excluding all writes
   through aliases is sufficient for a bounded immutability certificate.

The first part is validated. The second part is too weak for cacheable table loads:
a pre-existing or subsequently modified D-cache line can supply table bytes that
differ from the backing snapshot without a backing-memory write during the proof
interval. Physical backing identity is necessary, but cache/data-source lineage is
also required unless the verifier proves the table loads are uncached.

## Exact inputs

Plaid integration base inspected:

- repository: `sting-raider/Plaid`
- branch: `codex/executable-discovery`
- commit: `3cf45dc323cbcd9e6463ccc781d3de093a433097`
- existing recognizer: `crates/plaid-core/src/tables.rs`
- existing tests: `crates/plaid-core/tests/tables.rs`
- existing note: `research/indirect-pointer-tables.md`

Pinned independent reference source:

- ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- `ares/n64/cpu/memory.cpp` blob `f362ef67ab41ccf57330bbedd6f614e07a61dd17`
- `ares/n64/cpu/tlb.cpp` blob `3bec71ea1039b7fc5a5b2816ecc2b2ed534872dc`
- `ares/n64/cpu/dcache.cpp` blob `4de28e0ad9566d31f47210a997c22fa994785d26`

No ares code is copied into Plaid. The standalone model below encodes only the
address/backing relationships needed to falsify the proposed certificate.

## Source findings

At the pinned revision, ares classifies 32-bit kernel `0x80000000..0x9fffffff`
as cached KSEG0 and `0xa0000000..0xbfffffff` as direct KSEG1. Both devirtualize
to `(u32)(vaddr & 0x1fffffff)`; only the cache flag differs. Therefore
`0x80000104` and `0xa0000104` name the same physical byte location `0x104`.
A certificate that watches only one of those virtual ranges can miss mutation
through the other.

Mapped accesses are also alias-capable. Pinned ares TLB store lookup checks the
entry/ASID/region, validity and dirty bit, then constructs the physical address as
`entry.physicalAddress[lo] + (vaddr & entry.addressMaskLo)`. Distinct writable
virtual pages can therefore resolve to the same physical table backing. Failed
or non-dirty translations do not establish a mutation, which is why unresolved
translation cannot simply be treated as a successful overlapping write either;
it must remain a blocker until resolved.

Finally, cacheable data stores are not equivalent to immediate backing writes.
Pinned ares D-cache writes alter resident line bytes and mark them dirty. A later
miss/eviction writes the line back with `busWriteBurst`. D-cache reads return the
resident line on a hit and fill from backing only on a miss. Consequently:

- a cacheable alias store can change values seen by a later cached pointer-table
  load before any backing write occurs; and
- an old resident D-cache line can make a cached table load observe bytes different
  from an otherwise immutable current backing snapshot.

This is the decisive counterexample to treating "physical backing did not change"
as a complete pointer-table content proof.

## Executable adversarial model

`experiments/pointer_table_immutability_aliases.py` is a deterministic, dependency-
free bounded model. It deliberately compares a weak virtual-range checker with a
minimum physical-alias-aware mutation checker.

Run:

```text
python3 -m py_compile experiments/pointer_table_immutability_aliases.py
python3 experiments/pointer_table_immutability_aliases.py
```

Observed output:

```text
stale_dcache_source  physical=IMMUTABLE snapshot_match=False
same_virtual         virtual=MUTATED   physical=MUTATED
kseg0_alias          virtual=IMMUTABLE physical=MUTATED
tlb_alias            virtual=IMMUTABLE physical=MUTATED
deferred_writeback   virtual=IMMUTABLE physical=MUTATED
nonoverlap           virtual=IMMUTABLE physical=IMMUTABLE
unresolved_mapping   virtual=IMMUTABLE physical=OPEN
failed_write         virtual=IMMUTABLE physical=IMMUTABLE
table_before          80000040,80000050,80000060
table_after_kseg0     80000040,80000070,80000060
RESULT PARTIAL: virtual-only is unsound; physical mutation exclusion is necessary but cacheable table loads also need D-cache lineage
```

Harness SHA-256 at closeout:

`8606e78a5dc3ad2c005383472de77cd5ee6e9c5a54d47a1047014dbedc29bd7b`

### Cases

1. **same virtual control**: a direct store inside the snapshotted KSEG1 range is
   rejected by both checkers.
2. **KSEG0/KSEG1 alias**: the table is snapshotted at `0xa0000100`; a store to
   `0x80000104` resolves to physical `0x104`. The virtual-only proof incorrectly
   reports immutable while the physical checker rejects it. The model then mutates
   the actual backing word and demonstrates a candidate change from `0x80000050`
   to `0x80000070`.
3. **TLB alias**: `0x00400108` is mapped to physical `0x108`. Again the weak proof
   reports immutable while the physical checker rejects it.
4. **deferred D-cache writeback**: a cached alias store can dirty the table line;
   the eventual writeback reaches the table backing despite no write to the
   snapshotted virtual range.
5. **stale D-cache source**: with no writes at all in the proof interval, immutable
   backing containing `0x80000070` and an already resident cached word containing
   `0x80000050` disagree. A backing-only certificate cannot prove which value the
   runtime `LW` uses.
6. **non-overlap control**: a resolved store to physical `0x200` does not poison
   the table range.
7. **unknown translation**: the stronger checker returns OPEN, not immutable.
8. **failed write**: a failed mapping/modification attempt is not promoted into a
   mutation.

## Minimum future certificate obligation

A future exhaustive pointer-table certificate should not be phrased as "no writes
to guest range X". At minimum it needs all of the following, rechecked from primary
evidence rather than trusted producer labels:

1. **Dispatch-load identity**: exact load instruction(s), effective addresses,
   width/endian semantics, guard dominance and all relevant entry paths.
2. **Snapshot source identity**: bytes/hash plus the source actually capable of
   satisfying each dispatch load. For an uncached load this can be a verified
   physical/device backing span. For a cacheable load it also requires D-cache
   resident/fill/store/cache-operation lineage, or a proof that no cached state can
   supply a different value.
3. **Physical backing identity**: device plus physical span/generation, not only a
   virtual address. KSEG/TLB aliases must converge on this identity rather than be
   treated as separate tables.
4. **Mapping history**: KSEG mode plus relevant TLB mappings/ASIDs/regions and TLB
   changes over the certificate lifetime. An unresolved mapping that could reach
   the table keeps the proof OPEN.
5. **Complete mutation history for the declared scope**: successful CPU stores of
   all sizes, dirty D-cache modifications and writebacks, DMA/copies, RSP/device
   writes, relocation/patch paths, and any other writer capable of affecting the
   load source or backing span. A failed attempt is not a write witness; a missing
   sensor is not evidence of absence.
6. **Lifetime boundaries**: reset/restore, cache invalidation/fill/tag operations,
   overlay/load generation changes and any event that can replace the byte source
   terminate or re-establish the certificate.
7. **Fail-closed coverage proof**: the verifier needs evidence that the writer,
   mapping and cache histories are complete for the declared interval. Finite
   observation alone cannot turn absence of a mutation event into immutability.

A deliberately narrower first production certificate could require that the
recognized table load is proven uncached for its entire lifetime. That removes
D-cache state from the load-source proof, but it still needs physical backing,
TLB/direct alias coverage, complete writers and lifetime boundaries. It would be a
useful restricted certificate, not a general N64 pointer-table solution.

## What this does not prove

This experiment does not provide a production immutability certificate, complete
N64 writer census, TLB-mode verifier, D-cache chronology sensor, overlay lifetime,
or whole-ROM closure. It does not claim ares implementation details are themselves
N64-wide proof; they are a pinned behavioral/source oracle for constructing
counterexamples to a weaker Plaid rule.

The experiment also does not touch Plaid production files. Existing
`pointer_table_immutability_unproven` behavior remains the correct fail-closed
state until the above obligations are implemented and independently rechecked.

## Recommendation

**ADOPT** the architectural requirement that pointer-table content proofs be
backing/alias/load-source aware. In particular, reject any future implementation
that clears `pointer_table_immutability_unproven` solely from guest-virtual write
exclusion or physical backing write exclusion. Keep implementation work for the
primary integrator or a separately claimed verifier slice.
