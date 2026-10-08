# Architecture

## Final product boundary

```text
                +----------------------+
ROM ----------> | Compiler / Analyzer  |
                +----------+-----------+
                           |
                           v
                  Executable Program Map
                           |
                           v
                  Native Host Code
                           |
             +-------------+-------------+
             |                           |
             v                           v
      N64 Compatibility Runtime      Renderer/RSP
             |                           |
             +-------------+-------------+
                           v
                  Windows/Linux/macOS
```

The compiler may use instrumented emulators/dynarecs during preparation, research, and verification. The final native gameplay artifact must not require runtime MIPS instruction decoding or runtime MIPS JIT compilation.

## Core data model

The project should converge around an explicit `ProgramMap` rather than tool-specific metadata.

Conceptual fields:

```text
ProgramMap
  rom_identity
  regions[]
    rom_offset
    guest_vaddr
    size
    executable
    overlay_id?
  blocks[]
    guest_start
    guest_end
    direct_edges[]
    indirect_site?
  functions[]
    candidate_entry
    blocks[]
  indirect_sites[]
    guest_pc
    target_set[]
    evidence[]
  overlays[]
    rom_range
    load_address
    relocations[]
  executable_writes[]
  rsp_microcodes[]
  unresolved[]
```

Evidence should distinguish `static`, `trace`, `signature`, and `manual-test` origins.

## Guest addresses are not host pointers

Never replace a guest address with a host pointer globally. N64 code may store, compare, add to, relocate, or serialize guest addresses.

Use explicit types/concepts:

```text
GuestAddr(0x80123400)
NativeFn(UpdatePlayer_native)
```

and a linker/dispatch mapping between them.

## Native call lowering

Direct guest call:

```text
jal 0x80123400
```

may lower to a native direct call when the target is known and the observable guest register/link semantics are preserved.

Indirect guest call:

```text
jr $t9
```

requires a proven closed target set or a native dispatch representation over guest addresses. Unknown targets block a fully-native build.

## Executable overlays

The compiler must model code that moves from ROM into RAM and is relocated before execution. Overlay identity should be tied to ROM source bytes and load/relocation behavior, not only transient RAM addresses.

## Self-modifying / generated code

Any runtime write that produces executable guest code is a hard compatibility case. Detect it explicitly. Do not silently interpret it in native mode.

## Runtime

The runtime models N64-visible services and hardware effects required by the recompiled program, but it is not a guest CPU executor.

## Verification architecture

```text
same initial state
      |
 +----+-----+
 |          |
 v          v
reference   native
execution   execution
 |          |
 +----+-----+
      v
 state diff
```

Compare relevant:

- GPR/FPR/HI/LO state;
- PC/control-flow outcome;
- memory writes;
- exceptions;
- COP0-visible behavior;
- events/interrupt scheduling where applicable;
- MMIO effects.
