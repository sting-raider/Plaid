# W003 - Mupen64Plus `new_dynarec` instrumentation map

Date: 2026-10-08

Reference: `mupen64plus/mupen64plus-core` @ `ba95bab92a76744753bfe61470823a4937850ab0`

## Result

Mupen's current `new_dynarec` has a small enough hook surface to serve as Plaid's first dynamic executable-discovery sensor without changing execution semantics.

The important distinction is that we do **not** need to serialize Mupen's host-code cache. We need to serialize the *guest-side facts* Mupen learns while generating and linking that cache.

## Primary hook points

### 1. Block discovery / compilation request

File: `src/device/r4300/new_dynarec/new_dynarec.c`

Functions:

- `new_recompile_block(int addr)`
- `new_recompile_block_impl(int addr)`

`new_recompile_block()` is the W^X/JIT-write wrapper. `new_recompile_block_impl()` is the useful semantic hook.

The implementation explicitly performs a multi-pass compilation pipeline:

1. disassembly;
2. register dependencies / branch targets;
3. register allocation;
4. branch dependencies;
5. pre-allocation;
6. clean/dirty optimization;
7. 32-bit register analysis;
8. host assembly;
9. linker;
10. cache garbage collection.

**Instrumentation recommendation:** emit `BlockCompileBegin` after the guest virtual address has been validated/mapped, and emit `BlockCompiled` after Pass 9 has installed entry points but before Pass 10 can expire older code.

Do not use host code pointers as persistent identity. Persist guest addresses and source/mapping evidence instead.

### 2. Newly installed guest entry points

Within `new_recompile_block_impl()`, compiled guest entry points are inserted into `jump_in` with calls shaped like:

```c
ll_add(jump_in + page, vaddr, entry_point, ...)
```

Dirty/verification entries are also inserted into `jump_dirty`.

These insertions are a stronger hook than guessing function boundaries from emitted host code because they identify the guest virtual addresses that Mupen considers valid compiled entry points.

**Instrumentation recommendation:** wrap or instrument the `jump_in` insertion sites and emit `EntryPointInstalled { guest_addr, block_start, block_end, source_page }`.

### 3. Runtime missing-target discovery

Functions:

- `get_addr(...)`
- `get_addr_ht(...)`
- `get_addr_32(...)`
- `dynamic_linker(...)`
- `dynamic_linker_impl(void *src, u_int vaddr)`
- delay-slot variant `dynamic_linker_ds*`

When runtime execution reaches a target that has no compiled block, these paths eventually call `new_recompile_block(vaddr)`, then retry linking/lookup.

This is the exact event Plaid cares about: **an execution path proved that `vaddr` is executable even though it was not previously in the closed map.**

**Instrumentation recommendation:** in `dynamic_linker_impl` and the delay-slot equivalent, emit `TargetObserved` before compilation/lookup resolution. Include the source branch site's guest PC if it can be recovered from the link metadata; otherwise capture the source host stub only as a temporary correlation key and resolve it to a guest site through the link tables before writing the portable trace.

### 4. Branch/link creation

Function:

- `add_link(u_int vaddr, void *src)`

`add_link()` adds an outgoing link to `jump_out` after a target is linked. Pass 9 also resolves generated branch stubs, patches host branches when a target already exists, and otherwise leaves them routed through the dynamic linker.

This gives two different facts:

- a compiler-discovered direct edge;
- a runtime-observed/linked edge.

They should not be conflated.

**Instrumentation recommendation:**

- collect direct branch/call edges during the disassembly/branch-target passes;
- emit `RuntimeLink` from `add_link()` only as additional trace evidence.

### 5. Invalidation / executable writes

Functions:

- `invalidate_cached_code_new_dynarec(struct r4300_core*, uint32_t address, size_t size)`
- `invalidate_block(u_int block)`
- `invalidate_block_impl(u_int block)`

The generic R4300 code calls `invalidate_cached_code_new_dynarec(...)` when writes affect cached dynarec code. `invalidate_block()` wraps `invalidate_block_impl()` in the JIT write-protection bracket.

This is essential for detecting code whose bytes can change after initial compilation.

**Instrumentation recommendation:** emit `ExecutableWriteInvalidate { guest_address, size/page }` from `invalidate_cached_code_new_dynarec()` before block invalidation. Later, correlate the write with PI DMA/memory-copy instrumentation to distinguish overlays from true self-modifying/generated code.

## Proposed trace schema v0

Portable events should contain guest facts, not ephemeral host pointers.

```text
TraceHeader {
  schema_version,
  rom_sha256,
  reference_engine,
  reference_revision
}

BlockCompileBegin {
  seq,
  guest_start,
  guest_physical_start?,
  delay_slot_entry
}

BlockCompiled {
  seq,
  guest_start,
  guest_end,
  instruction_count,
  entry_points[]
}

DirectEdgeDiscovered {
  seq,
  site_pc,
  target_guest,
  kind: branch | call | jump,
  delay_slot_pc
}

IndirectTargetObserved {
  seq,
  site_pc,
  target_guest,
  delay_slot_pc?,
  observation_count_delta
}

RuntimeLink {
  seq,
  site_pc,
  target_guest
}

ExecutableWriteInvalidate {
  seq,
  guest_address,
  size
}
```

A later W012 trace extension should add ROM-source/DMA/overlay evidence rather than overloading the first schema.

## Important implementation notes

### Guest virtual address vs physical/source identity

Mupen internally has both virtual-address lookup structures and TLB/direct-map translation. The trace should preserve the guest virtual PC because that is what control-flow uses, while optionally recording translated physical/source information for overlay correlation.

### Delay slots

MIPS delay-slot entry must not be erased from the evidence model. Mupen has separate dynamic-linker handling for delay-slot cases, and its compilation entry API also encodes special entry semantics. The trace should therefore record the branch instruction PC and delay-slot PC separately where available.

### Code cache expiration is not program invalidation

Pass 10 can expire old host blocks because Mupen's generated-code cache is finite. Plaid must **not** interpret normal host-cache eviction as evidence that guest code ceased to exist. Only guest memory/code invalidation events matter to `ProgramMap` correctness.

### `jump_in` is not a function table

Entries are executable guest entry points/basic-block targets, not recovered source-language functions. Plaid must derive or model functions separately; correctness should be based on executable control-flow coverage, not pretty function boundaries.

## Minimal instrumentation patch strategy

The first Mupen research fork/patch should add a tiny trace sink with no dependency on Plaid core:

```text
new_dynarec trace hooks
        |
        v
newline-delimited binary/JSON events
        |
        v
Plaid importer
        |
        v
ProgramMap evidence
```

Keep the patch GPL-compatible and separate from Plaid's project-owned core until the licensing strategy is finalized.

Suggested initial hooks:

1. `new_recompile_block_impl` begin/end;
2. `jump_in` entry installation;
3. `dynamic_linker_impl` + delay-slot equivalent;
4. `add_link`;
5. `invalidate_cached_code_new_dynarec`.

That is sufficient for the first executable-discovery experiment. PI DMA/overlay provenance is intentionally deferred to W012.

## Conclusion

W003 hypothesis is supported: Mupen's dynarec exposes a compact set of semantic hook points that can export the runtime executable map Plaid needs without serializing or depending on Mupen's temporary host-code cache.

The next dependency is W004: define the versioned trace format and Plaid-side importer. W002 (`ProgramMap`) should proceed in parallel because the trace format should map cleanly into it.
