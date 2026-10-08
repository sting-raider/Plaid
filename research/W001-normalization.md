# ROM identity

2026-10-08. Hypothesis: byte-order variants should identify the same image.
Implementation follows the pinned Mupen ROM format signatures in
`src/main/rom.c`; no upstream code is copied.

`cargo test --workspace` verifies synthetic z64/v64/n64 bytes normalize to the
same bytes, header and SHA-256. A published SHA-256 `abc` vector checks the hash
encoding. Short, unaligned and unknown-signature inputs produce errors.

CRC1/CRC2 are metadata, not cryptographic identity, and are not currently checked.
The header entry point is metadata, not a proven executable load mapping.
