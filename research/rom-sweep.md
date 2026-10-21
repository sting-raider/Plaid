# Six unseen ROMs: ROM-only native sweep

2026-10-17; unchanged production tree at `6758817` (ADR-0188). Research claim:
measure the first fail-closed blocker of the normal ROM-only path on six titles
outside Plaid's development corpus. This supplies compatibility evidence for
milestone 5; no assumption is retired. Single worker, branch `rom-sweep`, no push
or canonical integration, no production edits.

## Method and limits

Read `AGENTS.md`, `ORCHESTRATION.md`, the architecture/plan/source documents,
current status/next steps, ADR-0188 and its retained research receipt. Current
status overrides README's stale statement that default RSP inputs are snapshots.
The command for **each** ROM was:

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
python scripts/native.py target/local-inputs/<short>.z64 --name sweep-<short> --rt64 --seconds 60 --require-audio
```

Only the ROM supplies game data; `--name` separates artifacts. No loads, symbol
maps, traces, snapshots or game-specific settings were supplied. Audio was
required for every title, had execution reached validation. Each first pipeline
process tree had a 1,500 s wall deadline; the script's native validation deadline
is `--seconds + 60` wall seconds. No deadline was hit. No runtime was reached,
so no native/game window opened, and there are **no measured VIs, graphics/audio
tasks, fault code/PC, or PCM peaks**. These are closure refusals, not runtime faults.
RSP extraction/selection, lowering, compile and link are **unreached** for all
six; ROM-derived candidate counts and unknown/ambiguous microcode compatibility
remain untested. No gate was bypassed to reach those stages.

Inputs came from `C:\Users\aliza\Documents\ROMs\N64\`, copied to ignored
`target/local-inputs/`. Exact basenames are the ROM column below plus `.z64`.
All six have magic `80371240`; `rom-info` reports `big_endian`. No conversion
was needed. Sizes are bytes (MiB in parentheses).

Plaid infers a boot destination for all six, including the 6103 header-entry
adjustment. It infers the BSS-based image size for five; Rogue Squadron uses
the default 1 MiB window because `boot_image_size` is null. A CIC label here
is a research cross-check, **not a CIC field emitted by Plaid**: sums of IPL3's
big-endian words match pinned Mupen `src/device/pif/cic.c` at
`ba95bab92a76744753bfe61470823a4937850ab0` (6101/6102/6103:
`cffb631223` / `d057c85244` / `d6497e414b`). The 6103 entry adjustment agrees
with pinned n64sym `src/n64sym.cpp:132` at
`ccf4600f3389f1a84bde23339225cf372fdf7712`. Source inspection only; no
reference implementation was copied or executed as an oracle in this survey.
Inferred boot metadata is not a verified complete boot/load model.

## Results

All six finish discovery and return `OPEN` under
`declared_static_images_guarded_ram_address_taken`; `native_complete=false`.
Every normal command exits 1 with `not CLOSED ... nothing is built`.

| ROM (short) | Size | CIC / inferred boot start; image bytes | Stage reached | First blocker class | Key evidence | Wall first / warm repeat |
| --- | ---: | --- | --- | --- | --- | ---: |
| Banjo-Kazooie (USA) (Rev 1) (`bk`) | 16,777,216 (16 MiB) | 6103 / `0x80000400`; `0x4e70` | Solve OPEN, 1 blocker | Missing post-boot executable image | `8000052c -> 8023d680`: target has no block; 0 loads | 53.531 / 0.703 s |
| GoldenEye 007 (USA) (`ge`) | 12,582,912 (12 MiB) | 6102 / `0x80000400`; `0x5cee0` | Solve OPEN, 7 blockers | Unmapped boot target + system effects | `800004b4 -> 70000510`: no block; 6 COP0 effects; 1 load | 0.984 / 0.938 s |
| Mario Kart 64 (USA) (`mk64`) | 12,582,912 (12 MiB) | 6102 / `0x80000400`; `0xf6510` | Solve OPEN, 31 blockers | Missing executable loads + system/indirect proofs | 4 unmapped PCs + 4 direct edges; 3 indirect sites; ERET/COP0; 1 load | 5.031 / 4.937 s |
| Paper Mario (USA) (`pm`) | 41,943,040 (40 MiB) | 6103 / `0x80025c00`; `0x749b0` | Solve OPEN, 204 blockers | Missing executable loads + system/indirect proofs | 8 unmapped PCs + 13 direct edges; 137 indirect sites; ERET/COP0/cache; 16 loads | 15.719 / 15.188 s |
| Star Fox 64 (USA) (Rev 1) (`sf64`) | 12,582,912 (12 MiB) | 6101 / `0x80000400`; `0xdd480` | Solve OPEN, 298 blockers | Missing executable images + boot/system proofs | 136 unmapped PCs + 157 direct edges; `8001efb8 -> a40000b0`; 0 loads | 3.407 / 3.547 s |
| Star Wars - Rogue Squadron (USA) (Rev 1) (`rs`) | 16,777,216 (16 MiB) | 6102 / `0x80000400`; `0x100000 fallback` | Solve OPEN, 211 blockers | Invalid table candidates + system/indirect proofs | 55 invalid table entries, 79 missing candidate targets, 12 indirect sites; 3 loads | 6.718 / 6.797 s |

BK's first time includes the release rebuild shared by subsequent runs. Its
warm repeat is 0.703 s; this is cache/build reuse, **not a production optimization**.
No per-ROM iteration bottleneck required investigation. A complete warm repeat
of the same six commands reproduced every discovery count, and rerunning solve
on those regenerated maps produced identical parsed verdicts.
Independent solve-only wall times (BK/GE/MK/PM/SF/RS) were
0.031 / 0.078 / 1.078 / 2.250 / 0.547 / 1.782 s.

| Measurement | BK | GE | MK64 | PM | SF64 | RS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Discovered blocks | 276 | 374 | 40,484 | 38,724 | 25,403 | 27,936 |
| Indirect sites reported by discovery | 17 | 30 | 2,974 | 3,257 | 1,462 | 1,640 |
| Discovery unresolved items (not scoped blockers) | 0 | 0 | 1,207 | 751 | 570 | 326 |
| Inferred loads | 0 | 1 | 1 | 16 | 0 | 3 |
| `unresolved_indirect_target` | 1 | 1 | 0 | 0 | 1 | 79 |
| `unmapped_target` | 0 | 0 | 4 | 8 | 136 | 0 |
| `unresolved_direct_target` | 0 | 0 | 4 | 13 | 157 | 0 |
| `unresolved_indirect_site` | 0 | 0 | 3 | 137 | 2 | 12 |
| `unsupported_scope_effect` | 0 | 6 | 19 | 45 | 2 | 52 |
| `exception_or_unsupported_instruction` | 0 | 0 | 1 | 1 | 0 | 1 |
| `invalid_pointer_table_entry` | 0 | 0 | 0 | 0 | 0 | 55 |
| `pointer_table_immutability_unproven` | 0 | 0 | 0 | 0 | 0 | 6 |
| `pointer_table_target_identity_unproven` | 0 | 0 | 0 | 0 | 0 | 6 |
| **Total scoped blockers** | **1** | **7** | **31** | **204** | **298** | **211** |

### Bounded diagnoses (hypotheses, not fixes)

- **BK:** header `80100400` adjusts to `80000400`; inferred image ends at
  `80005270`. The transfer at `8000052c` names `8023d680`, with no block and
  no inferred load. Hypothesis: post-boot code loading/decompression is outside
  current inference. `osInitialize` is already identified. One blocker does not
  mean one remaining obstacle to gameplay: only 276 boot-area blocks are known.
- **GoldenEye:** one raw load maps ROM `1050..33590` at `80000450`;
  boot code still targets `70000510`, absent from the map. Six effects at
  `80000470`, `480`, `490`, `49c`, `4a0`, `4a8` are five MTC0s and a COP0
  function. Hypothesis: boot mapping/system setup needs an explicit model;
  adding another plain ROM segment alone may not suffice. No `osInitialize`
  signature was identified.
- **MK64:** inferred secondary code starts at `8028df00`, while four missing
  sources are `802802ac`, `80280420`, `80281548`, `80281968`.
  ERET at `800d1a9c` and COP0 effects are also reachable. Hypothesis: another
  executable load and unrecognized SDK/system boundaries are required.
- **Paper Mario:** 16 loads were inferred but, for example, `80034b64` calls
  missing `80244060`; 137 indirect sites lack rechecked closed-target
  certificates. ERET at `8006b34c` plus COP0/cache effects remain. Only 18
  runtime functions were identified (neither `osInitialize` nor `osContInit`).
  Hypothesis: incomplete load/overlay inference and SDK identification amplify
  the indirect frontier; this survey does not prove which sites disappear.
- **Star Fox:** zero loads; many calls leave the main image, e.g.
  `80030ac0 -> 80199900`, with 136 distinct unmapped-PC diagnostics.
  There is also `8001efb8 -> a40000b0`, and MFC0/MTC0 effects at `8001ef40`
  / `8001ef4c`. Hypothesis: executable load inference plus a modeled boot/SP
  path is needed. `osInitialize` is already identified.
- **Rogue Squadron:** fallback 1 MiB boot window and 3 inferred loads
  (two share a slot). At table site `8006c694`, alleged targets include
  `8ca30004`, `8ce20004`; invalid entries include `00431021` and `08000915`.
  These resemble instructions, suggesting a table/base or image-classification
  error, not 79 established executable destinations. Six tables lack identity
  and immutability proofs. ERET at `80025d20` and many COP0/cache effects
  remain; only 12 runtime functions were identified. Hypothesis: qualify
  table provenance/bounds before expanding candidates. No inference that this
  title's custom RSP is the first blocker is supported by these runs.

## Ranked blocker classes and assumption ledger

Counts below are **ROMs with a demonstrated barrier in that class**, not ROMs
proven runnable after a fix; classes overlap. Guaranteed complete-ROM unlocks
from any single proposed fix: **0 demonstrated**. Difficulty is a qualitative
research estimate, not an implementation estimate validated by a spike.

| Rank | Class / affected ROMs | Reach | Estimated difficulty | README assumption ledger touched |
| --- | --- | ---: | --- | --- |
| 1 | Executable source/load/mapping inference: BK, GE, MK64, PM, SF64 | 5/6 | High: source-backed loads, aliases and possible decompression/overlays; BK is the smallest diagnostic | **1** executable universe/identity, **11** loads before entry, **12** overlay placement/lifetime; **3, 7** for mapped boot addresses |
| 2 | System instructions and runtime-boundary coverage: GE, MK64, PM, SF64, RS | 5/6 | Medium-high: identify genuine SDK variants or model COP0/cache/exception behavior with verifiers | **2** excluded system/external effects, **13** host libultra, **14** automatic runtime naming; **3, 7** for TLB/access semantics |
| 3 | Uncertified indirect sites: MK64, PM, SF64, RS | 4/6 | High: per-site data flow and rechecked certificates, after correct image recovery | **4** indirect targets, **5** callbacks, **6** returns; actual site roles still need classification |
| 4 | Invalid/unproven pointer-table candidates: RS | 1/6 | Medium-high: correct image/table/bounds evidence first, then immutable target identity | **8** read-only tables, **1** executable identity, **4** target closure |

**Single next fix:** extend general ROM-derived executable-load inference beyond
the BSS-bounded boot image, preserving source/placement verification. Start with
BK's `8000052c -> 8023d680` as a minimal retained regression, then test the same
mechanism against SF64/MK64/PM and characterize GE's mapping requirements.
This addresses the widest visible discovery barrier without broadening the
scope or disguising missing code as a larger indirect dispatch set. It is a
recommendation, not evidence that one loader pattern covers all five games.
RSP work has no measured unlock in this sweep because every ROM stops earlier.

## Reproduction, evidence and validation

Ignored raw evidence: `target/rom-sweep/<short>.stdout.log`, `.stderr.log`,
`.rom-info.json`, `.solve.json`, `.repeat.stdout.log`, `.repeat.stderr.log`.
`results.json` records commands, initial process IDs, start times, exits and wall
times. `repeat-timings.json` records command-boundary timestamps; `summary.json`,
`diagnosis.log` and `verification.json` retain derived diagnostics and repeat
checks. Reproduction helpers are `run_sweep.py`, `summarize.py`, `repeat.py`,
`diagnose.py`, `verify.py` in that same ignored directory. Initial inspection
helper `inspect_first.py` needed an absolute Windows executable path; that
harness-only correction did not affect any normal pipeline result.

The unchanged pipeline writes maps/IDs/loads into `target/native/sweep-<short>/`.
Large maps and generated game code were not dumped into the research context.
For complete solver diagnostics, without proceeding past the normal gate:

```powershell
.\target\release\plaid.exe solve target/local-inputs/<short>.z64 target/native/sweep-<short>/map.json --address-taken
```

| Short | SHA-256 of the exact big-endian input |
| --- | --- |
| bk | `f9ad43f64c3a38b0ca4067e24f570dcb8f3f8fec077c5c342484bcbec7ff6d22` |
| ge | `2cdcec8a9f0cb6e36337f3ee39d8ad105dc8afa6ba1c02d466e8f5b771f9a162` |
| mk64 | `d6b8538dd63f0132ecb2856e7d32816ed3c30e3e479aecd23cf83fb6ba17a5da` |
| pm | `9ec6d2a5c2fca81ab86312328779fd042b5f3b920bf65df9f6b87b376883cb5b` |
| sf64 | `385bcf1901ed12fb1152f3c227d1968cc54ae41e8566da66695df71af40a573f` |
| rs | `4813551d01d3a3474df3a51f84c31059cd2a9d1eeae7885dda51a88ee6b9f88d` |

Validation: all six normal commands executed twice with identical discovery
counts; exact solver verdicts reproduced on the regenerated maps (6/6).
ROM magic, byte order, sizes and SHA-256 metadata agree. All normal commands
fail closed as reported. No production Rust changes, so no production suite
was warranted for this documentation-only commit. All own survey/compiler
processes exited; no game process was started. Only this research note is
committed. No code changes, assumptions retired, native acceptance claims,
ROMs/assets, external messages, push or main write.

## Post-boot executable inference: partial implementation (ADR-0190)

2026-10-17; branch `post-boot-loads`, prepared on `5c0ddb5`. Single-worker
claim/hypothesis: a ROM-derived boot transformation can provide a general
executable image without recognizing a compressor or accepting a snapshot as
input. This work advances the mechanism and its verifier, **not commercial-ROM
closure**. The requested BK acceptance criteria remain unmet.

### Mechanism and authority

`plaid_core::boot_execution` executes an analysis-only bounded integer model
from the ROM's inferred boot address/window and declared IPL3 copy. Registers
other than r0 and RAM outside that copy begin unknown; writes can propagate
unknown values, but control, addresses and captured text cannot depend on them.
Execution stops at unsupported instructions, coprocessors, device/uncached
accesses, exceptions, unknown-dependent control or a 1,000,000-instruction
budget. No timers, controllers, firmware or guessed system-call results are
supplied. This is not an authentic PIF/IPL3 boot trace or a complete CPU/device
model. Its declared initial cache profile is empty, rather than reconstructed
from authentic IPL3 execution. Existing ares tracing was inspected first: its boot tooling needs
explicit state/firmware. Extending that verified path remains preferable to
inventing device semantics in this small model.

The first transfer beyond the boot window can yield the contiguous CPU-written
range containing its target. Every byte must be known, word aligned and written
back from D-cache; previously fetched instruction-cache lines are refused.
Normal KSEG0 D-cache line eviction and three writeback operations are modeled;
uncached aliases/discard and asynchronous device events are not. The public
`infer-loads` writes encoding `boot`, with consumed canonical ROM ranges,
transformation instruction count, target, ROM identity and output digest.
Composition executes the boot again and requires the exact output destination;
no supplied RAM snapshot can substitute for execution. Refusal preserves the
previous static declarations verbatim. Overlapping static declarations are
retained rather than overwritten by a boot candidate.

Native lowering reuses the existing declared-load content guard: executable
RAM bytes must equal the regenerated image before native entry; mutation revokes
verification, and mismatched text faults 8. No analysis executor, runtime MIPS
decoder, interpreter or JIT enters the generated C/native binary. This does not
close unknown targets or retire executable-universe/lifetime assumptions.

### Real ROM results

Each pair uses the archived pre-change release binary and the candidate release
binary to independently run `rom-info`, `infer-loads`, `identify`, `discover`
(with `--loads --address-taken --fr0`, and `--overlays` when available), then
`solve --address-taken`. No symbols or per-game load declarations were supplied.
The original survey inputs are retained; SM64/MM/F-Zero X/OoT use ignored local
ROM paths. Every pair has byte-identical load declarations, runtime IDs **and
complete maps**, including evidence identities. There are zero new accepted
commercial-ROM images. GE and Rogue Squadron were not rerun in this extension.

After collecting the complete map pairs, review added decoder validation and
canonical-address checks to the executor. The full local gate was rerun, and
final release inference was rerun for all eight ROMs: every declaration is still
byte-identical to both map-pair inputs. No map consumer or non-boot encoding
changed, so these retained map digests apply to those identical inputs. The
inference timings below use that final release recheck.

| ROM | Scoped blockers before -> after | Loads before -> after | infer-loads wall seconds before / after | Map |
| --- | ---: | ---: | ---: | --- |
| bk | 1 -> 1 | 0 -> 0 | 0.0318 / 0.2338 | identical |
| sf64 | 298 -> 298 | 0 -> 0 | 0.1012 / 0.1379 | identical |
| mk64 | 31 -> 31 | 1 -> 1 | 0.2003 / 0.2598 | identical |
| pm | 204 -> 204 | 16 -> 16 | 1.6121 / 1.7164 | identical |
| sm64 | 23 -> 23 | 1 -> 1 | 0.2067 / 0.2438 | identical |
| mm | 0 -> 0 | 2 -> 2 | 0.2741 / 0.3080 | identical |
| fzerox | 0 -> 0 | 10 -> 10 | 2.0038 / 2.1686 | identical |
| oot | 0 -> 0 | 3 -> 3 | 0.3141 / 0.3379 | identical |

SM64's 23 blockers are the untouched ROM-only default on both sides, rather than
the historical configured build with extra loads/runtime names. MM, F-Zero X
and OoT retain scoped CLOSED. Timings are process wall measurements made amid
other local validation, not a speedup claim. No inference bottleneck was found;
the release rebuild took 51.67 s. Full overlay maps remain expensive; MM's
discovery/solve wall measurements were 83.238 / 80.538 s,
unchanged code and identical output. No performance claim is made.

The precise analysis stops are model limits, not proof of unavoidable external
inputs (in particular COP0 Status could be provided by a verified boot profile):

- **bk:** `boot execution stopped at 800021a0 after 11136 instructions: unmodeled coprocessor state/instruction 40026000; verified boot/device state is required`.
- **sf64:** `boot execution stopped at 8001ef18 after 397125 instructions: external or unsupported memory input at a0300000`.
- **mk64:** `boot execution stopped at 800d1b40 after 412141 instructions: unmodeled coprocessor state/instruction 40026000; verified boot/device state is required`.
- **pm:** `boot execution stopped at 8006c670 after 202640 instructions: unmodeled coprocessor state/instruction 40026000; verified boot/device state is required`.
- **sm64:** `boot execution stopped at 80328720 after 115041 instructions: unmodeled coprocessor state/instruction 40026000; verified boot/device state is required`.
- **mm:** `boot execution stopped at 80085364 after 15987 instructions: unsupported instruction 50400007`.
- **fzerox:** `boot execution stopped at 800be6a0 after 93301 instructions: unmodeled coprocessor state/instruction 40026000; verified boot/device state is required`.
- **oot:** `boot execution stopped at 80001aa0 after 11903 instructions: write into executing boot image needs cache/lifetime proof`.

BK's normal command was also run:

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
python scripts/native.py target/local-inputs/bk.z64 --name post-boot-bk --rt64 --seconds 60 --require-audio
```

