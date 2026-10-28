# Authenticate the complete startup ROM copy (ADR-0293)

## Reproduced distinction

The native analysis window ends at the entry stub's BSS start (ADR-0184).
That bounds executable discovery; it does not bound IPL3's initial ROM-to-RAM
copy. GoldenEye's analysis window is0x5cee0 bytes while a fresh pinned-ares
handoff verifies all0x100000 ROM bytes at physical0x400. Native initialization
had installed only the smaller analysis window.

On the first native artifact, mapped source verification at virtual70000510
fails six distant guarded ranges despite an exact entry-body match. The first
mismatch is physical0xaf1d0. Restoring the authenticated startup copy makes all
288 guarded ranges verify. Source/mapping guards remain unchanged. Execution
still stops at VI0/fault3/PC800004b4 because1678 guarded words overlap existing
fixed source protections, first physical0xb6ac/tag2. This is a separate alias
ownership obligation, not permission to suppress the guard. No logo/title claim.

## General contract

At the first natural boot-entry fetch, the pinned ares adapter compares every
byte of the complete1MiB ROM copy against synchronized RDRAM using debugger
reads. The footer records destination, ROM offset, size and exact equality.
This is an entry-time comparison, not a later gameplay snapshot or a permanent
mapping. It never executes guest instructions in the native artifact.

The native startup header requires this exact verified record, a compatible
entry and RDRAM extent, in addition to the existing Status/EntryHi, SP and
0x400-byte prefix receipts. Malformed, partial, unverified or missing records
refuse. The native runtime installs that ROM data before its ordinary analysis
preload, checks the ROM length before reading, and retains the existing prefix
and SP initialization. BSS size remains an analysis bound. No game names or
addresses are used by the capability.

## Verifiers and receipts

The synthetic adapter fixture verifies short-source refusal, full-copy success,
the final byte, a shifted/mismatching handoff and entry-time provenance. Header
tests reject wrong destination/offset/size/boolean types or missing evidence.
The native runtime contract checks every byte of the1MiB copy beyond the smaller
analysis program and verifies clean native exit/PC/fault state. Truncating the
ROM by one byte refuses before execution. A retained pre-change runtime fails
the same full-copy check. The complete local gate includes these contracts.

Producing artifacts are ignored under target/ge-boot-copy-capture.json,
target/boot-copy-focused.log and target/receipts/ge-boot-copy. The latter contains
stop JSON, RDRAM/framebuffer PNGs and exact-tree gate/control receipts before
integration. The first comparison replay took1.211s; no optimization is claimed
from timings with different cache/workload conditions. CPU source/state layout
and RT64 bridge/patches are unchanged; control runtime objects are rebuilt.

Reference: ares9408cb43d4948fc3ea6e152a307a34348df3fe04, existing separately
built ISC analysis adapter. No upstream implementation body or ROM bytes are
copied into git.
