# CPU-copy backing transaction experiment

Hypothesis: in pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, an uncached KSEG1 `LW` -> `SW` copy can be joined to exact successful scalar identity-mapped RDRAM read/write transactions, but the same rule is invalid for cached KSEG0 copies because the load/store can terminate in D-cache residency and reach backing RDRAM only through cache-line fill/writeback.

The adversarial cached fixture loads word `0x11223344` through KSEG0, overwrites the same physical source through a KSEG1 alias with `0x55667788`, stores the still-loaded original word into a cached destination, verifies backing RAM still holds the old destination word before writeback, then executes guest `CACHE 0x19` (D-cache hit writeback). This is intended to falsify any provenance rule based on current backing RAM or register equality rather than ordered transactions.

Run:

```sh
python3 spikes/020-ares-cpu-copy-transactions/run.py
```

The runner requires `.refs/ares` at the exact pinned revision. It builds an unmodified-reference baseline and a generated-header instrumented build, compares final CPU/cache/RAM state, repeats the traced run byte-for-byte, and asserts the scalar/burst transaction chronology. Generated binaries, traces, and reference source remain under ignored `target/` / `.refs/` paths.

Status: experiment checkpoint; final verdict and exact observed evidence will be added after execution.