It still discovers 276 blocks, 17 indirect sites and zero discovery unresolved
items, then refuses at **solve OPEN, 1 blocker** (`8000052c -> 8023d680`). The
analysis stops earlier at `800021a0`, MFC0 Status, after 11,136 instructions;
no PI transfer or decompression was executed by this candidate. Lowering,
compilation, RSP-from-ROM and visible native validation are unreached. There is
no BK guest run, no game window, and **VI, runtime fault/PC and PCM peak are
unmeasured**, not zero or successful. The 60-second/audio requirement was not
bypassed. Further verified boot/device coverage is required before measuring
the next post-closure blocker.

### Synthetic and local gate receipt

Three Rust contracts cover deterministic copy/XOR decoding with a loop and
delay slots, output bytes/PC/registers/source ranges, composition replay/range
tampering, unknown inputs and output, ADDI overflow, missing writeback,
writeback variants, illegal delay-slot transfer and budget refusal.
`runtime/test_boot_execution.py` exercises the public CLI and normal scoped
solver, lowers the result, compiles it and runs from the **original IPL3 copy**,
not preloaded recovered text. All 32 registers, final PC and 0x100 bytes of RAM
match the existing pinned ares oracle exactly. Mutated text faults 8 before
native entry. The first ares attempt exposed missing D-cache writeback; the
successful native fixture evicts the dirty line before transferring. Raw CACHE
instructions remain excluded by the existing native scope, so those capture
variants are unit tests, not a claim of native CACHE support. The standalone
focused native contract and its invocation in the full runtime gate both pass.
Pinned ares is `9408cb43d4948fc3ea6e152a307a34348df3fe04`; the reference checkout is
clean and its separate oracle retains ISC/BSD notices. No reference code was
copied into production and no new dependency was introduced.

