# RSP from ROM: partial candidate, no integration

Current continuation: ADR-0188 accepts fetch-verified ROM-only dispatch for
the finite SM64/MM/F-Zero runs recorded at the end of this note. Older partial
receipts below are historical; OoT and whole-ROM closure remain separate gaps.
The following prepared-state receipt is historical, not the current HEAD.

Base and unchanged HEAD: `32408f6`. Result: **PARTIAL**. Nothing committed or
pushed. ADR-0188 remains reserved; README, canonical status, next steps and
progress data are unchanged. The hand input is **not retired** and the solver's
RSP-policy assumption remains open.

## Implemented hypothesis and scope

`plaid rsp-from-rom <rom> <map.json> <output-directory>` reconstructs canonical
raw/Yaz0/load/slot images through the existing `rom_images` path. The map must
match the canonical ROM hash. It collects aligned image pointers from data,
constant expressions in discovered CPU blocks, and the existing bounded
cross-block LUI/ADDIU/ORI search. The latter is factored before its CPU-function
content filter, preserving the old discovery behavior.

Pointers are search hints. A content filter requires decodable entry words and
RSP COP0/vector operations. Candidate text is lowered at the standard IMEM
placements 0 and 0x80. Rooted data windows also supply SDK-style descriptors:
u32 ucode-relative offset, u16 DMA length-minus-one, u16 SP destination.
Descriptor and microcode pairings are deliberately an overapproximation and
are checked by content. This finds F-Zero X's graphics overlays without any
snapshot input, game identification, names or addresses in production code.

The generated `rsp-files.json` is deterministic, hash-bound and explicitly
`complete: false`. Its candidate counts include placements, overlays and false
positives; they are **not a proven count of distinct game microcodes**. Native
code retains the existing per-word IMEM identity guards and fault stubs. There
is no runtime decoder, interpreter, JIT or snapshot fallback.

`native.py` now builds this ROM registry instead of its run/dump/lower/relink
feedback loop. It enables `PLAID_RSP_ROM`: before starting a task, boot bytes
must match a lowered candidate and a recognized boot's ucode DMA range must
match a lowered text. The boot DMA length, not a potentially ignored task
`ucode_size`, drives this conservative check. Synthetic tests deliberately
understate the task size and alter bytes beyond it. Unknown boot/text, that tail
mutation and an out-of-RAM pointer stop before any RSP output.

The bounded boot recognizer is **not a general boot-control-flow proof**. It
recognizes constant standard task transfers; arbitrary boot programs, multiple
or conditional executable transfers, and direct-loaded task conventions still
need a sound submission model before this feature can be accepted broadly.

## Local extraction and snapshot oracle

All ROMs/assets/generated C/binaries/captures remain ignored under `target/`.
No ROM-derived bytes are included in this note or synthetic fixtures.

| ROM | ROM candidate texts | Distinct candidate roots | Descriptor-derived texts | Extraction seconds | Retained snapshots covered |
| --- | ---: | ---: | ---: | ---: | --- |
| SM64 USA | 16 | 5 | 6 | 0.563 | 1/2 |
| OoT USA 1.2 | 38 | 14 | 10 | 1.875 | unavailable locally |
| MM USA | 34 | 10 | 14 | 2.734 | 1/1 |
| F-Zero X USA | 50 | 11 | 28 | 0.438 | 9/11 |

`runtime/check_rsp_rom.py <rsp-files.json> <snapshot-directory>` checks each
snapshot word against candidate words at the same IMEM position, excluding
trailing initialized zero padding. This is a strict retained-word oracle, not
an executable-reachability certificate. Its synthetic check rejects a forged
snapshot word. It never supplies discovery inputs or generates microcode.

The remaining SM64 snapshot has seven mismatching words from IMEM 0xea0
onward, beyond the audio instructions. The two remaining F-Zero X snapshots
have five/seven mismatching words at/after 0xd40, also in copied data following
the audio instructions. These are mutable RAM data, not fixed canonical ROM
bytes. Every retained F-Zero X graphics snapshot is covered. Do not discard or
mask these oracle failures to manufacture coverage; distinguishing executable
text from copied data is still an unresolved acceptance requirement.

