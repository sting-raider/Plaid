# Primary takeover: reconcile TLBWR selection/write histories

Base: 6d465ec96a8e6859b60ee65d94c12f14ca8987c9.
Candidates: 1ba1bb90249da4d81f6646d5f234c89e492fd01a (explicit selection);
0d0b920b999de745a0e7cf6140e8d008a717c444 (Wired range), PR #35.
Research: 62f722a0c4db72963f6c873ddd33b8df95ddbc7e,
research/ares-tlbwr-mapping-generations.md and spike 044 on that branch.

Hypothesis: concrete observed selection followed by a matching actual write is
the operation identity; CP0 Index, equal fingerprints and snapshot differences
cannot reconstruct the random replacement slot or erase a same-content write.

Retain the original Plaid explicit-selection replay/adversaries and reconcile
the competing candidate's validated Wired scope. Require Wired <32 and selected
slot in [Wired,31]. Remove broad model-only out-of-range no-write acceptance,
while retaining fault attempts without writer generations. The new lower-bound
regression fails against the prepared selection candidate, then passes with
the guard. No selection/write obligation is dropped to accommodate a branch.
Tighten nested no-write enum schema with unknown-field rejection.

Authenticate historical artifact 11611195370:
ZIP b404edf708c1c81f87a215a8e15fc863560b26c25fc7a1388279b3964437163f;
complete result 405def4f3c1e33c9cd0a8dd331ee1d33d0e664d1c578692989623796d986c11c.
State facts: first changed slot31 versus Index7, equal-payload decoy, zero changed
entries for the same-value second operation, and 32 controlled Wired30 slots in
30..31. A local comparison adapts those facts to 34 protocol fixture operations
with synthetic ordinals/fingerprints. This is not a callback/sensor capture or
mapping-content provenance claim. No hardware Random distribution is inferred.
No reference builds or new Actions runs.

Exact local ares HEAD and whole checkout cleanliness pass at
9408cb43d4948fc3ea6e152a307a34348df3fe04. The source guard checks concrete random
selection -> range return -> devirtualization clear -> slot assignment ->
synchronization -> notification ordering and interpreter decode. Recorded
interpreter-scc.cpp blob c3d119bf4931c4616ae297a4c18b561490207e11.

Focused TLBWI 7 and TLBWR 8 regressions pass. Saved-state comparison and exact
source guard pass. Required final local gate before publication:
cargo fmt --all -- --check;
cargo clippy --locked --workspace --all-targets -- -D warnings;
cargo test --locked --workspace;
python scripts/test_cli.py;
git diff --check.

Exclude both branch-only workflows/stale docs/lease receipts. Complete supplied
history hashing and every-field report rechecking remain mandatory. Source
coverage, mapping semantics, hardware Random distribution, translation context,
cache residency and executable lifetime/native flags remain false. No census,
whole-ROM or progress milestone is closed. Publish as direct child of exact
validated base after refetch and expected-head CAS force=false.

Outcome: focused tests, authenticated saved-state comparison, exact source guard,
fmt, strict Clippy, complete workspace and CLI gates PASS on the exact base above.
The retained outer fixed-point deletion adversary passes; no ignored/removed
closure check or milestone promotion.