All five required local gates pass on the final production/test tree:

- `cargo fmt --all -- --check`: exit 0, 0.801 s.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: exit 0, 6.281 s.
- `cargo test --locked --workspace`: exit 0, 81.813 s; 720 Rust tests.
- `python scripts/test_cli.py`: exit 0, 16.068 s.
- `python runtime/test_runtime.py`: exit 0, 137.952 s.

Progress data did not change, so progress.py --check was not required. README
was not edited. ADR-0190 was appended as bytes with the entire original
DECISIONS.md prefix preserved, including its non-UTF-8 byte. STATUS/NEXT name
the partial boundary. No push, main write, external claim message or copyrighted
ROM/asset is included. All own validation processes exited; no game was launched.

Ignored evidence: `target/post-boot-loads/{sweep.json,gate.json,bk-native.log}`,
the per-ROM `before/after` loads/IDs/maps/solve outputs and logs, gate-0..4.log;
`sweep.py`, `gate.py` and `receipt.py` reproduce this local receipt. Synthetic
native/oracle artifacts are under `target/boot-execution-contract/`.

Retained map digests (the before digest equals the after digest):

| ROM | SHA-256 |
| --- | --- |
| bk | `ee6e880441e2180b02adfc43f758d77046e25da6303481b943016303c2a37989` |
| sf64 | `8d5ac59450cabe60ce9bc0daf25519f4c75bbb13cfd3a790f37b5fe97a892dc2` |
| mk64 | `ce1388d785184416e07a302a42d86f3a01e5efcf135445cee8df60859b0d2202` |
| pm | `4f695875d6db5075849e1f6639ac22f5e96a11bc5cd5f194e3c6e4e02119bd2b` |
| sm64 | `456255a006e31fd74e15cf969941840568db8fc601b78d84e415c08e51691110` |
| mm | `fdc609d0a1f19d081356200a2ea207d6ab2ae03e957736ac4b66f3e8bb375127` |
| fzerox | `3ea5d068cdbac14e5f50d6aacfa200587a19b5c106aed3fc602a8ccf7386de1a` |
| oot | `b53f8802bba5f8388e2c5b375eecb529f8adc757c264d81539ee3d715f86cf4b` |

