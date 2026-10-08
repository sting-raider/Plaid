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
