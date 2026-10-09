# ares TLBWR mapping-generation identity

Date: 2026-10-09

Status: **IN PROGRESS** until the exact-pin workflow completes.

## Question

Can Plaid reconstruct every VR4300 `TLBWR` mapping-generation transition from ordinary pre/post TLB snapshots, CP0 Index, or payload equality, or must it capture the concrete random replacement slot at the mutation boundary?

## Hypothesis

At exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, `TLBWR` chooses one slot using `getControlRandom()` constrained by `Wired`, ignores CP0 Index as replacement identity, clears `devirtualizeCache`, writes the selected slot from staged `scc.tlb`, synchronizes derived entry state, and reports that concrete local slot to `debugger.tlbWrite(index)`.

Therefore a complete mapping-history stream must retain the actual selected slot and an ordered generation/event identity. Snapshot diffs may identify a value-changing write but must fail for a same-value rewrite; CP0 Index and payload matching are not substitutes.

## Exact source contract

The source guard requires, in order inside `CPU::TLBWR()`:

```text
u8 index = getControlRandom();
if(index >= TLB::Entries) return;
devirtualizeCache = {};
tlb.entry[index] = scc.tlb;
tlb.entry[index].synchronize();
debugger.tlbWrite(index);
```

It also guards `getControlRandom()`:

```text
if (scc.wired.index > 31) return (n6)random();
return random() % (32 - scc.wired.index) + scc.wired.index;
```

and the interpreter decode `op(0x06, TLBWR);`.

## Executable matrix

`spikes/044-ares-tlbwr-mapping-generation/driver.cpp` executes real `0x42000006` instructions with both CPU/RSP recompilers disabled.

1. **Misleading Index + equal payload decoy**: slot 7 already contains the target mapping, CP0 Index is 7, and `Wired=31`. The real write must change only slot 31; Index must remain 7. This falsifies `Index == replacement slot` and makes post-write payload equality ambiguous between slots 7 and 31.
2. **Same-value rewrite**: staging is copied from slot 31 and another real `TLBWR` executes with `Wired=31`. The devirtualization cache must still clear, proving the operation crossed the write path, while the entire normalized TLB snapshot must report zero changed slots. This falsifies snapshot-diff completeness.
3. **Wired range**: with `Wired=30`, 32 unique staged mappings are written. Every observed changed slot must be 30 or 31 while CP0 Index remains fixed at 5. The exact sequence is recorded and the entire executable is run twice; stdout must repeat byte-for-byte.
4. **Adversarial inference model**: 10,000 deterministic synthetic histories measure failures of snapshot-only, CP0-Index and payload-match inference, including same-value generations and duplicate equal mappings.

## Intended integration consequence

If the exact-reference run passes, an explicit TLB mapping mutation witness should minimally retain:

```text
chronology / generation id
operation kind (TLBWI or TLBWR)
selected concrete slot
full normalized pre-entry identity
full normalized post-entry identity
staged CP0 mapping state as useful evidence
Wired / Index context as context, not replacement identity
epoch (reset / restore handling remains separate)
```

The selected slot must be captured from the write boundary itself for `TLBWR` if complete same-value history matters. A consumer must not infer that slot solely from changed-state diff, payload equality, current virtual-to-physical mappings, or CP0 Index.

## Scope / non-claims

This does not characterize hardware random-number quality, `Wired > 31`, `TLBR`, `TLBP`, save-state restore, reset epochs, overlapping-entry architectural behavior, cacheable I-cache residency, or whole-ROM reachability. It is specifically a provenance/mapping-generation identity test against the exact pinned ares interpreter.
