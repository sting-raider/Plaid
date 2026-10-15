# Primary integration: unaligned loads and stores

Base: ea407a7. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main.

ADR-0134:
- `plaid-lower` lowers `LWL LWR LDL LDR SWL SWR SDL SDR` and `LWU` through
  checked helpers.
- The merge arithmetic starts from N64Recomp's `recomp.h` helpers (MIT);
  ares semantics win where the two differ.
- `LWR` sign-extends only at misalignment 3; otherwise it keeps the upper
  word.
- Stores write only the bytes they cover.
- The guarded scope admits these opcodes and states the access rule in its
  memory assumption.

Spike096 on pinned ISC ares 9408cb43: `unaligned` covers every misalignment,
lone `LWR` on a non-sign-extended register, and partial stores into
prefilled memory. It matches, as do the eleven earlier programs, and the
five negatives still fail closed. Mutation check: an always-sign-extending
`LWR` (N64Recomp's rule) makes `unaligned` mismatch ares.

ISA coverage: 85 -> 94 of 209 measured forms. OoT US 1.2 local measurement
(identified declarations): the `SWL` at `0x80003058` closes, leaving 20
guarded blockers. Six are in boot code: the boot return, `0x80000f10`, and
four FPU compare/branch sites.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--check`. No Actions. `native_complete` stays false.
