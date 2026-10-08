# SWARM BACKLOG

Statuses: `TODO`, `CLAIMED`, `BLOCKED`, `DONE`.

| ID | Status | Work item | Acceptance criterion |
|---|---|---|---|
| W001 | DONE | ROM format normalizer | Synthetic tests cover z64/v64/n64 byte order and canonical hashing input. |
| W002 | DONE | Define `ProgramMap` schema v0 | Schema represents regions, blocks, edges, indirect targets, overlays, evidence, unresolved items. |
| W003 | DONE | Mupen `new_dynarec` instrumentation design | Document exact hook points for block creation, links, invalidation, indirect target discovery. |
| W004 | DONE | Build dynamic trace format | Versioned machine-readable trace plus parser tests. |
| W005 | DONE | Direct CFG discovery | Starting from an entry PC, recursively recover direct branch/call targets with delay-slot semantics. |
| W006 | DONE | spimdisasm integration spike | Four synthetic function/table/truncation comparisons pass; PARTIAL verdict and production constraints recorded in spikes/001-spimdisasm. |
| W007 | DONE | Rabbitizer integration decision | Benchmark/assess using Rabbitizer vs project-owned decode layer; document ADR. |
| W008 | TODO | Known-symbol/signature discovery | Integrate or reproduce n64sym-style identification into evidence model. |
| W009 | TODO | Guest-address/native-symbol model | Prototype safe mapping without conflating guest pointers with host pointers. |
| W010 | TODO | Native backend spike | Emit one synthetic MIPS basic block as a relocatable host object and verify final machine state. |
| W011 | TODO | Differential verifier | Run equivalent synthetic block through reference and native paths and compare state. |
| W012 | TODO | Executable DMA/overlay tracing | Detect ROM->RAM code loads and represent relocation/load evidence. |
| W013 | DONE | Closed-world solver v0 | Report unresolved direct/indirect targets and refuse native-complete status while any remain. |
| W014 | TODO | Runtime boundary study | Map N64ModernRuntime/Mupen/ares/Gopher64 services to our planned runtime API. |
| W015 | TODO | First commercial-ROM validation protocol | Define legal local-ROM workflow and metadata-only expected-results fixtures. |

Broader corpus investigation: the pinned MIT n64-systemtest build is reproducible,
but the headless capture spike is PARTIAL (cartridge execution and CPU-oracle
limits). W010/W011 remain deferred; W012 still needs general source/write/lifecycle
coverage. See `spikes/002-systemtest-discovery/` and `docs/NEXT.md`.

Independent oracle foundation: `spikes/003-ares-oracle/` is VALIDATED for four
original cartridge/linked-memory/address-error cases and eight cross-reference
integer/control comparisons. W011 still requires a native path and broader
declared semantic coverage; this research does not complete W011 or W012.

Broader fetch sensing: `spikes/004-ares-fetch/` validates repeatable observations
of 52,424 RAM/548 SP/65 cartridge addresses on the pinned homebrew. Its synthetic
SP-entry/budget scope, startup failure and missing production adapter leave
W012 and whole-ROM closure open. No native backend work is promoted by this spike.

Raw capture import: typed 64-bit observations and full-source summary verification
now pass on the broader corpus (53,037 summaries; 4,999,998 accounted fetches).
Physical backing and execution generations remain unknown; W012 stays TODO.

Effective fetch context: the separate observer and v1 importer preserve physical/
cache variants with full-source rechecking and byte-identical v0 compatibility.
Cache/TLB/endian fixtures and both complete corpus checks pass. Actual byte-source
witnesses and lifecycle joins remain open; W012 stays TODO.

Finite ROM sources: delegated actual reads and v2 canonical-source import/recheck
now account for 1,852 fetches at 65 offsets while retaining all unknowns. Raw
provenance, source variants, legacy map hashes and OPEN gating pass. Boot/mode,
copy/cache/mutation lineage and executable lifetime remain open; W012 stays TODO.
