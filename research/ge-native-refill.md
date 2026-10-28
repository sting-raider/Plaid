# Native TLB refill investigation

Worker: ge-runtime-53fd3b3e. Prepared base: f1284ab8. No child agents.

Hypothesis: the lowered target 7f000bd0 must first take the guest's architectural
TLB exception; importing a captured mapping would bypass its real page loader.

## Natural pinned-ares observation

`experiments/tlb-refill/trace.py <local ROM> 0x7f000bd0` executes the untouched
ROM with the pinned 9408cb43d4948fc3ea6e152a307a34348df3fe04 Windows interpreter.
Instrumentation reads state only. No PC, mapping, RAM, or random state is injected.
Raw traces, vector bytes, generated licensed oracle and other game data remain
ignored under `target/refill-trace-complete/`.

At instruction call 23665344 the target is unmapped. Status is ff01, Wired=2,
EntryHi=70000000, Context=0, Cause=0. Only kernel mappings exist; the engine pair
is absent. The failed instruction fetch enters 80000000 at call 23665345:
BadVAddr=EPC=7f000bd0, EntryHi=7f000000, Context=XContext=003f8000,
Status=ff03, Cause=8, BD=0. ASID remains zero.

The fast vector reads Context, obtains the page-table base through the pointer
at 8005e4a4, reads its indexed PTE, stages PageMask=0, EntryLo0=1/EntryLo1=41,
executes TLBWR and ERET. Both pages are invalid. This is an intentional transition
to the general exception path, not a completed engine mapping. The retry at
23665364 enters 80000180 at 23665365. That vector jumps to 700101a0; the game
pages in the engine through its general handler and returns to the faulting PC.

At call 23818925 the target is retried, takes the fast vector again, and at
23818940 the installed global valid dirty cached pair is EntryLo0=d01f and
EntryLo1=d05f, EntryHi=7f000000, PageMask=0. Physical backing is 00340000/00341000;
the target fetch is physical 00340bd0. At 23818945 it executes successfully.
The reference stop is after that instruction, PC7f000bd4, VI74. Reference VI is
analysis evidence, not native runtime progress. The first trace's 256-instruction
limit was inadequate to observe demand paging; the retained script now records
the first128 instructions, mapping changes, and target retries until capture.

`cpu/exceptions.cpp`, `memory.cpp`, `tlb.cpp`, `interpreter-scc.cpp` and the ISC
license were read at the exact pin. Ares uses a PRNG sample within Wired..31,
or a six-bit sample for Wired>31. It does not establish an instruction-clock
Random implementation. No upstream implementation body was copied into Plaid.

## Exception-state candidate

Native state now distinguishes Context/XContext PTEBase knowledge from their
read-only BadVPN/region fields. The bounded kernel32 TLB exception transition
updates BadVAddr, EntryHi VPN/region with retained ASID, both Context registers,
Cause, EPC/BD and EXL, selecting BEV and refill/general vectors. Nested EXL
preserves EPC/BD. Unknown prerequisite state and unsupported addressing refuse
atomically. Explicit Context writes still cannot authorize full Context reads.

`python runtime/test_tlb_exceptions.py` passes60 full-state comparisons against
actual pinned-ares faulting fetch/load/store instructions, across positive and
negative32-bit addresses, miss/invalid/modification, delay slots, EXL and BEV.
Register/FPR/HI/LO, PC, memory and LLBit are compared; four mutations (BD, vector,
Context and nested EPC) are killed. The test is included in the runtime gate.
This candidate alone does not execute vectors or advance the native game.

## Remaining implementation

Authenticate/discover the copied vectors; preserve independently justified CP0
state across native SDK calls/context switches; establish Random selection;
execute the lowered fast and general handlers; represent checked ERET retries
and data-access delay slots without executing guest instructions at runtime.
Retain source-identity, mapping-generation and suspended native-frame guards.
Full local exact-tree gates and silent visible game controls precede any landing.
No logo/title/native-completeness claim is made.
