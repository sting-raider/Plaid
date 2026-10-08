# CPU power entry with explicit PIF firmware input

Hypothesis: loading the pinned reference's existing NTSC CPU PIF firmware and
starting from CPU::power's natural PC can establish boot-input provenance without
the host's SP-ROM copy, manual seed register or PC shortcut. Keep the reference
PIF processor HLE and enforced IPL2 checksum explicit; this is not hardware-wide
boot equivalence. Preserve the untouched homebrew and report any checksum/guest
failure without modifying either guest or reference opcode behavior.

The firmware is read as an ignored local input from the pinned checkout, hashed
and supplied through the reference's system pak. No firmware bytes are copied
into project sources or linked into the harness. Generated reference code and
notices remain under ignored target/. Research v3 declares CPU power entry,
firmware digest, PIF HLE and checksum policy. Plaid's current production reader
must reject that unsupported boot scope.

Verdict: VALIDATED for bounded boot-input observation and trace neutrality;
PARTIAL for broader guest execution. The fixed harness profile is NTSC,
CIC-NUS-6102, deterministic entropy and 8 MiB RAM. Both recompilers stay disabled.
This profile is declared by the harness, not automatically inferred from the ROM.
Firmware is 1,984 bytes with SHA-256
`fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`.

Run `python spikes/008-ares-pif-boot/run.py --budget 1000000` from the repository.
The first fetch is the CPU power PC `FFFFFFFFBFC00000`, physical `1FC00000`.
Plain/traced/repeated GPR/HI/LO/PC/Count/exception/PIF/COP0/PI/RAM/SP checkpoints
and messages agree; repeated raw streams match exactly. One million calls yield
one million fetches at 50 PIF, 920 SP and 185 RAM addresses. The firmware sets
COP0 Config to `7006E463` and passes the reference's checksum gate (PIF state 4).
The loader is still waiting for PI DMA, with timing registers `[64,18,7,3]`.
No guest tests have begun at this prefix. The raw stream is 154,485,582 bytes,
SHA-256 `fbdf4da4fbae6bec9712404b7f14df790fe1fb3aca1a9b1239e207248bffe021`.
Earlier 100,000- and five-million-call prefixes also repeat exactly.

Each process has an instruction budget of at most ten million and a wall budget
of 180–600 seconds, scaled by requested calls. A ten-million-call traced run
under concurrent capture load exceeded the original 180-second wall budget;
its truncated output is not accepted. Per-budget output directories preserve
completed prefixes, while result files are removed before each new attempt.

PIF and copied SP/RAM sources remain unknown. A matching firmware word alone
cannot distinguish the SI latch or PIF ROM lockout. No source/image/lifetime or
production boot certificate is promoted. The production reader rejects research
v3; explicit profile/input verification requires a separate format decision.
