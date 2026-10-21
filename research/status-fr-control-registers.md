# Status.FR and COP1 control registers (ADR-0238)

## Claim and diagnosis

Prepared against main 584b0eaf8c816746b2272c4ce73c0f5f9459c074 in
target/cop0-0235. The initial hypothesis was a missed native Status.FR writer.
Inspection disproves it: ADR-0235's plaid_cp0_write already masks Status and
sets fr_mode from bit 26 after every accepted MTC0/DMTC0 Status write. Boot
receipts do the same. SDK thread restores establish FR=0 and reject saved
FR=1 in the verified SDK ABI. ERET changes EXL/ERL, not FR; interrupt-mask,
CU1 acquisition and osInitialize writers also preserve FR. No writer fix is
needed in this cluster.

MK64's retained fault is at the HLE boundary for signature-identified
__osSetFpcCsr, before its first runtime thread, VI or task. Its startup reads
Status at 800d1b40, ORs CU1 and calls the actual lowered MTC0 Status helper
at 800d1b30. This preserves boot Status 34000000, including FR=1. The next
call at 800cc0f4 enters the helper at 800d1b50: CFC1 v0,FCSR; CTC1 a0,FCSR;
JR ra; NOP. It does not access an FPR. The runtime incorrectly demanded the
FR=0 FPR layout for that helper. Lowered CFC1/CTC1 had the same unnecessary
layout check. No commercial instruction bytes or assets are retained in git.

## Reference and change

Exact ares pin: 9408cb43d4948fc3ea6e152a307a34348df3fe04, clean checkout.
ares/n64/cpu/interpreter-fpu.cpp CFC1/CTC1 (425-433) check CU1 and call
getControlRegisterFPU/setControlRegisterFPU without consulting FR. By contrast
fgr_s/fgr_t accessors select FPR storage using floatingPointMode. The Status
setter in interpreter-scc.cpp (185-216) explicitly assigns bit 26 and invokes
setFloatingPointMode; the latter does not shuffle stored FPR bits at this pin.
These are reference semantics, not a hardware-equivalence claim.

plaid_status_cop1 now shares the existing CU1 acquisition/refusal policy.
plaid_status_fp retains its exact fail-closed layout check, then calls that
CU1 helper. Only CFC1/CTC1 and their __osSetFpcCsr HLE equivalent use the
layout-independent gate. Other operations, including COP1 branches, keep their
previous checks. No map assumption, decoder, fallback, dependency or game
constant is added. fr_mode's comment now describes actual writer-derived state.

License decision: inspected pinned ares LICENSE (ISC core and separately
preserved bundled notices). Original project-owned fixtures use the existing
separately licensed oracle builder; generated reference sources/binaries/notices
stay ignored. No upstream implementation is copied or linked into native mode.

## Deterministic contracts

runtime/test_status.c reproduces the original HLE failure: the new boot-FR=1
__osSetFpcCsr assertion fails before the fix. With the fix, both FR modes,
with and without complete Status knowledge, preserve mode while returning old
FCSR and setting rounding/condition bits. CU1 off outside an SDK context still
faults 11 before FCSR mutation; genuine FR mismatches still fault 11. Existing
256-case pinned-ares SDK masks/context/events and single/multipart lazy-CU1
thread tests remain in the gate.

runtime/test_fr.py lowers an original synthetic instruction sequence for both
map layouts. The guest performs three native Status writes, FR=1 -> FR=0 ->
FR=1, and CFC1/CTC1 in each mode. Both translations must match unmodified
pinned ares in complete reported GPR/FPR/HI/LO/PC/FCSR/condition state, Status
and the full 256-byte coherent RAM projection. Distinct FPR sentinels check
nonmutation. Restoring the old FR gate only in ignored generated C must fault
11 in both map layouts; restored translations pass again. Existing COP0 and
ERET contracts retain refusal atomicity, PC, exceptions, LL/SC and event gates.
The new fixture enables no events and uses bounded nontrapping FCSR values;
instruction-level timing and general guest exception delivery remain outside
this contract.

An accidental overlap of two exploratory oracle builds caused a WSL
"Text file busy" launch error. Neither result was treated as semantic evidence;
the final sentinel fixture and canonical runtime gate run sequentially.

Ignored evidence: target/fr-0238 (logs, diagnosis, game and mutation receipts),
target/fr-contract (synthetic oracle/native outputs), and the external canonical
gate directory X:/Plaid/target/fr-0238-gate. User ROMs remain local and ignored.
