# Actual identity-mapped RAM burst witnesses

2026-10-08. Hypothesis: sampling existing RDRAM burst results and stores can
establish actual backing transactions for the controlled cache cases, without
another guest read or clock. The pinned bus routes instruction-cache bursts
through MI to RDRAM::Writable; successful identity-mapped readBurst returns the
existing eight words, while writeBurst performs existing stores/hidden updates.
Opt-in callbacks sample these points in an ignored generated header. They never
invoke a memory/coherence/translation helper or change an N64 object layout.

Spike 016 reuses seventeen original guest instructions/eight cache operations
from spike 015. Four actual 32-byte RAM reads at 0/0x4000/0/0x4000 match the exact
four fill payloads; a completed 32-byte RAM store at 0x4000 matches the measured
writeback. Every requestor is instruction cache. Direct out-of-bounds test calls
return zero words/ignore stores and supply no valid backing witness, with no
change to the complete prior CPU/device-visible state. Plain/traced/repeated
checkpoints match and JSON repeats exactly.

Removing the new transaction records reproduces the complete prior projection,
SHA-256 `63d27623769528d7147d051c8f8597ff71ffb59ad78bdffc901accdaf9d164b9`.
Count=257; prior RAM/cache goldens remain exact. A fresh default-observer spike
015 build also retains its full outcomes. A separate recipe-only regression
checks enabled/disabled/enabled directory reuse removes a stale shadow header;
compiler calls are stubbed there and no CPU execution is claimed. Actual CPU
tests compile/run the pinned separately licensed reference with recompilers off.

Scope is deliberately successful identity-mapped bursts. Nonidentity translation
can remap chips and degrade returned bits; failures can return zeros or freeze
other bus paths. No witness is fabricated for those paths. Ordinary/ebus stores,
CPU/PI copies, reset/restore and unified transaction/fill/mutation/fetch ordering
need separate coverage. A RAM transaction identifies a finite backing access;
it proves neither ROM origin nor an immutable executable/cache lifetime. No
production image, generation or native artifact is promoted.
