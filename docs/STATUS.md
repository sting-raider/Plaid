# Status

2026-10-08. Milestone: M1, synthetic executable discovery.

ProgramMap v0 and discovery trace v0 are implemented. Both preserve guest facts,
versioning, provenance, and deterministic serialization. Execution identities
include image and generation, so overlays sharing a PC need not collapse.

Validation rejects malformed ranges, missing evidence, unsupported versions,
unordered/truncated traces, and entries outside compilation units.

Mupen compilation units are not treated as guest basic blocks. Target lookups
without source PCs are not represented as observed indirect edges.

No CPU lowering, native execution, compatibility, or native-complete claim.
