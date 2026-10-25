# Rogue Squadron: host-owned PI manager and task-load identities

Worker `rs-pi-jumptable-155f53e5`, base main
`e0447d439785233ac9d385f3d31cf7c8554598e1`; ADR-0273.
No child agents. README remains integrator-owned and untouched.

## Diagnosis

Local user-supplied Rogue Squadron USA Rev1, SHA256
`4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d`.
Independent silent visible execution of the preceding worker's final artifact
reproduces VI0/fault3/PC8002a2e4. Stop JSON gives v0=8002a2ec,
s6=80000cb0 and five SDK host thread records. No PI DMA, graphics or audio
has completed. All addresses here are diagnostic metadata, never matcher keys.

The routine begins at 8002a080 and implements __osDevMgrMain. At 8002a2c8
it reads the OSIoMesg type, subtracts 10, checks SLTIU7 and dispatches through
a seven-word table. Type11 selects index1, the ordinary cartridge read-DMA
case at 8002a2ec. The table words are:
8002a3cc,8002a2ec,8002a320,8002a3dc,8002a3dc,8002a354,8002a390.
Its ROM offset is 18b0 in the initial loaded image; it is not BSS initialized,
a missing overlay or overlapped decoded code. The entry prologue establishes
s6 at 8002a09c/a0a4. Receive calls and repeated loop paths separate that
constant from the switch. The bounded all-path table analysis has no surviving
base witness even though the local seven-way bound exists. This work does not
change that proof or add its targets speculatively.

osCreatePiManager at 80029e50 initializes queues, event8, priority and the
standard OSDevMgr, installs raw PI/EPI function pointers, creates its manager
thread at 8002a080, starts it and restores caller priority. osPiStartDma at
80029d70 constructs the standard message and sends/jams it to that manager.
Both compiled bodies differ from the pinned n64sym variants. Plaid already
owns these public APIs; leaving one guest implementation active creates a
mixed host/guest SDK boundary. Recognizing the family and using the existing
host PI implementation is the appropriate API-level fix.

## Implementation and verification boundary

Extend the existing full-body normalized-digest matcher. Retain exact external
named peer calls, function-relative internal jumps, scalar reference identities,
shared globals, body extents and no-hole/no-slot requirements. Public PI APIs
bind the existing runtime; no raw __osDevMgrMain runtime entry is introduced.
Its callback/raw-DMA pointer references are inert address metadata in the
replaced manager setup, not authenticated executable bodies or closure roots.
The existing SDK runtime ABI assumption is retained explicitly.

The PI and SI access-queue initializers have identical normalized bodies but
different globals. A helper profile can opt into a named owner: its verified
caller must call that exact entry and share agreeing globals. Failed owners
and dependencies are removed to a fixed point before ordinary ambiguity and
global-alias checks settle. This does not select an arbitrary duplicate or
relax ordinary peer ambiguity. The disabled-assert dependency in the SP graph
uses the same owner mechanism and is never exposed as a runtime API.

Binding PI DMA first completes one transfer and reaches missed osYieldThread,
fault1/8002e4ac. Its full scheduler/global peer graph now binds the existing
yield API. The next stop is raw SP status at 8002ba28, from osSpTaskLoad at
8002b6e0. Authenticate that complete task-loader and its copy, address-conversion,
TLB-probe, SP register/DMA/busy, writeback and disabled-assert peers; bind the
existing osSpTaskLoad and osVirtualToPhysical runtime APIs. There is no new
CPU/RSP execution implementation and no weakened MMIO/native target guard.

Synthetic authored bodies cover relocation, exact owner calls, corrupt owners,
shared PI globals, ordinary duplicate refusals and the retained body/peer/MI
table mutations. Inverting the production owner direct-target equality makes
`owned_helpers_require_the_authenticated_callers_exact_call` fail; the source
is restored. Seven SDK matcher tests pass afterward. Runtime PI contracts
exercise both priorities, O32 stack arguments, copied ROM bytes, v0 returns,
completion messages, s6 and RAM canaries; unsupported writes/bounds are refused.
The full gate retains scheduler saved-register/queue/interrupt tests, RSP
state/memory/fetch guards and pinned-ares comparisons.

