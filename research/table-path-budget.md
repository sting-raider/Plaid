# Bounded longer table proofs (ADR-0209)

Base: `4075dcc1fca921acfbf38510eac9bef70195200b`.

Tracing a retained, call-free Paper Mario dispatch found rejection at the
16-frame backward-path limit, with its range predicate already established.
The diagnostic required 20 frames to reach a concrete initializer and recheck
all incoming paths. It generated a fresh certificate; an old candidate prefix
hash was not treated as current proof. This was a resource limit, not evidence
of a changed pointer or index.

The general frame bound is now 32. The separate 4,096 instruction-read budget,
full pending-state cycle comparison, external-entry and call barriers, slot
binding checks and exact source/target verification are unchanged. Exceeding
either resource bound still rejects. No ROM address or target list appears in
the production change.

An authored 24-block case-backedge fixture failed at 16 frames and passes at
32. Changing the base in a middle delay slot, adding an unknown entry, and a
40-block path still reject. Existing guard-count and source/entry counterexamples
pass. A native 24-block case chain equals pinned ares over full register,
PC, FPU and RAM checkpoint state. Independent code review found no findings;
the reviewer did not run tests.

The fresh ROM-only pass is OPEN/15 with 56,799 blocks and 162 loads, down from
OPEN/16. It closes the 56-entry dispatch at `800e9de4`, adds no blocker sites,
and needs no extra roots or game-specific data. Native Paper Mario emission
remains refused. Ignored receipts are under `target/paper-mario/0209/`.

Optimized incremental compilation of this semantic constant change took
7.27 seconds. Discovery took 28.258 seconds and solve 16.785 seconds; the prior
entry-origin pass took 30.930 and 13.053 seconds. These are single operational
runs, not a controlled performance comparison. The larger path search remains
bounded. Canonical acceptance requires the exact final clean committed tree's
local format, Clippy, workspace, CLI, runtime and pinned-reference gates.
