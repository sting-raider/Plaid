# Exception roots require executable-generation identity

Status: IN PROGRESS on isolated research branch.

## Question

Can a whole-ROM certificate identify an exception root only by its architectural
vector virtual address plus the bytes currently present in backing storage?

The existing exception-vector research validates where pinned ares transfers for
VR4300 exceptions.  Separately, cached-code visibility research validates that a
valid I-cache line can continue supplying older executable bytes after backing
RDRAM has already changed.  This note composes those facts instead of silently
assuming an exception transfer bypasses ordinary fetch/cache state.

## Hypothesis

For BEV=0, the general exception root is `0xffffffff80000180`, a cached direct
segment address.  If that line is already resident from backing generation A and
physical RDRAM `0x180` is then replaced by generation B, an exception transfer to
the same vector can still fetch/execute generation A.  A root certificate that
substitutes current backing B for the actual resident fetch is unsound.

The minimum useful root fact is therefore not just `(root_kind, virtual_pc)`.
For cached roots it must carry or be joinable to the actual resident/fetch
generation, including the fill/backing generation that produced those resident
bytes.  Missing or ambiguous resident history keeps the root executable identity
UNKNOWN.  Equal payloads do not collapse generations.

## Evidence under test

The branch contains:

- `spikes/044-ares-exception-root-generation/`: exact pinned ares dynamic fixture;
- `experiments/exception_root_generation.py`: deterministic adversarial replay;
- `.github/workflows/research-exception-root-generation.yml`: fresh exact-pin CI.

The dynamic fixture deliberately does not add an exception/cache observer.  It
uses architectural execution results and direct cache state checks already exposed
by the exact reference: warm old handler, replace backing, guest `SYSCALL`, stale
handler execution, guest I-cache invalidate, second `SYSCALL`, new handler refill.
The trigger and cache-maintenance helper execute from KSEG1 so they cannot evict
the target by instruction-cache indexing.

The replay separately attacks value/current-memory shortcuts with same-value
replacement, changed replacement, refill-before-write ordering, post-write refill,
uncached BEV control, and missing-resident evidence.

## Closed-world impact if validated

A whole-ROM root verifier must separate:

1. architectural root transfer identity (exception kind/vector/context),
2. virtual/physical mapping identity,
3. backing byte generation,
4. resident instruction-cache generation, and
5. the executable bytes actually fetched at the root.

Proving item 1 does not prove item 5.  Current RAM at the vector is not a valid
replacement for resident-cache history.  This affects exception/interrupt roots,
handler mutation, overlays at handler addresses, and compiler-time exploration
that restores or forks machine states.

## Scope

This experiment is bounded to exact pinned ares, BEV=0 general exception entry,
identity RDRAM and interpreter execution.  It does not establish hardware timing,
all CACHE variants, TLB-mapped aliases, NMI/reset boot roots, complete mutation
coverage, or whole-ROM closure.  BEV=1 is retained only as an uncached policy
control in the adversarial model unless a separate executable fixture is added.

Exact run IDs/hashes and final verdict will be appended after branch-only CI.
