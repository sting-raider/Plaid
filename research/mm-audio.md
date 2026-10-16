# Native audio investigation (ADR-0189 reserved)

Owner: MM audio implementation worker; shared checkout with ROM RSP worker.

Hypotheses: AI address/length translation, RSP DMA/vector semantics, stale/incomplete snapshot or generated text ABI, SDK audio ABI.

Initial observation: visible MM capture task 100 has peak 0 and no native RSP state/memory changes. Pinned ares executes 12,687 instructions and changes 26 RDRAM bytes and 144 DMEM bytes. Native generated text under target/native/mm embeds the old plaid_rsp layout without the DPC callback, while the runtime uses the current layout with that callback. Header cache invalidation recompiles stale embedded layouts without repairing them. Testing regeneration and relink separately before production edits.

## Proven cause and fix

The retained `target/native/mm/rsp-texts/imem_000_49c70fc5.c` embedded a private
`plaid_rsp` definition predating ADR-0186's DPC callback. `runtime/plaid_rt.c`
used the new struct, so native RSP functions accessed the wrong state offsets.
Recompiling stale generated C against changed header dependencies did not repair
that private definition. The task count reported submissions, not valid halts.
Task 100's native before/after state was identical (including halted=0), while
pinned ares executed 12,687 instructions. `--rsp-capture` also reported success
before checking the task's return code, hiding that invalid completion.

Regenerating the same snapshot (unchanged IMEM bytes) and relinking **only** RSP
objects, keeping the CPU/runtime objects and AI model unchanged, restored full
spike098 agreement. This isolates the cause from AI translation, SDK buffer
functions, incorrect snapshot bytes, and vector/DMA instruction semantics.

Lowered RSP C now includes canonical `rsp_state.h`, and the host requires a
successful task to halt before capture acceptance. The retained-source ABI test
compiles two translation units, changes only their shared header layout, and
checks registers, PC, DMEM and halt/fault state. It fails with the old generator
(Windows assertion exit 3221226505), and passes both layouts after the fix.
Capture tests reject unknown code and success returned without halting.
`scripts/native.py --require-audio` records validation.wav and rejects silent or
empty PCM; three synthetic WAV cases exercise the check.

## Local evidence (no game bytes tracked)

- MM regenerated text, visible 60 seconds: peak 32768, 1,887,968 stereo frames,
  VI 3573, 3515 audio tasks, 1553 graphics tasks, fault 0.
- MM captured task 600, visible: WAV peak 30966; pinned ares
  9408cb43d4948fc3ea6e152a307a34348df3fe04 matches all RDRAM, IMEM,
  DMEM, scalar/vector/status state after 68,317 instructions; 4,599 RDRAM bytes
  changed. Task 100 also matches completely after regeneration.
- SM64 freshly lowered and rebuilt with the fix, visible 15 seconds: peak
  28116; VI 878, 864 audio tasks, 420 graphics tasks, fault 0.
- RSP-only regeneration, compilation and relink reused unchanged CPU objects:
  4.140 seconds. Fresh SM64 lower/compile/snapshot discovery/15-second validation:
  135.760 seconds (CPU lowering 17.626; CPU compilation through 93.742 seconds).
- Captures, hashes, WAVs, build logs and exact gate results are under ignored
  `target/mm-audio/`; the independent oracle source is not linked into games.

## Shared-checkout integration

Audio hunks share `crates/plaid-lower/src/rsp.rs`, `runtime/plaid_rt.c`,
`runtime/test_runtime.py` and `scripts/native.py` with the active ROM-derived RSP
worker. Do not stage those entire files while their edits are mixed. Audio-only
paths: `crates/plaid-lower/tests/rsp.rs`, `spikes/097-rsp-slice/run.py`,
`scripts/native_audio.py`, `scripts/test_native_audio.py`, and this note;
`runtime/README.md` had no pre-existing edits when updated. No commit or push
is allowed until ownership can be isolated as requested. ADR-0188 stays reserved
for the other worker; ADR-0189 records this fix after the full gate.

## Final rebuilt artifact

A fresh O1 runtime build took 232.779 seconds, and current-compiler RSP
regeneration/compile/relink took 7.680 seconds. The final `mm-audio.exe`, with
completion checks active and shared-header generated texts, completed another
visible erased-save 60-second run: peak **32569**, 1,832,784 stereo frames,
VI 3571, 3410 audio tasks, 2310 graphics tasks, fault 0. The preceding RSP-only
repair peaked at 32768; host-clock task scheduling makes exact game-run peaks
and task counts vary. SM64's fresh build remained at peak **28116**.

Review (code-review-and-quality skill): checked the generated-C callers,
canonical header compilation, narrow RSP completion boundary, opt-in WAV gate,
synthetic layout mutation, capture failures and signed PCM extremes. No N64
instruction transformation or audio address translation changed, and no game
identification, asset, reference implementation code or runtime interpreter/JIT
was introduced. Whole-ROM closure assumptions are unchanged.

## Final validation and handoff

- `cargo clippy --locked --workspace --all-targets -- -D warnings`: PASS on
  the current combined tree after the other worker corrected its chunk lint.
- `cargo test --locked --workspace`: PASS, 714 tests, 0 failures, 1 ignored.
- `python scripts/test_cli.py`: PASS (8.757 seconds).
- `python scripts/test_native.py`: PASS (cache invalidation and failed rebuilds).
- `python scripts/test_native_audio.py`: PASS, three WAV cases.
- Spike097: PASS, 27 positive cases and four fail-closed cases.
- Final real-task spike098: PASS, 68,417 instructions, 4,641 changed RDRAM
  bytes, full captured state/memory equality (oracle600-final.log).
- `cargo fmt --all -- --check`: final PASS (fmt-final.log). An earlier run
  exposed formatting in the other worker's new RSP test; that worker fixed it.
- `python runtime/test_runtime.py`: final PASS, 147.108 seconds, 15 contract
  families including the two new audio/RSP ABI and completion checks.
- The full runtime gate runs with `PLAID_RUNTIME_TEST_OUT` pointing inside
  `target/mm-audio/runtime-gate` so simultaneous validation cannot collide in
  the main runtime fixture directory. Exact logs/results: gate.json/gate-*.log.

No files staged and no commit or push. Required audio changes remain mixed
with ROM-RSP changes in four tracked files. `target/mm-audio/audio-only.patch`
preserves only the audio work against the other worker's semantic edits;
`git apply --reverse --check` verifies its ownership boundary against the
working tree. This is a patch for an integrator, not permission to stage the
mixed files. ADR-0189 is recorded in docs/DECISIONS.md with a short docs/STATUS.md note;
ADR-0188 remains reserved. The draft is also retained under target/mm-audio/.

`mm-rt64.exe` was absent from the process list when refreshed from the final
visibly validated `mm-audio.exe`. Both SHA-256:
5e8bead6dae1afca35f74c94d9a21c7c3cffe56475dc655dae1a6eb0594472e5.
Use target/rt64-shim/Release/mm-rt64.exe with the existing ROM/save launcher.
