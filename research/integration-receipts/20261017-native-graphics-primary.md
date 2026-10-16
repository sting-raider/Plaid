# Native graphics microcode and F-Zero X runtime (ADR-0186)

Milestone: 5. Prepared base: `39ed3cce067dda24a3425f89bc576a337815ef10`
(ADR-0185's separately validated shared-slot compiler).

Recovered the interrupted graphics candidate, completed its build/cache path,
and reviewed it with the code-review-and-quality skill. The graphics computation
is the ROM's own RSP microcode compiled to host code. There are no per-game
addresses, shaders, rendering substitutes, runtime instruction interpreter or
JIT. Existing IMEM word guards and unknown-text faults remain active.

Corrections completed during takeover:

- CPU MMIO and RSP COP0 share DPC state. CPU submissions synchronize CPU texture
  writes; a native graphics task leaves known SP memory readable. The added
  SP-read regression failed before its correction and passes after it.
- The generated RT64 source copy needs its original include directory in the
  **rt64 target's** CMake directory scope. A clean build exposed and fixed that
  omission; the original pinned reference remains unchanged.
- Object replacement is atomic and a failed rebuild invalidates its stamp.
  Launchers quote arguments, escape batch percent expansion, disable delayed
  expansion, and supply the graphics mode, ROM and save paths.
- Raw handle PI DMA reuses checked transfer code; synthetic tests check the o32
  fifth argument, bytes, return value, bounds and refused cartridge writes.

Evidence on the runtime tree:

- fmt, strict all-target workspace Clippy, **710** Rust tests, CLI, runtime and
  native-cache tests PASS. The final gate took **118.05 s**.
- Runtime regressions cover native graphics tasks and shared DPC registers,
  frozen command submission, wrapped DMEM, RDRAM bytes, CPU RAM visibility,
  post-task SP reads, raw PI DMA, the 7/11/7 slot differential, and existing
  scheduler/audio/save/overlay contracts.
- `cmake --build target/rt64-shim --config Release --target plaid_rt64 --parallel 8`
  PASS, including its GPU-free empty-vertical-load/TMEM and split-command
  contracts. Final incremental renderer build: **8.59 s**.
- Spike096 and spike097 PASS against ares
  `9408cb43d4948fc3ea6e152a307a34348df3fe04`. Spike098 revalidates retained real
  audio task 600: **94,150** instructions, **2,972** changed RDRAM bytes; all
  RDRAM, IMEM, DMEM and RSP state match. This is not a full-game graphics oracle.
- Native graphics windows remained visible. Automated Start presses at VI
  300..1200 enter a race. Two packaging runs before the final SP-read correction
  reached 3,692 / 3,683 VIs without fault. The final runtime completed **65 s**,
  **3,481 VIs**, **3,108 graphics tasks**, **3,462 audio tasks**, **fault 0**.
  Current-race capture confirms Blue Falcon surface markings and shading.
- Reproduction: `python scripts/native.py target/local-inputs/fzerox.z64 --name
  fzerox --rt64 --rsp-gfx --seconds 65`, with the scripted presses above as
  repeated `--press 0x1000@<VI>:4` arguments. The resulting launcher has no
  automation or time limit.

Iteration measurements: the initial packaging run compiled **29** C objects;
the unchanged repeat compiled **0**. The cache contract measured **0.0662 s**
cold versus **0.0016 s** cached, while dependency/flag/source changes rebuild
and a failed compiler leaves no valid stamp. End-to-end packaging took 158.35 s
initially, 169.07 s during concurrent isolated Rust validation, and 101.24 s
for the final runtime edit (two runtime objects rebuilt). These totals include
65-second game runs and varying Rust build contention; they are not a clean
end-to-end speedup benchmark.
An uncontended incremental pipeline smoke run then took **24.22 s**, including
a one-second visible game run, with **zero** C objects rebuilt.

RT64 pin: `43373749dac9bbc1b653e6a02aed40a9e1783bed` (MIT, Copyright (c) 2024
RT64 Contributors). Its generated empty-tile correction preserves the pinned
dependency and notices. Pinned ares register/parallel-rdp behavior was read as
a reference; no GPL implementation was copied.

Limitations: F-Zero X is CLOSED only in the address-taken scope, with 14
assumptions. Whole-ROM remains OPEN with 2,995 blockers. IMEM snapshots are
observed coverage; new modes can require new snapshots. RSP/DPC completion is
synchronous. No assumption retired; `native_complete` remains false.

Logs, screenshots, ROM, generated game code, binaries and snapshots stay under
ignored `target/`. Progress record/check PASS. No Actions. Temporary integration
checkout cleanup was rejected by automatic approval review ("blocked by policy");
its target junction remains and must not be used for concurrent builds. Root
compiler artifacts were rebuilt after isolated validation to avoid reusing that
checkout's embedded RSP headers.
