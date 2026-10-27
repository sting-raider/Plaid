# GoldenEye source closure

Worker `ge-closure-3c48592d`, prepared base `4507fce0`.

Claim: productize the explicit counterfactual reset/refill experiment from
`69ca5f68` as source discovery only. Admit raw ROM pages only when a complete
PI producer survives to the first mapped fetch, with unique global TLB mapping,
identity RAM backing, cache agreement and exact full ROM content. A redirected
PC is never neutral-input reachability or indirect target closure. Existing
native mapping/content/generation checks remain mandatory.

Changes are intended in the analysis-only ares adapter, harvest policy and
synthetic source contracts. No children, shared-reference refetch, bridge change,
runtime decoder or commercial assets. Exact-tree local gates and visible silent
controls precede any plain fast-forward landing. README is worker-owned.

The standalone retained-main MM control reaches VI1798/fault0/PC00000000 in
30s (30.766s wrapper), rather than the previously observed VI1612. Current
runtime/headers equal the retained build; fresh source identity will also be
checked in the integration gate. Receipt: ignored
`target/receipts/ge-closure/mm-clean-main.json`.

## ADR-0282: explicit refill source discovery

The production adapter has a separate `refill-v1` invocation and cache namespace.
Fresh reset authenticates an anchor by the same full first-fetch mapping/producer/
cache checks as neutral replay. After that instruction completes, the adapter
changes only PC/pipeline, recording anchor, target and both step numbers. The
pinned core executes every subsequent exception, refill, instruction and DMA.
The wrapper rechecks the anchor against unmodified exact replay, and requires a
complete source row and successful footer. Rust neutral replay explicitly rejects
counterfactual rows, including a counterfactual footer.

For raw source verification, a project-owned delegating observer records successful
reads from the actual cartridge ROM device, including their source offsets.
Ordered half reads, ordered successful byte writes and complete DMA termination
must all agree. Any later overlapping RAM producer, even an equal-value CPU write,
invalidates the completed producer. Only a unique surviving producer covering the
whole fetched page can authorize its raw ROM span. Existing identity backing,
global/unique TLB mapping and instruction-cache/RAM checks are retained. Adjacent
complete transfers join only with the same loader site and source displacement.
Equal payloads at other offsets do not change the recorded source.

Harvest emits existing `tlb_raw` source declarations, whose bytes are reconstructed
from the ROM at composition. Native mapping/content/generation checks remain
mandatory at execution; the counterfactual physical placement is not installed
as a permanent mapping. No altered-run callbacks, observed edges, RSP sources or
data snapshots enter the ordinary replay protocol. These are candidate executable
sources, not evidence that neutral input reaches them or exhaustive target sets.

Search policy selects the latest naturally authenticated mapped entry, and probes
one missing target per virtual 4KiB page, up to64 per refinement. No ROM-offset
formula, game hash or game address is a production rule. Normal replay/first-use
table repair precedes refill search. The general refinement cap increases16->64;
unchanged source frontiers still stop. Completed negative replays are memoized
under the full ROM/source/anchor/target key and revalidated on every cache hit.
The same missing-source refusal measures3.688s cold/0.093s warm on this host.

## First measured source batch

Fixed starting point: ADR0281's55 engine pages,11633 blocks and909/903 ordinary/
residual blockers. Verified refill search authenticates49 additional pages in
217.344s, from64 explicit roots (15 refuse). The map grows to19746 blocks.
Unmapped targets fall317->231; missing direct targets grow487->517 as newly
decoded code exposes dependencies. Total residual obligations grow903->1391.
These are coverage and source-gap measurements, not an aggregate closure claim.
The batch uses natural anchor7f0adabc, selected from the replay data rather than
hardcoded in the implementation. Ignored inputs, output declarations, individual
root receipts and solve JSONs are in `target/ge-closure/`.

Residual categories after this batch: direct517, indirect303, invalid tables261,
unmapped231, load straddles23, table immutability18, table identity18, runtime-body
conflicts6, unsupported slots6, callbacks7 and unsupported TLBWR1. First-use table
repair and subsequent normal-pipeline rounds are measured separately under
`target/native/goldeneye007usa/` and `target/ge-pipeline.log`.

## Verification and limits

`scripts/test_refill_sources.py` uses original synthetic guest code, without game
or firmware payloads in git. Neutral execution never reaches its mapped target;
the explicit root takes an actual reference instruction TLB miss and guest
DMA/TLBWI/ERET path. Fresh resets agree exactly; the expected source, physical/
virtual extent, ERET fetch, PC and instruction budget are asserted. Equal-value
post-DMA writes, partial/misaligned producers, invalid/non-global mappings,
missing anchors, changed metadata/bytes and cache separation are checked. Equal
payloads at different offsets preserve distinct causal sources. Production wrapper
tests cover footer-only boot metadata, raw-only harvest, duplicate suppression and
memoized refusal. The new unique-source condition inverted in a private generated
adapter fails the retained synthetic contract. Normal replay rejects altered rows
in Rust; existing mapped native contracts cover runtime source/generation refusals.

Reference: ares9408cb43 at the locked revision, ISC/SLJIT notices retained by the
existing separate builder. The delegating ROM-device observer uses the same
project-owned observation boundary as spike006. No reference implementation body,
commercial assets, runtime decoder/interpreter/JIT or RT64 changes are introduced.
The shared references and shim remain untouched. Default GCC15.2 is retained.

Full exact-tree gates, generated control-source/object identities, VI/fault/PC
stops, readback PNGs and integration metadata are ignored under
`target/receipts/ge-closure/`. Emission remains refused while source, cross-page,
table/callback and refill execution obligations remain. There is no GoldenEye
native VI, logo, title or whole-game claim at this source-discovery milestone.
