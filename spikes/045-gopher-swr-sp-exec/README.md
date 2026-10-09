# Spike 045 — exact-pinned Gopher64 SWL/SWR → SP execution

Question: does exact pinned Gopher64 actually produce the source-derived complete-word SP-memory payloads for `SWL`/`SWR`, especially big-endian `SWR` offset 2 (`0x22334400`), which differs from the already executed pinned-ares result (`0x22330000`)?

Pins:

- Plaid base: `ae41bdba82993ec8e77f47e5f9d3bb9af06f9256`
- Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- retained ares comparison: `9408cb43d4948fc3ea6e152a307a34348df3fe04`

The runner requires `.refs/gopher64` at the exact Gopher pin and a clean checkout:

```sh
python3 -m py_compile spikes/045-gopher-swr-sp-exec/run.py
python3 spikes/045-gopher-swr-sp-exec/run.py
```

It injects a `cfg(test)` module only for the duration of the run, decodes encoded `SWL`/`SWR` opcodes through Gopher's CPU table, routes them through the real SP memory map, and removes the injected files afterward. For each of 16 cases (8 opcode/offset combinations × DMEM/IMEM), it compares an unobserved baseline with a delegate observer that records the SP callback and then calls the original sink. Complete SP memory must match between the two runs. The entire matrix is then executed a second time and the extracted evidence records must be identical.

This experiment can establish exact-pinned Gopher64 behavior. It cannot establish N64 hardware truth; the pinned hardware-facing `n64-systemtest` corpus has no `SWL`/`SWR` SP-memory oracle for the discriminating case.
