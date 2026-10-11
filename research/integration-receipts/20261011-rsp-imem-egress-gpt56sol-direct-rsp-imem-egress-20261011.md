# Direct integration receipt: RSP IMEM reverse-DMA egress lineage

Date: 2026-10-11

Worker: `gpt56sol-direct-rsp-imem-egress-20261011`

Initial canonical base: `6b53a15c4c6eaadc8e0d002dd6818c600ebf2a7d`

First reconciled canonical base: `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`

Final tested canonical base before lease contention: `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`

Integration branch: `direct-integration/rsp-imem-egress-gpt56sol-direct-rsp-imem-egress-20261011`

## Source research

Primary evidence is the completed research branch
`research/rsp-imem-dma-egress-gpt56sol`:

- executable/source-guard head `72a7f6353be1463144d9638b1513ab046e01d266`;
- durable-note head `5960b4d1dabdbdb60b66ec4066f792204f3e3bc8`;
- `research/rsp-imem-dma-egress.md`;
- `spikes/047-ares-rsp-imem-dma-egress/`;
- issue #4 closeout `6079601651`.

Exact reference revisions remain the repository pins:

- ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
- Gopher64 `e96debac941a26ba4961e5145056c0821d3a56f7`;
- Mupen64Plus core `ba95bab92a76744753bfe61470823a4937850ab0`.

No reference implementation source is copied into Plaid production.

## Reproduced evidence

The exact research job was freshly rerun during integration as Actions run
`37920899821`, latest job `114506394364`, and completed successfully. The rerun
fetched the exact ares/Gopher pins, passed exact-source guards, rebuilt and ran
the controlled reference fixture, rejected all nine deliberate forged histories,
and uploaded fresh evidence artifact `11706757123` with ZIP SHA-256
`73ee9dd7728b9d2c975e49522d5a701ca0d20257e6da32c0a20be4b1b24ca242`.
The reproduced semantic outputs match the prior closeout exactly:

- 14 ordered events;
- 10 completed CPU-visible IMEM Word sinks;
- 4 completed IMEM-source reverse-SP-DMA RDRAM Dual sinks;
- all 32 exported bytes attributed to captured CPU-visible IMEM writers;
- successful same-value writer retained as sequence 1;
- equal-payload decoy present without stealing source identity;
- `0xff8 -> 0x000` offset wrap retains source region 1;
- all 9 measured history forgeries rejected;
- baseline/sensor-disabled/enabled/repeated state neutrality holds;
- event SHA-256 `6d7b5637b7c2e3c0180fbd9828cc95d8d087026b4877a60818f0ba604b0c8ce5`;
- bounded egress SHA-256 `c2cd1728c8d35065c95eb223c0e0d2fffdc5ac78d895e4bf19051680246fd795`;
- results SHA-256 `65032064adabbd8d5b0f0c3593021ddb465bb5bfa42782c19ddfbc372b3c8eb8`;
- enabled trace SHA-256 `f7515a50835b69df0edcfd12b44b2da0011507e2572ac40bf203a12f1a282f89`.

The production implementation was independently exercised on current-main code
through PR #15. Actions run `38151825940` checked the synthetic merge commit
`8b4dcae4d1f0d1990e3c35e4367305b83141ca54`, which reconciled the integration
head with canonical `539ff0ce72a98b296a8a28135fda6eab90a2f6ac`. It passed:

- `cargo fmt --all -- --check`;
- `cargo clippy --locked --workspace --all-targets -- -D warnings`;
- `cargo test --locked --workspace`;
- synthetic CLI checks;
- every existing CPU-copy/XORI/CPU-SP/RSP-composition/cache/SP-ingress/store/TLB
  regression gate;
- the independent fetch-summary realizability oracle.

The first PR run failed only the formatting gate; the exact formatter diff was
applied before the successful run. No semantic test was waived or skipped in the
successful run.

Canonical main then advanced through the exception-root and TLBWI integrations.
Rather than merge the stale PR view, the branch was reconciled onto canonical
`bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5` with two-parent commit
`835ace29cb77be76f692904003b5d7d47387035b`. Its tree is based on the canonical
TLBWI main tree and changes exactly four paths relative to that base: the module
export, the new egress module, its tests and this receipt. Post-reconciliation
Actions run `38153104173`, job `114510442838`, completed successfully with the
exact decoder pin, formatting, strict workspace Clippy, full locked workspace
tests, every retained synthetic contract and the independent fetch-summary
assignment oracle green.

## Adopted invariant

Production now has a bounded, source-bound replay API for captured
CPU-visible RSP IMEM writer generations followed by completed descriptor-selected
reverse SP-DMA RDRAM sinks.

