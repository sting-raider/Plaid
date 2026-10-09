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

## Strict Rust inspection

The original typed streaming v4 adapter validates all raw read/attempt fields and
fetch scopes before feeding the unchanged strict v3/v2/v1/v0/v5 consumers. A
report recheck rebuilds every field and digest from both complete raw sources,
canonical ROM and supplied firmware. Three adversarial integration tests cover
wrong kinds/payloads/widths/offsets, duplicated/truncated data, missing/ambiguous/
cached reads, changed unused attempts and forged reports. A synthetic differing
bank read proves that observed backing and supplied-firmware equality are separate.

Complete 610,000-call inspection and source rechecking pass, with 9,537,688 rows,
2055 PIF-backed fetches and 50 samples. Python and Rust agree on every observation,
digest and the entire exact nested v3 report. The original v4 source is
1,697,485,372 bytes with SHA-256
`6290b782040af1a010d82918ae2d050b9014d9aa22f86a70f6ee8e1cb3ff2856`.
Ordered backing digest:
`6d6daafb51683ed1669de4b5717ccacd9563f9a2296f0ebe47fb03844a0b4e64`.
Python report SHA-256:
`a1fc1469dab433b2c08e4e56f263c7f13efbaa2db1ef7900faf97ebb4a0c1ca4`.
Rust report SHA-256:
`8b273a9471003c958d4df57d6aea1c7629b07ce0ee0eb50424aba1404fb0ae30`.
The smaller Rust report SHA-256 is
`a9c80b7098b0ccf6a39a6ef1fc1e8fd74e1e05fdab732590a3284f326037f691`.

The read-only correction changes only the write-attempt branch of the observer;
these captured prefixes contain no such attempts. A fresh final-recipe capture
is continuing. The separate thirteen-case component fixture executes the corrected
attempt branch. All 100 integration tests and three unit tests pass, along with
formatting and strict Clippy. No production executable image or solver promotion
follows from finite read identity.
