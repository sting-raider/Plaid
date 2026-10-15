# Primary integration: declared executable loads and shared return closure

Base: 3397cfe. Milestone: 3. Worker: Claude co-integrator, user-authorized
on main, running autonomously at the user's request.

ADR-0136:
- `plaid-loads-v0` declares raw or Yaz0 ROM sources placed at a
  destination.
- `declared_loads::compose` builds the composite image. Discovery and
  lowering use it, and `ProgramMap.load_images` lets `solve` rebuild it.
- Only the guarded scope accepts declared loads, and blocks straddling a
  load boundary are blockers.
- The native artifact preloads only the base window. It verifies a load's
  executable bytes by content at the first entry into its code (fault 8)
  and store-protects them once verified (fault 2).
- Runtime functions write guest RAM through `plaid_runtime_write`.

ADR-0137: `returns::Closure` shares map-wide return-closure facts. The OoT
annotate pass went from more than 25 minutes to 69 ms. OoT boot-window
discovery maps and guarded solves are byte-identical to the previous
implementation.

Spike096 on pinned ISC ares 9408cb43: `load` (KSEG1 copy, then a call to the
copied routine, result 10) matches, as do the thirteen earlier programs.
`load_early` faults 8 and `load_patch` faults 2; the earlier six negatives
are unchanged.

OoT US 1.2 local measurement: dmadata file 27 (`code`, Yaz0 at ROM
`0xa62d40`, 0x103da0 bytes) is declared at `0x800116e0`. That VRAM came from
a local heuristic (internal `jal` targets on prologues) and is not evidence.
Discovery: 7451 blocks, 723 indirect sites. Guarded solve: 748 blockers:
- 182 `BREAK`;
- about 450 COP1 arithmetic, conversion and FCSR sites;
- 33 unresolved indirect sites;
- 7 unmapped or unresolved targets.

Local gate on the exact tree: fmt, locked Clippy `-D warnings`, locked
workspace tests, `scripts/test_cli.py`, spike096, `tools/progress.py
--check`. No Actions. `native_complete` stays false.