Receipts: `target/rsp-from-rom/{sm64,fzerox,oot,mm}/rsp-files.json` and each
available set's `coverage.json`. Original snapshot inputs are
`target/local-inputs/rsp-snaps`, `target/native/fzerox/rsp-snaps`, and
`target/native/mm/rsp-snaps`. A bounded local inventory found no retained OoT
IMEM snapshot set; no coverage claim is made for it.

## Visible native evidence and refusal

Reused unchanged F-Zero X CPU objects; regenerated and linked only the ROM
registry and current runtime. Both runs used visible RT64 windows,
`--rsp-gfx`, a 20-second guest validation limit and a 45-second process timeout.
No snapshots were loaded by either executable.

- **Strict candidate:** exit 1, `unknown ROM-derived RSP microcode`, VI 8,
  first audio task, zero graphics tasks. F-Zero X submits audio as a direct
  0x1000-byte boot/text image at the same address, not through the recognized
  standard boot DMA contract. Its boot/text task sizes are both 0x1000.
- **Control only:** omit `PLAID_RSP_ROM` while retaining the existing native
  per-word guards, to isolate ROM extraction/lowering. Exit 0 at the time
  limit; VI 770; 479 graphics and 741 audio tasks; fault 0. Stereo PCM at 32006
  Hz has 400864 frames and peak 14537. This is **not acceptance of the new
  task-start policy**. Wall time 30.016 s including window/renderer lifetime;
  the strict run took 4.281 s including startup/shutdown.

The direct task's full-page snapshot is not byte-identical to canonical ROM
because of the mutable tail above. Supporting direct boot alone would not
solve the identity boundary. SM64's standard boot also copies a larger range
than its real audio instructions; blindly comparing that complete DMA range
is too strict for mutable copied data. A sound static text/data boundary and
submission/overlay model is the next required work. Per-word runtime safety is
already retained, but it does not prove the requested task-start identity rule.

Local artifacts: `target/rsp-from-rom/fzerox/{strict,control}.{stdout,stderr,wav}`.
`build_run.py` there records the local compile/run procedure. A separate visible
one-task control capture confirmed the direct-task fields; its data stay local.
Every process started for game validation exited; no game process was left.

## Validation on the shared candidate tree

- `cargo fmt --all -- --check`: PASS after formatting the new test.
- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS.
- `cargo test --locked --workspace`: PASS, **714 passed, 0 failed, 1 ignored**
  across 81 reported suites. Three new Rust tests cover pointers/descriptor
  bounds, boot DMA sizing and content filtering/lowering.
- `python scripts/test_cli.py`: PASS.
- `python runtime/test_runtime.py`: PASS, including one successful ROM-derived
  task and four startup refusals (boot, text, bytes beyond the advertised size,
  bad pointer), expected RDRAM/vector output, and the snapshot positive/forgery.
  Existing scheduling, RCP, audio, native graphics, ABI, capture, overlay and
  slot contracts also pass.
- Progress data were not changed, so no progress record/check was performed.
- Pinned ares HEAD is `9408cb43d4948fc3ea6e152a307a34348df3fe04`;
  inspected RSP io.cpp/dma.cpp match the pin. No reference implementation code
  was copied. This change adds discovery/identity guards rather than a new
  instruction transformation; existing lower-rsp semantic verifiers remain.

Initial checks exposed a stale debug dependency cache referring to an older
checkout; it incorrectly treated edited sources as fresh. `cargo clean -p
plaid-core` and rebuild restored genuine compilation; the new tests then ran.
The first full runtime attempt lacked Cargo on PATH in a nested contract; the
complete suite was rerun successfully with the toolchain directory on PATH.
These initial attempts are not counted as successful validation.

RSP compilation in the local run helper measured **12.015 s cold / 0.015 s
repeat** for the same 50 texts/registry (object reuse). The synthetic ROM test
also compiles text objects once and shares them across its five runtime builds,
instead of recompiling every text five times; no before wall-time baseline was
retained for that test-harness fix. Production native.py retains its existing
content/dependency/compiler/flag cache. No performance equivalence claim beyond
the checked outputs is inferred from these finite measurements.

Logs are in `target/rsp-from-rom/{cargo-test,clippy,cli-test,runtime-test}.log`.

## Ownership and exact remaining work

