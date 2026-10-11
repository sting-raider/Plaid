# Primary takeover: resident mutation to exact backing writeback

Base: 24b77c041b6b49a305c47ee3715b4c810a288391.
Candidate: 5cd4b23c3afbba3b1a01339cdb61958dbd717c03, PR #42.
Research: 6cff6dc950c699abd7a5bfa8a56af9a65d789e43;
canonical spike 034 and research/ares-dcache-writeback-lineage.md (ADR-0067).

Hypothesis: concrete fill generation plus every successful resident mutation
revision and an exact same-snapshot successful backing transaction are necessary
before a cached mutation becomes backing-memory origin.

Adopt only original Plaid Rust/tests from the prepared candidate. Exclude its
workflows, validation trigger and stale canonical state. Reuse the already
reproduced canonical local complete result
8e4845630414a9ec99904fca5834ea0eab9162f67322c0598428473c74623034
(recorded trace e0cf9f8332b72377c20f665d89f640b80406ea358de7ecbf68de4b6936329192).
This is the primary strengthened local receipt, not the older worker recipe hash.
Original/disabled/enabled state and facts agree across all four guest phases.

Primary review adds a direct identity index guard. A deterministic regression
fails against the prepared code when every event changes slot256 to slot0 at
physical line0x1000, with equal payloads and a matching backing write. That
consistent forgery cannot represent the declared direct-KSEG0 identity scope.
The guard accepts the actual index and does not generalize it across TLB aliases.

The local adapter projects out I-cache traffic and separates the four controlled
phases (whose fixture resets are outside the sensed chronology). It renumbers
events and retains actual full-line payloads, fill/store/writeback order and
all 16 byte origins. Explicit hit writeback and dirty eviction produce exactly
two receipts; clean replacement and dirty invalidate/drop produce none.
Projected ordinals are comparison fixtures, not a complete sensor/epoch receipt.
No reference build or Actions dispatch.

Exact pinned ares HEAD/clean checkout and dcache.cpp SHA
a1e2dd9c619cae7dbba4162eab8ab09a239f818019b50a88e49b09501488650b
pass. Source context confirms virtual slot selection, full-line fill/writeback
and actual lower RDRAM effects. No upstream implementation enters production.

Nine focused regressions and all measured-source byte-origin comparisons PASS.
Required final local gate before canonical publication:
cargo fmt --all -- --check;
cargo clippy --locked --workspace --all-targets -- -D warnings;
cargo test --locked --workspace;
python scripts/test_cli.py;
git diff --check.

Authenticate complete supplied bytes externally and reconstruct every report
field. Same-value mutation changes revision; address/payload equality cannot
resurrect a retired resident generation. Original producer/operand ancestry,
source census, full cache semantics, TLB/cacheability/alias context, other store
families, reset/restore epochs, executable lifetime and native closure remain
OPEN. All broader flags false. No progress milestone or solver waiver.
Publish only direct child of exact locally validated base with refetch and
expected-head CAS force=false.

Outcome: focused tests, authenticated four-phase/all-byte comparison and exact
pinned source checks PASS. Final fmt/strict Clippy/full workspace/CLI gates
PASS on the exact base, including the retained outer fixed-point adversary.
No test or proof obligation was dropped.
