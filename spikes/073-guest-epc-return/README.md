# Guest EPC writers compose with ERET and executable ancestry

Controlled v16 extends the existing continuous handler graph at exact ISC ares
9408cb43d4948fc3ea6e152a307a34348df3fe04. Run `python run.py`; use
`--verify-existing` to recheck retained controls without rebuilding. Artifacts
stay ignored under `target/guest-epc-return-primary`.

After BREAK transfer332 and handler writer348/invalidation353, actual MFC0
read358 supplies GPR8 from the live EPC. MTC0 writer363 writes the same full value
but creates a fresh generation. ERET368 selects that writer, and returned
fetch370/fill372/decoder374 consumes replacement NOP with writer348 and earlier
DMEM/DMA/RSP byte parents. No host PC setter drives handler/return execution.

The 375-event complete source matches independent replay. Baseline, disabled,
enabled and repeat agree on 41 CPU steps and 59 full reported machine/cache/CP0/
pipeline controls; enabled sources repeat exactly. Completed EPC snapshots run
after the epilogue but before pipeline.end, so ordinary MFC0/MTC0 snapshot PC is
still the decoder PC. Exact guards retain sign-extended MFC0/full-source MTC0,
EPC setter and earlier exception/cache/DMA contracts.

Separate CP0 held-read ancestry from SP/RAM load provenance. Equal-value MTC0
replaces selected writer identity. LW/XORI/ADDU rewrites and opaque roots cut
held CP0 ancestry, even on equal values. A second write needs a current read;
it cannot reuse an ended generation. Tests insert same-value XORI/ADDU and a
second MTC0 into the full cached handler graph and require exact ancestry errors.

Only uncut kernel32/ERL0/IE0 frames and current-read/same-value EPC round trips
are admitted. Changed targets, other CP0 writes, ErrorEPC/ERL/interrupt/reset/
restore/root/census/mapping/lifetime/whole-ROM/native remain OPEN. All flags false;
static ERET remains unsupported. All sixteen earlier actual report bytes stay exact.
