# Direct integration receipt: cached exception-root generation

Date: 2026-10-11  
Worker: `gpt56sol-direct-exception-generation-20261011`  
Cluster: source-bound cached exception-root executable-generation replay

## Source research

- `research/exception-root-generation-gpt56sol` at
  `50c160680c936c1801fabe32907ca45304d3d313`.
- `research/exception-root-generation.md`.
- `experiments/exception_root_generation.py` from that research branch.
- `spikes/044-ares-exception-root-generation/*` from that research branch.
- Exact pinned ares revision
  `9408cb43d4948fc3ea6e152a307a34348df3fe04` from `refs.lock.toml`.
- Existing production root derivation from ADR-0101 / `exception_roots.rs`.

The research branch was treated as evidence only. None of its reference
implementation code, branch workflow scaffolding, or production guesses was
mechanically merged.

## Current-main reproduction

The integration branch began from main
`539ff0ce72a98b296a8a28135fda6eab90a2f6ac`. Before production code was adopted,
a fresh current-main-ancestry reproduction was built and executed in GitHub
Actions run `38152588083`, job `114508913891`.

The adversarial generation model ran twice byte-identically and reproduced the
research receipt:

`fb73e817fb097ca91caa100d5d5e179ec3b736df3785776f86618e6aa2000c8e`

A fresh checkout of exact pinned ares then built the exception-root fixture with
its guarded source blobs and reproduced the dynamic evidence receipt:

`f794aabf9f70f9755e719138ed13d70d0a26334dab01d5a5702ca6ebbb2710cb`

The executable result again showed the same BEV=0 general vector
`0xffffffff80000180` transferring first to stale resident handler generation A
after backing RDRAM had already advanced to generation B, then to generation B
only after a guest I-cache invalidate/refill.

After main advanced, the integration branch was explicitly reconciled with
`bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` (ADR-0102 / source-bound TLBWI
operation generations) before canonical documentation was updated.

BEV1/PIF integration advanced canonical main to
`9154b30b12026c8c122f654d7fe90f0f67968dce` and claimed ADR-0103. The cached-root
integration was then rebuilt on that exact tree, preserving `exception_pif` and the
BEV1 docs; this decision was renumbered ADR-0104.

## Adopted invariant

For the validated bounded scope, architectural exception-root identity and the
executable word generation fetched at that root are separate facts.

The production replay accepts an externally SHA-bound finite chronology for only
the exact validated cached root scope: BEV=0, general exception, EXL clear,
32-bit kernel context, identity RDRAM physical word `0x180` corresponding to
`0xffffffff80000180`.

- Every observed successful backing Word write has its own ordinal generation,
  even when its payload equals an earlier write.
- A captured I-cache fill receives its own ordinal identity and binds to the
  then-current observed backing-write generation.
- A later backing write does not relabel or refresh an already resident line.
- An observed invalidate removes that resident witness; a later fill may bind a
  new resident generation to a later backing writer.
- A root fetch with a captured resident generation must match that resident word
  and reports both the resident source and current backing generation separately.
- A root fetch without captured resident/fill evidence reports `Unknown` origin.
  Current backing bytes, equal payloads, the numeric vector, or the fetch value
  cannot manufacture the missing causal edge.
- Source event ordinals must be complete and contiguous within the supplied
  finite source. Deleted/reordered events, wrong physical words, fill/fetch
  payload forgeries, unsupported root state and source-hash tampering fail closed.
- `verify_exception_root_generation_report` reconstructs the complete report from
  the original source and expected source hash.

The report keeps reachability, mutation coverage, executable lifetime and native
completeness explicitly false.

## Rejected or superseded approaches

- Rejected: identify a cached handler by `(exception kind, vector PC, current
  backing bytes)`. The exact fixture falsifies this after backing rewrite.
- Rejected: collapse equal-valued writes/fills into one provenance generation.
  Same-value replacement is an explicit adversarial regression.
- Rejected: treat a newer resident identifier as proof of newer backing. The
  refill-before-write regression retains the older backing writer.
- Rejected: infer a root origin from current RDRAM when the resident/fill witness
  is absent. The production result remains `Unknown`.
- Rejected: generalize the bounded fixture into a universal cache, alias, TLB,
  reset/restore or exception-root model.
- Superseded: the temporary current-main reproduction model, spike-055 fixture,
  runner and branch-only workflow. They were deleted after their exact receipts
  were recorded; the validated source research remains the durable reference.

## Production files changed

- `crates/plaid-core/src/exception_root_generation.rs`
- `crates/plaid-core/src/lib.rs`
- `docs/STATUS.md`
- `docs/NEXT.md`
- `docs/DECISIONS.md` (ADR-0104)
- this receipt

No `docs/progress.json` milestone changed.

## Tests and results

Focused production regressions cover:

1. stale resident generation after changed backing;
2. invalidate/refill after the write;
3. refill before the write;
4. same-value backing rewrite without resident relabeling;
5. same-value rewrite followed by refill to the new generation;
6. missing resident evidence staying `Unknown`;
7. deleted/reordered ordinals;
8. fill and root-fetch payload forgery;
9. wrong physical/root scope;
10. complete source-hash and report-replay binding.

Pre-documentation merged-view canonical validation against main
`bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` passed in PR #26 run
`38152961040`, job `114510026306`: exact decoder pin, `cargo fmt --all -- --check`,
`cargo clippy --locked --workspace --all-targets -- -D warnings`,
`cargo test --locked --workspace`, synthetic CLI checks, retained CPU-copy/XORI/
SP/RSP/cache/TLB contracts, and the independent fetch-summary oracle all passed.

A final documented-head PR validation is required before the MAIN-WRITE lease and
will be recorded in issue #4 closeout together with the tested head.

## Limitations

This integration consumes a finite supplied event history. The external SHA binds
that source but does not prove the sensor observed every architecturally relevant
operation. Backing-write ordinals establish local storage generations, not
ultimate ROM/DMA/CPU producer ancestry.

The accepted scope is one cached Word at the BEV=0 general vector under the exact
validated 32-bit identity-RDRAM scenario. It does not establish broader cache
operation semantics, cache indexing, aliases/TLB mappings, PageMask/ASID/global
context, BEV=1/PIF backing, refill/XTLB vectors, interrupt/watch/cache-error roots,
reset/NMI, save/restore behavior, the complete handler span, or hardware timing
truth. Pinned ares is behavioral evidence, not hardware authority.

## Remaining proof obligations

Whole-ROM closure remains OPEN. In particular Plaid still needs authenticated
exception classification and BEV/EXL/address-mode chronology; complete execution
root enumeration and reachability; complete handler byte provenance; all relevant
backing/cache/mapping mutations and aliases; cache residency and executable
lifetimes across restore/reset; interrupt/reset/NMI and other root classes; RSP
executable identity; indirect-target closure; and a complete mutation census.

Nothing in this receipt permits a solver waiver or a native-complete claim.
