# Status

2026-10-08. Milestone: M1, synthetic executable discovery.

ProgramMap v0 and discovery trace v0 are implemented. Both preserve guest facts,
versioning, provenance, and deterministic serialization. Execution identities
include image and generation, so overlays sharing a PC need not collapse.

Validation rejects malformed ranges, missing evidence, unsupported versions,
unordered/truncated traces, and entries outside compilation units.

Mupen compilation units are not treated as guest basic blocks. Target lookups
without source PCs are not represented as observed indirect edges.

The separate GPL Mupen patch and C trace sink pass synthetic cross-language
tests. Patched x64 new_dynarec passes MinGW syntax checking. A full instrumented
Mupen execution and source-correlated indirect hooks remain unverified: M1 is
not yet claimed. `plaid check-map` and `plaid check-trace` validate artifacts.

No CPU lowering, native execution, compatibility, or native-complete claim.

ROM ingestion detects z64/v64/n64 signatures, normalizes bytes, parses the header,
and hashes canonical content. Eight Rust tests pass, including a SHA-256 known
vector and identical header/hash results across all byte orders. `plaid rom-info`
prints canonical identity and parsed metadata. Header entry PC is not assumed to
prove a ROM-to-RAM load mapping or a particular boot/CIC behavior.

Pinned Rabbitizer decoding and recursive direct CFG work on explicit code images.
Sixteen Rust tests cover formats, normalization, branches, calls, indirect sites,
delay slots, block splitting and rejected/unmapped paths. `plaid discover` writes
a ProgramMap for an explicitly supplied ROM/load range; it is not automatic boot
or whole-ROM discovery.
