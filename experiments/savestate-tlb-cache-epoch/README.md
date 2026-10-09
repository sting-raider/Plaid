# Savestate TLB + context + I-cache restore epoch experiment

Base Plaid commit: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`

Pinned ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

## Question

Can a synchronized compiler-time savestate restore reinstall an old installed TLB entry, active EntryHi/ASID translation context, and resident instruction-cache line without replaying the live operations that originally produced them? If so, can an external operation history safely keep using its latest generation IDs after load?

## Adversary

The exact-reference fixture creates coherent state S0:

- TLB slot 0 maps VA `0x4000`, ASID `0x11` to PA `0x1000`;
- a real interpreted `MTC0 EntryHi` selects ASID `0x11`;
- a cacheable TLB fetch fills instruction `0x34091111`.

It then saves a synchronized snapshot and performs two attacks.

1. **Distinct rollback:** install PA `0x3000` / ASID `0x22`, execute another real `MTC0 EntryHi`, and fetch `0x34092222`. Loading S0 must restore all three old states while external research counters and completed-fill history remain at the newer generations.
2. **Equal-state alias:** after the first load, perform a same-value TLBWI, same-value `MTC0 EntryHi`, invalidate/refill the identical S0 cache tuple, then load S0 again. Immediately before and after load, mapping values, EntryHi values, and resident line bytes/tag/index are equal. The old tuple matcher still points at fill 3 even though deserialization, not fill 3, installed the resident line after the second load.

This deliberately composes previously validated facts instead of re-proving any one of them.

## Reproduce

With the exact ares pin checked out at `.refs/ares`:

```sh
python3 -m py_compile experiments/savestate-tlb-cache-epoch/{model.py,source_guard.py,run.py}
python3 experiments/savestate-tlb-cache-epoch/model.py
python3 experiments/savestate-tlb-cache-epoch/source_guard.py
python3 experiments/savestate-tlb-cache-epoch/run.py
```

`run.py` builds an uninstrumented baseline plus generated completed-I-cache-fill instrumentation. It requires baseline, sensor-disabled and sensor-enabled architectural projections to agree and requires repeated sensor-enabled output to be byte-identical.

## Intended proof boundary

A successful run validates an **analysis chronology obligation for the exact pinned ares compiler-time oracle**, not N64 hardware savestate behavior. Savestate load is an emulator/exploration operation, not a guest-visible machine event.

The minimum safe join is snapshot-qualified. If the analysis does not serialize and restore trustworthy prior mapping/context/residency generations themselves, load must start a new restore epoch and root all reconstructed components in `(snapshot_id, restore_epoch, component)` rather than borrowing the latest live generation because values happen to match.
