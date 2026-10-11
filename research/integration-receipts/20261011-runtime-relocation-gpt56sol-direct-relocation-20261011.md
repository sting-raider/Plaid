# Direct integration receipt: source-bound runtime relocation generations

Date: 2026-10-11  
Worker: `gpt56sol-direct-relocation-20261011`  
Cluster: bounded runtime MIPS HI16/LO16 relocation mutation receipts  
Initial base: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`  
Current reconciliation base: `60c5af29a9199ae207d487b4d791b13fb21ae708`

## Source research

- `research/runtime-relocation-provenance-gpt56sol` at `253acfae6542e8bb65a42ae041c1115c301f4dcf`
- `research/runtime-relocation-provenance.md`
- canonical primary review `research/relocation-primary-review.md`
- exact pinned N64Recomp `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` from `refs.lock.toml`
- original exact-pin Actions `38004080089` / `38004157335`

The primary review is authoritative about the research model's limits: its Python
`strict_receipt` accepted a changed relocation event ID, an arbitrary mutually
matching output-generation label, and a boolean sequence value. Those behaviors
were not imported.

## Reproduced evidence

The exact pinned N64Recomp research workflow was freshly rerun during integration:
Actions run `38004157335`, fresh job `114511803278`, SUCCESS. It checked out the
exact pin, verified the source guards, executed the exact-source-guarded relocation
experiment twice and uploaded deterministic receipts. Fresh artifact
`11706854647` has archive digest
`sha256:b7ee041fe33b85d760e9699ffbab70b6aee592c00e3caf119c65ed74469892eb`.

The retained research counterexample remains the key causal result: preimages
`0x3c081111` and `0x3c082222` at the same site both become `0x3c088041` for HI16
target `0x80408000`. Therefore site/kind/target/postimage equality cannot identify
the input executable generation. The research also retains 100,000/100,000
strict rejections for generation swaps and cross-load pairs, and preserves
same-value relocation operations as generation-advancing mutations.

The production regression suite reproduces those obligations directly: erased
preimages remain distinct load/storage generations, equal-payload reloads mint
new load/storage generations, same-value relocations mint a fresh output storage
generation, and cross-load HI16/LO16 pairing rejects. Malformed boolean ordinals,
deleted writes, forged preimages, wrong postimages, reordered ordinals, forged
reports and wrong source hashes all fail closed.

## Adopted invariant

`plaid-runtime-relocation-history-v0` is a SHA-bound finite replay. It derives all
identity-bearing generations from the authenticated chronology rather than taking
them as caller labels:

- each `load_begin` mints a fresh load generation;
- each captured `load_word` mints a fresh storage generation, including equal
  payload reloads;
- each relocation begins from the exact current captured site generation;
- its concrete write must preserve the upper instruction half and match the
  bounded N64Recomp-observed HI16 or LO16 immediate transform;
- every successful relocation write mints a fresh storage generation, including
  before/after-equal writes;
- relocation operation generations are assigned by completed replay order;
- HI16/LO16 bounded pair inspection requires the correct kinds, equal target,
  one load generation and HI-before-LO chronology, while explicitly leaving
  guest symbolic pairing/addend semantics uncertified.

Contiguous numeric ordinals and begin-ordinal contexts replace arbitrary event
IDs. Rust `u64` deserialization rejects the Python boolean/integer ambiguity.
The whole report is reconstructed during verification.

## Rejected or superseded patches

No research branch was merged mechanically. In particular, the research Python
model is retained only as evidence and is superseded for production replay by
internally minted numeric generations and source-bound contiguous contexts. No
attempt was made to promote the current descriptive `program::Relocation` tuple
or to clear solver `unverified_relocation` blockers.

## Files changed

- `crates/plaid-core/src/relocation_history.rs`
- `crates/plaid-core/src/lib.rs`
- `research/integration-receipts/20261011-runtime-relocation-gpt56sol-direct-relocation-20261011.md`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md` (ADR-0104 at this reconciliation base)

## Validation

Reproduction and successive production integrations were validated rather than
assuming the research branch remained applicable:

- initial Actions `38153396985`: failed only `cargo fmt --check`; formatter diff
  was applied exactly; no semantic test had run on that attempt;
- reconciled Actions `38153524189` / job `114511693983`: SUCCESS on then-current
  main, including format, strict workspace Clippy, full locked workspace tests,
  every retained synthetic contract and the independent fetch-summary oracle;
- exact pinned N64Recomp relocation rerun `38004157335` / job `114511803278`:
  SUCCESS as recorded above;
- after RSP IMEM egress landed, canonical Actions `38154119898` / job
  `114513439853` passed exact decoder pin, `cargo fmt --all -- --check`,
  `cargo clippy --locked --workspace --all-targets -- -D warnings`,
  `cargo test --locked --workspace`, every retained synthetic CLI/history/cache/
  TLB/RSP contract, and the independent fetch-summary assignment oracle;
- after canonical Rust checks became manual-only, a branch-local validation
  workflow (not part of the integration diff) reran the same complete gate on the
  clean candidate plus only that YAML helper: Actions `38154487412` / job
  `114514528712`, SUCCESS. Comparing the tested commit to its clean parent shows
  exactly one added file, `.github/workflows/direct-relocation-validation.yml`;
  the branch was then returned to the clean parent so the helper cannot land;
- canonical main subsequently added source-bound NMI `root_provenance` only. This
  relocation integration is rebuilt on `60c5af29a9199ae207d487b4d791b13fb21ae708`,
  preserving `root_provenance`, `sp_dma_egress`, and the manual-only CI policy.
  A fresh full gate is required before a MAIN-WRITE lease; its concrete run is
  recorded in the issue #4 closeout.

## Limitations

This verifier consumes a supplied finite successful load/relocation chronology.
It does not discover guest relocator code, prove the sensor saw every relocation
attempt or executable mutation, authenticate general relocation formats/addends,
or prove that two same-load HI16/LO16 operations are one guest symbolic pair.
`R_MIPS_26` is intentionally outside this bounded contract.

A valid relocation replay proves a storage transformation edge only. It does not
establish ultimate source ancestry, physical alias completeness, cache-visible
instruction identity, executable lifetime, reachability, exception/root coverage,
indirect-target closure or whole-ROM closure. All report certification/native
flags remain false.

## Remaining proof obligations

- authenticate a complete relocation/mutation producer stream for the declared
  execution scope;
- join load generations to causal ROM/CPU/RSP/decompression ancestry;
- establish relocation format/addend/pair semantics where needed from actual guest
  code or independently validated metadata;
- compose resulting backing generations with mapping aliases and cache-resident
  executable generations;
- prove executable lifetimes and reachability;
- only then connect certified relocation receipts to ProgramMap facts and consider
  discharging `unverified_relocation` for those exact facts;
- whole-ROM/native-complete remains OPEN.