Owned paths/hunks:
- `apps/plaid/src/{main,rsp_rom}.rs`: CLI and registry generation.
- `crates/plaid-core/src/{lib,data_roots,rsp_rom}.rs`: root extraction and
  bounded boot/descriptor contracts, with synthetic unit tests.
- `crates/plaid-lower/src/rsp.rs`: only the new plausible_text filter;
  `crates/plaid-lower/tests/rsp_rom.rs`: its test.
- `runtime/plaid_rt.c`: only PLAID_RSP_ROM declarations and startup guard;
  `runtime/test_runtime.py`: only test_rsp_rom invocation.
- `runtime/{test_rsp_rom,check_rsp_rom}.py`, `scripts/native.py` ROM pipeline
  hunks, and this note.

Concurrent audio work owns the canonical shared-header generation change,
completion/capture checks, ABI tests, `--require-audio`, `runtime/README.md`,
`research/mm-audio.md`, and related paths. Those edits were preserved. Do not
stage entire mixed shared files as this worker's change.

Next: establish static executable boundaries inside task DMA ranges, handle
direct boot tasks, bind needed ucode_data/overlay descriptors to submissions,
prove or conservatively reject unsupported executable DMA, obtain/check an OoT
snapshot oracle, and rerun the complete gate plus a strict visible native run.
Only after all acceptance conditions pass should ADR-0188, README/status/next,
progress record/check and a commit be produced. The current candidate must not
be advertised as retiring the hand input or as an accepted fully native build.

## Continuation claim (2026-10-17)

Implementation worker on `rsp-from-rom`, prepared base `8139af6`, inherited
head `bede0e6`. Hypothesis: a direct-control-flow reachability certificate can
exclude DMA data, while unresolved register jumps must conservatively retain
the complete IMEM target set. Direct-loaded tasks should use the same content
check against their actual loaded IMEM. No narrowed indirect target assumption
will be silently substituted for a proof. No canonical writes or README edits.

## Continuation implementation and review

The original `0f7d83f` and inherited `bede0e6` trees compare byte-identical
(`git diff 0f7d83f bede0e6 --stat` is empty). The prepared port is complete,
and `bede0e6` descends from canonical `8139af6`. No audio fixes were dropped.

- `plaid-rsp-rom-v1` records conservative fetch-PC masks, unresolved register
  jumps and outgoing placement edges. Direct branches include both arms and
  delay-slot fetches; BREAK/fault terminates the supported native path.
  Independently entering a delay slot still traverses its fallthrough.
- Startup checks use these masks for task text. Proven data after a halt is
  excluded, but any unresolved register jump retains **every** word in the
  placement and records every external aligned IMEM target as an exit. A closed
  native switch does not establish a narrower hardware target set.
- Direct-loaded tasks match their actual initial IMEM rather than requiring a
  recognized rspboot. Boot lengths use the same doubleword rounding as loading.
  Standard boot tasks retain the conservative boot-byte check and check the
  recognized DMA's actual source span, irrespective of advertised ucode_size.
- `--rsp-dump` also records recognized dispatch placements. These are oracle
  outputs only; no snapshot is supplied to discovery, lowering or linking.
- Three new Rust tests cover fetch closure, both branch arms, delay slots,
  independent slot entry, external edges, invalid spans and conservative
  indirect jumps. Nine end-to-end synthetic tasks cover standard/direct
  success, reachable corruption (including beyond advertised text length),
  boot/pointer refusal, and permissible post-halt tail mutations. They verify
  native output and zero output on startup rejection. Existing instruction
  lowering and per-word identity guards are unchanged.
- Review mutation: deleting the indirect all-word expansion fails the focused
  test (exit 101); restoring the exact bytes returns 4/4 focused Rust tests to
  green. Log: `target/rsp-from-rom/reachability-mutation.log`.

### Why (a) remains open

The remaining SM64/F-Zero audio texts dispatch through `LH` from DMEM and
then `JR`; their target-table values and immutability are not proved. The
SM64 mismatches at/after IMEM 0xea0 are all lowerable words. F-Zero's
mismatches at/after 0xd40 include both lowerable words and a fault stub.
Neither a guessed prefix nor skipping fault stubs establishes an executable
boundary. The implementation therefore preserves these refusals and does not
claim full snapshot coverage. A next worker must prove the command-table
target set (including writes and executable DMA/overlays), or introduce an
explicitly verified and enforced supported dispatch model.

