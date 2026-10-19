# Loop predicates for guarded table dispatch (ADR-0207)

Base: canonical `5cc8d136cd071e76b0c72d3dca343435ab3455fe`.

The earlier guarded table search rejected repeated predecessor blocks. The
producer now records a frame's block start, anchor, exclusive end and complete
backward `Need` state. After processing that exact interval, a repeated frame
may terminate only when the entire pending predicate equals the earlier one.
Every other predecessor is still visited; entries, unsupported edges/calls,
empty predecessor sets, inconsistent results and resource limits reject.
The result still needs a concrete table base/count witness. No cycle invents
an initial value. Identical branch-flag obligations are deduplicated.

The comparison belongs at the block start after transfer: an unrelated polling
branch flag can be overwritten by the block's load. Comparing before transfer
would incorrectly distinguish the taken and fallthrough polling paths.

A rejected shortcut compared only the unresolved base register and offset.
It produced a false positive when an initial three-entry guard was replaced by
a seven-entry guard on a later iteration. The exact authored counterexample
failed before removal and now rejects. The final rule compares all fields,
including guard count, guard/index identity, pending pointer definitions,
constants and branch flags; it has no base-only exception.

Focused verification: 30 table Rust contracts and core all-target Clippy pass.
Native authored preheader and captured-value loops equal pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04` over full registers/PC/FPU state and
RAM checkpoints. In the captured-value case, index 1 is loaded from data,
pointer and guard are captured, and the current index register reaches 3
inside a finite polling loop; the original pointer correctly selects case 1.
Changed pointer/flag/base, missing initializer, unknown entry, changed count,
annulled slots, protected writes and wrong strides retain rejection coverage.

Independent review of the corrected exact-state rule reported no findings;
the reviewer did not run tests. The corrected fresh ROM-only Paper Mario pass
is OPEN/16 with 56,799 blocks and 162 loads, compared with OPEN/17 and 56,495
blocks. The 42-entry dispatch closes with nine distinct targets; no new blocker
sites appear. The earlier base-only experiment is superseded, including its
OPEN/17 result. No native Paper Mario artifact or run is accepted.

The debug discovery probe took 245.035 seconds and solve 37.404 seconds; using
an unoptimized compiler was slower overall than optimized iteration. Receipts
are ignored under `target/paper-mario/0207/`. Canonical validation commands are
the format, locked workspace/all-target Clippy, workspace tests, CLI, full
runtime and pinned-ares gates. Entry-origin and loop/call preservation work
remains; no uncertain entry barrier is removed by this change.
