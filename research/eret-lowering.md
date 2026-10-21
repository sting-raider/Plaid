# Bounded native ERET and aligned load destinations (ADR-0237)

Prepared base: 3c8fb8f76f4dadfde6ade2a5f882c1bae19f0320.
Hypothesis/claim: explicitly known guest return registers outside SDK contexts
can support a checked native ERET without pretending that HLE exceptions enter
guest vectors. This advances automatic executable coverage and native lowering.

## Runtime boundary

Plaid's exception/interrupt/thread HLE remains authoritative. It does not invoke
guest exception vectors, produce EPC/ErrorEPC, or expose a guest exception frame.
No such provenance is invented here. A guest-written EPC (register 14) or
ErrorEPC (30) is known only until a runtime boundary or context restore clears
cp0_known. MFC0/DMFC0 and MTC0/DMTC0 preserve full return-register values, as the
pin does. Unknown reads/returns fault 12.

The supported ERET is an explicit guest-controlled kernel/boot return, outside
SDK threads. Known Status must have EXL or ERL. ERL selects ErrorEPC and clears
only ERL (EXL survives); otherwise EPC is selected and EXL clears. LLbit clears,
FR and all other Status bits remain unchanged, and the next PC is the selected
aligned sign-extended 32-bit target. Unsupported state faults before mutation:
unknown Status/selected return register, SDK thread context, unsupported return
mode/address width/alignment, or a transition that enables interrupt sources.
IE itself is unchanged, so the HLE ints_enabled mirror remains consistent.
With no newly eligible CPU interrupt source, no HLE message, event, timer or
thread scheduling action is triggered by this supported transition. Pending
sources remain owned by the existing HLE policy. No cycle-accurate timing or
Count progression is claimed. General guest-handler vector entry, EPC production
on an exception, and guest/HLE exception-frame unwinding remain unsupported.

The target is not certified by an observed EPC value. Strict solve retains
an eret_return_target_unknown obligation; residual mode records each ERET site
and dispatches only to compiled local labels/native entries, faulting 3 elsewhere.
Unknown-target refusal happens after the supported architectural transition.
There is no delay slot, decoder, interpreter or JIT. native_complete stays false.
The solver re-derives this obligation from source even if diagnostics are deleted.
Discovery's existing terminal ERET representation is unchanged.

## Independent reference and synthetic checks

Pinned ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 is clean. Inspected ISC
LICENSE, interpreter-scc.cpp ERET/MTC0/DMTC0/register 14/30 and CPU state/LLbit.
No upstream implementation is copied or linked into Plaid's native artifact.
The project-owned runtime/test_eret.py executes actual lowered guest writes,
ERET and LL/SC for EXL, ERL and ERL+EXL, both FR modes, both return-register
move widths, and compares complete GPR/FPR/HI/LO/FCSR/PC/Status/LLbit and coherent
RAM with the pinned interpreter. A following invalid instruction proves that
ERET has no delay slot. The next return uses explicit target roots rather than
manufacturing static closure. Unknown, SDK, event-enabling, wide and unaligned
states refuse atomically; an undiscovered return target faults 3 after effects.
The ordinary COP0 boundary-invalidation and runtime event/Status fixtures remain
in the full gate. Deleting only LLbit clearing in an ignored generated C copy
fails the retained fixture with exit 3221226505; production code stays intact.

## MK64 discovery diagnosis and generic correction

These are four calls and four corresponding missing destinations, not eight
independent code images:

| Caller | Target | Raw ROM offset |
| --- | --- | --- |
| 80001f48 | 80281548 | 124b88 |
| 80001f58 | 802802ac | 1238ec |
| 8000273c | 80281968 | 124fa8 |
| 80002764 | 80280420 | 123a60 |

The loader at 8000105c builds ROM start 123640 and end **12aae0** (the
ADDIU low half aae0 is signed), computes/rounds their difference, and calls
80001158 with a0=80280000 supplied by a lone LUI in its call delay slot at
800010a0. Its wrappers also clear/cache-maintain the destination. Calls at
80002734/8000275c load this image before two of the missing calls; the other
calls are reached through a game-state switch. The distinct inferred image at
8028df00 comes from ROM f7510 and cannot supply any of these four addresses.

Destination candidates previously required a LUI plus ADDIU/ORI low half.
static_loads now also considers a LUI's complete 64 KiB-aligned value, with no
change to ROM range/source selection, unique placement or function-start score.
The recovered 0x74a0-byte raw image scores 196/196 internal calls at 80280000.
A synthetic removed-low-half positive and misplaced-address refusal are retained.
No ROM identity, game address or constant enters production code.

