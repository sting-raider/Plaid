# ares TLB-mapped uncached instruction-fetch provenance

Date: 2026-10-09

Result: **VALIDATED for the bounded tested pinned-ares scope**

Integration recommendation: **ADOPT** the narrow extension of the existing uncached identity-RDRAM fetch witness to successful TLB-mapped fetches whose resolved `PhysAccess.cache` is false. Do **not** treat a virtual address as having a stable physical backing across TLB writes, and do not generalize pinned ares cache-algorithm behavior into an N64-wide hardware invariant without independent hardware evidence.

## Question

The integrated direct-fetch work (`research/rdram-uncached-fetch-provenance.md`, `spikes/025-ares-rdram-uncached-fetch/`) proved that a direct KSEG1 instruction fetch can be joined to the exact successful ordinary identity-RDRAM scalar read that supplied it. It explicitly left TLB-mapped uncached fetches untested.

This experiment asks whether the same causal witness remains sound when address translation comes from a mutable VR4300 TLB entry, including virtual aliases, remapping, ASID/global matching, cache-algorithm changes, reverse-endian word-lane selection, and failed translations.

The falsifiable hypothesis was:

1. at pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, a valid TLB entry with cache algorithm 2 yields `PhysAccess.cache == false` and therefore reaches the ordinary uncached CPU bus path;
2. the existing fetch-boundary + successful scalar-read witness remains valid if it uses the *current* fetch context's virtual address, translated physical address and post-endian bus physical address;
3. physical-address/value equality alone is insufficient because different virtual aliases can name the same bytes, while the same virtual address can be remapped to different bytes;
4. cacheable mappings and failed translations must not receive this ordinary scalar-fetch witness.

## Reused instrumentation

This lane intentionally reuses the already integrated and neutrality-tested sensor from `spikes/025-ares-rdram-uncached-fetch/` rather than creating a competing provenance primitive.

The two callbacks share one monotonic ordinal:

- a scalar-RDRAM event emitted only after a successful in-range identity-mapped `Memory::Writable::read<Size>`;
- a CPU fetch boundary bracketing the actual cache-or-bus operation inside `CPU::fetch`, after translation and after reverse-endian physical-lane adjustment.

For one fetch, the reducer accepts an origin witness only when:

- the fetch resolves uncached;
- exactly one 4-byte `VR4300_UNCACHED` scalar read occurs strictly between its begin/end events;
- that read address equals the fetch's post-endian bus physical address;
- that read value equals the fetched instruction word.

Zero or multiple eligible reads fail closed.

## Exact pinned source behavior

Primary reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

At that revision:

- `CPU::devirtualize` sends mapped reads to `TLB::load`.
- `TLB::load(vaddr, entry)` rejects a non-global ASID mismatch, rejects an invalid selected half, computes `entry.physicalAddress[lo] + pageOffset`, and returns `PhysAccess{true, entry.cacheAlgorithm[lo] != 2, physicalAddress, vaddr}`.
- `CPU::TLBWI` clears the devirtualization cache, overwrites the indexed TLB entry, synchronizes its derived masks/global state, and therefore changes subsequent translations without changing the virtual PC.
- `CPU::instruction` performs translation before `CPU::fetch`; a failed translation returns before the fetch operation.
- `CPU::fetch` applies reverse-endian word-lane adjustment after translation, then chooses I-cache versus `busRead<Word>` from `PhysAccess.cache`.

The exact source guard in `spikes/036-ares-tlb-uncached-fetch/source_guard.py` fails if those contracts drift or the pinned checkout is dirty.

Pinned `n64-systemtest` `196f5421173220eb2f63a7a99c64795dc0ea0698` was also inspected as an independent architectural test source. Its TLB tests construct EntryLo values with explicit global/valid/dirty/coherency fields and exercise ASID mismatch. Pinned Mupen64Plus `ba95bab92a76744753bfe61470823a4937850ab0` was inspected too; its classic TLB LUT path preserves virtual-to-physical translation but does not provide an equivalent independent proof of ares's `CCA==2 -> uncached` fetch-path distinction. That absence is a reason to keep the cache-algorithm conclusion scoped to the tested oracle rather than promote it to hardware fact.

