# Physical PI storage writers to executable consumption

The existing PI lineage consumer now composes an authenticated byte attempt with
its actual completed storage primitive. The primitive must be immediate, unique,
one byte wide and agree with the attempt's PC/value. Its physical address may
differ from the requested address after RDRAM translation. Retain its original
writer ordinal. A successful identity-wrapper receipt continues to select that
separate writer, and must agree with the physical sink. Missing primitives and
unknown cartridge origins mint no parent; malformed or ambiguous intervals reject.
An ordinary backing change never refreshes an I-cache generation.
The legacy `failed_destination_witnesses` counts missing identity receipts; it
does not establish failure of a separately observed translated write.

The actual pinned fixture executes three PI I/O requests: identity copy, translated
copy and failed translation. It verifies returned ROM halves and every primitive's
attempt/return position. Both successful copies feed a real CPU instruction at
their physical destination. Eight full RAM/hidden hashes and selected GPR/PC/CP0/
PI state checkpoints agree across the separate baseline, disabled, enabled and
repeated controls; the 110-event enabled source repeats exactly. Host descriptor
calls and mapping changes are explicit controls. This does not prove decoded
guest MMIO, guest mapping ancestry, queue completion or hardware timing.

```text
python spikes/088-pi-storage-executable/run.py
python spikes/088-pi-storage-executable/run.py --verify-existing
python spikes/088-pi-storage-executable/test_consumer.py
python spikes/088-pi-storage-executable/test_retained.py
cargo test --locked -p plaid-core --test core pi_history::
```

`check_retained.py` is a delta check on an already validated complete source.
Require independently retained source and canonical-report digests. It hashes
every source byte and checks every PI interval against the new guard. Reuse the
earlier report only if every completed primitive still selects the same wrapper
writer; any newly selected physical-parent branch rejects this shortcut. The
supplied twenty-million source passes all 1,048,576 attempts; 1,978,805 ordinary
storage effects remain outside those attempts. This does not replace initial
source validation, mint a mutation census or certify future execution. Native and
whole-ROM closure remain OPEN. Reference sources, notices and local ROM evidence
stay in ignored paths.
