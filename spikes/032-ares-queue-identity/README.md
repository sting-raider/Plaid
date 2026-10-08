# Finite queue insertion identities

Run `python spikes/032-ares-queue-identity/run.py` (Windows uses WSL Ubuntu G++).
The clean pinned nall container is compiled separately as baseline and with an
optional generated header. Metadata outside its unchanged object follows actual
heap copies, successful insertion, cancellation, removal, reset and serialization.
Original source, license, binaries and receipts remain ignored under `target/`.

Six original cases cover heap movement, duplicate IDs, cancellation/repeated
cancellation, full capacity occupied by invalid entries, clock wrap, serialization/
restore and identical event/deadline insertions. Reported dispatches, occupied
serialized checkpoints and object size match original/disabled/repeated builds.
The independent ledger checker rejects five token/event/validity/movement attacks.
It conservatively loses identities at serialization boundaries. This is actual
container execution; CPU/device dispatch, transfer completion, hardware timing
and arbitrary checkpoint lifecycles remain unclaimed. See the research receipt.
