# Savestate restore as a composed TLB/context/cache provenance epoch

Date: 2026-10-09

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Result: **VALIDATED for the bounded exact-pinned-ares synchronized restore composition**.

Exact-pin Actions run: `37932794526`, job `113827386285`, source head `26e8fb421375a76497f0fe36de51c47001736107`, SUCCESS. Retained result artifact: `11616269118`, artifact digest `sha256:3c6cd3e366a2e80f52b409285f532ca731ff3e623dfb298ea63dfec68a9cf839`. Canonical `results.json` SHA-256: `134004fc731a195152693394ca7a94583ddd879d2f3522e9f2d032b54c03b9f8`.

## Hypothesis

Compiler-time exploration that loads a synchronized savestate cannot keep treating pre-load external mapping-operation, translation-context and cache-fill generation IDs as causal predecessors solely because restored values match them. A sound history must either restore those causal generations under the snapshot identity or introduce a new restore epoch whose reconstructed TLB entry, EntryHi/ASID context and resident I-cache state are rooted in the same snapshot.

The bounded exact-reference experiment validates this hypothesis.

## Prior evidence composed

This experiment intentionally composes, rather than duplicates:

- validated I-cache reset/restore evidence showing a synchronized load can recreate a resident line without a new completed fill;
- same-value TLBWI/TLBWR evidence separating mapping-operation generations from mapping content identity;
- MTC0 EntryHi/TLBR evidence separating active translation-context generations from installed TLB entry generations;
- TLB/I-cache synonym/remap evidence showing mapping changes and resident cache lifetimes are distinct axes.

## Exact source contract

At the pinned ares revision, `CPU::serialize(serializer&)` serializes every I-cache line's tag/index/words, every installed TLB entry including physical address/VPN/ASID fields, and the staged SCC TLB/EntryHi fields including active ASID. `System::unserialize()` validates the snapshot, calls `power(false)` for synchronized snapshots, then invokes the same bidirectional system serializer. System serialization processes RDRAM before CPU. The CPU serialization routine contains no TLBWI/TLBWR replay and no cache-fill call.

The branch source guard checked those exact statements at the pin before the executable fixture built.

Therefore a load can directly install the old three-axis state while a research sidecar that lives outside emulator serialization still contains later operation/fill identities.

## Executable evidence

`experiments/savestate-tlb-cache-epoch/fixture.cpp` creates S0 using one installed cacheable TLB mapping, one real interpreted `MTC0 EntryHi`, and one cache fill, then saves a synchronized snapshot.

The first phase changes all three axes to visibly different S1 state: slot 0 maps the same VA through ASID `0x22` to PA `0x3000`, EntryHi selects ASID `0x22`, and the resident line contains `0x34092222`. Loading S0 restores the slot to ASID `0x11` / PA `0x1000`, restores EntryHi/ASID `0x11`, and restores the resident `0x34091111` cache line. External mapping/context counters and the completed-fill observer do not rewind and receive no replay events. A post-load fetch hits the restored resident line without a new completed fill.

The second phase is the stronger equality adversary. It mints newer same-value mapping and EntryHi generations, invalidates/refills an exact-equal S0 cache tuple, then loads S0 again. Mapping contents, EntryHi/ASID, cache tag/index/words and instruction payload are equal immediately before and after load, but the causal installer after load is deserialization rather than the historical live operations. The existing historical tuple matcher returns fill `3`, demonstrating the false cross-load join directly.

Final result payload:

```json
{"external_generations":{"context":3,"mapping":3,"restore_epoch":2},"fill_count":3,"naive_post_restore_fill":3,"state":{"asid":17,"cache_tag":4097,"cache_word0":873009425,"distinct_rollback":true,"entryhi":16401,"equal_state_restore":true,"exception":0,"t1":4369,"tlb_pa0":4096}}
```

`run.py` also requires the uninstrumented baseline, generated instrumentation with observer disabled, and observer-enabled execution to have identical reported architectural state and external generation counters. The enabled run repeats byte-identically. All checks passed in the exact-pin Actions job.

`model.py` separately attacks the proposed certificate with mixed snapshot IDs, mixed restore epochs, live-generation substitution and equal-value latest-generation substitution. It rejects six forged histories; its deterministic logical report SHA-256 is `600de9c2843690b8221161daf38aaef06e8b74f46a47c6a05077d535a8dc7ed9`.

## Minimum evidence rule

For a load of snapshot `S` creating exploration epoch `E`, each reconstructed executable-state component must be represented as either:

1. a trusted causal generation serialized inside `S` and restored under capture `S`, or
2. a restore root such as `restore(S, E, component)`.

The mapping, translation context and cache residency used for one fetch must agree on the same restore capture/epoch when their causality crosses that load. Current value equality, physical backing equality, identical TLB contents, identical ASID, identical cache tag/index/words, or “latest matching generation” are insufficient substitutes.

A sidecar that is not itself serialized must never inherit the abandoned future's latest mapping/context/fill IDs across load. If the sidecar cannot reconstruct snapshot-qualified causal identities, those restored component origins are UNKNOWN except for the restore root.

## Closed-world impact

Without this boundary, checkpoint-based exploration can manufacture an impossible executable lineage: bytes observed after load may be attached to mapping/context/fill generations that occurred only in the abandoned post-snapshot future. Such a forged join could falsely satisfy executable-byte provenance, executable-lifetime and indirect-reachability obligations and therefore contribute to an unsound CLOSED result.

This result closes the bounded question of whether one synchronized pinned-ares restore can simultaneously resurrect installed mapping, active translation context and resident executable cache state without replaying the corresponding live events: it can.

## Remaining gap

This is an analysis/exploration chronology result, not an N64 hardware savestate claim. The fixture invokes the exact `CPU::TLBWI()` implementation for controlled TLB row installation rather than decoding a guest TLBWI instruction; the active EntryHi changes are real interpreted `MTC0` instructions. Prior TLBWI/TLBWR research supplies the separate guest-operation generation evidence being composed here.

The result does not model guest-visible reset/NMI, prove full-system provenance serialization, cover every external device, hidden RDRAM, RSP state, queue token or frontend save/load path, define persistent snapshot IDs across distributed workers, or by itself provide a whole-ROM closure certificate. Those unresolved components must remain OPEN/UNKNOWN until they have equivalent restore-epoch treatment.

## Integration recommendation

**ADOPT** the snapshot-qualified restore epoch as a hard composition boundary for compiler-time exploration. On load, either restore trusted provenance histories from the same snapshot namespace or create fresh restore-root identities for installed TLB state, active translation context, resident cache state and every other executable-relevant serialized component. Require composed fetch evidence to agree on capture/restore epoch. Never repair a missing restore lineage by matching values to the latest pre-load operation.
