# Direct integration receipt: snapshot-qualified restore epochs

Date: 2026-10-11

Worker: `gpt56sol-direct-restore-epoch-20261011-a7`

Initial base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

Current reconciliation base before final validation: `9154b30b12026c8c122f654d7fe90f0f67968dce`

## Source research

- `research/savestate-tlb-cache-epoch-gpt56sol` note-final head `b502bc5f07dbdd88b8e8f521391dc13f90b98519`.
- executable exact-pin research head `26e8fb421375a76497f0fe36de51c47001736107`.
- `research/ares-savestate-tlb-cache-epoch.md`.
- exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- original exact-pin research Actions run `37932794526`, job `113827386285`: PASS.
- fresh direct-integration exact-pin rerun `38152267899`, job `114507972690`: PASS after explicitly reconciling its validation tree with then-current canonical main. Result payload SHA-256 `134004fc731a195152693394ca7a94583ddd879d2f3522e9f2d032b54c03b9f8`.

Research branches were treated as evidence, not mechanically merged.

## Reproduced evidence

The retained exact-reference fixture demonstrates a synchronized analysis-time load that restores installed TLB state, active EntryHi/ASID translation context and resident instruction-cache state without replaying the live TLB/context/cache operations that originally produced them.

The equal-value adversary is decisive: later live generations can contain values identical to the saved snapshot, yet loading the snapshot must not select those later generations as causal predecessors. One load is a new causal boundary even when every restored value compares equal.

Source guards also rechecked the pinned ares serialization surfaces. Prior fresh rerun hashes were:

- CPU serialization source SHA-256 `8cc65fad5508ef9d85e6715c31a6b5c577a46c8967b8e57d594d4f20d0dd369d`;
- system serialization source SHA-256 `284dde684315884a5ae5cfb7e5a9ce2e2d3e261a8cecaab508cd18a339425744`.

A final exact-pin rerun against the final reconciled integration head is required before main write and is appended below.

## Adopted invariant

For the bounded synchronized compiler-time restore scope validated by the exact pinned-reference experiment:

1. A snapshot save binds opaque digests for installed TLB state, active translation context and resident instruction-cache state to one explicit snapshot identity.
2. Every accepted snapshot load carries a fresh, monotonically ordered restore epoch.
3. The load must provide exactly one restored root for each of those three validated components, all bound to the same load ordinal, snapshot identity and restore epoch.
4. Every restored component digest must match the digest captured by that snapshot.
5. A composed restored execution context is valid only when all three roots come from the same snapshot/load/restore epoch.
6. Equal component contents never repair a mixed-snapshot or mixed-epoch history and never reconnect restored state to an abandoned live generation.
7. Restore roots, reports and composed contexts are non-deserializable with private fields; trusted typed values originate only from successful source-bound replay and expose read-only accessors.
8. Empty or save-only histories cannot issue a restore report.
9. The source SHA authenticates the supplied finite history only. It does not certify that every emulator save/load path or every executable-relevant serialized subsystem was observed.

## Review hardening and superseded candidate

The worker's first candidate represented live-generation and save/load events directly and exposed public deserializable result fields. Review against the independently developed duplicate integration lane reproduced a real API hazard: callers could fabricate a `RestoreRoot`/report-shaped value without source inspection and later mistake type shape for verified provenance. That candidate is superseded and must not land.

The adopted production shape keeps the same validated semantic boundary but hardens the trust surface: result fields are private, output types are `Serialize`-only, composition accepts only authenticated roots, a synchronized load must be followed by exactly the three validated component roots, and empty/save-only histories reject. This is a selective production adoption after review, not authority granted to the duplicate claim or a mechanical branch merge.

The earlier accidental unrelated TLB-context commit `40058601905fccb8fa9a77ba07cac9aa6544f7bb` remains rejected and is not part of this integration.

## Files changed

- `crates/plaid-core/src/restore_epoch.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` only when the final canonical state is reconciled
- this receipt

Temporary exact-reference validation workflow scaffolding is branch-only and must be deleted before canonical merge.

## Production adversaries

The hardened module covers at least:

- repeated equal-state loads mint distinct restore roots;
- same-value roots from different epochs do not compose;
- mixed snapshot identities do not compose;
- missing, duplicate and orphan component roots fail closed;
- restored component digest mismatch fails closed;
- unsaved snapshots fail closed;
- reused/reordered restore epochs fail closed;
- forged load-boundary metadata fails closed;
- source receipt mismatch fails closed;
- noncontiguous/deleted/reordered source ordinals fail closed;
- invalid snapshot identities fail closed;
- empty/save-only histories issue no restore report.

## Validation history

Earlier candidate validation against canonical main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`:

- PR merge-tree Actions run `38152271308`, job `114507982788`: PASS after a formatting-only first failure was corrected;
- permanent branch Actions run `38152702871`, job `114509249272`: PASS;
- required gates included `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, canonical synthetic contracts and independent oracle checks.

The independently reviewed hardened restore implementation also passed canonical Actions on its isolated integration branch before selective adoption. Final evidence must come from this worker's reconciled head, not from that branch, and is appended before closeout.

## Limitations

- This is compiler-time/reference-emulator exploration chronology, not an architectural N64 savestate mechanism.
- Only installed TLB state, translation context and resident instruction-cache state are modeled by this bounded contract.
- RSP state/microcode, queues/tokens, hidden/frontend memory, device state, provenance sidecars and other executable-relevant serialized state remain outside this scope until separately modeled.
- A trusted source SHA proves byte identity of the supplied history, not sensor completeness.
- Restore roots are not yet composed with complete physical-backing identity, TLB mapping-operation/context history, cache byte provenance or executable lifetime.
- Guest reset, NMI and power/reset chronology are separate architectural events and cannot be collapsed into emulator snapshot load.
- No existing solver blocker is waived. `native_complete` remains false.

## Remaining proof obligations

- compose canonical mapping-operation/context writer evidence with restore roots without allowing abandoned pre-load generations to survive by value equality;
- bind resident I-cache restore roots to byte-level executable provenance and later invalidation/replacement chronology;
- model every executable-relevant serialized subsystem required by a declared exploration scope;
- bind snapshot identity and load chronology across forked/distributed exploration;
- preserve reset/NMI chronology separately;
- complete mutation census, indirect-target closure and whole-ROM lifetime proof before any CLOSED/native-complete promotion.

UNKNOWN remains UNKNOWN across omitted components or missing source events. Equal bytes, equal register values, equal cache tuples, matching addresses or finite successful traces never reconnect provenance across a restore.

## Final reconciliation and validation

Pending final branch reconciliation onto canonical main `9154b30b12026c8c122f654d7fe90f0f67968dce` (or any newer serialized predecessor) and required full/exact-pin validation before MAIN-WRITE lease.
