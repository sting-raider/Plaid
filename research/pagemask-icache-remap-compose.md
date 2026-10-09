# Large-PageMask TLB -> I-cache resident provenance composition

Date: 2026-10-10

Result: **VALIDATED for the bounded exact-pinned ares composition tested here**.

This worker composes previously validated primitives at a seam that had remained open: large-PageMask translation had been executed with uncached fetches, while cacheable TLB/I-cache lifetime work had exercised ordinary 4 KiB mappings.

## Question

For a cacheable executable fetch under 16 KiB or 64 KiB TLB mappings, what identities must remain distinct across same-value mapping writes, backing mutation, remaps, temporary context unreachability, and PageMask geometry changes?

The tested hypothesis was that a defensible cached-fetch witness needs the causal chain

```text
ordered mapping operation + translation context
    -> normalized PageMask/EntryLo translation
    -> actual translated physical address/tag
    -> cache fill + backing-writer provenance
    -> resident generation/lifetime
    -> cached instruction fetch
```

and cannot replace any of those identities with value equality, current mapping state, or current backing contents.

## Exact inputs

Canonical Plaid base at claim time:

- `211176e7a489fecf8331d02915ee982cd279cb62`

Exact references from `refs.lock.toml`:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

Prior independently validated inputs composed here include the large-PageMask fetch result (`research/tlb-pagemask-gpt56sol`), TLBWI/TLBWR operation-generation work, cacheable TLB synonym/remap lifetime work (`research/tlb-icache-synonyms-gpt56sol`), and the ASID/TLBR context/lifetime results coordinated through issue #4.

No production Plaid file is modified on this branch.

## Guarded source contracts

Pinned ares normalizes PageMask and derives `addressMaskLo` / `addressSelect`; mapped translation chooses EntryLo with `vaddr & addressSelect` and computes the physical address from the selected physical base plus `vaddr & addressMaskLo`.

Pinned ares then passes both the original virtual address and translated physical address to its cacheable I-cache path. Its I-cache selects a line with `vaddr >> 5 & 0x1ff`, tests a physical 4 KiB tag from `paddr & ~0xfff`, and fills from the translated physical tag plus the line index.

Source SHA-256 receipts from Actions run `38003027737`:

```text
ares tlb.cpp:       93722177331f1df2cd7cbf313909bf20a148183d8cbd73db928b7cf0bff506d1
ares memory.cpp:    55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74
ares cpu.hpp:       6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27
Gopher64 cache.rs:  45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177
n64-systemtest TLB: 221bc0f3239ddbb1f9e4d16b2910edf007db34997915db7b2d4703f5683d88f4
```

The source guard deliberately preserves a material emulator disagreement: pinned Gopher64 indexes its I-cache from physical address, unlike the ares virtual-index selection. Therefore this result establishes a provenance/lifetime obligation, not a universal VR4300 virtual-index rule.

## Exact-pinned ares composition fixture

`experiments/pagemask-icache-remap/driver.cpp` uses the existing Plaid headless exact-ares build path with CPU/RSP recompilers disabled, identity RDRAM, interpreted synthetic instructions, and real ares `TLBWI()` mapping operations.

### 16 KiB mapping versus fixed-4K reconstruction

VA `0x00021000` belongs to the even half of a 16 KiB mapping because the normalized selector is bit 14 (`0x4000`), although virtual bit 12 is set. The actual executable word is at PA `0x00011000`; an equal-valued decoy is planted at the fixed-4K guess `0x00020000`.

The first cacheable fetch misses once, executes `0x1111`, and installs physical tag `0x00011001`.

A same-value legal TLBWI of the same mapping leaves that resident line valid with the same tag. This composes the prior mapping-operation result with resident lifetime: the mapping operation is a new ordered generation, but it does not automatically retire or replace the cache resident.

The physical backing at PA `0x00011000` is then changed to instruction `0x2222` without a cache operation. The next fetch is a hit with no additional miss and still executes resident `0x1111`. Current backing bytes are therefore not provenance for the cached hit.

### Equal-payload physical remap

The same VA is remapped, still as 16 KiB, to actual PA `0x00031000`, deliberately containing the same `0x1111` instruction payload. TLBWI itself leaves the prior resident valid/tagged `0x00011001`; the next fetch sees the physical-tag mismatch, incurs one miss, refills, still returns `0x1111`, and changes the resident tag to `0x00031001`.

Equal payload therefore does not preserve backing or resident identity across a physical-tag change.

### Remap-away/back and temporary context unreachability

After refilling the original mapping with current backing `0x2222`, the backing is changed again to `0x4444`. Remapping away and back without an intervening fetch preserves the resident. Fetching after return incurs no miss and executes stale resident `0x2222`.

The fixture then stages a nonmatching ASID and receives TLB-load exception code 2 for the same VA. That failed translation incurs no I-cache miss and leaves the resident valid/tag-identical. Restoring the matching ASID produces another resident hit on stale `0x2222`.

The direct ASID staging deliberately isolates lifetime behavior; guest MTC0/TLBR writer semantics are delegated to their already validated research lanes.

### Same VA, 16 KiB -> 64 KiB geometry change

The same VA is remapped with a 64 KiB PageMask (`addressSelect=0x10000`). Correct large-page translation yields PA `0x00051000`; a fixed-4K reconstruction would choose an equal-valued decoy at `0x00070000`.

