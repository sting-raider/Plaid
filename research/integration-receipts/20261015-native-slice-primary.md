# Primary integration: synthetic native vertical slice (milestone 1)

Base: 1696f68. Milestone: 1 of the ADR-0125/0126 plan. Worker: Claude
co-integrator, user-authorized on main.

New `crates/plaid-lower` lowers a map the solver reports CLOSED under the new
`DeclaredStaticImagesGuardedRam` scope to one C translation unit: blocks become
labels, direct transfers `goto`, indirect jumps a `switch` over the proven
target set with a fault default, and every instruction outside the supported
integer subset rejects the program. Semantics follow the pinned ares
interpreter, including sign-extended 32-bit results, ares's 35-bit MULT operand
and its divide-by-zero results. No guest decoder or interpreter is emitted.
`plaid lower-c <words.bin> <base> <entry> <exit> <out.c>` runs discovery,
solve and lowering.

The new solver scope admits RDRAM data loads/stores and pure compare/HI-LO
arithmetic, and adds an explicit assumption: stores never reach executable
bytes and each 16-byte line is accessed through only one of KSEG0/KSEG1. The
native runtime checks both on every access and aborts (faults 2, 4). The
original `DeclaredStaticImages` contract and its tests are unchanged.

Spike096 on pinned ISC ares 9408cb43 (recompiler disabled): alu, muldiv,
loops, memory and transfers match exactly on PC, all GPRs, HI, LO and a
256-byte CPU-coherent RAM window. Ordered-state SHA256s are in the ignored
receipt `target/native-slice/receipt.json`. `self_modifying` faults 2 and
`cache_alias` faults 4 natively, as required. Host compiler: MinGW-w64 GCC,
x86-64, `-O2 -std=c99 -Wall -Werror`.

Findings: (1) the first memory corpus mixed KSEG0 and KSEG1 on one line and
diverged, because the VR4300 D-cache is write-back; this became the fault-4
assumption instead of a silent coherent model. (2) `jr $ra` has no closure
proof, so no program with a function return reaches CLOSED; that is the next
discovery requirement in NEXT.md.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests (new plaid-lower and pipeline scope tests included),
`scripts/test_cli.py`, spike096 differential run, `tools/progress.py --check`:
all PASS. No Actions. `native_complete` stays false everywhere.
