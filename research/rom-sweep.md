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
