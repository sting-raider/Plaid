# Integration receipt: ordered SD/SDL/SDR mutation effects

Date: 2026-10-11

Worker: `gpt56sol-direct-64bit-store-20261011`

Base main inspected: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

Current reconciled main ancestor at this receipt revision: `31c10020665e8386656fd943acab111b5c7e1671`

Integration branch: `direct-integration/64bit-store-mutations-gpt56sol`

Validation PR: #11

## Source research

This integration consumes the bounded, validated semantics from:

- branch `research/64bit-store-mutation-gpt56`;
- `research/ares-64bit-store-mutation.md` (research commit `ad5a342e1b6d4336124808c70145c034202febea`);
- `spikes/025-ares-64bit-stores/`, finalized in research at `8b1e9d4ddefc1f650b27f8163ee2179b8e401366`;
- exact pinned-reference harness commit `c41dc462f55bf12a0fbdc15a68b0f138d34c899b`;
- issue #4 research closeout `6063448712`.

The relevant upstream reference is ares at the exact `refs.lock.toml` revision
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

## Reproduced evidence

Before adopting production code, the retained current-main independent model was
rechecked. It reports:

```text
PASS: decomposition widths/lane uniqueness and unaligned SDL+SDR pairs
sha256 768ff87e0f0690e427a5efad86af02dba7a0a4d56dabceff1adec66bdbfba03e
```

The exact pinned-reference GitHub Actions job was rerun on 2026-10-11
(run `37801439305`, attempt 2, job `114506561685`). It checked out ares at
`9408cb43d4948fc3ea6e152a307a34348df3fe04` and reproduced:

```text
PASS: 158 repeated pinned-ares SD/SDL/SDR cases
results_sha256=cf8f82bde400e23c0f2225ee55baaf727b7f09b87c2ca2489c2e295aed6c5f1e
```

The production implementation first went fully green at code head
`eb91b8122988fec1408124b13a64edf302b11daa` (Rust-checks run `38151850943`,
job `114506753689`). A semantic naming audit then renamed the backing mutation layer
from the potentially misleading `IdentityRdramBacking` to
`ObservedRdramBacking`, keeping physical sink identity explicitly supplied rather
than inferred. That code was fully green at `44201dcf444aa949835cd46b366d070df32ef167`
(run `38152080386`, job `114507422712`).

Canonical main advanced repeatedly during serialized integration. This branch was
explicitly reconciled, rather than mechanically merging stale research state:

- exception-root main `539ff0ce72a98b296a8a28135fda6eab90a2f6ac` via feature merge
  `585fbf8e6c32c92e8983b5664976efefc2c1ed00`, with full canonical run
  `38152284430` / job `114508021402` passing;
- source-bound TLBWI-generation main `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`
  via feature merge `dadd67c25a3a18e7fd9f24c53bd22411da182d9f`, with full canonical run
  `38153237293` / job `114510836908` passing;
- bounded COP1 store-normalization main `dd3f627d2c27f84611439ec1888ec4e3015e6bd2`
  via feature merge `8c040b6ce60f00d6a60fc4f725bd137b5b503e85`, with full canonical run
  `38153419139` / job `114511381400` passing; the receipt-bearing follow-up head
  `3af37a3012d30a47c26be9f93607b1743e1be1b1` also passed the complete gate in
  run `38153571031` / job `114511833977`;
- BEV1 exact PIF-root backing-provenance main
  `9154b30b12026c8c122f654d7fe90f0f67968dce` via feature merge
  `5663731c0937492940549f9aad0c390897881704` and receipt-bearing follow-up
  `b8ceb14488739b2fe7bcf1e37f74a6e8374c8495`;
- source-bound RSP IMEM reverse-SP-DMA egress main
  `31c10020665e8386656fd943acab111b5c7e1671` via feature merge
  `f7cbaf9a1f6fe1f4bed7e271505c49367d42e187`. The receipt-bearing head produced by
  this update must pass the complete canonical gate before any MAIN-WRITE lease or
  merge.

The validated reconciled code has passed all of:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- `python scripts/test_cli.py`;
- canonical CPU-copy, XORI, CPU-SP producer, RSP/CPU IMEM composition, XORI
  cache-visibility, PageMask cache-remap, PI cache-visibility, SP-DMA DMEM-ingress,
  RSP-store-isolation, EntryHi cache-reactivation and TLBR cache-reactivation
  synthetic contracts;
- the independent fetch-summary assignment oracle.

