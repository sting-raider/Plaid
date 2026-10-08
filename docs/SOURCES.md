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

Pinned core license: ISC with BSD SLJIT and additional upstream notices.
`spikes/003-ares-oracle/` builds separately and preserves LICENSE under ignored
target/. The bounded interpreter oracle agrees with Mupen on eight original
integer/control fixtures and verifies four cartridge/linked-memory/address-error
cases. No reference code is linked into Plaid core or a native artifact.
`spikes/004-ares-fetch/` additionally observes exact CPU fetches on the untouched
homebrew with a generated const debugger accessor. Its synthetic SP-entry/budget
scope excludes authentic PIF/IPL2 boot and complete-suite claims; streams remain
ignored and no RAM-copy or executable-lifetime inference is introduced.
`spikes/005-ares-physical-fetch/` records existing effective physical/cache inputs
in a generated CPU fetch TU. Cache-staleness, TLB remapping and endian-selection
fixtures pass; full broad checkpoint and v0-projection agreement remain exact.
The metadata establishes access context, not source backing or code lifetime.
`spikes/006-ares-rom-source/` forwards the actual ROM PI device once and records
returned halves in a bounded interpreter fetch window. Six original cases check
real source reads and rejection of latch/open-bus/prior-data contamination, with
unchanged CPU/PI checkpoints. Source/image promotion remains separate work.
`spikes/007-ares-rom-fetch/` extends that sensor to the bounded homebrew prefix:
1,852 reads at 65 canonical offsets, exact physical-capture projection and unchanged
checkpoints/messages. Other memory sources and executable lifetimes remain unknown.
`spikes/008-ares-pif-boot/` reads the existing NTSC CPU PIF firmware as an ignored
local input and records its digest, with no firmware bytes in project sources.
Natural CPU power entry and repeated checkpoints pass within a fixed NTSC/6102
profile. The reference PIF processor remains HLE; boot/source/lifetime scope is
not promoted into production or native mode. No firmware redistribution is added.
`spikes/009-ares-boot-profile/` versions the complete declared setup and checks
unchanged v3 projection/checkpoints. These metadata remain reference inputs;
source, executable-lifetime and hardware-equivalence claims are not promoted.
`spikes/010-ares-cache-snapshot/` reads selected instruction-cache fields at the
existing prologue, without coherence/translation/bus calls. Twelve original
fixtures preserve repeated CPU/timing and full RAM/cache checkpoints. Slot/data
observations remain finite context, with fill/copy/mutation lineage unresolved.
`spikes/011-ares-cache-fetch/` extends selected-line sensing to the bounded boot
prefix, with prior-stream projections and unchanged repeated CPU/device/memory/
cache checkpoints. Research v5 remains unsupported by production; snapshot
payloads establish neither fill provenance, epochs nor executable coverage.

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
