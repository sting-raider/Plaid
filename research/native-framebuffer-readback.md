# Native framebuffer readback

## Claim and reproduction

BK displays puzzle-piece outlines but black interiors during loading
transitions. The shared RT64 bridge synchronizes native CPU RAM into its
private RDRAM, but does not return rendered pixels. The native game later
reads framebuffer data from CPU RAM. Hypothesis: missing renderer-to-CPU
transfers cause the black interiors.

An ignored diagnostic build adds only a full-RDRAM value comparison/copyback
after graphics submissions. With copyback enabled, colored puzzle images
appear; with it disabled, the user observes black interiors again. Both use
the same compiled game/RSP objects, fresh EEPROM and scripted Start/A inputs.
This isolates the transfer direction; the diagnostic bypasses cache/protection
and is not the production implementation.

Local inputs, generated objects, scripts, saves and captures remain ignored
under `target/bk-puzzle/`; no game bytes or images are committed.

## Pinned source and correction

RT64 is pinned at `43373749dac9bbc1b653e6a02aed40a9e1783bed`.
`src/hle/rt64_state.cpp`, `State::fullSync`, waits for framebuffer rendering,
then calls `Framebuffer::copyNativeToRAM` separately for color and depth.
`src/hle/rt64_framebuffer.cpp` and `src/render/rt64_native_target.cpp` complete
GPU readback and install word-swapped bytes in the bridge's private RDRAM.
The default emulator configuration enables rendering to RAM.

Extend Plaid's existing source-copy patch mechanism to report each completed
row span after those calls. The bridge records physical offsets/lengths,
converts bytes by absolute `(physical + index) ^ 3`, and delivers the spans
after the synchronous renderer job returns, while the runtime owns the guest
execution baton. The same seam serves display-list HLE and compiled-RSP raw
RDP submissions. The pinned checkout is not modified.

For each span, `plaid_runtime_write` validates bounds and executable protection
before `dma_wrote` preserves resident cache bytes and handles complete lost
lines. Only then are guest RAM and the bridge's input snapshot updated.
Do not infer coverage from unequal bytes: equal-valued transfers still apply
cache policy. Do not mark neighboring bytes seen or overwrite unsynchronized
pages. Refusal propagates as an explicit guest fault, without committing that
span. Earlier accepted spans may already have completed.

These are completed host readback transfers, not individual RDP pixel-write
witnesses. The existing RT64 rendering/timing assumptions are retained.
No ROM names, expected game words, guest addresses or game-code patches occur
in production; test addresses belong only to synthetic programs. No guest
interpreter or JIT is introduced, and no assumption is retired.

## Verification

`runtime/rt64/test_rdp.cpp` exercises the actual transfer helper without a GPU:
unaligned/partial byte order, two exact spans, same-valued callbacks, refusal
preserving the snapshot, and a RAM-boundary rejection. The CMake build also
requires each pinned patch context to match exactly once.

`runtime/test_gfx_readback.py` drives a synthetic native guest through graphics
submissions: cached old versus uncached new values, explicit invalidation and
refill, unchanged neighboring data, equal-valued transfers, partial/full
lost-line behavior, protected executable text, and bounds refusal without a
partial overwrite. An isolated mutation removing pre-write cache bookkeeping
fails on the cached-old assertion; the tracked source stays unchanged.

Visible production BK runs, 75 seconds each, finish at fault 0:

| Run | VI | Graphics tasks | Audio tasks | PI transfers |
| --- | ---: | ---: | ---: | ---: |
| First | 4471 | 1691 | 2231 | 6325 |
| Repeat with transition captures | 4477 | 1689 | 2234 | 6327 |

The captured title-screen pieces contain the title image; the closing
file-select puzzle contains Banjo and the room image. Evidence is retained
locally as `production2-seq-25.png` and `production2-seq-45.png`. Finite visual
coverage does not establish a complete playthrough, correct mixing or
pixel-perfect rendering. BK's previously documented compiled-RSP graphics
entry fault is independent and remains open.

The prior diagnostic baseline and corrected runs both maintain approximately
59.6 VI/s over 75 seconds. This is an iteration-rate sanity check, not an
isolated GPU/readback benchmark; frame scheduling and host wall time vary.
The production correction adds no whole-RAM readback scan. Incremental BK
runtime compile/link took 6.701 seconds while reusing generated CPU/RSP objects.

Shared-renderer controls also complete visibly with scripted input and fault 0:
Majora's Mask display-list HLE, 30 seconds, VI 1764 and PCM peak 32768;
F-Zero X compiled-RSP/raw RDP, 30 seconds, VI 1784 and peak 15734.
Peak amplitude establishes nonempty output, not mixing fidelity. Control saves
are isolated copies. Existing generated native executables must be relinked
with the changed graphics callback ABI; the normal builder invalidates runtime
objects when shared headers change.

Commands: `cmake --build target/rt64-shim --config Release --target plaid_rt64`,
`python runtime/test_runtime.py`, and the repository's local fmt/Clippy/Rust/CLI
gate. Exact committed-tree results and shared-renderer controls are recorded
in the integration closeout and ignored `target/bk-puzzle/` receipts.
