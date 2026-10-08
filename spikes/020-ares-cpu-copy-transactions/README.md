# CPU-copy backing transaction experiment

Hypothesis: in pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, an uncached KSEG1 `LW` -> `SW` copy can be joined to exact successful scalar identity-mapped RDRAM read/write transactions, but the same direct rule is invalid for cached KSEG0 copies because the load/store can terminate in D-cache residency and reach backing RDRAM only through cache-line fill/writeback.

## Verdict: PARTIAL

The controlled uncached case is validated. The direct cached-copy rule is rejected by an adversarial stale-source alias case.

The cached fixture loads `0x11223344` through KSEG0, overwrites the same physical source through KSEG1 with `0x55667788`, stores the still-loaded original word into a cached destination, verifies backing destination RAM still contains `0xaabbccdd`, then executes guest `CACHE 0x19` (D-cache hit writeback).

Observed relevant chronology:

- uncached phase: scalar read `0x1000 -> 0x11223344`, then scalar write `0x2000 <- 0x11223344`;
- cached phase ordinal 5: D-cache fill from `0x1000`, first word `0x11223344`;
- ordinal 6: uncached KSEG1 alias store changes source backing `0x1000` to `0x55667788`;
- ordinal 7: D-cache fill from destination `0x2000`, first word `0xaabbccdd`;
- before writeback, destination backing is still `0xaabbccdd` while its resident dirty D-cache word is `0x11223344`;
- ordinal 8: D-cache burst writeback to `0x2000`, first word `0x11223344`.

Thus current source RAM at writeback is not the origin of the bytes being written. Cached CPU-copy provenance must carry versioned cache-line/lane history from fill/load through resident stores to writeback; physical address and current RAM bytes are insufficient.

Run:

```sh
python3 spikes/020-ares-cpu-copy-transactions/run.py
```

The runner requires `.refs/ares` at the exact pinned revision. It builds an unmodified-reference baseline and a generated-header instrumented build, compares final CPU/cache/RAM state, repeats the traced run byte-for-byte, and asserts the scalar/burst transaction chronology. Generated binaries, traces and reference source remain under ignored `target/` / `.refs/` paths.

Two clean isolated GitHub Actions runs passed: `37798077372` and `37798119815`. The latter produced artifact `11559372938`, digest `sha256:e8cdf9a8134b9c7f72e033398007a33691322232317728bd253f5c8b22f9135b`. The temporary CI workflow was removed after the checkpoint; the durable reproduction command is the runner above.

See `research/ares-cpu-copy-provenance.md` for source mapping, exact hashes, limitations and the integration recommendation.
