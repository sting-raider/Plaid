# Evidence merger v0

2026-10-08. Hypothesis: static and finite trace facts can merge deterministically
without turning observation into closure or overwriting contradictions.

Tests show commutativity, idempotence, dual provenance on merged blocks, visible
contradictory extents, and rejection of conflicting ROM/provenance identities.
Trace instruction words must match a unique supplied mapping; PC alone is never
enough. Invalidation advances a conservative session epoch. Compilation after an
invalidation gets a distinct execution identity even if its bytes happen to match.

Source-correlated indirect observations populate observed sets only when both
current identities and a decoded indirect site are unique. Uncorrelated lookups
remain diagnostics. Mask-restricted and pagespan entries remain unsupported.
Conflict errors on named overlay/provenance identities reject the entire pure merge
operation; the original input artifacts retain both sources unchanged.

`cargo test --workspace`: 20 Rust tests pass; strict Clippy and C exporter tests pass.
No trace-coverage or native-complete claim follows from these tests.
