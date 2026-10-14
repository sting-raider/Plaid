# Status

Last updated 2026-10-15. This page is the current state in one screen. The
per-cluster history it replaces (spikes 001-095, every receipt summary) is
preserved verbatim in [`STATUS-LOG.md`](STATUS-LOG.md). Priorities live in
[`NEXT.md`](NEXT.md); decisions in [`DECISIONS.md`](DECISIONS.md).

**Summary:** the discovery and proof foundation is substantial; native lowering
works for synthetic CLOSED programs only; no commercial ROM is CLOSED; there is
no runtime yet. `native_complete` is `false` everywhere.

## By layer

| Layer | State | Main gap | Evidence |
| --- | --- | --- | --- |
| Discovery (ROM -> ProgramMap) | ROM normalization, direct CFG, local and cross-block indirect proofs, trace import, conflict-aware merge | `jr $ra` returns have no closure proof; no function model | `crates/plaid-core/tests/` |
| Closure proof (solver) | Fail-closed whole-ROM solver; assumption scopes `DeclaredStaticImages` and `DeclaredStaticImagesGuardedRam` reach CLOSED for synthetic programs | No commercial scope reaches CLOSED | `tests/pipeline.rs`, ADR-0126 |
| Executable provenance | PI/SP/PIF/cache/TLB/RSP byte lineage over pinned ares histories; 20M-fetch commercial boot prefix retained locally | Paused by ADR-0125 until a milestone needs it | [`STATUS-LOG.md`](STATUS-LOG.md) |
| Native lowering | `crates/plaid-lower`: CLOSED map -> one C unit; proven-target dispatch only; runtime store guard; no interpreter | Integer subset only; one C function per program, not per guest function | spike096 |
| Runtime and rendering | None | Planned reuse of N64ModernRuntime + RT64 (ADR-0126) | — |

## Real-ROM numbers

| ROM (local, never committed) | Result |
| --- | --- |
| Ocarina of Time US 1.2, conditional window `0x1000..0x101000` at `0x80000400` | 293 blocks, 45 indirect sites, **62 whole-ROM blockers** (44 unresolved indirect sites, 8 unsupported instructions, 4 other site-level blockers, 6 global model obligations) |
| Super Mario 64 | Not run yet: no local ROM supplied |
| Commercial ROMs CLOSED | **0** |

Reproduce the OoT numbers with `plaid discover <rom> 0x1000 0x80000400
0x100000 0x80000400 map.json`, then `plaid solve <rom> map.json`.

## Native lowering subset (spike096)

Matches the pinned ares interpreter exactly (all GPRs, HI, LO, a 256-byte RAM
window) on five synthetic programs:

- ALU and shifts: `LUI ORI ADDIU ANDI XORI SLTI SLTIU ADDU SUBU AND OR XOR NOR SLT SLTU SLL SRL SRA SLLV SRLV SRAV`
- HI/LO: `MULT MULTU DIV DIVU MFHI MFLO MTHI MTLO`, including divide-by-zero and INT_MIN/-1
- Memory: `LB LBU LH LHU LW SB SH SW` through KSEG0 and KSEG1
- Control: `BEQ BNE BLEZ BGTZ BLTZ BGEZ J JAL JR JALR` with delay slots; indirect jumps only over proven targets

Anything else rejects the whole program. A store into executable bytes (fault
2) or cached and uncached access to the same 16-byte line (fault 4, because the
write-back D-cache makes the result state-dependent) aborts instead of
executing.
