# Queue identities through actual heap movement

Primary receipt, 2026-10-09. Hypothesis: external metadata can retain distinct
successful insertion identities through the pinned queue's actual heap moves,
including equal event/deadline pairs, without changing its object layout or
reported dispatch/state behavior. Removal identity must precede CPU/device joins.

`python spikes/032-ares-queue-identity/run.py` passes on clean ares/nall
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, WSL Ubuntu x64 G++ 15.2.
The generated header adds nullable callbacks at actual insertion/copy/removal/
cancellation/reset/serialization sites. All existing operations stay in place;
tokens live outside the reference queue. Reference headers/LICENSE and generated
builds remain ignored; no upstream code enters Plaid's Rust dependency graph.

The six-case, 2,104-record capture retains 523 successful insertions and one
rejection while 512 canceled entries still occupy capacity. Eight valid removals
retain distinct identities, including two identical event/deadline entries.
Two known canceled removals produce no callbacks; 512 invalid removals after a
serialization boundary have unknown identities. Two valid removals across save/
restore also remain unknown. Repeated cancellation emits 516 records total.
The observer forgets all identities at each serialization entry, including save;
this deliberately conservative policy supplies no restored identity certificate.

Original-header, observed-header disabled and repeated enabled reported dispatch
arrays, occupied serialized checkpoints and 6,152-byte queue object size agree.
Only occupied entries are compared; unused reference storage is not state evidence.
Five forged token/event/validity/movement records fail independent replay.
Result SHA-256:
`c1388fb65891853c214d3651e3a9069f317ef19f22857e778a1de2fe412c14d0`.

This executes the actual container, not CPU/device dispatch or guest PI MMIO.
The observed valid removals are dispatch candidates under the container's step
callback, not transfer completion or hardware timing certificates. Compose the
sensor with actual CPU dispatch and PI request/status boundaries before joining
queue identities to copy effects. Capture gaps, arbitrary restore/reset policies
and broader lifecycle identity remain separate obligations.