Remaining unproven: BK scoped closure and all downstream native stages;
commercial boot execution/device initialization; broader instruction/cache/event
semantics; generated-code overlays after the first transfer; whole-ROM closure
and game execution for the other surveyed titles. This is a **partial** commit,
not a validation handoff for unavailable tools: all requested local gates ran,
but the boot/device semantics needed to achieve the main objective remain work.

## Ares-driven post-boot harvest continuation (ADR-0190)

Implementation claim, 2026-10-17, sole worker on `post-boot-loads`: use the
pinned ares interpreter as an **analysis-time** executor, rather than extend
Plaid's integer executor with a second CPU/device implementation. The declared
profile is reset through the pinned NTSC PIF firmware, CIC selected by IPL3
CRC32, 8 MiB RAM, deterministic entropy, controller 1 connected with neutral
inputs, and no supplied save/snapshot state. Unknown IPL3 signatures refuse.
Budgets are 100,000,000 instruction calls or 3,600 VI per boot; the normal
pipeline permits at most eight discovery/closure rounds. Reaching the budget
does not prove a controller input is required, and no input is synthesized.

`scripts/ares_boot.cpp` uses the existing separate headless ares builder and
passive successful fetch, RAM scalar/burst write and PI DMA observers. RAM
producer tracking begins at the inferred game entry, after real IPL3 execution.
At the first fetch of a requested missing KSEG0 target, it snapshots its
contiguous, word-aligned produced RAM range; absent producers, other-device
writers and stale resident I-cache words refuse capture. CPU writes are
completed uncached writes/writebacks, not a claim of per-byte data-flow lineage.
PI requests retain RAM destination, physical cartridge source and length;
canonical consumed ROM ranges are explicitly PI-request-only, not an exhaustive
list of CPU ROM reads. The whole canonical ROM and pinned firmware are hashed.
Multiple requested target images can be harvested during one deterministic boot.
New closure frontiers trigger a fresh deterministic replay, within the declared
round limit; this is not an exhaustive executable-universe proof.

`scripts/native.py` attempts the harvest only after normal scoped closure is
OPEN, then repeats identify/discover/solve. Static declarations and existing
images are preserved; overlaps are subtracted rather than overwritten. New
`ares_boot` declarations retain whole-ROM source zero and the first fetch entry.
Composition invokes the owned helper to regenerate bytes from the ROM, validates
identity/budget/ranges/digest, and selects only a bounded subrange of that capture.
No RAM snapshot file is accepted as an input or replay cache. An in-process memo
avoids repeating the same entry within one composition. Native entry retains the
existing executable-byte comparison and fault 8 on mismatch. No ares code,
decoder, interpreter or JIT is linked into a native gameplay artifact.

The small original `boot` executor remains a fallback for its retained synthetic
contracts and pure integer boot paths; it has not gained CPU/device semantics.
The ares source/license stays separate at the pinned revision; the builder keeps
the complete ISC/BSD notices. Only project-owned observer/driver code is reused.

### Final continuation receipt

The standard pipeline was rerun from ROM-only inputs on the final mechanism.
The archived `5c0ddb5` release binary and predecessor baseline maps supply the
before side; GE was independently regenerated with that binary. The same scope
and original ROM identities above apply. Every unchanged row below has a
byte-identical complete map, not just matching counts.

| ROM | Scoped blockers before -> after | Loads before -> after | Final pipeline wall seconds | Map |
| --- | ---: | ---: | ---: | --- |
| bk | 1 -> 72 | 0 -> 3 | 217.691 | expanded |
| sf64 | 298 -> 298 | 0 -> 0 | 8.060 | identical |
| mk64 | 31 -> 31 | 1 -> 1 | 9.142 | identical |
| pm | 204 -> 204 | 16 -> 16 | 32.487 | identical |
| ge | 7 -> 7 | 1 -> 1 | 0.595 | identical |
| sm64 | 23 -> 23 | 1 -> 1 | 6.098 | identical |
| mm | 0 -> 0 | 2 -> 2 | 80.949 | identical |
| fzerox | 0 -> 0 | 10 -> 10 | 12.349 | identical |
| oot | 0 -> 0 | 3 -> 3 | 58.214 | identical |

SM64's 23 blockers are the original ROM-only default, not its separately
configured historical CLOSED build. MM/F-Zero X/OoT retain scoped CLOSED.
SF64/MK64/PM have no new capture in the 100-million-call no-input profile;
GE's missing `70000510` is outside the KSEG0 harvest model. These are finite
profile results, not proofs of input dependence or general unrecoverability.

BK's first missing transfer is now resolved. Its successive blocker counts are
**1 -> 223 -> 117 -> 72**, with blocks **276 -> 3,799 -> 31,951 -> 32,321**.
This exposes previously absent executable candidates rather than reducing the
original one-blocker boot map to closure. Runtime identification grows to 66.
The three nonoverlapping declarations are:

| Destination / size | First fetch entry | Instruction calls at capture | Declared image SHA-256 |
| --- | --- | ---: | --- |
| `8023d680 / 399a0` | `8023d680` | 24,290,457 | `5bfe89660f627f6eb4d439e80d4cc16e5ec11de08fccdedcf4b0f81bff9a9fb7` |
| `80277020 / 10e5f0` | `8033e138` | 65,052,624 | `a6c78e0a71aec0e687500777a5a933220952c9e0d78e7e8b31586d978d40f485` |
| `80385610 / 8600` | `8038b700` | 83,823,886 | `b1b41a1a39ce56f6010840b785a204d75655de21a1e1676a9833e63044de5c25` |

