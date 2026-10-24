# Catalog slot binding over first-fetch replay text (ADR-0267)

Prepared worker: mp2-overlay-binding-d69651e4. Recovery/integration worker:
mp2-overlay-binding-40755f0f. Prepared and validated base main:
`2f420897165f030677e0c00c7ad4909c7e1a483b`.
Issue #4 claim: https://github.com/sting-raider/Plaid/issues/4#issuecomment-6381923700.
No child agents, README edits, shared-reference fetches or shared shim rebuilds.

## Reproduction and discriminating evidence

Before: a visible RT64 run of the local Mario Party 2 USA ROM, with
`SDL_AUDIODRIVER=dummy`, `--stop-at none --seconds 30`, stops at VI 8,
fault 8, PC `80102800`, RA `80077ca0`, audio tasks 3 and PI DMAs 17.
The screen has not rendered a graphics task. ROM SHA-256:
`0b7b2ec3bd2ac8713b4c43f74a634285a720779964ee2658f7ad2dfa97b33576`.

The existing declared-load file holds a fixed `ares_boot` image at
`801016c0+1360`, replayed at entry `80102800`. The generated fixed function
`F_80102800` calls `plaid_verify_load` before executing it. That fixed
identity bypasses selection among the 116 catalog overlays sharing the
same runtime address. This is a fixed first-use content mismatch, not
missing overlay discovery, BSS mismatch or ambiguous catalog selection.

Pinned ares `9408cb43d4948fc3ea6e152a307a34348df3fe04` independently
replays the first fetch at `80102800` after 59,502,017 instructions.
Its last PI request is ROM `37f290+220` to physical `102800`; the capture
covers `801016c0+1360`. Output SHA-256:
`7c86aa6deaf757a46db60ffeb6fe2e01da9d97404f29cdf3edf3b477157ae8c1`.
The actual native bytes at the refusal instead match the catalog file at
ROM `36d9a0+560`: all `530` text bytes match, and the `10` BSS bytes are zero.
The initial instruction bytes differ at offset `e`: the files refer to
different linked data. The test establishes different occupants; it does
not assume that native and neutral ares choose the same game path.

Ignored local evidence under `target/receipts/mp2-binding/`:
`baseline.log`, `native-ram.bin`, `oracle-entry.json`, `oracle-ram.bin`,
`compare.py`, `inspect.py`, and `control-mp2/loads-comparison.json`.
No ROM, save, game screenshot, trace payload or extracted bytes are committed.

## General change and deterministic verification

After catalog declarations are assembled, subtract their linked executable
text from fixed first-fetch `AresBoot` declarations. Preserve replay prefix,
suffix, evidence, original replay entry, nonexecutable data and other load
encodings. The clipped declarations are recomposed and hashed normally;
no stale code/edge certificate is retained. MP2's fixed replay shrinks to
`801016c0+1140`, ending exactly where the shared text begins. All 116 catalog
loads remain. The three snapshot blocks disappear (157,064 -> 157,061).
The residual solve is CLOSED with 8 residual sites, `native_complete: false`.

No runtime content or mapping verifier is relaxed. First slot entry still
requires a unique relocated-text/guarded-data/BSS match. Bound executable
writes still revoke the binding; unknown entries still fault. No runtime
MIPS decoder, interpreter, JIT or fallback is introduced.

The core synthetic test covers overlapping alternate text extents, preserved
prefix/suffix, nonempty replay evidence and other encodings, exact coverage, idempotence and the
requirement that catalog declarations have content-bound execution.
Inverting only the `relocatable` guard fails that test (exit 101, 37.754 s);
restoration passes. `runtime/test_slots.py` now also checks raw catalog
switching against pinned ares (checked architectural state and the RAM
snapshot slice at `1000..1100`, 7/11/7),
tampered text, ambiguous text, and nonzero BSS refusal. Existing raw and
paired-stream cases remain. Current focused test and mutation logs are in
the ignored receipt directory.

## Validation and continuation receipt

Current-code discovery/lowering, native controls, save-load repro, timings
and exact-tree gate are recorded below after completion. All game windows
stay visible and every process receives `SDL_AUDIODRIVER=dummy`.

### MP2 continuation and the next blocker

The native ROM-copy diagnostic observes the actual ROM `36d9a0+560` transfer
to physical `102800`, joining the byte comparison to its producer. The
fixed executable enters that catalog overlay and reaches the HUDSON logo.
The original diagnostic build and a separately rebuilt, diagnostic-free
runtime both then stall at VI 520. GDB reads the latter at 30 seconds:

