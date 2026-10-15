# Primary integration: RSP tasks from IMEM snapshots

Base: bab784c. Milestone 4 (audio). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0169:** IMEM is plain bytes that DMA can rewrite. A lowered text is a
4 KiB IMEM snapshot found by running the game, not a ROM offset, and it runs
a word only while IMEM still holds it. The runtime does libultra's
`osSpTaskLoad` and `osSpTaskStartGo` for tasks other than graphics, picks
the text that holds the current word, and fails closed when none does.
`--rsp-dump` saves the missing snapshot, and `runtime/rsp_texts.py` lowers
it. DPC_STATUS reads an idle RDP. `--wav` writes the audio buffers.

Result:
- SM64 needs two snapshots (rspboot at IMEM 000, aspMain at 080). It runs
  20 s with 1190 audio tasks and no fault.
- A 30 s WAV at 32006 Hz holds the intro and title audio. The user listened
  to it and confirmed it.
- spike098 (new) matches pinned ares 9408cb43 exactly, in all of RDRAM, IMEM,
  DMEM and the RSP state, on real tasks 1 (6478 instructions) and 600 (94150
  instructions, 2972 RDRAM bytes). Task 600's after-state RDRAM sha256 is
  `bacd6668d83a4011f8bdc94e952b9d9ef31f8a3e022150afb4f3849666f721dc`.
- spike097 adds `dma_imem` and `dpc_status`; `imem_stale` stays a fault.
- `runtime/test_runtime.py` runs an rspboot-shaped task through the snapshot
  protocol.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096: passing.
- spike097 with `--rebuild` (the driver changed): passing.
- spike098 with `--rebuild`: passing.
- `tools/progress.py --record` and `--check`

The ROM, snapshots, lowered microcode, captures and WAV stay local. Actions
were not used. `native_complete` stays false.
