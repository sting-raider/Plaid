# Upstream / Reference Source Map

All commits below are pinned in `refs.lock.toml`. `scripts/fetch_refs.*` clones them into `.refs/`, which is gitignored.

These projects are **references by default**, not automatically vendored dependencies. Check each license before copying or linking code.

## N64Recomp/N64Recomp

Purpose:

- static N64 recompilation model;
- MIPS instruction lowering;
- direct-call/tail-call translation;
- jump-table/relocation handling;
- `LiveRecomp` host-code generation architecture.

Why it matters: this is the closest existing proof that N64 binaries can become standalone native code.

## mupen64plus/mupen64plus-core

Purpose:

- study `new_dynarec` runtime block discovery;
- understand how unknown guest PCs become translated blocks;
- observe mature handling of dynamic control flow and invalidation.

Planned use: instrumented discovery/reference fork or patch series. Not the final runtime.

## ares-emulator/ares

Purpose:

- accuracy-oriented N64 behavioral oracle;
- CPU/RSP/hardware semantics;
- differential testing/reference implementation.

## gopher64/gopher64

Purpose:

- readable Rust implementation of N64 CPU/hardware behavior;
- additional behavioral oracle;
- useful reference for Rust-side data structures and semantics.

## N64Recomp/N64ModernRuntime

Purpose:

- study native runtime boundaries for recompilation projects;
- libultra-style services, events, saves, overlays, PI/VI/RSP integration.

## rt64/rt64

Purpose:

- evaluate modern native N64 rendering integration;
- avoid rewriting the RDP/rendering stack in the first research milestone.

## Decompollaborate/spimdisasm

Purpose:

- N64-focused MIPS static analysis;
- function/pointer/symbol discovery;
- candidate frontend or validation source for our `ProgramMap`.

Pinned source license: MIT. A separately built comparison in
`spikes/001-spimdisasm/` uses the backend with original fixtures and explicit
section/mapping inputs. Its PARTIAL verdict treats functions/tables as hints;
there is no production dependency or exhaustive coverage inference.

## Decompollaborate/rabbitizer

Purpose:

- MIPS/RSP instruction decoding and register tracking;
- compare against or integrate for early decoder work.

## shygoo/n64sym

Purpose:

- known N64 library-function signature discovery;
- identify libultra/common routines without requiring symbols from the user.

## lemmy-64/n64-systemtest

Purpose:

- correctness tests for CPU, exceptions, TLB, memory, RSP, and other N64 behavior;
- verification corpus for lowering/runtime work.

Pinned source license: MIT. `spikes/002-systemtest-discovery/` builds guest source
with exact nightly-2022-07-10 and locked dependencies; the separately installed
MIT nust64 0.4.1 packager includes libdragon open-source IPL3. ROM/ELF/tool outputs
stay ignored and are not runtime dependencies. The PARTIAL headless probe exposes
unsupported cartridge execution in the dynarec and LLD/exception/LLAddr limits
in the interpreter. This pin cannot serve as a universal CPU oracle by itself.

## Source-use policy

Before introducing code copied or linked from an upstream project:

1. inspect its current license at the pinned commit;
2. record the decision in `docs/DECISIONS.md`;
3. preserve notices and obligations;
4. avoid contaminating a permissive component with GPL code accidentally;
5. when uncertain, use the project as a behavioral/reference oracle instead of copying implementation text.