- VI 520, graphics 504, audio 514, PI DMA 48;
- fault 0, fault_pc `00000000`, state pc `00000000`, RA `80016174`;
- `osCreateThread` is in `pthread_join` at runtime/plaid_rt.c:592;
- its caller is native `F_800160fc`; the old host is parked in the scheduler's
  `wait_for_baton`, and the join holds the scheduler mutex `big`.

No guest fault PC exists here; the state PC is not a sampled instruction PC.
At four seconds the window is black, at seven it visibly shows HUDSON,
and at 30 it is black again. No title/menu was reached, so no input presses
were applied. Both the runtime timer and VI delivery cannot advance through
the join. The first run's 95-second outer timeout and a direct-log repeat
reproduce the stall; the diagnostic-free observation is externally killed
after recording its 30-second state. This is continuation evidence, not
successful 30-second timed completion, gameplay acceptance or a speedup.

Ignored evidence: `repeat.log` (ROM copy receipt), `quiet-run.log`,
`quiet-state.log`, `quiet-observation.json`, `mp2-quiet-{4,7,30}.png`,
`observe.py`, `build_quiet.py`, and the generated/native `control-mp2/`.
The three screenshots have been visually inspected. No canonical runtime
scheduler or renderer source is changed; the next thread-lifetime blocker
is retained explicitly in STATUS/NEXT.

### Iteration and review

Rust 1.99.1, Python 3.12.6, MinGW GCC 15.2.0 on Windows x86-64. Initial
release bootstrap took 70 s; the candidate release rebuild took 30.21 s.
The diagnostic-free MP2 runtime rebuild took 58.163 s. The original refusal
returned in 2.082 wall seconds including launch/shutdown; the candidate
was observed for 30 s and stalled as above. Those paths execute different
work, so their wall times do not measure a speedup.

Current C/RSP source bytes are regenerated before object reuse. All 124
MP2 RSP objects are source-identical and reuse takes 0.075 s. PM/BK fresh
discovery gives identical load declarations. None of the five control maps
has a fixed-replay/catalog-text intersection (`control_noop.py`), proving
the new reconciliation is a no-op there. Redundant MM discovery was stopped
rather than waiting on another full analysis; retained control maps then
feed the current lowerer, RSP discovery and runtime build. CPU objects are
reused only after exact generated-source equality. Lowering/runtime headers
are unchanged from main. This avoids repeated compilation without changing
native semantics; no compiler benchmark claim is made.

Review covers slicing boundaries, overlapping alternates, source/evidence
preservation, deterministic recomposition/hash, explicit data, BSS and
ambiguity guards, code-write revocation, unchanged runtime semantics and
compile-time cost. The mutation fails and restoration passes. No reference
code, dependency or game-specific production address was added.

## Recovery and independent verification on current main

The requested branch was occupied by the prepared checkout. Its production,
test and documentation diff was recovered into `t3/mp2-overlay-binding-1`
in `t3-40755f0f`, preserving the original checkout. Main `2f420897` is a
direct descendant of ADR-0266 (`5b00eb84`). Recovery claim:
https://github.com/sting-raider/Plaid/issues/4#issuecomment-6385821089.
No child agents were created. Local .refs, the existing oracle and the
shared ADR-0266 shim were linked without refetching or rebuilding them.
Game executables and copied DLLs were placed in local `target/native-bin`;
none of the protected junctions was removed or recursively deleted.

An empty replay-cache directory forced a fresh pinned-ares replay. It again
fetches `80102800` at step 59,502,017, records PI `37f290+220 -> 102800`,
and reproduces the full captured bytes and PI list exactly. Replay time is
1.663 s. The recovery native baseline with `--dump 0x80102800 348` gives
VI 8, fault 8, PC `80102800`, RA `80077ca0`; its own RDRAM dump matches
all `530` text bytes of ROM `36d9a0`, with all `10` BSS bytes zero. The
quiet refusal with the RDRAM dump returns in 1.457 s.
The earlier repeat under compilation load reached VI 12 with identical
fault/PC, three audio tasks and 17 PI DMAs; VI pacing is host-dependent.

Fresh discovery again yields 157,061 blocks, all 116 catalog loads and only
`801016c0+1140` as fixed replay text. The residual solver is CLOSED with
eight residual sites and `native_complete: false`. CPU main/part sources
were regenerated and compared byte-for-byte with the prepared candidate
before object reuse. Discovery took 62.340 s; discovery, solve, lowering
and RSP regeneration together took 119.322 s. All 124 RSP objects reused
in 0.391 s after source comparison; the diagnostic-free runtime rebuild
took 59.881 s. This is an iteration receipt, not a cross-workload speedup.

