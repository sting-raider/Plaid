# Direct integration receipt: snapshot-qualified restore epochs

Date: 2026-10-11

Worker: `gpt56sol-direct-restore-epoch-20261011-a7`

Initial base main: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

Final validated reconciliation base at this stage: `31c10020665e8386656fd943acab111b5c7e1671`

## Source research

- `research/savestate-tlb-cache-epoch-gpt56sol` note-final head `b502bc5f07dbdd88b8e8f521391dc13f90b98519`.
- executable exact-pin research head `26e8fb421375a76497f0fe36de51c47001736107`.
- `research/ares-savestate-tlb-cache-epoch.md`.
- exact ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- original exact-pin research Actions run `37932794526`, job `113827386285`: PASS.
- fresh direct-integration exact-pin rerun `38152267899`, job `114507972690`: PASS.

Research branches were treated as evidence, not mechanically merged.

## Reproduced evidence

The retained exact-reference fixture demonstrates a synchronized analysis-time load that restores installed TLB state, active EntryHi/ASID translation context and resident instruction-cache state without replaying the live TLB/context/cache operations that originally produced them.

The equal-value adversary is decisive: later live generations can contain values identical to the saved snapshot, yet loading the snapshot must not select those later generations as causal predecessors. One load is a new causal boundary even when every restored value compares equal.

The final pre-lease exact-pin rerun was Actions `38154090044`, job `114513349124`. Its validation checkout resolved canonical main to `31c10020665e8386656fd943acab111b5c7e1671`, confirmed the branch was already reconciled to that main, fetched exact ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`, and passed the adversarial model, source guard and real fixture. It reproduced:

- CPU serialization source SHA-256 `8cc65fad5508ef9d85e6715c31a6b5c577a46c8967b8e57d594d4f20d0dd369d`;
- system serialization source SHA-256 `284dde684315884a5ae5cfb7e5a9ce2e2d3e261a8cecaab508cd18a339425744`;
- result payload SHA-256 `134004fc731a195152693394ca7a94583ddd879d2f3522e9f2d032b54c03b9f8`;
- six forged histories rejected by the retained adversarial model.

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

Permanent production diff:

- `crates/plaid-core/src/restore_epoch.rs`
- `crates/plaid-core/src/lib.rs`
- this receipt

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md`, and `progress.json` are intentionally unchanged. This bounded primitive neither clears an existing closure obligation nor changes the project milestone/state; the receipt records the new evidence model without pretending a larger proof has become CLOSED.

Temporary exact-reference workflow scaffolding was used only to rerun the pinned fixture and is deleted before canonical merge.

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
- permanent branch Actions run `38152702871`, job `114509249272`: PASS.

The branch was later rebuilt as a real descendant of current canonical main `31c10020665e8386656fd943acab111b5c7e1671`, preserving landed COP1, BEV1 PIF-root, TLBWI and RSP IMEM-egress production state while overlaying only the restore module, module export and receipt.

Final pre-lease canonical Rust validation with the temporary exact-pin workflow present:

- Actions run `38154092604`, job `114513356846`: PASS.
- `cargo fmt --all -- --check`: PASS.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS.
- `cargo test --locked --workspace`: PASS.
- exact decoder dependency pin: PASS.
- synthetic CLI checks and all retained CPU-copy, XORI, CPU-SP, RSP/IMEM, cache-visibility, PageMask-remap, PI, SP-DMA, RSP-store, EntryHi/TLBR and independent fetch-summary oracle contracts: PASS.

Fresh exact-reference evidence on the same reconciled production content:

- Actions run `38154090044`, job `114513349124`: PASS.
- exact pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- result SHA-256 `134004fc731a195152693394ca7a94583ddd879d2f3522e9f2d032b54c03b9f8`.

A final permanent-head Rust run after removing the temporary workflow and updating this receipt is still required before a MAIN-WRITE lease. If canonical main advances first, the branch must be reconciled again and the required gates rerun.

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
