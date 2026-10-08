# Bounded independent CPU oracle

2026-10-08. ares `9408cb43d4948fc3ea6e152a307a34348df3fe04`; Mupen
`ba95bab92a76744753bfe61470823a4937850ab0`; x64 WSL Ubuntu GCC/G++ 15.2.

Hypothesis: an independently implemented interpreter can check the existing
integer/control subset and the cartridge/LLD/address-error gaps exposed by the
larger homebrew probe without changing reference CPU semantics.

`spikes/003-ares-oracle/run.py` builds the pinned core, asserts CPU/RSP
recompilation disabled, supplies explicit state and executes actual instruction
fetch/decode/device memory. It records complete GPR/HI/LO/PC plus exception,
BD/EPC/BadVAddr/LLAddr and a memory checkpoint. All twelve fixtures repeat with
identical states. Eight shared cases match Mupen's pure, untraced and traced
dynarec results in all GPRs, HI/LO and PC. Four independent capability cases
verify cartridge JALR/return, LLD/SCD results and ordinary/delay-slot AdEL state.

The headless frontend must own hidden-RAM backing, normally provided by Vulkan;
its omission caused RAM-write crashes in the first harness. The generated build
guards one unguarded renderer load call and omits UI assets. Fixture ROM words
populate the frontend pak before connection because reference ROM writes are
ignored. Reference power supplies a stack register, so the harness explicitly
zeros registers and supplies the shared SP bootstrap's final r25/r10 values.
These are declared initialization requirements, not guest patches or CPU changes.

The separate executable keeps ISC/BSD notices and contains an interpreter by
design for research. No code enters Plaid's Rust core or a native artifact. There
is no new performance, boot, full-device, FPU/TLB/RSP or whole-suite claim. The
VALIDATED verdict is limited to these repeatable fixtures; wider executable
capture and closed-world proofs remain next. Whole-ROM output stays OPEN.
