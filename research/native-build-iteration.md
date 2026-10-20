# Native pipeline build iteration

At base `94a4d7cb1dc602c22a2f49babe95e7a1e7d02040`, a controlled
release rebuild after touching the core source took 135.276 seconds with the
default release profile and 8.471 seconds with
`CARGO_PROFILE_RELEASE_INCREMENTAL=true` (15.97 times faster). Initial cache
setup took 158 and 164 seconds respectively. Toolchain: Rust/Cargo 1.98.0.

An authored 4096-byte synthetic ROM produced byte-identical discovery maps
and solve JSON. Map SHA256:
`ff86a137f4becb13faeeb7c0a3b8288101c6aeee0d6a6b9fa7a8a792db2d57eb`;
solve SHA256:
`4461c6520f75253074fc0db49cfbb379d6537e8ae0a6dcd811685c63057d2fd3`.
The ignored measurement receipt is in the experiment worktree at
`target/build-iteration-bench/receipt.json`.

`scripts/native.py` defaults only its Cargo subprocess to release incremental
compilation, preserving an explicit environment override. This changes the
compiler build cache; generated native C compiler flags remain unchanged.
For manual local iteration use:

```powershell
$env:CARGO_PROFILE_RELEASE_INCREMENTAL='true'
cargo build --locked --release -p plaid
```

## Test build layout and dev profile (2026-10-21)

Base `1ea8aff4`, Rust 1.98.0 MSVC, 20 threads, one shared target directory.
`cargo test --locked --workspace`; "rebuild" touches `crates/plaid-core/src/lib.rs`
then reruns `--no-run`. All variants pass the same 886 tests.

| Variant | Rebuild | Test run |
| --- | ---: | ---: |
| 84 plaid-core test binaries (before) | 40.7 s | 173.7 s |
| one `tests/core` binary | 11.0 s | 172.6 s |
| + `debug = "line-tables-only"`, dependencies without debug info | 8.4 s | 152.2 s |
| + `opt-level = 1` (kept) | 8.1 s | 18.1 s |

The test run was bound by one unoptimized binary (167 s). `opt-level = 1`
keeps overflow checks and debug assertions. A build after a profile change
costs 276 s instead of about 126 s; a warm target directory avoids it.
Receipts: ignored `target/paper-mario/0222/bench`.
