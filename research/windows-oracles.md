# Native Windows reference oracles (ADR-0295)

Base: 131f0565. GoldenEye WIP remains separately committed as e787a696 (ADR-0294).
The migration removes every live WSL launcher from runtime/ and scripts/ and
shares the ADR-0254 native pinned-ares builder, instrumentation and cache.
No upstream implementation is vendored; existing ISC ares and GPL Mupen notices
remain with the separately built reference outputs.

Before migration, the complete runtime suite passed in 542.344 s. An additional
550.594 s legacy run captured 166 raw oracle invocations from 19 test modules,
including all 17 runtime WSL callers and boot/refill contracts. Inputs, driver
hashes, instrumentation manifests and raw output bytes are retained locally under
`target/receipts/windows-oracles/equivalence/`. Boot result files are compared too.

Receipts below were generated in the `target/windows-oracles` worktree; local
`target/` paths are relative to that checkout. The landing requires the final
exact-tree gate and a post-gate check that WSL has not started.

Native Mupen validation: all eight CPU/dynarec scenarios pass, as do all six
full-core device sessions. The mutation fixture has byte-identical Linux/Windows
CPU states and raw traces (untraced/traced/repeat); this exposed a stale assertion
which expected a byte mismatch instead of the existing intervening-store refusal.
Windows trace environment must be set before process creation because the C
runtime environment can otherwise predate Python's later environment updates.

Strict ares equivalence passed: all 166 calls, five driver builds and 55
boot result files, including matching absence for refused inputs. Aggregate
stdout/result SHA-256 (both routes): `fe5e9df90f765dca9c0cb4c218f656f9be5cb7dcfc7f22b6155fc1b844f4dff6`. Captured stderr
also compares byte-for-byte. The native-only cached replay took 22.172 s; this
is an equivalence-replay timing, not the runtime-suite timing.

WSL was shut down before native gates. The initial check reported no running
distributions; the final post-gate check remains required.

The supported spike096 main also had a stale callback-negative expectation:
active overlay writes now refuse with fault2 at store PC80000070, before a later
revoked return could fault8. The migrated runner asserts both fault2 and that
precise store PC; no compiler/runtime behavior changed. CPU/RSP runner locals
were renamed so direct native oracle calls cannot shadow their function names.

Additional RSP vectors exposed nondeterministic MinGW oracle results. The pinned
upstream `cmake/common/compiler_common.cmake` requires `-fwrapv` and
`-fno-strict-aliasing`; the standalone builder had omitted both. Match those
compiler semantics for the reference union/lane accesses and signed arithmetic.
All captured CPU/boot output and the vector suite must be revalidated after this
change. Retained Linux RSP outputs cover all 27 programs; WSL is shut down again
before the native/final gates. This changes reference build flags, not guest
semantics or instrumentation.

With the upstream compiler flags, all 166 CPU/boot outputs remain byte-identical
(aggregate SHA-256 `fe5e9df90f765dca9c0cb4c218f656f9be5cb7dcfc7f22b6155fc1b844f4dff6`), as do all 27 RSP programs.
A new gated synthetic `runtime/test_rsp_oracle.py` freezes the independently
retained Linux full-vector-state/raw-output digest. It includes PC, registers,
accumulator, flags and all reported memories, and detected the omitted flags.

The complete Mupen comparison now passes eight CPU scenarios and six device
sessions: raw CPU stdout, all 24 saved device CPU states and all 42 reference traces
compare byte-for-byte, without newline normalization. Native machine-readable
streams/files use binary output. Both migrated Mupen test commands pass again.
Their retained artifacts are under `target/receipts/windows-oracles/mupen-equivalence/`.

The first full native cache warm-up passed in 877.406 s with simultaneous control
builds. This cold/contended value is not comparable to the 542.344 s idle legacy
baseline. The final warm, idle, exact-tree gate timing is recorded in the landing
commit message and `target/receipts/windows-oracles/final-gate.json`.

Controls use unchanged main compiler/runtime code (131f0565), freshly lowered
and built with GCC15.2, visible windows and SDL dummy audio, one game at a time.
All stop records report fault0 / fault_pc00000000. At30s: MM1798, PM1798,
BK1798, SF641798, OoT1797 and Rogue Squadron1799 VIs. The earlier MM1612-VI
observation did not reproduce with MM alone; no runtime speed fix was needed.
MP2 at45s with the requested presses reaches Rules Land selection at2697 VIs.
OoT at60s with the requested save-load presses reaches the opening scene from a
valid retained SRAM slot at3596 VIs. All framebuffer PNGs were decoded directly
from the stop-time RDRAM and VI registers and inspected; artifacts and commands
are in `target/receipts/windows-oracles/controls/`. The SRAM fixture hash is in
`oot-save-fixture.json`; the source save was copied, not modified.

Self-review checked pin validation, cache invalidation, driver-relative includes,
binary stream semantics, Win64 assembly/DLL loading and preserved refusal paths.
The source audit finds no live WSL launcher or path helper in runtime/ or scripts/.
No RT64 bridge/patch or native game runtime code changed, so no shim rebuild is
required. The final gate and WSL-running check must pass before exact-head landing.
