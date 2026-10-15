# Next

## Milestone plan (ADR-0125, ADR-0126) — read this first

This section overrides the per-cluster continuation notes below wherever they
conflict. Those notes record open obligations; they are not a work queue.

Plaid's novelty is automatic discovery and closure proof from an untouched ROM.
Below that, reuse: lower through C (`crates/plaid-lower`), then link generated
code with N64ModernRuntime (GPL-3.0, so linked game apps are GPL-3.0) and RT64.
Every claim in issue #4 must name the milestone it advances and report the
effect in its receipt.

| # | Milestone | Done when | State |
| --- | --- | --- | --- |
| 1 | Synthetic ROM -> C -> native | spike096 programs, including nested/recursive calls, match pinned ares exactly; fail-closed cases fault | **done** (spike096, ADR-0127) |
| 2 | SM64 discovery recall | >= 99% of real functions found, scored locally against a decomp symbol map used only as an oracle | open: 8.1% (245/3029, ADR-0149) |
| 3 | SM64 closed under declared assumptions | solver CLOSED in an explicit assumption scope; every assumption listed and checked | open |
| 4 | SM64 boots natively to title | lowered code linked with N64ModernRuntime + RT64; no interpreter linked | open |
| 5 | Retire assumptions; OoT | assumptions discharged one by one; OoT via Yaz0 (PR #28) and relocation (PR #31) | open |

Next concrete steps, in order:

1. Done: return closure and function-level lowering (ADR-0127). Calls are C
   calls; every return checks `$ra` against its call's continuation. On OoT,
   43 of the 44 unresolved indirect sites are now certified returns.
2. Done: `plaid solve <rom> <map> --guarded-ram` and the 64-bit integer
   subset (ADR-0128). OoT guarded-scope blockers: 143 -> 82.
3. Done: declared runtime functions as a discovery boundary (ADR-0129). On
   OoT a heuristic declaration of 17 system functions leaves 1 guarded-scope
   blocker, but the first thread entry was never discovered.
   Done: runtime callbacks (ADR-0130). OoT now discovers its thread entry
   (613 blocks) and has 6 guarded-scope blockers.
   Done: COP1 data moves (ADR-0131); OoT is at 3 guarded-scope blockers.
   Done: guarded jump tables (ADR-0132). The remaining OoT blockers are
   memory-loaded function pointers inside libultra internals that the
   heuristic declaration leaves as guest code.
   Done: identification evidence (ADR-0133). `plaid identify` declares
   N64Recomp's reimplemented functions from n64sym signature matches. OoT:
   320 blocks, 21 guarded blockers (7 in boot code; 14 from calls into the
   region its code segment is later DMA'd over).
   Done: unaligned loads and stores (ADR-0134).
   Done: COP1 compares and BC1 branches (ADR-0135).
   Done: declared executable loads verified by content (ADR-0136) and a
   shared return-closure context (ADR-0137). OoT with its `code` segment
   declared: 7451 blocks, 748 guarded blockers.
   Done: `BREAK` as a checked abort (ADR-0138); OoT at 566 guarded blockers.
   Done: COP1 arithmetic, conversions and FCSR access (ADR-0139); OoT at
   42 guarded blockers.
   Done: GCC's scheduled jump-table shapes (ADR-0140); OoT at 8082 blocks,
   31 guarded blockers, with no unresolved jump table left.
   Done: runtime identification over declared loads (ADR-0141); OoT at
   7684 blocks, 29 guarded blockers, none of them instruction-scope.
   Recorded negative (ADR-0142): every one of the 21 function-pointer
   `jalr` sites takes its target from memory, and a sound field-store
   census would need whole-program store points-to, so they stay open.
   Store-guarded fixed-address cells would close only 1 of 22.
   Done: host-entry returns hand control back to the host (ADR-0146); OoT
   at 28 guarded blockers.
   **Next:** the 7 64DD calls target a driver that ships on the 64DD disk,
   not the cartridge (no dmadata file places code there). Guarded flag cells
   that prove the guarding flag stays 0 were prototyped and rejected
   (ADR-0147): the writer census misses stores through pointers. OoT is at
   its sound frontier. Prioritise SM64 (step 4), which needs the user's ROM.
   Done: runtime functions named from a reference symbol map (ADR-0148,
   `plaid identify ... --symbols`). Mario Party 2 showed that n64sym's
   database misses some SDK builds: 27 of its 29 boot-window blockers sit
   in an unidentified `osInitialize`. Use the SM64 decomp map for both
   recall and identification.
   Done: the SM64 ROM and a locally built, matching decomp map (CC0, commit
   9921382) are in `target/local-inputs/`. Forwarded callbacks (ADR-0149)
   open SM64's `-O0` thread creation: 2936 blocks, 8 guarded blockers, 8.1%
   recall (`research/sm64-first-measurement.md`).
   **Next for SM64:**
   - Disjoint declared loads, one image per segment, for the engine
     (`0x80378800`) and goddard (`0x8016f000`) segments. These are 4 of
     the 8 blockers.
   - The 3 audio `jr` dispatches.
   - Data-driven roots (level and behavior scripts) for recall.
4. **SM64 recall harness** (milestone 2): the scorer is ready (ADR-0144,
   `plaid recall <map.json> <sm64.us.map> [start end]`). Once the user
   supplies the ROM: discover from the real entry point, then score
   against a locally built decomp map. Keep ROM bytes, maps and traces
   ignored.
5. **Lowered subset growth** pulled by SM64: done for `ROUND/CEIL/FLOOR`
   and the `.L` conversions (ADR-0143), then branch-and-link, `LL/SC`,
   `SYNC` and conditional traps (ADR-0145): 196 of 209 forms. The other 13
   are COP0, TLB, `ERET`, `SYSCALL` and `CACHE`, which stay behind the
   runtime boundary unless a ROM needs them in guest code.
6. **Known-library evidence**: done for runtime boundaries (ADR-0133); PR #50's
   source-bound candidate model is still open for other uses.

Paused until a milestone needs them: RSP/SP lane, producer, task-root and
reverse-DMA provenance beyond spike095.

Unchanged: every AGENTS.md invariant, fail-closed semantics, exact-head CAS,
no ROMs or game-derived bytes in git, no GitHub Actions, and `native_complete`
plus every broad certification flag `false` until proven. Assumption scopes are
added as new scopes; existing scopes are never weakened.

## Historical per-cluster continuation notes

Scoped scalar RSP stores now connect rooted operand facts to DMEM writers and
CPU executable backing (spike094). Continue the graph through DMA/RAM/copy and
computed executable-byte origins, keeping code-read, operand, method and byte-
effect identities separate. Do not infer a writer from temporal overlap or equal
values. External/DMA effects remain cuts unless their own origins are proven.
Task/reset/control roots, general/vector producers, complete writer/backend
coverage, continuous lifetimes and whole-ROM/native closure remain OPEN.

Exact raw RSP consumption now feeds rooted scalar producer facts (spike093).
Continue from these definitions through actual DMEM/RAM writers and executable
consumption, and bind guest task/control/PC/reset producers to operand roots.
The boot recipe emits only the first initial operand root; later discontinuities
without a declared root reject. Captured inputs and unsupported instructions
stay opaque, and roots must cut equal-value held definitions. Do not infer task,
writer census, hardware or continuous lifetime completeness from these facts.

Lower IMEM effects now compose with CPU/RSP executable consumption on raw v8
(spike092). Continue actual register/data/task producer and execution-epoch
composition. Equal-byte writes, fill/load and new installations must not revive
ended parents; preserve reads frozen before those effects. Bulk cuts supply no
producer lineage. Restore/retirement, raw-pointer/backend coverage, complete
writer census, full lifetimes and whole-ROM/native closure remain OPEN.

Performed RSP consumption now joins the existing raw PI/RAM/IMEM state through
exact read receipts (spike091). Continue actual register/data/task producers and
writer/epoch coverage; a fetched instruction's byte parents do not authenticate
its operands or close its future target set. Preserve logical PC versus actual
masked read address, frozen read parents and unperformed lookahead independently.
RSP hardware consensus, full lifetime and whole-ROM/native closure remain OPEN.

Lower DMEM storage cuts now compose on raw history v6, including equal primitive
RSP writes that bypass CPU-window wrappers. Continue authenticating actual RSP
instruction/register/task producers separately; a sink cut supplies no source
parent. Preserve per-lane effects, IMEM independence and frozen DMA reads. Reuse
authenticated old v3/v5 results where this added protocol is unselected; broader
source, mutation, cache/mapping and execution-epoch coverage remains OPEN.

The existing raw-clock PI consumer now composes RAM parents with validated SP DMA
read/install occurrences and actual CPU SP consumption (spike089). Continue into
actual RSP consumption and producer/register definitions using complete histories;
this CPU path does not authenticate an RSP task or scheduler. Preserve frozen
source-read parents, independent SP writer identity and equal-write revocation.
Missing/ambiguous reads remain unknown; general census/lifetime/closure stay OPEN.

Physical PI storage writers now compose with executable consumption. Extend
other actual producer scopes while retaining original effect identity, separate
mapping/root obligations and independent cache residency. The 110-event native
reference fixture uses explicit host descriptor/mapping controls; it does not
prove guest MMIO or mapping ancestry. Reuse the authenticated commercial-prefix
report only when a complete delta check proves all writer selections unchanged.

The v5 boot source now places ordinary storage effects on the original PI/SP/
fetch clock. Continue actual producer/cached operand/mapping/root composition
from its retained69,513,732-record twenty-million prefix. Scalar/equal storage
writes and full backing fill/load cuts revoke RAM parents; surviving I-cache
generations stay independent. Restore/retirement still reject without execution-
epoch evidence. Preserve raw writer identities and externally retained digests;
finite sensor records do not establish mutation completeness or future closure.

The opt-in storage mutation sensor (spike086) reaches ordinary Memory::Writable effects beneath RAM
wrappers, including translated/EBus writes and explicit bulk/restore/retirement
cuts. Preserve actual component splits and unknown parents; bind actual producer
contexts separately. The25-effect/20-checkpoint contract does not cover raw-pointer
backends, hidden RAM or complete scheduling. Reuse its retained controls before
extending local-ROM capture; do not treat identity-only history as a writer census.

Continue the existing RSP producer path from original-clock register definitions
through actual installed-code consumption. Controlled v3 joins CPU IMEM installs
to RSP fetched words; v4 additionally joins original-clock RSP definition/DMEM
parents through separate reverse-DMA RAM writes to actual CPU fetch/decoder
contexts. Controlled v5 also binds promoted-current identity and exact complete
descriptor progression to that graph. Controlled v6 joins the RAM byte writers
through actual Dual read/IMEM installation back to RSP instruction consumption.
Controlled v7 also joins actual two-read/two-store DMEM ingress to RSP load
definitions with distinct lane parents. Controlled v8 also retains actual pending
address mutations and length recommit/supersession through promotion and immediate
handoff to installed-code consumption. Controlled v9 connects an actual decoded
CPU direct-KSEG1 SW through its pending length commit/synchronous promotion to
installed-code consumption. Controlled v10 also joins actual completed I-cache
burst/fill parents to cached CPU execution after changed backing, with explicit
opaque host control roots. Controlled v11 also joins actual guest HitInvalidateI
through fresh DMA writers/refill to cached execution; equal words cannot reuse
ended fill ancestry. Controlled v12 also joins actual SP LW/register/CPU SW RAM
copies through resident-vs-refilled executable ancestry. Controlled v13 also
retains one actual in-place XORI expression from original load parents through
RAM writing/invalidation/refill to transformed instruction consumption. Controlled
v14 also joins an actual copied/transformed BREAK to its exception transfer and
first cached handler fetch with separate writer ancestry. Controlled v15 also
joins the live exception-produced EPC generation through continuous handler
mutation/cache invalidation/ERET to returned instruction consumption. Controlled
v16 also retains an actual MFC0 read and equal-value MTC0 EPC writer, selects the
fresh writer at ERET and rejects held reads of ended generations. Controlled v17
also derives a changed EPC through one actual in-place XORI and connects ERET's
selected target to a separate CPU writer/refill/executable chain. Controlled v18
also binds actual TLBWI/current normalized entries to mapped cached BREAK/EPC/
ERET/returned execution. Equal TLB writes replace mapping operation identity but
preserve I-cache generations. Controlled v19 also binds actual EntryHi/ASID
context writes (including equal rewrites) separately from installed-slot writers
to both mapped consumptions. Fixture20 additionally composes a nonidentity
mapped address with surviving stale hits before/after actual ASID restoration,
then actual invalidation/refill/root/return in the same v19 protocol. Controlled
v20 also binds actual EntryLo0 page writers through TLBWI to changed physical
selection and fresh writer/root/return ancestry. Staging alone leaves the old
installed mapping active; equal page rewrites retain distinct identity. Controlled
v21 also composes actual TLBR loads from installed slot/page ancestry with active
ASID and mapped consumption; equal loads retain occurrence identity. Controlled
v22 additionally joins completed direct-SP SC effects/current LL source reads to
actual IMEM/RSP consumption, preserving failed attempts and equal writer identity.
Controlled v23 also joins SB/SH whole-SP-Word sinks and a held XORI expression
to actual IMEM/RSP consumption, keeping device vs aligned addresses and shifted
lanes' weaker ancestry distinct. Controlled v24 also connects actual decoded
uncached RAM LW/current byte writers through CPU held expressions and RAM/IMEM
copies to RSP consumption; an equal fresh RAM writer changes the next load's
parent without changing the previous load. Controlled v25 also binds actual
cached RAM LW to canonical D-cache resident state, captured backing-read writer
parents and IMEM/RSP consumption. Current backing changes cannot alter old
resident parents; actual HitInvalidateD/refill selects the new RAM writer.
Controlled v26 also binds actual cached SW sources/equal mutation revisions to
complete16-byte HitWritebackD export, including untouched resident lanes, then
RAM/IMEM/RSP consumption. Cached post-export reads retain mutation ancestry.
Fixture28 also composes surviving mapped I-cache execution after equal export,
then actual guest invalidation/refill to CPU consumption of that export. Next
compose other mapping/control producers and broader root/control lifetime with
complete mutation coverage. Keep ERET admission bounded to the uncut ERL0/kernel32/IE0 frame;
ordinary static ERET stays unsupported. Reuse retained748-event/127-control
fixture28 and729-event/124-control v26,
674-event/114-control v25,
610-event/102-control v24,
570-event/94-control v23,
542-event/88-control v22,
506-event/80-control v21,
485-event/77-control v20,
431-event/68-control fixture20,
421-event/66-control v19,
400-event/63-control v18,386-event/61-checkpoint v17,375-event/59-checkpoint v16,
365-event/57-checkpoint v15,
339-event/52-checkpoint v14,
295-event/45-checkpoint v13,
259-event/39-checkpoint v12,
228-event/34-checkpoint v11,208-event/31-checkpoint v10,195-event/
29-checkpoint v9,180-event/26-checkpoint v8,152-event/23-checkpoint v7,
142-event/21-checkpoint v6,136-event v5 and
134-event v4 (same19 controls),97-event/17-checkpoint v3 and all earlier
compatibility sources; no repeat reference build is needed for compatible consumers.
A fetched word or matching final image cannot exclude unsensed writes.

Continue from the complete twenty-million-call CIC6105 PI/fill/consumption join.
Canonical and independent replay agree on2472203 full candidate fetches,
172 samples/27 fills, beginning at seq17527797: ROM0x1000 -> four actual PI
byte writes -> cached RAM0x400/declared entry. Preserve these source clocks and
discrete observations while composing complete mutation coverage and cache/TLB/
mapping/execution-root lifetime. Avoid another equivalent capture or isolated
consumer. Neither unchanged values nor a finite prefix exclude unsensed writes.
The canonical `inspect-sp-pi-fetch-lineage` / `verify-sp-pi-fetch-lineage`
boundary retains independent raw source receipts. Primitive reconstruction also
joins request1/token6 to dispatch event1 and one status transition; its pending
list is empty. The declared ROM entry is observed at seq17527797, cached physical
0x400, with source unknown. Do not infer executable lifetime, mutation coverage
or hardware boot from finite byte agreement. Reuse retained sources and the
release CLI; no additional emulator rebuild is needed for compatible consumers.

The bounded fetch/history capture ceiling is twenty million calls, with the
unchanged 100-million history-record guard. Full repeated sources and disabled/
repeated checkpoints agree. Preserve the earlier million-call report as a
compatibility receipt; exclude the old timed-out partial source. Buffered output
preserves all getters/records and measured about5x improvement. Do not bypass
Random-register disassembly queries or conflate queue clock with CPU Count.

Use explicit verified CIC selection for local ROM capture (ADR-0123). The shared
profiled driver and import gate now admit NTSC/6102 and NTSC/6105; existing
homebrew captures retain their original 6102 scope. Reuse the compatible build
and retained sources to extend the supplied ROM prefix into actual RAM/PI/SP
chronology. The million-call prefix reaches low RAM at PC ffffffff80000004;
its 41 distinct RAM PCs remain source/lifetime unknown. The larger authenticated
prefix now observes the ROM entry. Preserve both boundaries and producer clocks;
larger prefixes do not establish boot completion or executable immutability.

COP1 context consumers must preserve the canonical architectural register-zero
check. Frame callback clocks still need an authenticated join to FPR ancestry
and resident/backing lifetime; equal values or ordinals alone do not supply it.

Primary integration harvest (2026-10-11): static executable-identity hardening is
integrated, along with trace/event integrity, retained raw-fact solver gates and
Region/load/overlay validation, fetch-summary realizability and pointer guards.
Intervening-writer provenance, negative controls and measured merge indexing are
reconciled, along with the bounded two-path join candidate. The 45 branches with
core source/test candidates have been reconciled; remaining research-only evidence
needs source-contract review and composition, not automatic production promotion.
Keep TLB/cache/lifetime, producer and execution-root research separate until its
source contracts compose. Following user steering, prioritize production
consumers of validated findings using authenticated swarm receipts and focused
integration regressions; avoid repeating reference builds without a concrete
need. No new research lane. See `research/integration-harvest-20261011.md`.

1. Observe actual backing read/write transactions and unify fill/cache-operation/
   fetch/copy ordering before constructing contextual executable identities.
   Controlled completed fills, guest tag stores, hit/miss invalidation, explicit
   fill and hit/miss writeback now preserve independent reference checkpoints.
   Successful identity-mapped RAM bursts now supply actual transaction witnesses;
   translated/degraded paths and general store/copy coverage remain unclaimed.
   Remapping/degradation/failure boundary tests now preserve baseline and full
   hidden-memory hashes while retaining unsupported paths as unknown. Unify
   transaction/fill/cache-operation/fetch order now passes on a 43-record controlled
   ledger, with independent checkpoints and forged-history rejection. The parallel
   scalar-fetch, CPU-copy, RSP, exception, restore and 64-bit mutation fixtures now
   reproduce locally. Shared explicit fetch boundaries and scalar reads/writes
   pass a 95-record ledger, its prior projection and independent primitive
   fixtures. The bounded boot prefix now preserves v5 bytes/checkpoints while
   retaining 5,051,089 ordered records and 32 actual RAM-backed fills. Strict Rust
   complete-source inspection/report rechecking now agrees with independent
   Python evidence. Buffered PI component cases now join 95 ROM byte origins to
   successful RAM effects, retaining discarded lanes, failed destinations and
   separate completion. A 481-record composed fixture now preserves actual fetch/
   fill origins through equal/changed reloads, guest SW/invalidation and partial
   words. Versioned boot chronology now retains 8,823,134 records and exact ROM
   origins for 1,638,808 successful PI writes, preserving complete v0/v5 sources
   and independent checkpoints. Original strict Rust v1 inspection and complete
   report source rechecking now agree with every retained count/hash and the exact
   v0 projection. Keep finite PI effects separate from production identities;
   do not certify completion from last-write context: actual queue-container and
   source checks expose duplicate IDs, cancellation and silent insertion failure.
   Actual-container insertion identities now survive heap movement/cancellation,
   including equal deadlines and save; load remains unknown. Compose this sensor
   with actual PI request and CPU dispatch/status boundaries now passes both
   directions in a finite component fixture. The bounded boot extension
   now joins accepted requests, queue outcomes and actual dispatch/status scopes.
   Original strict Rust v2 inspection and CLI rechecking preserve complete nested
   sources; compose broader source/mutation contexts before production promotion;
   keep general cache, byte lifetime and mutation completeness separate.
   Current tags/effective addresses can differ from resident-byte history; keep
   those identities separate. A recovered synchronized-restore/cache-power
   fixture now confirms restored residency without a fill and rejects a latest-
   tuple causal shortcut; broader reset/NMI/restore capture policy remains open.
   Extend additional source-specific contexts and lifecycle sensing beyond the
   current bounded homebrew boot prefix.
   V0/v1/v2/v4/v5 import and complete-source checks preserve all legacy map hashes.
   V5 retains resident context; actual ROM-read witnesses retain canonical sources.
   Production RAM/SP/PIF backing, copy/mutation lineage and executable lifetimes
   stay unknown. Bounded identity-RAM scalar contexts and RSP IMEM fragment lineage
   now have reference evidence; neither establishes a complete mutation census.
   Reproduced SP lifecycle evidence requires actual promotion/pending mutations,
   grouped count/skip rows and modulo-bank spans; BUSY edges and pending length
   commits are insufficient identities. Keep the ares/Mupen/Gopher FULL-policy
   disagreement unresolved until hardware-oriented evidence settles it.
   Actual PIF fetch-stage backing witnesses now pass nine adversaries with supplied
   firmware. Compose declared firmware/device/offset identity with the ordered
   capture; keep physical mirrors separate and require actual in-context reads.
   Keep the supplied-firmware, fixed NTSC/6102/8-MiB/deterministic/PIF-HLE scope
   visible; the finite guest-test prefix proves neither suite completion nor whole-
   ROM coverage. Retain raw sources for chronology and rechecking, with OPEN
   solver gating. Continue RSP/exception/TLB/FPU verification before expanding
   semantic claims; Mupen's pinned homebrew limitations remain documented in STATUS.
2. Model/sense non-PI copies and executable writes beyond PI-backed snapshots.
   The constant aligned cached-RDRAM SW sensor is partial; general addresses,
   other sizes, TLB/uncached paths and CPU-copy provenance remain unmodeled.
   Reproduced COP1 stores require successful mutation sensing below integer-only
   opcode handlers, FR-sensitive payload normalization and distinct cache/backing
   events. Reference callback count is not a hardware transaction/atomicity proof.
   Extend restored target-entry sensing beyond successful dirty lookups; verified
   snapshots now explain pending same-epoch returns, and explicit source-unit
   tags identify older units still executing. Preserve boot-source/lifecycle
   obligations; keep
   speculative compilation distinct from execution.
3. Prove pointer-table data immutability and guard coverage before issuing exhaustive
   table certificates. Extend cross-block joins only with rechecked invariants;
   the current table recognizer and single-predecessor chains are restricted passes.
4. Track decompression, CPU copies, address aliases and overlay unload/reload,
   relocation and instruction-patch snapshots. PI copy sensing alone is insufficient.
5. Implement whole-ROM certificate verifiers for roots/boot, exceptions, execution
   modes, RSP identity and executable mutation. No flags may waive these obligations.
6. Design a provenance-bearing candidate adapter if promoting the partial
   spimdisasm spike; assess known-symbol signatures separately. Measure analysis
   size/cost before making scalability claims.
7. Begin tiny native integer lowering only after discovery beyond the current
   synthetic scope is demonstrably useful, with reference differential tests.
   ADR-0125/0126: the synthetic native slice is done (spike096); see the
   milestone plan at the top of this file.

Commercial-ROM native lowering remains deferred until a commercial scope is
CLOSED; the ADR-0125 synthetic vertical slice is the only exception.

Source-preserving discovery solve admission now rechecks external expectations,
raw primitives, ROM-aware installed entries and compiled roots before emitting a
closure report. Supplied instruction words must match captured compiled snapshots,
including legacy opaque identities (ADR-0117).
Preserve expected sets independently at trusted capture/import boundaries; do not
recreate them from edited submissions. Compose other source domains, remaining
derived projections and complete sensor/lifetime obligations next (ADR-0114).

Cached general-root v1 now composes full-line slot replacement and the canonical
pinned NMI/reset/power profile with word-specific captured backing ancestry.
V2 additionally cuts all prior observer ancestry at successful restore boundaries,
including repeated equal snapshots; snapshot labels supply no byte authentication.
Retain v0/v1 contracts. Connect actual root-entry/fetch chronology, complete
writers/cache/mapping census and authenticated snapshot/component epochs before
using these finite receipts as lifetime or whole-ROM proof (ADR-0115).

The user-supplied Ocarina of Time US revision-2 ROM has an ignored local conditional
entry-window baseline: 293 blocks, 45 indirect sites and an OPEN whole-ROM report.
The explicit initial mapping is a hypothesis, not authenticated boot evidence.
Use it to prioritize real executable discovery; keep game bytes/maps/traces local.

Keep user ROMs in ignored `roms/` and derived maps/traces in ignored `artifacts/`.

SP writer/fetch composition now joins normalized captured sinks to actual CPU
executable bank reads with externally retained complete-source receipts. Same-
value writers replace candidates and contradictory bytes cannot revive from
later equality. Compose decoded CPU/RSP producers, PIF initialization, complete
lower-sink census and lifecycle/request identity before claiming ultimate origin
or RSP closure. Existing v3 reports/CLI remain unchanged (ADR-0116).

The decoded RSP -> DMEM -> CPU register -> IMEM chain now has a generic bounded
Rust consumer for the authenticated unified source (ADR-0118). Preserve the
actual source clock, mixed/unknown byte parents and whole-register definition
cuts. Extend incoming register/initialization ancestry and unify this producer
context with boot mutation/executable-fetch sources before claiming RSP identity,
complete mutation coverage or general executable consumption/lifetime. Controlled
v3/v4 now establish discrete RSP and CPU consumption on their own source clock;
they do not grant whole-ROM execution coverage. Separate RSP
scalar/DMEM-DMA candidate histories cannot be joined by equal labels or payloads.

The supplied game's IPL3 matches the pinned reference CIC-6105 checksum. Explicit
6105 capture/import support and the retained twenty-million-call prefix are now
available. Reuse those authenticated sources; do not relabel a 6102 run or the
conditional static map as game boot evidence.

Cached Word reads now share dcache_writeback's resident state and full-line
export ancestry (ADR-0119). Controlled v25 joins actual decoded LW/register,
backing-writer roots and IMEM/RSP consumption on the original clock. Compose
broader cached mutations/writebacks/dispatch with this normalized operation stream.
Controlled v26 now joins actual Word SW and complete HitWritebackD exports to
both cached/uncached operand consumption and IMEM/RSP execution; wider stores,
other cache operations and general mutation/lifetime coverage remain open.
Current backing content cannot replace the source of a cached pointer. Keep
physical immutability and complete writer/guard/target/cache-lifetime coverage
separate; the finite read/writeback report grants no table certificate. The
physical-immutability prepared histories remain pending composition with an
authenticated snapshot and complete mutation census.

COP1 physical FPR byte lineage now composes with canonical completed uncached
backing-store normalization (ADR-0120). Preserve the same source clock and
independent normalization contexts. Join actual backing writer ancestry and
executable fills/fetches next; cached COP1 loads/stores, arithmetic/other FPR
writers, producer census and context/lifetime still need source evidence. The
96-case fixture's declared instruction/GPR seeds and modeled physical selections
are checked against actual selected-register snapshots and backing effects;
they are not a complete guest instruction/writer capture for arbitrary ROMs.

Ordered cached SD/SDL/SDR subwrites now compose with resident-to-backing ancestry
under the explicit v2 kernel32/BEV1/prefilled direct scope (ADR-0121). Preserve
actual primitive callbacks rather than deriving their clock from final snapshots
or splitting a Double store into invented Word writes. Bind upstream GPR writer
ancestry and subsequent executable fills/fetches to these byte occurrences next.
Uncached/TLB/degraded/cache-miss paths, other actors, lifecycle and complete
mutation coverage remain separate obligations; no whole-ROM gate is promoted.

Target-qualified root classification now preserves VR4300 cache-error exclusion
and existing numeric exception candidates as distinct proof results (ADR-0122).
Carry the explicit target and hardware authority through future root-universe
certificates. Exclusion is not emulator silence and numeric selection is not
reachability, handler provenance or lifetime. Reset/NMI/interrupt/watch/root
census obligations remain OPEN; do not invent a CacheError handler for VR4300
or apply this exclusion/vector contract to generic MIPS III.

EBus hidden fetches require a separate derived-bits source witness or Unknown; retain actual read context and hidden-storage lifecycle before any origin promotion (ADR-0062).

Successful TLB-mapped uncached fetches now have finite source evidence; retain current translated/post-endian addresses in each access context and add mapping-generation/lifecycle evidence before proving alias history (ADR-0063).

Compose the reproduced translated scalar raw-read and delivered-transform witness with actual access contexts; decide degraded executable-image identity explicitly and retain unsupported paths as unknown (ADR-0064).

Retain full per-byte outgoing D-cache lineage before actual writeback and slot replacement. The reproduced clean-lane overwrite counterexample rules out dirty-mask-only provenance (ADR-0065).

General mutation sensing must normalize at the actual storage sink: CPU SB/SH reaching SP IMEM replaces a full Word and can carry upper source-register bytes (ADR-0066).
Bounded `cpu_sp_subword` production normalization now consumes an exact decoded
context plus completed Word effect. Compose it with authenticated ordered
writer/mapping sources; the primitive does not establish those sources' coverage
or executable lifetime.

PI read-side save/load/rejection now has independent actual-reference reproduction. Compose request/queue outcomes with the bounded boot stream while retaining RDRAM-to-PBUS data effects separately from scheduled status.

Carry both resident generation and mutation revision into exact writeback scopes. The primary four-phase fixture and six forgeries pass; compose broader store/epoch sensing before production lineage promotion (ADR-0067).

Compose RDRAM SB/SH successful byte effects with the general mutation sensor and later cache writeback; nominal width remains sink-specific and failed attempts supply no effect.

Distinguish ordinary RSP DMEM stores from CPU/SP-DMA IMEM sinks. Preserve observed lineage if those DMEM bytes are copied into executable IMEM later (ADR-0068).

Bounded boot request/queue/dispatch composition now passes the full prefix under ADR-0069. Original strict Rust v2 inspection and complete-source report rechecking now preserve exact nested v1/v0/v5 validation and unknown/unbound/canceled boundaries. Explicit v2 CLI inspection/rechecking now preserves version separation and input protection. Compose broader mutation/source contexts before promoting scheduling evidence into production identities. Keep finite scheduling facts separate from byte-transfer timing, lifetimes and whole-ROM closure.

Observed PI byte-chain replay now passes full independent corpus/source checks (10,954 fetches, 185 samples). The separate finite CLI inspection/rechecking now passes byte-order/source/report/input gates. Validate actual CPU SP DMEM/IMEM backing-read sensing for the remaining 596,991 SP fetches. Preserve raw writer/fill/read ordinals and mixed/unknown bytes; keep mutation coverage and executable lifetime uncertified. See `research/boot-pi-fetch-lineage.md`.

The controlled actual CPU SP sensor now passes independent baseline/disabled/
repeat state and seven forgeries (ADR-0072). Compose it into a separate boot
history version with exact prior-source projection, then add a strict original
Rust consumer. Keep CPU DMEM/IMEM backing separate from ultimate ROM origin and
RSP-originated DMEM mutations; PIF reads/initialization are the next source gap.

The latest RSP worker closeout now reproduces the nonzero SRV bit-12 adversary
(29 decoded probes); no ordinary RSP store gains an IMEM sink. Include those
actual DMEM mutations if extending CPU-to-SP source lineage.

The v3 SP boot extension now preserves all prior sources/checkpoints on the
10,000-call capture. Finish full-prefix independent replay and strict source-bound
Rust consumption, then compose actual PIF backing and SP producers. Its eleven
standalone forgeries supplement the actual controlled sensor adversaries.

Strict Rust v3 inspection/source rechecking now passes the full retained capture;
finish the independent full Python comparison and expose the tested finite CLI.
Actual PIF reads are the remaining fetch-backing domain; ultimate SP producers,
ordinary RSP DMEM mutations and executable lifetimes remain separate.

The v3 CLI now passes all source/report/version/input gates. Finish the full
independent comparison, then compose actual PIF-ROM backing reads and normalized
PIF backing writes. Keep SI busy-latch/lockout/RAM/cached paths unknown unless an
actual in-context ROM backing read is observed.

Full v3 Python/Rust replay and source binding now agree, including 512 unknown
out-of-range DMA receipts. Compose actual PIF ROM reads/writes next, retaining
current backing separately from supplied-firmware payload equality and ultimate
SP origin. The 2055 PIF fetches remain the last backing-read domain in this prefix.

PIF write probes require a correction to the earlier next-step wording: pinned
ares ROM backing is read-only, so delegated attempts are distinct no-effect
records. Finish complete v4 source/replay comparison and strict Rust integration.
Then pursue ultimate SP producers and actual RSP DMEM mutation chronology;
backing reads alone cannot certify executable lifetimes or whole-ROM closure.

Strict v4 PIF full-source replay and independent comparison now pass. Backing
identity exists for the observed PIF/SP/RAM fetch domains in this fixed prefix;
this does not establish ultimate SP producers or a mutation census. Continue
actual RSP DMEM mutation chronology and producer evidence, keeping executable
lifetimes, boot/exception coverage and whole-ROM certificates open.

SP producer inventory requires subword and FPR producers as well as integer SW:
2256 SB and six SWC1 effects occur in the verified prefix. Preserve actual full-
Word SP normalization and FR-sensitive FPR semantics. Next, validate scoped RSP
DMEM sinks and then compose actual instruction/dataflow evidence; same-PC/value
matching alone is not ultimate source provenance.

Controlled RSP DMEM sink replay now passes actual scalar/vector/wrap/same-value
cases. Controlled CPU SP refetch composition now also preserves scalar/vector
partial writers, neighboring writes, same-value CPU overwrite and unknown
foreign-sink cuts under independent checkpoint checks. Extend actual producer
instruction/dataflow evidence and complete-history source rechecking before
any broader promotion. Keep initial byte snapshots explicit; neither matching
values nor instruction PCs prove ultimate producer dataflow/lifetime.

Adjacent uncached LW/LWU-to-SW source evidence is now reconciled with full captured
GPR continuity, sequential PCs and independent instruction checkpoints. Before
production copy promotion, compose complete execution-attempt/source histories
and eventual executable consumption. Keep cached, transformed, non-adjacent,
interrupt and lifetime cases unknown; the callback alone is not a census.

The one-step adjacent XORI source contract is also reconciled, including explicit
zero-immediate transform identity. Preserve this exact def-use boundary when
composing broader producer evidence; matching transformed values does not select
a source generation. Decompression/relocation and general dataflow remain open.

Actual decoded CPU SW/SB/SWC1-to-SP context now replaces caller-supplied operand
metadata in the controlled fixture. Compose this precise GPR/FPR source witness
with complete boot histories and earlier register lineage before production
promotion. Keep unscoped writes unattributed; preserve guest-byte snapshot view
and reference-specific full Word normalization without inferring hardware truth.

RSP DMEM through actual CPU LW/GPR/SW to IMEM now has a reconciled finite
composition contract with mixed/unknown source bytes separate from sink
generations (ADR-0091). Before promotion, compose actual executable consumption
and complete lifetime/attempt histories. The reference fixture's source register
operands are measured; their ultimate ROM/DMA ancestry remains unresolved.

The XORI/cache branch's unmodified four-scenario behavior probe is now retained.
Compose actual captured transform definitions with cache resident/revision,
completed writeback and fill/fetch events before issuing ancestry certificates.
Abstract generation chains and identical final payloads cannot fill missing
measured edges; preserve stale and early-refill controls (ADR-0092).

Large-PageMask/cache-remap behavior is now retained under spike 049. Bind actual
historical translation and mapping/context operations to measured fill/writer
receipts before production promotion; a miss flag cannot authenticate new
resident or backing generations. Preserve temporary-unreachability controls and
the unresolved ares/Gopher index-source disagreement (ADR-0093).

PI copy/cache visibility now retains complete finite source/sink/fill/fetch
regressions under spike 050. Compose actual queue-container lifecycle identities
only for completion claims; do not require completion to retain successful byte
writes or use completion to refresh cached code. Extend general writer/census/
lifetime evidence before production origin promotion (ADR-0094).

Forward DMEM ingress now retains strict paired Word lane/source-read contracts
under spike 051. Compose actual request identities, RDRAM storage ancestry and
RSP consumer definitions before issuing executable provenance certificates.
Missing successful source reads remain unknown; nearest equal-valued reads
cannot identify a lane. Directly staged component calls do not close scheduler,
writer-census or executable-lifetime obligations (ADR-0095).

RSP store-domain behavior now retains all scalar/vector store families in the
finite spike 052 matrix, including aligned SRV's zero-byte control. Preserve the
pinned interpreter/source DMEM-only classification when composing RSP writers,
while retaining CPU-window, DMA and out-of-band IMEM mutations independently.
Hardware/recompiler, task activation/retirement and lifetime completeness remain
separate obligations (ADR-0096).

Guest EntryHi/cache reactivation now retains the finite spike 053 controls.
Compose measured context writers with installed mapping, backing and resident
histories before issuing certificates; internal snapshot equality and miss counts
are insufficient. Preserve inactive residents until a verified replacement or
invalidation boundary, and retain the ares/Gopher index disagreement (ADR-0097).

The finite TLBR/cache controls now share that obligation under spike 054.
Keep successful context loading distinct from operation occurrence: TLBP and
out-of-range TLBR do not supply a successful EntryHi load at the pin. Compose
actual histories before production promotion; repeated snapshots do not recover
same-value writer identity (ADR-0098).

Original Rust CPU-copy replay now consumes the validated adjacent LW/LWU and
one-step XORI history protocol through inspect/verify CLI commands. It preserves
source-read and sink-write ordinals under an external complete-source receipt.
Compose those witnesses with storage writer ancestry and eventual executable
consumption next; a bounded copy witness is not a mutation census or solver
certificate (ADR-0099).

The separate captured-definition consumer now retains live read identity through
unrelated register reads/NOP and one XORI, with phase/ORI/failed-read cuts. Compose
these qualified read/write identities with storage and executable consumers;
do not infer general source census from a contiguous captured sequence (ADR-0100).


Production now has a bounded general/TLB exception-root selector (ADR-0101).
Whole-ROM root work must next authenticate the exception classification plus
BEV/EXL/address-mode chronology, compose each selected root with handler-byte
provenance and cache/mapping lifetime, and independently justify interrupt,
watch, reset/NMI and cache-error roots. Numeric vector derivation is neither
reachability nor a complete execution-root certificate.

Production now has source-bound TLBWI operation generations (ADR-0102). Compose
them with authenticated mapping content, PageMask/ASID/global state, TLBWR and
other mapping/context operations, actual fill/resident histories and save/restore/
reset chronology before using them in executable-lifetime or translation proofs.
A same-content legal TLBWI remains a distinct operation; snapshot inequality and
equal payloads cannot recover occurrence or selected-slot identity. Complete
sensor coverage and a full TLB mutation census remain OPEN.


The bounded BEV=1 general-root PIF composition now authenticates one exact
singleton observed handler fetch from complete PIF sources (ADR-0103). Next root
work must bind that fetch to authenticated exception occurrence/classification and
BEV/EXL/address-mode chronology, then compose cache/mapping executable lifetime.
Reproduce BEV=1 refill/XTLB source behavior separately before extending the rule,
and independently discharge interrupt/watch/cache-error/reset/NMI roots. Repeated
coalesced PIF observations, equal returned bits and matching mirrors stay OPEN
without per-occurrence same-fetch backing identity.

Production now also has a bounded source-bound cached BEV=0 general-root Word replay
(ADR-0104). Compose it with authenticated exception classification and BEV/EXL/mode
chronology, complete backing/cache/mapping mutation histories and full handler spans
before treating a selected root as executable provenance. ADR-0103 separately binds
one BEV=1 root occurrence to exact PIF backing; neither decision proves root
reachability or census completeness. Extend separately to TLB refill/XTLB roots,
interrupts, reset/NMI and other execution roots. Missing residency stays UNKNOWN;
equal current bytes never recover a writer or fill generation.


## PI interrupt producer composition remains open

Production can replay an authenticated bounded PI completion -> raw MI.PI -> MI mask/poll -> CPU RCP-pending chain without borrowing PI-copy equality or latest-request state. Next work must independently bind accepted request/queue dispatch to completion observations, compose with the generic CPU interrupt eligibility/root gate, account for other MI/timer/software producers plus reset/save/restore chronology, and prove source/sensor completeness for the declared scope. Unknown chronology remains OPEN; this is not a producer census or root-closure waiver.

The bounded generic maskable gate now exists in `interrupt_roots` (ADR-0106).
Join authenticated producer/status/BEV chronology to the same boundary before
using its numeric candidate for executable-root evidence. Suppression at one
boundary does not exclude that root from the execution model. Actual transfer,
handler-source/lifetime and complete root census still require separate proof.

Bounded PageMask half/offset geometry now exists in `tlb_geometry` (ADR-0107).
Compose it only with an independently selected/authenticated mapping and retain
the actual translated transaction address. Geometry alone does not establish
ASID/global/valid/dirty/CCA, overlapping-entry selection, operation generations,
resident/backing lineage or executable lifetime; larger unvalidated masks reject.

Bounded guest Cause-write operation replay now exists in software_interrupt
(ADR-0108). Connect authenticated raw operand/source history and actual
producer/Status/BEV chronology to the same interrupt boundary before root
composition. Preserve successful same-value writes as distinct operations and
keep hardware pending producers independent. Saved state-row adapters do not
establish callback chronology or complete sensor coverage.

Mapped uncached fetch/backing joining now exists in tlb_fetch (ADR-0063), using
strict tlb_geometry. Compose its opaque mapping/context references with actual
TLB-operation and CP0 writer history before claiming mapping ancestry/lifetime.
Preserve virtual aliases and same-address remaps as independent fetches. Cached
residency and unsupported region/endian geometry still need separate evidence.

TLBWR operation replay now exists beside TLBWI/TLBR (ADR-0109). Compose explicit
selection/write generations with authenticated normalized mapping content and
the same fetch context; neither Index nor equal content supplies that ancestry.
Keep the source/census, ASID/global/CP0, cache and reset/restore obligations OPEN.

Resident-to-backing writeback replay now exists in dcache_writeback (ADR-0067).
Compose actual CPU copy/transform/store ancestry with its mutation ordinal and
byte lanes, then bind exported bytes to subsequent executable fills/fetches.
Cached mutation alone cannot refresh instruction residency; TLB/alias and epoch
transitions require independent authenticated context and lifetime evidence.

CPU copy's captured-writer chronology now records phase-scoped successful Word
stores (ADR-0110). Complete writer coverage is still required before turning a
compatible captured candidate into actual source ancestry. Compose external
device/RSP/DMA and cache/epoch cuts explicitly; observed contradictory reads
already revoke stale candidates and equal later values do not restore them.

Completed Word SC -> SP normalization now exists in cpu_sp_conditional
(ADR-0111). Compose its context/effect identities with an independently complete
writer stream and actual IMEM execution before granting executable ancestry.
Missing sinks are absence of evidence without source completeness. SCD, cached/
mapped aliases and reservation lifetime remain separate unvalidated obligations.

Bounded observed Count/Compare operation replay now exists in timer_interrupt
(ADR-0112). Compose independently authenticated timer transitions with Status/
BEV at the same interrupt boundary and the actual handler source. The v0 schema
has no elapsed-time event: unrepresented Count progression rejects. Resolve
reference scheduling disagreements with stronger evidence before extending it;
finite replay does not authenticate decoded guest writes or complete the census.

Source-available discovery-trace manifests now exist in evidence_manifest
(ADR-0113). Preserve the expected exact source set at the trusted import/build
boundary before edits; do not regenerate it from an edited map or trace. The
explicit primitive verifier rejects missing/unexpected sessions and reuses full
source projection checks. Integrate that preserved input at future certificate
boundaries and retain stronger entry/ROM checks plus typed adapters for other
domains; a manifest over an incomplete sensor does not establish closure.
