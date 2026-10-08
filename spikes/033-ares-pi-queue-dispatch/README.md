# PI request -> queue token -> dispatch contract

This bounded spike tests the minimum evidence needed to join a pinned ares PI DMA request to a later PI completion without borrowing the latest PI write context.

Run:

```sh
python3 spikes/033-ares-pi-queue-dispatch/run.py
```

The runner requires `.refs/ares` at exact revision `9408cb43d4948fc3ea6e152a307a34348df3fe04`. `source_guard.py` checks the relevant queue, CPU and PI source contracts. `model.py` is an original fail-closed model of the already-validated queue-identity sensor composed with PI request/dispatch/completion boundaries. It runs fixed counterexamples plus 2,000 deterministic 80-action fuzz histories and an independent ledger replay that rejects five forged joins.

The important cases are successful read/write requests, silent queue-capacity rejection despite the immediate PI copy effect, cancellation followed by an identical event, equal-deadline distinct tokens, and serialization/restore identity loss. A completion is certifiable only when one request is bound to one successful insertion token, that token survives uncanceled in the same capture epoch, the valid removal is the one immediately consumed by CPU dispatch with the same event class, and the common `PI::dmaFinished()` call occurs under that dispatch context.

This spike does **not** execute the full pinned CPU/PI implementation. Actual queue-container identity/movement behavior is inherited from `spikes/032-ares-queue-identity/`; the new CPU/PI composition is source-guarded and model/fuzz tested. Therefore the result is `PARTIAL`, not a hardware or full-core completion certificate. A future full-core observer should reuse this contract and must preserve fail-closed behavior across reset/savestate lifecycles.
