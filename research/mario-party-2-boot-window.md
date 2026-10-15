# Mario Party 2 boot window: a second closure measurement

Date: 2026-10-15. Measured at base f1fd0f9 (ADR-0147). Decision: ADR-0148.

## Why

Milestone 3 needs SM64, and no SM64 ROM is available locally. Mario Party 2
(USA), from the user's local ROM folder (read in place, never copied into the
repository), is a second commercial vehicle that shows which blocker classes
generalize beyond OoT.

## Commands

```
plaid identify R 0x1000 0x80000400 0x100000 .refs/n64sym/src/builtin_signatures.sig > id.json
plaid discover R 0x1000 0x80000400 0x100000 0x80000400 map.json id.json
plaid solve R map.json --guarded-ram
```

## Result

- 51 runtime functions identified; `osViGetCurrentFramebuffer` is ambiguous.
- 712 blocks, 92 indirect sites. OPEN, with 29 guarded blockers.
- **27 instruction-scope blockers.** All of them are in libultra system
  routines that identification missed: `CACHE` in three cache routines
  (`0x800a1d40`, `0x800a1df0`, `0x800a1e70`), `MTC0/MFC0` in four COP0
  accessors, and `MTC0/TLBWI` in two TLB routines.
- **2 unresolved indirect sites.** `0x8007ed20` calls `node->fn` while
  walking a linked list rooted at two globals. `0x8007edcc` calls a
  function pointer carried in a message. Both load their targets from
  memory, so they hit the ADR-0142 store points-to frontier.

## Why identification missed them

Every call into the system routines comes from one function at
`0x800a7d40`, plus one game call into the D-cache routine. That function is
the SDK's `osInitialize`, which N64Recomp reimplements. Declared as a runtime
function, it would hide its callees from discovery.

n64sym's database has three `osInitialize`/`__osInitialize_common` variants
whose first 8 bytes (crcA) match at `0x800a7d40`, but none of their
whole-body CRCs (crcB) match. The cache routines behave the same way. For
example, `osInvalICache` at `0x800a1df0` matches the crcA of three variants
of size `0x74` and the crcB of none. Its body schedules
`addiu t1,t1,-0x20` before `andi t2,t0,0x1f`, which no listed variant does.
Mario Party 2 uses a libultra build the database does not cover.

Plaid does not accept crcA-only matches. A wrong name would bind guest code
to the wrong host implementation.

The tiny COP0 accessors (`__osSetSR`, `__osGetSR`, `__osGetCause`,
`__osSetWatchLo`) and `osUnmapTLBAll` do match exactly. But N64Recomp does
not list them as reimplemented: only the unidentified `osInitialize` calls
them.

## Consequence

Signature coverage depends on the SDK build, so it is a per-game risk for
milestone 3 as well. ADR-0148 adds the path N64Recomp itself uses: name
runtime functions from a reference symbol map (`plaid identify ...
--symbols`), the same decomp map milestone 2 already uses as its recall
oracle. With a symbol map for Mario Party 2, the 27 instruction blockers
would sit behind `osInitialize` and the cache routines. Without one, they
stay open. The 2 pointer calls remain OPEN either way.
