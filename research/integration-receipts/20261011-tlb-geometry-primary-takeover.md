# Primary takeover: bounded PageMask geometry

Hypothesis: recover the prepared validated PageMask geometry helper, preserving
the exact selected half and in-page offset instead of reconstructing all mappings
as 4-KiB pages. Complete receipt rechecking must bind an external mask/address.

Base: `d2e298905a8af05ea3bf942b7d46bab326753d72`.
Candidate: `709c0c8080d3fa25a0480721114dfedf9c47e213`, PR #32,
READY closeout `6111027088`. Source research:
`409017c6be4aff64b53f1d93161cc23d4696aee6`. Preserve only the original Plaid
module and six regressions. Exclude historical workflow/lease scaffolding,
unrelated merged modules and stale ADR-0105 numbering; that number now belongs
to PI interrupt producer provenance.

## Evidence and design

Authenticate historical artifact `11610251345` ZIP receipt
`27dd9bc5f12fc6da64b21852df30d42ca4f89345e4ab134dbc78a19899aa7406`
and complete result receipt
`486296f8df73a1f0b7ccc2a4849df9130d69084b5bfed4e7c1e2ecc41edaac56`.
Six actual successful mapped fetches retain independent completed backing reads;
equal-valued opposite-half decoys do not change their physical sources. The
invalid selected even-half case at VA `00091000` supplies no successful fetch,
despite bit12 naming a valid decoy. The helper supplies geometry only and must
not turn that even selection into a valid mapping/fetch certificate.

The existing canonical spike-049 result receipt
`d884a8ce86b01192750afd9f7539e2a618f5a0dcb72c54f777134c9561fe8a35`
independently retains measured PageMask/selectors for 16-/64-KiB pages. Compare
saved bytes, without reference rebuilds or new Actions runs. Exact pinned ares
TLB source and n64-systemtest PageMask expectations remain source context only;
no upstream implementation is copied.

Accept only exact raw masks `0`, `6000`, `1e000` in this bounded version.
Malformed patterns and larger model-only sizes reject. Reuse the prepared helper
to derive the half/offset for an already selected entry. Add complete receipt
reconstruction from independent input, checking every nested geometry field,
address, selected half and offset. Equal addresses/bytes are not mapping identity.

Current TLBWI/TLBR modules retain operation generations; this helper does not
select an entry, mint a mapping/context generation, validate ASID/global/region/
valid/dirty/CCA, or derive ultimate byte origins. Preserve cache/reference
disagreements and all mapping/producer/lifetime/census/native proof obligations.

## Local gates before canonical publication

Retain all six candidate regressions and add full-receipt corruption/input/scope
tests. An ignored local Rust harness compares authenticated actual-source half/
offset cases and measured PageMask selectors from both saved results.

```text
cargo test --locked -p plaid-core --lib tlb_geometry
cargo test --locked -p plaid-core --test tlb_geometry
python spikes/049-ares-pagemask-cache-remap/test_verify.py
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python tools/progress.py --check
git diff --check
```

The canonical commit must be a direct child of the exact locally validated base;
refetch before expected-head CAS, with force disabled. No progress milestone or
solver waiver changes.
