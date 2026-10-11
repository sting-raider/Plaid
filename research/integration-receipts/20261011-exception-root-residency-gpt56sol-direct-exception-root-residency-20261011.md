# Direct integration receipt: cached exception-root resident generation binding

Date: 2026-10-11
Worker: `gpt56sol-direct-exception-root-residency-20261011`
Result at receipt creation: validation in progress; main integration not yet authorized

## Base and source research

- Base main: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Source research: `research/exception-root-generation-gpt56sol` at `50c160680c936c1801fabe32907ca45304d3d313`.
- Durable research note: `research/exception-root-generation.md`.
- Executable fixture: `spikes/044-ares-exception-root-generation/` on the source research commit.
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Historical validated dynamic evidence SHA-256: `f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`.
- Historical adversarial model report SHA-256: `fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`.

The source branch is evidence, not authority. No production code was cherry-picked from it.

## Reproduced evidence against current integration base

A temporary PR-only workflow materializes the exact research reducer/fixture from the source commit, checks out the exact pinned ares revision independently, reruns the adversarial reducer twice, and executes the stale-handler fixture. The temporary workflow will be removed before integration. Final run IDs and hashes are recorded below after completion.

The important result being rechecked is that a real BEV=0 general exception transfer to `0xffffffff80000180` can execute an older resident I-cache handler generation after backing RDRAM has already changed. After invalidation/refill, the same numeric vector executes the newer backing generation. Equal payloads across backing writes still represent different provenance generations.

## Adopted production invariant

The production consumer is deliberately narrower than the research model. `plaid-core::exception_root_history` accepts only a source-bound finite history for the validated BEV=0, non-nested, general-vector, identity-RDRAM cached root scope. It first rechecks the supplied `ExceptionRootReceipt` with `resolve_exception_root`.

The replay then:

- requires an externally supplied SHA-256 receipt for the exact history bytes;
- requires contiguous event ordinals;
- mints a fresh backing generation for every observed backing write, including same-value writes;
- mints a fresh resident generation for every observed fill;
- binds a resident fill to the backing generation current at that fill only when payload and physical backing agree;
- preserves invalidation as a resident-lifetime cut;
- binds the root fetch only to the resident generation current at the fetch and that resident's fill-time backing generation;
- retains current backing generation only as diagnostic state, never as the cached fetch source;
- reports `UNKNOWN` when the cached root lacks a resident generation or the resident fill lacks backing-generation ancestry;
- rejects root-PC/physical/payload/order/source-receipt contradictions rather than guessing.

Successful replay explicitly leaves ultimate byte origin, mutation coverage, executable lifetime, root-set completeness and native completeness false.

## Adversarial production regressions

Unit regressions cover:

1. changed backing after fill: stale resident generation wins over newer current backing;
2. refill after backing write: binding moves to the new backing generation;
3. refill before backing write: newer resident identity remains tied to the older backing generation;
4. same-value backing rewrite: a new backing generation is minted without stealing resident provenance;
5. current backing with no resident: result remains `UNKNOWN`;
6. resident fill with no backing ancestry: result remains `UNKNOWN`;
7. invalidation without refill: cached root remains `UNKNOWN`;
8. equal-value write at another physical address cannot steal lineage;
9. source-hash tampering and ordinal reordering are rejected;
10. wrong root PC or resident payload is rejected;
11. BEV=1 and TLB-refill scopes remain unsupported rather than generalized from this fixture.

## Rejected / intentionally unpromoted scope

- No current-backing or payload-equality shortcut is accepted.
- No TLB refill/XTLB root executable identity is inferred from the general-vector fixture.
- BEV=1 uncached behavior from the abstract reducer is not promoted as executable reference evidence.
- No TLB alias/mapping chronology, restore epoch, reset/NMI, cache-error, interrupt/watch, full handler execution, mutation census or whole-ROM root-set certificate is added.
- The temporary research reproduction workflow is not a production dependency and must be deleted before integration.

## Production files

- `crates/plaid-core/src/exception_root_history.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` only if the canonical state change is accepted
- this receipt

No `docs/progress.json` milestone is changed.

## Validation

Pending final canonical PR and exact-reference results. Before a main-write lease, the final branch must pass:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- canonical synthetic CLI/history/oracle checks;
- focused exception-root history regressions;
- exact pinned-ares stale-handler reproduction.

## Remaining proof obligations

Even after successful integration, the result is only a bounded source-bound composition primitive. Whole-ROM closure still requires authenticated exception classification and status chronology, complete mapping/cache histories, handler-byte provenance beyond this first-word identity-RDRAM scope, executable lifetimes, complete mutation census, interrupt/watch/reset/NMI/cache-error roots, TLB/refill-root composition, restore/save chronology and a complete execution-root census. Missing evidence remains OPEN.
