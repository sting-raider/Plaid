# Actual CPU SP backing observations in bounded boot

Date: 2026-10-09. Exact ares pin:
`9408cb43d4948fc3ea6e152a307a34348df3fe04`.

The original spike-039 sensor passes independent unchanged-reference/disabled/
enabled/repeated checkpoints and seven actual-history forgeries. Spike 040
composes its completed bank reads and normalized CPU/DMA stores into access
history v3. Generated reference sources, binaries, ROM/firmware and raw traces
stay ignored. Original production Rust consumes data only; it links no reference
runtime or guest instruction executor.

## Finite contract

An uncached CPU fetch inherits a bank/offset witness only from one actual matching
CPU SP Word read within its exact raw begin/end interval. Read context, PC,
physical address and returned word must agree. Physical mirrors remain distinct
even when they select the same backing. Missing, duplicate, foreign and cached
reads remain unknown. Sample endpoints are discrete observations, not lifetimes.

Completed CPU Word sinks retain their normalized width/payload, including equal
writes and device widening of SB. DMA stores retain actual RAM address, bank,
offset, width and payload. A receipt must match a successful SP-DMA RAM read in
the current uninterrupted read/store batch. Unrelated events cut that batch;
missing/ambiguous receipts stay unbound. This is not a DMA request, scheduling,
hardware atomicity or ultimate byte-origin certificate.

The streaming original Rust adapter validates every v3 row before projecting
to the unchanged strict v2 consumer. It renumbers raw contexts explicitly and
retains v3 read/write ordinals in its own observations. The complete nested v2/
v1/v0/v5 report verifies scheduling, buffered ROM effects, supplied ROM/firmware
and every paired fetch. Report rechecking reconstructs every field and digest,
including unused SP store payloads. ProgramMap and solver behavior stay unchanged.

## Executed evidence

The 10,000-call prefix is independently **VALIDATED**: 39,862 raw rows, 9857 SP
Word events and 7945 SP-backed fetches. All previous source bytes/messages and
unchanged-reference/disabled/repeated machine checkpoints agree. Python and Rust
agree on every count, sample and raw/projection/ordered digest. Rust report SHA:
`a9694b37a287e5f6ce0ec92c32ac94149e651b055ef7248b41b17b9b02d3229e`.

The full 610,000-call capture also preserves every prior v2/v5 byte and independent
checkpoint. Complete Rust inspection and entire-report source rechecking pass:
9,535,231 rows, 596,991 SP-backed fetches, 920 distinct samples and 512 DMA store
receipts. All receipts bind and no read receipt is left unconsumed. Full Python
nested replay is still running; its final report comparison is pending.

Three Rust integration tests cover full nested sources, raw ordinals, normalized
store effects, flags/report forgery, changed unused source rows, firmware/fetch
changes, malformed/truncated/duplicate data, ambiguous/missing/foreign/cached
reads and stale DMA receipts. All 97 integration tests plus three unit tests pass,
as do formatting and strict Clippy. The standalone retained contract suite has
22 passing models/source guards; it makes no reference-execution claim.

## Remaining obligations

SP bank identity does not identify PIF/ROM initialization or RDRAM ultimate origin.
Ordinary RSP DMEM stores, general producer/mutation coverage and reset/restore
remain open. The fixed supplied-firmware NTSC/6102/8-MiB/deterministic/PIF-HLE
prefix proves neither guest-suite completion nor whole-ROM coverage. Mutation
coverage, executable lifetime and native-complete flags remain false. Compose
actual PIF reads and producer history next.
