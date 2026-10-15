# Function-pointer `jalr` sites under the guarded scope: negative result

Date: 2026-10-15. Milestone: 5 (OoT), measured at base 48f9427 (ADR-0141).
Decision: ADR-0142.

## Question

OoT US 1.2 with its declared Yaz0 `code` segment has 29 guarded blockers.
22 are unresolved indirect sites: 21 `jalr` calls and the boot return. Can a
sound, fail-closed points-to argument close the `jalr` sites, either
through function-pointer parameters or through a census of every store to
a struct field?

## Measurement

Inputs are local and ignored: the ROM in `target/local-inputs/`; `code`
(dmadata file 27, Yaz0 at ROM `0xa62d40`, `0x103da0` bytes) declared at
`0x800116e0`; and `plaid identify --loads` over the pinned n64sym
signatures (59 functions). The run reproduces the numbers: 7684 blocks,
698 indirect sites and 29 blockers.

For each site, the source of the called register, traced back through the
composite image:

| Sites | Target register comes from |
| --- | --- |
| 9 in `0x800d2540` (`_Printf`-shaped), `jalr s4` | `s4` = parameter `a0`, copied at `0x800d2574` |
| `0x80000f10` | `lw v1, 0x70(v0)`: a struct field |
| `0x800a12e4`, `0x800a15e0`, `0x800a1b1c`, `0x800a2cec`, `0x800af7bc` | fields `4`, `8`, `0x2ec`, `0x460` and `4` of a parameter struct |
| `0x800a1320` | field `0x74` of the struct that global `0x80121af0` points to |
| `0x800a151c` | parameter `a1` through its home slot. Both callers load it from memory (`0x18(s2)`, an overlay-table entry) |
| `0x800b88d8` | global cell `0x80101e20` |
| `0x800bacb8`, `0x800badfc` | global cell `0x8012c350` (BSS) |
| `0x800cdb98` | field `4` of a list node reached from `0x80105a70` |

`_Printf` has five `jal` callers in the composite image, and the map
contains three of them:
- `0x800ae1c8` passes `0x800ae064` in `a0`, built with `lui`/`addiu`.
- `0x800cf01c` passes `0x800cef80` the same way.
- `0x800cf06c` is in `0x800cf050` (PrintUtils_VPrintf-shaped), which passes
  `lw a0, 0(a0)`: word 0 of the struct its caller supplies. That caller is
  `0x800ccda8` (GfxPrint_VPrintf-shaped). It forwards its own `a0`, which it
  receives from `0x800ccdc8` (GfxPrint_Printf-shaped). That function has
  five call sites, and each passes a struct pointer held in `s0` or `s3`.

### Parameter flow alone closes nothing

A register-only argument would cover any parameter that every caller sets
to a proven constant. It needs a closed caller set, an `s`-register copy
that the body never redefines, and o32 callee-saved preservation. It fails
on every site: each chain ends at a memory load. `_Printf` has four
constant callers out of five, but the fifth reads the struct.

### A field-store census is unsound

The obvious census finds one store of a code constant to offset 0 of a
parameter struct that matches: `sw t8, 0(a0)` at `0x800ccd1c`, which stores
`0x800cccc0` (GfxPrint_Init-shaped). So `{0x800ae064, 0x800cef80,
0x800cccc0}` is a plausible target set for `_Printf`. Plausibility is not
proof:

- The field has no fixed address. The objects are callers' locals or
  members of larger structs.
- Closed code holds 5633 store instructions. 3228 use a base other than
  `sp`, and 520 are `sw x, 0(base)` with a non-`sp` base, the same shape as
  the field store. None of their base addresses is proven, so any of them
  may write the field.
- Declared runtime functions write guest RAM at caller-supplied addresses,
  for example `osEPiStartDma`, `osRecvMesg` and `osContGetReadData`.
- A stack object's word 0 holds stale frame contents until the init
  function runs.

A sound census therefore needs points-to for every store address: field
and allocation-site sensitive, across 7684 blocks, plus write summaries for
the runtime functions. That is a whole-program memory analysis, not a
recognizer.

### Why runtime checking cannot stand in for the proof

Native lowering dispatches a `jalr` over its candidate set and faults 3
otherwise. So an unsound census would still be fail-closed natively. But if
a runtime-checked guess counted as closure, any guessed set would close,
and the closed-world gate would mean nothing. Returns (ADR-0127) and tables
(ADR-0132) close under assumptions with a stated reason, and native code
enforces those assumptions. A guessed census has no such reason.

### The one sound route measured: guarded cells

ADR-0132 makes table bytes read-only through the store guard (fault 2).
That idea generalizes to a *guarded cell*: a fixed-address word that only
named store PCs may write. Natively, any other CPU store or runtime write
that overlaps the cell would fault. The cell's value set would then be
statically sound: its initial bytes, plus the values proven at its writer
sites.

Yield on OoT is **1 of 22**:
- `0x800b88d8`: cell `0x80101e20` starts as `0x80004280`. Its only writer,
  `sw a0, 0x1e20(at)` at `0x800b8c64`, is a setter with one caller
  (`0x800a0be8`), which passes `0x80000b70`.
- Cell `0x8012c350` is written with `lw t5, 4(s0)`, a memory value.
- Every other site is a field of an object with no fixed address.

One site does not pay for a new native store check on every store, a
writer-PC table and a parameter-flow verifier. Revisit guarded cells only
if SM64 (milestones 2 and 3) shows fixed-address function-pointer cells as
a significant blocker class.

## Result

All 21 `jalr` sites stay open. `native_complete` stays false. No code
changed. The OoT measurement is unchanged at 7684 blocks and 29 guarded
blockers.
