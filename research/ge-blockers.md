# GoldenEye mapped-code blocker reduction

Worker: `ge-blockers-d61e1e7c`; initial main: `733de02a`.
User-local input: GoldenEye 007 (USA), canonical SHA-256
`2cdcec8a9f0cb6e36337f3ee39d8ad105dc8afa6ba1c02d466e8f5b771f9a162`.
No commercial bytes, traces, saves or framebuffer assets are committed.

## Initial hypothesis

Measure the ordinary ROM-only pipeline before selecting the change. Candidate
causes are unvisited mapped-page sources, page-crossing instruction/slot
representation and TLB refill semantics. In particular, relative branches must
use the architectural PC before selecting an analysis storage identity; arithmetic
on separately placed page addresses must not manufacture a guest destination.

Command: `python scripts/native.py "<local GoldenEye USA ROM>" --rt64 --seconds 30`.
All native runs use `SDL_AUDIODRIVER=dummy`, visible windows, stop JSON and
RDRAM/framebuffer readbacks. Initial artifacts: ignored `target/ge-baseline.log`
and `target/ge-baseline-time.json`. Exact blocker counts and final evidence follow
after measurement. No emission or gameplay success is claimed at this checkpoint.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` is a read-only ISC
reference/test oracle. Its branch implementation and pipeline use the executing
virtual PC; its TLB load path selects physical pages independently. No reference
implementation is copied into Plaid production.

## ADR-0281: architectural relative targets

Placed8093fff0/virtual7f0cfff0 branches to virtual7f0d000c, whose bytes already
exist at809c000c. The old arithmetic instead named absent storage8094000c.
`CodeImage::branch_target` now computes the architectural destination before
selecting storage inside the same fragment. Discovery, CPU-body validation and
lowering share it. External destinations stay virtual until source-derived
alternate discovery and the existing mapping/content/generation binding select
native code. Conditional tails preserve the entering continuation; linked calls
preserve virtual RA and the call continuation. Ordinary and likely slot behavior
is unchanged. No game constant, empirical source relation, decoder/interpreter/
JIT or permanently contiguous physical mapping is introduced.

## Measurements

| Source set | Blocks | Engine pages | Ordinary / residual blockers |
| --- | ---: | ---: | ---: |
| Main733de02a normal pipeline | 9,035 | 48 | 591 / 588 |
| Candidate with identical48-page loads | 9,647 | 48 | residual749 |
| Candidate normal pipeline | 11,633 | 55 | 909 / 903 |

On fixed sources, the largest baseline category, unresolved direct targets,
decreases **331 -> 317**. Forty-six formerly blocked source sites resolve;33
newly exposed sites acquire that blocker (some sites have multiple edges).
New code also adds indirect/table obligations, so the fixed-source total grows.
Automatic harvest authenticates seven more engine pages and exposes further
dependencies. This is a bounded category reduction and correctness repair,
not a reduction in all whole-map obligations. The candidate reaches the existing
16-attempt pipeline cap; source convergence and native completeness remain open.

Baseline pipeline:337.255s including cold release compilation. Candidate:314.663s
with incremental compilation, shared replay cache and expanded coverage. Unequal
workloads are not a speedup comparison. Both return1 and emit no executable.
Commands, exit codes, maps, declarations, solve JSONs and timings are ignored in
`target/ge-{baseline,candidate}*`; fixed-source results are in
`target/ge-baseline/fixed-sources-{map,residual}.json`.

Residual blockers by projected site region (unmapped storage targets are
attributed to their incoming source edges):

| Kind | Main mapped boot | Main7f engine | Candidate mapped boot | Candidate7f engine |
| --- | ---: | ---: | ---: | ---: |
| unresolved direct target | 4 | 327 | 4 | 483 |
| unmapped target | 0 | 194 | 0 | 317 |
| unresolved indirect target | 0 | 44 | 0 | 59 |
| unresolved runtime callback | 7 | 0 | 7 | 0 |
| runtime function decoded | 5 | 0 | 6 | 0 |
| unsupported delay slot | 0 | 4 | 0 | 4 |
| block straddles load | 0 | 2 | 0 | 3 |
| unsupported scope effect | 1 | 0 | 1 | 0 |
| invalid table entry | 0 | 0 | 0 | 13 |
| table immutability unproven | 0 | 0 | 0 | 3 |
| table target identity unproven | 0 | 0 | 0 | 3 |
| Total | 17 | 571 | 18 | 885 |

Ordinary KSEG0/base boot and conventional overlays have zero final blockers.
The boot mapping executes at70000000+; its synthetic storage is not KSEG0.
Address-taken/strict adds2 ERET and1 indirect-site obligation on main; candidate
adds2 ERET and4 indirect-site obligations. Residual dispatch does not discharge
missing direct sources, invalid tables or TLBWR.

## Verification and remaining scope

The new Rust test fails baseline's first virtual-target assertion and passes
the candidate. The synthetic native fixture fails baseline lowering with
`transfer to 80802000 has no proven block`. Eight native/pinned-ares comparisons
cover linked/unlinked ordinary/likely taken/untaken branches, positive/negative
displacements, all GPR/FPR/PC/HI/LO/FCSR and the complete256-byte output RAM
window. Inverted branch arms are detected; altered destination bytes fault3
through the original binding. Internal/absent destinations are separate checks.
The final focused check takes60.135s. Its native oracle uses the existing exact
input cache instead of starting WSL for every new fixture. No events are queued
in these contracts; this is not a timing-accuracy or exception-delivery claim.

Full gates and silent visible control receipts are under ignored
`target/receipts/ge-blockers`. Fresh generated control CPU sources are checked
before object reuse; compiler/header/flag keys and RSP source/object identities
are independently checked. Runtime/headers and RT64 bridge/patches are unchanged;
no shim ctest, shared rebuild or shared-reference refetch is needed. The worker
updates README in a follow-up commit after the code landing. Final gate/control
and landing receipts supplement this note.

GoldenEye has no native VI/fault/PC or framebuffer milestone because emission
remains refused. Next: authenticate unvisited pages from a general decoded loader
relation; represent cross-page slots/continuations without assuming neighboring
physical pages; verify TLBWR/Random/Wired, Context/refill/exception entry and mapping
lifetimes; resolve newly exposed table/callback obligations. No logo/title or
whole-game acceptance is inferred from analysis.
