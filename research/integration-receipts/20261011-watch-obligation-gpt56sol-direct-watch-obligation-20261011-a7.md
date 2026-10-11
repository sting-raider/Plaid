# Direct integration receipt: bounded VR4300 Watch exception obligation

Date: 2026-10-11

Worker: `gpt56sol-direct-watch-obligation-20261011-a7`

Claim base: `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`

Final validated base: `0e0e999b626dbda3f47cfd6aa89673618ae20350`

PR: #36 (development/reproduction vehicle only; canonical landing is a clean direct commit)

## Source research

This integration selectively consumes the validated subset from
`research/watch-exception-roots-gpt56sol` at
`c187ff70e4f0464a034198fd91e8cf131d9d86b7`, especially
`research/watch-exception-roots-gpt56sol.md` and
`experiments/watch-exception-roots-gpt56sol/model.py`.

The bounded source facts are taken from the VR4300 User's Manual
`U10504EJ7V0UM00` (7th edition, sections 6.3.8 and 6.4.17) plus exact pinned
reference audits. Within the adopted scope:

- WatchLo PAddr0 identifies an 8-byte physical-address block.
- R and W independently enable load and store Watch matching.
- CACHE is excluded from Watch triggering.
- a matching enabled access uses ExcCode 23 and the BEV-sensitive common
  general exception vector at `+0x180` when it is actually the admitted
  exception;
- EXL postpones Watch rather than proving either immediate entry or ordinary
  completion; and
- Watch state is undefined after reset, so reset must not be normalized to a
  convenient disabled/zero value.

The research model also preserves higher-priority exception classification as a
separate input. A physical Watch match cannot be promoted to an immediate Watch
root unless absence of higher-priority preemption is independently established.

Exact pinned research sources include ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, Gopher64
`e96debac941a26ba4961e5145056c0821d3a56f7`, Mupen64Plus Core
`ba95bab92a76744753bfe61470823a4937850ab0`, and n64-systemtest
`196f5421173220eb2f63a7a99c64795dc0ea0698`.

A fresh rerun of the retained exact-pin Watch research workflow passed as Actions
run `37970065497`, job `114512794005`. It rebuilt the exact pinned ares matrix,
reran the deterministic adversarial model, and rechecked the source guards. The
important disagreement remains explicit: pinned ares contains Watch register
state and an ExcCode-23 helper but the audited memory-access paths do not invoke
that helper. Emulator non-observation therefore does not discharge the hardware
Watch obligation.

## Reproduced current-main gap

Reproduction was test-first. Commit
`52840ff7bdeb40455b4858f006530d9e1d601224` added only the focused Watch
regression. PR #36 run `38153572786` failed before a production Watch assessment
API existed, reproducing that canonical Plaid had numeric general/TLB root
selection but no typed Watch reachability/root obligation boundary.

The first implementation run `38153690989` failed only `rustfmt` on two test
`let-else` forms; that was fixed rather than waived. A subsequent full run
`38153803804` passed.

During final review, the retained research model exposed a missing fail-closed
condition in the first Rust helper: known/unknown higher-priority exception
status. Production was hardened so an immediate Watch receipt now requires
`higher_priority_exception = Some(false)`. Unknown priority remains unresolved;
known preemption yields no immediate Watch.

Canonical `main` then advanced repeatedly through BEV=1 PIF provenance, RSP IMEM
egress, the manual-only workflow policy, NMI root provenance, and cached
exception-root generation replay. The candidate was reconciled each time without
dropping those modules. The decisive final validation used exact base
`0e0e999b626dbda3f47cfd6aa89673618ae20350` and tested branch head
`fa6d76f7078d7981e42b670c7a55cc4891150844`.

Because canonical `.github/workflows/rust.yml` is intentionally manual-only and
this connector worker has no local Rust checkout/toolchain, a temporary
branch-only `direct-watch-validation.yml` duplicated the canonical commands for
post-drift validation. That workflow is validation scaffolding only and is not
present in the production landing.

