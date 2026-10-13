# Writer ancestry reaches exception transfer and first handler fetch

Original controlled v14 extension of spike070 at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`; use
`--verify-existing` to recheck controls without rebuilding. Outputs stay ignored
under `target/writer-break-handler-primary`.

Actual LW300/read301 supplies NOP parents from DMEM ingress/RAM/RSP ancestry.
CPU SW306/writer307 copies NOP to handler RAM180. XORI312 then produces BREAK13,
and CPU SW317/writer318 installs it at6028. Guest CACHE323/invalidation324 ends
the old fill; burst328/fill329 expose BREAK to decoder331. The captured exception
transition332 derives the BEV0/general root, cause9, EXL and non-delay EPC from
the actual decoder before/after states using the canonical root resolver.

After decoder completion333, first root fetch334/burst335/fill336 and handler
decoder338 retain the separate handler CPUwriter307 parents. The fixture checks
the actual exception PC for the handler and does not call the host PC setter.
Required root fetch/decoder identity cannot be replaced by opaque reseeding,
unrelated actors, equal bytes or a truncated post-exception source.

Baseline/disabled/enabled/repeat agree on34 CPU steps and52 complete reported
machine/cache checkpoints, each hashing all512 I-cache tuples. Enabled sources
repeat exactly. Independent complete source/image/definition/cache/root/parent
graph matches Rust. The source guard authenticates exact exception/EPC/vector
implementation alongside prior cache/DMA/memory guards.

Only non-delay, non-nested, BEV0/kernel32 BREAK and its immediate cached handler
entry are admitted. Captured incoming pointers/registers remain unknown roots.
This is one source-bound exception occurrence and first handler consumption;
complete exception/interrupt/TLB/reset/restore/root/lifetime/whole-ROM/native
coverage remains OPEN. Every general certification flag stays false.
