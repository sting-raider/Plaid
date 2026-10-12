# Decoded store64 through actual cached subwrites to backing export

This integration fixture reuses spike 034's project-owned generic lower D-cache
and successful identity-RDRAM burst callbacks on exact ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. It executes encoded SD/SDL/SDR in both
endian contexts, repeats successful stores with equal bits, then executes CACHE
0x19 to export the resident line. It also retains alignment failures.

The scope is prefilled direct-KSEG0 identity-RDRAM, kernel32 with BEV1. Explicit
fixture code/register seeds are not a general guest writer/root census. Before/
after full GPR snapshots and PC/exception results accompany actual primitive
callbacks; RAM, hidden-memory, complete D-cache, HI/LO and timing-count controls
match original/disabled/repeated runs. The 48 first-store results match the
retained 158-case aggregate matrix, which by itself did not supply this clock.

```bash
python spikes/056-ares-store64-writeback-compose/run.py
python scripts/test_store64_writeback.py
```

The second command reuses the authenticated retained source without rebuilding
the emulator. Inputs/binaries/notices/observations remain under ignored
target/store64-writeback-primary. The first command builds the original and
instrumented references only when their source manifests change. No workflow or
runtime reference dependency is introduced. Hardware atomicity, complete
mutation sensing, operand-definition ancestry, TLB/restore/cache lifetime and
whole-ROM/native closure remain OPEN. See ADR-0121 and the integration receipt.
