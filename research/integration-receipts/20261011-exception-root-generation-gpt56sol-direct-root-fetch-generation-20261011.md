# Direct integration receipt: cached exception-root executable generation

Date: 2026-10-11
Worker: `gpt56sol-direct-root-fetch-generation-20261011`
Cluster: source-bound cached exception-root executable-generation binding
Initial base main: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`
Latest reproduced main parent before this receipt: `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`
Integration branch: `direct-integration/exception-root-generation-gpt56sol-direct-root-fetch-generation-20261011`

## Source research

- `research/exception-root-generation-gpt56sol` at `50c160680c936c1801fabe32907ca45304d3d313`
- `research/exception-root-generation.md`
- `experiments/exception_root_generation.py`
- `spikes/044-ares-exception-root-generation`
- exact pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- original exact-pin Actions run `37934230000`, plus a fresh integration-time rerun of the same exact job as attempt 2 on 2026-10-11

The research branch is evidence only. No research implementation was mechanically merged.

## Reproduced evidence

Fresh exact-pin attempt 2 of Actions run `37934230000` completed successfully against ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The adversarial reducer reproduced:

- report SHA-256 `fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`;
- four rejected current-backing/vector forgeries: changed backing while stale, refill-before-write, same-value backing replacement, and missing resident evidence;
- cached root `0xffffffff80000180` retaining backing generation 1 while later storage generation 2 exists;
- a refill after invalidation selecting backing generation 2;
- an uncached BEV control remaining a separate backing-visible case rather than being generalized into the cached proof.

The exact pinned ares executable fixture reproduced:

- evidence SHA-256 `f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`;
- one warm cached handler execution with value 1;
- replacement backing word `0x24020002` while the resident instruction remains `0x24020001`;
- the same root PC `0xffffffff80000180` executing stale handler value 1 before invalidation;
- invalidate/refill selecting resident word `0x24020002` and handler value 2;
- one I-cache hit and two misses in the bounded fixture.

This reproduces the important causal result: architectural transfer to a vector address does not identify the executable generation fetched there. Current backing contents are not a substitute for resident I-cache provenance.

## Adopted invariant

Production now has a bounded source-hash-bound replay for cached direct-segment exception-root fetch evidence in `plaid_core::root_fetch`.

The verifier keeps four identities distinct:

1. architectural exception-root selection, supplied through an independently rederived `ExceptionRootReceipt`;
2. physical backing generations, minted from ordered authenticated backing-generation events even when the payload is unchanged;
3. resident I-cache generations, minted only by an exact fill tied to one live backing event;
4. the actual root fetch, which must name the exact live resident fill that supplies the fetched word.

Resident state is keyed by the direct-mapped I-cache slot, not by physical address. Therefore an index-conflicting fill for a different physical line replaces the prior resident witness. An explicit `residency_cut` destroys the reusable witness without guessing what became resident.

The report intentionally leaves all closure-style fields false. Source hashing authenticates the supplied finite history; it does not prove the observer complete.

## Rejected and superseded patches

The first integration draft keyed resident state by physical word. Review found that this could falsely retain the root witness after a different physical line filled the same direct-mapped I-cache slot. That draft was rejected before integration. The production replay instead keys residency by cache slot and includes an index-conflicting-fill regression.

Two earlier CI heads failed only the canonical formatter and did not reach the complete gate. Their formatting diffs were applied; neither failed head is an integration candidate.

No research workflow, patched reference implementation, branch-only reducer, or spike code is adopted into production.

## Files changed by this cluster

- `crates/plaid-core/src/root_fetch.rs`
- `crates/plaid-core/src/lib.rs` (module export only, preserving later canonical modules)
- this receipt

Canonical STATUS/NEXT/DECISIONS are updated only if the final serialized main integration still changes their live documented state. `progress.json` is not changed because no milestone or whole-ROM/native-complete obligation is closed.

## Production adversarial regressions

`root_fetch` tests cover:

- changed backing while an older resident generation remains executable;
- invalidate then refill selecting the new backing generation;
- refill-before-later-write remaining tied to the older backing generation;
- same-value backing replacement minting a distinct storage generation without relabeling resident code;
- equal-value foreign backing being rejected as a fill source;
- same-slot/different-physical index-conflicting fills evicting the prior resident identity;
- missing resident evidence and explicit unknown residency cuts failing closed;
- equal-value but wrong resident-generation identifiers being rejected;
- invalidation naming the wrong resident generation being rejected;
- malformed virtual-slot/physical-index joins being rejected;
- reordered event ordinals being rejected;
- source-hash tampering being rejected;
- forged exception-root receipts being rederived and rejected;
- unsupported uncached BEV roots being rejected rather than generalized;
- architectural transfer without an authenticated handler fetch failing closed.

## Validation results

Pre-reconciliation canonical PR run `38153128980` on `ffb41a07f0b792ec9ba22729b56c7527aa1d0bca`: PASS after formatting corrections.

Reconciled canonical PR run `38153301321` on `91711eb4b3848b047340c86f697a5affdd41cd5f` against TLBWI-integrated main `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`: PASS, including:

- exact decoder pin check;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- all retained synthetic provenance/cache/TLB/RSP contracts;
- independent fetch-summary assignment oracle.

Main then advanced to `dd3f627d2c27f84611439ec1888ec4e3015e6bd2` with bounded COP1 mutation normalization. The integration branch was reconciled again at `f0596adf8926bf090d3b5be6cf673424a905cdb4`, preserving the new `cpu_mutation` and `tlb_history` exports. The final documented head must pass the same canonical workflow before a main-write lease is acquired.

Fresh exact pinned-reference validation: Actions run `37934230000`, attempt 2, job `114511277928`: PASS with the model/evidence hashes recorded above.

## Limitations and remaining proof obligations

This primitive does **not** prove:

- that the supplied history is complete;
- the producer/writer ancestry of each backing-generation event;
- complete executable mutation coverage;
- arbitrary CACHE operation semantics or every residency transition;
- mapped/TLB exception-root fetch identity;
- uncached BEV/root identity beyond refusing this cached verifier's scope;
- handler reachability beyond the authenticated transfer/fetch pair;
- handler control-flow closure;
- mapping-context or alias lifetime;
- cache lifetime outside the supplied bounded chronology;
- exception classification, BEV/EXL/address-mode chronology completeness;
- interrupt, watch, reset, NMI, or cache-error root completeness;
- save/restore/reset chronology;
- complete root census;
- whole-ROM executable-universe closure;
- native completeness.

UNKNOWN remains UNKNOWN when resident/fill/backing evidence is missing, cut, mismatched, reordered, or outside the bounded cached-direct scope.

## Codex handoff

Treat `plaid_core::root_fetch::inspect_cached_exception_root_history` as a fail-closed compiler-time evidence primitive for a supplied, externally complete cached-root history. Do not infer a resident generation from vector address, current RAM bytes, matching values, cache tags, or a finite execution trace. A valid witness means only that the supplied ordered history causally binds that root fetch to that resident fill and its backing generation. All census, completeness, mapping/cache lifetime, writer ancestry, reachability, and native-complete obligations remain separate and OPEN.
