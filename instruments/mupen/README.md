# Mupen discovery instrument

Pinned revision: `ba95bab92a76744753bfe61470823a4937850ab0`.
This patch and sink are GPL-2.0-or-later, separate from Plaid core. See the
reference's `LICENSES` and original source notices. `COPYING` contains the GPL v2
text copied from the pinned reference's `doc/gpl-license`.

Run `python scripts/prepare_mupen.py`, then build Mupen normally with new_dynarec.
The script refuses a different revision or unrelated tracked reference edits.
Set `PLAID_TRACE_PATH`, `PLAID_ROM_SHA256` (canonical big-endian hash), and
`PLAID_ROM_SIZE` before starting the reference. These identity values are supplied
by the caller, not independently verified by the sink. Always compare them with
Plaid's normalization output. The sensor is disabled unless a path is set.

`python scripts/test_exporter.py` builds a strict C99 synthetic driver, checks
deterministic bytes and guest fields, and passes its output to the Rust parser.
This tests the sink protocol, not a complete running Mupen session.

`python scripts/test_mupen_hooks.py` compiles the actual pinned `new_dynarec.c`
and cartridge ROM copy routine with synthetic inputs. Four compilation units
exercise normal and pagespan entries, links, invalidation and DMA. It checks
deterministic traces, canonical source matching, generation separation and OPEN
solver output. Generated host code is never executed. Runtime helpers abort if
called; a fixed interrupt-time helper supports the copy test only and establishes
no timing semantics. This is not a running reference CPU oracle.

`python scripts/test_mupen_execution.py` separately executes synthetic integer/
control code on the actual pinned x64 dynarec and pure interpreter and compares
all GPRs, HI/LO and PC, with tracing enabled and disabled. Linux GCC/NASM are
required; Windows dispatches the worker through WSL Ubuntu. Unsupported runtime
services trap. Flat memory and a sentinel stop policy exclude full boot, devices,
interrupt timing and broader CPU semantics.

`python scripts/test_mupen_session.py` builds a full pinned reference library in
ignored `target/` from a clean Git export plus the research patch. An original
synthetic IPL3 fixture programs PI DMA, polls busy, executes the copied payload,
checks RAM store/load, and reports completion through IS64 MMIO. The frontend
attaches bundled dummy plugins and stops via the public API. All GPRs, HI/LO and
PC agree across pure/traced/untraced engines; repeated 42-event traces match.
Two further fixtures replace code at the same RAM address and execute through
cached/uncached entries. Their CPU states and 81/80-event reruns match; the importer
keeps generations separate and marks physically overlapping sources as candidates.
CPU-store mutation and CPU-copy fixtures also agree across engines (78/33 events).
Changed PI-backed snapshots remain Unknown; CPU copies produce no invented DMA
or canonical load source. Load mappings distinguish copy events from recompilation.
An additional store/register stress fixture checks zero and branch-delay-slot
stores. With `PLAID_TRACE_WRITES=1`, the six sessions emit 43/83/82/82/34/48 events.

`PLAID_TRACE_WRITES=1` enables a restricted x64 sensor after successful aligned
SW to a constant cached-RDRAM address, including return from an invalidation stub.
It preserves caller-save registers and reports source PC, destination and value.
Raw stores survive import; overlap with a previously compiled physical region
adds Unknown executable-write evidence. Dynamic addresses, other store sizes,
TLB/uncached paths and non-x64 hosts are outside this capability. The stress case
identifies the older still-running source unit through explicit unit tags. Its
return also gains a verified dirty-entry snapshot, adding one event (49 total).
Raw evidence is retained; other unsensed restore paths remain unresolved.
The importer verifies ROM sources for executed DMA-backed units and keeps raw
indirect evidence. The boot source remains unverified and the solver stays OPEN.
Linux requires GCC/make/NASM and SDL2/zlib/libpng headers/runtime libraries;
Windows uses WSL Ubuntu. See `scripts/build_mupen_core.py` for prefix overrides.
Dummy plugins exclude rendering/audio/RSP. PIF HLE with unknown-CIC fallback is
reference setup for this synthetic test, not verified commercial boot behavior.

Set `PLAID_TRACE_EXECUTION=1` to emit source-correlated x64 JR/JALR events.
The generated sensor preserves allocated caller-save registers and the saved
pre-delay-slot target. It runs after the delay slot and before either general
lookup or inline mini_ht dispatch; repeated return-cache hits are tested.
Each event includes the trace-local unit ID embedded at compilation. Import
validates that the unit already completed and contains the source PC, then uses
its exact decoded identity even if invalidation has advanced the epoch. The raw
map records a session-qualified CompileBegin evidence reference. Targets still
require a unique snapshot in the current epoch; legacy events lacking unit
context retain conservative source joins. No execution sample closes a site.
Successful dirty lookups additionally emit `entry_bytes_verified` after the
reference compares saved unit bytes against memory. Entry/mask and complete words
must match the earlier completed unit. ProgramMap preserves this separate raw
snapshot fact; it may explain a pending older target before the next invalidation.
It cannot explain a future observation or establish execution/copy/closure.
Page-spanning predecessors record an indirect source tag and source unit. The separate delay-slot
unit emits only when its predecessor tag matches, using the saved branch target;
direct predecessors clear the tag. Eight scenarios agree across traced/untraced
dynarec and pure interpreter, including pagespan JR/JALR, custom links, likely
annulment and register stress. Other hosts remain outside this capability.

Instrumented hooks: validated compile begin, compilation finish before Pass 10,
normal/restricted/pagespan entry installs, dynamic linker and lookup helpers,
outgoing links, generic invalidation, and page invalidation. Units contain actual
instruction words, not host code or host identities. Global invalidation is null.
The cartridge hook records actual copied ROM bytes, clipped at ROM and RDRAM
ends; zero-fill and zero-length operations do not become ROM-copy evidence.

Limitations: broader restored-entry/cache-hit coverage, ProgramMap pagespan predecessor state, non-x64 execution
sensors, non-PI copies and RSP sensors remain unimplemented.
Runtime links may also be created at compile time. Cache expiry is not emitted.
Invalidation is not proof of a memory write. Trace v0 cannot prove complete
coverage; crashes and unfinished sessions intentionally lack a valid end record.
