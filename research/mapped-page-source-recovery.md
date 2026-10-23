# Independent mapped-page source recovery

Base: `9d65ce45e47a15dd903eba7326278d9499240bb2` (ADR-0250 behavior).
Local input: user-supplied GoldenEye 007 (USA), canonical SHA-256
`2cdcec8a9f0cb6e36337f3ee39d8ad105dc8afa6ba1c02d466e8f5b771f9a162`.
No ROM bytes, RAM payloads or commercial instruction traces are committed.

## Claim and production change

An unsupported open-call projection must not prevent an independent first-fetch
source request. Previously `harvest()` refused before running any replay when
`replay_sites()` encountered an `ares_tlb` image. The already supported mapped
snapshot mechanism therefore never reached the missing direct engine targets.

On projection refusal, a nonempty existing source request now runs the ordinary
bounded source-only replay, without call sites, coverage probing or observation
bindings. The receipt retains the call-projection refusal. A request with no
known entry still refuses. Malformed/ambiguous composed image bindings still
refuse before the fallback. No unsupported call gains an observed target.
Already declared `ares_tlb` text is excluded from missing-source requests; its
data tail and targets beyond the text remain eligible. Raw shared-slot occupant
and ordinary call-observation behavior are retained.

This reuses ADR-0236's `ares_tlb` declaration, its whole-ROM exact first-fetch
replay during composition, and physical/content/generation checks. ADR-0250
continues to recover data independently. There is no new encoding, runtime
instruction executor, target-set proof, native exception delivery or TLBWR
lowering. All existing native-emission blockers remain authoritative.

## How the engine pages reach memory

The initial boot mapping is the earlier global 4 MiB even half at virtual
`70000000`, backed by physical zero. That mapping alone does not supply engine
code at `7f000000`. The initialized boot-data stream at `70020d90` starts with
`1172`; independent raw-DEFLATE inflation after its marker yields `0x3c550`
bytes ending at `8005d2e0` (ADR-0250). This is distinct from the paged engine
source examined here.

The resident page loader beginning at `700019d8` rounds its requested virtual
address to an 8 KiB pair. At `70001a34..70001a70`, it selects a pool slot and
calls the cartridge copy routine at `70005c1c` with size `0x2000` and source
`0x34b30 + (virtual_address & 0x00ffe000)`. The returned physical pool address
is converted to EntryLo bits at `70001abc..70001af4`. The page table is at
`8005dbf0`, with 16-byte records indexed by the virtual pair offset shifted by
13; a separate pool-occupancy table starts at `8005e3f0`. The observed pool
selection includes a modulo-90 pseudorandom choice. These are ROM observations,
not production constants or a universal loader model.

The refill stub at `70001b60..70001ba8` is copied to vector `80000000`. It sets
PageMask=0, reads Context to index the page table, writes EntryLo0 and the
adjacent physical page as EntryLo1, performs TLBWR, then ERET. The actual
analysis-time execution has TLBWR at `80000034`. Wired is set to 2 at
`70001bb0..70001bbc`. Pinned ares independently defines PageMask=0 as 4 KiB
halves, EntryLo PFN translation, global/valid handling, and TLBWR's Random-index
selection. The observed `7f000000` refill has EntryLo0=`d01f`, EntryLo1=`d05f`:
physical `340000`/`341000`, global/valid/dirty/cache algorithm 3.

A source-only replay of requested `7f000000` reaches its first fetch at step
67,137,997 (VI 103). The snapshot is exactly 4 KiB at physical `340000`, with a
preceding PI request of 8 KiB from cartridge `10034b30`
into that pool pair. The captured page equals the raw ROM range
`34b30..35b30`; no decompression is needed for this page. Other engine-page
snapshots and the loader arithmetic support the same raw source relation.
Equal payload alone is not promoted to a causal DMA-source witness or an
exhaustive proof: production continues to authenticate the actual first-fetch
RAM through replay. The empirical affine relation is not extrapolated to
unexecuted pages.

The pool can evict/reload virtual pairs. A first-fetch physical binding does
not prove all later page placements, exception delivery or executable lifetime.
Those remain required work before native acceptance. The boot snapshot's broad
text/data boundary remains another independent open problem.

## Reproduction and verification

Normal command (visible if emission becomes possible, silent validation):

```
python scripts/native.py "<local GoldenEye USA ROM>" --rt64 --seconds 30
```

`python scripts/test_ares_boot.py` covers source-only fallback with unsupported
mapped calls, no-entry/no-byte refusal, exact mapped-text coverage boundaries,
and two neighboring virtual pages backed by nonneighboring physical pages.
The latter executes authored COP0/TLBWI/store/jump instructions in pinned ares;
batched and exact first-fetch replays agree byte for byte. Existing invalid,
non-global, stale-cache, producer, raw-occupant and native/reference contracts
remain in the full runtime gate. In-memory mutations reversing source-only
selection and mapped-text coverage each fail the new authored contract; original
source passes again. No production file is altered by mutation testing.

Reference: `.refs/ares` at locked
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, ISC, inspected
`ares/n64/cpu/tlb.cpp` and `interpreter-scc.cpp`. Used only as the existing
analysis/test oracle. No upstream implementation was copied into Plaid's native
runtime and no new dependency or licensing decision is needed.

