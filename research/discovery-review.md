# Continuing discovery review

2026-10-08. Baseline: pushed `240b66e` on `codex/executable-discovery`.
The review follows the existing plan, decisions, task ledger, research notes,
experiment acceptance criteria and current implementation boundaries.

The synthetic M1–M3 foundation is useful: canonical ROMs, byte-backed CFGs,
session-qualified trace evidence, verified PI-copy mappings, rechecked constant
target certificates and a solver that reconstructs required control facts.
Finite target observations and table snapshots remain insufficient for closure.
Deleting diagnostics or CFG facts cannot manufacture a native-complete map.

The later reference experiments address real limitations rather than restarting
that model. Mupen's pinned cartridge/LLD gaps motivate the independent ares
observer. Firmware input fixes the declared boot setup's initial Config mismatch
without patching the guest. Complete raw-source verification preserves v0/v1/v2/
v4/v5 facts and earlier serialization hashes. None of these bounded prefixes
proves complete guest-test execution or an executable universe.

The central remaining join is chronological byte history. Cache snapshots recur
after eviction; different virtual slots can contain equal payloads; guest CACHE
tag stores move effective hit pages while retaining words from an earlier fill.
Successful RAM bursts identify finite transactions, while translated/degraded/
failed paths stay outside the identity-only witness policy. Payload or address
equality therefore cannot establish copy origin, image generation or lifetime.
Raw summaries' first/last indices are not continuous intervals.

Next, test one ordered transaction/fill/CACHE/fetch ledger on the existing
controlled fixture, including the declared host mutation before stale writeback.
Require independent baseline and complete prior projection equality. Keep fixture
writes visibly distinct from guest CPU/device copies. Then test reset/restore and
ordinary mutation/copy boundaries before broader capture and contextual image
construction. This is the existing NEXT priority, not a new architecture.

Current baseline validation: all 76 Rust integration tests, formatting and strict
Clippy pass. Earlier source-specific acceptance checks and complete corpus hashes
are documented in their research notes; this review does not claim to rerun them.
Whole-ROM remains OPEN, `native_complete=false`, and native lowering stays deferred.

The subsequent fresh fetch found orchestration updates through `3cf45dc` and 17
isolated research branches. Their durable findings are being reconciled separately;
the branch tips, evidence levels and reproduction results belong in the parallel
research review. The local baseline above describes the starting checkout only.
