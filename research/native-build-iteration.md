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
