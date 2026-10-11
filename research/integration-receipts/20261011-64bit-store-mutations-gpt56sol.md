# Integration receipt: ordered SD/SDL/SDR mutation effects

Date: 2026-10-11

Worker: `gpt56sol-direct-64bit-store-20261011`

Base main inspected: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

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

The exact pinned-reference GitHub Actions job was then rerun on 2026-10-11
(run `37801439305`, attempt 2, job `114506561685`). It checked out ares at
`9408cb43d4948fc3ea6e152a307a34348df3fe04` and reproduced:

```text
PASS: 158 repeated pinned-ares SD/SDL/SDR cases
results_sha256=cf8f82bde400e23c0f2225ee55baaf727b7f09b87c2ca2489c2e295aed6c5f1e
```

The production branch was validated by Rust-checks run `38151850943`, job
`114506753689`, at code head `eb91b8122988fec1408124b13a64edf302b11daa`.
The following all passed:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- `python scripts/test_cli.py`;
- canonical CPU-copy, XORI, CPU-SP producer, RSP/CPU IMEM composition, XORI
  cache-visibility, PageMask cache-remap, PI cache-visibility, SP-DMA DMEM-ingress,
  RSP-store-isolation, EntryHi cache-reactivation and TLBR cache-reactivation
  synthetic contracts;
- the independent fetch-summary assignment oracle.

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
   `identity_rdram_backing`).

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
- `crates/plaid-core/src/lib.rs` — exports the production module;
- this receipt.

No `progress.json` milestone changed. `docs/STATUS.md`, `docs/NEXT.md` and
`docs/DECISIONS.md` are intentionally unchanged because this integration adds a
validated primitive without changing Plaid's high-level closure status, priority
ordering, or native-complete claim.

## Limitations and remaining proof obligations

This integration is **not** a whole-ROM mutation census, hardware equivalence
certificate, backing-provenance proof, or executable-lifetime proof. In particular,
it does not close:

- `SB`, `SH`, `SWL`, `SWR`, `SCD`, COP1 or RSP store mutation classes;
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
