# Guarded flag cells for branch pruning: negative result

Date: 2026-10-15. Milestone: 5 (OoT), measured at base 21265ef (ADR-0146).
Decision: ADR-0147.

## Question

OoT US 1.2 with its declared `code` segment has 28 guarded blockers. 7 of
them are calls into the 64DD driver at `0x801c7740..`, which ships on the
64DD disk, not on the cartridge. Each call sits behind
`lbu t, 0x80121ae2; beqz t`, and no closed store writes that byte. Can a
general *guarded flag cell* prove such branches one-way?

The idea: a fixed-address cell that a block loads and tests against zero
has a value set made of its initial value plus every constant written to it
by a constant-address store. Native code would check every store and
runtime write that overlaps the cell, so the cell could never leave that
set. If every value decides the branch the same way, the other edge is dead,
and blockers reachable only through dead edges drop out.

## Prototype and measurement

A prototype (not landed) worked as follows:
- It recognized `load cell; ...; beq/bne cell-reg, zero` at the end of a
  block, with the address constant within the block.
- It computed value sets from in-block constant-address stores. A partial
  store, or a store of an unknown value, rejected the cell.
- It recomputed liveness from the entries, callbacks and indirect
  candidates, skipping dead edges.
- It discharged dead-path blockers in the guarded scope.

Two corrections were needed before the numbers meant anything:

1. **Initial values.** Cells below the images include the IPL3 system area,
   for example `0x80000300` (`osTvType`), which IPL3 writes, so it is not
   zero. Cells inside the IPL3 window take their "initial" value from ROM
   bytes that boot code later clears as BSS. Only cells above every image,
   the program's zero-initialized static storage, can take zero as their
   initial value. That needs a new assumption: RDRAM above the images reads
   as zero until written.
2. **Cross-block writers.** A `lui at` in one block followed by a store
   through `at` in the next looks like an unknown-address store. The
   prototype rejected a cell when an unknown-base store's offset matched the
   cell's `%lo`.

With both corrections, OoT shows:
- 15 cells above the images decide 22 branches and make 163 of 7684 blocks
  dead.
- The guarded blockers drop from 28 to 20. 6 of the 7 64DD calls go, and so
  do 3 of the 21 function-pointer sites.

## Why it does not land

The value set is only as good as the census of writers, and the census
cannot see writes through pointers. Several of the 15 cells sit among
scheduler and audio globals (`0x80128524..0x8012bada`), where code
typically writes through a context pointer passed as a parameter: the
offset is the field offset, and the base is unknown. Neither the in-block
rule nor the `%lo` rule matches those stores.

For such a cell, `{0}` is the census's blind spot, not a fact about the
game. Pruning would then delete live code. Natively, the guard would fault
on the first legitimate write, so the artifact fails closed. But the
CLOSED claim would rest on an assumption that the game is likely to
violate during normal play. That is the same reason ADR-0142 rejects
runtime-checked guesses.

A sound version needs to know every store that may alias the cell: points-to
analysis for store addresses across the whole program, plus write summaries
for runtime functions. That is the analysis ADR-0142 found out of reach.

## Result

No code changed, and the prototype was reverted. OoT stays at 28 guarded
blockers. The 64DD calls stay open, as does every branch on a fixed-address
cell. Revisit this together with store points-to (ADR-0142) if SM64 needs
it.
