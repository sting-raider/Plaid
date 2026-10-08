# Bounded boot PI request and queue history

Original optional streamed research sensor, exact pinned ares only. It composes
the validated request/queue/CPU-dispatch boundaries with history v1's actual ROM
halves, buffer consumption and successful RDRAM byte writes. Prior histories and
checkpoints must remain exact complete projections.

```sh
python3 spikes/037-ares-boot-pi-queue-history/test_verify.py
python3 spikes/037-ares-boot-pi-queue-history/run.py --budget 10000
python3 spikes/037-ares-boot-pi-queue-history/run.py --budget 610000 --capture queue
python3 spikes/037-ares-boot-pi-queue-history/run.py --budget 610000 --verify-existing
```

The full check can reuse the retained fully checked spike-030 v1 baseline. It
still compares every byte, complete footer, source, projection and reported
checkpoint; it does not accept a cached report as evidence.

Pre-capture queue rows have token/request zero. Successful insertion alone mints
a token. Save preserves identity; reset/load cuts it. Copy effects may exist even
if insertion fails. The declared no-host-restore boot policy rejects a captured
load boundary; cut behavior is independently tested by the component fixtures.
An actual valid removal must supply the immediate CPU dispatch,
and each known PI status stays bound to that scope. Equal event/deadline/value
fields supply no identity. Legacy v1 status fields retain their original weaker
last-copy metadata and are not promoted into the new dispatch witness.

`test_verify.py` exercises scheduling contracts and forged histories only. The
complete runner separately delegates buffered-source and v0/v5 validation and
compares original/disabled/enabled/repeated reference output. Real source data and
licensed generated upstream sources stay under ignored `target/` and `.refs/`.

Status is research-only. General PBUS destinations, cache/copy/mutation lineage,
lifetimes, reentrancy and whole-ROM closure remain unknown. No ProgramMap source
or native artifact is promoted; `native_complete` stays false.
