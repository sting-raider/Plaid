# Large-PageMask TLB -> I-cache resident provenance composition

Date: 2026-10-10

Result: **VALIDATED for the bounded exact-pinned ares composition tested here**.

This worker does not claim a new primitive hardware rule. It composes already validated Plaid research at a seam that had remained explicitly open: large-PageMask translation had only been executed with uncached fetches, while cacheable TLB/I-cache lifetime research had only exercised ordinary 4 KiB mappings.

## Question

When a cacheable executable fetch uses a 16 KiB or 64 KiB TLB mapping, what identities must a closed-world proof preserve across same-value TLB writes, backing mutation, remaps, temporary mapping/context unreachability, and PageMask geometry changes?

The falsifiable hypothesis was that current virtual PC, current backing contents, current TLB mapping, or equal instruction bytes are individually insufficient. A defensible cached-fetch witness must compose, at minimum:

1. the ordered mapping-operation generation and translation-context generation;
2. the normalized PageMask/EntryLo selection that produced the fetch translation;
3. the actual translated physical address / physical cache tag;
4. the backing writer generation that supplied a cache fill;
5. a distinct cache-resident generation preserved until a verified cache lifetime boundary.

A TLB rewrite or temporary ASID unreachability was hypothesized **not** to be a cache-resident retirement by itself. A remap whose actual translated physical tag changes was hypothesized to force a miss/refill on the next cacheable fetch, even when the new instruction payload is equal.

## Exact inputs

Canonical Plaid base at claim time:

- `211176e7a489fecf8331d02915ee982cd279cb62`

Exact references from `refs.lock.toml`:

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- n64-systemtest: `196f5421173220eb2f63a7a99c64795dc0ea0698`

Prior independently validated inputs composed here:

- `research/tlb-pagemask-gpt56sol`, final research head `409017c6be4aff64b53f1d93161cc23d4696aee6`: PageMask selects EntryLo/offset using normalized page geometry and actual translated PA; fixed bit 12 is unsound for large pages.
- `research/tlb-icache-synonyms-gpt56sol`, current research head `40d44a590e8c3c00d0b930e7603e2ff86b2a4178`: exact pinned ares can retain stale cacheable executable residents across backing mutation and TLB remap-away/back, while a different physical tag forces refill.
- `research/tlbwi-mapping-generation-gpt56sol`: legal same-value TLBWI is an ordered mapping operation even when pre/post mapping content is equal; mapping-operation identity is distinct from content identity and I-cache lifetime.
- completed ASID/TLBR cache-lifetime work from issue #4: translation-context reachability is distinct from installed mapping and resident-cache identity.

No production Plaid file is modified on this branch.

## Exact source contracts

`experiments/pagemask-icache-remap/source_guard.py` requires clean exact reference revisions and guards the following composition.

Pinned ares TLB synchronization derives:

```text
pageMask &= supported alternating bits
pageMask |= pageMask >> 1
addressMaskLo = (pageMask | 0x1fff) >> 1
addressSelect = addressMaskLo + 1
```

Mapped fetch translation selects the EntryLo half using `vaddr & addressSelect` and computes the physical address from that EntryLo base plus `vaddr & addressMaskLo`.

Pinned ares cacheable mapped fetch then calls I-cache with both the original virtual address and translated physical address. Its I-cache selects a resident slot from `vaddr >> 5 & 0x1ff`, tests a physical 4 KiB tag from `paddr & ~0xfff`, fills from that physical tag plus the line offset, and reads the fetched word lane from translated `paddr`.

Source SHA-256 receipts from Actions run `38003027737`:

```text
ares tlb.cpp:       93722177331f1df2cd7cbf313909bf20a148183d8cbd73db928b7cf0bff506d1
ares memory.cpp:    55f833718501d018d7e81e089a1ca53a9891154b8952cc2ec1b5126fda632c74
ares cpu.hpp:       6f252eda8444e447031d1bdbbd094ed8286a5028e2136c9ccca911287512fc27
Gopher64 cache.rs:  45fad688563424d08d8dbbd094ed8286a5028e2136c9ccca911287512fc27
n64-systemtest TLB: 221bc0f3239ddbb1f9e4d16b2910edf007db34997915db7b2d4703f5683d88f4
```

**Correction:** the Gopher64 cache receipt printed by the actual run is `45fad688563424d08d8db0e2ce52c588f65cb8f114f14648e190dee6090af177`; the line above is intentionally not used as evidence and is superseded by this exact runner output. The source guard also preserves a material emulator disagreement: pinned Gopher64 selects I-cache lines by physical address, unlike the ares virtual-index selection. Therefore the portable conclusion is a provenance/lifetime obligation, not an assertion that ares cache indexing is universal VR4300 hardware truth.

Pinned n64-systemtest independently labels the PageMask encodings used for 16 KiB and 64 KiB mappings. It was source-inspected, not executed on physical hardware in this worker.

## Combined exact-pinned ares fixture

