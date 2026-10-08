# Canonical imported facts and provenance

2026-10-08. Windows, Rust 1.98, Python 3.12, pinned reference fixtures.

Symptom/hypothesis: repeated sensor facts inserted after the last compilation
remain separate because their evidence sets differ. `merge_maps` unions identical
semantic facts by stripping evidence from its key, so merging the imported map
with itself can change its representation. Duplicate conflict diagnostics may
similarly survive when a later merge expands the evidence behind a conflict.

The regression `repeated_sensor_facts_preserve_provenance_and_merge_idempotence`
failed before the fix with `cargo test -p plaid-core --test merge <test-name>`.
It captures three identical indirect, entry-verification, word-store and DMA
facts after the final compilation. The imported map differed from its self-merge.
All execution evidence was present; the mismatch was canonical representation.

Fix: use the existing semantic provenance union once at import completion for
raw sensor facts, writes and unresolved items. Normalize newly added merge
diagnostics after conflict generation. Preserve every event ID and all semantic
fields, including source unit, value, verification epoch and copy-event identity.
No per-event rescan or new resolution rule is added; no performance claim is made.

The regression now passes, with one record per repeated fact and three evidence
references each. The correlated indirect target retains all six indirect/check
event references. Expanded block conflicts retain one diagnostic, all evidence,
commutative/associative merging and self-merge stability. Full-core and CPU harness
checks require imported JSON bytes to equal self-merged JSON bytes.

All 63 Rust integration tests, formatting, strict Clippy, CLI/exporter/hooks,
eight CPU scenarios, six full-core sessions and the spimdisasm comparison pass.
Whole-ROM remains OPEN; event counts and CPU states are unchanged. Some map
diagnostic record counts fall because equivalent facts now share provenance,
not because a blocker was resolved or removed.