The last no-input replay reaches analysis VI 187 at 100,000,000 instruction
calls. Seven missing targets remain (`8038dd30`, `8038e374`, `8038e400`,
`8038f128`, `8038f158`, `8038f1b0`, `80390544`). The scoped blocker classes are
47 unsupported scope effects, eight unsupported/invalid instruction candidates,
seven unmapped targets, seven unresolved direct targets, two unresolved indirect
sites and one unresolved indirect target. `ERET` at `80002b5c` is an immediate
system-boundary barrier. Some decoder candidates in the third range may be
contiguous produced data reached by static overapproximation; this receipt does
not assert those invalid words actually executed. Text/data classification,
SDK boundary coverage and later executable loads remain work.

The requested normal command ran with `--rt64 --seconds 60 --require-audio`,
using name `ares-boot-bk-final`. It refuses at **solve OPEN, 72 blockers**.
Lowering, compilation, RSP-from-ROM, the visible native window and audio
validation are therefore unreached. **Native VI, fault/PC and PCM peak are
unmeasured**, not zero. The analysis VI count is not a native gameplay result.

Independent normal-pipeline and sweep runs produce byte-identical BK load
declarations, including all three image digests and provenance. Runtime IDs are
identical after LF/CRLF normalization. Their maps differ only by that raw ID
file's SHA-256 in runtime evidence; replacing precisely that declaration digest
makes the parsed maps identical. The seven retained baseline map comparisons
and the independent GE map pair are byte-exact. The before-control digests
printed above remain applicable; BK's sweep map digest is
`8344ee63bf7893f277c4da6122ba4f684b5d69473bc3af9f0111b45508f118ff`.

The versioned helper protocol is `plaid-ares-boot-harvest-v1`. Composition
rejects other protocol versions, bad ROM/core identity, target/range/budget or
digest mismatches. The final release replay is also rechecked after adding the
protocol-version gate; snapshots cannot replace regeneration.

Synthetic verification retains all predecessor differential/native contracts.
New tests run a synthetic CPU store/fetch sequence twice with exact output,
PC, CPU-write ranges and call count, then test budget refusal, absent producers,
stale I-cache refusal, overlap subtraction/static-load preservation, and
production rejection of synthetic IPL3 in all three byte orders. The initial
state for that driver fixture is explicitly declared post-IPL; authentic reset
of an open synthetic ROM remains unproven. The runtime gate invokes it.

Iteration speed: BK's 24,290,457-call complete capture is byte-identical between
the debugger-tracer implementation and passive instruction callback, including
the stop record (SHA-256 `dc479110f736d3ae41c4c30191b5ffa490186584d9f1e71317b9a2ca8c566c5c`).
Wall times are **14.591 -> 2.581 s** (5.65x), measured once amid local validation.
The same full pinned-source HEAD diff takes **0.044 s** with native git on
DrvFS; the Linux git version was interrupted after **>110 s**. No reference
source check was skipped. MM's unchanged map/solve still dominates its 80.949 s
pipeline; this task makes no speedup claim for discovery itself.

Final local gate (same Rust/production tree; comments/docs do not affect it):

- `cargo fmt --all -- --check`: exit 0, 0.755 s.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: exit 0, 5.340 s.
- `cargo test --locked --workspace`: exit 0, 81.443 s; 720 Rust tests.
- `python scripts/test_cli.py`: exit 0, 8.090 s.
- `python runtime/test_runtime.py`: exit 0, 122.024 s.

Progress data did not change, so `tools/progress.py --check` was not required.
README was not changed. ADR-0190 was rewritten as bytes while preserving the
entire earlier DECISIONS.md prefix and its non-UTF-8 byte. No ROM/assets, push,
main write, external messages or game-specific exception is included.

Ignored evidence: `target/ares-boot/{sweep.json,sweep-final.log,verification.json,
final-gate.json,benchmark.json,reference-check-timing.json,bk-final.log}` and the
per-ROM loads/IDs/maps/solve/harvest receipts; final normal BK artifacts are in
`target/native/ares-boot-bk-final/`. The ignored `sweep.py`, `verify.py`, `gate.py`
and `bench.py` reproduce the local receipt. All owned compiler/oracle/validation
processes are closed; no native game process was launched because closure stayed
OPEN. This is a **partial implementation**, not a missing-environment handoff.
Commercial native execution, exhaustive executable/overlay lifetime closure,
input requirements beyond the finite budget and the newly exposed static
candidates remain unproven. No assumption was retired.

## BK closure continuation (partial, ADR-0191)

Implementation claim, 2026-10-17, sole worker on bk-closure: test whether
independently linked SDK copies in disjoint supplied images cause global
signature constraints to reject valid runtime boundaries. Preserve native
closed-world refusal and existing executable-byte guards. Milestone 5; no
assumption retired. Final measurements and remaining obligations follow below.

### Identification and exact blocker classification

The predecessor diagnostic was rerun successfully; its old empty ID file and
WSL path error were not evidence of signature failure. The boot osInitialize
at 80001d70 already matches the pinned n64sym CRC/relocations. Recovered images
were already included in identify. The actual failure was treating independently
linked libultra copies as one symbol namespace: the recovered osClockRate and
osViClock addresses caused rejection of the boot candidate, while relocated
copies of other functions remained globally ambiguous. ADR-0191 preserves whole-image matching and additionally scopes data
symbols/name uniqueness to connected supplied image components (holes separate
them), retaining cross-component callee checks and within-component ambiguity.
The same scanned candidates feed both resolutions; conflicting names or sizes
at one address select no runtime boundary.
Adjacent loads remain one component; this is not complete SDK-copy inference.
No SDK version signature, title-specific rule or runtime service was added.

The reproducible classifier is `research/classify-sweep-blockers.py`; it reads
retained solve/map artifacts and optional ignored byte images, reports raw words,
COP0 registers, containing blocks, incoming edges and indirect certificates.
It never supplies images to the compiler. The 72 -> 29 assertion and the actual
map/provenance comparisons are retained under target/bk-closure.

| Scoped blocker kind | Before | After |
| --- | ---: | ---: |
| unsupported_scope_effect | 47 | 8 |
| exception_or_unsupported_instruction | 8 | 7 |
| unmapped_target | 7 | 7 |
| unresolved_direct_target | 7 | 7 |
| unresolved_indirect_site | 2 | 0 |
| unresolved_indirect_target | 1 | 0 |
| **Total** | **72** | **29** |

Of the original 47 effects, 40 are genuine system instructions: 19 MFC0,
15 MTC0, two TLBP, two TLBR, one TLBWI and one ERET. The other seven are the
same noncanonical/invalid words counted again by the unsupported-instruction
class. ERET is also counted in both classes. After identifying the SDK copies,
39 genuine system effects, ERET's second diagnostic, and the two exception
handler dispatch sites (800024a0, 80002850) disappear behind the existing HLE
boundary. This does not add native ERET/COP0 support or prove HLE equivalence.

The remaining genuine system instruction is MFC0 Status at 80259d30, an exact
existing __osGetSR signature (CRC A 6658f48b, B 7f62261b). That helper is absent
from Plaid's supported runtime service set. Its caller at 80246f70 tests Status
bit 0x1000, so replacing it with osGetCount or a guessed constant is unsound.
A verified guest-visible Status/interrupt-mask model remains necessary.

The third indirect blocker was a false runtime name: the jump-table case at
803111d4 is `jr ra; addiu v0,zero,11`, also the complete osVoiceInit stub
signature. Existing plausibility checks admitted this unrelated switch arm,
removing its guest block while the table still required it. Constant-return
two-instruction signatures now leave such code as guest code. The existing
12-entry guarded-table and return machinery then closes this dispatch at
803111b4. No new indirect certificate kind was necessary. Effectful small
signatures remain eligible; no guest instruction semantics changed.

