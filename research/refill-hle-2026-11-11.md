# Firmware-free refill boot initialization

Claim: counterfactual refill replay must initialize the same firmware-free
post-IPL1/IPL2 state as an ordinary replay before executing guest IPL3. The
counterfactual root does not change that precondition or authorize a source.
Prepared base: `37f16c6b39f1a944359208594f13e57fff1e8ebb`.

On the local GoldenEye input, a clean `--deep` build at `4e9ddde5` ran
800.055 seconds and refused with 812 non-residual blockers (490 unresolved
direct, 303 unmapped and 19 unresolved indirect) and six residual sites.
Its final refill harvest rejected all 64 requests because the required anchor,
source and footer were absent. A retained declaration set recovered 49,381
blocks and closed residual solve with six sites, then the visible dummy-audio
baseline faulted 12 at `80810a7c`, VI 2, with zero graphics tasks.

The refill oracle excluded `refill-v1` from firmware-free initialization and
therefore executed the zero-filled firmware image instead of guest IPL3. A
synthetic CIC-6102 IPL3 spin comparison fails before the change (`stop_pc`
`bfc00040` versus `a4000040`) and passes after it, comparing stop PC, steps,
VI, SP and CP0 state. `python scripts/test_refill_sources.py` passes, including
its retained real exception/DMA/TLB/ERET and provenance refusal contracts.
The exact pinned ares revision is `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

With the initializer, the same local run's anchor `7f0adabc` and target
`7f002000`, previously rejected, produce a complete 4096-byte source at ROM
offset `36b30`. This is not a game-specific source declaration; the existing
oracle validates the anchor, PI transaction, mapping, bytes and footer.
No runtime or completeness claim follows from this page. Inputs, generated code
and outputs stay under ignored `target/`.

The checked-handoff WIP starts from local commits `eb020023` and `1d7ad881`;
its reconciliation onto the current tree is preserved in a local Git stash.
Its synthetic test passes in the original tree and its lowered retained map recognizes the
dispatcher, but the real run rejects `k0` after the guest reuses it for an MI
register. An ignored diagnostic removal of that check runs 30 seconds at
VI 1798/fault 0 but produces no graphics: the pager enqueues the stopped owner
in the guest run queue without updating host scheduler ownership. Source-
verified host/guest queue integration and end-to-end validation remain open.
