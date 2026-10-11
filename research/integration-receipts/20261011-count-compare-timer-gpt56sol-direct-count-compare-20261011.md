# Direct integration receipt: Count/Compare timer producer history

Worker: `gpt56sol-direct-count-compare-20261011`

Date: 2026-10-11

Cluster: source-bound VR4300 Count/Compare timer producer generations and IP7 acknowledgement provenance.

## Source research

- Research branch: `research/count-compare-interrupt-producer-gpt56sol`
- Reviewed research head: `74fcfa7cf20314048e612b9685249fb738cfa7af`
- Durable research note: `research/count-compare-interrupt-producer.md`
- Exact-pin workflow lineage: Actions run `37999959747`, job `114055349538`
- Reference pins from `refs.lock.toml`:
  - ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
  - Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`
  - Mupen64Plus Core `ba95bab92a76744753bfe61470823a4937850ab0`
  - n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The research branch was treated as evidence, not as merge authority. No research branch was mechanically merged.

## Reproduced evidence

Before adopting production code, the exact-pin research job `114055349538` was rerun. Its exact-reference checkout, source-contract guards, Python syntax checks, adversarial causal model, exact ares build/execution matrix, evidence hashing and artifact upload all completed successfully.

The research evidence establishes the bounded portable facts used here:

1. A successful Compare write clears the observed timer-pending request.
2. A same-value Compare rewrite is still a causal acknowledgement operation and must receive a fresh operation/register generation even though the visible value is unchanged.
3. A Count write does not acknowledge an already-latched timer request in the validated scope.
4. A value-only `(Count, Compare)` snapshot is insufficient to identify timer causal state.
5. Exact Count-rewrite/equality scheduling is not portable evidence: the pinned references disagree, and the pinned n64-systemtest revision has no dedicated hardware-arbitrating fixture for that timing question.

Current canonical `main` was inspected during integration. It already carried exception-root and later NMI-root production evidence, but no production Count/Compare timer producer history replay. The timer cluster therefore remained genuinely unconsumed and did not duplicate the active interrupt-gate or software-IP0/IP1 integration lanes.

## Adopted invariant and production abstraction

Production adds `crates/plaid-core/src/timer_interrupt.rs` and exports it from `crates/plaid-core/src/lib.rs`.

The module replays a strict, source-hash-bound finite timer history. It preserves distinct causal identities for:

- successful Count writes;
- successful Compare writes;
- per-register write generations;
- a global Count/Compare operation generation;
- observed false-to-true timer assertion generations;
- Compare acknowledgement of a previously pending request.

Replay is fail closed on source-digest mismatch, unknown fields, noncontiguous ordinals, stale before-values, contradictory pending-state transitions, Count writes forged as acknowledgements, repeated assertions while already pending, changed/deleted source under an old digest, and report tampering.

A `timer_assert` record is an authenticated observed transition. The implementation deliberately does **not** derive assertion occurrence from Count/Compare value equality or encode an emulator event deadline. This keeps the validated operation/provenance facts while refusing to invent the unresolved Count-rewrite timing rule.

The report keeps the following proof claims explicitly false:

- sensor coverage certified;
- exact Count-rewrite timing certified;
- interrupt-gate chronology certified;
- save/restore/reset chronology certified;
- handler lifetime certified;
- whole-ROM roots certified;
- native complete.

Thus the new abstraction cannot waive missing closure evidence.

## Rejected or superseded patches/assumptions

- Rejected wholesale adoption of the research branch and its emulator fixture as production code.
- Rejected any rule that infers acknowledgement from a Compare value change. Same-value writes remain operations.
- Rejected any rule that lets Count writes clear an already pending timer request.
- Rejected deriving timer assertions from equal final values or from a final-state snapshot.
- Rejected promoting the Gopher64 relative-deadline behavior to hardware truth.
- Rejected promoting the ares/Mupen Count-rewrite scheduling behavior to hardware truth.
- Preserved the reference disagreement until hardware/system-test evidence resolves it.
- The first production validation attempt failed only `cargo fmt --all -- --check`; the exact rustfmt changes were applied before the accepted validation runs.
- Temporary branch-only CI scaffolding is validation machinery and is not intended for canonical `main`.

## Files changed for production

Intended canonical diff:

- `crates/plaid-core/src/lib.rs`
- `crates/plaid-core/src/timer_interrupt.rs`
- `research/integration-receipts/20261011-count-compare-timer-gpt56sol-direct-count-compare-20261011.md`

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md`, and `progress.json` are intentionally unchanged. This integration adds a reusable bounded evidence primitive but does not discharge the timer census, interrupt-gate chronology, handler lifetime, whole-ROM closure, or native-complete milestones.

## Validation

### Reference reproduction

Fresh rerun of exact-pin research job `114055349538` in Actions run lineage `37999959747`: **PASS** for exact reference checkout, source guards, adversarial model, exact ares matrix and durable evidence hashing/upload.

### Production validation before latest-main reconciliation

Actions run `38154534765` on integration head `934a18440e2b0f7a03418505a6374afb429af8d2`: **PASS**.

### Production validation after reconciliation onto canonical main `60c5af29a9199ae207d487b4d791b13fb21ae708`

Actions run `38154701888`, job `114515162151`, tested integration head `bae6e1adffc5e4c82dc84992a326ba1289a4774b`: **PASS**.

Passed gates include:

- exact decoder dependency-pin guard;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked -p plaid-core timer_interrupt`;
- `cargo test --locked --workspace`;
- `python scripts/test_cli.py`;
- synthetic CPU-copy, XORI transform, CPU SP producer, RSP/CPU IMEM composition, XORI cache visibility, PageMask cache remap, PI cache visibility, SP DMA DMEM ingress, RSP store isolation, EntryHi cache reactivation and TLBR cache reactivation contracts;
- independent fetch-summary assignment oracle.

Adversarial timer regressions specifically cover equal-value/different-generation Compare writes, Count-as-ack forgery, observed assertion identity versus value inference, repeated assertion without acknowledgement, stale before-state, reordered ordinals, deleted source under an old receipt and complete-report tampering.

## Limitations

The source SHA authenticates the supplied finite history bytes; it does not prove that an observer captured every architecturally relevant timer event. Sensor/census completeness therefore remains a separate obligation.

This integration does not establish:

- cycle-exact Count rewrite/equality timing;
- hardware-universal event-scheduler semantics;
- Status.IM7 / IE / EXL / ERL / BEV chronology or vector selection;
- software Cause IP0/IP1 ownership or external MI/device interrupt producer histories;
- save/restore/reset timer epochs;
- handler executable-byte provenance;
- cache-visible handler state;
- TLB/mapping/alias lifetime of handler bytes;
- all execution roots for an arbitrary ROM;
- whole-ROM CLOSED status;
- native completeness.

UNKNOWN remains UNKNOWN for every one of those dimensions.

## Remaining proof obligations

A whole-ROM certificate still needs to compose the timer producer with independently validated interrupt eligibility/vector chronology, complete reachable Count/Compare mutation census, save/restore/reset chronology, all other interrupt producers, handler executable provenance, mapping/cache/backing lifetime and the rest of the root/mutation/indirect closure model.

If Plaid eventually needs a stronger Count-write timing rule, obtain a dedicated hardware/system-test arbiter first. The current reference disagreement is a reason to keep the obligation OPEN, not a reason to select whichever emulator behavior makes closure convenient.