The bounded boot recognizer also remains a search contract, not a proof of
arbitrary conditional/multiple executable transfers. Direct-load identity
support is verified synthetically, but does not certify every different boot
program's subsequent executable DMA. All manifests remain `complete: false`;
the solver RSP-policy assumption is not retired.

### Continuation local gate

All five required gates pass on the final production/test source tree:

| Command | Result | Seconds |
| --- | --- | ---: |
| cargo fmt --all -- --check | PASS | 0.843 |
| cargo clippy --locked --workspace --all-targets -- -D warnings | PASS | 6.594 |
| cargo test --locked --workspace | 717 passed, 0 failed, 1 ignored; 81 suites | 93.516 |
| python scripts/test_cli.py | PASS | 2.844 |
| python runtime/test_runtime.py | PASS, including all 9 ROM task contracts | 136.515 |

Logs: `target/rsp-from-rom/{fmt,clippy,test,cli,runtime}-continuation.log`,
with statuses/timings in `gates-continuation.json`. The temporary review
mutation was restored byte-for-byte and its focused tests rerun successfully.
Progress data are unchanged; no progress record/check applies. README, ADR-0188,
STATUS and NEXT are intentionally unchanged because acceptance is incomplete.
Pinned ares remains `9408cb43d4948fc3ea6e152a307a34348df3fe04`; its RSP
DMA/io sources were inspected without copying reference code.

### Continuation timings

For this source tree, debug extraction took 2.171 / 2.344 / 27.250 / 30.922 s
for SM64 / F-Zero / MM / OoT. Selecting the release compiler for the same
workload reduced those to 0.547 / 0.375 / 2.515 / 1.610 s, with the same
16 / 50 / 34 / 38 candidate counts. This is a build-profile/tool-selection
measurement, not a new analysis optimization. F-Zero RSP object compilation
was 6.515 s cold versus 0.156 s cached with source/header/flag digests.
The large MM runtime compile remained expensive; its object is cached by the
local run helper. No output-equivalence claim is inferred beyond the tests
and finite visible runs.

### Continuation coverage and visible runs (final, still PARTIAL)

| ROM | ROM candidates (placements included) | Raw snapshot images covered |
| --- | ---: | ---: |
| SM64 USA | 16 | 1/2 |
| OoT USA 1.2 | 38 | 1/4 unique combined oracle images |
| MM USA | 34 | 1/1 |
| F-Zero X USA | 50 | 9/11 |

SM64/F-Zero/MM checks use the original retained sets and the unchanged strict
word-content oracle. OoT now has four unique byte images: the current native
ROM-registry failure snapshot plus before/after captures of the retained
executable's first type-4 task and first audio task. Identical before/after
audio images are deduplicated by SHA-256; no failing image was removed.
Provenance: `target/rsp-from-rom/oot/snapshots-combined-unique/provenance.json`;
report: `coverage-combined-unique.json`. These files remain ignored. Captures
never feed the ROM compiler or registry. The two bootstrap variants each have
7 unknown words; the post-bootstrap image has 325. The audio image is covered.
This is oracle acquisition and partial verification, **not full OoT coverage**.

- **MM, strict ROM registry, visible RT64:** 60-second guest limit, 100-second
  process timeout; exit 0 at the time limit, wall 61.328 s, VI 3549, graphics
  tasks 1242, audio tasks 3495, fault 0. Stereo PCM: 1,870,752 frames at
  32006 Hz, peak 31417. The same `native_audio.audio_peak` check used by
  `native.py --require-audio` passes. The window was confirmed as visible
  (`MainWindowTitle=RT64`, nonzero window handle). No snapshot text linked.
- **F-Zero, strict ROM registry, visible RT64, --rsp-gfx:** 20-second guest
  limit, 60-second timeout; exit 1, wall 5.406 s, VI 10, first audio task,
  zero graphics tasks. Stop: unknown ROM-derived RSP microcode. Direct loading
  is supported, but conservative indirect reachability still compares the
  mutable tail, so neither game nor required-audio acceptance is achieved.
