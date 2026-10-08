# Bounded CPU PIF boot input

2026-10-08. Hypothesis: the existing pinned NTSC CPU PIF firmware can establish
input provenance and natural power entry without host SP copying or seed/PC
shortcuts. Spike 008 supplies the ignored firmware through the system pak before
power, preserves enforced IPL2 checksum and the reference PIF processor HLE, and
records its digest. Both recompilers are disabled. Firmware bytes and reference
objects stay ignored; the separate build preserves upstream notices.

The harness declares NTSC/CIC-NUS-6102, deterministic entropy and 8 MiB RAM. These
are experiment inputs, not automatic ROM profile discovery or hardware-wide boot
equivalence. CPU::power supplies PC FFFFFFFFBFC00000. Existing prologue/access/
delegating-ROM observers run unchanged. No guest instructions, firmware bytes,
device busy state or timing registers are patched.

Firmware size is 1,984 bytes; SHA-256
`fa7b09795ef1e54461e59f6f2d902368133e3f1cd980e34383e6a780d74beffd`.
The canonical homebrew hash is
`629f908c200bbf21013dcd1d331d4ddedd08a6c9d7ae1f528421564238056e8a`.
At one million calls, plain/traced/repeated CPU/COP0/Count/PIF/PI and RAM/SP
checkpoints agree, as do messages and repeated raw bytes. There are one million
fetches at 50 PIF, 920 SP and 185 RAM addresses. Config is 7006E463 and the PIF
checksum stage has passed (state 4, WaitTerminateBoot). The CPU polls PI status
at FFFFFFFF807FFE5C; DMA busy is 1, IO busy 0 and BSD1 is [64,18,7,3]. No guest
test has begun. Raw bytes: 154,485,582; SHA-256
`fbdf4da4fbae6bec9712404b7f14df790fe1fb3aca1a9b1239e207248bffe021`.

The earlier five-million-call prefix also repeats exactly and remains in this
loop (Count 30,784,366). Primary PI::ioWrite schedules dmaDuration before dmaWrite;
dmaWrite copies immediately, while the queued dmaFinished later clears busy.
CPU::synchronize advances that queue. Boot programs BSD timing, so the old
synthetic-entry prefix's faster progress cannot establish equivalence. A longer
plain run reaches the guest tests, but broader traced neutrality is pending.
The first longer trace exceeded 180 seconds under concurrent output load and is
rejected as incomplete. Keep the ten-million instruction ceiling and scale the
finite wall timeout to at most 600 seconds; this changes no guest event timing.

Research v3 declares firmware digest, natural power entry, PIF HLE and checksum
policy. Production deliberately rejects this scope without output. A future
format must explicitly carry the complete boot profile and recheck firmware
input, not accept a hash claim alone. PIF source remains unknown: SI busy latches
and PIF ROM lockout can return words without reading firmware. RAM/SP copy/cache
lineage, execution modes, lifetimes and whole-ROM coverage remain unresolved.

Existing v0/v2 streams and state/message goldens remain exact with the conditional
boot path present. Rust's 72 tests and CLI/exporter/Mupen integrations pass, as do
the earlier static/homebrew/oracle/source-boundary experiments. No native artifact
or complete guest-suite result is claimed.
