# Primary composition: SP captured writers to executable backing consumption

Base: d4316ef9216eb593e8683f093beba8138cb8d9f6. Claim: 6113115229.
Source: canonical sp_history v3 and its authenticated actual CPU SP sensor;
bounded-boot-sp-history.md and retained exact-pin receipts. PR #29 candidate
rsp-imem-install @ db66c527a8761b5804fe5872e7b03d362671d9c1 reviewed for per-byte
supersession. Request/promotion lifecycle remains unconsumed; do not close PR #29.

Hypothesis: compose actual captured SP storage sink occurrences with the existing
exact CPU executable read context rather than adding another independent event
ledger. New opt-in replay uses the same complete canonical stream/projection and
returns the entire old report unchanged. Both history and paired fetch sources
must match independently preserved expected hashes.

Track 8192 bank bytes. CPU/other observed Word sinks and normalized 4/8-byte DMA
sinks mint candidates from raw write ordinals. DMA candidates retain an actual
matching backing-read ordinal where available; absence stays unbound. Equal-value
Word writes supersede prior DMA candidates. Preserve physical fetch identities
separately from mirrored bank/offset storage. Actual contradictory reads cut only
incompatible bytes; later matching payloads cannot revive them without new sinks.
Each actual eligible fetch retains its candidate snapshot, discrete endpoints
and raw read identities, plus an ordered typed-result digest.

This is compatibility with the latest captured writer, not ultimate provenance:
v3 does not provide complete ordinary RSP/out-of-band initialization/mutation
coverage. Ultimate ancestry, mutation census, executable lifetime and native
flags remain false. No new observer, sensor format, primitive assumption,
request identity, decoder/executor or solver waiver. ADR-0116.

Four unit adversaries PASS: equal-value CPU replacement with untouched DMA lanes;
per-byte permanent cuts/fresh writers; bank/end-offset/8-byte indexing separation;
partial and unknown candidate counts. CLI complete-source scenarios PASS: full
legacy equality, bound DMA/CPU supersession, partial contradiction followed by
equal reads, no writer, source mismatch, report forgery and input protection.
Legacy SP CLI and canonical CLI tests pass.

Retained actual 10,000-call source replay passes without emulator rebuild. The
prior entire report authenticates to the canonical receipt:
a9694b37a287e5f6ce0ec92c32ac94149e651b055ef7248b41b17b9b02d3229e.
All 7945 SP executable backing reads retain compatible captured writers; 1663
captured sinks, zero contradictory byte candidates in that prefix. New ordered
candidate digest 98f34ddeedff83b976ccb1c837ec1d6836c24e1c30777bbdfe8b7ed9c159ed57;
new complete report SHA256
06375101bba8d61b67b8ddebc3e12976494c25e343bd9c5773b27e8812017449.
The entire nested legacy projection equals the retained report. Scope remains
supplied-firmware NTSC/6102/8-MiB/deterministic/PIF-HLE single-run finite capture,
not suite completion or a game/whole-ROM proof. Exact relied-on clean pinned ares
HEAD/files checked; canonical sensor contracts reused. No redundant reference build.

Full LOCAL gate PASS: fmt check; strict locked workspace/all-target Clippy; full
locked workspace including actual outer fixed-point deletion adversary; canonical
CLI; new composition CLI; legacy SP CLI; diff check. Logs and captured reports:
target/sp-writer-primary (ignored). Progress milestones unchanged. No Actions,
branch workflows, raw research/module merge or upstream production copying.

Separately, the supplied user's ROM checksum uses pinned mia source only in an
ignored licensed diagnostic. Seed 0x91 returns 0x8618a45bc2d3, identifying CIC-6105.
Current 6102 boot profiles remain unchanged; no wrong-profile run was performed.
The conditional static baseline and all ROM/trace/map bytes remain local ignored.

Remaining: decoded CPU/RSP producer ancestry, PIF/ROM initialization, general SP
mutations/census, promoted request/read source identity, epoch/cache/mapping/restore
composition, actual RSP execution, root universe and whole-ROM/native closure.
