# Primary composition: completed compilation to closure admission

Base: 75765ab42b2e478db34aada1b0215399d88af90a. Claim: 6114737379.
Sources: canonical ADR-0113/0114 source sets and typed trace projection/import;
current solver static identity/deletion regressions. No new research lane.

Hypothesis: a source-preserving report cannot drop a completed compilation's
root declaration just because the source lacks explicit install events. Actual
re-imported execution identities and captured words must constrain both submitted
roots and separate later solver instruction witnesses.

Reproduced red on current main: source contains a known closed self-loop and an
unresolved-JR unit, with no EntryInstalled events. Removing the JR unit's regions,
blocks, entries, indirect sites and diagnostics while keeping all trace metadata
made ordinary finite solving and prior source admission CLOSED. New admission
rejects missing source-derived root/provenance. The empty-root-only preliminary
probe correctly remained OPEN under missing_entry_universe; the retained positive
root is necessary to expose the deletion defect.

New verifier reuses the original ROM-aware importer and exact source event
metadata, requires each compiled root's canonical identity/provenance to survive,
and permits extra roots from later composition. It compares supplied instruction
words to typed captured snapshots for those identities. Legacy opaque labels
cannot substitute new control flow: a second deterministic regression changes an
unresolved-JR snapshot into a supplied self-loop while retaining opaque root
identity/metadata and a consistent edited CFG. Ordinary finite solving closes;
source admission rejects the mismatched captured word. Missing instruction
witnesses still produce OPEN through the ordinary solver.

Eight focused admission tests PASS, including both new negative cases, compiled
metadata/root binding, added roots, missing instruction source, existing source-
set/raw-negative/install deletion/ROM/merge checks. Five retained installed-entry
projection tests pass unchanged. CLI now covers compilation without install
records, preserving the source expectation while removing its whole map
projection. Authentication rejects before report emission.

Mandatory local fmt, strict locked workspace/all-target Clippy, full locked
workspace including actual outer fixed-point deletion adversary, canonical CLI
and diff checks PASS on exact base. Logs: target/compiled-source-primary ignored.
No hardware semantics changes, reference rebuilds, Actions or workflow scaffolds.
STATUS/NEXT/DEVELOPMENT/DECISIONS updated under ADR-0117; milestones unchanged.

Still not an execution-root census, cache/mapping/byte lifetime certificate,
authentication of every derived map field or whole-ROM/native closure. Compiler
roots are retained projections, not newly claimed execution. Ordinary solve and
legacy explicit primitive/install helpers keep their existing contract.

Harvest disposition while finding this defect: PR #31 relocation and PR #28
(and its recovered candidate) decompression retain valuable supplied-event
models, but their initial-generation/operation seams are not authenticated guest
transform provenance from current canonical captures. Do not merge an isolated
ledger as if that composition existed. They remain pending, not consumed or
superseded; no PR closure or new upstream runtime dependency.
