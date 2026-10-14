# Primary integration: 64-bit integer subset and checked overflow traps

Base: a85d679. Milestone: 3 (real code under declared assumptions). Worker:
Claude co-integrator, user-authorized on main.

`plaid solve <rom> <map> --guarded-ram` solves under
`DeclaredStaticImagesGuardedRam`. On the local OoT US 1.2 conditional window
it first reported 143 blockers, 130 of them instructions outside the scope.

ADR-0128: the guarded scope admits the VR4300 doubleword integer ops, `LD`/`SD`
and the overflow-trapping `ADD`/`ADDI`/`SUB`, under an added assumption that
trapping adds never overflow. `plaid-lower` lowers them with ares semantics
(read from `.refs/ares` `ares/n64/cpu/interpreter-ipu.cpp` at 9408cb43) and
aborts with fault 6 on overflow. Branch-likely forms now lower too.

Spike096 on pinned ISC ares 9408cb43 (recompiler disabled): the new `wide`
program (64-bit ALU and shifts, `DMULT`/`DMULTU`/`DDIV`/`DDIVU` including
divide-by-zero and `INT64_MIN / -1`, `SD`/`LD`, taken and nullified likely
slots) and the six earlier programs match exactly on PC, all GPRs, HI, LO and
the RAM window. `overflow` faults 6 natively; the other negatives still fault
2, 4 and 5.

OoT guarded-scope blockers: 143 -> 82 (69 libultra system instructions: COP0,
`LDC1`/`SDC1`, `CACHE`, `CFC1`/`CTC1`, `BREAK`; 8 exception/invalid words; 2
delay slots; 1 indirect site; 2 unmapped-target). Whole-ROM: unchanged at 62.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 differential run,
`tools/progress.py --check`: all PASS. No Actions. `native_complete` stays
false everywhere.
