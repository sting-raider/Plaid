# Next

1. Model cartridge-resident executable sources and a capable capture path. The
   pinned homebrew spike exposes unsupported B0001040 execution in new_dynarec;
   the interpreter also lacks LLD and fails upstream exception/LLAddr checks.
   Add stronger independent CPU/RSP verification before extending semantic claims.
2. Model/sense non-PI copies and executable writes beyond PI-backed snapshots.
   The constant aligned cached-RDRAM SW sensor is partial; general addresses,
   other sizes, TLB/uncached paths and CPU-copy provenance remain unmodeled.
   Extend restored target-entry sensing beyond successful dirty lookups; verified
   snapshots now explain pending same-epoch returns, and explicit source-unit
   tags identify older units still executing. Preserve boot-source/lifecycle
   obligations; keep
   speculative compilation distinct from execution.
3. Prove pointer-table data immutability and guard coverage before issuing exhaustive
   table certificates. Extend cross-block joins only with rechecked invariants;
   the current table recognizer and single-predecessor chains are restricted passes.
4. Track decompression, CPU copies, address aliases and overlay unload/reload,
   relocation and instruction-patch snapshots. PI copy sensing alone is insufficient.
5. Implement whole-ROM certificate verifiers for roots/boot, exceptions, execution
   modes, RSP identity and executable mutation. No flags may waive these obligations.
6. Design a provenance-bearing candidate adapter if promoting the partial
   spimdisasm spike; assess known-symbol signatures separately. Measure analysis
   size/cost before making scalability claims.
7. Begin tiny native integer lowering only after discovery beyond the current
   synthetic scope is demonstrably useful, with reference differential tests.

Native lowering remains deferred until discovery is demonstrably useful.

Keep user ROMs in ignored `roms/` and derived maps/traces in ignored `artifacts/`.