- **OoT, strict ROM registry, visible RT64:** exit 1 at VI 2, wall 1.297 s,
  first non-graphics task (type 4, not audio); unknown ROM-derived RSP microcode.
  A separate ROM-registry control with the startup check disabled produces an
  IMEM snapshot but faults at RSP PC 0xc0: an SP write attempts to overwrite
  RAM that the newly generated CPU map protects as executable (CPU fault 2).
  No protection or semantic check was bypassed to make this run succeed.
- **OoT, retained executable, oracle only:** visible, timed runs with
  --rsp-dump and --rsp-capture retain the type-4 task and first audio task.
  Both exit 0; independently inspected after states are halted=1, broken=1,
  PC 0x90 and 0xb8. The audio capture reaches VI 236 and 230 graphics tasks.
  This pre-existing snapshot-backed executable is **not** ROM-derived
  acceptance evidence. Its captures are only byte-content test oracles.

Local reproduction: `python target/rsp-from-rom/extract-release-continuation.py`
recreates all four registries. `build_run_continuation.py fzerox mm oot` records
the strict build flags/CPU maps/run commands, using only manifest-listed ROM
objects. The expensive diagnostic OoT control compile was interrupted after
its strict run; only that helper and its child compilers were terminated, and
the interrupted object/stamp were removed. `capture_oracle_continuation.py oot`
uses an O0 host runtime (CPU and RSP objects remain O1), to capture the diagnostic
without another slow O1 runtime compile. Runtime compilation: approximately
173 s O1 versus 13.909 s O0; both diagnostic variants are unaccepted controls,
not a production optimization or game-equivalence claim. All game processes
started here exited or were bounded by subprocess timeouts. No own game or
compiler process remains.

Exact next work: prove/guard the DMEM dispatch-table target and write policy for
SM64/F-Zero; establish the origins/transformations of OoT's bootstrap images;
resolve the CPU-map protection conflict for its type-4 task without blanket
unprotection or a game-specific exception; then rerun full snapshot checks,
strict visible F-Zero/MM and the complete local gate. ADR-0188 remains reserved.

Retained OoT oracle executable SHA-256:
`714526347388fd48704090e3b1aaf0706dbcc786ed18fccbeb476f77d32c7ce1`.
Its source/binary provenance is not independently re-established here, so the
captured boot/audio images are finite comparison inputs, not a pinned-reference
semantic proof.

## Fetch-verified dispatch continuation (2026-10-17)

Claim: select a unique ROM-derived candidate by entry words reachable without
indirect transfers. Per-word IMEM identity checks and closed native dispatch
(ADR-0167) enforce every later fetch, including mutable tails. Unknown or
ambiguous startup matches refuse. Direct-loaded tasks use the same contract.
This replaces the predecessor requirement for a static text/data partition.
No snapshots enter compilation; no interpreter/JIT or game exceptions.

### Implemented dispatch policy and deterministic evidence

The manager authorized the ADR-0167 native dispatcher plus per-word fetch guards
as the enforced supported model. Static entry reachability stops at each JR/JALR
without abandoning other pending branch paths. Both standard-boot text and
direct-loaded tasks require exactly one mask match; zero or ambiguous matches
refuse. Recognized boots use this same mask, then their actual DMA span for text.
No mutable tail is trusted: every later instruction still passes its IMEM fetch
guard. The default native.py already used rsp-from-rom and PLAID_RSP_ROM; verified
it has no snapshot loader and added oracle-only --rsp-dump forwarding.

Four focused Rust tests pass. Fourteen end-to-end ROM contracts pass: the prior
nine standard/direct state/output and startup cases, plus a synthetic LH/JR
dispatch with unchanged code, a changed JR target (refuses at PC 040), a changed
fallthrough word (refuses at PC 044), changed unexecuted data (succeeds), and a
duplicate startup candidate (refuses). These cases use synthetic ROM bytes only.
Retained strict snapshot-word mismatches remain oracle results and were not
masked or deleted to manufacture coverage; they no longer define task acceptance.

### Final visible ROM-only runs

All linked RSP objects came exclusively from each ROM-derived manifest. No
snapshot objects were linked. Runtime and generated native RSP guards stayed on.
RT64 windows remained visible (MM and SM64 observed with nonzero window handles).
The same native_audio.audio_peak checker used by --require-audio passed all
three accepted runs. Guest limits were 20/60/20 seconds, with process timeouts
of 60/100/60 seconds for F-Zero/MM/SM64. CPU objects were reused for F-Zero/MM;
SM64 was regenerated from its retained map for the current runtime ABI.

