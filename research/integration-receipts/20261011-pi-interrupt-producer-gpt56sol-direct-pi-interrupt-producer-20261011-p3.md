# PI interrupt producer direct-integration receipt

Date: 2026-10-11
Worker: gpt56sol-direct-pi-interrupt-producer-20261011-p3
Canonical parent: ba301823e3869514a396a3989c6e820381924946
Source implementation: 88bade1622ecd3f202f0ca2afdf11aae5d2c6413
Validation run: 38156164791

## Source research and reproduced evidence
Research source is research/pi-interrupt-root-compose-gpt56sol @ 9843c85db8b3654cc01923cdcba7f52d7abf4056, research/pi-interrupt-root-composition.md, and experiments/pi-interrupt-root-compose-gpt56sol/{model.py,source_guard.py}. Adjacent pi_queue_history.rs and pi_fetch_lineage.rs were audited but are not equivalent completion evidence. Pre-adoption run 38154507627 reproduced existing PI history 19/19, exact pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04, Mupen64Plus Core ba95bab92a76744753bfe61470823a4937850ab0 and Gopher64 e96debac941a26ba4961e5145056c0821d3a56f7 source guards, plus RESULT_SHA256=90187885016ce98b2f8fbcf4104b419c9a2450c182a9d2cd82093b61a9eb0ab2. The retained adversarial campaign covers failed queue insertions, cancellation, masked completion/unmask, clear, equal-payload latest-copy decoys, same-value mask repolls, and 64 histories / 320000 operations (6154 copies without queued completion, 40095 same-value mask operations, 56 roots whose causal source differs from latest copy).

Source-head validation run 38155091621 passed focused 19+8 tests, exact guards/model, cargo test --locked --workspace, cargo fmt --all -- --check and strict workspace clippy. R3 reconciliation run 38155651127 passed the same gate on TLBR main. Main later advanced by the non-overlapping LL/SC mutation integration, so this run repeats every required check on ba301823e3869514a396a3989c6e820381924946 before emitting a clean commit.

## Adopted invariant
A PI byte copy/request is not an interrupt-completion witness. Only an explicit source-hash-bound completion observation may mint a completion generation and raw MI.PI ancestry. MI mask writes mint separate poll generations even when same-value. Interrupt clear cuts raw ancestry. Restore cuts raw/mask ancestry to UNKNOWN. CPU RCP-pending derives only from authenticated raw ancestry plus observed mask state. Equal payloads, current snapshots, latest requests, final state and finite traces cannot manufacture chronology.

## Rejected / superseded patches
No mechanical research merge; no ares queue/timing policy is hardware truth; pi_queue_history guest_completion_claimed=false remains unchanged; no PI-copy/latest-value inference; no generic CPU interrupt gate/BEV root duplication. The later pi-irq-provenance x4 worker explicitly withdrew as duplicate evidence.

## Files changed
crates/plaid-core/src/lib.rs; crates/plaid-core/src/pi_interrupt_history.rs; crates/plaid-core/tests/pi_interrupt_history.rs; docs/STATUS.md; docs/NEXT.md; docs/DECISIONS.md; this receipt.

## Limitations / remaining proof obligations
Source/sensor completeness and authenticity, hardware timing, accepted request/queue-dispatch -> completion join, reset/save/restore chronology beyond explicit cuts, non-PI producers, generic CPU eligibility/root transfer, handler byte/cache/mapping/lifetime provenance, complete root/mutation census, whole-ROM closure and native completeness remain OPEN. Missing chronology remains UNKNOWN; no flag waives it.