`experiments/pagemask-icache-remap/driver.cpp` uses the existing Plaid headless exact-ares build path with CPU/RSP recompilers disabled and identity RDRAM. It executes real ares TLBWI mapping operations and interpreted synthetic instructions.

### 16 KiB false-4K selector

VA `0x00021000` is in the **even** half of a 16 KiB mapping because the synchronized selector is bit 14 (`0x4000`), even though virtual bit 12 is set. The real translated executable word is at PA `0x00011000`. An equal-valued instruction is planted at the fixed-4K decoy `0x00020000`.

The first cacheable fetch misses once, executes `0x1111`, and installs physical cache tag `0x00011001`.

A legal same-value TLBWI of the same mapping leaves that resident line valid with the same tag. This combines the prior mapping-operation result with cache lifetime: an operation generation occurred, but it did not itself mint a new resident generation or retire the old one.

The physical backing at PA `0x00011000` is then changed to instruction `0x2222` with no cache operation. A subsequent fetch is a hit with no additional miss and still executes resident `0x1111`. Current backing contents are therefore not executable provenance for the hit.

### Equal-payload physical remap

The same VA is remapped, still as 16 KiB, to actual PA `0x00031000`, which is deliberately given the same `0x1111` instruction payload. TLBWI itself again leaves the prior cache line valid/tagged `0x00011001`; the next fetch detects physical-tag mismatch, incurs exactly one miss, refills, remains value-equal at `0x1111`, and changes resident tag to `0x00031001`.

Thus equal payload does not preserve resident or backing identity across a translated-physical-tag change.

### Remap-away/back and context unreachability

The fixture returns to the original 16 KiB mapping, fetches current backing `0x2222` to establish a fresh resident at tag `0x00011001`, then changes that physical backing to `0x4444`.

It remaps the VA away and back without an intervening fetch. The resident remains valid and tag-identical. Fetching after return incurs no miss and executes stale resident `0x2222`, not current backing `0x4444`.

The fixture then directly stages a nonmatching ASID, attempts the same VA, and receives TLB-load exception code 2. The failed translation incurs no I-cache miss and leaves the resident valid/tag-identical. Restoring the matching ASID and fetching again incurs no miss and still executes stale resident `0x2222`.

The direct ASID staging here is intentionally a composition fixture, not a re-proof of guest MTC0/TLBR semantics. Those context-writer primitives were independently validated elsewhere. The result here is the lifetime statement: temporary translation unreachability does not, by itself, retire the resident in exact pinned ares.

### Same-VA 16 KiB -> 64 KiB geometry change

The same VA is then mapped through a 64 KiB PageMask (`addressSelect=0x10000`). Correct large-page translation yields PA `0x00051000`. A fixed-4K bit-12 reconstruction would choose the equal-valued decoy at `0x00070000`.

The next cacheable fetch incurs one miss and installs tag `0x00051001`, while executing the same external payload `0x2222`. Changing only mapping geometry therefore cannot be reconstructed downstream from fixed-4K rules, current bytes, or value equality; the exact translated PA and new resident generation are required.

A separate 64 KiB odd-half control uses VA `0x00070000`, for which bit 12 is clear while PageMask selector bit 16 selects EntryLo1. Equal-valued bytes exist at the fixed-4K EntryLo0 decoy PA `0x00080000`, but the actual cache tag is `0x000a0001` and the executed instruction is fetched from PA `0x000a0000`.

### Exact fixture receipt

Actions run `38003027737`, job `114065363686`, exact behavior head `347680f4f14f6860c9e24bde46b9253dcedc94b7`:

```text
fixture stdout SHA-256: 79bf5340619d62ee2afc1c5862ee324d5403eec9fc697b84153b15d9703134ea
result JSON SHA-256:    7d0116e2a31c186951ebb248ac81b78df2fcb342ccbb005f6aa88e2fd44c0f86
I-cache state SHA-256:  9929c6d182ea6efd93fe325a9c71040c944babd9037fba2f7254ca944471125d
```

Miss chronology in the accepted result:

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

## Independent adversarial composition model

`model.py` is not derived from the ares fixture output. It independently implements the guarded PageMask formulas and a minimal cache-resident state machine with separate:

- mapping operation generation;
- translation-context generation;
- translated PA / physical tag;
- backing writer generation;
- resident generation.

The canonical scenario reproduces the expected causal relationships, then forges six witnesses independently. Every forged witness is rejected:

```text
current_backing
equal_payload_new_resident
fixed4k_paddr
wrong_context_generation
wrong_mapping_generation
wrong_physical_tag
```

It also explicitly models two equal-content mapping generations for same-value TLB writes, proving the model does not collapse operation generation into mapping content identity.

A deterministic 50,000-case 16 KiB/64 KiB sweep (`seed=0x504c414944cace`) produced:

```text
fixed-4K (half,PA) wrong: 46,065 / 50,000
physical cache tag wrong: 46,065 / 50,000
bit-12 half alone wrong:  25,028 / 50,000
```

Model SHA-256:

```text
922c54f8c09f6f330cea4b1307c059b68423be6faaeb81c79dbe0db1bc671327
```

