# Direct integration receipt: PageMask-aware TLB mapped uncached fetch provenance

Date: 2026-10-11

Worker: `gpt56sol-direct-tlb-uncached-pagemask-20261011`

Cluster: source-bound PageMask-aware CCA=2 TLB mapped instruction fetch -> exact ordinary identity-RDRAM backing witness.

## Source research

This integration consumes evidence, not branch implementation, from:

- `research/tlb-uncached-fetch-gpt56sol` at `7ca433849844fb22a84106001a28e8be9a3002d9`
  - `research/ares-tlb-uncached-fetch-provenance.md`
  - original exact-pin Actions run `37850545963`
- `research/tlb-pagemask-gpt56sol` at `409017c6be4aff64b53f1d93161cc23d4696aee6`
  - `research/ares-tlb-pagemask-fetch-provenance.md`
  - original exact-pin Actions run `37917557580`
- pinned references from `refs.lock.toml`:
  - ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`
  - n64-systemtest `196f5421173220eb2f63a7a99c64795dc0ea0698`

The production implementation below is original Plaid Rust. No reference-emulator code, research instrumentation, generated observer code, or branch-only workflow is adopted.

## Reproduced evidence on current-main lineage

Before adding production code, a one-off branch workflow restored only the validated PageMask research harness onto canonical base `bbfafdee69f1d641c6325b5fc3fecb5b22bcedc5`, fetched the exact pinned references above, and re-ran the model plus executable reference matrix.

Reproduction receipt:

- Actions run `38153342519`, job `114511152389`: PASS.
- independent 100,000-case PageMask model SHA-256: `a5d4638e35372905086b57571edb56e96d5d682cf78bf11ef606e7bb6765939a`.
- exact-reference result SHA-256: `486296f8df73a1f0b7ccc2a4849df9130d69084b5bfed4e7c1e2ecc41edaac56`.
- the temporary reproduction workflow was deleted before the production diff.

The reproduced executable cases establish, for the bounded pinned-reference scope, that:

1. PageMask changes the even/odd selector and in-page offset; fixed bit 12 / fixed 4-KiB reconstruction is unsound for larger pages.
2. The exercised 4-KiB, 16-KiB and 64-KiB mappings select the expected physical backing for both halves.
3. Invalid selected halves fault before a successful fetch even when an equal-valued or otherwise plausible other half exists.
4. For exercised CCA=2 mapped fetches, one completed ordinary `VR4300_UNCACHED` RDRAM Word transaction inside the fetch boundary supplies the backing witness; CCA=3 does not.
5. ASID/global selection affects whether the translation is usable; equal values cannot repair a failed translation.
6. The exercised 4-KiB reverse-endian case changes the post-translation bus Word address from physical `0x7000` to `0x7004`.
7. Equal-valued data reads outside the fetch boundary do not become fetch ancestry; ambiguous in-window reads fail closed.

The evidence is exact pinned-emulator/reference evidence, not a universal VR4300 hardware theorem. Reference disagreement and unexecuted combinations remain outside the production certificate scope.

## Adopted invariant

`plaid_core::tlb_fetch` replays a separately authenticated finite source and certifies only the following bounded fact:

> A successful, source-recorded low-region TLB instruction fetch using execution-backed 4-KiB, 16-KiB or 64-KiB PageMask geometry may retain an exact ordinary identity-RDRAM backing witness only when the selected mapping half is valid, the mapping is usable for the supplied ASID/global state, the selected CCA is 2, the translated physical address recomputes from the supplied mapping under the reproduced PageMask formula, and exactly one completed aligned four-byte `VR4300_UNCACHED` RDRAM read occurs inside the same fetch context at the exact post-endian bus physical address with the exact fetched Word.

The replay preserves, rather than collapses:

- virtual fetch root;
- opaque mapping reference;
- opaque translation-context reference;
- raw/normalized PageMask geometry;
- selected even/odd half;
- translated physical address;
- post-endian bus physical address;
- backing-read ordinal;
- fetch chronology and word value.

The mapping and translation-context references are deliberately opaque. This module does not mint or authenticate their generations.

## Fail-closed boundaries

The production replay rejects rather than guesses when presented with:

- fixed-4-KiB / fixed-bit-12 large-page reconstruction;
- equal-value wrong-PFN backing;
- invalid selected halves;
- non-global ASID mismatch;
- unsynchronized global halves;
- unsupported normalized PageMask sizes beyond the execution-backed 4/16/64-KiB scope;
- cacheable/non-CCA=2 selected mappings;
- nonzero address-region cases not covered by the executed evidence;
- large-PageMask plus reverse-endian composition not executed by the retained evidence;
- missing, duplicate, foreign-address or wrong-value in-window backing reads;
- wrong post-endian bus address;
- nested/truncated contexts, noncontiguous ordinals or reordered epochs;
- deleted/tampered source data through the externally supplied complete-source SHA-256;
- forged derived reports through full source replay and equality checking.

A malformed raw PageMask is normalized only according to the reproduced source formula and only if the resulting geometry is one of the execution-backed sizes. This preserves the pinned normalization behavior without generalizing to untested page sizes.

## Rejected or superseded approaches

The following were explicitly not adopted:

- mechanically merging either research branch or emulator instrumentation;
- deriving backing from equal payloads, final memory, current TLB contents, numeric virtual/physical addresses, or finite fetch existence;
- treating a TLB mapping-content fingerprint or opaque caller label as an authenticated mapping generation;
- treating a successful mapped fetch as proof of sensor completeness, mapping-operation completeness or translation-context chronology;
- promoting the independently useful large-PageMask cache-remap research into a cached-fetch certificate without measured fill/resident ancestry;
- extrapolating region matching or large-page reverse-endian composition beyond the executed matrix;
- broadening the certificate to all PageMask encodings merely because the arithmetic formula can compute them.

A separate relocation-provenance candidate was considered and not selected for this cluster because its retained review exposed weaker caller-supplied event-label trust boundaries; this integration does not supersede relocation research.

## Production files

- `crates/plaid-core/src/tlb_fetch.rs`
- `crates/plaid-core/src/lib.rs` (module export only)
- `crates/plaid-core/tests/tlb_fetch.rs`
- `crates/plaid-core/tests/tlb_fetch_scope.rs`
- this receipt

Canonical `STATUS.md`, `NEXT.md`, `DECISIONS.md` and `progress.json` are intentionally unchanged by this bounded integration. The existing TLB/PageMask/cache/lifetime/whole-ROM proof obligations remain OPEN, and no milestone or closure obligation is discharged. This matches the direct-integration policy used by other bounded provenance primitives that add reusable evidence without changing closure state.

## Validation

Production integration branch validation before final main reconciliation:

- PR #40 Rust checks run `38154162247`, job `114513565956`: PASS.
- exact decoder dependency pin: PASS.
- `cargo fmt --all -- --check`: PASS.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS.
- `cargo test --locked --workspace`: PASS.
- canonical CLI checks: PASS.
- retained CPU-copy, XORI, CPU-SP producer, RSP CPU-IMEM, XORI/cache, PageMask/cache-remap, PI/cache, SP-DMA DMEM-ingress, RSP-store, EntryHi/cache and TLBR/cache synthetic contracts: PASS.
- independent fetch-summary assignment oracle: PASS.

This run's merge tree already included canonical RSP IMEM reverse-SP-DMA egress production code from `31c10020665e8386656fd943acab111b5c7e1671`. Canonical main then advanced only by infrastructure commit `24689113469e0a3325601d7b6fd41b4d06ecf761`, which made `.github/workflows/rust.yml` manual-only and did not change the tested Rust tree. Issue #4 explicitly records that post-policy direct-integration workers need not manufacture new Actions runs for that infrastructure-only drift; the validated commands/results remain the code receipt.

Focused adversarial coverage includes all fail-closed boundaries listed above, including equal-value decoys, unsupported geometry/cache policy, source deletion/reordering and derived-report forgery.

## Limitations and remaining proof obligations

This integration does **not** certify:

- completeness or authenticity of the event-producing sensor beyond the externally trusted source digest;
- TLBWI/TLBWR/TLBP/TLBR or CP0 writer census;
- mapping-entry content provenance or mapping-operation generation;
- PageMask/ASID/global writer chronology;
- translation-context generation or lifetime;
- arbitrary address regions, page sizes or reverse-endian combinations outside the executed matrix;
- cached I-cache fill/resident/tag ancestry;
- stale cache lifetime across remap, invalidation, save/restore, reset or NMI;
- mutation census, pointer-table immutability or executable lifetime;
- reachability, exception/interrupt/root completeness or indirect-target closure;
- overlay/relocation lifetime;
- whole-ROM CLOSED status or native completeness.

All report certification booleans for those broader properties remain false. Unsupported or missing evidence stays UNKNOWN. No solver waiver or native-complete path is introduced.

## Integration consequence

The useful new production fact is narrow but composable: once a future caller independently authenticates the relevant mapping/context history and the finite source, Plaid can retain a PageMask-correct mapped uncached fetch root and its exact ordinary-RDRAM backing transaction without collapsing virtual identity, mapping identity, translation context or physical backing. Cached fetches and broader TLB lifetime remain separate obligations.
