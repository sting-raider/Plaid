# Bounded boot PIF-ROM backing

Hypothesis: an existing PIF ROM Word read within the actual uncached CPU fetch
interval can identify the selected modulo-ROM offset. Equal values from SI busy
latches, lockout, PIF RAM or cached paths cannot substitute for that read.

## Read-only counterexample

The initial mutable-ROM assumption was falsified by an actual write probe.
Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` declares the bank as
`Memory::Readable rom`. Both endian implementations make its write method a
no-op. The existing unlocked PIF Word-write delegate therefore supplies an
attempt payload only; locked writes skip the delegate altogether. Recording
this as a successful backing mutation would be wrong.

The separately built original sensor consumes existing read results and delegated
attempts without extra guest reads, clock steps, translation or object-layout
changes. Thirteen actual cases preserve unchanged-reference, disabled and repeated
enabled CPU/RAM/DMEM/PIF-RAM/PIF-ROM checkpoints. Three unlocked attempts retain
their normalized offset/payload; the locked attempt emits none. Equal, changed
and mirrored payloads all leave the entire ROM backing unchanged. The original
nine read-path adversaries also pass. Result SHA-256:
`6d4047acfdbad00c96ceed5e9720109f822ce3773dcde0906c353f11c842363c`.

## Finite chronology

Optional access-history v4 adds `pif_rom_word` and `pif_rom_write_attempt` on the
same raw ordinal. Projection removes these rows and renumbers contexts into the
exact prior v3 source. Read/attempt kinds cannot be interchanged. One matching
read within an uncached PIF fetch supplies a witness; missing, ambiguous, foreign,
cached and latch-only paths stay unknown. Firmware equality is a separate fact.
Out-of-band changes cannot be inferred from guest write attempts.

The 10,000-call capture has 42,319 rows, 2457 bank reads, 2055 PIF-backed fetches
and 50 discrete samples. All witnessed words match supplied firmware; no delegated
write attempt occurs. The remaining 7945 fetches retain their existing SP report.
All prior raw v3/v2/v1/v0/v5 sources, messages and independent checkpoints match.
Raw SHA-256:
`22764b1e8d9d03738116f794c7eb58413834d6ae3a95e0028cf90acbc23951dd`.
Ordered backing SHA-256:
`a305ee90a80b029f79d0b6b879d692a6e89da2dc17a0eb1130b936ac1decf7d4`.
Corrected Python report SHA-256:
`b308b5bf39ec8558446c83dfc60a5187c99d0da78cb5365cd0feaa364e91f3a1`.

Full-prefix validation is continuing. Generated reference sources, original
copyright notices, binaries, raw traces and supplied ROM/firmware remain ignored.
The fixed NTSC/6102/8-MiB/deterministic/PIF-HLE prefix proves neither complete
mutation coverage nor executable lifetime nor whole-ROM closure. All certification
flags remain false; ProgramMap and solver are unchanged.
