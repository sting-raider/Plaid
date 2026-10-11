# Primary takeover: captured overlap-copy writer chronology

Base: 65aa3cc43be7ea2eb4a36c25afe47414259fa2a0.
Candidate: 963fd816c2253c023f9dc65a11b19754cd55684b, PR #30.
Research: 30f79b201766356c65c37137b4b1ef964f265d0f;
research/overlap-cpu-copy-lineage.md and research closeout 6091204841.

Hypothesis: forward overlap may consume earlier captured destination writes;
initial/final byte snapshots cannot reconstruct that chronology. Retain fresh
successful phase-scoped Word-writer identities without claiming that captured
coverage proves ultimate read ancestry.

The candidate extends current canonical cpu_copy by a separate report and API,
reusing its strict adjacent and live-definition parsers. Existing wire/CLI
contracts are preserved. Every successful captured SW creates a fresh identity,
including same-value non-copy writes. Phase changes cut local writer candidates.
Externally authenticated source bytes and whole-report reconstruction are required.

Primary review found a contradictory-read gap. Store A to source0x1004, read B
there, then read A again. Prepared code reported the old captured generation for
both reads. The retained deterministic regression fails against prepared code
([None,Some(1),Some(1)]) and passes after tracking the captured value and cutting
the candidate on contradiction ([None,None,None]). A later equal value does not
revive an older writer. This preserves valid forward-overlap candidates without
confusing relative capture chronology with a complete mutation history.

Six lineage regressions and the ten existing CPU copy/definition regressions
PASS. Retained source research was already validated against exact pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. This integration changes the consumer of
canonical strict source records, not a new hardware contract; no reference rebuild
or Actions run is needed or triggered.

Required final local gate on the exact base:
cargo fmt --all -- --check;
cargo clippy --locked --workspace --all-targets -- -D warnings;
cargo test --locked --workspace;
python scripts/test_cli.py;
git diff --check.

Exclude raw research implementation and stale predecessor docs/receipts.
Captured latest compatible writer is only a candidate. Complete storage ancestry,
CPU/device/RSP/DMA mutation coverage, cached/mapped/epoch composition, executable
consumption/lifetime, whole-ROM closure and native completeness remain OPEN;
all broader flags false. No progress milestone or solver waiver. Publish direct
child of exact validated head after refetch and expected-head CAS force=false.

Outcome: focused copy/lineage tests and fmt/strict Clippy/full workspace/CLI
gates PASS on the exact base, including the retained outer fixed-point adversary.
Older PR #6/#20 CPU-copy implementation/tests are identical to the final prepared
candidate's selected paths; their remaining differences are predecessor canonical
modules/docs. They are superseded with PR #30 by this reconciled consumer.
