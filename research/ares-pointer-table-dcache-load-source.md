# Cacheable pointer-table D-cache load source on pinned ares

Date: 2026-10-10  
Result: **VALIDATED for the bounded exact-reference fixture described here**  
Plaid base: `211176e7a489fecf8331d02915ee982cd279cb62`  
Reference: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`

## Question

Can a cacheable CPU pointer-table load that immediately feeds an indirect jump be causally attributed to the exact D-cache resident generation that supplied the pointer, instead of current RDRAM bytes or pointer-value equality?

For this bounded pinned-reference scope, yes. The necessary source distinction is observable and replayable, but it requires ordered cache/backing history. Current backing bytes, a physical-address immutability argument, or equal pointer values are not sufficient substitutes.

This is reference behavior, not a claim of hardware truth.

## Prior research composed

This experiment composes three already-established Plaid findings rather than reopening them:

- `research/pointer-table-immutability-aliases.md`: physical backing immutability does not by itself identify the source of a cacheable table load because D-cache residency can diverge from backing.
- the exact-reference D-cache residency/eviction work (`research/ares-dcache-eviction-lineage.md` and its research branch): cache slot/tag/fill/writeback chronology must be represented explicitly.
- `research/pointer-target-generation-lifetime.md` on `research/pointer-target-generation-gpt56sol`: the numeric pointer value is separate from the executable generation/lifetime reached by that pointer.

The remaining bounded uncertainty was the actual load-source join: whether an interpreted table `LW` that drives `JR` can be tied to the resident generation that actually supplied the register value.

## Executable fixture

`spikes/047-ares-pointer-table-dcache-load-source/` builds the exact pinned ares source with both CPU and RSP recompilers disabled. The fixture executes real interpreted MIPS instructions. A table `LW` immediately supplies the register consumed by `JR`, and each candidate target executes a distinct marker instruction.

Controlled addresses:

- table backing: physical `0x00002000`, cached KSEG0 alias `0xffffffff80002000`, uncached KSEG1 alias `0xffffffffa0002000`;
- same-D-cache-index conflict line: physical `0x00004000`;
- code: physical `0x00006000`, guest KSEG0 `0xffffffff80006000`;
- targets: `0x80007000`, `0x80007100`, and `0x80007200`.

The five cases deliberately separate payload equality from causal identity:

| Case | Ordered history before dispatch | Exact dispatch result | Backing at dispatch/end | Causal distinction |
| --- | --- | --- | --- | --- |
| `stale` | fill pointer A; uncached alias writes backing B | resident hit returns A; target A marker executes | B | resident source is older than current backing |
| `same` | fill A; uncached alias writes A again | resident hit returns A | A | equal payload, distinct backing generation |
| `refill` | fill A; backing becomes B; equal-index conflict replaces slot; table refills | miss/refill returns B; target B marker executes | B | dispatch source is the new fill generation |
| `same_refill` | fill A; backing writes A again; conflict line also contains A; table refills A | miss/refill returns A; target A marker executes | A | old resident, equal-payload decoy, new backing and new refill all contain A but remain distinct provenance |
| `resident` | backing starts B; cached store changes resident word to C only | resident hit returns C; target C marker executes | B | resident-only write supplies dispatch while backing disagrees |

The successful exact-reference run at semantic head `db3bb8e4724fed401f78f66d3d1451ea97c2ce3d` was GitHub Actions run `38046992465`.

Observed dispatch summaries were:

```text
stale:       dispatch=0x80007000 hit=True  backing=0x80007100 marker=0x11
same:        dispatch=0x80007000 hit=True  backing=0x80007000 marker=0x11
refill:      dispatch=0x80007100 hit=False backing=0x80007100 marker=0x22
same_refill: dispatch=0x80007000 hit=False backing=0x80007000 marker=0x11
resident:    dispatch=0x80007200 hit=True  backing=0x80007100 marker=0x33
```

The sensor records completed D-cache reads/writes and relevant RDRAM scalar/burst operations. Each scenario is compared against both a separately built unmodified baseline and the instrumented binary with callbacks disabled. Facts and final state hashes must agree across all three, and the traced run must repeat byte-for-byte.

## Causal replay

`verify.py` independently replays a total ordered history. It keeps separate identities for:

- physical backing word generation;
- D-cache line fill generation;
- resident slot/index/tag identity;
- per-word resident source generation;
- cached resident write generation;
- the exact dispatch-load operation at its guest virtual PC and physical table address.

Three cases make value-based provenance especially unsound:

1. In `same`, the dispatch source is the original resident fill while the backing generation advanced through a same-value uncached store.
2. In `same_refill`, both table fills and the equal-index conflict-line decoy contain pointer A. The dispatch is sourced only from the second table fill generation.
3. In `resident`, the line's fill identity remains the original fill but the dispatched word's source generation is the later cached store; current RDRAM still contains B.

The replay rejects twelve adversarial histories/claims:

1. stale load attributed to current backing;
2. same-value backing generations collapsed;
3. same-value refill attributed to the old fill;
4. equal-payload conflict-line decoy substituted as source;
5. exact dispatch load deleted;
6. same-value backing write deleted;
7. resident cached store deleted;
8. dispatch physical source forged;
9. backing write reordered after dispatch;
10. duplicate event ordinal introducing ambiguous order;
11. dispatch resident tag forged;
12. resident-only dispatch attributed to unchanged backing.

The successful strict replay report hash at the semantic validation head was:

```text
fbd918c9b8d93a838921df8c086d91dc63fe2015fa101c0a9e0b2a25a21efa39
```

All 103 `plaid-core` tests also passed in that run.

## Minimum evidence contract implied by the result

A future cacheable pointer-table certificate must not certify the table load from current RAM contents alone. For each proof-relevant load, the evidence needs enough information to reconstruct the successful operation and its actual source:

1. **Operation identity:** ordered operation identity, guest PC, effective virtual address, access width/endian context, and the physical address selected for that operation.
2. **Resident identity:** cache identity, selected slot/index, valid/tag identity, resident line generation and the per-byte/word source generation covering the loaded pointer.
3. **Miss/fill parentage:** on a miss, the exact successful fill/replacement receipt and the backing generations from which its lanes were populated.
4. **Hit continuity:** on a hit, proof that the selected resident generation remained current through the exact load, rather than consulting later backing state.
5. **Mutation chronology:** all successful cached stores and other resident mutations, including same-value stores, plus invalidation/replacement/writeback/reset/restore boundaries that can change which generation is resident.
6. **Backing chronology kept separate:** physical backing generations may advance without changing resident contents, and resident contents may advance without immediately changing backing.
7. **Target identity kept separate:** after the pointer bits are sourced correctly, the numeric target still has to be joined to the executable target generation/lifetime established by the separate indirect-target and executable-lifetime evidence.

Missing, ambiguous, reordered or contradictory history must leave this obligation UNKNOWN/OPEN. Equal payloads must never be used to borrow provenance across generations or cache slots.

## Closed-world impact

This validates a missing primitive for composing pointer-table evidence with cache history: a cacheable indirect-target load can be represented as an exact resident-generation read receipt and replayed against backing/fill/mutation chronology.

It does **not** make guarded pointer-table closure sound on its own. Plaid's current production evidence does not yet provide this complete load-source receipt/chronology for arbitrary ROM execution. A solver must therefore remain OPEN when a proof-relevant table load is cacheable and the exact resident source cannot be established.

The result also reinforces that table-target closure has two independent joins:

1. table load -> pointer value source generation; and
2. pointer value -> executable target generation/lifetime.

Satisfying one does not waive the other.

## Remaining gaps

This bounded experiment intentionally does not settle:

- real-hardware/system-test validation of the exact cache behavior;
- mapped/TLB table loads and translation-context/PageMask/ASID composition;
- explicit `CACHE` instruction variants and all invalidate/writeback interactions;
- save/restore/reset/NMI chronology;
- DMA/RSP/other-agent writes that may affect backing or residency indirectly;
- partial, unaligned or endian-changing pointer construction;
- completeness of all table writers and all guard/call sites;
- target executable-generation/lifetime closure;
- whole-ROM history scalability and completeness.

Those obligations remain OPEN when not separately proven.

## Reproduction

```sh
git -C .refs/ares checkout 9408cb43d4948fc3ea6e152a307a34348df3fe04
python3 spikes/047-ares-pointer-table-dcache-load-source/run_exact.py
python3 spikes/047-ares-pointer-table-dcache-load-source/verify.py \
  target/ares-pointer-table-dcache-load-source/evidence.json
cargo test --locked -p plaid-core
```

The branch workflow checks out the exact pinned reference, guards the source/script identities, executes the full fixture, repeats the strict replay deterministically, emits hashes, and runs the Plaid regression suite.

## Integration recommendation

Integrate the **evidence semantics**, not the research sensor: introduce a production representation equivalent to a source-bound resident-read receipt keyed to the exact load operation. Make resident line/word generations first-class and compose them with existing writer/backing history and indirect-target generation/lifetime evidence. Same-value writes, refills and replacements must mint/retain distinct causal identities. Any incomplete cache chronology must fail closed.
