# Mupen discovery instrument

Pinned revision: `ba95bab92a76744753bfe61470823a4937850ab0`.
This patch and sink are GPL-2.0-or-later, separate from Plaid core. See the
reference's `LICENSES`, `doc/gpl-license`, and original source notices.

Run `python scripts/prepare_mupen.py`, then build Mupen normally with new_dynarec.
The script refuses a different revision or unrelated tracked reference edits.
Set `PLAID_TRACE_PATH`, `PLAID_ROM_SHA256` (canonical big-endian hash), and
`PLAID_ROM_SIZE` before starting the reference. These identity values are supplied
by the caller, not independently verified by the sink. Always compare them with
Plaid's normalization output. The sensor is disabled unless a path is set.

`python scripts/test_exporter.py` builds a strict C99 synthetic driver, checks
deterministic bytes and guest fields, and passes its output to the Rust parser.
This tests the sink protocol, not a complete running Mupen session.

Instrumented hooks: validated compile begin, compilation finish before Pass 10,
normal/restricted/pagespan entry installs, dynamic linker and lookup helpers,
outgoing links, generic invalidation, and page invalidation. Units contain actual
instruction words, not host code or host identities. Global invalidation is null.

Limitations: inline assembly lookup hits can bypass C sensors; source-correlated
JR/JALR observations, restored entries, PI DMA and RSP sensors are not implemented.
Runtime links may also be created at compile time. Cache expiry is not emitted.
Invalidation is not proof of a memory write. Trace v0 cannot prove complete
coverage; crashes and unfinished sessions intentionally lack a valid end record.
