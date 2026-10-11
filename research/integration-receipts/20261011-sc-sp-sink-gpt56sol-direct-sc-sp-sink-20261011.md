# Direct integration receipt: completed Word SC -> SP mutation normalization

Date: 2026-10-11
Worker: `gpt56sol-direct-sc-sp-sink-20261011`
Cluster: completed VR4300 Word `SC` -> CPU-visible SP DMEM/IMEM mutation normalization
Initial claim base: `31c10020665e8386656fd943acab111b5c7e1671`
Final reproduced canonical parent before this receipt: `0e0e999b626dbda3f47cfd6aa89673618ae20350`
Integration branch: `direct-integration/sc-sp-sink-gpt56sol-direct-sc-sp-sink-20261011`

## Source research

- `research/cpu-sc-sp-sink-gpt56sol` at `47db2b2baa9a640111085b68a722fe316ed5e43e`
- `research/cpu-sc-sp-sink.md`
- `spikes/045-ares-cpu-sc-sp-sink`
- exact pinned ares revision from `refs.lock.toml`: `9408cb43d4948fc3ea6e152a307a34348df3fe04`
- exact pinned Gopher64 revision from `refs.lock.toml`: `e96debac941a26ba4961e5145056c0821d3a56f7`
- retained research Actions runs `37918954587` and `37919397607`

The research branch is evidence only. No research implementation or patched emulator code was mechanically merged.

## Reproduced evidence

The exact-pinned research fixture was rerun during integration as Actions run `37919397607`, attempt 2, job `114513979438`, and passed against pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The reproduced trace SHA-256 is:

`311ece0fd647d9c4bfc6cb1e5a9558c938bf3ef5d51810ae4ca752a81a9b5bcb`

The reproduced summarized-result SHA-256 is:

`454ea55a300bee86480f55d6152cdd2970495e60121eb0b93e3d8a8ff0f4e6d2`

The bounded exact-reference matrix reproduced:

- four successful aligned Word `SC` attempts, covering DMEM and IMEM and both changed-value and same-value destinations, each reaching exactly one measured CPU-origin SP Word sink;
- two no-reservation `SC` attempts failing without an SP sink;
- two real-`LL` then misaligned `SC` attempts taking AddressStore exception 5 without an SP sink;
- changed-value successful writes carrying `0x112233bb`;
- same-value successful writes carrying `0x11223344` and remaining writer events even though destination bytes did not change;
- one equal-address/equal-value direct CPU-write decoy outside the decoded `SC` context, which must not inherit `SC` provenance;
- five forged histories rejected: dropping a same-value successful writer, fabricating a failed sink, stealing the equal-value decoy, erasing the `SC` opcode context, and erasing the reservation-context distinction used by the research observer.

The exact pinned Gopher64 source remains corroborating evidence for `SC` being conditional and for successful stores reaching memory, but its reservation-lifetime structure is not imported as hardware truth. Pinned references differ in reservation details, so production deliberately does not predict `SC` success or define reservation lifetime here.

## Adopted invariant

Production now exposes `plaid_core::cpu_sp_conditional::verify_sc_sp_effect` as a bounded, effect-driven normalizer.

A Word `SC` instruction is only an attempted conditional store. The verifier creates a mutation witness only when an independently observed completed CPU-origin SP Word sink is causally bound to the exact captured execution context.

For an accepted completed sink the verifier rederives and checks:

1. the instruction is exactly Word `SC` (opcode `0x38`);
2. a nonzero instruction-context identity is present;
3. sink `context_id` and source PC match that exact instruction context;
4. the effective virtual destination comes from the captured pre-instruction base GPR plus the sign-extended immediate;
5. the destination is Word-aligned;
6. the bounded integration scope is the uncached direct segment (`KSEG1`), never an inferred cached/TLB alias;
7. the independently observed physical sink exactly matches the direct mapping;
8. the physical sink is within the 8 KiB CPU-visible SP DMEM/IMEM window and yields the exact bank/offset;
9. the completed sink payload equals the low 32 bits of the captured pre-instruction source GPR.

The witness preserves the full pre-instruction source GPR in addition to the stored Word. This matters when `base == rt`: `SC` overwrites `rt` with its success result after the attempted store, so post-instruction register equality is not a trustworthy source witness.

`effect = None` creates no writer. This represents a failed or faulting attempt only when lower-effect observation completeness is established independently; the absence of an effect is not itself a sensor-completeness proof.

A completed same-value sink still creates a witness. No before/after inequality participates in writer identity.

## Adversarial production regressions

`cpu_sp_conditional` tests cover:

- successful DMEM and IMEM completed sinks;
- same-value successful sink retained as a writer;
- absent completed sink creating no writer;
- equal-value decoy from another instruction context rejected;
- non-`SC` opcode rejected even with a plausible completed sink;
- wrong source payload rejected;
- forged virtual/physical mapping rejected;
- physical sinks outside DMEM/IMEM rejected;
- cached-direct claims rejected rather than silently translated into this uncached scope;
- misaligned completed claims rejected;
- a misaligned attempt with no observed completed effect still creating no writer;
- `base == source` deriving both address and payload from pre-instruction state;
- zero context identities and wrong-PC joins rejected;
- zero effect ordinals rejected by the production verifier.