Read-only references, checked against refs.lock.toml:

- n64sym ccf4600f3389f1a84bde23339225cf372fdf7712,
  src/builtin_signatures.sig and LICENSE.md: SDK naming/variants and relocations;
  MIT, Copyright (c) 2017-2020 shygoo.
- N64ModernRuntime cdf5abbd5026fef5c364c676e4667c45e42b6863,
  librecomp/src/pi.cpp: no-op manager creation and host PI DMA entry boundary;
  GPL-3.0 COPYING. Behavioral comparison only; no code copied.
- ares 9408cb43d4948fc3ea6e152a307a34348df3fe04 remains the retained CPU/RSP
  differential oracle (ISC). Private oracle copy retains checked driver,
  fixture and recipe hashes; shared reference sources are read-only.

No SDK/game instruction body, ROM, copyrighted asset or snapshot is committed.
Only normalized digests, extents and relocation/call metadata accompany the
project-owned matcher logic and authored synthetic programs.

## Measured result and remaining blocker

Identification rises 25 -> 32 runtime functions. CPU residual sites fall
20 -> 19; native_complete remains false. No target guard or closure gate changes.
The ordinary RT64 HLE path now reaches an unsupported GBI, emits its diagnostic,
and access-violates (exit3221225477) without stop JSON. Do not invent VI/fault/PC
for that process or treat it as a successful frame.

With the existing --rsp-gfx path, a 30-second request stops in 1.500s on
`unlowered RSP code`: VI1, CPU fault0/fault_pc00000000, RA800146d0,
15 PI DMAs, one graphics task, zero audio tasks and twelve SDK thread records.
The RSP entry is db0; a separate 30-second readback request stops in 1.578s
with the same counters. Framebuffer006dd280, decoded as 320x240 RGBA5551,
is almost entirely black with a few low green pixels and no title/menu.
No applicable Start/A menu interaction exists yet. Desktop pixels are not used.

Diagnostic-only IMEM snapshots show the refused 64-byte prefix uniquely in ROM
at20518. The prior 080 placement contains that sequence eight bytes later;
the refused db0 snapshot SHA256 is
7d97bedb380fd73e51131f3f977614bdb16d1ee12b2c83820fa97b63bb6eecfc.
Recover its DMA/placement provenance and candidate coverage before further
native graphics acceptance; a numeric ROM match alone is not that proof.
Snapshots were never fed to discovery or native compilation. HLE support and
ROM-derived RSP placement remain separate unresolved work.

## Acceptance and iteration receipt

All runs use SDL_AUDIODRIVER=dummy, visible SDL windows, the default MinGW
GCC15.2, runtime stop JSON and completed RDRAM/framebuffer readback. No desktop
captures. Shared .refs and RT64 Release remain untouched; no protected junction
is recursively removed, no reference is refetched and the shared shim is not
rebuilt. Retained load declarations are content-verified compiler inputs, not
closure proof or a claim of fresh-ROM analysis coverage.

Reproduce the bounded run with:

```
python scripts/native.py <local-rom> --loads <retained-verified-loads.json> --rt64 --rsp-gfx --seconds 30
```

Local acceptance commands on the final exact tree:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

Required controls: PM/BK/MM/SF64/OoT at30s, MP2 at30s with Start600/1250 and
A1360/1440/1520/1600/1680/1760 (all4VI), and OoT at60s with Start1200 and
A1400/1550/1700/1850 (all4VI). The frozen-tree command exit/timing records,
final control VI/fault/PCs and readback evidence are retained under ignored
`target/receipts/rs-pi-jumptable/` and summarized in the issue #4 closeout.

Fresh RS rebuilds repartition CPU C when SDK identities change. Unchanged
outputs still use native.py's source/compiler/header/flag cache checks. For
controls, migrating328 retained RSP objects took33.110s, each only after its
old normal cache key and byte-identical actual -O2 preprocessed output at
old/new paths were checked. The subsequent cached RS pipeline takes6.016s
including its1.500s native refusal, versus the25.015s preceding pipeline
without the final task-load identity. Different semantic stop points mean
this is iteration latency, not a native game speed comparison. Window-only
validation omits unused headless compilation/linking. No stale headless build
is used as acceptance evidence.
