# Executing indirect source units

2026-10-08. Mupen pin `ba95bab92a76744753bfe61470823a4937850ab0`.

Hypothesis: embedding the trace-local compilation ID in a generated JR/JALR
callback identifies a unit still executing after invalidation, without guessing
its image from PC and the current import epoch. This does not identify restored
target entries or establish that the unit's original bytes remain in RAM.

Inspected the pinned `new_recompile_block_impl`, `rjump_assemble`,
`pagespan_assemble`, `pagespan_ds`, ABI argument registers and `emit_movimm64`.
The unit counter is assigned at compile begin; generated code receives a literal
ID. The normal sensor copies the saved pre-delay-slot target to ARG2 before
assigning the 64-bit unit ID and source PC. Caller-save preservation remains in
place. Pagespan predecessors save both branch tag and literal source unit in a
helper before existing branch calculations; the separate delay-slot unit reports
the predecessor ID. Direct predecessors clear the tag. No host pointer is emitted.

Trace `source_unit` is optional/defaulted for old producers. When present, the
referenced unit must already have completed and contain the site. Import selects
the exact CodeImage identity, then requires a decoded indirect site there. Raw
ProgramMap observations retain the execution epoch separately from the source
unit's session-qualified CompileBegin evidence ID. A unit is compilation
provenance, not an execution-coverage or byte-immutability certificate.

Targets still require a unique captured image in the execution epoch, including
first compilation after the event but before invalidation. An older source is
allowed only through explicit unit context. Without that field, the importer
retains its same-epoch source rule. A tagged return to an older target remains
uncorrelated. Trace validators reject unknown, unfinished and out-of-range units;
the importer retains raw evidence whenever the decoded source/target join fails.

Results: 60 Rust integration tests, strict Clippy, formatting, CLI, exporter,
four-unit compile-only hook harness, eight CPU scenarios, six full-core sessions,
and the four-fixture spimdisasm comparison pass. All GPR/HI/LO/PC values match the
interpreter and untraced dynarec; traced reruns match byte for byte. Full-core
event counts remain 43/83/82/82/34/48. The store-stress JALR at 80000488 now
joins the executing generation-8 unit to its newly compiled generation-9 target.
The return to the older main-unit continuation remains unresolved. Whole-ROM
closure stays OPEN with `native_complete=false` in every session.

Reproduce with the commands in README. The GPL research patch remains separate
from Rust. This scope covers the pinned x64 sensors on original synthetic input;
exceptions, cache expiry, restored target activation/byte verification, broader
write coverage and other host architectures remain outstanding.
