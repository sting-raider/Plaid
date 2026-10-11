# Development guide

This document keeps build, verification, CLI, and reference-lab details out of the README.

The authoritative engineering state is still [`STATUS.md`](STATUS.md) and [`NEXT.md`](NEXT.md).

## Toolchain

Core development requires:

- Rust toolchain from `rust-toolchain.toml`
- a C compiler for the pinned Rabbitizer dependency
- Python 3.11+
- additional Linux/WSL build tools for reference experiments

Some pinned Mupen/ares experiments require GCC/G++, make, NASM, SDL2/zlib/libpng development packages, or other dependencies described by the relevant `spikes/` README.

External reference repositories are pinned in [`../refs.lock.toml`](../refs.lock.toml) and are kept outside the repository.

Fetch the reference lab with:

```bash
python scripts/fetch_refs.py
```

Local ROMs belong in ignored `roms/`. Derived traces, maps, reports, and corpora belong in ignored `artifacts/`.

## Fresh-worker environment bootstrap

A new direct-integration worker is expected to bootstrap its environment when it starts empty.

Missing `cargo`, a missing Plaid checkout, or absent pinned references at startup are setup tasks, not reasons to skip the lane.

Typical bootstrap flow:

```text
1. clone or obtain a writable Plaid checkout
2. fetch latest main
3. inspect rust-toolchain.toml
4. install the required Rust toolchain if necessary
5. ensure Python and required native build packages are available
6. fetch refs with scripts/fetch_refs.py or fetch only the exact pinned ref needed
7. verify the local commands work
8. continue with integration work
```

Workers may use the environment's normal package manager, Rust bootstrap tooling, and network access to install open-source build dependencies. Do not use GitHub Actions merely because the fresh runtime starts without the toolchain.

Only treat environment setup as genuinely unavailable after reasonable setup attempts show a hard runtime restriction, such as no usable shell/install path or no way to obtain a required dependency. If useful candidate work already exists by then, preserve it as a validation handoff.

Historical direct-integration results marked `BLOCKED` only because a fresh session lacked `cargo`, a checkout, or a pinned reference should be treated as recoverable prepared candidates after bootstrap.

## Canonical local validation

GitHub Actions is manual-only. Integrations should be validated locally.

Run at minimum:

```bash
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
```

When a change touches a retained synthetic contract, run the relevant `spikes/*/test_verify.py` checks as well.

When reference semantics matter, reproduce against the exact revision in `refs.lock.toml` rather than an arbitrary upstream checkout.

Historical CI is supporting evidence only. It is not a substitute for validation of the exact candidate tree being proposed for `main`.

## Main CLI

Useful discovery commands include:

```text
plaid rom-info <rom>
plaid check-trace <trace.ndjson>
plaid check-map <map.json>
plaid discover <rom> <rom_offset> <guest_start> <size> <entry> <out.json>
plaid import-trace <rom> <trace.ndjson> <out.json>
plaid import-fetch <rom> <fetch.ndjson> <out.json>
plaid verify-fetch <rom> <fetch.ndjson> <map.json>
plaid import-boot-fetch <rom> <firmware> <fetch.ndjson> <out.json>
plaid verify-boot-fetch <rom> <firmware> <fetch.ndjson> <map.json>
plaid merge <left.json> <right.json> <out.json>
plaid solve [rom] <map.json>
```

Numbers accept decimal or `0x` notation.

`discover` requires an explicit load mapping. Trace import compares captured DMA-backed code against canonical ROM bytes. Supplying a ROM to `solve` enables source-witness rechecking. The CLI whole-ROM solve path remains fail-closed; producing a report is not the same as reaching `CLOSED`.

Use `plaid --help` and the relevant subcommand `--help` for the exact current argument list.

## Source-bound history consumers

Plaid also contains strict consumers for bounded research histories. These are deliberately separate from claims of whole-ROM completeness.

Current families include:

```text
inspect-boot-history / verify-boot-history
inspect-pi-boot-history / verify-pi-boot-history
inspect-pi-queue-boot-history / verify-pi-queue-boot-history
inspect-pi-fetch-lineage / verify-pi-fetch-lineage
inspect-sp-boot-history / verify-sp-boot-history
inspect-pif-boot-history / verify-pif-boot-history
inspect-cpu-copy-history / verify-cpu-copy-history
inspect-cpu-definitions / verify-cpu-definitions
```