| ROM | VIs | Graphics tasks | Audio tasks | Fault | PCM peak |
| --- | ---: | ---: | ---: | ---: | ---: |
| F-Zero X USA (--rsp-gfx) | 1147 | 858 | 1135 | 0 | 18001 |
| MM USA | 3553 | 1243 | 3484 | 0 | 31471 |
| SM64 USA | 1157 | 552 | 1148 | 0 | 28039 |

PCM stereo frames: 608608 / 1866656 / 612848 respectively, 32006 Hz.
Local artifacts: target/rsp-from-rom/<game>/strict-fetch.{stdout,stderr,wav};
reproduction: extract-release-continuation.py then build_run_fetch.py under the
same ignored directory. No ROM bytes, generated microcode or game assets in git.

OoT USA 1.2 builds with the ROM-only registry but refuses at VI 2: zero
graphics tasks, one non-graphics task counted in audio_tasks (type 4, not an
audio acceptance), CPU fault 2, RSP fault 1 at IMEM 0c0. The RSP's RDRAM write
callback enforces CPU executable-memory protection, matching the predecessor's
control diagnosis. No protection was bypassed. PCM contains zero frames; peak
is unavailable. This is not an accepted ROM, nor evidence of audible output.
Wall times: F-Zero 25.235 s; MM 61.578 s; SM64 24.625 s; OoT 1.266 s. All native processes exited under the specified timeouts.

### Validation, performance and review

All Rust gates pass: fmt 1.062 s; strict workspace/all-target Clippy 1.469 s;
workspace tests 19.750 s, 717 passed, 0 failed, 1 ignored across 81 reported
suites. CLI passes (rerun after --rsp-dump forwarding); progress --check passes.
Progress data did not change: the RSP executable-universe milestone stays partial
and no assumption is retired, so --record is not applicable. README is unchanged.

No new optimization changes outputs. Reusing the predecessor's per-source RSP
object cache avoids repeated lowering compilation: F-Zero's recorded cold
6.515 s becomes 0.094 s cached here (registry regenerated); MM 0.156 s cached.
Release extraction now measured 0.422/0.312/1.969/1.266 s for SM64/F-Zero/MM/OoT
with unchanged 16/50/34/38 candidate counts. SM64's obsolete single CPU unit
cannot compile against the current runtime; generating 16 parts and compiling
them in parallel takes 31.234 s (no comparable old ABI build succeeds).

Initial runtime attempts exposed a stale debug CLI, then two fixture setup
errors (the content filter needs two RSP-specific operations, and modifying a
ROM requires rediscovery rather than merely replacing the top-level map hash).
Corrected fixture rediscovery preserves normal provenance validation. These
failed attempts are not passing gates. Focused final 14-contract run: 32.562 s.

Code review checks startup bounds/uniqueness, direct/indirect delay behavior,
all later fetch guards, synthetic failure PCs and asset exclusion. No reference
code copied. Pinned ares HEAD remains 9408cb43d4948fc3ea6e152a307a34348df3fe04;
RSP io.cpp/dma.cpp inspected for the retained doubleword-rounded load contract.
The remaining work is OoT bootstrap/protection compatibility, broader ROM
coverage and general executable-universe/loader/timing proof, not a guessed
static audio text/data boundary.

Final complete runtime gate: PASS, 117.266 s, including all 14 ROM contracts,
ABI mutation, completion/capture, scheduling, RCP/AI, native graphics, overlay
and shared-slot contracts. Gate receipts/logs: target/rsp-from-rom/gates-fetch.json
and {fmt,clippy,test,cli,runtime}-fetch.log (final CLI: cli-fetch-final.log).
Review mutation: invert the direct-mask indirect-transfer predicate; focused
tests fail (exit 101). Restore the exact original bytes: 4/4 pass. Log:
review-mutation-fetch.log. The initially attempted byte replacement did not
match CRLF and changed nothing; the actual mutation was then applied and tested.
All five gates and progress consistency pass on the restored production tree.
No own native/game/compiler process remains. Branch rsp-from-rom; no push or
canonical main write. This is accepted for three finite ROM paths, partial
corpus support because OoT refuses; no whole-ROM claim.
