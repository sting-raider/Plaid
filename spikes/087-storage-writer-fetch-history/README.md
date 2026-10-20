# Storage effects on the original boot writer/fetch clock

The shared capture driver now composes spike086's passive ordinary storage
observer with the existing PI/queue/SP/fetch producer. History v5 adds strict
`storage_effect` records on the **same** original counter/context as every
existing primitive. No matching by PC/value or independent observer clocks.

The existing `sp_history` and `pi_fetch_lineage` consumers validate the complete
source and external digests, then revoke RAM parents for scalar storage effects.
Equal writes revoke parents too. Whole-RAM fill/file-load cuts clear backing
parents. These effects never refresh or retire separately witnessed I-cache
generations. Completed PI wrapper writes still select their actual successful
writer occurrence, distinct from the preceding storage primitive. V3 reports
remain compatible; v5's SP projection is labeled report-v1.

The boot contract retains `single_run_no_host_restore`. Storage restore and
retirement records reject until execution-epoch/root evidence composes. Bulk
cuts must cover the declared full8MiB backing; scalar effects admit only actual
aligned/masked Byte/Half/Word components and truncated payloads. Raw pointer,
JIT/Vulkan, hidden-RAM, general producer/mapping/cache/root coverage and all future
execution remain separate obligations. All broad proof flags remain false.

Synthetic source/CLI/independent-model regressions:

```text
cargo build --locked -p plaid
python spikes/087-storage-writer-fetch-history/test_consumer.py
python spikes/087-storage-writer-fetch-history/test_legacy_projection.py
cargo test --locked -p plaid-core --test core pi_history::
```

Use the existing ignored local capture workflow with `--history storage`. The
complete supplied CIC6105 twenty-million prefix retains69,513,732 records,
including3,027,381 additional storage effects. Baseline/disabled/repeated machine
checkpoints and complete paired fetch bytes match the authenticated earlier
capture. Reuse retained sources for compatible consumers; this capture was needed
because the old identity-only sensor lacked those occurrences. No ROM, firmware
or copyrighted raw instruction/source data belongs in Git.

`check_legacy_projection.py` streams the complete v5 history, removes only storage
rows and restores legacy ordinal/context numbering. Its reconstructed bytes must
match an independently retained v3 source digest. The actual 66,486,351-record
legacy history matches exactly; unchanged payload bytes are never reparsed.