Ignored local evidence is under `target/ge-paging-20261023/target/`: baseline
and final normal pipeline logs/maps/loads, `baseline-*-taken.json`,
`baseline-residual-dispatch.json`, `direct-probe.json`, `paging-capture.json`,
`loader-disasm.txt`, `tlb-trace.log`, `ares-contract.log`,
`review-mutations.log`, `full-gate/results.json`, and control logs. The ignored
`make-probe.py`/`run-probe.py` copies the existing analysis adapter and logs only
TLBWI/TLBWR PC, step and staging-register metadata before those instructions;
no guest bus accesses or instruction semantics are added. The pinned source
checkout stays unmodified.

## Before/after and remaining blockers

The untouched baseline normal pipeline reproduces **4706 blocks, OPEN 175
ordinary / 172 residual**. The new normal pipeline reaches **9035 blocks,
OPEN 592 ordinary / 589 residual**, with 48 authenticated 4 KiB engine-page
sources. It stops because the bounded replay supplies no additional source;
13 harvest iterations are below the pipeline's 16-iteration cap. No GoldenEye
native artifact, window, or gameplay run is emitted.

Of the original 85 unresolved direct edges (78 distinct destinations), **81
now have decoded destinations**. The remaining four edges name only
`7f010290` (three edges) and `7f08fe74` (one). Their expected source pages from
the observed loader relation would start at ROM `44b30` and `c3b30`,
respectively, but they remain UNKNOWN because those pages were not captured.
These offsets are research leads, not accepted declarations.

The larger total is newly exposed dependency coverage, not a net reduction
in whole-map obligations. Residual classes: 331 unresolved direct targets,
194 unmapped targets, 44 indirect targets, seven runtime callbacks, five
runtime-body/decode conflicts, four unsupported delay slots, two blocks crossing
load boundaries and two scope effects. Strict adds two ERET return obligations
and one indirect-site obligation. There is no invalid-table-entry blocker.

Concrete next sources include `7f00b134`, `7f00b238`, `7f00b47c`, `7f00c408`
and `7f00d828`. Page-end transfers also expose the need for an authenticated
cross-page instruction/delay-slot representation: placed `8093fffc`,
`8094dffc`, `80a33ffc`, `80a4affc`; crossing-load blocks at `80a49fd0` and
`80a5cffc` remain refused. Synthetic placement is not a guest runtime address.
The refill's unsupported TLBWR remains virtual `70001b94` / placed `80801b94`
(actual vector execution `80000034`); another scope effect is virtual
`7000d330` / placed `8080d330`. Do not bypass either or replace the page pool
with a permanently contiguous physical binding. General exception entry,
Context/Random/Wired state, source-authenticated unvisited pages and later
mapping/eviction generations still need verified contracts.

Timing observations: the first cold baseline pipeline's log spans 138.011 s;
the expanded candidate spans 534.009 s amid concurrent compilation/game work.
They perform different coverage workloads and are not a performance comparison.
The standalone requested-page replay reports 8.029 s for 67,137,998 interpreter
calls. Source-only batching captures multiple requested pages per bounded replay;
excluding declared mapped text prevents duplicate source requests without
changing that text. All replay timings and cache identities remain in ignored
receipts, rather than a speedup claim from unequal maps.

The complete canonical commands are recorded by `target/gate.py` into
`target/full-gate/results.json` (preflight) and `target/final-gate/results.json`
(final tree). They are fmt, locked workspace/all-target Clippy with warnings
denied, full locked workspace tests, CLI tests, and the full runtime suite
including native/pinned-reference state/RAM contracts and the complete ares
harvest suite. Silent visible 30-second control commands and their return codes,
time-limit/fault records and elapsed times are retained in
`target/verified-bk.json` and `target/verified-mm.json`. Final integration requires
all five local gate results and both controls to pass; their exact results and
CAS base/landed commit are in the issue #4 closeout and ignored landing receipt.
README and progress data are unchanged.

## Recovery on current main

The prepared uncommitted candidate above was recovered from the expired
`ge-paging-20261023` claim, preserving the original worktree and evidence.
Integration base: `378804c3125c599218ef80d2dc965b9409df6476`.
ADR number reconciled to 0255; no game constants were introduced.
Fresh exact-tree validation receipts live in this worktree under
`target/recovery-gate/`, with fresh pipeline and control logs under `target/`.

Fresh recovery measurements reproduce 4706 -> 9035 blocks, 0 -> 48 engine
pages, 175/172 -> 592/589 ordinary/residual blockers, and 81/85 original
direct edges now decoded. Remaining original edges target 7f010290 (three)
and 7f08fe74 (one). `target/recovery-summary.json` records the exact counts
and blocker classes. Normal pipelines refuse as required (exit 1).
Baseline/expanded end-to-end times: 274.641/196.988 seconds; the former
includes cold release compilation, and replay cache/coverage workloads differ.
These numbers are not evidence of a speedup.
Fresh in-memory mutations are caught, and the added ambiguous-image negative
refuses before source-only replay. The locked ares revision and local ROM hash
were independently rechecked; the retained 7f000000 capture again matches
raw ROM at 34b30 without introducing that empirical relation into production.
