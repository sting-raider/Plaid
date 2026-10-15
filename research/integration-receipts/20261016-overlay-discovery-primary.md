# ADR-0172 stage 1: ROM-owned overlay candidates

Milestone 5. Base: `9c5ef482f8030213005f333e69a1925f7211d105`.
Claim: issue #4 comment 6200706937.

The shared checkout contains pre-existing indexing optimizations. This batch
is prepared in an isolated checkout of the exact canonical base; those changes
are preserved and excluded from this commit and its validation tree.

The ROM file-table recognizer finds a unique sorted, terminated table whose
self-entry covers it. Overlay tuples in reconstructed source images must match
file identity, decoded size, section boundaries, relocation trailer and BSS.
No title, table address, actor number or ROM offset is embedded. Data-only
overlays remain data-only. The initial explicit profile is Zelda64, not every
N64 overlay format.

The relocation model handles MIPS 32/26/HI16/LO16 with register-selected high
halves, signed low carry, segmented pointers, source checks and bounded RAM
destinations. Unknown kinds, duplicate/unaligned/out-of-section sites, missing
high halves and out-of-image targets reject. Native lowering and runtime
mapping have not changed; candidate discovery grants no closure certificate.

`inspect-overlays` rebuilds the input map's images against the ROM and records
their identities. It refuses to overwrite either input. ROMs, decoded images,
maps and the catalog remain local and ignored.

Evidence:
- Focused Rust tests cover synthetic table placement at different addresses,
  relocation at three load bases including signed-low carry, malformed
  trailers and pairs, and contradictory ranges.
- The CLI regression builds a synthetic ROM and ProgramMap, discovers the
  expected overlay, rejects a mismatching table span and protects its inputs.
- Local OoT measurement: 469 candidates, 468 with text; 16,968 HI16, 17,014
  LO16, 11,160 MIPS26 and 7,501 MIPS32 relocations. All candidates materialize
  at the analysis test base. This is format validation, not relocated native
  execution or ares differential evidence.
- N64Recomp's MIT pin `ffb39cdad1da5de07eaaa48bd1db4a89a7986771` was inspected
  for section-address immediates and dynamic function lookup. ADR-0172 links
  the Zelda64 format and loader behavior reference at exact revision
  `8a3634ca774a9b58d822cbc2cc09309f31eac6a4`. No reference implementation was
  imported.

Landing gate: fmt, strict locked workspace/all-target Clippy, locked workspace
tests, CLI tests, runtime tests, spike096, progress `--record` and `--check`,
and diff review. The issue #4 closeout records the actual gate result and CAS
commit. RSP lowering is unchanged; spike097/098 need no new capture or rebuild
for this metadata-only stage. Retained ROM/RSP evidence is preserved.

Next: link-address native overlay lowering, exact first-entry byte checks,
binding generations and invalidation, relocated execution against ares; then
the fixed OoT blockers and native title/audio campaign. Whole-ROM and native
OoT completion remain open. No GitHub Actions.
