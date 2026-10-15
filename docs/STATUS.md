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
| Native lowering | `crates/plaid-lower`: CLOSED map -> C, one C function per guest function; declared runtime functions become `plaid_rt_<name>` calls (ADR-0129); calls are C calls and returns are checked (fault 5); proven-target dispatch only; runtime store and cache-alias guards; no interpreter | Integer subset, COP1 moves and compares | spike096 |
| Runtime and rendering | Runtime boundary: declared host functions with an ABI assumption (ADR-0129) and proven callbacks entered through `plaid_enter` (ADR-0130) | Identification evidence for declarations; N64ModernRuntime + RT64 link (ADR-0126) | spike096 `boundary`, `callback` |

## Real-ROM numbers

| ROM (local, never committed) | Result |
| --- | --- |
| Ocarina of Time US 1.2, conditional window `0x1000..0x101000` at `0x80000400` | 293 blocks, 45 indirect sites, **62 whole-ROM blockers** (44 unresolved indirect sites, 8 unsupported instructions, 4 other site-level blockers, 6 global model obligations). 43 of the 44 unresolved indirect sites are returns with ADR-0127 certificates, which count only in the assumption scope. Under `--guarded-ram`: **82 blockers**, 69 of them libultra system instructions (ADR-0128). With heuristic runtime declarations and the `osCreateThread` callback (ADR-0129/0130): **628 blocks, 6 blockers** after COP1 moves and guarded jump tables (ADR-0131/0132). With n64sym-identified declarations (ADR-0133, 39 functions): **320 blocks, 16 blockers** after unaligned access and COP1 compares (ADR-0134/0135): in boot code only the host return and one pointer call. With the Yaz0 `code` segment declared as a load (ADR-0136): **7451 blocks, 566 blockers** after `BREAK` became a checked abort (ADR-0138), then **42 blockers** after COP1 arithmetic, conversions and FCSR access (ADR-0139). Recognizing GCC's scheduled jump-table shapes (ADR-0140) closes all 12 remaining tables and extends discovery to **8082 blocks, 31 blockers**: 22 unresolved indirect sites (9 `jalr s4` output callbacks in one `_Printf`-shaped function, 12 struct function-pointer calls, the boot return), 4 unresolved direct targets, 3 unmapped targets, one `COP0` and one `CACHE` instruction. Identifying runtime functions over the composite image as well (ADR-0141, 59 functions) leaves **7684 blocks, 29 blockers**: the 22 indirect sites and 7 calls into the 64DD driver segment at `0x801c7740..`, each behind a "64DD present" flag test. No instruction-scope blocker remains. A points-to census for the 21 function-pointer `jalr` sites is recorded as unsound; they stay open (ADR-0142). Host-entry returns (ADR-0146) remove the boot return: **28 blockers**, the 21 function-pointer sites and 7 calls into the 64DD driver, which is not on the cartridge |
| Mario Party 2 USA, window `0x1000..0x101000` at `0x80000400` | 51 n64sym-identified runtime functions; 712 blocks, 92 indirect sites; under `--guarded-ram` **29 blockers**: 27 libultra system instructions behind an `osInitialize` whose SDK build n64sym lacks, and 2 memory-loaded function-pointer calls (ADR-0148, `research/mario-party-2-boot-window.md`). `identify --symbols` can name runtime functions from a reference map instead |
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
- COP1 data moves (FR = 1): `MFC1 DMFC1 MTC1 DMTC1 LWC1 LDC1 SWC1 SDC1`; all 32 `C.cond.S/D` compares and `BC1F BC1T BC1FL BC1TL`, with NaN operands faulting 7 (ADR-0135)
- COP1 arithmetic (ADR-0139): `ADD SUB MUL DIV SQRT ABS MOV NEG` in `.S` and `.D`, `CVT.S` from D/W/L, `CVT.D` from S/W/L, `CVT/ROUND/TRUNC/CEIL/FLOOR` to W and L from S/D (ADR-0143), `CFC1 CTC1`, with FCSR rounding modes, cause and sticky flags and FS flushing as pinned ares
- System (ADR-0145): `LL LLD SC SCD` with an exact LLbit, `SYNC`, and the twelve conditional traps checked as never taken
- Control: `BEQ BNE BLEZ BGTZ BLTZ BGEZ J JAL JR JALR BLTZAL BGEZAL` and the branch-likely forms, with delay slots; indirect jumps only over proven targets, including bounded jump tables in GCC's scheduled shapes (ADR-0132/0140); nested, recursive, pointer and tail calls with checked returns

Anything else rejects the whole program. A store into executable bytes (fault
2) or cached and uncached access to the same 16-byte line (fault 4, because the
write-back D-cache makes the result state-dependent) aborts instead of
executing, as does a return whose `$ra` is not its call's continuation (fault 5) or an
overflowing trapping add (fault 6) a COP1 operation outside the modeled subset: a NaN or subnormal operand, an out-of-range conversion or an enabled FPU exception (fault 7), entry into a declared load whose bytes are not in RAM (fault 8), a reached `BREAK` (fault 9), or a taken conditional trap (fault 10).
