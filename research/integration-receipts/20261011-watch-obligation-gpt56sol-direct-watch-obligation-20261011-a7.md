# Direct integration receipt: bounded VR4300 Watch exception obligation

Date: 2026-10-11

Worker: `gpt56sol-direct-watch-obligation-20261011-a7`

PR: #36

## Source research

The production boundary is derived from the validated subset in
`research/watch-exception-roots-gpt56sol` at
`c187ff70e4f0464a034198fd91e8cf131d9d86b7`, especially
`research/watch-exception-roots-gpt56sol.md` and
`experiments/watch-exception-roots-gpt56sol`.

That research combines the VR4300 User's Manual (`U10504EJ7V0UM00`, 7th
edition, sections 6.3.8 and 6.4.17) with exact pinned reference audits. The
manual establishes the bounded facts consumed here: WatchLo selects an 8-byte
physical-address block through PAddr0 bits 31:3; R/W enable load/store trapping;
CACHE is excluded; a matching enabled access raises ExcCode 23; Watch uses the
BEV-sensitive common `+0x180` exception vector; EXL postpones Watch; and Watch
register state is undefined after reset rather than architecturally disabled.
The research model also keeps higher-priority exception classification separate:
a matching Watch candidate is not admitted as an immediate Watch when a known
higher-priority exception preempts it.

Exact pinned sources used by the research are ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, Gopher64
`e96debac941a26ba4961e5145056c0821d3a56f7`, Mupen64Plus Core
`ba95bab92a76744753bfe61470823a4937850ab0`, and n64-systemtest
`196f5421173220eb2f63a7a99c64795dc0ea0698`.

A fresh rerun of the exact research workflow, run `37970065497`, job
`114512794005`, passed on 2026-10-11: exact pinned references were fetched,
the adversarial certificate model passed, source contracts remained guarded,
and the exact pinned ares matrix rebuilt and passed. This reproduces the
important disagreement rather than treating an old badge as authority: pinned
ares still has guest-writable/serialized Watch state and an ExcCode-23 wrapper
but no audited load/store call site invoking it, so emulator non-observation
cannot discharge the architectural Watch obligation.

The source research remains **PARTIAL** overall. It does not validate exact
postponed-entry timing after EXL clears, the complete hardware exception-priority
order, branch-delay behavior on hardware, the full privilege/ERL matrix, or a
physical N64 system-test receipt. Those facts are not invented below.

## Reproduced current-production gap

A test-only production regression was first committed as
`52840ff7bdeb40455b4858f006530d9e1d601224`. PR #36 Rust-check run
`38153572786` failed before a production implementation existed: canonical
Plaid exposed a numeric general/TLB root selector but no typed Watch
reachability/state assessment boundary. The branch was then reconciled with the
concurrent BEV=1 PIF-root main state through
`443828de57badeb980ae380cdfecd06a9b821963` before implementation validation.

The first implementation run `38153690989` failed only the formatting gate on
two test `let-else` statements; dependency pin validation had already passed and
Clippy/tests were skipped by the formatter failure. The formatting defect was
fixed rather than waived.

The reconciled implementation head `4e80c00dc97f57a383479d18e796ba200cf1832e`
then passed PR #36 Rust-check run `38153803804`, job `114512497250`: exact
decoder dependency pin, `cargo fmt --all -- --check`,
`cargo clippy --locked --workspace --all-targets -- -D warnings`,
`cargo test --locked --workspace`, CLI checks, every retained synthetic history/
cache/RSP/TLB contract, and the independent fetch-summary assignment oracle all
passed.

After canonical `main` advanced through RSP IMEM egress and then infrastructure
commit `24689113469e0a3325601d7b6fd41b4d06ecf761` made the canonical Rust
workflow manual-only, the production candidate was reconciled onto that exact
main state. During final review the source model's explicit
`higher_priority_exception` input exposed a missing fail-closed boundary in the
first Rust helper. Production was hardened so an immediate Watch root now
requires independently established `higher_priority_exception = Some(false)`;
unknown priority remains unresolved and known preemption yields no immediate
Watch.

Because this connector-only worker had no checked-out local repository while the
canonical workflow had intentionally stopped automatic PR runs, a temporary
**branch-only** workflow duplicated the canonical commands for one exact
post-drift validation. It is validation scaffolding only and is excluded from
the production tree. Run `38154501397`, job `114514570117`, checked PR merge SHA
`436bc6ba045e8fcf88babe702c547378ee20d6dd`, which merges hardened production
head `b19b089b20c3f5d0c2af8c2723b1a1e23db849da` into exact main
`24689113469e0a3325601d7b6fd41b4d06ecf761`. It passed:

- exact Rabbitizer dependency pin check;
- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- every retained CPU-copy/XORI/CPU-SP/RSP/cache/PageMask/PI/SP-DMA/RSP-store/
  EntryHi/TLBR synthetic contract; and
