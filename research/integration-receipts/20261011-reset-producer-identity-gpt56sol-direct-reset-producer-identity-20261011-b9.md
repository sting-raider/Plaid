# Direct integration receipt: reset/HW2/NMI producer-delivery identity

Date: 2026-10-11
Worker: `gpt56sol-direct-reset-producer-identity-20261011-b9`
Cluster: policy-neutral reset request / HW2 / NMI event generation identity
Claim base: `9154b30b12026c8c122f654d7fe90f0f67968dce`

## Source research

- branch: `research/reset-hw2-nmi-producer-gpt56sol`
- final research head: `003fc98d51f8c20dcb92c2154d6f7f1ac1cf1cf9`
- durable note: `research/reset-hw2-nmi-producer.md`
- adversarial model: `experiments/reset-hw2-nmi-producer/model.py`
- source guard: `experiments/reset-hw2-nmi-producer/source_guard.py`
- exact pinned Mupen64Plus: `ba95bab92a76744753bfe61470823a4937850ab0`
- exact pinned Gopher64: `e96debac941a26ba4961e5145056c0821d3a56f7`
- research final-head Actions run: `38053001322`
- original final-head job: `114215767619`
- fresh integration rerun job: `114512249112`

`refs.lock.toml` on the integration base still carries exactly those Mupen64Plus
and Gopher64 revisions.

## Reproduced evidence

Fresh exact-pin rerun `38053001322` / job `114512249112` completed SUCCESS during
integration. It re-checked the guarded pinned sources and executed the deterministic
adversarial model twice.

The reproduced portable facts are deliberately weaker than either emulator's
policy:

- exact pinned Mupen64Plus can accumulate multiple same-type reset-related queue
  nodes, including distinct nodes with equal `(type,count)` values;
- exact pinned Gopher64 uses one replaceable NMI event slot, so a later reset may
  overwrite/coalesce an earlier pending NMI;
- both guarded delivery paths consume/disable the selected event before invoking
  its handler;
- Mupen queue save/restore serializes `(type,count)` but no external Plaid producer
  token, so equal restored rows cannot recover observer ancestry by value equality;
- therefore pending state, event type/count equality, PC equality and payload
  equality are not portable causal event identity.

The research deterministic payload SHA-256 is
`b6c83636a61bb77dbed04030a70fd085f111a569c43d23c5707ea04a57b0d6b2`.
The guarded-source canonical payload SHA-256 is
`4e975061e69d31838e193ae160e80fb5b1e01d50c9d1a38122303dab0547901d`.

The research result is PARTIAL about physical reset behavior: the references
materially disagree on accumulate-vs-coalesce semantics. That disagreement is
preserved, not resolved by voting.

## Adopted production invariant

`plaid_core::reset_producer` performs a bounded, source-bound observed-history
replay with explicit generations for reset requests and HW2/NMI delivery events.
It does not choose a universal repeated-reset policy.

The verifier requires:

- a syntactically valid complete-capture SHA-256 namespace;
- original contiguous record ordinals;
- nonzero, never-reused reset request generations;
- nonzero, never-reused event generations;
- produced events to reference an already-observed request generation;
- deliveries to consume one still-active event exactly once with the same delivery
  kind;
- explicit supersession to reference two existing, still-active events of the same
  kind;
- imported pending events with unavailable request ancestry to remain explicitly
  producer-UNKNOWN.

Multiple active events may have the same delivery kind and the same schedule value
without merging. Explicit supersession can represent a captured coalescing event,
but the resulting report still sets `repeated_reset_policy_certified=false`.

A delivery of an imported event is representable for chronology, but its receipt
has no request generation and `producer_identity_certified=false`. No later equal
value can attach ancestry to it.

## Adversarial regressions

Focused Rust tests cover:

- two reset requests whose HW2 and NMI events have equal schedule values but retain
  distinct generations and request ancestry;
- explicit coalescing/supersession without promoting it to hardware truth;
- imported pending event delivery with UNKNOWN request ancestry;
- duplicate/replayed delivery;
- attempted delivery of a superseded event;
- fabricated request ancestry;
- reused request and event generations;
- supersession to a consumed replacement, across delivery kinds, or to self;
- deleted/reordered source ordinals;
- wrong delivery kind;
- zero generations and malformed capture identity.

## Production files changed

- `crates/plaid-core/src/reset_producer.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md`
- this receipt

`progress.json` is intentionally unchanged: this does not close reset/NMI root
coverage, whole-ROM closure or native completeness.

## Validation

Initial current-main production head `1ec1f608f27b9282ad03c439760bd26b875f6cca`
passed canonical workflow `38153705376`, job `114512210917`:

- exact decoder dependency pin check: PASS
- `cargo fmt --all -- --check`: PASS
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS
- `cargo test --locked --workspace`: PASS
- synthetic CLI checks: PASS
- all canonical CPU-copy/XORI/CPU-SP/RSP-IMEM/cache/PageMask/PI/SP-DMA/RSP-store/EntryHi/TLBR synthetic contracts: PASS
- independent fetch-summary assignment oracle: PASS

Fresh exact-pinned reset-producer research rerun `38053001322` / job
`114512249112`: PASS.

The final tested integration head and canonical main CI are recorded by the issue
#4 MAIN-INTEGRATION CLOSEOUT after any required main reconciliation.

## Rejected / superseded approaches

- Do not encode Mupen's `+50,000,000` count delay as N64 hardware timing.
- Do not encode Gopher64's one-slot coalescing as universal reset semantics.
- Do not encode Mupen's accumulating queue as universal reset semantics.
- Do not infer event identity from equal pending values, `(type,count)`, PC or
  payload equality.
- Do not replay a consumed or superseded event as a fresh delivery.
- Do not attach a pre-save observer token to an imported/restored equal-valued
  pending row unless an independent save/restore identity contract proves it.
- Do not use this module to manufacture NMI root-fetch or executable-byte
  provenance; those are separate obligations and an earlier direct-integration
  worker owns that lane.

The first research workflow attempt that failed because an evidence directory was
created after `tee` is harness-only history and not semantic counterevidence. The
fixed research workflow changed no experiment semantics.

## Limitations / remaining proof obligations

This integration does **not** prove:

- physical reset-button electrical or hardware scheduling semantics;
- whether real hardware accumulates, suppresses, stretches or coalesces repeated
  reset requests;
- Mupen/Gopher timing constants;
- a complete reset-request or NMI producer census;
- save/restore producer identity or chronology epochs;
- simultaneous maskable IRQ/NMI priority;
- NMI architectural root transfer, fetch occurrence or root-byte provenance;
- reset/cache/mapping executable lifetime;
- whole-ROM CLOSED or native completeness.

A future composition may consume a certified NMI delivery receipt as one input to
NMI-root causality, but it must still independently prove the root transfer, actual
root fetch and executable-byte source/generation. UNKNOWN ancestry remains UNKNOWN.
