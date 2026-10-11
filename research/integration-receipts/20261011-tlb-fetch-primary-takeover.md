# Primary takeover: mapped uncached fetch/backing identity

Base: 990ec898d7671d01a0f405dcef8eaeee6a1accfe.
Prepared candidate: ffe7758c006b33e61254bc6d1dcd6062e1ebdd11, PR #40.
Research: 7ca433849844fb22a84106001a28e8be9a3002d9 (mapped fetch);
409017c6be4aff64b53f1d93161cc23d4696aee6 (PageMask).

Hypothesis: retain one actual mapped uncached fetch's exact ordinary RDRAM Word
read without collapsing virtual identity, supplied mapping/context references,
translated address, post-endian bus address or read chronology.

## Reconciliation and evidence

Adopt original Plaid Rust and adversarial tests from the prepared candidate,
excluding branch workflows, historical leases and stale canonical documentation.
Authenticate existing locally reproduced complete result bytes:
mapped fetch e72d4332f3112bea8b1130183d93c7791e688edca7340903ed6a5e5bd58cd851;
PageMask 486296f8df73a1f0b7ccc2a4849df9130d69084b5bfed4e7c1e2ecc41edaac56.
No new reference build or Actions dispatch.

The current geometry helper rejects malformed PageMasks; the candidate normalized
them from emulator implementation behavior. Reconcile on the canonical stricter
invariant: reuse derive_tlb_page_offset and change the malformed-mask acceptance
test to rejection. This does not weaken an obligation or reject an executed legal
positive case. Larger unvalidated masks remain unsupported.

A new deterministic adversary fails against prepared code: set selected PFN base
to 0x1004 and change translated/bus/read addresses to match. A Word-aligned read
alone does not prove the mapping has architectural low12-zero PFN form. The
primary now checks both supplied half bases. Exact pinned ares EntryLo assignment
fields support that representation; no upstream implementation enters Rust.

Thirteen actual fetches compare successfully through local protocol adapters:
seven original 4-KiB mapped fetches and six PageMask fetches. The adapters preserve
captured fetch/read order and values but project out the cached control, renumber
ordinals and attach mapping/context labels from controlled driver stages. Those
ordinals/labels are synthetic, not sensed TLB-operation generations or complete
sensor coverage. Cached control and translation-failure facts remain negative
evidence; equal-valued data reads remain outside their fetch boundaries.

The exact ares and n64-systemtest guards pass for pins in refs.lock.toml,
including whole selected checkout cleanliness. Recorded ares source blobs:
interpreter-scc.cpp c3d119bf4931c4616ae297a4c18b561490207e11;
tlb.cpp 3bec71ea1039b7fc5a5b2816ecc2b2ed534872dc;
memory.cpp f362ef67ab41ccf57330bbedd6f614e07a61dd17.

## Validation and limits

Thirteen focused tests retain successful geometry, strict masks, invalid halves,
ASID/global matching, endian bus lanes, exact in-window reads, decoys, source
deletion/report edits, unsupported regions and large-page endian scope.
Added PFN and typed-protocol regressions pass after the red/green guard.

Required local final gate on the exact base:
cargo fmt --all -- --check;
cargo clippy --locked --workspace --all-targets -- -D warnings;
cargo test --locked --workspace;
python scripts/test_cli.py;
git diff --check.

All broader report flags remain false. Complete sensor authenticity/coverage,
selected mapping provenance/generations, CP0/mapping/context chronology, cached
residency, root reachability, mutation census, executable lifetime, whole-ROM
closure and native completeness stay OPEN. No progress milestone or solver
waiver. Publish only as direct child of the locally validated head after refetch
and expected-head CAS with force disabled.

Outcome: all focused/saved-source/pin checks and the complete local final gate
PASS on the exact base above. Workspace tests include the retained actual
outer fixed-point deletion adversary. CLI remains OPEN for whole-ROM scope.
Progress data is unchanged and its consistency check passes.