- the independent fetch-summary assignment oracle.

The same full-workspace log explicitly ran `tests/watch_roots.rs`: **7/7 passed**,
including the new independent-priority regression, reset-unknown/CACHE behavior,
8-byte physical matching, missing/postponed context, BEV root selection,
same-value distinct generations, and malformed-state rejection.

## Adopted invariant

Production now has a deliberately small `watch_roots` assessment primitive.
It accepts already-authenticated state/context rather than pretending to discover
that context itself.

- Reset or otherwise unauthenticated Watch state remains `Unknown`; it is never
  replaced with a convenient zero/disabled assumption.
- A known Watch configuration carries a nonzero external register-history
  generation. Equal semantic WatchLo values may therefore retain different
  operation identities; this verifier never derives generation from value
  equality.
- PAddr0 matching is an 8-byte **physical** block comparison. A virtual address,
  numeric target equality, or current mapping is not accepted as a substitute for
  trustworthy physical-translation evidence.
- R enables loads and W enables stores independently. Disabled access classes
  produce a bounded no-immediate-Watch result.
- CACHE is explicitly outside the Watch trigger set and is classified without
  inventing Watch register state.
- An otherwise matching access cannot become an immediate Watch merely because
  priority evidence is absent. Unknown higher-priority status remains unresolved;
  a known higher-priority exception yields no immediate Watch; only independently
  established absence of such preemption permits the bounded Watch-root result.
- An enabled physical match with known non-preemption, `EXL=false`, and known BEV
  produces a typed ExcCode-23 receipt at the existing common general `+0x180`
  root.
- Missing physical address, unknown Watch state, unknown priority/EXL/BEV, or a
  matching access while EXL is set remains unresolved. In particular, the
  verifier does not approximate postponed Watch as either an ordinary access or
  an immediate exception.
- Malformed claimed known state, including generation zero or a non-8-byte-aligned
  physical block, is rejected.

This receipt is a reachability/root obligation primitive, not a closure
certificate. A caller must independently establish the histories supplied to it.

## Adversarial regressions

Focused Rust regressions cover:

- reset-unknown versus explicit CACHE exclusion;
- `+0` and `+4` addresses matching one 8-byte physical block while `+8` does not;
- R/W access-class separation;
- unknown priority remaining unresolved and known higher-priority preemption not
  becoming an immediate Watch;
- missing physical-address evidence;
- unknown EXL and BEV;
- EXL-postponed matching accesses remaining unresolved;
- BEV=0 and BEV=1 common-vector roots;
- equal-value configurations with distinct generations remaining distinct; and
- malformed generation/alignment claims being rejected.

The exact research workflow additionally reran its deterministic 100,000-history
adversarial model and exact pinned ares matrix. The research model preserves
same-value register rewrites as separate history events and rejects forged claims
that collapse reset-unknown, physical aliases, priority preemption, postponed
state, BEV roots, or same-value generations.

## Rejected / superseded approaches

No research branch was mechanically merged. The Python adversarial model remains
research evidence, not a production implementation. Pinned ares's missing Watch
execution call site was explicitly **not** imported as hardware truth, and no
emulator-majority rule was used. The production code reuses Plaid's already
validated numeric general-vector selector only after the bounded Watch conditions
are satisfied.

No STATUS/NEXT/DECISIONS/progress change is made by this integration. Canonical
NEXT/ADR state already keeps Watch as a separate OPEN whole-ROM root obligation;
this bounded helper does not authenticate the required CP0/translation/priority
chronology, handler bytes, executable lifetime, root-set completeness, or any
milestone. Changing those documents to imply otherwise would be a larger claim
than the evidence supports.

The temporary `.github/workflows/direct-watch-validation.yml` exists only on the
integration branch to obtain the post-drift validation above. It is deliberately
excluded from the clean production commit and does not revert or bypass the
canonical manual-only CI policy.

## Files changed in the production integration

- `crates/plaid-core/src/watch_roots.rs`
- `crates/plaid-core/src/lib.rs` (module export only)
- `crates/plaid-core/tests/watch_roots.rs`
- this receipt

## Limitations and remaining proof obligations

Still OPEN:

- complete/authenticated WatchLo write census and register-generation chronology;
- BEV, EXL, ERL, privilege-mode and complete exception-priority writer chronology;
- trustworthy virtual-to-physical translation/mapping identity for every relevant
  reachable load/store, including aliases and TLB remaps;
- exact hardware timing for EXL-postponed Watch and the complete hardware
  exception-priority matrix;
- branch-delay Watch behavior and a physical N64/system-test receipt;
- handler-byte provenance, mapping/cache residency and executable lifetime at the
  selected common root;
- interaction with save/restore/reset/NMI chronology;
- complete exception/root and executable-mutation censuses;
- whole-ROM closed-world proof and native completeness.

`UNKNOWN` remains `UNKNOWN`; this integration weakens no solver or
`native_complete` obligation.
