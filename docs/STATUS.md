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
| Discovery (ROM -> ProgramMap) | ROM normalization, direct CFG, local and cross-block indirect proofs, function partitioning and return certificates (ADR-0127), trace import, conflict-aware merge | Jump tables beyond the bounded recognizer; overlays and DMA | `crates/plaid-core/tests/`, `crates/plaid-lower/tests/` |
| Closure proof (solver) | Fail-closed whole-ROM solver; assumption scopes `DeclaredStaticImages` and `DeclaredStaticImagesGuardedRam` reach CLOSED for synthetic programs | No commercial scope reaches CLOSED | `tests/pipeline.rs`, ADR-0126 |
| Executable provenance | PI/SP/PIF/cache/TLB/RSP byte lineage over pinned ares histories; 20M-fetch commercial boot prefix retained locally | Paused by ADR-0125 until a milestone needs it | [`STATUS-LOG.md`](STATUS-LOG.md) |
| Native lowering | `crates/plaid-lower`: CLOSED map -> C, one C function per guest function; declared runtime functions become `plaid_rt_<name>` calls (ADR-0129); calls are C calls and returns are checked (fault 5); proven-target dispatch only; runtime store and cache-alias guards; no interpreter | Integer subset only | spike096 |
| Runtime and rendering | Runtime boundary: declared host functions with an ABI assumption (ADR-0129) and proven callbacks entered through `plaid_enter` (ADR-0130) | Identification evidence for declarations; N64ModernRuntime + RT64 link (ADR-0126) | spike096 `boundary`, `callback` |

## Real-ROM numbers

| ROM (local, never committed) | Result |
| --- | --- |
| Ocarina of Time US 1.2, conditional window `0x1000..0x101000` at `0x80000400` | 293 blocks, 45 indirect sites, **62 whole-ROM blockers** (44 unresolved indirect sites, 8 unsupported instructions, 4 other site-level blockers, 6 global model obligations). 43 of the 44 unresolved indirect sites are returns with ADR-0127 certificates, which count only in the assumption scope. Under `--guarded-ram`: **82 blockers**, 69 of them libultra system instructions (ADR-0128). With heuristic runtime declarations and the `osCreateThread` callback (ADR-0129/0130): **628 blocks, 6 blockers** after COP1 moves and guarded jump tables (ADR-0131/0132). With n64sym-identified declarations (ADR-0133, 39 functions): **320 blocks, 20 blockers** after unaligned access (ADR-0134), 6 in boot code (host return, one pointer call, four FPU compare/branch sites) and 14 from calls into the area the code segment is later DMA'd over |
| Super Mario 64 | Not run yet: no local ROM supplied |
| Commercial ROMs CLOSED | **0** |

Reproduce the OoT numbers with `plaid discover <rom> 0x1000 0x80000400
0x100000 0x80000400 map.json`, then `plaid solve <rom> map.json`.

## Native lowering subset (spike096)

Matches the pinned ares interpreter exactly (all GPRs, HI, LO, a 256-byte RAM
window) on eleven synthetic programs (also comparing all 32 FPRs):

- ALU and shifts: `LUI ORI ADDIU ANDI XORI SLTI SLTIU ADDU SUBU AND OR XOR NOR SLT SLTU SLL SRL SRA SLLV SRLV SRAV`
- HI/LO: `MULT MULTU DIV DIVU MFHI MFLO MTHI MTLO`, including divide-by-zero and INT_MIN/-1
- 64-bit: `DADD DADDU DSUB DSUBU DADDI DADDIU DSLL DSRL DSRA DSLL32 DSRL32 DSRA32 DSLLV DSRLV DSRAV DMULT DMULTU DDIV DDIVU LD SD`, plus trapping `ADD ADDI SUB` with an overflow check
- Memory: `LB LBU LH LHU LW LWU SB SH SW` through KSEG0 and KSEG1, and the unaligned `LWL LWR LDL LDR SWL SWR SDL SDR` (ADR-0134)
- COP1 data moves (FR = 1): `MFC1 DMFC1 MTC1 DMTC1 LWC1 LDC1 SWC1 SDC1`
- Control: `BEQ BNE BLEZ BGTZ BLTZ BGEZ J JAL JR JALR` and the branch-likely forms, with delay slots; indirect jumps only over proven targets, including bounded jump tables (ADR-0132); nested, recursive, pointer and tail calls with checked returns

Anything else rejects the whole program. A store into executable bytes (fault
2) or cached and uncached access to the same 16-byte line (fault 4, because the
write-back D-cache makes the result state-dependent) aborts instead of
executing, as does a return whose `$ra` is not its call's continuation (fault 5) or an
overflowing trapping add (fault 6).