For each captured full-Word IMEM sink, every written byte receives the sink's
ordered event ordinal as its current writer generation, even when the payload is
unchanged. For each completed eight-byte reverse-DMA sink, the source bank must
be IMEM (`region == dma_region == 1`), the captured source offset must equal the
live descriptor's aligned 12-bit source offset, and the completed RDRAM sink must
match the captured descriptor destination. The bank identity is kept separate
from the wrapping 12-bit offset, so a later source offset `0x000` is still IMEM
when the descriptor bank remains IMEM.

Known current IMEM bytes are checked against the completed DMA payload only as an
integrity condition after source location is established. Payload equality never
selects a source. A source byte with no captured IMEM writer remains `None` in the
receipt instead of being inferred from the DMA value. The report is re-created
from the externally authenticated complete source for verification.

## Rejected / superseded approaches

The research Python replay and branch-only workflow are evidence, not production
code, and were not merged mechanically. The production API uses original Rust
and a new typed source format rather than importing the fixture-specific state,
initial-byte generator, fixed destination windows, or research observer schema.

The following shortcuts are explicitly rejected:

- infer ancestry from equal payloads or a nearest equal IMEM span;
- treat final IMEM/RDRAM snapshots as writer identity;
- infer a bank switch merely because a 12-bit source offset wraps;
- manufacture a writer for an uncaptured source byte from the completed DMA
  payload;
- treat descriptor count/skip values as a complete DMA request/lifecycle proof;
- treat this bounded replay as a complete IMEM mutation census or executable
  lifetime certificate.

The existing forward RDRAM -> SP ingress consumer in `sp_history.rs` is retained
unchanged. This integration adds the reverse direction rather than generalizing
that v3 boot format without evidence.

## Files changed

Production / tests:

- `crates/plaid-core/src/sp_dma_egress.rs`;
- `crates/plaid-core/src/lib.rs`;
- `crates/plaid-core/tests/sp_dma_egress.rs`.

Receipt:

- this file.

`docs/STATUS.md`, `docs/NEXT.md`, `docs/DECISIONS.md` and `progress.json` are
intentionally unchanged by this bounded integration. The production evidence
surface grows, but no project milestone, closure obligation or architectural
waiver changes: complete mutation coverage, executable lifetime, whole-ROM closure
and native completeness all remain OPEN. This receipt records the narrower
production contract without manufacturing a broader canonical-state transition.

No solver, ProgramMap, progress-map, native backend, emulator runtime, or reference
source file is changed.

## Focused adversarial regressions

The Rust regressions cover:

1. repeated same-value IMEM Word writes advancing writer identity;
2. newer equal-payload IMEM decoys not stealing a descriptor-selected source;
3. IMEM bank preservation across `0xff8` followed by `0x000` source offsets;
4. partial source coverage retaining four UNKNOWN byte writers rather than
   reverse-inferencing them from the sink value;
5. known-source payload mismatch rejection;
6. wrong source offset versus descriptor, wrong bank, wrong destination and
   noncontiguous chronology rejection;
7. unknown-field/schema rejection;
8. complete-source SHA deletion resistance for a same-value writer;
9. complete report rechecking rejecting forged byte ancestry and a forged
   `native_complete` flag.

## Limitations

This is a finite compiler-time evidence consumer, not a hardware oracle. The
fresh exact fixture corroborates the source contract for the pinned reference
path, but emulator agreement is not N64 hardware truth.

The new source protocol does not establish that every IMEM writer or every SP DMA
was captured. Its SHA-256 must come from a separately trusted complete-source
receipt for the declared scope. Initial IMEM bytes are UNKNOWN unless a captured
writer establishes them. The API currently accepts only the controlled full-Word
CPU-visible IMEM writer class and eight-byte IMEM-source DMA sink class; other
writer classes remain outside this protocol rather than being guessed.

The underlying research source selection is tied to the exact guarded reference
sequence in which the live descriptor-selected IMEM Dual read immediately
precedes the completed RDRAM Dual sink. The production replay does not claim a
separate physical source-read event, arbitrary asynchronous interleavings, FIFO
request identity, cancellation/failure policy, save/restore/reset chronology, or
concurrent CPU/RSP mutation safety.

## Remaining proof obligations

Whole-ROM closure remains OPEN. At minimum Plaid still needs:

- a complete IMEM mutation census across CPU, SP DMA, host/reset/restore and any
  other relevant producer paths;
- authenticated SP DMA request/promotion/completion identity where lifecycle
  matters;
- composition of each captured IMEM writer with ultimate storage/dataflow
  ancestry rather than stopping at the local writer event;
- executable consumption and lifetime composition for exported/imported bytes;
- cache/TLB/backing joins for RDRAM destinations when they later become
  executable;
- hardware-oriented evidence or an explicit reference-scoped policy for
  semantics that cannot be established from emulator agreement;
- whole-ROM roots, indirect-target, overlay/relocation, mutation and RSP identity
  certificates.

No CLOSED/native-complete flag is changed by this integration.
