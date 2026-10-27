# Mapped sequential continuations

Worker `ge-closure-3c48592d`; candidate based on ADR0282/README main
`bf6ef29b`. This is the same worker's isolated next milestone, without children.

Hypothesis: instruction advancement must use the architectural virtual PC at
fragment boundaries. Linear flow and branch/call continuations cannot inherit
the identity of neighboring analysis storage. Splitting there and dispatching
over source-derived alternates should preserve independent native mapping,
content and generation guards, plus the original entering return continuation.
Guest RA is still the source instruction's architectural PC+8.

Baseline synthetic case: two virtual neighbors, with nonadjacent physical backing
in the even/odd halves of a guest TLB entry. The first fragment falls through
after1024 instructions. Baseline refuses `block_straddles_declared_load`; pinned
ares reaches the exit with result11. The candidate splits the block, admits the
neighbor through its own native binding and matches all GPR/FPR/PC/HI/LO/FCSR and
the256-byte output window. Nine call/branch paths and native source/continuation
mutations now verify this scope. No cross-page delay-slot admission is claimed.

The settled ADR0282 source frontier is45418 blocks/222 engine pages,435 ordinary/
432 residual blockers. Categories: direct132, unmapped104, indirect87, straddles67,
slots26, runtime-body conflicts8, callbacks7 and TLBWR1. Original903 residual
obligations have fallen432, while coverage grew11633->45418 blocks. Ignored source
baseline: `target/ge-converged-0282` in the primary worker checkout. Measurements
of the candidate must use those same source declarations before expanding again.

## ADR-0283 implementation and measurements

`CodeImage::sequential_pc` keeps storage only while execution stays in the same
fragment; its single source lookup avoids two linear slot walks per instruction.
Discovery ends a block at the boundary and names the guest continuation. Bound
alternates suppress the overlapping fallback ROM identity. Delay slots remain
inside their source fragment, including the special case of an annulled likely
slot; external slots are explicitly refused even if fallback bytes are present.

Lowering rederives each continuation from source bytes/addresses and builds a
separate native target set. It reuses existing mapping/content/generation dispatch
and passes the entering return continuation. Storage PC+8 still supplies the
source-relative guest link expression, so the caller's mapping delta gives the
architectural RA even when its continuation lies in another fragment. The emitted
dispatcher cannot silently decode, interpret or JIT an unknown target.

Fixed-source results, same ROM/declarations and release compiler profile:

| Measure | ADR0282 main | Candidate |
| --- | ---: | ---: |
| Engine pages | 222 | 222 |
| Blocks | 45418 | 46512 |
| Residual blockers | 432 | 202 |
| Missing direct targets | 132 | 30 |
| Unmapped targets | 104 | 2 |
| Blocks crossing load bounds | 67 | 0 |
| Unsupported delay slots | 26 | 42 |

The remaining202 comprise indirect91, slots42, direct30, invalid tables17,
table immutability2, table identity2, runtime-body conflicts8, callbacks7,
unmapped2 and TLBWR1. New table obligations reflect newly decoded code. Existing
first-use data repair is a separate refinement, not included in this fixed-source
claim. Ordinary scope is209 blockers; residual scope retains7 site records.
Emission stays refused. Ignored maps, declarations, solve JSONs and release timing
vectors: `target/ge-sequential-final/`. Preliminary matched warm discovery is
29.735s before/31.828s after, with expanded coverage; this is not a speedup claim.
Final-tree timings and local validation are recorded in the same receipt family.

## Verification

`runtime/test_mapped_continuations.py` compares all32 GPRs/FPRs, PC, HI/LO,
FCSR/FCC and the entire256-byte output window against exact pinned ares. Nine
paths cover linear flow, JAL/JALR returns, ordinary/likely taken/untaken branches,
and ordinary/likely untaken link branches. The last group checks virtual RA after
an annulled slot explicitly through the complete state comparison. Adjacent
virtual pages use nonadjacent physical backing within an even/odd TLB entry.
Three destination-byte mutations fault3, and three wrong-continuation mutations
are detected. Baseline's linear case refuses at the load-straddle gate.

The Rust contract separately checks internal/external/wrapping advancement,
foreign adjacent storage, a call continuation, missing cross-page slots and a
conventional KSEG0 slot that overlaps the fallback ROM window. The latter cannot
borrow fallback bytes as either code identity or delay instruction. Existing
native TLB alias/remap/generation contracts remain in the full runtime gate.
No events are queued in the new CPU fixtures; no new interrupt/refill delivery,
instruction-cycle accuracy or whole-game claim is made.

Reference use: unchanged pinned ares9408cb43 ISC/SLJIT oracle, retaining existing
notices in ignored builds. No upstream implementation body or commercial assets
enter production. Default GCC15.2 CPU/RSP flags, runtime and RT64 bridge/patches
are unchanged. Exact-tree gate, source/object identity checks, visible silent
controls, stop JSONs and RDRAM PNGs belong under ignored
`target/receipts/ge-continuations/`; no shared shim rebuild is required.
