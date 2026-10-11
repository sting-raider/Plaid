# Direct integration receipt: cached exception-root resident generation binding

Date: 2026-10-11
Worker: `gpt56sol-direct-exception-root-residency-20261011`
Result: validated on the direct-integration branch; canonical main integration pending serialized lease

## Base and source research

- Initial base main: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`.
- Reconciled canonical bases during validation: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` and `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`.
- Source research: `research/exception-root-generation-gpt56sol` at `50c160680c936c1801fabe32907ca45304d3d313`.
- Durable research note: `research/exception-root-generation.md`.
- Executable fixture: `spikes/044-ares-exception-root-generation/` on the source research commit.
- Exact pinned ares revision: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Expected dynamic evidence SHA-256: `f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`.
- Expected adversarial model report SHA-256: `fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`.

The source branch is evidence, not authority. No production patch was mechanically merged or cherry-picked from it.

## Reproduced evidence

The important counterexample was reproduced repeatedly against the evolving current-main composition using a branch-only workflow that materialized the exact research reducer/fixture from `50c160680c936c1801fabe32907ca45304d3d313` and independently checked out exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The fixture demonstrates that a real BEV=0 general exception transfer to `0xffffffff80000180` can execute an older resident I-cache handler word after backing RDRAM has already changed. After invalidate/refill, the same numeric root executes the newer backing generation. Therefore the vector address, current backing bytes, and equal payloads are not executable-generation identity.

Fresh exact-reference runs preserved the original hashes:

- PR run `38153077205`, job `114510364767`: PASS; model report SHA-256 `fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`; dynamic evidence SHA-256 `f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`.
- Post-TLBWI explicit reconciliation run `38153225071`: PASS.
- Post-COP1-mutation reconciliation run `38153441451`: PASS.

The exact fixture reports the same vector for both executions, `handler=1` while the old resident remains, then `handler=2` after invalidate/refill. The adversarial reducer rejects four vector/current-backing forgeries. Repeated model execution is deterministic.

## Adopted production invariant

`plaid_core::exception_root_history` is deliberately narrower than the research model. It accepts only a source-bound finite history for the validated BEV=0, non-nested, general-vector, identity-RDRAM cached first-handler-word scope. It first rechecks the supplied `ExceptionRootReceipt` through `resolve_exception_root`.

The replay:

- authenticates the exact history bytes against an externally supplied SHA-256 receipt;
- requires contiguous event ordinals and rejects events after the root fetch;
- mints a fresh backing generation for every observed backing write, including same-value writes;
- mints a fresh resident generation for every completed fill;
- binds a resident fill to the same-physical-address backing generation current at that fill only when the payload agrees;
- treats invalidation as a resident-lifetime cut;
- binds the cached root fetch only to the resident generation current at fetch and that resident's fill-time backing generation;
- preserves current backing generation only as diagnostic state, never as the cached fetch source;
- returns `UNKNOWN` when the cached root lacks resident evidence or the resident fill lacks backing-generation ancestry;
- rejects root-PC/physical/payload/order/source-receipt contradictions rather than selecting a convenient generation.

A successful bounded replay leaves `ultimate_byte_origin_certified`, `mutation_coverage_certified`, `executable_lifetime_certified`, `root_set_complete`, and `native_complete` false.

## Adversarial production regressions

Module tests cover:

1. changed backing after fill: stale resident generation wins over newer current backing;
2. refill after backing write: binding moves to the new backing generation;
3. refill before backing write: the newer resident identity remains tied to the older backing generation;
4. same-value backing rewrite: a new backing generation is minted without stealing resident provenance;
5. current backing with no resident: result remains `UNKNOWN`;
6. resident fill with no backing ancestry: result remains `UNKNOWN`;
7. invalidation without refill: cached root remains `UNKNOWN`;
8. equal-value write at another physical address cannot steal lineage;
9. source-hash tampering and reordered ordinals are rejected;
10. wrong root PC or resident payload is rejected;
11. BEV=1 and TLB-refill scopes remain unsupported instead of being generalized from this fixture.
12. equal-value fill at physical `0x4180` evicts the prior `0x180` resident because both occupy the same direct-mapped I-cache slot; the later root fetch remains `UNKNOWN`.

## Review hardening

A withdrawn overlapping integration worker identified a pre-merge adversary in the first draft: residency was keyed by full physical address, which could preserve two impossible simultaneous residents in one direct-mapped cache slot. The production replay now keys resident state by the VR4300 16 KiB / 32-byte-line cache slot while retaining exact physical identity in the resident witness. Every fill replaces the slot, invalidation conservatively cuts the slot, and a fetch can reuse a resident only when that slot's exact physical identity matches. Equal-value alias fills do not rescue the evicted witness. This finding blocked main integration until the revised branch passed the full canonical gates.

## Canonical validation

The integration was repeatedly reconciled as main advanced instead of testing only its original base.

- On the TLBWI-generation composition, Rust checks run `38153077270` passed exact decoder pin, `cargo fmt --all -- --check`, strict `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, all canonical synthetic contracts, and the independent fetch-summary oracle.
- Explicit post-TLBWI branch reconciliation `5c7e027cc7e76c88d7c78d84a9bfcb7b654c995d` passed Rust checks run `38153225089` and exact-reference run `38153225071`.
- Explicit post-COP1-mutation branch reconciliation `1f19de7d681d24d5595f089393bc88211cb4ed23` passed Rust checks run `38153441380` and exact-reference run `38153441451`.
- An earlier canonical run failed only `cargo fmt --all -- --check`; canonical rustfmt was applied, after which all semantic and workspace gates passed. No gate was weakened.

A temporary branch-only reproduction/format workflow was used solely to obtain exact-pinned evidence and canonical rustfmt in the connector-only environment. It is deleted before production integration and is not a production dependency.

## Rejected / intentionally unpromoted scope

- No current-backing, cache-tag, vector-address, or payload-equality shortcut is accepted.
- No TLB refill/XTLB root executable identity is inferred from the general-vector fixture.
- BEV=1 behavior from the abstract reducer is not promoted as executable reference evidence by this integration.
- No TLB alias/mapping chronology, restore epoch, reset/NMI, cache-error, interrupt/watch root, full handler execution, mutation census, or whole-ROM root-set certificate is added.
- Successful finite replay is not sensor completeness or future-execution completeness.

## Production files

- `crates/plaid-core/src/exception_root_history.rs`
- `crates/plaid-core/src/lib.rs`
- canonical `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` when the serialized final canonical base is fixed
- this receipt

No `docs/progress.json` milestone changes.

## Remaining proof obligations

Even after integration, this is only a bounded source-bound composition primitive. Whole-ROM closure still requires authenticated exception classification/status chronology, complete mapping/cache histories, handler-byte provenance beyond this first-word identity-RDRAM scope, full executable lifetimes, complete mutation census, interrupt/watch/reset/NMI/cache-error roots, TLB/refill-root composition, restore/save chronology, and a complete execution-root census. Missing evidence remains OPEN.

Final main SHA, final production commit, final canonical CI, and ADR number are recorded by the issue #4 closeout after serialized landing.
