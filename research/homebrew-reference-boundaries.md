# Larger homebrew reference boundary

2026-10-08. Pinned test source `196f5421173220eb2f63a7a99c64795dc0ea0698`;
Mupen `ba95bab92a76744753bfe61470823a4937850ab0`; nust64 0.4.1.

The reproducible experiment and commands are in
`spikes/002-systemtest-discovery/README.md`. MIT guest source, exact old nightly,
locked dependencies and isolated Cargo workspace produce a 2,742,284-byte ROM;
repeated packaging yields SHA-256
`629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a`.
ROM, ELF, reference builds, logs and manifests stay under ignored target/.

The normal libdragon production boot executes cartridge code at B0001040. The
pin's `new_recompile_block_impl` accepts RDRAM/SP/TLB sources, then exits 1 for
this range. An incomplete 356,124-byte trace prefix survives (2,874 records);
Plaid's strict parser rejects its missing footer. Do not fabricate completion or
feed ELF metadata/partial records into a claim of automatic executable recovery.

The same ROM on the pure interpreter reaches many upstream tests and emits 410
IS64 messages, including nine failures, before NI at `80163180:D0640000`. Major
opcode 52 is explicitly unimplemented in `pure_interp.c`; `cached_interp.c`
also aliases LLD to NI. Unaligned exception and LLAddr failures independently
show that the oracle scope is narrower than complete hardware semantics. These
findings do not invalidate the existing restricted integer/control differential
fixtures; they prevent broadening those claims without another oracle.

The probe's five-second/16-MiB bounds limit exploration, not guest completion or
deterministic checkpoints. No graphics/audio/RSP correctness is established by
dummy plugins. Neither reference path completes the upstream suite. Verdict is
PARTIAL: build/packaging are validated, broad discovery/correctness are blocked
by demonstrated reference capabilities. General cartridge source modeling and
a stronger independent CPU/RSP observer are next, before W010/W011. No guest
workarounds, runtime fallback or native artifact is introduced.