The next cacheable fetch incurs one miss, executes the same external payload `0x2222`, and installs tag `0x00051001`. A separate 64 KiB odd-half control uses VA `0x00070000`: fixed bit 12 points at an equal-valued EntryLo0 decoy at PA `0x00080000`, but PageMask selector bit 16 correctly selects EntryLo1 / PA `0x000a0000`, producing tag `0x000a0001`.

## Exact execution receipt

Actions run `38003027737`, job `114065363686`, behavior head `347680f4f14f6860c9e24bde46b9253dcedc94b7` succeeded end-to-end. The fixture was executed twice and the runner required byte-identical stdout.

```text
MODEL_SHA256=922c54f8c09f6f330cea4b1307c059b68423be6faaeb81c79dbe0db1bc671327
FIXTURE_STDOUT_SHA256=79bf5340619d62ee2afc1c5862ee324d5403eec9fc697b84153b15d9703134ea
RESULT_SHA256=7d0116e2a31c186951ebb248ac81b78df2fcb342ccbb005f6aa88e2fd44c0f86
I-cache state SHA-256=9929c6d182ea6efd93fe325a9c71040c944babd9037fba2f7254ca944471125d
```

Accepted miss chronology:

```text
start=0
first 16K fill=1
backing-mutated stale hit=1
equal-payload different-tag remap=2
return-to-original refill=3
remap-away/back stale hit=3
ASID-failed attempt=3
ASID return hit=3
16K->64K geometry remap=4
64K odd control=5
```

All explicit resident-preservation checks (`same_value_tlbwi`, `away_back`, `asid_fail`) are true.

Uploaded artifact from that run:

```text
artifact id:     11650076724
artifact bytes:  2755
artifact digest: sha256:3ed2f0e3108b78f802964304f628175d7acc61855a9aaacc415de8d9f037b219
```

## Independent adversarial model

`model.py` independently tracks mapping-operation generation, translation-context generation, translated PA/physical tag, backing-writer generation, and resident generation.

It rejects six forged witnesses independently:

```text
current_backing
equal_payload_new_resident
fixed4k_paddr
wrong_context_generation
wrong_mapping_generation
wrong_physical_tag
```

It also represents two equal-content same-value mapping operations as distinct generations.

A deterministic 50,000-case 16 KiB/64 KiB sweep (`seed=0x504c414944cace`) produced:

```text
fixed-4K (half,PA) wrong: 46,065 / 50,000
physical cache tag wrong: 46,065 / 50,000
bit-12 half alone wrong:  25,028 / 50,000
```

The sweep measures the failure surface of the naive reducer; it is not guest reachability evidence.

## Result and closed-world impact

**VALIDATED**, narrowly.

A future Plaid closure certificate cannot merely prove PageMask translation, TLB/context generations, backing writers, and cache residency independently. The cached-fetch witness must bind the exact historical translation to the resident bytes actually consumed.

None of these are sound substitutes for that join:

- fixed bit-12 / low-12-bit mapping reconstruction;
- current TLB mapping alone;
- current RDRAM bytes alone;
- virtual PC alone;
- physical backing alone;
- equal instruction payloads;
- pre/post equality of mapping content;
- treating every mapping/context reachability change as a cache-resident retirement.

A useful minimum evidence shape is:

```text
(mapping_op_generation,
 translation_context_generation,
 normalized_mapping_identity_or_exact_translation_result,
 translated_physical_address,
 architecture-neutral_resident_identity,
 physical_tag_or_equivalent_validation,
 resident_generation,
 fill/backing_provenance,
 fetch_sequence)
```

Concrete cache slot/index is an emulator-observer detail while the hardware rule remains unsettled. Production Plaid should retain an architecture-neutral resident-generation identity with enough evidence to justify its lifetime. If the relevant cache/TLB behavior cannot be modeled for the declared execution scope, closure remains OPEN.

## Remaining gaps

- No physical N64/VR4300 measurement was run; pinned ares and Gopher64 disagree on I-cache index selection.
- Combined dynamic execution covers 16 KiB and 64 KiB PageMask cases, not every legal larger page.
- Overlapping/undefined TLB entries, 64-bit mapped regions, supervisor/user region rules, reverse-endian cacheable fetch, guest CACHE operations, reset/save/restore epochs, NMI/reset interactions, and non-identity/degraded RDRAM remain separate obligations.
- ASID leave/return is directly staged here to isolate lifetime behavior; guest context-writer provenance comes from the completed MTC0/TLBR lanes.
- Backing mutation is debugger-side to isolate the cache-lifetime seam; CPU/DMA/RSP writer provenance must be composed separately in production.
- This proves bounded observed provenance/lifetime composition, not exhaustive reachability, indirect-target closure, or whole-ROM completeness.

## Integration recommendation

**ADOPT the proof obligation, not ares-specific cache indexing.** Preserve the exact translation result under its historical mapping/context generation and bind it to a distinct resident generation whose fill/backing provenance and lifetime are independently justified. Do not reconstruct large-page backing later with fixed 4 KiB geometry, and do not retire or resurrect cache generations merely from TLB/context reachability changes.

No production patch is proposed because current canonical Plaid does not yet expose a unified production TLB/context/cache-resident event stream to patch safely. The durable deliverable is the executable regression plus the composition contract for that future evidence model.

## Reproduce

With exact pins checked out under `.refs/`:

```sh
python3 -m py_compile experiments/pagemask-icache-remap/{source_guard.py,model.py,run.py}
python3 experiments/pagemask-icache-remap/source_guard.py
python3 experiments/pagemask-icache-remap/model.py
python3 experiments/pagemask-icache-remap/run.py
sha256sum target/pagemask-icache-remap/results.json
```