Each verifier reconstructs or rechecks facts from complete supplied sources rather than trusting an editable report. The exact supported protocol/version and remaining obligations are documented in the corresponding module, tests, ADR, research note, or integration receipt.

A bounded source-bound receipt does **not** by itself establish:

- sensor completeness;
- whole-program mutation completeness;
- executable lifetime;
- universal mapping/TLB history;
- whole-ROM closure;
- native completeness.

## Reference experiments

### Mupen

The Mupen instrumentation is maintained as a separate research boundary because of licensing and architectural separation.

Useful scripts include:

```bash
python scripts/test_mupen_hooks.py
python scripts/test_mupen_execution.py
python scripts/test_mupen_session.py
```

These exercises cover different scopes. For example, the hook harness can compile and test instrumented routines without executing generated host code, while the execution harness compares synthetic integer/control behavior between the pinned dynarec and interpreter.

Do not generalize a bounded fixture into a whole-ROM or hardware claim.

### ares

`spikes/003-ares-oracle/run.py` builds the pinned ares reference separately and runs original synthetic cartridge, memory, exception, and cross-reference cases.

Many later `spikes/` directories contain more narrowly scoped cache, TLB, PI/SP/PIF, RSP, exception/root, and mutation experiments. Their README and verifier define the exact claim.

Reference disagreement is evidence, not something to silently average away.

## Raw fetch and boot-source formats

The repository has several versioned fetch/history formats created during provenance research. Later formats retain progressively more physical/cache/source context while preserving explicit unknown states.

Important rules across these formats:

- current backing bytes do not identify cached resident bytes;
- equal payloads do not identify producer generations;
- physical addresses do not establish ultimate origin;
- observations do not prove an exhaustive event census;
- missing/ambiguous source information remains unknown;
- source/report verification must bind the complete supplied inputs.

See [`STATUS.md`](STATUS.md), [`NEXT.md`](NEXT.md), [`DECISIONS.md`](DECISIONS.md), and the relevant `research/` receipts for exact protocol details.

## Progress-map generation

[`progress.json`](progress.json) is the milestone source of truth.

Regenerate:

```bash
python tools/progress.py
```

Check without rewriting:

```bash
python tools/progress.py --check
```

Do not mark a milestone verified merely because a research branch exists. The progress map describes canonical `main`.

## Swarm development and canonical writes

Automated workers should read:

- [`../AGENTS.md`](../AGENTS.md)
- [`../ORCHESTRATION.md`](../ORCHESTRATION.md)
- [`STATUS.md`](STATUS.md)
- [`NEXT.md`](NEXT.md)
- [`DECISIONS.md`](DECISIONS.md)

Research/integration workers coordinate semantic ownership through issue #4.

In user-authorized direct-integration mode there is **no main-write lease**. Workers may prepare and validate in parallel, but a canonical write must use exact-head compare-and-swap:

1. fetch `main` and record exact SHA `A`;
2. reconcile the candidate onto `A`;
3. run all required local validation on that exact tree;
4. refetch `main` immediately before the write;
5. if it moved, reconcile and rerun validation;
6. if it is still `A`, update `main` atomically with `expected_sha=A`;
7. if the CAS loses a race, fetch the winner, reconcile, retest, and retry.

Never force-push `main`. Never land a candidate validated only against an older parent. A claim in issue #4 prevents duplicated semantic work; it does not reserve the canonical branch.

### Validation handoffs

Workers should bootstrap required tooling themselves. A handoff is for a genuine late task-specific setup failure after useful work exists, not for an initially empty fresh runtime.

When a handoff is necessary, record what setup was attempted, the exact candidate branch/head, the remaining commands, and the environment failure. Another worker should bootstrap the required environment, reconcile the semantic change to current `main`, rerun the full gate, and perform the CAS.

Do not relax the local gate to avoid a handoff.

## Scope discipline

Plaid's strongest rule is also the boring one: do not convert uncertainty into confidence by changing vocabulary.

A fact can be useful while still being partial. A reference can be informative while still disagreeing with hardware or another reference. A source-bound receipt can be valid while still not proving a complete executable lifetime.

When in doubt, leave the obligation open and document why.
