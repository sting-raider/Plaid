# PI request -> queue token -> CPU dispatch

This bounded spike tests the minimum evidence needed to join a pinned ares PI DMA request to the later queue removal / CPU dispatch that invokes the common PI completion handler, without borrowing the latest PI write context or mistaking the handler for the byte-transfer boundary.

Pinned upstream revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Run

Source-guarded model and fuzz contract:

```sh
python3 spikes/033-ares-pi-queue-dispatch/run.py
```

Actual pinned-core fixture:

```sh
python3 spikes/033-ares-pi-queue-dispatch/actual.py
```

Both require `.refs/ares` at the exact pinned revision.

## What is exercised

`source_guard.py` checks 13 queue / CPU / PI source contracts. `model.py` runs fixed adversaries plus 2,000 deterministic 80-action fuzz histories and rejects five forged histories.

`actual.py` then builds and executes the real pinned ares headless N64 core. It reuses the external queue-identity sensor from `spikes/032-ares-queue-identity/` and adds only project-owned research metadata. The fixture executes actual `PI::ioWrite`, `PI::dmaWrite`, queue insertion/removal, `CPU::synchronize`, and `PI::dmaFinished`.

It compares:

1. uninstrumented baseline;
2. observer-capable build with callbacks disabled;
3. observer-capable build with callbacks enabled;
4. a repeated enabled run.

The baseline, disabled and enabled fixture facts/state hashes must match, and repeated traced output must be byte-identical.

## Adversarial cases

- normal PI DMA write: one request -> one successful insertion token -> one valid removal -> the same token/request at actual `dmaFinished`;
- PI status cancellation: the exact token becomes invalid and no completion is certified;
- 512-slot full queue: queue insertion fails silently while the immediate actual PI byte copy still occurs, proving that copy effect does not imply scheduled completion;
- two equal-deadline `PI_DMA_Write` events: distinct queue tokens reach the common handler while request identity remains unbound;
- serialize/reset/restore: the real event survives but external identity is intentionally forgotten, so completion remains unknown.

## Validated scope

The bounded contract is:

`PI request id + PI event class -> successful queue token -> uncanceled valid removal -> CPU dispatch(event, token) -> dmaFinished under that dispatch context`

This proves a request-to-dispatch identity in the tested pinned-ares scope. It does **not** prove N64 hardware timing and does **not** mean the byte transfer occurs at `dmaFinished`. At this ares revision the PI copy is executed synchronously in the register-write path after the queue insertion attempt.

Exact-pin Actions run `37846985240`, job `113550181178`: **SUCCESS**.

- model report SHA-256: `ebab07300e683fa8d555f0fc4228fe3627b04bd261778373594be76cb3be0b27`
- model result SHA-256: `d2934edd6252f069a25eb4e57fd71ee3e1d2724a027f461685c50dea64d99d26`
- actual trace SHA-256: `a52ac2df67c03f4bbc68fe26c9a8ac09113212a9c6971af556d02d892d5d300c`
- actual result SHA-256: `3b5b3850b35dd26ad728b5bac49eb1e8791f4b749d2aba11c09ee73ae4af9b6d`

See `research/pi-request-queue-dispatch.md` for source maps, coordination provenance, exact limitations and the integration handoff.
