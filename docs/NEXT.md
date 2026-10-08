# Next

1. Model/sense non-PI copies and executable writes beyond PI-backed snapshots.
   CPU-copy and mutation reference fixtures now retain their unknown-source/write
   blockers. Preserve boot-source and lifecycle obligations; keep speculative
   compilation distinct from execution.
2. Prove pointer-table data immutability and guard coverage before issuing exhaustive
   table certificates. Extend cross-block joins only with rechecked invariants;
   the current table recognizer and single-predecessor chains are restricted passes.
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
