# Primary integration: runtime identification by n64sym signatures

Base: a7717bc. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main.

ADR-0133:
- `plaid-core::signatures` parses n64sym `sig_v1` files and matches them at
  every word-aligned offset of a code image, with relocated immediates
  cleared (n64sym rule, MIT).
- Only N64Recomp's reimplemented functions (MIT list) are declared.
- Names matching several addresses, or addresses matching several names,
  stay guest code and are listed as ambiguous.
- `plaid identify` emits `plaid-runtime-functions-v0`, with `osCreateThread`
  `a2` as a callback, for `discover` and `lower-c`.
- Matches are identification evidence; the solver still lists the runtime
  ABI as an assumption.

Tests: unit tests for the CRC, relocation-insensitive matching, both
ambiguity cases, a changed unrelocated word, and malformed files.
`scripts/test_cli.py` runs identify → discover end to end on a synthetic ROM
and checks that a malformed signature file is rejected.

OoT US 1.2 local measurement with the pinned n64sym `builtin_signatures.sig`:
39 functions identified; `__ull_rem` is ambiguous. Discovery covers 320
blocks, and `solve --guarded-ram` reports 21 blockers. Seven are in boot
code:
- the boot return;
- the `0x80000f10` pointer call;
- `C.EQ.S`/`BC1T` at `0x800008cc..0x80000900`;
- `SWL` at `0x80003058`.

The other 14 follow calls at `0x80000624` and `0x80000d94` into stale
IPL3-window bytes, which the code-segment DMA overwrites before those calls
run.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, `tools/progress.py --check`. No
Actions. `native_complete` stays false everywhere.
