# Direct integration receipt: reset/NMI root fetch provenance separation

Date: 2026-10-11  
Worker: `gpt56sol-direct-nmi-root-provenance-20261011`  
Cluster: fail-closed reset/NMI root transfer -> root-fetch occurrence -> executable-byte source separation

## Source research

- `research/nmi-root-gpt56sol` @ `e3816459edde22570849320b3dd9ad1081ed1c2d` (`research/nmi-root-contract.md`): bounded architectural NMI-root behavior; PARTIAL outside the tested reference scope.
- `research/nmi-root-fetch-provenance-gpt56sol` @ `6b22b7ebdf796f4032ca3c76534b868602f6917a` (`research/nmi-root-fetch-provenance.md`): VALIDATED bounded composition of NMI transfer, progress to first root fetch and source-bound PIF backing.
- Exact reference revision from `refs.lock.toml`: ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.
- Validated exact-pin research Actions: run `37970271648`, job `113954819130`, SUCCESS. Result JSON SHA-256 `35e17aac669eb7efdab166e78d214efc98c0c7289864e1f6fb2ceab0b952185f`; independent chronology-model payload SHA-256 `2c15ad692cd6927e146c2ab306c47f7158c418d2a52b1d0356a91cd4198cb900`.
- Exact source guards retained by that research: CPU `65cd30ce6e04a8799f6c50f07cc8dec13e55122bd8d5fea23e99e3e6734214f1`; exceptions `e24b2877fb5d629ca3f10f64dba9a612babb879c53ed142b42557920f216ffa7`; PIF IO `9bc87b9353a5b9c52f1b4b609aba4858e4a257f4a82d7007aee908a7faa2b86c`; SI IO `6b63ba45c11d9242794aa211a8ee17ee742a4d8f348486a7a0c25382fca411ca`.
- Canonical ADR-0103 / `exception_pif` was integrated while this lane was validating. It is complementary, not a substitute: ADR-0103 authenticates one BEV=1 general-vector PIF-backed fetch, whereas this integration keeps reset/NMI architectural transfer, NMI deassertion/progress, actual root-fetch occurrence and source-bound root bytes independently represented.

## Reproduced evidence against current integration work

The validated reference result was rechecked before adoption rather than treating the research branch as authority:

- a real first NMI instruction boundary can set PC to `0xffffffffbfc00000` while leaving NMI pending and performing zero root fetches / zero PIF reads;
- a second instruction boundary with NMI still pending can re-enter NMI, again performing zero root fetches and overwriting ErrorEPC with the root PC;
- after an explicit pending clear, the tested reference performs an uncached fetch at VA `0xffffffffbfc00000`, PA `0x1fc00000`; the positive PIF case has exactly one in-context offset-0 PIF backing read for the fetched Word;
- an SI busy-latch case can return the same instruction Word with no PIF backing read;
- PIF lockout can return a root Word with no normal PIF backing witness;
- a prior equal-valued PIF read is not usable as provenance for a later root occurrence.

The independent model rejects seven forged histories: root-transfer-only, persistent re-entry, stale equal foreign read, fetch while pending, equal SI-latch payload, wrong fetch context and wrong firmware offset.

Production branch validation before final canonical reconciliation used draft PR #27. Workflow `38153492755`, job `114511598471`, PASS: exact decoder pin, `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`, `cargo test --locked --workspace`, every retained synthetic contract and the independent fetch-summary oracle. Earlier CI failures were formatting and one test-helper shadowing error only; both were corrected before this green run.

## Adopted invariant

A reset/NMI root certificate must not collapse these facts:

1. **Architectural transfer identity**: an observed NMI boundary transferred architectural control to the reset/NMI root.
2. **Progress/root-fetch occurrence**: after the relevant pending condition is observed deasserted, a concrete uncached root fetch actually begins and completes in the same transfer context.
3. **Executable-byte source**: PIF origin is granted only to a matching in-context normalized PIF backing read for that fetch, with the exact supplied firmware identity. Root address, returned Word equality, a previous/latest equal read, or a transfer to the root is insufficient.

The production `root_provenance` replayer therefore authenticates the complete supplied finite source by SHA-256, requires contiguous ordinals and explicit transfer/fetch contexts, tracks NMI pending/deassertion separately, and retains root-fetch source as optional/UNKNOWN when the backing witness is missing or ambiguous. Report verification replays the complete source and exact-compares the receipt.

Broader report flags remain hard-false: producer lifecycle, root reachability completeness, root-set completeness, executable lifetime and native completeness.

## Rejected / superseded patches and shortcuts

- No research instrumentation, patched emulator code or branch-only workflow is a production dependency.
- No inference from `PC == 0xffffffffbfc00000` to instruction fetch/execution.
- No inference from equal fetched bits or equal PIF firmware bytes to source identity.
- No recycling of an earlier/foreign PIF read into a later root fetch.
- No adoption of pinned ares as hardware truth for NMI producer timing, deassertion mechanism, Status.SR behavior, repeated-reset policy or simultaneous-event priority.
- No weakening of solver OPEN/CLOSED obligations.
- ADR-0103's BEV=1 general-exception binding remains separate; this change does not generalize or reinterpret it.

## Files changed

- `crates/plaid-core/src/root_provenance.rs`
- `crates/plaid-core/src/lib.rs`
- this receipt
- canonical STATUS/NEXT documentation only if included in the final reconciled commit; ADR numbering is not consumed merely to restate the already-documented fail-closed root/provenance principle.

## Adversarial production regressions

The production unit matrix covers:

- correct transfer -> deassert -> root fetch -> exact PIF read;
- root transfer with no fetch;
- repeated/persistent NMI re-entry with no fetch;
- equal payload with no matching PIF read;
- stale earlier equal PIF read;
- wrong read context, wrong offset and multiple ambiguous reads;
- supplied-firmware mismatch;
- fetch while NMI remains pending;
- deleted/substituted source or firmware under complete-source receipts;
- reordered/noncontiguous history;
- forged/tampered report under full replay verification.

## Limitations and remaining proof obligations

This is a bounded compiler-time evidence consumer, not an N64 reset/NMI theorem. Still OPEN:

- complete reset-button/HW2/NMI producer and deassertion chronology;
- physical-hardware reset/NMI timing and simultaneous interrupt/NMI priority;
- reference disagreement over Status.SR and any unvalidated reset-state fields;
- all possible root source/device states beyond the authenticated observed history;
- proof that a fetched root instruction retired or progressed through a complete handler path;
- handler-byte cache/mapping residency and executable lifetime;
- save/restore/reset composition and cache-resident generations;
- complete exception/root census, mutation census and future-reachability proof;
- whole-ROM CLOSED and native-complete proof.

UNKNOWN remains UNKNOWN. This receipt must not be used as a waiver for any of those obligations.
