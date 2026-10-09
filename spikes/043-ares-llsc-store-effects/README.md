# ares LL/SC storage-effect experiment

Question: can conditional-store executable mutation provenance be decided at actual completed storage sinks instead of trusting SC/SCD opcodes, success-register values, or one emulator's reservation semantics?

The exact-pin fixture executes decoded LL/LLD + SC/SCD sequences in the pinned ares interpreter with recompilers disabled. It covers reservation failure, aligned success, misaligned write failure, cached/uncached destinations, 4/8-byte widths, changed values, and same-value stores. The research observer records only completed identity-RDRAM scalar effects and D-cache burst read/write effects. Cached success is sampled before a guest `CACHE 0x19` writeback and again afterward.

Run:

```sh
python3 spikes/043-ares-llsc-store-effects/run.py
```

Generated reference shadows, binaries and result files stay under ignored `target/` / `.refs/`.