The first recovered mutation helper doubled CRLF and failed in compilation;
that attempt is excluded. After correcting the helper to preserve exact
source bytes, inverting the relocatable guard reaches and fails the named
test assertion (exit 101, 35.072 s). Restoration passes. The synthetic
catalog switching, tamper, ambiguity and BSS contracts independently pass
against the exact pinned oracle. Final-tree runtime tests repeat them.

The rebuilt diagnostic-free MP2 executable independently reproduces the
HUDSON screen at seven seconds and the black-screen stall at thirty:
VI 520, graphics 504, audio 514, PI 48, fault 0, fault_pc `00000000`,
state pc `00000000`, RA `80016174`. GDB again places `osCreateThread`
in a host join while the old thread waits for the baton and `big` is held.
The parked process was externally terminated after inspection. No title
or menu appeared and no presses were applied. This fixes the overlay
refusal, while timed completion remains blocked by native thread lifetime.

The review checks slicing bounds, union/order behavior for overlapping
alternates, original replay entry/source/evidence, recomposition and hash
renewal, BSS/data guards and runtime binding uniqueness/revocation. No
production runtime code, reference implementation or game address was added.

### Recovery control runs

All five control maps have no fixed-replay/catalog-text intersections,
checked before reuse. Current lowering regenerated each CPU source and
compared the part sources before reusing their objects; current RSP
registries and native runtime were rebuilt. Each control ran alone,
visibly, with `SDL_AUDIODRIVER=dummy` and a 30-second limit.

| Game | VI | Fault | Fault PC | Build s | Run/shutdown s |
| --- | ---: | ---: | --- | ---: | ---: |
| pm | 1798 | 0 | 00000000 | 30.244 | 30.761 |
| bk | 1798 | 0 | 00000000 | 19.844 | 30.753 |
| mm | 1798 | 0 | 00000000 | 136.820 | 30.788 |
| sf64 | 1798 | 0 | 00000000 | 19.958 | 30.796 |
| oot | 1798 | 0 | 00000000 | 94.094 | 30.782 |

These are finite control-flow/fault controls; they do not establish complete
gameplay, visual equivalence or hardware timing. The unchanged dispatch and
content guards remain active. Logs and complete stop records are in
`target/receipts/mp2-binding/controls-pm-bk-mm-sf64-oot.json` and each
`control-*/` directory. The shared scissor-fixed shim was used unchanged.

### ADR-0265 save-load reproduction and frozen-tree gate

A fresh copy of the same local SRAM used by ADR-0265 receives the exact
five presses: `0x1000@1200:4`, `0x8000@1400:4`, `0x8000@1550:4`,
`0x8000@1700:4`, `0x8000@1850:4`. No other game or compilation ran
during it. Current OoT reaches the 60-second limit with VI 3596,
fault 0, fault_pc `00000000`, RA `80000810`,
graphics 1517, audio 3423, PI 7841,
and 60.700 s including shutdown. The 55-second full-client
capture visibly shows Link in his tree house with Kokiri narration.
Ignored receipts: `oot_save_load.py`, `visual-repro.json`,
`visual-oot-repro.log` and `visual-oot-scene-55.png`. Saves and game
images remain local and ignored.

The shared synthetic oracle's pinned revision and driver hashes matched,
but its historical builder-recipe hash did not. The local oracle junction
was unlinked with nonrecursive `os.rmdir`, after checking its exact target;
the shared X:/Plaid directory was neither traversed nor removed. A private
local directory now holds the current-recipe Linux oracle. Its revision,
both fixture drivers and builder hash all match the exact source tree.
The production reference checkout remains clean at the pinned commit.

The final integration gate freezes one staged tree and asserts its identity
and absence of unstaged changes before and after every command:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- `python tools/progress.py --check`

Complete exits and timings, validated base and tree are recorded in
`target/receipts/mp2-binding/final-gate.json` and `final-gate-*.log`.
The runtime gate repeats the catalog/ares switching and refusal contract,
plus retained cache, text-write, overlay, coroutine, state/memory and event
contracts. Final closeout in issue #4 records the gate results and landed
SHA. No historical CI is substituted for this local gate.

Integration requires a refetch immediately before writing, equality of main
with the validated base, a commit whose parent is exactly that base,
`git merge-base --is-ancestor origin/main HEAD` and a plain
`git push origin HEAD:main`. Main drift requires reconciliation and another
full gate. README.md is untouched. Remaining MP2 gap is the independently
reproduced thread-recreation deadlock; no timed-completion, title/menu,
gameplay or native-completeness claim is made.
