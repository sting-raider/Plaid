# Primary takeover: bounded maskable interrupt gate

Hypothesis: the prepared maskable-interrupt gate can reuse current production
general-vector selection without conflating architectural eligibility with
producer identity, occurrence or complete-root reachability. A receipt must
also recheck against the independently supplied input boundary state.

Reconciliation base: `a8d3a529884f35987f655d76ade4db85da1f36f3`.
Prepared candidate: `a4d814b2d488003e0763ad3796220228eb86b4fb`, PR #22;
source research: `716b0dc18a8bd0427dfa7c629b1bd3d5952d0ad1`, closeout `6078668009`.
The candidate was repeatedly validated but stranded by obsolete main-write
leases. Its code and adversarial matrix are retained semantically; historical
workflow scaffolding and its stale integration receipt are not merged.

## Source evidence and design

The original 32-case actual ares boundary capture distinguishes interrupted
guest instruction suppression from ordinary ADDIU retirement using PC, GPR,
EPC, EXL and Cause state. Historical artifact `11706932602` ZIP receipt
`757e474c1b9fe626df09f574e19601007d8384bdcf77d4c95146b238af912bd7`
and result receipt
`2775206efc797f614c07c36a783909c5468b55d609d93c34764c097499777eaf`
are authenticated before local production comparison. No Actions run is started
and no reference emulator is rebuilt.

The bounded rule admits a numeric root candidate only for nonempty normalized
Cause.IP/Status.IM intersection, IE set, EXL clear and ERL clear. Reuse current
`exception_roots` General selection: BEV=0 `ffffffff80000180`, BEV=1
`ffffffffbfc00380`. Preserve complete input bits and the exact enabled subset.
Add a verifier that reconstructs the full receipt from the independent boundary
input, rejecting edited input, subset, vector and suppressed-state receipts.

Pinned ares CPU/exception blobs and Gopher64 exception blob are checked at the
recorded exact revisions with selected-file cleanliness. Those reference sources
are behavior/context only; no implementation is copied. Current PI interrupt
producer replay is complementary: it does not supply a complete architectural
gate boundary or all producer ancestry. Watch/NMI/reset/asynchronous priority
and exception-root byte histories remain distinct.

## Local validation before canonical publication

Retain the candidate's three regressions (32 actual-source cases: 18 admitted,
14 suppressed) and add receipt-mutation/suppression/type regressions. Compare
all 32 authenticated historical source rows in an ignored local Rust harness.

```text
cargo test --locked -p plaid-core --test interrupt_roots
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
git diff --check
```

The final canonical commit must directly parent the validated exact main head
and use expected-head CAS with force disabled. No complete producer/status
writer census, chronology/timing, root occurrence/reachability, handler byte
provenance/lifetime, hardware-universal semantics or native closure follows.
No solver waiver or progress milestone change.