### Missing text, generation limits, and native refusal

All seven remaining decoder candidates are reached by direct calls, rather
than merely unreferenced data-root guesses:

| Candidate PC / word | Incoming call site |
| --- | --- |
| 8038cdbc / 02ae0000 | 802c2898 |
| 8038d37c / 03880001 | 80352660 (entry 8038d360) |
| 8038d3a0 / 03470001 | 80352638 (entry 8038d398) |
| 8038d3c4 / 035b0001 | 80352640 (entry 8038d3a4) |
| 8038d528 / 009000c0 | 80352688 (entry 8038d51c) |
| 8038d570 / 009200c2 | 80352670 (entry 8038d564) |
| 8038da14 / 3e99999a | 80333d60 |

These bytes look like pointer/record/float data in the captured generation.
That is not a proof that every such target is non-executable in every supported
state. Missing overlay generations or overapproximated calls remain plausible;
no text/data exclusion or invalid-word lowering was added. They remain seven
unsupported-instruction plus seven scope-effect blockers.

The seven missing targets remain 8038dd30, 8038e374, 8038e400, 8038f128,
8038f158, 8038f1b0 and 80390544, each with one unresolved direct call. An
analysis-only 500,000,000-call neutral-input replay (predecessor driver with
only its budget ceiling raised) reaches **VI 676**, stop PC **8024082c**, with
all seven still unfetched and no new harvest. Its raw stop receipt SHA-256 is
6ce0c14a183ea1fbd06d878261ef76b02d6508f2a2ae4083701c8aef48ac71d2.
This is finite negative evidence, not proof of input dependence or dead code.
The production ceiling/profile remains 100,000,000 calls / 3,600 VI; temporary
PLAID_DIAG instrumentation and the WIP budget change are removed.

The normal command (followed by byte-identical BK identification and a solver
recheck after the final control-map correction) was:

```powershell
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
python scripts/native.py target/local-inputs/bk.z64 --name bk-closure-final --rt64 --seconds 60 --require-audio
```

It reaches **solve OPEN, 29 blockers**, with 32,192 blocks and 87 runtime IDs.
Successive scoped counts are 1 -> 181 -> 74 -> 29. The three load declarations,
image digests and complete provenance are byte-identical to ADR-0190's retained
BK loads. Native lowering, RSP extraction, compilation, visible gameplay and
audio validation remain unreached. **Native VI, fault/PC and PCM peak are
unmeasured**, not zero. No native artifact or game process was launched.

### Final sweep, regressions and validation

| ROM | Scoped blockers before -> after | Loads before -> after | Final status |
| --- | ---: | ---: | --- |
| BK | 72 -> 29 | 3 -> 3 | OPEN |
| Star Fox 64 | 298 -> 298 | 0 -> 0 | OPEN |
| Mario Kart 64 | 31 -> 31 | 1 -> 1 | OPEN |
| Paper Mario | 204 -> 164 | 16 -> 19 | OPEN |
| GoldenEye | 7 -> 7 | 1 -> 1 | OPEN |
| Rogue Squadron | 211 -> 211 | 3 -> 3 | OPEN |

Paper Mario's runtime IDs increase 18 -> 121, with no names removed. With the
original loads the fix gives 168 blockers; subsequent ares harvests give
168 -> 164. Three new declarations at 80200000/80, 80200080/190 and 802b2000/f0
are replayed with existing provenance/guards. Final blocks grow 38,724 -> 41,689.
Its final classes are 135 unresolved indirect sites, 13 direct edges, eight
unmapped targets and eight unsupported scope effects. No claim of native play
or closure is made for any of these six ROMs.

SM64's ROM-only default remains OPEN with 23 blockers and a byte-identical map.
Its separately configured CLOSED build (original two static loads and reference
map completion) was regenerated with the archived pre-harvest binary and final
binary using identical commands: both CLOSED, 45,419 blocks, byte-identical
complete maps. Comparing that build to the older ADR-0171 historical map also
shows pre-existing entry/address-taken census changes; the actual new before/
after pair is exact. MM and F-Zero X remain CLOSED with byte-identical maps.
SF64/MK64/GE also retain byte-identical full maps. Rogue Squadron's ID files are
identical after LF/CRLF normalization; only the corresponding raw declaration
SHA-256 differs in its map evidence/runtime declarations, and normalizing just
that digest makes the complete parsed maps identical. No other normalization
is used. Per-file SHA-256 receipts are in map-verification.json.

Five new deterministic Rust regressions cover independent globals and duplicate
relocated names, within-component ambiguity, getter disambiguation, hole-crossing
refusal, cross-component call tampering, constant-return switch lookalikes and
an effectful small-signature control. The independent-SDK regression fails with
the original 40dde18 production identifier (0 matches versus 4), then passes
with the fix. All twelve focused signature tests pass. Split-image VI-global evidence
and conflicting name/size refusal are explicitly covered. The final full runtime gate
retains native state/RAM/PC comparisons with pinned ares, executable tamper faults,
heap/shared-slot overlay tests and RSP startup/fetch/ABI/event checks. No new
instruction lowering, runtime CPU state or text exclusion bypass was introduced.

Final local gate on the final production/test tree:

| Command | Exit | Seconds |
| --- | ---: | ---: |
| cargo fmt --all -- --check | 0 | 0.795 |
| cargo clippy --locked --workspace --all-targets -- -D warnings | 0 | 5.687 |
| cargo test --locked --workspace | 0 | 83.234 |
| python scripts/test_cli.py | 0 | 7.500 |
| python runtime/test_runtime.py | 0 | 128.641 |

Rust total: **725 passed, one ignored**. Progress data is unchanged, so
progress.py --check is not required. No performance optimization is claimed;
these are measured validation times, not a before/after speed benchmark.
The earlier checkpoint gates were superseded by this complete gate after
preserving whole-image evidence and adding its regressions. Final review checked namespace boundaries, cross-image calls,
small-stub behavior and retention of all closure refusals. No reference code or
new dependency was copied. Pinned ares and n64sym HEADs are exact and clean.
DECISIONS was edited as bytes; the complete pre-task byte prefix, including its
non-UTF-8 byte, is SHA-256 verified unchanged. README is untouched.

Ignored evidence: target/bk-closure/{before-classification.json,
after-classification.json,solve-final.json,later.jsonl,regression-red.log,
signature-final.log,map-verification.json,decisions-prefix.json}, final-sweep/
loads/IDs/maps/solve/harvest receipts, sm64-configured{,-before,-accepted}/, gate-accepted/
and native-final.log; checked-sweep/results.json and recheck.py retain the
accepted-revision identification/solver checks. The retained local sweep/gate/SM64 scripts reproduce the
commands; target/native/bk-closure-final/ holds the normal BK pipeline artifacts.
Diagnostic byte images remain ignored outputs, never compiler input snapshots.
No push/main write, external messages, ROM/assets or compatibility exception is
included. This is a **partial implementation**, with all required local validation
available and completed, not a missing-capability validation handoff. BK Status
semantics, static text/data or overlay-generation proof, executable lifetime,
input requirements and all downstream native gameplay/audio remain unproven.
No assumption is retired.

