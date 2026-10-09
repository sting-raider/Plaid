# BEV=1 32-bit TLB-refill root -> PIF provenance experiment

This branch-only experiment composes two already validated Plaid primitives:

1. a 32-bit kernel true TLB load miss with `EXL=0, BEV=1` enters the refill vector at
   `0xffffffffbfc00200`; and
2. an uncached CPU fetch from PIF ROM has PIF-byte provenance only when the exact
   active fetch contains a successful `PIF::readInt -> rom.read<Word>` backing read.

The fixture executes the actual miss against exact pinned ares, then executes the
first refill-handler instruction from synthetic PIF bytes. Instrumented and
uninstrumented builds must agree on architectural state, and the instrumented run
is repeated byte-for-byte.

Modes deliberately include equal-value decoys, a masked PIF mirror, SI bus-latch
return, and PIF ROM lockout. `model.py` also rejects forged fetch IDs, source
offsets, returned words, firmware identities, physical mirrors, vector identity
and duplicate backing ordinals.

No Nintendo firmware bytes are included. The synthetic 1,984-byte PIF image is
generated at runtime.

Run in the branch CI environment:

```sh
python3 experiments/bev1-tlbrefill-pif-root/model.py
python3 experiments/bev1-tlbrefill-pif-root/run.py
```
