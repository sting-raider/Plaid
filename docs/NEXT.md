# Next

1. Run a synthetic N64 program in an instrumented reference session. Add
   source-correlated JR/JALR events and cover inline assembly lookup hits/misses.
   Keep speculative compilation distinct from actual execution.
2. Extend indirect certificates with sound cross-block propagation and bounded
   jump/pointer tables; independently recheck their assumptions and target sets.
3. Track decompression, CPU copies, address aliases and overlay unload/reload,
   relocation and instruction-patch snapshots. PI copy sensing alone is insufficient.
4. Implement whole-ROM certificate verifiers for roots/boot, exceptions, execution
   modes, RSP identity and executable mutation. No flags may waive these obligations.
5. Assess pinned spimdisasm/signature evidence on synthetic inputs, and measure
   analysis size/cost before making scalability claims.
6. Begin tiny native integer lowering only after discovery beyond the current
   synthetic scope is demonstrably useful, with reference differential tests.

Native lowering remains deferred until discovery is demonstrably useful.

Keep user ROMs in ignored `roms/` and derived maps/traces in ignored `artifacts/`.
