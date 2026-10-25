# Rogue Squadron slot data and first visible screen (ADR-0275)

Base main: `1a521a0d3138fff80359e8215e1870f4d56f7081`.
Worker: `rs-first-frame-132c526a`; branch `t3/rs-first-frame`.
Coherent implementation checkpoint: `1d3cfc3b`.

## Fault and independent reference evidence

Fault2 is the lowerer's active-native-text/immutable-proof-data write refusal,
not an SB alignment or opcode restriction (`crates/plaid-lower/src/lib.rs`,
fault table and `plaid_protected`/`plaid_ovl_write`). The native stop's
PC80884650 is a compiler slot identity, not a physical placement. Overlay1
has synthetic link808760e0 and binds to actual guest800960e0; the instruction
is at linked800a4650, worda0620001: SB v0,1(v1), v0=41,v1=80096bfc.
It modifies a string byte5f at80096bfd; no emitted block covers that word.

The second code-built descriptor supplies ROMfdec0..126660 (287a0 bytes) at
800960e0. Full native RDRAM comparison finds0 differences with that payload;
the other two descriptor sources differ in159181/43466 bytes over their
respective extents. The raw data-first payload defeats the executable-prefix
heuristic, whose fallback marks the entire file as candidate text. Binding
therefore marked the string's word prot255; ovl_active[1] made the write
refuse. It is neither a relocated guest data pointer nor missing BSS.

An independent private observer runs the ROM naturally on pinned ares
9408cb43d4948fc3ea6e152a307a34348df3fe04 (ISC), with interpreter-only CPU/RSP.
At guest800a4650 after174642997 instructions/VI173 it sees the same word,
v0/v1 and source comparisons159181/0/43466. Before SB the RAM byte is5f;
after SB its existing D-cache line contains41. Native scheduling is an SDK
abstraction, so VI is not asserted equal to oracle timing. No diagnostic
snapshot supplies compiler input. Pinned SB/D-cache/FPR/Status source was
read, not copied. Original private observer and receipts remain ignored.

## General change and verifier

For slot alternates only, lower every map block into an executable range,
including its delay slot. Merge adjacent/overlapping ranges. Binding verifies
all emitted instruction bytes after relocation plus the existing immutable
table/tail-cell sources. Untouched gaps can change independently of identity.
Ordinary relocatable files retain their previous complete-file and BSS checks.
The protection union uses sorted disjoint intervals; proof data wins overlaps
and stays immutable even without a live frame. Binary search bounds membership
cost. No runtime MIPS decoder/JIT/interpreter or per-game exception is added.

All bound emitted code remains pinned while any overlay frame can resume.
Inactive text writes revoke; missing/changed text refuses rebinding, restored
text rebinds even after mutable data writes. Indirect dispatch still selects
only emitted native entries; unlowered candidate gaps never authorize code.
Ambiguous identities, missing overlays, stale mappings and immutable proof
inputs retain refusal semantics. CPU native_complete:false/19 residual sites
remain; this change proves no whole-ROM executable closure.

`runtime/test_slot_data.py` builds an original data-first slot through public
CLI discovery/lowering, executes actual guest copy/calls/byte stores and
compares all reported CPU state against pinned ares. It checks prefix and
inter-function data, code mutation/rebinding after data changes, tail-cell
immutability inside the candidate extent and live-frame code writes. Removing
the active-frame guard in a private generated unit kills the test. The source
is restored in finally; production source is never mutated by that test.
Malformed emitted ranges are rejected in the Rust verifier test. The first
full runtime gate exposed a data-only layout (text=0) regression in the public
verifier wrapper; it now supplies no instruction interval while retaining the
complete-file/BSS comparison. The existing every-byte/BSS contract passes. The runtime
gate invokes this contract together with retained overlay/slot/lifetime tests.

## Native continuation and readback

Every native request has a visible window and SDL_AUDIODRIVER=dummy. Only the
runtime stop JSON supplies VI/fault/PC. Visual checks use RDRAM, not desktop
capture. User ROM SHA2564813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d;
ROM/assets/save files and captures are ignored, never committed.

