# Pinned hook and DMA integration

2026-10-08. Follow-up to W003/W004 and W012.

Hypothesis: the trace sink works at actual pinned new_dynarec hook sites, and
cartridge DMA observations can establish executable source mappings only when
captured words match canonical ROM bytes.

Reference: Mupen64Plus core `ba95bab92a76744753bfe61470823a4937850ab0`,
`src/device/r4300/new_dynarec/new_dynarec.c` and `src/device/cart/cart_rom.c`.
The patch/sink/harness are isolated GPL research instrumentation; GPL text is
preserved in `instruments/mupen/COPYING`. No Mupen implementation enters Rust core.

`scripts/test_mupen_hooks.py` builds actual reference routines using GCC 15.2 on
Windows. It compiles a self-jump, a changed same-PC indirect unit, a pagespan entry
and an external direct link. The cartridge routine copies synthetic ROM bytes
before compilation. ROM-end and RDRAM-end transfers are clipped, and beyond-ROM
zero-fill emits no ROM-copy event. Two runs produce identical 38-event traces.
Rust checks the trace, imports verified loads, preserves invalidation generations
and produces an OPEN whole-ROM solver report.

The harness never executes generated host code. Runtime helpers trap on calls;
the interrupt-time helper returns zero solely for the copy harness. This experiment
is not an N64 CPU, timing, execution-coverage or compatibility verification.
Source-correlated JR/JALR hooks and inline assembly lookup coverage remain next.

The final discovery integration adds bounded traversal of local indirect targets,
retains candidates when new roots invalidate a prefix proof, rejects duplicate
provenance keys, coalesces observations with static site proofs and checks extra
contradictory CFG facts. Synthetic CLI tests exercise all ROM byte orders, deterministic
maps, idempotent merging, canonical identity rejection and fail-closed reports.

Result: useful synthetic discovery foundation, verified by 45 Rust tests plus CLI,
sink and actual-hook integration scripts. Whole-ROM closure is not established;
native lowering remains deferred. STATUS supersedes historical test counts and
pending PI-hook notes in the earlier milestone records.