## Executed matrix

`spikes/036-ares-tlb-uncached-fetch/driver.cpp` uses real pinned-ares `CPU::TLBWI` writes and the interpreter path with CPU/RSP recompilers disabled.

1. **CCA=2 positive**: VA `0x4000` -> PA `0x1000`, non-global ASID 7. Executes `ORI t1,0,0x1234` and obtains scalar witness ordinal 2.
2. **Virtual alias**: VA `0x8000` -> the same PA `0x1000`, same instruction/value. Obtains a distinct fetch context and scalar witness ordinal 5.
3. **TLB remap**: entry 0 is rewritten through `TLBWI`; the same VA `0x4000` now maps to PA `0x3000`, containing the same instruction/value. Obtains scalar witness ordinal 8 at the new backing address.
4. **CCA=3 control**: VA `0xc000` -> PA `0x5000`. Pinned ares marks the access cacheable; the instruction executes through I-cache and receives no ordinary scalar witness.
5. **Reverse endian**: VA `0x10000` translates to raw PA `0x7000`, but the actual uncached word bus transaction occurs at `0x7004`; the witness records `0x7004` and executes `ORI ... 0x9abc`.
6. **Equal-value data-read decoy**: mapped code at VA `0x14000` performs an uncached mapped load of zero from VA `0x18000`, followed by a zero/NOP instruction. Scalar chronology is code `0x9000`, data `0xb000`, next code `0x9004`; both instruction fetches receive their own witnesses because the equal-valued data read lies outside the second fetch boundary. The reducer's adversarial mutation moves that data read inside the second fetch interval and correctly makes the witness unknown.
7. **Global ASID override**: a global mapping written with ASID 1 still resolves when current ASID is 99 and receives scalar witness ordinal 23.
8. **Non-global ASID mismatch**: same semantic shape without global bits raises TLB load exception code 2 at VA `0x20000`; no CPU fetch boundary or eligible scalar fetch event occurs.
9. **Invalid selected half**: raises TLB load exception code 2 at VA `0x24000`; no fetch witness.
10. **True TLB miss**: all TLB entries are cleared, VA `0x28000` raises TLB load exception code 2; no fetch witness.

The reducer also directly asserts the two provenance counterexamples:

```text
VA 0x4000 -> PA 0x1000 -> word 0x34091234
VA 0x8000 -> PA 0x1000 -> word 0x34091234   # same PA/value, different VA
VA 0x4000 -> PA 0x3000 -> word 0x34091234   # same VA/value, different PA after TLBWI
```

Therefore neither `(physical address, value)` nor `(virtual address, value)` is a sufficient mapping-history identity.

## Exact run and receipts

Successful GitHub Actions run:

```text
run:          37849934100
job:          113560061383
source head:  81eb12332403e889dd55f452e7617d30fd7b51f3
ares pin:     9408cb43d4948fc3ea6e152a307a34348df3fe04
compiler:     g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
artifact id:  11580739009
artifact SHA: 48cf5b441b10a4d60f7ea678a5eb7b8fb99ac75e53aa9d1cf60cc08174bf2156
results SHA:  e72d4332f3112bea8b1130183d93c7791e688edca7340903ed6a5e5bd58cd851
```

The job checked out the exact ares commit, passed Python/source guards, built both the unmodified-reference baseline and generated observer build, executed the full matrix, repeated the enabled trace byte-for-byte, and uploaded the receipts.

Observed final state included:

```text
Count:              56
exception:          2   # final deliberate TLB-miss phase
I-cache hits:       0
I-cache misses:     1
RAM SHA-256:        c302a329a983b90d0e53b4bfa4da0627bbf12d07034e8c5e69e935fc88bb04cb
I-cache SHA-256:    9497126bfa2f88c9372cf05f7919b21e4465169c05a3b59b0117c55f3d6fef61
```

