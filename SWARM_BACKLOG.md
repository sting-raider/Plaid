# SWARM BACKLOG

Statuses: `TODO`, `CLAIMED`, `BLOCKED`, `DONE`.

| ID | Status | Work item | Acceptance criterion |
|---|---|---|---|
| W001 | DONE | ROM format normalizer | Synthetic tests cover z64/v64/n64 byte order and canonical hashing input. |
| W002 | DONE | Define `ProgramMap` schema v0 | Schema represents regions, blocks, edges, indirect targets, overlays, evidence, unresolved items. |
| W003 | DONE | Mupen `new_dynarec` instrumentation design | Document exact hook points for block creation, links, invalidation, indirect target discovery. |
| W004 | DONE | Build dynamic trace format | Versioned machine-readable trace plus parser tests. |
| W005 | TODO | Direct CFG discovery | Starting from an entry PC, recursively recover direct branch/call targets with delay-slot semantics. |
| W006 | TODO | spimdisasm integration spike | Compare its recovered functions/pointers against our map on legal/synthetic inputs. |
| W007 | TODO | Rabbitizer integration decision | Benchmark/assess using Rabbitizer vs project-owned decode layer; document ADR. |
| W008 | TODO | Known-symbol/signature discovery | Integrate or reproduce n64sym-style identification into evidence model. |
| W009 | TODO | Guest-address/native-symbol model | Prototype safe mapping without conflating guest pointers with host pointers. |
| W010 | TODO | Native backend spike | Emit one synthetic MIPS basic block as a relocatable host object and verify final machine state. |
| W011 | TODO | Differential verifier | Run equivalent synthetic block through reference and native paths and compare state. |
| W012 | TODO | Executable DMA/overlay tracing | Detect ROM->RAM code loads and represent relocation/load evidence. |
| W013 | TODO | Closed-world solver v0 | Report unresolved direct/indirect targets and refuse native-complete status while any remain. |
| W014 | TODO | Runtime boundary study | Map N64ModernRuntime/Mupen/ares/Gopher64 services to our planned runtime API. |
| W015 | TODO | First commercial-ROM validation protocol | Define legal local-ROM workflow and metadata-only expected-results fixtures. |
