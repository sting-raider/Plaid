# Trace/exporter v0 evidence

2026-10-08. Hypothesis: guest facts can cross a standalone C-to-Rust trace boundary
without host JIT addresses and without conflating lookup with resolved edges.

Inspected Mupen `new_dynarec.c` and `LICENSES` at the pinned revision. Confirmed
the W003 normal and restricted `jump_in` installs; found another install in
`pagespan_ds`. The low address bit encodes special delay-slot entry semantics and
must be preserved separately from the aligned PC. JR/JALR lookup helpers do not
reliably supply a source PC. Assembly hash-table hits can bypass those helpers.

Commands/results:

- `cargo test --workspace`: five format/invariant tests pass.
- `cargo clippy --workspace --all-targets -- -D warnings`: passes.
- `python scripts/prepare_mupen.py`: exact revision guard and patch application pass.
- `python scripts/test_exporter.py`: C99 `-Wall -Wextra -Werror`, ten events,
  deterministic repetitions, disabled/bad-identity sensor checks, Rust importer pass.
- `gcc -std=gnu99 -fsyntax-only -DNEW_DYNAREC=NEW_DYNAREC_X64 -DDYNAREC -DWIN32
  -I .refs/mupen64plus-core/src -I .refs/mupen64plus-core/subprojects/md5
  .refs/mupen64plus-core/src/device/r4300/new_dynarec/new_dynarec.c`: passes on MinGW.

Conclusion: wire/sink and pinned hook syntax are verified. A full instrumented
N64 execution and assembly source/target correlation remain unverified. M1 is
not yet claimed. No copied GPL implementation enters plaid-core.