OoT's first component-only control remained CLOSED but lost six boot VI runtime
names. This was caught before closeout: whole-image evidence is now preserved
and combined with component recovery, with name/size conflicts refusing a
boundary. The accepted OoT map retains all 65 previous runtime declarations
and adds only osSetTime at 801ca3c0 (24-byte existing SDK signature). Its guest
block and return disappear: 155,770 -> 155,769 blocks; scoped CLOSED remains
unchanged. This is the sole semantic control-map difference. The split-image
global-evidence regression prevents the discarded VI-boundary regression.

After that correction, identify and solve were rerun for all ten ROM/control
inputs on the accepted revision. Exact IDs permit reusing the corresponding
complete already-regenerated map (discovery code and inputs are unchanged);
PM and OoT were rediscovered because their ID bytes changed. PM's function
list stays identical (121); only the now-resolved osSetTime ambiguity metadata
and its declaration digest change. Its digest-normalized map stays identical.
BK remains byte-identical to the complete normal run (including IDs and map),
with the same 29-blocker verdict. MM/F-Zero X/ROM-only SM64 controls stay
byte-identical to the original baselines. Configured SM64 was also independently
rediscovered again on the accepted revision and is byte-identical to its
pre-change configured baseline. All ten final verdicts and hashes are retained
in checked-sweep/results.json and map-verification.json. No new native control
gameplay run was made; this regression evidence is identification/map/closure
plus the complete synthetic native runtime gate.

Iteration timing control (single local runs, not a speedup claim): configured
SM64 identify/discover/solve before were 0.683 / 6.814 / 1.081 seconds; accepted
revision 0.350 / 6.468 / 1.076 seconds, with byte-identical complete maps.
No owned compiler/oracle/validation/game processes remain after closeout.

## BK shared-slot continuation (2026-10-17, partial)

Branch `bk-closure-3`, prepared base main `6d846df` / WIP `8b2270b`.
Single-worker experiment claim: identify the producer of the third harvested
image and derive its executable alternates and text/data bounds from the
loader/container, retaining the closed-world refusal until verified. The
predecessor's local decoded pair at ROM fc9ef0/fcbacd matches the captured
80385610 image; that observation alone does not establish the slot's universe.
`research/trace-slot-writers.cpp` observes effective CPU store addresses and
recent call arguments against pinned interpreter-only ares. All ROM, decoded
bytes and trace outputs stay ignored under target/. No native artifact is
authorized by this research checkpoint, and no Status constant is substituted.

### Loader and source-catalog result (ADR-0192)

The store observer built and ran against clean pinned ares
`9408cb43d4948fc3ea6e152a307a34348df3fe04`, interpreter-only, NTSC/PIF reset,
CIC-NUS-6103, neutral gamepad. Its first build exposed a WIP include error:
ares_boot.cpp redefines/undefines main internally; including the original
fixture driver directly fixes the harness without changing reference code.
The 100,000,000-call experiment ends at analysis PC 8033fec0 (budget exhausted;
the stop entry 80385610 itself is not fetched). Effective stores into the
slot are observed at **8023e5f8 and 8023e7e4**. The call history and loader
disassembly establish this chain:

- 8024ffa0 selects the indexed 44-byte segment-table row at 80275120;
- **80251da0** selects the physical source range from **803ffe10 + index*8**,
  DMA-loads its compressed bytes through 802401d0, then calls **8023dd24 twice**;
- 8023dd24 / 8023dda8 / 8023dd50 skip the six-byte 1172 header and invoke the
  raw-DEFLATE implementation at 8023f290; output/source pointers advance;
- the first stream supplies text, the second supplies data. The wrapper aligns
  the destination to 16 bytes. The segment table independently agrees with
  both decoded sizes and identifies the following BSS extent;
- **80001bf0** initializes the actual physical source table using literal
  LUI/ADDIU/SW sequences. The segment table's virtual ROM fields exceed the
  physical ROM and must not select compressed sources.

The original project-owned research parser and production Rust recognizer
recover the literal-store catalog without supplied guest addresses or offsets.
They then match its complete decoded pair census to a unique segment table in
a boot-named ROM container. BK has **15 source pairs**: one resident engine,
one empty entry and **13 executable files sharing 80385610**. Source starts,
in catalog-index order 2..14, are fa6f80, fa8ee0, fac0e0, fb1810, fb5450,
fb7480, fbc9c0, fc1ba0, fd91f0, fc77e0, fc9ef0, fcc120 and fd3400. These
are output evidence, never production constants. The matching metadata comes
from ROM container f1c830 at decoded offset 37aa0.

An independent Python/zlib pass agrees with all 13 Rust declarations, including
source ends, destinations and text/data lengths. Index 12's fc9ef0/fcbacd
pair exactly matches all **34288 code/data bytes** of the predecessor's captured
80385610 generation. Its final 16 captured bytes are nonzero runtime checksum
state in the BSS extent: do not turn them into source bytes or assume BSS is
still zero when first fetched. All seven old invalid candidates lie in that
pair's data section. Each of the seven missing numeric targets is inside the
text of other catalog members; the retained evidence records the per-target
index census. This establishes a declared candidate set, not universal
reachability or a lifetime proof for the loader.

### Production change and verifiers

`infer-loads` now emits rare_pair declarations for the shared files. Each
composition decodes the bounded ROM range again, requires DEFLATE stream end
and exact decoded size, and checks the declared text size against the first
stream. Complete-catalog/metadata ambiguity and damaged catalogs refuse
inference; valid suffixes of a damaged table are not admitted. The new encoding
uses the existing ADR-0185 placed files, relocations and ADR-0187 verified
binding/native-frame pins. Data remains available for table reads, while an
instruction accessor excludes slot data from roots, CFG fallthrough and delay
slots. Explicit execution into data stays an OPEN obligation. No runtime MIPS
decoder/JIT, guessed SDK boundary or compatibility exception is added.

Four deterministic Rust tests cover stream end/truncation/size failures;
literal-store dataflow and delay slots; relocated catalog inference and
missing/ambiguous metadata; composition, text-bound tampering, data-pointer
relocation and code-shaped data-root/CFG refusal. Three independent research
parser contracts also pass. The public CLI/native slot contract now tests raw
and paired encodings: pinned-ares state fields (GPR/FPR/HI/LO, PC, FPU flags
and the retained RAM slice) match through
**7 -> 11 -> 7**. Each generation's actual slot writes are copied into that
RAM slice, so the comparison covers all three text-memory results. The oracle
requires no exception; tampered or ambiguous executable text faults. Existing
heap-overlay/native-frame-pin contracts remain in the full runtime gate.
No new CPU instruction semantics or event policy is claimed.

The first complete normal ROM-only pipeline after pair inference reports
1 -> 186 -> **1 scoped blocker**, preserving 87 runtime IDs. The last blocker
is **MFC0 Status at 80259d30**, an existing exact __osGetSR SDK signature.
Its caller 80246f70 tests Status bit 0x1000. The other seven original scope
effects duplicated the invalid/data candidates and disappear with proper slot
generations; none needs COP0 lowering. Runtime osSetIntMask/osGetIntMask still
return fixed masks, and __osDisableInt/__osRestoreInt use a separate enable bit.
A correct __osGetSR needs verified architectural Status, masks, thread context
and event interactions, not another guessed constant. That work remains open.

BK blocker classes:

| Class | Before | After |
| --- | ---: | ---: |
| unsupported_scope_effect | 8 | 1 |
| exception_or_unsupported_instruction (invalid candidates) | 7 | 0 |
| unmapped_target | 7 | 0 |
| unresolved_direct_target | 7 | 0 |
| **Total** | **29** | **1** |

