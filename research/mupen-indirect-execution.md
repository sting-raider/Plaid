# Source-correlated indirect execution

2026-10-08. Pinned Mupen core `ba95bab92a76744753bfe61470823a4937850ab0`.

Hypothesis: a generated x64 sensor after the delay slot, before mini_ht/general
dispatch, can capture in-unit JR/JALR source/target facts without changing CPU
state, including return-cache hits that bypass C lookup helpers.

Evidence: `rjump_assemble` already preserves a target register when the delay
slot overwrites its guest source. `do_miniht_jump` can directly jump to host code
on a cache hit. The sensor copies that saved operand into ABI arguments, saves/
restores allocated caller-save registers, and runs before cycle flags are computed.
It is enabled only by `PLAID_TRACE_EXECUTION=1` and advertises restricted coverage.

The GPL headless harness builds actual pinned new_dynarec, x64 assembly linkage,
pure interpreter, register access and CP0 support. Flat memory mapping and a
shared sentinel interrupt stop policy are test scaffolding; unsupported services
abort. No Plaid CPU implementation or native artifact is introduced.

Two synthetic programs exercise repeated JALR and direct JAL calls, JR returns,
delay-slot effects and a final JR whose delay slot overwrites its target register.
GPRs, HI/LO and PC agree across pure interpreter, untraced dynarec and traced
dynarec. Traced reruns produce identical bytes. JAL's three returns produce source
events while bypassing C target lookups; JALR's returns use general lookup.

The initial entry fixture used J from 0xa4000040 and correctly reached the
uncached 0xa0000000 alias in both CPUs. Replaced it with LUI/JR to explicitly
enter 0x80000000. This was a fixture expectation error, not a reference CPU fix.

The importer retains raw observations and defers first-target-compilation joins
within an invalidation epoch. A Rust regression checks event-before-compilation,
roundtrip/merge and rejection of cross-generation correlation. Observations never
become closed-target certificates. Pagespan, other host architectures, real
devices, exception behavior, timing and full boot coverage remain outstanding.

Reproduce: `python scripts/test_mupen_execution.py` on Windows with WSL Ubuntu,
or Linux with GCC/NASM and Rust. NASM can be supplied by `PLAID_NASM`; this run
used an apt package extracted under ignored `target/reference-tools/`, with no
system package installation.

Follow-up: the corpus now covers eight scenarios, including page-spanning JR,
custom-link JALR and direct J. Predecessor tags are written before boundary
dispatch, then checked after the separate delay-slot unit. Direct predecessors
emit no indirect event. The saved target survives a slot overwrite. Additional
custom links, likely-branch annulment and all-GPR register stress agree across
the same three CPU modes; repeated traces remain identical. This completes the
x64 pagespan sensor experiment, not the ProgramMap predecessor-state proof or
device/timing coverage.
