# Exception handler root x I-cache residency composition

Status: **VALIDATED for the bounded exact-pinned ares experiment**.

Successful execution receipt: Actions run `38050813544`, job `114209395345`,
behavioral result SHA-256
`9715f83c898ae315ff2be8ed95c19dbf3019e6cd44953f6eec9fabe1d5577dd8`.
See `research/exception-handler-cache-composition.md` for evidence and limits.

This bounded fixture asks whether selecting the BEV=0 general exception vector
also identifies the executable bytes that service that root. It composes existing
exception-vector and I-cache/backing primitives instead of treating either as a
whole-ROM certificate.

## Hypothesis

After a cached fetch has filled the KSEG0 general-vector line at
`0xffffffff80000180`, an uncached KSEG1 write to physical `0x180` changes RDRAM
without changing the resident I-cache line. A later real guest `SYSCALL` should
select the same vector and execute the older resident handler word until a guest
CACHE hit-invalidate forces a refill. A successful same-value backing write must
also remain a distinct storage generation even though handler bits do not change.

The exact pinned reference validated this hypothesis.

## Exact reference

- ares: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- Plaid branch base: `211176e7a489fecf8331d02915ee982cd279cb62`

The build helper generates observer-only source shadows under `target/`; the
pinned ares checkout remains unmodified. No reference code is copied into Plaid's
production runtime.

## Sequence

1. Put handler A (`ADDIU s0,zero,0x11`) at physical `0x180`.
2. Execute an actual guest `SYSCALL` from uncached KSEG1 and then the first
   instruction at BEV=0 general vector, warming the KSEG0 I-cache line.
3. Execute guest KSEG1 `SW` of handler B (`...0x22`) to physical `0x180`.
4. Trigger the same exception again with no CACHE operation. Handler A still
   executes from the resident line even though current RDRAM holds B.
5. Execute guest CACHE hit-invalidate on the vector line, trigger again, and
   require handler B plus a new completed fill.
6. Execute another successful guest KSEG1 `SW` of handler B, i.e. equal payload
   but a fresh backing operation. Trigger without invalidation and then after a
   second invalidation/refill.

Traced mode records the actual handler fetch, completed I-cache fills, and
successful scalar RDRAM writes. Plain mode leaves those observers disabled. The
runner requires repeated traced output to be byte-identical and plain/traced
architectural checkpoints to agree.

## Commands

```sh
python3 experiments/exception-handler-cache-compose/source_guard.py
python3 experiments/exception-handler-cache-compose/model.py
python3 experiments/exception-handler-cache-compose/run.py
sha256sum target/exception-handler-cache-compose/results.json \
  target/exception-handler-cache-compose/model-report.json
```

`.refs/ares` must be checked out at the exact pin first. The branch workflow does
that from scratch on Ubuntu 24.04.

## What the pass proves

Only for this bounded pinned-reference scope, exception-root selection and
handler-byte identity are separate facts. The root operation must be joined to
the actual first handler fetch and, for cached fetches, to the resident/fill
history that supplies its bytes. Current backing bytes are not a substitute.

## What it cannot prove

This is not hardware truth, arbitrary-ROM reachability, an exhaustive exception
root census, a complete cache mutation census, reset/save/restore provenance,
TLB synonym truth, or an executable lifetime certificate. Pinned references can
disagree on cache organization. Missing or ambiguous resident history must stay
UNKNOWN/OPEN rather than being repaired from value equality.