The normal command is `python scripts/native.py target/local-inputs/bk.z64
--name bk-slot-final --rt64 --seconds 60 --require-audio`. It still refuses at
**solve OPEN**; lowering, native RSP extraction, compilation, visible game
execution and audio validation are unreached. Native VI, fault/PC and PCM
peak are **unmeasured**, not zero. No game window was opened or hidden.

### Controls, timings and closeout

| ROM | Scoped blockers before -> after |
| --- | ---: |
| BK | 29 -> 1 |
| Star Fox 64 | 298 -> 298 |
| Mario Kart 64 | 31 -> 31 |
| Paper Mario | 164 -> 164 |
| GoldenEye | 7 -> 7 |
| Rogue Squadron | 211 -> 211 |

The first checkpoint completely regenerated all nine non-BK control maps and
their IDs: byte-identical to ADR-0191's accepted baselines. MM, F-Zero X and
OoT remain scoped CLOSED; ROM-only SM64 remains OPEN/23. Separately configured
SM64 also regenerates byte-identically and remains CLOSED. Final-tree reruns
and the final local gate are recorded below. No control-game play is inferred
from a map comparison.

The catalog scan avoids decoding boot-named stream candidates when no source
catalog exists. Single local infer-loads timings before -> after that shortcut
and text-bound hardening (not a robust performance claim): BK 0.259 -> 0.060 s,
Paper Mario 2.035 -> 1.937 s, MM 0.275 -> 0.308 s. Each declaration file is
byte-identical across that comparison. No broad speedup is claimed from noisy
single runs. The new paired inference itself took 0.054 s for BK in a separate
warm check.

Retained ignored artifacts: target/bk-slot/{oracle/,writers.jsonl,catalog.json,
evidence.json,check-evidence.py,infer-{before,after}*.json,decisions-prefix.json,
slots.log,sweep/,final-sweep/,gate/,final-core-gate/} and local runner scripts;
target/native/bk-slot-{closure,final}/ hold the normal pipeline artifacts.
The original DECISIONS byte prefix, including its non-UTF-8 byte, is preserved
and SHA-256 checked. README and progress data are untouched. No push or main
write is made. This is **partial implementation**, with Status semantics,
whole-loader lifetime, exhaustive execution and native gameplay/audio unproven.

Final-tree closeout: the normal BK command again returns OPEN/1, **33,796
blocks, 87 runtime declarations and 13 paired slot loads plus two replayed
fixed loads**. Its complete map is byte-identical to the initial paired-slot
run, including after instruction/data-access hardening. A separate final solve
stores the sole unsupported_scope_effect at 80259d30 in solve-final.json.
All nine final non-BK maps and IDs regenerate byte-identically to their
ADR-0191 baselines. Configured SM64 also independently regenerates identically
and remains CLOSED (45,419 blocks). MM/F-Zero X/OoT remain CLOSED. The six-ROM
scoped total is **740 -> 712**. No regression is attributed to normalization;
these are exact complete-file comparisons using the original declaration
newline convention.

The complete gate passes, with final Rust checks rerun after the last production
change and the runtime suite rerun after adding per-generation memory snapshots:

| Local gate | Result | Measured seconds |
| --- | --- | ---: |
| cargo fmt --all -- --check | PASS | 0.867 |
| cargo clippy --locked --workspace --all-targets -- -D warnings | PASS | 5.471 |
| cargo test --locked --workspace | 729 passed, 1 ignored | 80.125 |
| python scripts/test_cli.py | PASS | 14.026 |
| python runtime/test_runtime.py | PASS; stronger memory-snapshot repeat also PASS | 170.154 (first complete run) |

The strengthened runtime repeat was not separately stopwatch-timed. Its log
timestamps span approximately 166 seconds; runtime-final.log is the accepted
repeat evidence. The two original strict-Clippy findings (is_multiple_of and
as_chunks style) are fixed. An attempted release rebuild while the first sweep
held plaid.exe open hit Windows file locking; after that owned process exited,
the final release rebuild passed (59.35 s). This is not a capability blocker.
Four new Rust tests and three research-parser tests pass. The retained slot
contract covers both encodings with three refusal/switch cases each. There is
no new timing/interrupt semantic claim; the existing runtime event, RSP/ABI,
overlay tamper and active-frame-pin verifiers remain green.

Progress data did not change, so progress.py --check is not required. Final
review checked decoded bounds, complete-catalog refusal, source/text metadata
recomputation, data-root/CFG separation and preservation of existing encodings.
Clean exact-pinned ares and the original DECISIONS byte prefix were checked
again. All owned oracle/build/sweep/validation processes have exited; there is
no owned game process. The user's later request to see a run was withdrawn
before any emulator or native game window was launched. This is a verified
partial milestone, not a missing-environment validation handoff.

## Default residual dispatch sweep (ADR-0233, 2026-10-21)

Tree: `experiment/default-dispatch-0233` on main `496b7e43`; command
`python scripts/native.py <rom> --rt64 --seconds 60`, visible window. Times are
whole-pipeline wall clock on the laptop.

| ROM | Ordinary solve | Residual solve | Result |
| --- | --- | --- | --- |
| GoldenEye 007 | OPEN 7 | OPEN 7, 0 sites | 348 blocks; boot harvest stops at `mtc0` (`40820000`); 6 unsupported_scope_effect, 1 indirect target at TLB-mapped `70000510` |
| Mario Kart 64 | OPEN 30 | OPEN 27, 3 sites | 18 unsupported_scope_effect, 4 unmapped, 4 unresolved direct, 1 `eret` (156 s) |
| Star Fox 64 | OPEN 298 | OPEN 296, 2 sites | 136 unmapped, 157 unresolved direct targets (273 s) |
| Rogue Squadron | OPEN 243 | OPEN 225, 18 sites | 87 unresolved indirect targets, 61 invalid pointer-table entries, 54 unsupported_scope_effect (422 s) |
| Paper Mario | OPEN 8 | CLOSED, 8 sites | built; VI 2908, 2875 gfx / 2904 audio tasks, 30185 PI DMAs, fault 3 at map `80916450` calling `80240310` (1186 s) |
| Ocarina of Time | CLOSED | not needed | built; stops at unknown ROM-derived RSP microcode, VI 4 (883 s) |
| Mario Party 2 | n/a | n/a | `plaid identify` exits non-zero |

Classification: `research/classify-dispatch-sweep.py` (residual-solve blocker kinds).
No ROM, map or generated code is committed.

## Bounded COP0 continuation (ADR-0235, 2026-10-22)

On main e9d1ccf0 plus the reconciled COP0 candidate, the requested normal
visible-window pipelines (--rt64 --seconds 60) stop before emitting a game:
GoldenEye OPEN 7 -> 1 (348 blocks, mapped target 70000510 absent), Mario Kart
64 ordinary OPEN 30 -> 13 and residual OPEN 27 -> 10 (40,610 blocks; ERET,
four missing targets/eight source/edge blockers). Pipeline wall times were
6.812 and 215.547 s respectively. Neither reached a window, VI or audio.
Seven native COP0/TLB forms are verified, 196/209 -> 203/209 ISA coverage;
ERET/CACHE and mapped executable discovery are still open. BK/F-Zero X
complete discovery maps are unchanged. The retained candidate MM executable
visibly reproduces fault 2 at 80089668, VI 0, with identical reported state;
known BK/MM regressions are not repaired. Full evidence and limitations:
[research/cop0-lowering.md](cop0-lowering.md).
