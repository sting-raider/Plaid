# Primary integration: AI DMA timing and live audio

Base: 8829e51. Milestone 4 (audio). Worker: Claude co-integrator,
user-authorized on main, running autonomously.

**ADR-0170:** the runtime models the AI as pinned ares does: a two-entry DMA
FIFO drained at the DAC rate on the host clock. That gives the game
`osAiGetLength`, `osAiGetStatus`, the full-FIFO refusal and the AI event per
buffer start. With RT64, each buffer plays through SDL (`plaid_audio_play`
in the shim).

Result:
- `runtime/test_runtime.py` checks the FIFO, the status bits, the event
  timing (one buffer of DAC time, measured in COUNT ticks) and the samples
  sent to the WAV file and the host.
- SM64 runs 30 s with no fault and 1768 audio tasks. Its audio keeps pace:
  29.5 s of audio (31.3 s before).
- The user played past the title with live audio and confirmed it works.

Gate on the exact tree, all passing:

- `cargo fmt --all -- --check`
- `cargo clippy --locked --workspace --all-targets -- -D warnings`
- `cargo test --locked --workspace`
- `python scripts/test_cli.py`
- `python runtime/test_runtime.py`
- spike096
- `tools/progress.py --record` and `--check`
- the RT64 shim rebuilt with MSVC

plaid-lower is unchanged, so spike097 and spike098 do not apply. The ROM
and its audio stay local. Actions were not used. `native_complete` stays
false.
