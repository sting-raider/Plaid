# Promoted DMA request identity on the CPU consumption graph

The guest prefix/checkpoints are unchanged from spike061. Add actual
pending->current promotion and completion-before-busy-clear/handoff callbacks.
Mint request identity at the raw promotion ordinal and bind every completed
reverse-DMA Word to that identity, preserving individual byte writers through
actual CPU fetch and decoded execution.

```sh
python spikes/062-promoted-dma-cpu-consumption/run.py
python spikes/062-promoted-dma-cpu-consumption/run.py --verify-existing
python scripts/test_rsp_definitions.py --promoted --source target/promoted-dma-cpu-consumption-primary/source.json
```

The recipe authenticates/re-executes the retained spike061 unchanged-reference
binary and checks all nineteen controls against the recorded v4 baseline. Build
only the required new sensor. Digest enrollment is durable in issue4/comment
6125875532; reject changed controls/binary/build/source. Optional sensing adds
no reference object fields, guest reads or guest program changes. Disabled,
enabled and repeated sensor state/checkpoints match the authenticated baseline.

Independent complete136-event replay checks promotion54, separate writes55/56
and completion57; the exported NOP reaches CPU fetch132/read133/decoder135.
The verifier checks descriptor-derived Word count, lane order, length/count/skip
row progression, PBUS wrapping and final endpoints. A nonempty fragment set
cannot stand in for a complete declared transfer. Focused regressions retain the
prepared PR29 early-completion counterexample and exercise count/skip/wrap,
equal reloads and immediate completion-to-promotion identity.

Only the controlled promoted-current DMEM egress scope is represented. Mutable
pending length commits and sampled BUSY falling edges supply no identity. General
FIFO/hardware policy, accepted pending requests, restore/reset/DMA ingress,
writer census, executable lifetime and whole-ROM/native closure remain OPEN.
All certification flags stay false. V0-v4 reports/default behavior remain exact;
generated reference shadows/binaries/captures stay ignored with ISC notices.