- Independent baseline: VI104/fault2/80884650,48graphics/54audio/32PI.
  Prior ADR0274 records VI105/48graphics/53audio, black framebuffer.
- Fixed30s explicit native-RSP request stops at VI114/fault12/80013c34,
  53graphics/62audio/36PI, RA80017f64; native19.250s/pipeline76.625s.
- Automatic unknown-GBI LLE readback: VI112/samefault/PC,53graphics; a naive
  320x240 decode is wrong (5659 nonblack pixels). Actual VI width is640.
- Private observation-only native wrapper records VI111/fault12/80013c34,
  VI width640, formatRGBA5551, Status2000ff01 and SDK thread80155520.
  Its640x480 RDRAM surface `first-frame.png` has19496 nonblack pixels/48colors,
  showing the readable Star Wars: Rogue Squadron copyright screen. It is a
  visible startup screen, not interactive-menu or gameplay acceptance.
- Automatic LLE with Start100:4/A110:4 repeats fault12/80013c34 nearVI112.
  Input cannot pass the unsupported instruction.

The next instruction is MTC0 at80013c34, after MFC0 Status and OR04000000.
The matrix routine requests2400ff01: FR0->FR1 while preserving other bits.
The current generic Status guard rejects guest writes in SDK-owned threads.
Even permitting that write would next fault11 at80013c40 because this map's
FPR accesses are statically FR0. Verified dynamic FPR layout lowering plus
scheduler/Status integration is a separate substantive change; no guard is
weakened here. Pinned ares uses distinct odd-FPR transfer rules in FR0 andFR1. Its independent
natural run reaches this MTC0 after219975593 instructions/VI216 and changes
Status2000ff01 ->2400ff01; the private oracle-fr.json records both boundaries.

## Iteration and acceptance procedure

This fresh checkout lacked target artifacts and Cargo on PATH. Cargo was
available in ~/.cargo/bin; default MinGW GCC15.2 is used. C: ran out of space
during the initial Rust build; only this worker's checked target/release and
target/native directories moved to private X:/Plaid-worker-artifacts/
rs-first-frame-132c526a backing. No protected junction was deleted or moved.
Shared .refs and RT64 Release are read-only junctions, never refetched/rebuilt;
the private synthetic oracle was copied. No RT64 patch or shared rebuild is
needed. No README edits or child agents.

409 unchanged RSP objects migrated in43.453s only after checking each old
normal cache key and byte-identical actual -O2 preprocessed output. Unchanged
CPU parts reuse only exact generated source/key equality; changed runtime
objects compile normally. Controls regenerate native lowering and RSP code
from retained content-bound ProgramMaps, with normal solver and source/
compiler/header/flag checks. This is runtime/lowering regression coverage,
not a claim of fresh discovery for those controls. Unused headless linking
is skipped for window-only controls.

The first sparse prototype emitted one memcmp per block; GCC exited1 without
a diagnostic (both normal temp and private X: temp). Coalescing contiguous
blocks yields145/39/10 disjoint protection intervals for the three overlays,
and the successful fixed pipeline takes76.625s including19.250s gameplay.
The failed warm prototype took62.437s but produced no executable: it is not a
throughput baseline. This is a generation-size correction, not a measured
steady-state speedup. Full command timings and exit codes live in ignored
`target/receipts/rs-first-frame`.

Final local gate commands, on the final tree before fast-forward integration:

```
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
python scripts/test_cli.py
python runtime/test_runtime.py
python tools/progress.py --check
```

The ignored gate.json/runtime-gate.json and per-command logs are authoritative
for results/timings. Controls are silent visible30s PM/BK/MM/SF64/OoT; MP2 uses
Start600/1250 and A1360/1440/1520/1600/1680/1760 (all4VIs). OoT save-load uses
60s, Start1200 and A1400/1550/1700/1850 (all4VIs). Stop JSON, commands, timings
and MP2/OoT framebuffer images remain in the receipt directory. MP2 must still
show destination selection; these controls do not imply RS gameplay closure.

Integration uses a final refetch, exact base equality, direct-parent/tree
checks, merge-base ancestry and plain `git push origin HEAD:main`; no force.
The final landed SHA is recorded in the issue4 closeout and integration.json.
