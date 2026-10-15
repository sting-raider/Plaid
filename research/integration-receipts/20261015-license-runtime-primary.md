# Primary integration: license and runtime decision

Base: 9d6da37. Milestone 4 (SM64 native boot), the decision step. The owner
delegated the runtime and license choice in chat: "Whatever you think is the
best approach".

ADR-0158:
- Plaid is licensed `MIT OR Apache-2.0`. `LICENSE-MIT`, `LICENSE-APACHE`,
  the crate manifests and the README say so.
- The reuse audit found GPL code only in `instruments/mupen/`, which is
  carved out (ADR-0006).
- Milestone 4 uses Plaid's own C runtime plus RT64 (MIT, pinned 4337374).
  N64ModernRuntime (GPL-3.0) stays a reference only.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- spike096: PASS
- `tools/progress.py --record` and `--check`

No code paths changed. Actions were not used.
