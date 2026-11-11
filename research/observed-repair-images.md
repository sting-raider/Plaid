# Observed repair images, step 2a

Implementation claim: authenticated runtime bytes can be lowered independently
of ROM bytes at the same guest address, with explicit generations, exact content
selection and no interpreter/JIT fallback. Automatic repair iteration is excluded.

Prepared base: 5cb53eef0e857c84ef31c91b6613d3b5a7bae6d1.
Branch: implementation/observed-repair-images.

Synthetic contract: `python runtime/test_observed_images.py`, also registered in
both CLI and runtime suites. It converts a synthetic fault-15 capture through the
actual capture writer, admits it through loads/discover/solve/lower-map, compiles
and executes generated C. It checks all GPRs, PC, RAM output, unchanged source
bytes, HI/LO and CP0 knowledge. Negative cases check zero observed-code side effects.
No ROM, firmware, commercial trace, copied upstream implementation or frontend
change is included. Existing pinned ares test oracles remain reference-only.

Validation contract (all local, required before the canonical CAS):

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`

The landing commit message records the final exact-tree exit codes and timings;
full local logs are retained under ignored `target/observed-gate/`. The first cold
Rust workspace test pass took 162.758 s; that supporting pass predates the final
bound-image check simplification and does not substitute for the final gate.
The focused synthetic contract took 5.982 s in one measured run (before the last
direct-branch case). A deliberate mutation bypassing the generated whole-window
comparison was caught by the negative execution assertion in 9.287 s. The mutation
only changed temporary generated C and was discarded; no source guard was disabled.
The constant observed verifier uses `memcmp` over authenticated bytes, avoiding
ordinary overlay relocation reconstruction/allocation. A still-valid binding
reuses its protection map after rechecking bytes; block entry checks its bound
image directly instead of searching every candidate entry again.

Limits: the broad capture window is fully compared and pinned while active;
mutable data inside it may conservatively refuse execution. No instruction-cache
history, writer census, DMA provenance or completeness certificate is inferred.
An alternate KSEG alias requires its own captured root; equal physical backing
alone does not authorize a different J/JAL virtual PC region. No commercial-game
validation is claimed. Step 2b remains out of scope.