This sweep measures the failure surface of a tempting reducer. It is not guest reachability evidence.

## CI artifact

Run `38003027737` succeeded end-to-end. Uploaded artifact:

```text
artifact id:     11650076724
artifact bytes:  2755
artifact digest: sha256:3ed2f0e3108b78f802964304f628175d7acc61855a9aaacc415de8d9f037b219
```

The runner executes the exact fixture twice and requires byte-identical stdout before accepting the receipt.

## Result

**VALIDATED**, narrowly.

For the tested exact-pinned ares cacheable 16 KiB/64 KiB mappings, PageMask-aware translation composes cleanly with physical-tag I-cache residency only when the proof keeps the causal join explicit:

```text
ordered mapping operation + translation context
    -> normalized PageMask/EntryLo translation
    -> actual translated physical address/tag
    -> cache fill and backing writer identity
    -> resident generation/lifetime
    -> cached instruction fetch
```

None of the following is a sound substitute:

- fixed bit-12 / low-12-bit TLB reconstruction;
- current TLB mapping alone;
- current RDRAM bytes alone;
- virtual PC alone;
- physical backing alone;
- equal instruction payloads;
- pre/post equality of TLB mapping content;
- treating every mapping/context reachability change as a cache-resident retirement.

A mapping operation generation and a resident generation are different things. A same-value legal TLBWI is still an operation generation but does not automatically begin/end a resident lifetime. Conversely, a subsequent fetch through a changed translated physical tag creates a new resident generation even when its bytes are equal to the prior resident.

## Closed-world impact

This closes one composition gap between previously separate PageMask, TLB-generation/context, and cached-executable lifetime results. A future WholeRom/native-complete certificate cannot merely prove each primitive in isolation; its fetch witness must bind the exact historical translation to the resident bytes actually consumed.

A useful minimum evidence shape is:

```text
(mapping_op_generation,
 translation_context_generation,
 normalized_mapping_identity_or_exact_translation_result,
 translated_physical_address,
 cache_slot_or_architecturally-equivalent_resident_identity,
 physical_tag,
 resident_generation,
 fill/backing_provenance,
 fetch_sequence)
```

Fields such as concrete cache slot/index are emulator-observer details when the hardware rule is unsettled; production Plaid should preserve an architecture-neutral resident-generation identity and enough evidence to justify it. If relevant cache/TLB behavior cannot be modeled for the declared scope, closure remains OPEN.

## Remaining gaps

- No physical N64/VR4300 measurement was run. Pinned ares and Gopher64 materially disagree on I-cache index selection, so no universal virtual-index hardware rule is claimed.
- Dynamic execution covers 16 KiB and 64 KiB PageMask cases only; larger legal pages remain model/source composition rather than combined cacheable execution.
- This worker does not solve overlapping/undefined TLB entries, 64-bit mapped regions, supervisor/user region rules, reverse-endian cacheable fetch, guest CACHE operations, reset/save/restore epochs, NMI/reset interactions, or non-identity/degraded RDRAM.
- The ASID leave/return phase directly stages the context to isolate lifetime behavior. Guest context-writer provenance is delegated to the already validated MTC0/TLBR research.
- Backing mutation is debugger-side in the fixture to isolate the cache-lifetime seam. CPU/DMA/RSP writer provenance is separately researched and must be composed in production.
- This proves bounded observed provenance/lifetime composition, not exhaustive reachability, indirect-target closure, or whole-ROM completeness.

## Integration recommendation

**ADOPT the proof obligation, not ares-specific cache indexing.** When cached executable provenance is required, preserve the exact translation result under its historical mapping/context generation and bind it to a distinct resident generation whose fill/backing provenance and lifetime are independently justified. Do not reconstruct large-page backing later with fixed 4 KiB geometry, and do not retire/resurrect cache generations merely from TLB/context reachability changes.

No production patch is proposed from this worker because Plaid's current canonical phase does not yet have a unified production TLB/context/cache resident event stream to patch safely. The durable artifact is the composition contract and adversarial executable regression for the primary integrator to adopt when that evidence model is introduced.

## Reproduce

With exact pins checked out under `.refs/`:

```sh
python3 -m py_compile experiments/pagemask-icache-remap/{source_guard.py,model.py,run.py}
python3 experiments/pagemask-icache-remap/source_guard.py
python3 experiments/pagemask-icache-remap/model.py
python3 experiments/pagemask-icache-remap/run.py
sha256sum target/pagemask-icache-remap/results.json
```

Expected behavior receipt from run `38003027737`:

```text
MODEL_SHA256=922c54f8c09f6f330cea4b1307c059b68423be6faaeb81c79dbe0db1bc671327
FIXTURE_STDOUT_SHA256=79bf5340619d62ee2afc1c5862ee324d5403eec9fc697b84153b15d9703134ea
RESULT_SHA256=7d0116e2a31c186951ebb248ac81b78df2fcb342ccbb005f6aa88e2fd44c0f86
```