Final exact-base validation: Actions run `38155018131`, job `114516100111`,
PASS. It executed:

- exact Rabbitizer dependency pin verification;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- `python scripts/test_cli.py`;
- every retained synthetic contract in spikes 044-054; and
- `python experiments/fetch-summary-realizability/model.py`.

The same full-workspace log ran `tests/watch_roots.rs`: **7/7 PASS**. It also ran
and passed the newly landed cached exception-root generation tests from the final
base, proving the Watch candidate was validated with that canonical integration
present rather than merely beside an older tree.

## Adopted invariant

Production now exposes a deliberately small `watch_roots` assessment primitive.
It consumes already-authenticated context and does not pretend to discover that
context by value equality or final state.

- `WatchState::Unknown` remains unresolved for relevant load/store accesses.
- A known Watch configuration carries a nonzero external register-history
  generation. Equal WatchLo values may retain distinct operation identities.
- The match is the trustworthy 8-byte **physical** block; virtual equality,
  current mappings, or numeric address coincidence are not substitutes.
- R/W enable load/store independently.
- CACHE is explicitly classified outside the Watch trigger set.
- Missing physical address, unknown exception priority, unknown EXL, unknown BEV,
  or a matching access while EXL is set remains unresolved.
- Known higher-priority preemption does not produce an immediate Watch receipt.
- Only an enabled physical match with known non-preemption, known `EXL=false`,
  and known BEV produces an ExcCode-23 receipt at the existing common `+0x180`
  root.
- Generation zero and non-8-byte-aligned claimed known Watch blocks are rejected.

The helper is a reachability/root obligation primitive, not a closure
certificate. It does not authenticate its supplied histories.

## Adversarial regressions

Focused Rust tests cover reset-unknown behavior, CACHE exclusion, `+0`/`+4`
matching versus `+8` mismatch, R/W separation, unknown and known priority
preemption, missing physical evidence, unknown EXL/BEV, EXL-postponed matching,
BEV=0/1 root selection, same-value configurations with distinct generations,
and malformed generation/alignment claims.

The retained research model separately exercises 100,000 deterministic histories
and forged claims including reset-unknown collapse, physical alias confusion,
CACHE-as-Watch, EXL-postponed collapse, wrong BEV root, higher-priority
preemption, and same-value generation coalescing.

## Rejected / superseded approaches

No research branch was mechanically merged. The Python model remains research
evidence, not production code. Pinned ares's missing Watch access call site was
explicitly rejected as hardware truth. No emulator-majority rule, virtual-address
shortcut, equal-value generation collapse, current-backing inference, or
postponed-Watch approximation is accepted.

The temporary validation workflow is excluded from the canonical tree. No
STATUS/NEXT/DECISIONS/progress update is made because this bounded primitive does
not discharge an existing whole-ROM/root/lifetime obligation or milestone.

## Files changed

Canonical production diff is exactly four paths:

- `crates/plaid-core/src/watch_roots.rs`
- `crates/plaid-core/src/lib.rs` (one module export)
- `crates/plaid-core/tests/watch_roots.rs`
- this receipt

## Limitations / remaining proof obligations

Still OPEN:

- complete and authenticated WatchLo writer census and register-generation
  chronology;
- trustworthy BEV/EXL/ERL/privilege and complete exception-priority chronology;
- trustworthy virtual-to-physical translation/mapping identity for every relevant
  reachable load/store, including aliases and TLB remaps;
- exact hardware timing after EXL-postponed Watch and the complete hardware
  exception-priority matrix;
- branch-delay Watch behavior and a physical N64/system-test receipt;
- selected handler-byte provenance, mapping/cache residency and executable
  lifetime;
- save/restore/reset/NMI chronology composition;
- complete exception/root and executable-mutation censuses; and
- whole-ROM closed-world proof and native completeness.

`UNKNOWN` remains `UNKNOWN`; no solver or `native_complete` obligation is
weakened.