At each reconciliation, the live comparison remained bounded to this integration's
three paths: one `lib.rs` export, the new `store_mutation.rs`, and this receipt. The
landed exception, PIF-root, TLBWI, COP1 and RSP IMEM-egress production state is
preserved.

One pre-green regression expectation was corrected during validation: the first
little-endian `SDR` offset-1 Word subwrite for source `0x1122334455667788` is
`0x22334455` (`source >> 24`), not `0x44556677`. The production decomposition was
unchanged; the failing assertion was the erroneous test literal.

## Adopted invariant

Plaid now has a production source-contract rechecker for the validated ares
`SD`/`SDL`/`SDR` behavior. The abstraction deliberately keeps these identities
separate:

1. one architectural store attempt (`operation_event`);
2. each ordered concrete subwrite (`event` + contiguous `sequence`);
3. the handler address/width/value of that concrete subwrite;
4. the separately observed physical sink;
5. the immediate mutation layer (`dcache_resident` versus
   `observed_rdram_backing`).

For completed receipts, the rechecker requires the exact validated decomposition
for operation, endian mode and low address bits. It requires exact subwrite values,
non-reused event identities, and the cache/backing distinction. Rejected-before-
mutation attempts must carry no effects. The exact ares revision and independent
model hash are part of the source contract.

The physical sink is intentionally not derived from the guest address. Equality of
addresses or values is not provenance, and guest translation/endian/cache context
remains a separate obligation.

## Adversarial regressions

Focused tests cover:

- all eight `SDL`/`SDR` offsets in both modeled endian contexts;
- aligned `SD` and rejection of completed misaligned `SD`;
- known three-subwrite decompositions;
- cache-resident/backing-layer confusion;
- explicit physical sink identity not inferred from the guest address;
- equal-value subwrites retaining distinct event identities;
- deleted, reordered and forged subwrites;
- rejected attempts carrying forged mutation effects;
- wrong source revision/model identity;
- overflowing physical sink spans.

These are deliberately causal/identity tests rather than final-state equality tests.

## Rejected or superseded patches

No research branch was merged mechanically. The research instrumentation and
branch-only workflow remain research evidence, not production dependencies.

The initial research sub-hypothesis that a later `SDL`/`SDR` subwrite could fault
after an earlier one committed was rejected by the validated source/harness for the
stable-translation scope: the subwrites remain within one aligned 8-byte window,
and the tested invalid-TLB path fails before RDRAM/D-cache mutation. Production code
does not encode a partial-prefix-on-fault rule.

The existing aligned `ObservedWordStore { value: u32 }` path was not widened or
silently reinterpreted as these receipts. Doing that would erase architectural
operation identity and ordered subwrites and would falsely imply that old sensors
covered mutation classes they did not observe.

## Files changed

- `crates/plaid-core/src/store_mutation.rs` — bounded production receipt types,
  source-contract validation and adversarial tests;
- `crates/plaid-core/src/lib.rs` — exports the production module while preserving
  the landed exception-root, PIF-root, TLB-history, COP1-mutation and RSP
  IMEM-egress APIs;
- this receipt.

No `progress.json` milestone changed. `docs/STATUS.md`, `docs/NEXT.md` and
`docs/DECISIONS.md` are intentionally unchanged because this integration adds a
validated primitive without changing Plaid's high-level closure status, priority
ordering, or native-complete claim.

## Limitations and remaining proof obligations

This integration is **not** a whole-ROM mutation census, hardware equivalence
certificate, backing-provenance proof, or executable-lifetime proof. In particular,
it does not close:

- `SB`, `SH`, `SWL`, `SWR`, `SCD`, RSP or other remaining CPU/out-of-band mutation
  classes; the separate landed COP1 SWC1/SDC1 normalizer and RSP reverse-DMA egress
  lineage are complementary and do not make the global census complete;
- completeness of the sensor that would produce these receipts;
- source-byte ancestry of the stored payload;
- arbitrary TLB histories, aliases, PageMask/ASID/context generations or legal
  reverse-endian user/TLB execution;
- device-side error semantics outside the validated bounded path;
- D-cache writeback joining from a resident mutation to backing ancestry;
- I-cache residency/stale executable visibility;
- DMA/copy/decompression/relocation composition;
- executable lifetime closure or whole-ROM CLOSED status.

UNKNOWN remains UNKNOWN for all of those obligations. This primitive must not be
used to waive them or to promote native completeness.
