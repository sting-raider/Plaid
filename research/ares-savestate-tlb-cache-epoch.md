# Savestate restore as a composed TLB/context/cache provenance epoch

Date: 2026-10-09

Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

Status: **IN PROGRESS** pending exact-pin executable CI.

## Hypothesis

Compiler-time exploration that loads a synchronized savestate cannot keep treating pre-load external mapping-operation, translation-context and cache-fill generation IDs as causal predecessors solely because restored values match them. A sound history must either restore those causal generations under the snapshot identity or introduce a new restore epoch whose reconstructed TLB entry, EntryHi/ASID context and resident I-cache state are rooted in the same snapshot.

## Prior evidence composed

This experiment intentionally composes, rather than duplicates:

- validated I-cache reset/restore evidence showing a synchronized load can recreate a resident line without a new completed fill;
- same-value TLBWI/TLBWR evidence separating mapping-operation generations from mapping content identity;
- MTC0 EntryHi/TLBR evidence separating active translation-context generations from installed TLB entry generations;
- TLB/I-cache synonym/remap evidence showing mapping changes and resident cache lifetimes are distinct axes.

## Exact source contract

At the pinned ares revision, `CPU::serialize(serializer&)` serializes every I-cache line's tag/index/words, every installed TLB entry including physical address/VPN/ASID fields, and the staged SCC TLB/EntryHi fields including active ASID. `System::unserialize()` validates the snapshot, calls `power(false)` for synchronized snapshots, then invokes the same bidirectional system serializer. System serialization processes RDRAM before CPU. The CPU serialization routine contains no TLBWI/TLBWR replay and no cache-fill call.

Therefore a load can directly install the old three-axis state while a research sidecar that lives outside emulator serialization still contains later operation/fill identities.

## Controlled adversarial construction

`experiments/savestate-tlb-cache-epoch/fixture.cpp` creates S0 using one installed cacheable TLB mapping, one real interpreted `MTC0 EntryHi`, and one cache fill, then saves a synchronized snapshot.

The first phase changes all three axes to visibly different S1 state and loads S0. Assertions require the TLB row, EntryHi/ASID and resident I-cache tuple to roll back together while external mapping/context counters and the completed-fill observer do not rewind or receive replay events. A post-load fetch must hit the restored resident line without a new fill.

The second phase is the stronger equality adversary. It mints newer same-value mapping and EntryHi generations, invalidates/refills an exact-equal S0 resident tuple, then loads S0 again. Values immediately before and after load are identical, yet the causal installer changed from the live fill to deserialization. The historical tuple matcher is expected to return the latest equal fill, demonstrating a false join if load is not an explicit epoch boundary.

`model.py` separately attacks the proposed certificate with mixed snapshot IDs, mixed restore epochs, live-generation substitution and equal-value latest-generation substitution. The current local model rejects six forged histories; its deterministic report SHA-256 is `600de9c2843690b8221161daf38aaef06e8b74f46a47c6a05077d535a8dc7ed9`.

## Minimum evidence rule under test

For a load of snapshot `S` creating exploration epoch `E`, each reconstructed executable-state component must be represented as either:

1. a trusted causal generation serialized inside `S` and restored under capture `S`, or
2. a restore root such as `restore(S, E, component)`.

The mapping, translation context and cache residency used for one fetch must agree on the same restore capture/epoch when their causality crosses that load. Current value equality, physical backing equality, identical TLB contents, identical ASID, identical cache tag/index/words, or “latest matching generation” are insufficient substitutes.

## Closed-world impact

Without this boundary, checkpoint-based exploration can manufacture an impossible executable lineage: bytes observed after load may be attached to mapping/context/fill generations that occurred only in the abandoned post-snapshot future. Such a forged join could falsely satisfy executable-byte provenance, lifetime and indirect-reachability obligations and therefore create an unsound CLOSED result.

## Remaining gap

Exact pinned-reference execution and neutrality checks are still pending at this checkpoint. Even if validated, this result is scoped to compiler-time ares synchronized savestate exploration. It does not model guest-visible hardware reset/NMI, prove full-system provenance serialization, cover external devices/hidden RDRAM/RSP state exhaustively, or by itself provide a whole-ROM closure certificate.
