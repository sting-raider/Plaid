# Primary integration: COP1 data moves

Base: 867a9b0. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main.

ADR-0131: the guarded scope admits COP1 data moves (`MFC1 DMFC1 MTC1 DMTC1
LWC1 LDC1 SWC1 SDC1`) under an explicit CU1 = 1 / FR = 1 assumption. The
assumption is listed only when such moves are present. `plaid-lower` adds
`u64 f[32]` and follows ares's FR = 1 register views (read from `.refs/ares`
`ares/n64/cpu/interpreter-fpu.cpp` at 9408cb43).

Spike096 on pinned ISC ares 9408cb43, oracle rebuilt: the oracle and harness
now print all 32 FPRs, and the oracle pins CU1 and FR. The new `fpu` program
(high-word preservation on `MTC1`/`LWC1`, `MFC1` sign extension, `LDC1`/`SDC1`
round trip, odd FPR) and the nine earlier programs match exactly. The four
negatives still fault 2, 4, 5 and 6.

OoT US 1.2 local measurement, with the same heuristic runtime declarations as
ADR-0130: 613 blocks and 3 guarded-scope blockers (boot return `0x8000058c`,
memory-loaded `jalr` `0x80000f10`, jump table `jr t2` `0x80003acc`).

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096 differential run,
`tools/progress.py --check`: all PASS. No Actions. `native_complete` stays
false everywhere.