The uninstrumented baseline, observer-capable build with observers disabled, and observer-enabled build had identical `facts` and emulated `state`. The enabled trace repeated byte-for-byte. Canonical compact JSON hashes from the receipt were:

```text
baseline/plain state+facts payload: 4eb52bd6bbfcbfe42eae8d30d17eca89ecc0fc110b34c6863df66203d03269ec
traced payload:                    09285692aa13a98e876337b59beb962807a2ba1158b0d79ce56979ee6bd92ce3
evidence payload:                  c28ef17d2c526875f9e53b8579a7b36a26d83852957d00ebc5537d8ef9876880
```

## Safe integration contract

The existing ordinary identity-RDRAM uncached-fetch witness can be extended to a **successful mapped fetch** when the actual resolved fetch context says it is uncached and the same strict transaction join succeeds.

A normalized observed-fetch witness should retain at least:

```text
fetch-context / chronology identity
virtual PC / vaddr
current translated paddr
post-endian bus paddr
resolved cache-vs-uncached class
exact successful backing transaction identity
fetched bytes/value
```

For closure reasoning, do not model `vaddr -> paddr` as immutable. TLB write/remap chronology is a separate state transition and should receive an explicit mapping generation/event if Plaid needs to prove *mapping history*, rather than merely the origin of one observed fetch. The experiment proves that using the current translated paddr inside each fetch context is sufficient for this bounded byte-origin join; it does **not** prove that vaddr/paddr alone reconstructs prior TLB generations.

Global mappings also demonstrate why a naive `entry ASID == current ASID` provenance condition is wrong: global state legitimately bypasses the ASID comparison.

## Remaining gaps

This result is intentionally narrow.

- It is exact pinned-emulator evidence, not a hardware characterization of every VR4300 coherency algorithm. Only ares's tested CCA=2/CCA=3 path distinction is claimed here.
- Only 4 KiB-page even-half mappings were exercised. Odd halves, larger PageMask values, region matching, 64-bit mapped segments, supervisor/user addressing modes and other EntryHi corner cases remain untested.
- The experiment exercised `TLBWI`, not `TLBWR`, probe/read instructions, save-state restore, reset epochs or arbitrary replacement/cache behavior.
- The CCA=3 control only proves that the *ordinary scalar-read* witness must fail closed. It does not solve cached I-cache fill/residency provenance.
- It does not instrument a TLB-write provenance stream or assign mapping-generation IDs. That is still needed if closure depends on reconstructing all alias/remap lifetimes.
- Only identity ordinary RDRAM backing is positively witnessed. Non-identity/degraded RDRAM, EBUS, SP, PIF and other sources still require their own source-specific backing witnesses.
- This says where the bytes of an **observed** mapped uncached fetch came from. It does not prove exhaustive reachability, indirect-target closure or the closed executable universe.

Within those boundaries the hypothesis is **VALIDATED**: pinned ares TLB CCA=2 mapped instruction fetches enter the same causally joinable uncached identity-RDRAM scalar path as direct KSEG1 fetches, while aliases, remaps, cacheable mappings and translation failures do not justify collapsing mapping history or fabricating an ordinary backing witness.

## Reproduce

From a Plaid checkout with `.refs/ares` at the exact pin:

```sh
python3 -m py_compile spikes/036-ares-tlb-uncached-fetch/run.py \
  spikes/036-ares-tlb-uncached-fetch/source_guard.py
python3 spikes/036-ares-tlb-uncached-fetch/run.py
sha256sum target/ares-tlb-uncached-fetch-spike/results.json
```

Expected recorded `results.json` SHA-256:

```text
e72d4332f3112bea8b1130183d93c7791e688edca7340903ed6a5e5bd58cd851
```

## Primary integration reproduction (2026-10-09)

Retained original fixture from `7ca4338`; primary WSL reproduction passes the
full matrix and exact worker result SHA-256
`e72d4332f3112bea8b1130183d93c7791e688edca7340903ed6a5e5bd58cd851`.
Baseline, observer-disabled, enabled and repeated reported states agree. The
finite per-fetch source contract is adopted; immutable virtual mapping and
whole-ROM closure remain unclaimed.
