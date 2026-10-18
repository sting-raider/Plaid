# Remaining-ROM automatic pipeline sweep, 2026-10-18

## Result

Tested all five additional local ROMs against production commit
`109f467099bccab55bb217d5cb44595aa2679425`. Each completes the automatic
discovery/solve path but remains **OPEN**, so the pipeline correctly refuses
lowering and native emission. No new native game, graphics, audio or gameplay
result is claimed. Native VI, fault/PC and PCM values are unmeasured.

This distinguishes earlier finite native runs from automatic input coverage:
BK, Majora's Mask and F-Zero X have passed ROM-only builds; the retained SM64
and Ocarina of Time native results use additional build inputs. Those runs do
not establish that every instruction, runtime boundary or new game's
executable universe is supported.

## Reproduction

For each local ROM below, run from the repository root:

```powershell
python -u scripts/native.py target/local-inputs/<rom>.z64 --name test0201-<rom> --rt64 --seconds 30 --require-audio --press 0x1000@300:4 --press 0x1000@600:4
```

No `--loads`, symbol files, supplied guest offsets or game-specific patches
were passed. The native input options would apply after a successful build;
they do not inject input into the neutral-controller analysis-time replay.
All five commands exit 1 with `not CLOSED ... nothing is built`.

Commands, ROM hashes, timings, complete logs, regenerated IDs/maps/loads and
solve verdicts remain ignored under `target/remaining-roms-0201/` and
`target/native/test0201-<rom>/`. No ROM bytes, game code or assets are tracked.
Two bounded read-only Luna investigations supported the diagnosis; primary
owns the runs and recorded claims.

## Current results

| ROM | Blocks | Inferred/recovered loads | Scoped blockers | Pipeline seconds |
| --- | ---: | ---: | ---: | ---: |
| GoldenEye 007 (`ge`) | 348 | 1 | 7 | 1.605 |
| Mario Kart 64 (`mk64`) | 40,610 | 1 | 30 | 15.153 |
| Paper Mario (`pm`) | 41,816 | 19 | 164 | 185.995 |
| Star Fox 64 (`sf64`) | 25,554 | 0 | 298 | 9.804 |
| Rogue Squadron (`rs`) | 27,938 | 3 | 210 | 8.459 |

These are scoped blocker diagnostics, not distinct bugs or estimates of work
until gameplay. Times include the automatic pipeline with shared build/cache
reuse; two jobs ran concurrently. They exclude the extra solve used by the
receipt collector. No isolated performance comparison is claimed.

Compared with the retained post-ADR-0191 sweep, GoldenEye stays at 7, Mario
Kart moves 31 to 30, Paper Mario stays at 164 after harvesting, Star Fox stays
at 298, and Rogue Squadron moves 211 to 210. Full map/identifier contents also
changed since that historical snapshot; matching counts do not imply identical
proofs. This test pass changes no production code or accepted scope.

## First barriers and bounded diagnoses

**GoldenEye:** five MTC0s, TLBWI, and a jump from `0x800004b4` to an unmapped
candidate `0x70000510` remain. Static boot interpretation stops on COP0 at
`0x80000470`. The ares harvester only requests missing KSEG0 RAM targets, so
that candidate is outside its accepted address class. The preceding TLB setup
suggests translated execution, but this sweep does not certify its backing
mapping. Another arbitrary plain RAM load is not an established solution.

**Mario Kart:** four targets `0x802802ac`, `0x80280420`, `0x80281548` and
`0x80281968` are absent, along with their four direct edges. Three indirect
sites, 18 system/scope effects and ERET remain. Ares reaches the full
100,000,000-call budget, 133 VI, with all four targets still pending and no
captured image. That is a bounded replay without target coverage, not proof
that the functions cannot be loaded. The sole inferred secondary load begins
at `0x8028df00`, above these missing functions.

**Paper Mario:** automatic harvesting recovers three declarations beyond the
16 static loads. The solve sequence is 168, 168, then 164 blockers. The final
classes are eight unmapped targets, 13 direct edges, 135 indirect sites and
eight system/scope effects. Neutral replay reaches its 100,000,000-call budget
at 123 VI with 33 requested targets still pending in the last attempt. A
subset of source recovery succeeded; executable/overlay and indirect-flow
closure remain open. This reproduces the earlier 164-blocker result.

**Star Fox:** static inference stops at `0x8001ef18` on unsupported/unproven
memory input at `0xa0300000`, producing no loads. The subsequent pinned-ares
harvest is a separate observation: it completes its 100,000,000-call budget,
121 VI, with all 136 requested targets remaining and no image. Do not label
that ares result as the static interpreter's memory refusal. Solve reports
136 unmapped targets, 157 direct edges, two indirect sites, one indirect
target and two system/scope effects. No native RSP or rendering test occurs.

**Rogue Squadron:** solve retains 55 invalid table entries, 79 unresolved
table targets, 12 indirect sites, six table immutability and six target-identity
obligations, 51 system/scope effects and ERET. Instruction-like values among
the table candidates require better source/table provenance before admitting
them as executable destinations. The current missing-KSEG0-target/table-source
harvester has no frontier it can recover here; it returns without a replay.
This run does not identify custom RSP support as the first barrier.

## Next general work

Start with Mario Kart's four missing code targets: establish their ROM source,
copy/load/decompression path and executable bounds, then express the evidence
through the general load recognizer and synthetic contracts. GoldenEye needs
a verified boot COP0/TLB mapping path. Paper Mario and Star Fox need broader
source/load coverage; Rogue Squadron needs qualified pointer-table provenance.
None should be unblocked by accepting an observed address without its bytes,
mapping, mutability and control-flow obligations.

Paper Mario is the iteration bottleneck in this sweep. Ares-backed declarations
are replayed while separate identify/discover/solve processes compose images;
the Rust memo is intentionally in-process (`ares_boot.rs::execute`). Any future
replay reuse must preserve the pinned source/firmware, ROM identity, entry,
budget, payload hashes and deterministic proof checks. This sweep records the
cost and does not weaken those checks or claim an optimization.

## Validation scope

The recording commit changes documentation only. Its local validation reruns
solve for all five retained maps, compares complete parsed verdicts, verifies
the refusal/no-artifact conditions and checks the Git diff. The full Rust,
CLI and runtime gate on production commit `109f467` remains prior evidence;
it is not presented as a new native test of these five games. No assumption
is retired and `native_complete` remains false for every result.
