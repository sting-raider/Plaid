# EPC transform targets compose with returned executable ancestry

Controlled v17 extends spike073's actual live handler/EPC/cache graph at exact
ISC ares9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py` or
`--verify-existing` to reuse controls. Artifacts stay ignored under
`target/epc-transform-target-primary`.

BREAK transfer332 saves EPC6028. Handler LW342/read343 feeds separate CPU
writers348 at6028 and353 at602c. CACHE358 ends fill329. MFC0 read363 -> XORI367
changes6028 to602c -> MTC0 writer372 -> ERET379 selects the new current EPC.
Returned fetch381/burst382/fill383/decoder385 consumes known NOP at602c with
writer353/load342/read343/DMEM ingress152/RAMwriter58/original RSP ancestry.
Handler and return execute naturally without host PC setters.

The386-event complete source matches independent replay. Baseline/disabled/
enabled/repeat agree on43 CPU steps and61 complete reported machine/cache/CP0/
pipeline controls; enabled sources repeat exactly. EPC accesses retain the
post-epilogue/pre-pipeline.end snapshot boundary. Handler ERET at1a0 has a distinct
fresh fill376 with honest unknown initial-code parents, separate from returned
fill383 with captured RAM writer parents.

Reuse the existing full64/unsigned-u16 XORI receipt on a held current EPC read.
Keep original read bits, transform and completed writer separate. ERET/later
MFC0 select the latest writer's completed EPC, never the old exception capture.
Repeated/renamed/unattributed transforms and opaque roots cut candidate ancestry.
Old v16 still cuts transforms; all seventeen earlier report bytes stay exact.

Only bounded uncut kernel32/ERL0/IE0 current-read/single-in-place-XORI writes are
admitted. Other transforms/arbitrary CP0 sources/ERL/interrupt/reset/restore/
mutation/mapping/root/lifetime/whole-ROM/native remain OPEN, all flags false and
static ERET unsupported. No upstream implementation copied/linked.