The map grows 40610 -> 41631 blocks. Ordinary OPEN 13 -> 4 (three unresolved
indirect sites plus ERET target); residual 10 -> 0, with four residual sites.
This permits a validation artifact, not a fully-native closed-world certificate.

## Requested normal ROM pipelines

Both commands are python scripts/native.py <local ROM> --rt64 --seconds 60.
GoldenEye returns 1 at analysis refusal, 26.041 s: 3716 blocks, OPEN 339 ordinary /
327 residual (12 sites). Its previous two ERET instruction/scope pairs become
two return-target residual obligations; table bounds, targets, callbacks and
one other scope effect remain. No native executable/window/VI/audio is reached.

MK64 builds an RT64 validation executable with 38 ROM-derived RSP texts and
native_complete:false, then returns 1 after an immediate native stop. Pipeline
228.187 s; VI 0, graphics tasks 0, audio tasks 0, PI DMAs 0, framebuffer 00000000,
fault 11 at 800cc0f4 (ra 800cc0fc, a0 01000800). This is the existing Status/FR
boundary before the first COP1 control write, not ERET execution or accepted
60-second gameplay. No BK/MM native regression is modified. Window launch is
visible. Screen contents could not be independently inspected: the Computer Use
helper returned 'failed to connect native pipe ... (os error 2)'. Zero-frame
telemetry is not claimed as an observed screenshot.

## Discovery controls and timings

Retained declarations/runtime IDs are rerun through current release discovery:

| ROM | Blocks | Prior seconds | Current seconds | Complete-map SHA-256 |
| --- | ---: | ---: | ---: | --- |
| BK | 81465 | 29.020 | 26.368 | b41011d9f0a7d626a49ca6cebfe0b042dd27c606cf69cec7efb427745b2b9467 |
| F-Zero X | 28119 | 4.802 | 4.780 | 92ef76696f942aa543b11f43bd073fb25137937cb7ab93039135e221d850c05f |
| MM | 214963 | 173.214 | 217.630 | a52eb0e427e338a178a99b82d1fd8e996ac203c94f48905317b1b734cefc0603 |

All complete maps are byte-identical. These before/after operational times run
amid other local builds; they do not establish an algorithmic speedup/regression.
Warm release compilation took 52.47 s amid differential/core tests; no compiler
speedup is claimed. ISA coverage 203/209 -> **204/209 (97.6%)**, with ERET counted
only under explicit residual dispatch and checked runtime state. No assumption
is retired. tools/progress.py regenerates checked coverage and must pass --check.

Ignored evidence: target/eret-0237/{games.log,*-final.log,*-run.json,*-ordinary.json,
*-residual.json,discovery.json,*-map.json,mutation.json}; target/eret-contract/.
Canonical gate: python X:/Plaid/target/paper-mario/0222/gate.py with
GATE_TREE=X:/Plaid/target/cop0-0235, GATE_OUT=X:/Plaid/target/eret-0237-gate.
All five steps must return zero; the full unfiltered Rust suite must really run
on the final tree. Final timings/commit identity follow in the integration receipt.

Remaining: MK64 Status/FR startup fault 11 (left to the existing regression
investigation), guest-vector exception entry and scheduler-frame contracts,
EPC production/event-enabled ERET, broader GoldenEye source/table closure,
TLBWR/Random, Count/Compare/Cause, CACHE and whole-ROM coverage.

## Prepared-tree validation and review

The developmental five-step gate returns zero throughout: fmt 1.2 s, Clippy
7.4 s, full workspace tests 40.5 s, CLI 5.5 s, runtime 291.5 s (346.1 s summed).
The Rust suite actually compiles and runs **910 passing tests, one ignored**.
Its logs are preserved as target/eret-0237/initial-gate. Review then makes the
nonselected EPC/ErrorEPC point at an invalid word, strengthening selection
coverage, and clarifies the residual-only coverage-probe comment. The final
complete gate must rerun after documentation/source freeze before canonical CAS.

Review covered correctness, readability, architecture, trust boundaries and
bounded work. A deleted ERET diagnostic cannot forge strict closure because
source-derived expected CFG supplies the obligation. Status/EPC state is never
borrowed from HLE contexts. Unknown dispatch is an architectural transition plus
fault, not atomic state refusal. The low-half-free destination remains only a
candidate under unchanged placement/source checks; ambiguity remains refused.
No production dependency, game constant, guest decoder or fallback is added.
The historical DECISIONS working bytes remain an exact 414837-byte prefix.
