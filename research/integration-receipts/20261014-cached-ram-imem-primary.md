# Primary integration: cached operands through frozen RAM parents to RSP execution

Base:424268a6c4967d21eea556b953ecd6a935980492. Claim:6151904261.
Harvest canonical DcacheReplay/ADR0119/0121, retained actual spike034/pointer-read
contracts, current v24 CPU/RAM/IMEM graph and exact pinned D-cache callbacks.
No raw research/scaffold merge or second cache policy.

Controlled v25/fixture26 binds decoded direct-KSEG0 Word LW to actual backing
burst/fill/delivered read and full16-byte/tag/index/dirty resident snapshots.
Full CPU GPR/control/link/endian before/completed states and signed64 result
restrict kernel32/IE0/BEV0/EXL0/ERL0/non-delay/big-endian clean cached scope.
Existing actual RAM writes enter the same canonical state's backing diagnostics.
Capture RamByteOrigin at each actual backing burst, then derive delivered parents
through canonical BackingFill identity. CpuCachedRamLoad wraps decoder/read/
resident/physical byte/RAM parents inside existing CPU held expressions and RAM/
IMEM copies; it is not a separate installed SP writer or continuous lifetime.

Burst616/fill617 -> LW615/read618 selects RAMwriter595 (already retaining
handler473/DMEM/DMA/RSP ancestry); IMEM624/RSP626 consumes NOP. XORI631 derives
ADDU21, then actual uncached RAMwriter637 changes e02c. Cached LW642/read643
still delivers NOP from617/595; IMEM649/RSP651 retains those original parents
despite captured backing637/21. Actual HitInvalidateD657 ends617. Fresh burst663/
fill664 -> LW662/read665 selects637/21, then IMEM671/RSP673 consumes ADDU. Older
reads do not change. Cached payload equality and current RAM are not causal seams.
Both existing mapped root/return/I-cache graph and new operand/D-cache graph stay
connected to the original RSP/DMA/CPU producer occurrences.

Actual674 events/114 full existing machine/cache/CP0/pipeline/TLB controls,
86 CPU steps/31 RSP words/7 definitions agree baseline/disabled/enabled/repeat.
Full independent event/report graph agrees. Canonical D-cache projection has
23 original-clock primitives:15 captured backing Word mutations,2 backing reads,
2 fills,3 delivered reads,1 invalidation; no resident mutations/writebacks.
All TWENTY-SIX earlier report bytes remain EXACT; repeated/stale-source gates PASS.

Source:dad5c111b70c1276019571c3ee4bdc8bbef63710f47975261fc17e3db229a685.
Report:2024528a333297bf353c22f25b5df12996f7983da17931c746c796734f66e03f.
Baseline:770fff2267b95f79d27bacbc427b1314b98c5868fb214b85a8d21d6c0f35a648.
Build:0c963fd2eb304c467ee6c17ebfdaf2b87f9dcddc285c4e70c0455871374cd5d5.
Sensor:85b207a6648ffad42032a3b449f500c6cc8c6c2b09034c9451accbabbc8af0ab.
Build:a170e2d3a880aca9510ec84c71f8b3a577b08fca6afdb3bb8529df291176f9ef.
Results:6246e1a7ac1398a806fc81bef115c2b2e64b8c5316aa39be5cae4fecf2d79c88.
Exact clean ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04. Immutable
dcache.cpp:a1e2dd9c619cae7dbba4162eab8ab09a239f818019b50a88e49b09501488650b;
all prior source guards retained. Generated passive callbacks reuse the existing
completed fill/valid-clear/read boundaries; executing DataCache::read is hooked,
readDebug excluded. Results/state/timing unchanged in disabled/reference runs.
Ignored capture:target/cached-ram-load-imem-consumption-primary; reports:
target/cached-ram-imem-integration-primary; logs:target/cached-ram-imem-*.
No older reference/full-ROM rebuild, Actions, ROM/assets or upstream production reuse.

Focused63 Rust and complete actual/synthetic CLI PASS, with17 cached source/13
report forgeries plus all prior adversaries and shifted-lane positive check.
Missing/duplicate/misbound/inconsistent bursts/fills/reads, current backing used
as resident bytes, altered full tags/dirty/untouched lanes, omitted/misbound
invalidation/control/GPR results and stale/future physical/writer parents reject.
Pure negative-word regression checks full signed64 result and Unknown fill parents.
Clippy's larger pending-load variant is handled by boxing that internal optional
operand; all old report bytes stay exact. Synthetic reclocking updates nested
primitive ordinals as well as carrier ordinals; its shifted-lane check remains
separate from actual reference evidence. Older RAM-copy adversaries select their
actual producer contexts instead of the new tail. No lint/assertion waiver.

Canonical final-tree gate: cargo fmt --all -- --check; strict locked workspace/
all-target Clippy; full locked workspace tests; python scripts/test_cli.py;
git diff --check. Issue4 closeout records final results, exact-head CAS/fetched
verification. STATUS/NEXT/DEVELOPMENT/ADR0119 update production composition;
progress milestones unchanged. Warm unsensed/dirty/mapped/degraded/failed/other
accesses/cached mutation/writeback/global source/census/root/lifetime/whole-ROM/
native stay OPEN; all flags false, static ERET unsupported.