## Validation results

Fresh exact-pinned research reproduction:

- Actions run `37919397607`, attempt 2, job `114513979438`: **PASS**;
- trace SHA-256 `311ece0fd647d9c4bfc6cb1e5a9558c938bf3ef5d51810ae4ca752a81a9b5bcb`;
- result SHA-256 `454ea55a300bee86480f55d6152cdd2970495e60121eb0b93e3d8a8ff0f4e6d2`.

Current-main-derived production validation:

- canonical parent: `0e0e999b626dbda3f47cfd6aa89673618ae20350`;
- reconciled validation head: `e29d36475b3f456580b93708d1134974320eafad`;
- branch-only canonical-equivalent run `38155135900`, job `114516444269`: **PASS**;
- exact decoder dependency pin: PASS;
- `cargo fmt --all -- --check`: PASS;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS;
- focused `cargo test --locked -p plaid-core cpu_sp_conditional -- --nocapture`: PASS;
- `cargo test --locked --workspace`: PASS;
- `python scripts/test_cli.py`: PASS;
- retained synthetic CPU-copy/XORI/CPU-SP/RSP/cache/PageMask/PI/SP-DMA/RSP-store/EntryHi/TLBR contracts: PASS;
- independent fetch-summary assignment oracle: PASS.

The temporary `.github/workflows/direct-sc-sp-validation.yml` exists only on the integration branch because canonical `.github/workflows/rust.yml` is intentionally manual-only. The temporary workflow duplicates the canonical checks and adds the focused `cpu_sp_conditional` command. It is validation scaffolding and must not be included in the canonical production commit.

## Rejected and superseded work

- No research branch was merged mechanically.
- SCD is explicitly excluded. The validated SCD research retains a structural reference disagreement and is not generalized from the Word `SC` result.
- General LL/SC reservation creation, invalidation, address matching, success prediction and lifetime were rejected from this production abstraction. The exact reference behavior is evidence for the bounded fixture, not automatically hardware truth.
- Cached/TLB/reverse-endian alias handling was rejected from this bounded direct-KSEG1 verifier rather than guessed from effective address or equal payload.
- Early integration heads that failed only rustfmt or a test-helper name-shadowing compile error were corrected and discarded before the current-main full green run.
- A later issue #4 claimant, `gpt56sol-direct-sc-sp-writer-20261011-b2`, selected the same research cluster after this worker's earlier claim. Its work is review/reproduction evidence only; the duplicate must not be independently landed.

## Permanent files changed by this cluster

- `crates/plaid-core/src/cpu_sp_conditional.rs`
- `crates/plaid-core/src/lib.rs` (one module export while preserving all current-main modules)
- `research/integration-receipts/20261011-sc-sp-sink-gpt56sol-direct-sc-sp-sink-20261011.md`

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md`, and `progress.json` are intentionally unchanged. This bounded mutation normalizer improves reusable evidence coverage but does not discharge a canonical whole-ROM, executable-lifetime, root-census, solver, or native-complete milestone.

## Limitations and remaining proof obligations

This primitive does **not** prove:

- completeness of the instruction-context or completed-SP-effect observer;
- LL/SC reservation creation, invalidation, address matching, lifetime or success semantics;
- SCD semantics;
- SB/SH, SWL/SWR, SD/SDL/SDR, COP1 or other CPU mutation families;
- cached, TLB-mapped, reverse-endian or other aliases of SP memory;
- translation/mapping provenance outside its explicit direct-KSEG1 scope;
- RSP-origin scalar/vector writer ancestry;
- SP-DMA ingress or egress ancestry;
- cache writeback ancestry;
- complete CPU/RSP mutation census;
- downstream IMEM executable fetch identity or cache-visible executable state;
- executable lifetime closure;
- save/restore/reset/NMI chronology composition;
- complete exception/interrupt/root census;
- whole-ROM executable-universe closure;
- native completeness.

UNKNOWN remains UNKNOWN when the lower completed-effect observation is absent without an independent completeness guarantee, when a claimed completed effect cannot be joined to the exact instruction context, or when the destination lies outside the bounded direct-KSEG1 SP scope.

## Codex handoff

Treat `verify_sc_sp_effect` as a sink-level compiler-time normalization boundary, not an LL/SC emulator. A valid witness says that an independently observed completed CPU-origin SP Word sink is consistent with and causally bound to one captured Word `SC` execution context. It does not explain why the reservation succeeded, prove that all attempted stores were observed, or establish downstream executable lifetime.

Do not infer an `SC` writer from opcode presence, final `rt`, `llbit`, matching destination bytes, matching address/value, or a finite trace. Same-value completed sinks remain distinct writer occurrences. Failed/faulting attempts mint no storage writer only when that absence comes from an independently complete lower-effect source. SCD and reservation-policy semantics remain separate OPEN work.